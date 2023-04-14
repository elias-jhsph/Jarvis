from PyQt6.QtCore import Qt, QEvent, QTimer, QRectF
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QScrollArea, QHBoxLayout, \
    QGraphicsDropShadowEffect, QSizePolicy, QSpacerItem
from PyQt6.QtGui import QMovie, QColor, QFont, QPalette, QTextOption, QPainter
from processor import get_chat_history
from animation import JarvisWaveform
from multiprocessing import Queue
import sys
import datetime


def format_message(message):
    date_time_str = message.get("utc_time","").split(" ")[1][:-1]
    try:
        date_time_obj = datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        date_time_obj = datetime.datetime.strptime(date_time_str, "%H:%M:%S.%f")

    formatted_datetime = date_time_obj.strftime("%A, %B %d, %Y at %I:%M %p")

    model_info = ""
    if message.get("model"):
        model_info = f"Source AI Model: {message['model']} - "

    return f"{model_info}{formatted_datetime}: {message['content'].split(': ')[1]}"


class AspectRatioLabel(QLabel):
    def paintEvent(self, event):
        if self.movie():
            painter = QPainter(self)
            pixmap = self.movie().currentPixmap()
            scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            rect = QRectF(0, 0, scaled_pixmap.width(), scaled_pixmap.height())
            rect.moveCenter(self.rect().center().toPointF())
            painter.drawPixmap(rect.topLeft(), scaled_pixmap)
        else:
            super().paintEvent(event)


