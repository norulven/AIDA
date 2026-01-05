"""Text-to-speech using Piper."""

import subprocess
import tempfile
from pathlib import Path

from src.core.config import PiperConfig


class PiperTTS:
    """Text-to-speech using Piper - uses system audio player to avoid Qt conflicts."""

    PIPER_CMD = "piper-tts"

    def __init__(self, config: PiperConfig, speaker_device: str | None = None):
        self.config = config
        self.speaker_device = speaker_device  # PulseAudio sink name, None = default
        self._model_path: Path | None = None
        self._current_process: subprocess.Popen | None = None
        self._ensure_voice_available()

    def _ensure_voice_available(self) -> None:
        """Ensure the voice model is available."""
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        model_file = self.config.data_dir / f"{self.config.voice}.onnx"
        if model_file.exists():
            self._model_path = model_file

    @property
    def model_path(self) -> Path | None:
        """Get the path to the voice model."""
        if self._model_path is None:
            model_file = self.config.data_dir / f"{self.config.voice}.onnx"
            if model_file.exists():
                self._model_path = model_file
        return self._model_path

    def _paplay_cmd(self, raw: bool = False) -> list[str]:
        """Build paplay command with optional device."""
        cmd = ["paplay"]
        if self.speaker_device:
            cmd.extend(["--device", self.speaker_device])
        if raw:
            cmd.extend(["--raw", "--rate=22050", "--channels=1", "--format=s16le"])
        return cmd

    def speak(self, text: str) -> None:
        """Synthesize and play speech (blocking)."""
        if self.model_path is None:
            raise RuntimeError(f"Voice model not found: {self.config.voice}")

        # Pipe directly to paplay/aplay to avoid Python audio libraries
        try:
            # piper-tts outputs raw audio, pipe to paplay (PulseAudio)
            piper = subprocess.Popen(
                [
                    self.PIPER_CMD,
                    "--model", str(self.model_path),
                    "--output-raw",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            player = subprocess.Popen(
                self._paplay_cmd(raw=True),
                stdin=piper.stdout,
                stderr=subprocess.PIPE,
            )

            # Send text and wait
            piper.stdin.write(text.encode())
            piper.stdin.close()
            player.wait()
            piper.wait()

        except FileNotFoundError as e:
            # Fallback to file-based approach
            self._speak_via_file(text)

    def _speak_via_file(self, text: str) -> None:
        """Fallback: synthesize to file and play with aplay."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = Path(f.name)

        try:
            subprocess.run(
                [
                    self.PIPER_CMD,
                    "--model", str(self.model_path),
                    "--output-file", str(output_path),
                ],
                input=text,
                text=True,
                capture_output=True,
                check=True,
            )

            # Play with aplay or paplay
            try:
                subprocess.run(self._paplay_cmd() + [str(output_path)], check=True)
            except FileNotFoundError:
                subprocess.run(["aplay", str(output_path)], check=True)

        finally:
            if output_path.exists():
                output_path.unlink()

    def speak_async(self, text: str) -> None:
        """Synthesize and play speech (non-blocking)."""
        if self.model_path is None:
            return

        # Stop any current playback
        self.stop()

        # Start piper and player in background
        try:
            piper = subprocess.Popen(
                [
                    self.PIPER_CMD,
                    "--model", str(self.model_path),
                    "--output-raw",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self._current_process = subprocess.Popen(
                self._paplay_cmd(raw=True),
                stdin=piper.stdout,
                stderr=subprocess.PIPE,
            )

            # Send text in background
            piper.stdin.write(text.encode())
            piper.stdin.close()

        except Exception:
            pass  # Fail silently for async

    def stop(self) -> None:
        """Stop any currently playing audio."""
        if self._current_process and self._current_process.poll() is None:
            self._current_process.terminate()
            self._current_process = None

    def save_to_file(self, text: str, output_path: Path | str) -> None:
        """Synthesize speech and save to file."""
        if self.model_path is None:
            raise RuntimeError(f"Voice model not found: {self.config.voice}")

        subprocess.run(
            [
                self.PIPER_CMD,
                "--model", str(self.model_path),
                "--output-file", str(output_path),
            ],
            input=text,
            text=True,
            capture_output=True,
            check=True,
        )

    def list_available_voices(self) -> list[str]:
        """List available voice models in data directory."""
        voices = []
        if self.config.data_dir.exists():
            for model in self.config.data_dir.glob("*.onnx"):
                voices.append(model.stem)
        return voices

    @classmethod
    def is_available(cls) -> bool:
        """Check if Piper is installed."""
        try:
            result = subprocess.run(
                [cls.PIPER_CMD, "--help"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
