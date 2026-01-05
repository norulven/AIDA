"""Audio device enumeration for Aida."""

import subprocess
from dataclasses import dataclass


@dataclass
class AudioDevice:
    """Represents an audio device."""

    id: str | int
    name: str
    is_default: bool = False


class AudioDeviceManager:
    """Manage audio device enumeration."""

    @staticmethod
    def list_microphones() -> list[AudioDevice]:
        """List available microphones using sounddevice."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            default_input = sd.default.device[0]

            microphones = []
            for i, device in enumerate(devices):
                if device["max_input_channels"] > 0:
                    microphones.append(AudioDevice(
                        id=i,
                        name=device["name"],
                        is_default=(i == default_input),
                    ))

            return microphones

        except Exception:
            return []

    @staticmethod
    def list_speakers() -> list[AudioDevice]:
        """List available speakers using PulseAudio."""
        try:
            # Get list of sinks
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return []

            # Get default sink
            default_result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
            )
            default_sink = default_result.stdout.strip()

            # Parse sink output
            speakers = []
            current_name = None
            current_description = None

            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Name:"):
                    current_name = line.split(":", 1)[1].strip()
                elif line.startswith("Description:"):
                    current_description = line.split(":", 1)[1].strip()
                    if current_name and current_description:
                        speakers.append(AudioDevice(
                            id=current_name,
                            name=current_description,
                            is_default=(current_name == default_sink),
                        ))
                        current_name = None
                        current_description = None

            return speakers

        except Exception:
            return []

    @staticmethod
    def set_default_speaker(sink_name: str) -> bool:
        """Set the default PulseAudio sink."""
        try:
            result = subprocess.run(
                ["pactl", "set-default-sink", sink_name],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_default_microphone_index() -> int | None:
        """Get the default microphone device index."""
        try:
            import sounddevice as sd
            return sd.default.device[0]
        except Exception:
            return None

    @staticmethod
    def get_default_speaker_name() -> str | None:
        """Get the default PulseAudio sink name."""
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