class ChatWindow(QMainWindow):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.oldest_message_id = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Voice Assistant Chat")
        self.resize(800, 600)
        self.dark_mode()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)

        self.chat_area = QScrollArea(self)
        layout.addWidget(self.chat_area)

        self.chat_widget = QWidget()
        self.chat_area.setWidget(self.chat_widget)
        self.chat_area.setWidgetResizable(True)
        scroll_layout = QVBoxLayout()
        scroll_widget = QWidget()
        scroll_widget.setLayout(scroll_layout)
        self.chat_area.setWidget(scroll_widget)
        self.chat_area.setWidgetResizable(True)
        self.chat_widget.setLayout(scroll_layout)


        self.create_loading_animation(scroll_layout)

        # self.waveform_widget = JarvisWaveform(self, QSize(140, 140))
        # layout.addWidget(self.waveform_widget)

        self.load_chat_history()  # Keep only this call, remove any other call to this method
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_chat)
        self.update_timer.start(1000)

        self.chat_area.viewport().installEventFilter(self)
        self.chat_area.verticalScrollBar().valueChanged.connect(self.on_scrollbar_value_changed)

        # Use a single-shot timer to update the chat labels after the window is shown
        QTimer.singleShot(0, self.update_chat_labels)

    def create_loading_animation(self, scroll_layout):
        self.loading_movie = QMovie("icons/loading.gif")  # Replace with the path to your GIF
        self.loading_label = AspectRatioLabel()
        self.loading_label.setMovie(self.loading_movie)
        self.loading_label.setScaledContents(True)
        self.loading_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.loading_label.hide()
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Set the maximum width to 5% of the chat area width
        gif_size = int(self.width() * 0.10)
        self.loading_label.setFixedSize(gif_size, gif_size)
        self.loading_label.setMaximumWidth(int(self.chat_area.width() * 0.10))

        # Create a QHBoxLayout and add the loading_label to it with stretch factors
        # Create a QHBoxLayout and add the loading_label to it with stretch factors
        loading_animation_layout = QHBoxLayout()
        loading_animation_layout.addStretch(1)
        loading_animation_layout.addWidget(self.loading_label)
        loading_animation_layout.addStretch(1)

        # Add the loading_label widget to the chat area's layout
        scroll_layout.addWidget(self.loading_label)
        scroll_layout.setStretchFactor(self.loading_label, 1)
        scroll_layout.addWidget(self.chat_widget)
        scroll_layout.setStretchFactor(self.chat_widget, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_chat_labels()

        # Update the loading_label width when the window is resized
        self.loading_label.setMaximumWidth(int(self.chat_area.width() * 0.10))

    def show_loading_animation(self):
        self.loading_label.show()
        self.loading_movie.start()

    def hide_loading_animation(self):
        self.loading_movie.stop()
        self.loading_label.hide()

    def on_scrollbar_value_changed(self, value):
        if value == 0:
            self.load_older_chat_history()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.Scroll and source == self.chat_area.viewport():
            if self.chat_area.verticalScrollBar().value() == 0:
                self.load_older_chat_history()
        return super().eventFilter(source, event)

    def dark_mode(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)

    def create_chat_label(self, message):
        formatted_text, formatted_time, formatted_model = self.format_chat_message(message)
        chat_label = QLabel(formatted_text)
        chat_label.setWordWrap(True)
        chat_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        chat_label.setFixedWidth(int(self.chat_area.width() * 0.7))
        chat_label.adjustSize()
        chat_label.mousePressEvent = lambda event: self.on_chat_label_click(chat_label, formatted_time, formatted_model)

        if message['role'] == 'assistant':
            chat_label.setStyleSheet(
                "background-color: #6C757D; color: white; border-radius: 5px; padding: 5px; margin: 2px;")
        else:
            chat_label.setStyleSheet(
                "background-color: #343A40; color: white; border-radius: 5px; padding: 5px; margin: 2px;")

        return chat_label

    def on_chat_label_click(self, chat_label, formatted_time, formatted_model):
        if hasattr(self, 'selected_chat_label'):
            self.selected_chat_label.setStyleSheet("")
            self.selected_chat_label.setGraphicsEffect(None)

        self.selected_chat_label = chat_label
        chat_label.setStyleSheet("border: 1px solid #888; background-color: rgba(0, 0, 0, 0.1);")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setColor(QColor(0, 0, 0, 128))
        shadow.setOffset(2, 2)
        chat_label.setGraphicsEffect(shadow)

        chat_label.setText(f"<b>{formatted_time}</b> {chat_label.text()} <div align='right'><b>{formatted_model}</b></div>")

    def format_chat_message(self, message):
        role = message["role"]
        content = message["content"]
        time_str = self.format_time(message.get("utc_time",""))
        model_str = message.get("model", "")

        formatted_time = f"{role.capitalize()} at {time_str}:"
        formatted_model = f"Model: {model_str}" if model_str else ""

        formatted_text = f"{content}"
        return formatted_text, formatted_time, formatted_model

    def format_time(self, utc_time):
        if utc_time == "":
            return ""
        dt = datetime.datetime.strptime(utc_time, "%Y-%m-%d %H:%M:%S.%f")
        local_time = dt.astimezone()
        formatted_time = local_time.strftime("%A, %B %d, %Y at %I:%M %p")
        return formatted_time

    def update_chat_labels(self):
        for index in range(self.chat_widget.layout().count()):
            item = self.chat_widget.layout().itemAt(index)
            if item:
                layout = item.layout()
                if layout:
                    chat_label = layout.itemAt(0).widget()
                    if chat_label:
                        chat_label.setFixedWidth(int(self.chat_area.width() * 0.7))
                        chat_label.adjustSize()

    def load_chat_history(self):
        chat_history = get_chat_history()
        for message in chat_history:
            chat_label = self.create_chat_label(message)
            layout = self.create_chat_layout(message, chat_label)
            self.chat_widget.layout().addLayout(layout)

    def refresh_recent_history(self):
        chat_history = get_chat_history(limit=1)
        if chat_history:
            most_recent_message = chat_history[0]
            formatted_message = format_message(most_recent_message)
            chat_label = QLabel(formatted_message)
            chat_label.setWordWrap(True)
            self.chat_widget.layout().addWidget(chat_label)

    def create_chat_layout(self, message, chat_label):
        layout = QHBoxLayout()

        if message["role"] == "user":
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(chat_label)

        return layout

    def add_message_to_chat(self, message, position="bottom"):
        chat_label = self.create_chat_label(message)
        layout = self.create_chat_layout(message, chat_label)

        if position == "top":
            self.chat_widget.layout().insertLayout(0, layout)
        else:
            self.chat_widget.layout().addLayout(layout)

        message_id = message.get("id")
        if message_id is not None:
            if self.oldest_message_id is None or message_id < self.oldest_message_id:
                self.oldest_message_id = message_id

    def load_initial_chat_history(self):
        chat_history = get_chat_history()
        for message in chat_history:
            self.add_message_to_chat(message)

    def update_chat(self):
        while not self.queue.empty():
            message = self.queue.get()
            self.add_message_to_chat(message)

    def load_older_chat_history(self):
        self.hide_loading_animation_and_scroll_to_top()
        QTimer.singleShot(2000, self.hide_loading_animation_and_load_history)

    def hide_loading_animation_and_load_history(self):
        if self.oldest_message_id is not None:
            older_chat_history = get_chat_history(id=str(int(self.oldest_message_id) - 1))
            if older_chat_history:
                for message in reversed(older_chat_history):
                    self.add_message_to_chat(message, position="top")
        self.hide_loading_animation()

    def hide_loading_animation_and_scroll_to_top(self):
        self.hide_loading_animation()
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().minimum())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    queue = Queue()
    # Add some sample messages to the queue


    main_window = ChatWindow(queue)
    main_window.load_initial_chat_history()
    main_window.show()

    queue.put({"role": "user", "content": "Hello, how are you?"})
    queue.put({"role": "assistant", "content": "I'm doing well, thank you!", "model": "gpt-4"})

    sys.exit(app.exec())
