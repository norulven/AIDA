"""Configuration management for Aida."""

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class MemoryConfig:
    """Memory system configuration."""

    enabled: bool = True
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local/share/aida")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache/aida")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_semantic_results: int = 3
    auto_extract_facts: bool = True
    include_semantic_context: bool = True


@dataclass
class TaskConfig:
    """Task management configuration."""

    enabled: bool = True
    default_reminder_minutes: int = 30
    speak_reminders: bool = True
    auto_sync_ha: bool = False
    default_ha_list: str | None = None


@dataclass
class OllamaConfig:
    """Ollama LLM configuration."""

    host: str = "http://localhost:11434"
    model: str = "dolphin-llama3:8b"
    vision_model: str = "llava:7b"
    temperature: float = 0.7
    system_prompt: str = """You are Aida, a helpful AI desktop assistant.
You help users with tasks like web searches, opening applications, and answering questions.
Be concise and friendly. When asked to perform actions, confirm what you're doing.

You have access to the user's webcam and can see them when they ask. If someone asks you to see them, look at them, describe what you see, or any vision-related request - you CAN do this. The system will capture an image for you to analyze."""


@dataclass
class WhisperConfig:
    """Whisper STT configuration."""

    model_size: str = "base"  # tiny, base, small, medium, large
    device: str = "auto"  # auto, cpu, cuda
    language: str = "en"
    beam_size: int = 5


@dataclass
class PiperConfig:
    """Piper TTS configuration."""

    voice: str = "en_US-amy-medium"
    speed: float = 1.0
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local/share/piper")


@dataclass
class EdgeTTSConfig:
    """Edge TTS configuration."""
    voice: str = "en-US-AriaNeural"  # or en-GB-SoniaNeural, nb-NO-PernilleNeural


@dataclass
class MailConfig:
    """Email configuration."""
    enabled: bool = False
    email: str = ""
    password: str = ""  # App password recommended
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    calendar_enabled: bool = False
    caldav_url: str = ""  # e.g., https://apidata.googleusercontent.com/caldav/v2/your-email/events


@dataclass
class HomeAssistantConfig:
    """Home Assistant configuration."""
    enabled: bool = False
    url: str = "" # e.g., http://homeassistant.local:8123
    token: str = ""


@dataclass
class CameraConfig:
    """Webcam configuration."""

    device_id: int = 0
    width: int = 640
    height: int = 480


@dataclass
class AudioConfig:
    """Audio device configuration."""

    microphone_device: int | None = None  # sounddevice device index, None = default
    speaker_device: str | None = None  # PulseAudio sink name, None = default


@dataclass
class AidaConfig:
    """Main Aida configuration."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    piper: PiperConfig = field(default_factory=PiperConfig)
    edge_tts: EdgeTTSConfig = field(default_factory=EdgeTTSConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    ha: HomeAssistantConfig = field(default_factory=HomeAssistantConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tasks: TaskConfig = field(default_factory=TaskConfig)
    
    tts_provider: str = "piper"
    wake_word: str = "aida"
    wake_word_enabled: bool = True
    config_dir: Path = field(default_factory=lambda: Path.home() / ".config/aida")

    def save(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config_file = self.config_dir / "config.json"

        data = {
            "ollama": {
                "host": self.ollama.host,
                "model": self.ollama.model,
                "vision_model": self.ollama.vision_model,
                "temperature": self.ollama.temperature,
                "system_prompt": self.ollama.system_prompt,
            },
            "whisper": {
                "model_size": self.whisper.model_size,
                "device": self.whisper.device,
                "language": self.whisper.language,
                "beam_size": self.whisper.beam_size,
            },
            "piper": {
                "voice": self.piper.voice,
                "speed": self.piper.speed,
                "data_dir": str(self.piper.data_dir),
            },
            "edge_tts": {
                "voice": self.edge_tts.voice,
            },
            "mail": {
                "enabled": self.mail.enabled,
                "email": self.mail.email,
                "password": self.mail.password,
                "imap_server": self.mail.imap_server,
                "smtp_server": self.mail.smtp_server,
                "calendar_enabled": self.mail.calendar_enabled,
                "caldav_url": self.mail.caldav_url,
            },
            "ha": {
                "enabled": self.ha.enabled,
                "url": self.ha.url,
                "token": self.ha.token,
            },
            "camera": {
                "device_id": self.camera.device_id,
                "width": self.camera.width,
                "height": self.camera.height,
            },
            "audio": {
                "microphone_device": self.audio.microphone_device,
                "speaker_device": self.audio.speaker_device,
            },
            "memory": {
                "enabled": self.memory.enabled,
                "data_dir": str(self.memory.data_dir),
                "cache_dir": str(self.memory.cache_dir),
                "embedding_model": self.memory.embedding_model,
                "max_semantic_results": self.memory.max_semantic_results,
                "auto_extract_facts": self.memory.auto_extract_facts,
                "include_semantic_context": self.memory.include_semantic_context,
            },
            "tasks": {
                "enabled": self.tasks.enabled,
                "default_reminder_minutes": self.tasks.default_reminder_minutes,
                "speak_reminders": self.tasks.speak_reminders,
                "auto_sync_ha": self.tasks.auto_sync_ha,
                "default_ha_list": self.tasks.default_ha_list,
            },
            "wake_word": self.wake_word,
            "wake_word_enabled": self.wake_word_enabled,
            "tts_provider": self.tts_provider,
        }

        with open(config_file, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "AidaConfig":
        """Load configuration from file."""
        config = cls()
        config_file = config.config_dir / "config.json"

        if config_file.exists():
            with open(config_file) as f:
                data = json.load(f)

            if "ollama" in data:
                config.ollama = OllamaConfig(**data["ollama"])
            if "whisper" in data:
                config.whisper = WhisperConfig(**data["whisper"])
            if "piper" in data:
                piper_data = data["piper"].copy()
                piper_data["data_dir"] = Path(piper_data["data_dir"])
                config.piper = PiperConfig(**piper_data)
            if "edge_tts" in data:
                config.edge_tts = EdgeTTSConfig(**data["edge_tts"])
            if "mail" in data:
                config.mail = MailConfig(**data["mail"])
            if "ha" in data:
                config.ha = HomeAssistantConfig(**data["ha"])
            if "camera" in data:
                config.camera = CameraConfig(**data["camera"])
            if "audio" in data:
                config.audio = AudioConfig(**data["audio"])
            if "memory" in data:
                memory_data = data["memory"].copy()
                memory_data["data_dir"] = Path(memory_data["data_dir"])
                memory_data["cache_dir"] = Path(memory_data["cache_dir"])
                config.memory = MemoryConfig(**memory_data)
            if "tasks" in data:
                config.tasks = TaskConfig(**data["tasks"])
            if "wake_word" in data:
                config.wake_word = data["wake_word"]
            if "wake_word_enabled" in data:
                config.wake_word_enabled = data["wake_word_enabled"]
            if "tts_provider" in data:
                config.tts_provider = data["tts_provider"]

        return config
