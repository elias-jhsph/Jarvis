import os
import sys
import time
from pyaudio import PyAudio, paInt16, paContinue
from numpy import zeros, frombuffer, int16, pi, exp, sin
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QRegion, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget


class JarvisWaveform(QWidget):
    def __init__(self, parent=None):
        """Initialize the widget.

        :param parent: parent widget (default=None)
        :type parent: QWidget
        """
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("Jarvis Icon Animation")
        self.resize(120, 120)
        self.num_waves = 5
        icons_folder = "icons/"
        if getattr(sys, 'frozen', False):
            icons_folder = os.path.join(sys._MEIPASS, "icons/")
        self.icon_path = icons_folder + "icon.icns"
        self.icon = QPixmap(self.icon_path)
        self.prev_icon = None
        self.prev_icon_opacity = 0
        self.base_wave_colors = []

        average_color = self.calculate_average_color(self.icon)
        self.update_base_wave_colors(average_color)

        self.audio_data = zeros(1024)
        self.init_audio_stream()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(20)

        self.start_time = time.time()
        self.setStyleSheet("background-color: transparent; border: none;")

    def init_audio_stream(self):
        """Initialize the audio stream."""
        self.p = PyAudio()
        self.stream = self.p.open(format=paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024,
                                  stream_callback=self.audio_callback)

    def audio_callback(self, in_data, frame_count, time_info, status):
        """Process the audio data from the stream.

        :param in_data: input data
        :type in_data: bytes
        :param frame_count: number of frames
        :type frame_count: int
        :param time_info: time information
        :type time_info: dict
        :param status: stream status
        :type status: int
        :return: stream status
        :rtype: int
        """
        audio_data = frombuffer(in_data, dtype=int16)
        self.audio_data = audio_data
        return None, paContinue

    def draw_icon(self, painter, icon, opacity):
        """Draw the icon with the given opacity.

        :param painter: painter object
        :type painter: QPainter
        :param icon: icon pixmap
        :type icon: QPixmap
        :param opacity: opacity value (0-1)
        :type opacity: float
        """
        max_amplitude = abs(self.audio_data).max() / 32768
        scaling_factor = 0.80 + max_amplitude * 0.2
        icon_width = int(self.width() * 0.01)
        icon_height = int(self.height() * 0.01)
        scaled_icon = icon.scaled(icon_width, icon_height,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)

        scaled_width = int(scaled_icon.width() * scaling_factor)
        scaled_height = int(scaled_icon.height() * scaling_factor)
        x = (self.width() - scaled_width) // 2
        y = (self.height() - scaled_height) // 2
        painter.save()
        painter.setOpacity(opacity)
        painter.drawPixmap(QPoint(x, y),
                           scaled_icon.scaled(scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        painter.restore()

    def calculate_average_color(self, pixmap):
        """Calculate the average color of the pixmap.

        :param pixmap: input pixmap
        :type pixmap: QPixmap
        :return: average color
        :rtype: QColor
        """
        image = pixmap.toImage()
        width, height = image.width(), image.height()
        total_red, total_green, total_blue = 0, 0, 0
        pixel_count = 0

        for x in range(0, width, 10):  # Adjust the step size for faster performance at the cost of accuracy
            for y in range(0, height, 10):
                color = QColor(image.pixel(x, y))
                total_red += color.red()
                total_green += color.green()
                total_blue += color.blue()
                pixel_count += 1

        return QColor(total_red // pixel_count, total_green // pixel_count, total_blue // pixel_count)

    def update_base_wave_colors(self, average_color):
        """Update the base wave colors based on the average color.

        :param average_color: average color
        :type average_color: QColor
        """
        base_color = average_color.toHsl()
        self.base_wave_colors = []

        min_lightness = 50

        for i in range(self.num_waves):
            color = QColor.fromHsl(
                (base_color.hue() + 20 * i) % 360,
                min(base_color.saturation() + 30 * i, 255),
                max(base_color.lightness() - 20 * i, min_lightness), )
            self.base_wave_colors.append(color)

    def create_icon_region(self, pixmap, transparency_threshold=100):
        """Create a region based on the opaque pixels of the icon.

        :param pixmap: input pixmap
        :type pixmap: QPixmap
        :param transparency_threshold: transparency threshold (default=100)
        :type transparency_threshold: int
        :return: region object
        :rtype: QRegion
        """
        image = pixmap.toImage()
        width, height = image.width(), image.height()
        region = QRegion()

        for x in range(width):
            for y in range(height):
                color = QColor(image.pixel(x, y))

                if color.alpha() > transparency_threshold:
                    region += QRegion(x, y, 1, 1)

        return region

    def paintEvent(self, event):
        """Paint the widget."""
        with QPainter(self) as painter:
            # Draw the previous icon
            if self.prev_icon and self.prev_icon_opacity > 0:
                self.draw_icon(painter, self.prev_icon, self.prev_icon_opacity)

            # Draw the current icon
            self.draw_icon(painter, self.icon, 1 - self.prev_icon_opacity)

            painter.setRenderHint(QPainter.Antialiasing)

            # Draw the waveform
            icon_width = self.icon.width()
            icon_height = self.icon.height()
            circle_diameter = int(icon_width * 0.95)
            circle_x = (self.width() - circle_diameter) // 2
            circle_y = (self.height() - circle_diameter) // 2
            circle_radius = circle_diameter / 2

            max_height = self.height() // 2
            width = self.width()
            num_waves = self.num_waves
            max_amplitude = abs(self.audio_data).max() / 32768
            data = self.audio_data
            current_time = time.time() - self.start_time
            wave_start_x = int(self.width() * 0.13)
            wave_end_x = int(self.width() * 0.87)

            for i in range(num_waves):
                color = self.base_wave_colors[i]
                painter.setPen(QColor(color))

                for x in range(wave_start_x, wave_end_x):
                    phase_shift = (i * 15) + (x / 8) + (current_time * 2 * pi * (i % 2) / 5)
                    amplitude = max_amplitude * (num_waves - i) / num_waves
                    frequency = (2 * pi * (i + 1) / width) * 4

                    # Adjust the amplitude based on the x-axis position with modified Gaussian scaling factor
                    scaling_factor = 1.5 * exp(-((x / width - 0.5) ** 2) / 0.075)
                    y = int(amplitude * sin(frequency * x + phase_shift) * max_height * scaling_factor)

                    # Add vertical offset to each wave
                    vertical_offset = int((sin(current_time + i * pi / num_waves) * max_height * 0.1) - 0.25)

                    # Add curvature to the wave lines
                    curvature_offset = int(sin(x * (1 + i) / 100) * max_height * 0.05)

                    painter.drawLine(x, max_height - y + vertical_offset + curvature_offset, x,
                                     max_height + y + vertical_offset + curvature_offset)

    def update_icon_path(self, new_icon_path, fade=True):
        """Update the icon path and fade in the new icon.

        :param new_icon_path: path to the new icon
        :type new_icon_path: str
        :param fade: whether to fade in the new icon (default=True)
        :type fade: bool
        """
        self.prev_icon = QPixmap(self.icon_path)
        self.prev_icon_opacity = 1
        self.icon_path = new_icon_path
        self.icon = QPixmap(self.icon_path)

        average_color = self.calculate_average_color(self.icon)
        self.update_base_wave_colors(average_color)
        if fade:
            fade_duration = 1000  # Fade duration in milliseconds
            fade_steps = 20
            fade_interval = fade_duration // fade_steps

            def decrease_opacity():
                self.prev_icon_opacity -= 1 / fade_steps
                if self.prev_icon_opacity <= 0:
                    self.prev_icon_opacity = 0
                    self.prev_icon = None
                else:
                    QTimer.singleShot(fade_interval, decrease_opacity)
                self.update()

            QTimer.singleShot(fade_interval, decrease_opacity)

    def force_close(self):
        """Forcefully close the widget."""
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

    def closeEvent(self, event):
        """Handle the close event."""
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_widget = JarvisWaveform()
    main_widget.show()

    # Demonstrate the dynamic icon update after 5 seconds
    QTimer.singleShot(2000, lambda: main_widget.update_icon_path("icons/listening.incs"))
    QTimer.singleShot(4000, lambda: main_widget.update_icon_path("icons/processing_small.icns"))
    sys.exit(app.exec())
