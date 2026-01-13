#!/usr/bin/env python3
"""Aida - AI Desktop Assistant for KDE Plasma."""

import sys
import threading
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Slot, QThread

from src.core.config import AidaConfig
from src.core.assistant import AidaAssistant
from src.ui.main_window import MainWindow
from src.ui.tray import TrayIcon
from src.ui.settings_dialog import SettingsDialog
from src.ui.tasks_window import TasksWindow

# API Server imports
import uvicorn
from src.api.server import app as api_app, set_assistant_instance


class ApiServerThread(QThread):
    """Runs the FastAPI/Uvicorn server in a separate thread."""
    
    def __init__(self, host="0.0.0.0", port=8085):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None

    def run(self):
        """Start the Uvicorn server."""
        # We need to run uvicorn in a way that doesn't block signal handling too aggressively
        # or we just use the standard run() since we are in a QThread.
        try:
            uvicorn.run(api_app, host=self.host, port=self.port, log_level="info")
        except Exception as e:
            print(f"Server error: {e}")


class AidaApp:
    """Main application class."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Aida")
        self.app.setQuitOnLastWindowClosed(False)

        # Load configuration
        self.config = AidaConfig.load()

        # Initialize components
        self.assistant = AidaAssistant(self.config)
        
        # Connect Assistant to API Server
        set_assistant_instance(self.assistant)
        
        # Start API Server
        self.api_thread = ApiServerThread(host="0.0.0.0", port=8085)
        self.api_thread.start()
        print("API Server started on http://0.0.0.0:8085")

        self.main_window = MainWindow()
        self.tray = TrayIcon()

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect all signals."""
        # Main window signals
        self.main_window.message_sent.connect(self._on_message_sent)
        self.main_window.mic_button_clicked.connect(self.assistant.toggle_listening)
        self.main_window.wake_word_toggled.connect(self.assistant.set_wake_word_enabled)

        # Assistant signals
        self.assistant.response_ready.connect(self._on_response_ready)
        self.assistant.status_changed.connect(self.main_window.set_status)
        self.assistant.listening_changed.connect(self.main_window.set_listening)
        self.assistant.listening_changed.connect(self.tray.set_listening)
        self.assistant.speech_recognized.connect(self._on_speech_recognized)
        self.assistant.wake_word_detected.connect(self._on_wake_word)

        # Tray signals
        self.tray.activated.connect(self._toggle_window)
        self.tray.quit_requested.connect(self._quit)
        self.tray.toggle_listening.connect(self.assistant.toggle_listening)
        self.tray.settings_requested.connect(self._show_settings)
        self.tray.tasks_requested.connect(self._show_tasks)

    @Slot()
    def _on_wake_word(self) -> None:
        """Handle wake word detection."""
        self.tray.show_message("Aida", "I'm listening...")
        # Show and focus window
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    @Slot(str)
    def _on_message_sent(self, message: str) -> None:
        """Handle user message."""
        self.main_window.add_message(message, is_user=True)
        self.assistant.process_message(message)

    @Slot(str)
    def _on_response_ready(self, response: str) -> None:
        """Handle assistant response."""
        self.main_window.add_message(response, is_user=False)
        # Optionally speak the response
        # self.assistant.speak(response)

    @Slot(str)
    def _on_speech_recognized(self, text: str) -> None:
        """Handle recognized speech."""
        self.main_window.add_message(text, is_user=True)

    @Slot()
    def _toggle_window(self) -> None:
        """Toggle main window visibility."""
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    @Slot()
    def _quit(self) -> None:
        """Quit the application."""
        self.assistant.cleanup()
        self.tray.hide()
        self.app.quit()

    @Slot()
    def _show_settings(self) -> None:
        """Show the settings dialog."""
        dialog = SettingsDialog(self.config, self.main_window)

        # Load available models
        try:
            models = self.assistant.llm.list_models()
            dialog.set_available_models(models)
        except Exception:
            pass

        # Connect settings changed signal
        dialog.settings_changed.connect(self._on_settings_changed)

        dialog.exec()

    @Slot()
    def _show_tasks(self) -> None:
        """Show the tasks window."""
        # Ensure tasks system is initialized
        if not self.config.tasks.enabled:
            self.tray.show_message("Aida", "Tasks are disabled in settings.")
            return

        try:
            store = self.assistant.tasks.store
            dialog = TasksWindow(store, self.main_window)
            dialog.exec()
        except Exception as e:
            self.tray.show_message("Aida", f"Could not open tasks: {e}")

    @Slot()
    def _on_settings_changed(self) -> None:
        """Handle settings change."""
        # Reload config
        self.config = AidaConfig.load()

        # Update assistant config
        self.assistant.config = self.config

        # Clear LLM to pick up new model/prompt
        self.assistant._llm = None

        # Clear STT and TTS to pick up new audio devices
        self.assistant._stt = None
        self.assistant._tts = None

        # Restart wake word listener with new microphone
        self.assistant.stop_wake_word_listener()
        self.assistant.start_wake_word_listener()

        self.tray.show_message("Aida", "Settings saved.")

    def run(self) -> int:
        """Run the application."""
        # Show tray icon
        self.tray.show()

        # Show main window
        self.main_window.show()
        
        # Set initial UI state
        self.main_window.wake_word_check.setChecked(self.config.wake_word_enabled)

        # Check if Ollama is available
        if not self.assistant.llm.is_available():
            self.tray.show_message(
                "Aida",
                "Warning: Ollama is not available. Make sure it's running.",
            )

        # Start wake word listener (runs in separate process)
        self.assistant.start_wake_word_listener()
        self.tray.show_message("Aida", f"Say '{self.config.wake_word}' to activate me!")

        return self.app.exec()


def main():
    """Main entry point."""
    app = AidaApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
