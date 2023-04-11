import sys
from PyQt6.QtCore import QTimer, Qt, QPointF, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont, QPen, QPainterPath
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
import random
import math


class VoiceAssistantWidget(QWidget):
    animation_value = property(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.animation = QPropertyAnimation(self, b"animation_value")
        self.animation.setStartValue(0)
        self.animation.setEndValue(100)
        self.animation.setDuration(6000)  # Increase the duration to 6 seconds
        self.animation.setLoopCount(-1)  # Infinite loop
        self.animation.start()
        self.init_ui()

    def init_ui(self):
        # Initialize layout and labels for input/output text
        layout = QVBoxLayout()
        self.input_label = QLabel("Input text")
        self.output_label = QLabel("Output text")

        # Customize font and appearance
        font = QFont("Arial", 14)
        self.input_label.setFont(font)
        self.output_label.setFont(font)

        layout.addWidget(self.input_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.output_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

        # Initialize animation-related variables
        self.animation_value = 0

        # Set up timer for animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)  # Update every 16ms (approx. 60 FPS)

        # Initialize stars
        self.num_stars = 50
        self.stars = [{'x': random.uniform(0, 1), 'y': random.uniform(0, 1), 'size': random.uniform(1, 3), 'opacity': random.uniform(0, 1)} for _ in range(self.num_stars)]

    def update_animation(self):
        self.animation_value += 1

        # Update stars opacity and position
        max_radius = 60
        for star in self.stars:
            star['opacity'] += random.uniform(-0.02, 0.02)  # Slow down opacity changes
            star['opacity'] = max(0, min(1, star['opacity']))

            # Update star position to be within the pulsating circles area
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(0, max_radius)
            star['x'] = 0.5 + radius * math.cos(angle) / self.width()
            star['y'] = 0.5 + radius * math.sin(angle) / self.height()

        self.update()  # Trigger paint event
        QTimer.singleShot(50, self.update_animation)

    def draw_sine_waves(self, painter):
        num_waves = 5
        wave_color = QColor(255, 0, 0, 80)  # Semi-transparent red color
        max_wave_amplitude = 20  # Increase amplitude distortion towards the center
        wave_period = 500

        # Create a clipping path using the circle area
        clipping_radius = 60 * 0.4  # Reduce the diameter by 30%
        clipping_path = QPainterPath()
        clipping_path.addEllipse(QPointF(self.width() / 2, self.height() / 2), clipping_radius, clipping_radius)
        painter.setClipPath(clipping_path)

        painter.setPen(QPen(wave_color, 2))

        for i in range(num_waves):
            path = QPainterPath()
            offset = (self.animation_value + i * 20) % wave_period

            for x in range(0, self.width(), 1):
                t = (x + offset) / wave_period * 2 * math.pi
                amplitude = max_wave_amplitude * (1 - abs(x - self.width() / 2) / (self.width() / 2))

                # Make amplitude drop to 0 at the clipping path
                circle_boundary = self.width() / 2 - clipping_radius
                if x < circle_boundary or x > self.width() - circle_boundary:
                    amplitude = 0

                y_offset = random.uniform(-3, 3)  # Random y-axis offset
                y = self.height() / 2 + amplitude * math.sin(t) + y_offset
                if x == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            painter.drawPath(path)

        # Reset the clipping path
        painter.setClipping(False)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw Jarvis-themed pulsating circles
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_circles(painter)

        # Draw oscillating sine waves
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_sine_waves(painter)

        # Draw twinkling stars
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_stars(painter)

        painter.end()

    def draw_circles(self, painter):
        start_color = QColor(0, 191, 255)
        end_color = QColor(0, 0, 128)

        num_circles = 5
        max_radius = 60
        min_radius = 20

        for i in range(num_circles):
            radius = min_radius + (self.animation_value + i * 6) % (max_radius - min_radius)
            gradient = QLinearGradient(self.width() / 2, self.height() / 2 - radius, self.width() / 2, self.height() / 2 + radius)
            gradient.setColorAt(0, start_color)
            gradient.setColorAt(1, end_color)

            # Calculate the opacity for the current circle
            opacity = 1 - (radius - min_radius) / (max_radius - min_radius)
            painter.setOpacity(opacity)

            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)

            x = int(self.width() / 2 - radius)
            y = int(self.height() / 2 - radius)
            w = int(2 * radius)
            h = int(2 * radius)
            painter.drawEllipse(x, y, w, h)

    def draw_stars(self, painter):
        star_color = QColor(255, 255, 255)

        for star in self.stars:
            painter.setOpacity(star['opacity'])
            painter.setBrush(star_color)
            painter.setPen(Qt.PenStyle.NoPen)

            x = int(self.width() * star['x'] - star['size'] / 2)
            y = int(self.height() * star['y'] - star['size'] / 2)
            w = int(star['size'])
            h = int(star['size'])
            painter.drawEllipse(x, y, w, h)


def main():
    app = QApplication(sys.argv)
    widget = VoiceAssistantWidget()
    widget.setWindowTitle("Jarvis Voice Assistant")
    widget.resize(400, 300)
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
