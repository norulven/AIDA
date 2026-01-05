"""Wake word detection for Aida using separate process."""

from multiprocessing import Process, Queue, Value
import numpy as np
import time
import ctypes

from PySide6.QtCore import QObject, Signal, QTimer


def _wake_word_process(wake_word: str, model_size: str, microphone_device: int | None, muted_flag, running_flag, event_queue: Queue):
    """Run wake word detection in a separate process."""
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from scipy import signal
    import threading

    # Load model in this process
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # Use 48000 Hz for recording, resample to 16000 for Whisper
    record_rate = 48000
    whisper_rate = 16000
    chunk_duration = 1.5

    event_queue.put("info:Wake word listener started")

    while running_flag.value:
        # Check mute status - if muted, just sleep
        if muted_flag.value:
            time.sleep(0.1)
            continue

        try:
            # Use callback-based recording so we can abort if muted
            audio_buffer = []
            recording_aborted = threading.Event()
            samples_needed = int(chunk_duration * record_rate)

            def audio_callback(indata, frames, time_info, status):
                # Check if we should abort recording
                if muted_flag.value or not running_flag.value:
                    recording_aborted.set()
                    raise sd.CallbackAbort()
                audio_buffer.append(indata.copy())

            # Start recording with callback
            with sd.InputStream(
                device=microphone_device,
                samplerate=record_rate,
                channels=1,
                dtype=np.float32,
                callback=audio_callback,
                blocksize=int(record_rate * 0.1),  # 100ms blocks for quick mute response
            ):
                # Wait for enough samples or abort
                start_time = time.time()
                while not recording_aborted.is_set():
                    current_samples = sum(len(buf) for buf in audio_buffer)
                    if current_samples >= samples_needed:
                        break
                    if time.time() - start_time > chunk_duration + 0.5:
                        break  # Timeout safety
                    time.sleep(0.05)

            # If recording was aborted due to mute, discard
            if recording_aborted.is_set() or muted_flag.value:
                continue

            # Combine audio buffers
            if not audio_buffer:
                continue
            audio = np.concatenate(audio_buffer)

            # Resample to 16000 Hz for Whisper
            audio_flat = audio.flatten()
            num_samples = int(len(audio_flat) * whisper_rate / record_rate)
            audio_resampled = signal.resample(audio_flat, num_samples).astype(np.float32)

            # Check again before transcription (transcription takes time)
            if muted_flag.value:
                continue

            # Transcribe
            segments, _ = model.transcribe(
                audio_resampled,
                language="en",
                beam_size=3,
                no_speech_threshold=0.4,
            )

            text = " ".join(s.text for s in segments).lower().strip()

            # Final check before emitting - must not be muted
            if not muted_flag.value and wake_word.lower() in text:
                event_queue.put("wake_word_detected")
                time.sleep(0.5)  # Brief pause after detection

        except sd.CallbackAbort:
            continue  # Recording was aborted, try again
        except Exception as e:
            event_queue.put(f"error:{e}")
            time.sleep(1)


class WakeWordListener(QObject):
    """Wake word listener using separate process to avoid Qt conflicts."""

    wake_word_detected = Signal()
    error = Signal(str)

    def __init__(self, wake_word: str = "aida", model_size: str = "tiny", microphone_device: int | None = None):
        super().__init__()

        self.wake_word = wake_word
        self.model_size = model_size
        self.microphone_device = microphone_device  # None = system default

        self._process: Process | None = None
        self._event_queue: Queue | None = None
        self._muted_flag = None  # Shared Value for instant muting
        self._running_flag = None
        self._timer: QTimer | None = None

    def start(self) -> None:
        """Start the wake word listener process."""
        if self._process is not None:
            return

        # Create shared flags for instant communication
        self._muted_flag = Value(ctypes.c_bool, False)
        self._running_flag = Value(ctypes.c_bool, True)
        self._event_queue = Queue()

        # Start process
        self._process = Process(
            target=_wake_word_process,
            args=(self.wake_word, self.model_size, self.microphone_device, self._muted_flag, self._running_flag, self._event_queue),
            daemon=True,
        )
        self._process.start()

        # Start timer to poll for events
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_events)
        self._timer.start(100)

    def stop(self) -> None:
        """Stop the wake word listener."""
        if self._timer:
            self._timer.stop()
            self._timer = None

        if self._running_flag:
            self._running_flag.value = False

        if self._process:
            self._process.join(timeout=3)
            if self._process.is_alive():
                self._process.terminate()
            self._process = None

        self._event_queue = None
        self._muted_flag = None
        self._running_flag = None

    def mute(self) -> None:
        """Mute wake word detection instantly."""
        if self._muted_flag:
            self._muted_flag.value = True
            # Clear any pending events to prevent stale detections
            if self._event_queue:
                try:
                    while not self._event_queue.empty():
                        self._event_queue.get_nowait()
                except:
                    pass

    def unmute(self) -> None:
        """Unmute wake word detection."""
        if self._muted_flag:
            self._muted_flag.value = False

    # Aliases for compatibility
    def pause(self) -> None:
        self.mute()

    def resume(self) -> None:
        self.unmute()

    def _check_events(self) -> None:
        """Check for events from the worker process."""
        if self._event_queue is None:
            return

        try:
            while not self._event_queue.empty():
                event = self._event_queue.get_nowait()
                if event == "wake_word_detected":
                    # Double-check mute status before emitting
                    if self._muted_flag and not self._muted_flag.value:
                        self.wake_word_detected.emit()
                elif event.startswith("error:"):
                    self.error.emit(event[6:])
        except:
            pass
