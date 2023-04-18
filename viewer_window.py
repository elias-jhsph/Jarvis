from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, \
    QSizePolicy
from PySide6.QtGui import QMovie, QColor, QPalette
from PySide6.QtWebEngineWidgets import QWebEngineView
from processor import get_chat_history
from animation import JarvisWaveform
from multiprocessing import Queue
import sys
import datetime


def format_message(text):
    first_hundred = text[:150]
    rest = text[150:]
    am_index = first_hundred.find("AM:")
    pm_index = first_hundred.find("PM:")
    if am_index != -1:
        first = first_hundred[am_index + 3:]
    elif pm_index != -1:
        first = first_hundred[pm_index + 3:]
    else:
        first = first_hundred
    output = first + rest
    return output


class ChatWindow(QMainWindow):
    def __init__(self, queue):
        super().__init__()
        self.saved_scroll_position = None
        self.queue = queue
        self.oldest_message_id = None
        self.largest_message_id = None
        self.retry_count = 0
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Jarvis Assistant History and Chat")
        self.resize(800, 600)
        self.setStyleSheet("border: 10px solid black; background-color: black;")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.central_widget.setLayout(main_layout)

        # Zones 1 and 2 - Loading animation and Chat history
        zone_1_and_2_widget = QWidget()
        zone_1_and_2_layout = QVBoxLayout()
        zone_1_and_2_layout.setContentsMargins(0, 0, 0, 0)
        zone_1_and_2_layout.setSpacing(0)
        zone_1_and_2_widget.setLayout(zone_1_and_2_layout)
        main_layout.addWidget(zone_1_and_2_widget)
        main_layout.setStretchFactor(zone_1_and_2_widget, 3)

        # set up

        initial_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    font-family: Arial, sans-serif;
                    background-color: black;
                }
            </style>
        </head>
        <body>
        </body>
        </html>
        """

        # Zone 2 - Chat history
        self.chat_area_history = QWebEngineView(self)
        self.chat_area_history.setHtml(initial_html)
        self.scroll_check_timer = QTimer()
        self.scroll_check_timer.timeout.connect(self.check_scroll_position)
        zone_1_and_2_layout.addWidget(self.chat_area_history)

        # Zones 3 and 4 - JarvisWaveform and Real-time messages
        zones_3_and_4_widget = QWidget()
        zones_3_and_4_layout = QHBoxLayout()
        zones_3_and_4_layout.setContentsMargins(0, 5, 0, 0)
        zones_3_and_4_layout.setSpacing(0)
        zones_3_and_4_widget.setLayout(zones_3_and_4_layout)
        main_layout.addWidget(zones_3_and_4_widget)
        main_layout.setStretchFactor(zones_3_and_4_widget, 1)

        # Zone 3 - JarvisWaveform
        self.jarvis_waveform_container = QWidget()
        self.jarvis_waveform_container.setFixedWidth(int(self.width() * 0.25))
        self.jarvis_waveform_container.setStyleSheet(
            "background-color: white; border: 10px solid white; border-radius: 40px;")

        self.jarvis_waveform = JarvisWaveform(self.jarvis_waveform_container)

        jarvis_waveform_container_layout = QVBoxLayout()
        jarvis_waveform_container_layout.addWidget(self.jarvis_waveform)
        self.jarvis_waveform_container.setLayout(jarvis_waveform_container_layout)

        zones_3_and_4_layout.addWidget(self.jarvis_waveform_container)

        # Zone 4 - Real-time messages
        self.chat_area_realtime = QWebEngineView(self)
        self.chat_area_realtime.setHtml(initial_html)
        zones_3_and_4_layout.addWidget(self.chat_area_realtime)

        # Create loading animation after initializing chat_area_history
        self.create_loading_animation()

        self.chat_area_history.installEventFilter(self)

        def update_chat_timer():
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_chat)
            self.update_timer.start(1000)

        self.chat_area_history.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.chat_area_realtime.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.chat_area_history.loadFinished.connect(self.load_initial_chat_history)
        self.chat_area_history.loadFinished.connect(self.scroll_check_timer.start(2000))
        self.chat_area_realtime.loadFinished.connect(update_chat_timer())
        self.chat_area_history.setStyleSheet("background-color: black;")
        self.chat_area_realtime.setStyleSheet("background-color: black;")

    def create_loading_animation(self):
        self.loading_movie = QMovie("icons/loading.gif")
        self.loading_label = QLabel(self)
        self.loading_label.setMovie(self.loading_movie)
        self.loading_label.setScaledContents(True)
        self.loading_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.loading_label.hide()
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("background-color: transparent; border: none;")

        gif_size = int(self.width() * 0.1)
        self.loading_label.setFixedSize(gif_size, gif_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_loading_animation()

    def position_loading_animation(self):
        self.loading_label.setMaximumWidth(int(self.chat_area_history.width() * 0.10))
        self.loading_label.move(
            int((self.chat_area_history.width() - self.loading_label.width()) / 2),
            int((self.chat_area_history.height() - self.loading_label.height()) / 2)
        )

    def show_loading_animation(self):
        self.loading_label.show()
        self.loading_movie.start()

    def hide_loading_animation(self):
        self.loading_movie.stop()
        self.loading_label.hide()

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

    def check_scroll_position(self):
        js_script = "window.pageYOffset"
        self.chat_area_history.page().runJavaScript(js_script, 0, self.handle_scroll_position)

    def handle_scroll_position(self, value):
        if value == 0:
            self.load_older_chat_history()

    def add_message_to_chat(self, chat_area, message, add_to_bottom=False):
        id = message.get("id", None)
        if id is not None:
            if self.oldest_message_id is None:
                self.oldest_message_id = int(id)
            if int(id) < self.oldest_message_id:
                self.oldest_message_id = int(id)
            if self.largest_message_id is None:
                self.largest_message_id = int(id)
            if int(id) > self.largest_message_id:
                self.largest_message_id = int(id)
        role = message["role"]
        content = format_message(message["content"]).lstrip()

        timestamp_str = message.get("utc_time", None)
        if timestamp_str:
            timestamp_obj = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
            timestamp = timestamp_obj.strftime("%A, %B %d, %Y at %I:%M %p")
        else:
            timestamp = ""

        model_info = ""
        if message.get("model"):
            model_info = f"From {message['model']} on "

        if role == "user":
            bubble_color = "#6C757D"
            bubble_align = "right"
            outer_margin = "0 5% 15px 30%"
        else:
            bubble_color = "#6c88a1"
            bubble_align = "left"
            outer_margin = "0 30% 15px 5%"

        formatted_text = f"""
                    <div style="
                        display: flex;
                        flex-direction: column;
                        align-items: {bubble_align};
                        margin: {outer_margin};
                    ">
                        <div style="
                            background-color: {bubble_color};
                            color: white;
                            border-radius: 16px;
                            padding: 10px 14px;
                            display: inline-block;
                            max-width: 100%;
                            text-align: left;
                            word-wrap: break-word;
                            {('border-top-left-radius: 4px;' if role == 'assistant' else 'border-top-right-radius: 4px;')}
                        ">
                            <span style="white-space: pre-wrap;">{content}</span>
                        </div>
                        <div style="display: inline-block; margin: 5px 0; font-size: 10px; color: #999;">
                            {model_info}{timestamp}
                        </div>
                    </div>
                """
        if add_to_bottom:
            js_script = f"""
                    var new_div = document.createElement('div');
                    new_div.innerHTML = `{formatted_text}`;
                    var body = document.getElementsByTagName('body')[0];
                    body.appendChild(new_div);
                """
        else:
            js_script = f"""
                var old_scroll_position = window.pageYOffset;
                var new_div = document.createElement('div');
                new_div.innerHTML = `{formatted_text}`;
                var body = document.getElementsByTagName('body')[0];
                body.insertBefore(new_div, body.firstChild);
                var new_scroll_position = window.pageYOffset;
                var scroll_difference = new_div.offsetHeight;
                window.scrollTo(0, old_scroll_position + scroll_difference);
            """

        chat_area.page().runJavaScript(js_script)

    def update_chat(self):
        while not self.queue.empty():
            message = self.queue.get()
            if message == {}:
                self.clear_realtime_chat()
                self.load_last_two_history_messages()
            else:
                self.add_message_to_realtime_chat(message)

    def clear_realtime_chat(self):
        self.chat_area_realtime.clear()

    def load_initial_chat_history(self):
        chat_history = get_chat_history(limit=6)
        for message in chat_history:
            self.add_message_to_chat(self.chat_area_history, message)
        QTimer.singleShot(10, self.position_loading_animation)

    def load_last_two_history_messages(self):
        # Load last two messages from history and add them to Zone 2
        chat_history = get_chat_history(limit=2)
        if int(chat_history[0]["id"]) + 1 == self.largest_message_id:
            for message in reversed(chat_history):
                self.add_message_to_chat(self.chat_area_history, message, add_to_bottom=True)
        else:
            if self.retry_count < 5:
                self.retry_count += 1
                QTimer.singleShot(500, self.load_last_two_history_messages)
            else:
                self.retry_count = 0

    def add_message_to_realtime_chat(self, message):
        self.add_message_to_chat(self.chat_area_realtime, message, add_to_bottom=True)

    def load_older_chat_history(self):
        self.show_loading_animation()
        QTimer.singleShot(500, self.hide_loading_animation_and_load_history)

    def hide_loading_animation_and_load_history(self):
        if self.oldest_message_id is not None:
            older_chat_history = None
            if (self.oldest_message_id - 1) > 0:
                older_chat_history = get_chat_history(id=str(self.oldest_message_id - 1), limit=4)
            if older_chat_history:
                for message in older_chat_history:
                    self.add_message_to_chat(self.chat_area_history, message)
                self.hide_loading_animation()
        else:
            self.hide_loading_animation()

    def closeEvent(self, event):
        self.jarvis_waveform.closeEvent(event)
        event.accept()


if __name__ == "__main__":
    app = QApplication([])
    queue = Queue()
    main_window = ChatWindow(queue)
    main_window.show()

    queue.put({"role": "user", "content": "Hello, how are you?"})
    queue.put({"role": "assistant", "content": "I'm doing well, thank you!", "model": "gpt-4"})
    # queue.put({})
    main_window.jarvis_waveform.update_icon_path("icons/listening.png")
    sys.exit(app.exec())
