"""Main window for Aida."""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QFrame,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from src.ui.visualizer import VisualizerWidget


class ChatMessage(QFrame):
    """A single chat message widget."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Sender label
        sender = QLabel("You" if is_user else "Aida")
        layout.addWidget(sender)

        # Message text
        message = QLabel(text)
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)

        # Style based on sender (explicit text color for dark themes)
        if is_user:
            self.setStyleSheet("background-color: #e3f2fd; border-radius: 8px; color: #1a1a1a;")
            sender.setStyleSheet("font-weight: bold; color: #1565c0;")
        else:
            self.setStyleSheet("background-color: #f5f5f5; border-radius: 8px; color: #1a1a1a;")
            sender.setStyleSheet("font-weight: bold; color: #6a1b9a;")


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    message_sent = Signal(str)
    mic_button_clicked = Signal()
    wake_word_toggled = Signal(bool)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Aida - AI Assistant")
        self.setMinimumSize(500, 600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QLabel("Aida")
        header.setFont(QFont("Sans", 24, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Visualizer
        self.visualizer = VisualizerWidget()
        layout.addWidget(self.visualizer)

        # Status label
        self._status_label = QLabel("Ready")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # Wake word toggle
        self.wake_word_check = QCheckBox("Listen for 'Aida'")
        self.wake_word_check.setChecked(True)
        self.wake_word_check.toggled.connect(self.wake_word_toggled.emit)
        
        # Center the checkbox
        ww_layout = QHBoxLayout()
        ww_layout.addStretch()
        ww_layout.addWidget(self.wake_word_check)
        ww_layout.addStretch()
        layout.addLayout(ww_layout)

        # Chat area
        self._chat_area = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_area)
        self._chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chat_layout.setSpacing(10)

        # Scrollable chat
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidget(self._chat_area)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

        # Input area
        input_layout = QHBoxLayout()

        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Type a message or press the mic button...")
        self._input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._input_field)

        # Mic button
        self._mic_button = QPushButton("🎤")
        self._mic_button.setFixedSize(40, 40)
        self._mic_button.clicked.connect(self.mic_button_clicked.emit)
        input_layout.addWidget(self._mic_button)

        # Send button
        send_button = QPushButton("Send")
        send_button.clicked.connect(self._send_message)
        input_layout.addWidget(send_button)

        layout.addLayout(input_layout)

    def _send_message(self) -> None:
        """Send the current message."""
        text = self._input_field.text().strip()
        if text:
            self._input_field.clear()
            self.message_sent.emit(text)

    @Slot(str, bool)
    def add_message(self, text: str, is_user: bool) -> None:
        """Add a message to the chat."""
        message = ChatMessage(text, is_user)
        self._chat_layout.addWidget(message)

    @Slot(str)
    def set_status(self, status: str) -> None:
        """Update the status label."""
        self._status_label.setText(status)
        
        # Heuristic for active modes
        active_keywords = [
            "Speaking", "Thinking", "Searching", "Fetching", 
            "Opening", "Looking", "Organizing", "Compressing", "Renaming"
        ]
        
        if any(keyword in status for keyword in active_keywords):
             self.visualizer.set_mode("speaking")
        elif not "Listening" in status:
             self.visualizer.set_mode("idle")

    @Slot(bool)
    def set_listening(self, listening: bool) -> None:
        """Update UI for listening state."""
        if listening:
            self._mic_button.setStyleSheet("background-color: #ff5252;")
            self._status_label.setText("Listening...")
            self.visualizer.set_mode("listening")
        else:
            self._mic_button.setStyleSheet("")
            self._status_label.setText("Ready")
            # Don't set to idle immediately, let set_status handle "Speaking" etc.

    def clear_chat(self) -> None:
        """Clear all chat messages."""
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
