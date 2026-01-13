"""Settings dialog for Aida."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QTextEdit,
    QPushButton,
    QFormLayout,
    QTabWidget,
    QWidget,
    QLineEdit,
    QCheckBox,
    QListWidget,
)
from PySide6.QtCore import Signal

from src.core.config import AidaConfig
from src.core.audio_devices import AudioDeviceManager


class SettingsDialog(QDialog):
    """Settings dialog for configuring Aida."""

    settings_changed = Signal()

    # Language presets
    _presets = {
        "English": {
            "whisper_lang": "en",
            "piper_voice": "en_US-amy-medium",
            "prompt": """You are Aida, a helpful AI desktop assistant.
You help users with tasks like web searches, opening applications, and answering questions.
Be concise and friendly.

CRITICAL INSTRUCTION: You must NOT hallucinate or make up information. If you do not know the answer to a question, or if you cannot verify the state of a device (like a light or door) because you lack access, simply state that you do not know or cannot check. Do not guess.

You have access to the user's webcam and can see them when they ask. If someone asks you to see them, look at them, describe what you see, or any vision-related request - you CAN do this. The system will capture an image for you to analyze."""
        },
        "Norwegian": {
            "whisper_lang": "no",
            "piper_voice": "no_NO-talesyntese-medium",
            "prompt": """Du er Aida, en hjelpsom AI-skrivebordsassistent.
Du hjelper brukere med oppgaver som nettsøk, åpning av applikasjoner og å svare på spørsmål.
Vær kortfattet og vennlig.

KRITISK INSTRUKSJON: Du må IKKE hallusinere eller finne på informasjon. Hvis du ikke vet svaret på et spørsmål, eller hvis du ikke kan bekrefte tilstanden til en enhet (som et lys eller en dør) fordi du mangler tilgang, si ganske enkelt at du ikke vet eller ikke kan sjekke. Ikke gjett.

Du har tilgang til brukerens webkamera og kan se dem når de spør. Hvis noen ber deg om å se dem, se på dem, beskriv hva du ser, eller andre synsrelaterte forespørsler - du KAN gjøre dette. Systemet vil ta et bilde du kan analysere."""
        }
    }

    def __init__(self, config: AidaConfig, parent=None):
        super().__init__(parent)

        self.config = config
        self._available_models: list[str] = []

        self.setWindowTitle("Aida Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)

        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        main_layout = QVBoxLayout(self)
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- General Tab ---
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setSpacing(15)

        # Language Settings
        lang_group = QGroupBox("Language")
        lang_layout = QFormLayout()
        
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Custom", None)
        for lang in self._presets.keys():
            self._lang_combo.addItem(lang, lang)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addRow("Preset:", self._lang_combo)
        
        lang_group.setLayout(lang_layout)
        general_layout.addWidget(lang_group)

        # LLM Settings
        llm_group = QGroupBox("LLM Settings")
        llm_layout = QFormLayout()

        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(250)
        llm_layout.addRow("Model:", self._model_combo)

        self._vision_model_combo = QComboBox()
        self._vision_model_combo.setMinimumWidth(250)
        llm_layout.addRow("Vision Model:", self._vision_model_combo)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setMinimumHeight(100)
        self._prompt_edit.setMaximumHeight(150)
        llm_layout.addRow("System Prompt:", self._prompt_edit)

        llm_group.setLayout(llm_layout)
        general_layout.addWidget(llm_group)

        # Audio Settings
        audio_group = QGroupBox("Audio Settings")
        audio_layout = QFormLayout()

        self._mic_combo = QComboBox()
        self._mic_combo.setMinimumWidth(250)
        audio_layout.addRow("Microphone:", self._mic_combo)

        self._speaker_combo = QComboBox()
        self._speaker_combo.setMinimumWidth(250)
        audio_layout.addRow("Speaker:", self._speaker_combo)

        audio_group.setLayout(audio_layout)
        general_layout.addWidget(audio_group)
        
        self.tabs.addTab(general_tab, "General")

        # --- Mail Tab ---
        mail_tab = QWidget()
        mail_layout = QFormLayout(mail_tab)
        mail_layout.setSpacing(15)
        
        self._mail_enabled = QCheckBox("Enable Mail Integration")
        mail_layout.addRow(self._mail_enabled)
        
        self._email_edit = QLineEdit()
        mail_layout.addRow("Email:", self._email_edit)
        
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("App Password recommended")
        mail_layout.addRow("Password:", self._password_edit)
        
        self._imap_server_edit = QLineEdit()
        mail_layout.addRow("IMAP Server:", self._imap_server_edit)
        
        self._imap_port_edit = QLineEdit()
        mail_layout.addRow("IMAP Port:", self._imap_port_edit)
        
        self._smtp_server_edit = QLineEdit()
        mail_layout.addRow("SMTP Server:", self._smtp_server_edit)
        
        self._smtp_port_edit = QLineEdit()
        mail_layout.addRow("SMTP Port:", self._smtp_port_edit)
        
        # Spacer
        mail_layout.addRow(QLabel("--- Calendar ---"))
        
        self._cal_enabled = QCheckBox("Enable Calendar Integration")
        mail_layout.addRow(self._cal_enabled)
        
        self._caldav_url_edit = QLineEdit()
        self._caldav_url_edit.setPlaceholderText("Find this in your calendar provider settings")
        mail_layout.addRow("CalDAV URL:", self._caldav_url_edit)
        
        self.tabs.addTab(mail_tab, "Mail & Calendar")

        # --- Home Assistant Tab ---
        ha_tab = QWidget()
        ha_layout = QFormLayout(ha_tab)
        ha_layout.setSpacing(15)
        
        self._ha_enabled = QCheckBox("Enable Home Assistant Integration")
        ha_layout.addRow(self._ha_enabled)
        
        self._ha_url_edit = QLineEdit()
        self._ha_url_edit.setPlaceholderText("e.g. http://homeassistant.local:8123")
        ha_layout.addRow("URL:", self._ha_url_edit)
        
        self._ha_token_edit = QLineEdit()
        self._ha_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._ha_token_edit.setPlaceholderText("Long-Lived Access Token")
        ha_layout.addRow("Token:", self._ha_token_edit)
        
        self.tabs.addTab(ha_tab, "Home Assistant")

        # --- RSS Feeds Tab ---
        rss_tab = QWidget()
        rss_layout = QVBoxLayout(rss_tab)
        rss_layout.setSpacing(10)

        self._rss_enabled = QCheckBox("Enable RSS Feeds")
        rss_layout.addWidget(self._rss_enabled)

        rss_layout.addWidget(QLabel("Configured news feeds:"))

        self._rss_list = QListWidget()
        self._rss_list.setMinimumHeight(150)
        rss_layout.addWidget(self._rss_list)

        # Add feed controls
        add_feed_layout = QHBoxLayout()
        self._rss_name_edit = QLineEdit()
        self._rss_name_edit.setPlaceholderText("Feed name (e.g. VG Nyheter)")
        add_feed_layout.addWidget(self._rss_name_edit)

        self._rss_url_edit = QLineEdit()
        self._rss_url_edit.setPlaceholderText("Feed URL")
        add_feed_layout.addWidget(self._rss_url_edit)

        self._rss_add_btn = QPushButton("Add")
        self._rss_add_btn.clicked.connect(self._add_rss_feed)
        add_feed_layout.addWidget(self._rss_add_btn)

        rss_layout.addLayout(add_feed_layout)

        self._rss_remove_btn = QPushButton("Remove Selected")
        self._rss_remove_btn.clicked.connect(self._remove_rss_feed)
        rss_layout.addWidget(self._rss_remove_btn)

        rss_layout.addStretch()
        self.tabs.addTab(rss_tab, "RSS Feeds")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._refresh_btn = QPushButton("Refresh Devices")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        button_layout.addWidget(self._refresh_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)

        main_layout.addLayout(button_layout)

    def set_available_models(self, models: list[str]) -> None:
        """Set the available Ollama models."""
        self._available_models = models
        self._update_model_combos()

    def _update_model_combos(self) -> None:
        """Update model combo boxes with available models."""
        current_model = self._model_combo.currentText()
        current_vision = self._vision_model_combo.currentText()

        self._model_combo.clear()
        self._vision_model_combo.clear()

        for model in self._available_models:
            self._model_combo.addItem(model)
            self._vision_model_combo.addItem(model)

        # Restore selection or set config value
        if current_model and current_model in self._available_models:
            self._model_combo.setCurrentText(current_model)
        elif self.config.ollama.model in self._available_models:
            self._model_combo.setCurrentText(self.config.ollama.model)

        if current_vision and current_vision in self._available_models:
            self._vision_model_combo.setCurrentText(current_vision)
        elif self.config.ollama.vision_model in self._available_models:
            self._vision_model_combo.setCurrentText(self.config.ollama.vision_model)

    def _on_language_changed(self, index: int) -> None:
        """Handle language preset change."""
        lang = self._lang_combo.itemData(index)
        if not lang or lang not in self._presets:
            return

        preset = self._presets[lang]
        self._prompt_edit.setPlainText(preset["prompt"])
        
        # We store the other settings temporarily, applied on save
        # Could also update UI for voice if we had a voice selector exposed here
        
    def _load_current_settings(self) -> None:
        """Load current settings into the UI."""
        # Check if current settings match a preset
        current_whisper = self.config.whisper.language
        current_prompt = self.config.ollama.system_prompt
        
        found_preset = False
        for lang, preset in self._presets.items():
            if (preset["whisper_lang"] == current_whisper and 
                preset["prompt"].strip() == current_prompt.strip()):
                
                index = self._lang_combo.findData(lang)
                if index >= 0:
                    self._lang_combo.setCurrentIndex(index)
                    found_preset = True
                break
        
        if not found_preset:
             self._lang_combo.setCurrentIndex(0) # Custom

        # System prompt
        self._prompt_edit.setPlainText(self.config.ollama.system_prompt)
        
        # Mail settings
        self._mail_enabled.setChecked(self.config.mail.enabled)
        self._email_edit.setText(self.config.mail.email)
        self._password_edit.setText(self.config.mail.password)
        self._imap_server_edit.setText(self.config.mail.imap_server)
        self._imap_port_edit.setText(str(self.config.mail.imap_port))
        self._smtp_server_edit.setText(self.config.mail.smtp_server)
        self._smtp_port_edit.setText(str(self.config.mail.smtp_port))
        self._cal_enabled.setChecked(self.config.mail.calendar_enabled)
        self._caldav_url_edit.setText(self.config.mail.caldav_url)
        
        # HA settings
        self._ha_enabled.setChecked(self.config.ha.enabled)
        self._ha_url_edit.setText(self.config.ha.url)
        self._ha_token_edit.setText(self.config.ha.token)

        # RSS settings
        self._rss_enabled.setChecked(self.config.rss.enabled)
        self._rss_list.clear()
        for feed in self.config.rss.feeds:
            self._rss_list.addItem(f"{feed['name']} - {feed['url']}")

        # Refresh device lists
        self._refresh_devices()

    def _refresh_devices(self) -> None:
        """Refresh the audio device lists."""
        # Microphones
        self._mic_combo.clear()
        self._mic_combo.addItem("System Default", None)

        microphones = AudioDeviceManager.list_microphones()
        for mic in microphones:
            label = f"{mic.name}" + (" (default)" if mic.is_default else "")
            self._mic_combo.addItem(label, mic.id)

        # Set current selection
        if self.config.audio.microphone_device is not None:
            for i in range(self._mic_combo.count()):
                if self._mic_combo.itemData(i) == self.config.audio.microphone_device:
                    self._mic_combo.setCurrentIndex(i)
                    break

        # Speakers
        self._speaker_combo.clear()
        self._speaker_combo.addItem("System Default", None)

        speakers = AudioDeviceManager.list_speakers()
        for speaker in speakers:
            label = f"{speaker.name}" + (" (default)" if speaker.is_default else "")
            self._speaker_combo.addItem(label, speaker.id)

        # Set current selection
        if self.config.audio.speaker_device is not None:
            for i in range(self._speaker_combo.count()):
                if self._speaker_combo.itemData(i) == self.config.audio.speaker_device:
                    self._speaker_combo.setCurrentIndex(i)
                    break

    def _save_settings(self) -> None:
        """Save settings and close dialog."""
        # Update config
        if self._model_combo.currentText():
            self.config.ollama.model = self._model_combo.currentText()

        if self._vision_model_combo.currentText():
            self.config.ollama.vision_model = self._vision_model_combo.currentText()

        self.config.ollama.system_prompt = self._prompt_edit.toPlainText()

        # Apply language preset settings if selected
        lang = self._lang_combo.currentData()
        if lang and lang in self._presets:
            preset = self._presets[lang]
            self.config.whisper.language = preset["whisper_lang"]
            # Only update Piper voice if using Piper
            if self.config.tts_provider == "piper":
                self.config.piper.voice = preset["piper_voice"]

        self.config.audio.microphone_device = self._mic_combo.currentData()
        self.config.audio.speaker_device = self._speaker_combo.currentData()
        
        # Mail config
        self.config.mail.enabled = self._mail_enabled.isChecked()
        self.config.mail.email = self._email_edit.text().strip()
        self.config.mail.password = self._password_edit.text()
        self.config.mail.imap_server = self._imap_server_edit.text().strip()
        try:
            self.config.mail.imap_port = int(self._imap_port_edit.text().strip())
        except ValueError:
            pass
        self.config.mail.smtp_server = self._smtp_server_edit.text().strip()
        try:
            self.config.mail.smtp_port = int(self._smtp_port_edit.text().strip())
        except ValueError:
            pass
            
        self.config.mail.calendar_enabled = self._cal_enabled.isChecked()
        self.config.mail.caldav_url = self._caldav_url_edit.text().strip()

        # HA config
        self.config.ha.enabled = self._ha_enabled.isChecked()
        self.config.ha.url = self._ha_url_edit.text().strip()
        self.config.ha.token = self._ha_token_edit.text()

        # RSS config
        self.config.rss.enabled = self._rss_enabled.isChecked()
        # Rebuild feeds list from QListWidget
        feeds = []
        for i in range(self._rss_list.count()):
            item_text = self._rss_list.item(i).text()
            # Parse "Name - URL" format
            if " - " in item_text:
                name, url = item_text.split(" - ", 1)
                feeds.append({"name": name, "url": url})
        self.config.rss.feeds = feeds

        # Save to file
        self.config.save()

        # Emit signal
        self.settings_changed.emit()

        self.accept()

    def _add_rss_feed(self) -> None:
        """Add a new RSS feed to the list."""
        name = self._rss_name_edit.text().strip()
        url = self._rss_url_edit.text().strip()

        if not name or not url:
            return

        # Add https:// if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        self._rss_list.addItem(f"{name} - {url}")
        self._rss_name_edit.clear()
        self._rss_url_edit.clear()

    def _remove_rss_feed(self) -> None:
        """Remove the selected RSS feed from the list."""
        current_row = self._rss_list.currentRow()
        if current_row >= 0:
            self._rss_list.takeItem(current_row)
