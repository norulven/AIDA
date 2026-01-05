"""Audio visualization widget."""

import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

class VisualizerWidget(QWidget):
    """Widget that simulates audio visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setFixedHeight(80)
        
        # State
        self._active = False
        self._mode = "idle"  # idle, listening, speaking
        
        # Animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_bars)
        self._timer.start(30)  # ~30 FPS
        
        # Bars
        self._num_bars = 20
        self._bars = [0.1] * self._num_bars
        self._target_bars = [0.1] * self._num_bars
        
        # Colors
        self._idle_color = QColor("#555555")
        self._listening_color = QColor("#ff5252") # Red-ish
        self._speaking_color = QColor("#448aff") # Blue-ish

    def set_mode(self, mode: str):
        """Set visualization mode: 'idle', 'listening', 'speaking'."""
        self._mode = mode
        self.update()

    def _update_bars(self):
        """Update bar heights."""
        # Smoothing factor
        alpha = 0.2
        
        for i in range(self._num_bars):
            # Generate target based on mode
            if self._mode == "idle":
                # Gentle wave
                self._target_bars[i] = 0.1 + 0.05 * random.random()
            elif self._mode == "listening":
                # High energy, erratic
                self._target_bars[i] = random.uniform(0.1, 0.8)
            elif self._mode == "speaking":
                # Rhythmic, center-focused
                dist = abs(i - self._num_bars // 2)
                scale = max(0.1, 1.0 - (dist / (self._num_bars / 2)))
                self._target_bars[i] = random.uniform(0.2, 0.9) * scale

            # Interpolate
            self._bars[i] = self._bars[i] * (1 - alpha) + self._target_bars[i] * alpha
            
        self.update()

    def paintEvent(self, event):
        """Draw the visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        # painter.fillRect(self.rect(), Qt.GlobalColor.black) # Optional
        
        # Determine color
        if self._mode == "listening":
            color = self._listening_color
        elif self._mode == "speaking":
            color = self._speaking_color
        else:
            color = self._idle_color
            
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        w = self.width()
        h = self.height()
        bar_width = w / self._num_bars
        gap = 2
        
        for i, val in enumerate(self._bars):
            # Calculate bar dimensions
            bar_h = val * h * 0.8
            x = i * bar_width + gap / 2
            y = (h - bar_h) / 2 # Center vertically
            
            # Draw rounded rect
            rect = QRectF(x, y, bar_width - gap, bar_h)
            painter.drawRoundedRect(rect, 4, 4)
