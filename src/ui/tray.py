"""System tray integration for Aida."""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal, QObject


class TrayIcon(QObject):
    """System tray icon for Aida."""

    # Signals
    activated = Signal()
    quit_requested = Signal()
    settings_requested = Signal()
    toggle_listening = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._tray = QSystemTrayIcon()
        self._setup_icon()
        self._setup_menu()
        self._connect_signals()

    def _setup_icon(self) -> None:
        """Set up the tray icon."""
        # Use a system icon as placeholder
        icon = QIcon.fromTheme("assistant", QIcon.fromTheme("user-desktop"))
        self._tray.setIcon(icon)
        self._tray.setToolTip("Aida - AI Assistant")

    def _setup_menu(self) -> None:
        """Set up the context menu."""
        menu = QMenu()

        # Listen action
        self._listen_action = QAction("Start Listening", menu)
        self._listen_action.triggered.connect(self.toggle_listening.emit)
        menu.addAction(self._listen_action)

        menu.addSeparator()

        # Settings action
        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        # Quit action
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.activated.emit()

    def show(self) -> None:
        """Show the tray icon."""
        self._tray.show()

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray.hide()

    def set_listening(self, listening: bool) -> None:
        """Update the listening state."""
        if listening:
            self._listen_action.setText("Stop Listening")
            self._tray.setToolTip("Aida - Listening...")
        else:
            self._listen_action.setText("Start Listening")
            self._tray.setToolTip("Aida - AI Assistant")

    def show_message(self, title: str, message: str) -> None:
        """Show a notification message."""
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
