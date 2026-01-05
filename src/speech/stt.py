"""Speech-to-text using Whisper."""

from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

from src.core.config import WhisperConfig


class WhisperSTT:
    """Speech-to-text using faster-whisper."""

    def __init__(self, config: WhisperConfig, microphone_device: int | None = None):
        self.config = config
        self.microphone_device = microphone_device  # None = system default
        self.model: WhisperModel | None = None
        self.sample_rate = 16000
        self.is_recording = False
        self._audio_buffer: list[np.ndarray] = []

    def load_model(self) -> None:
        """Load the Whisper model."""
        device = self.config.device
        if device == "auto":
            device = "cuda" if self._cuda_available() else "cpu"

        compute_type = "float16" if device == "cuda" else "int8"

        self.model = WhisperModel(
            self.config.model_size,
            device=device,
            compute_type=compute_type,
        )

    def _cuda_available(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def transcribe_file(self, audio_path: Path | str) -> str:
        """Transcribe audio from a file."""
        if self.model is None:
            self.load_model()

        segments, _ = self.model.transcribe(
            str(audio_path),
            language=self.config.language,
            beam_size=self.config.beam_size,
        )

        return " ".join(segment.text for segment in segments).strip()

    def transcribe_audio(self, audio: np.ndarray) -> str:
        """Transcribe audio from numpy array."""
        if self.model is None:
            self.load_model()

        segments, _ = self.model.transcribe(
            audio,
            language=self.config.language,
            beam_size=self.config.beam_size,
        )

        return " ".join(segment.text for segment in segments).strip()

    def start_recording(self) -> None:
        """Start recording audio from microphone."""
        self._audio_buffer = []
        self.is_recording = True

        def callback(indata, frames, time, status):
            if self.is_recording:
                self._audio_buffer.append(indata.copy())

        self._stream = sd.InputStream(
            device=self.microphone_device,
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=callback,
        )
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return audio data."""
        self.is_recording = False
        self._stream.stop()
        self._stream.close()

        if self._audio_buffer:
            audio = np.concatenate(self._audio_buffer, axis=0)
            return audio.flatten()
        return np.array([])

    def record_and_transcribe(self, duration: float = 5.0) -> str:
        """Record for a fixed duration and transcribe."""
        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            device=self.microphone_device,
        )
        sd.wait()
        return self.transcribe_audio(audio.flatten())

    def save_audio(self, audio: np.ndarray, path: Path | str) -> None:
        """Save audio to file."""
        sf.write(str(path), audio, self.sample_rate)
