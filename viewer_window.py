import os
import urllib
import sys
import datetime

from PySide6.QtCore import Qt, QTimer, QFile, QTextStream
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy
from PySide6.QtGui import QMovie, QColor, QPainter, QPainterPath
from PySide6.QtWebEngineWidgets import QWebEngineView

from processor import get_chat_history
from animation import JarvisWaveform
from multiprocessing import Queue


def load_stylesheet() -> str:
    """
    Load the stylesheet for the application.

    :return: The stylesheet content.
    :rtype: str
    """
    prefix = ""
    if getattr(sys, 'frozen', False):
        prefix = sys._MEIPASS + "/"
    file = QFile(prefix+"style.qss")
    file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(file)
    return stream.readAll()


def format_message(text: str) -> str:
    """
    Format the message to be displayed.

    :param text: The input text to be formatted.
    :type text: str
    :return: The formatted message.
    :rtype: str
    """
    first_text = text[:150]
    rest = text[150:]
    am_index = first_text.find("AM:")
    pm_index = first_text.find("PM:")
    if am_index != -1:
        first = first_text[am_index + 3:]
    elif pm_index != -1:
        first = first_text[pm_index + 3:]
    else:
        first = first_text
    output = first + rest
    return output


def generate_typing_code(content: str, role: str) -> str:
    """
    Generate typing animation code.

    :param content: The content to be typed.
    :type content: str
    :param role: The role of the typist.
    :type role: str
    :return: The typing animation code.
    :rtype: str
    """
    code = []
    i = 0
    for char in content:
        encoded_char = urllib.parse.quote(char)
        code.append(f"setTimeout(function() {{typedText += "
                    f"decodeURIComponent('{encoded_char}'); span.textContent = "
                    f"typedText;}}, {role}_typing_speed * {i});")
        i += 1
    return "".join(code)


class GrayLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)

    def paintEvent(self, event) -> None:
        """
        Paint event for the GrayLine widget.

        :param event: The paint event.
        :type event: QPaintEvent
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gray_color = QColor("#262b30")
        painter.setBrush(gray_color)
        painter.setPen(Qt.NoPen)
        width = self.width() * 0.7
        x_offset = self.width() * 0.15
        height = self.height()
        radius = 2  # adjust the radius of rounded corners here

        path = QPainterPath()
        path.addRoundedRect(x_offset, 0, width, height, radius, radius)
        painter.drawPath(path)


class ChatWindow(QMainWindow):
    """
    A custom QMainWindow class for displaying chat history and real-time messages in a user-friendly interface.

    The ChatWindow class consists of a chat history area and a real-time message area, along with a JarvisWaveform
    widget for visualizing speech. The chat history area displays past messages, while the real-time message area
    shows the current conversation as it happens. The interface also includes a talking animation to indicate
    whether Jarvis is speaking, listening, thinking, etc.
    """
    def __init__(self):
        """
        Initialize the ChatWindow class.
        """
        super().__init__()
        self.saved_scroll_position = None
        self.queue = None
        self.oldest_message_id = None
        self.largest_message_id = None
        self.last_rt_message_role = None
        self.messages_in_history_area = 0
        self.retry_count = 0
        self.init_ui()

    def init_ui(self):
        """
        Initialize the user interface.

        The user interface consists of a chat history area and a real-time message area, along with a JarvisWaveform
        widget for visualizing speech.
        """
        self.setWindowTitle("Jarvis Assistant History and Chat")
        self.resize(800, 600)
        self.setStyleSheet(load_stylesheet())
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.central_widget.setLayout(main_layout)

        # Zones 1 and 2 - Loading animation and Chat history
        zone_1_and_2_widget = QWidget()
        zone_1_and_2_layout = QVBoxLayout()
        zone_1_and_2_layout.setContentsMargins(0, 0, 0, 10)
        zone_1_and_2_layout.setSpacing(0)
        zone_1_and_2_widget.setLayout(zone_1_and_2_layout)
        main_layout.addWidget(zone_1_and_2_widget)
        main_layout.setStretchFactor(zone_1_and_2_widget, 3)

        # Gray line
        gray_line = GrayLine(self.central_widget)
        main_layout.addWidget(gray_line)
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
        zones_3_and_4_layout.setContentsMargins(0, 10, 0, 0)
        zones_3_and_4_layout.setSpacing(0)
        zones_3_and_4_widget.setLayout(zones_3_and_4_layout)
        main_layout.addWidget(zones_3_and_4_widget)
        main_layout.setStretchFactor(zones_3_and_4_widget, 1)

        # Zone 3 - JarvisWaveform
        self.jarvis_waveform = JarvisWaveform()
        self.jarvis_waveform.setFixedWidth(int(self.width() * 0.25))
        zones_3_and_4_layout.addWidget(self.jarvis_waveform)

        # Zone 4 - Real-time messages
        self.chat_area_realtime = QWebEngineView(self)
        self.chat_area_realtime.setHtml(initial_html)
        zones_3_and_4_layout.addWidget(self.chat_area_realtime)

        # Create loading animation after initializing chat_area_history
        self.create_loading_animation()

        self.chat_area_history.installEventFilter(self)

        def update_chat_timer():
            """
            Create a QTimer to update the chat history and real-time messages.
            """
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

    def attach_queue(self, queue):
        """
        Attach a text queue to the ChatWindow so that it can receive messages from the main thread.
        """
        self.queue = queue

    def create_loading_animation(self):
        """
        Create a loading animation to display when Jarvis is thinking, speaking, or listening.
        """
        icons_path = "icons/"
        if getattr(sys, "frozen", False):
            icons_path = os.path.join(sys._MEIPASS, icons_path)
        self.loading_movie = QMovie(icons_path + "loading.gif")
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
        """
        Re-position the loading animation when the window is resized.
        """
        super().resizeEvent(event)
        self.position_loading_animation()

    def position_loading_animation(self):
        """
        Position the loading animation in the center of the chat history.
        """
        self.loading_label.setMaximumWidth(int(self.chat_area_history.width() * 0.10))
        self.loading_label.move(
            int((self.chat_area_history.width() - self.loading_label.width()) / 2),
            int((self.chat_area_history.height() - self.loading_label.height()) / 2)
        )

    def show_loading_animation(self):
        """
        Show the loading animation.
        """
        self.position_loading_animation()
        self.loading_label.show()
        self.loading_movie.start()

    def hide_loading_animation(self):
        """
        Hide the loading animation.
        """
        self.loading_movie.stop()
        self.loading_label.hide()

    def check_scroll_position(self):
        """
        Check the scroll position of the chat history. Then send that information to handle_scroll_position.
        """
        js_script = "window.pageYOffset"
        self.chat_area_history.page().runJavaScript(js_script, 0, self.handle_scroll_position)

    def handle_scroll_position(self, value):
        """
        Handle the scroll position of the chat history. If the user is at the top of the chat history,
        load older messages.
        """
        if value == 0 and self.messages_in_history_area > 4:
            self.load_older_chat_history()

    def add_message_to_chat(self, chat_area, message, add_to_bottom=False,
                            appear_as_typed=False, append_to_last_bubble=False):
        """
        Add a message to the chat history or real-time messages.

        This function is critical to the ChatWindow. It is responsible for adding messages to the chat history and
        real-time messages. It also handles the logic for appending messages to the last bubble, appearing as if the
        message is being typed, and adding messages to the bottom of the chat history. It uses a combination of
        JavaScript and Python to accomplish this.

        :param chat_area: The chat area to add the message to.
        :type chat_area: QWebEngineView
        :param message: The message to add to the chat area.
        :type message: dict
        :param add_to_bottom: Whether to add the message to the bottom of the chat area.
        :type add_to_bottom: bool
        :param appear_as_typed: Whether to appear as if the message is being typed.
        :type appear_as_typed: bool
        :param append_to_last_bubble: Whether to append the message to the last bubble.
        :type append_to_last_bubble: bool
        :return: None
        """
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
        if append_to_last_bubble:
            content = " " + content
        else:
            self.messages_in_history_area += 1
        timestamp_str = message.get("utc_time", None)
        if timestamp_str:
            timestamp_obj = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
            timestamp = timestamp_obj.strftime("%A, %B %d, %Y at %I:%M %p")
        else:
            timestamp = ""

        model_info = ""
        if message.get("model"):
            model_info = f"From {message['model']}"
            if timestamp != "":
                timestamp = " on " + timestamp

        if role == "user":
            bubble_color = "#6C757D"
            bubble_align = "right"
            outer_margin = "0 5% 15px 30%"
        else:
            bubble_color = "#6c88a1"
            bubble_align = "left"
            outer_margin = "0 30% 15px 5%"

        formatted_text = f"""
                    <div class="chat-bubble" style="
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

        if appear_as_typed:
            typing_delay = "50"  # you can adjust the typing speed by changing this value
            typing_code = generate_typing_code(content, role)
            typing_code = typing_code.replace('\n', ' ')
        else:
            typing_delay = "50"
            typing_code = ""

        js_appear_as_typed = str(appear_as_typed).lower()

        js_script_without_typing = f"""
            var new_div = document.createElement('div');
            new_div.innerHTML = `{formatted_text}`;
            if ({str(add_to_bottom).lower()}) {{
                var body = document.getElementsByTagName('body')[0];
                body.appendChild(new_div);
                window.scrollTo(0, document.body.scrollHeight);
            }} else {{
                var old_scroll_position = window.pageYOffset;
                var body = document.getElementsByTagName('body')[0];
                body.insertBefore(new_div, body.firstChild);
                var new_scroll_position = window.pageYOffset;
                var scroll_difference = new_div.offsetHeight;
                window.scrollTo(0, old_scroll_position + scroll_difference);
            }}
        """

        js_script = f"""
            function process_{role}_typing_queue() {{
                if ({role}_typing_queue.length > 0) {{
                    var message = {role}_typing_queue[0];
                    var new_div = document.createElement('div');
                    new_div.innerHTML = message.formatted_text;
                    var body = document.getElementsByTagName('body')[0];

                    if (message.add_to_bottom && message.append_to_last_bubble) {{
                        var last_bubble = body.getElementsByClassName('chat-bubble');
                        last_bubble = last_bubble[last_bubble.length - 1];
                        var span = last_bubble.getElementsByTagName('span')[0];
                        typedText = span.textContent;
                        {role}_typing_speed = message.typing_delay;

                        if (message.appear_as_typed) {{
                            var newText = message.formatted_text.match(/<span[^>]*>([^<]+)<\/span>/)[1];
                            var index = 0;
                            function type() {{
                                if (index < newText.length) {{
                                    span.innerHTML += newText.charAt(index);
                                    index++;
                                    window.scrollTo(0, document.body.scrollHeight);
                                    setTimeout(type, {role}_typing_speed);
                                }} else {{
                                    {role}_typing_queue.shift();
                                    process_{role}_typing_queue();
                                }}
                            }}
                            type();
                        }} else {{
                            span.textContent += message.formatted_text.match(/<span[^>]*>([^<]+)<\/span>/)[1] + " ";
                            {role}_typing_queue.shift();
                            process_{role}_typing_queue();
                        }}
                    }}

                    else {{
                        if (message.add_to_bottom) {{
                            body.appendChild(new_div);
                        }} else {{
                            body.insertBefore(new_div, body.firstChild);
                        }}

                        if (message.appear_as_typed) {{
                            var span = new_div.getElementsByClassName('chat-bubble')[0].getElementsByTagName('span')[0];
                            span.innerHTML = "";
                            var typedText = "";
                            {role}_typing_speed = message.typing_delay;
                            var newText = message.formatted_text.match(/<span[^>]*>([^<]+)<\/span>/)[1];
                            var index = 0;
                            function type() {{
                                if (index < newText.length) {{
                                    span.innerHTML += newText.charAt(index);
                                    index++;
                                    window.scrollTo(0, document.body.scrollHeight);
                                    setTimeout(type, {role}_typing_speed);
                                }} else {{
                                    {role}_typing_queue.shift();
                                    process_{role}_typing_queue();
                                }}
                            }}
                            type();
                        }} else {{
                            {role}_typing_queue.shift();  // Added this line
                            process_{role}_typing_queue();  // Added this line
                        }}
                    }}
                }}
            }}

            if ({js_appear_as_typed}) {{
                var message = {{
                    formatted_text: `{formatted_text}`,
                    add_to_bottom: {str(add_to_bottom).lower()},
                    append_to_last_bubble: {str(append_to_last_bubble).lower()},
                    appear_as_typed: {js_appear_as_typed},
                    typing_delay: {typing_delay},
                    typing_code: `{typing_code}`
                }};
                {role}_typing_queue.push(message);
                if ({role}_typing_queue.length === 1) {{
                    process_{role}_typing_queue();
                }} else if (('{'{role}'}') === 'assistant') {{
                    user_typing_speed = 5; // Speed up user messages when an assistant message is queued
                }}
            }} else {{
                {js_script_without_typing}
            }}
        """

        chat_area.page().runJavaScript("""
            if (typeof user_typing_queue === 'undefined') {
                user_typing_queue = [];
                user_typing_speed = 50;
            }
            if (typeof assistant_typing_queue === 'undefined') {
                assistant_typing_queue = [];
                assistant_typing_speed = 50;
            }
        """)

        chat_area.page().runJavaScript(js_script)

    def update_chat(self):
        """
        Updates the chat area with the messages in the queue.

        This function is called every 100 milliseconds. And it checks if there are any messages in the queue and if so,
        it adds them to the chat area using the add_message_to_chat function. Sometimes, the queue contains a message
        that is meant to clear the realtime chat area. In that case, this function clears the real time chat area and
        then adds the messages in the queue to the historical chat area.
        """
        if self.queue:
            while not self.queue.empty():
                message = self.queue.get()
                if message.get("finished", False):
                    self.clear_realtime_chat()
                    for each_message in reversed(message["results"]):
                        self.add_message_to_chat(self.chat_area_history, each_message, add_to_bottom=True)
                else:
                    if message.get("clear", False):
                        self.clear_realtime_chat()
                    else:
                        self.add_message_to_realtime_chat(message)

    def clear_realtime_chat(self):
        """
        Clears the realtime chat area.

        This function is called when the queue contains a message that is meant to clear the realtime chat area.
        We use the setHtml function to set the html of the realtime chat area to an empty string.
        """
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
        self.chat_area_realtime.setHtml(initial_html)

    def load_initial_chat_history(self):
        """
        Loads the initial chat history.

        This function is called when the chat window is opened. It loads the initial chat history from the database
        and adds it to the historical chat area. It also positions the loading animation.
        """
        chat_history = get_chat_history(limit=6)
        for message in chat_history:
            self.add_message_to_chat(self.chat_area_history, message)
        QTimer.singleShot(10, self.position_loading_animation)

    def add_message_to_realtime_chat(self, message):
        """
        Adds a message to the realtime chat area.

        This function is called when the queue contains a message that is meant to be added to the realtime chat area.
        It uses the add_message_to_chat function to add the message to the realtime chat area. It has to check if the
        message is from the same role as the last message in the realtime chat area. If it is, then it adds the message
        to the last bubble in the realtime chat area. If it is not, then it adds the message to the realtime chat area
        as a new bubble.

        :param message: The message to be added to the realtime chat area.
        :type message: dict
        :return: None
        """
        if message.get("role"):
            if self.last_rt_message_role is None:
                self.last_rt_message_role = message.get("role")
                self.add_message_to_chat(self.chat_area_realtime, message, add_to_bottom=True, appear_as_typed=True)
            elif message.get("role") == self.last_rt_message_role:
                self.last_rt_message_role = message.get("role")
                self.add_message_to_chat(self.chat_area_realtime, message, add_to_bottom=True,
                                         appear_as_typed=True, append_to_last_bubble=True)
            else:
                self.last_rt_message_role = message.get("role")
                self.add_message_to_chat(self.chat_area_realtime, message, add_to_bottom=True, appear_as_typed=True)
        else:
            self.add_message_to_chat(self.chat_area_realtime, message, add_to_bottom=True, appear_as_typed=True)

    def load_older_chat_history(self):
        """
        Loads older chat history.

        This function is called when the user scrolls to the top of the historical chat area. It loads older chat
        history from the database and adds it to the historical chat area. It also delays the calling of the
        hide_loading_animation_and_load_history function by 300 milliseconds to give the loading animation time to
        appear.
        """
        self.show_loading_animation()
        QTimer.singleShot(300, self.hide_loading_animation_and_load_history)

    def hide_loading_animation_and_load_history(self):
        """
        Hides the loading animation and loads older chat history.

        This function is called after the loading animation has appeared. It loads older chat history from the database
        and adds it to the historical chat area. It also sets the oldest_message_id variable to the id of the oldest
        message in the historical chat area. It also hides the loading animation.
        """
        if self.oldest_message_id is not None:
            older_chat_history = None
            if (self.oldest_message_id - 1) > 0:
                older_chat_history = get_chat_history(id=str(self.oldest_message_id - 1), limit=8)
            else:
                self.hide_loading_animation()
            if older_chat_history:
                for message in older_chat_history:
                    self.add_message_to_chat(self.chat_area_history, message)
                self.hide_loading_animation()
        else:
            self.hide_loading_animation()

    def closeEvent(self, event):
        """
        Overrides the closeEvent function.

        This function is called when the user closes the chat window. It hides the chat window instead of closing it.
        This is done so that the chat window can be shown again without having to create a new instance of the chat.

        :param event: The close event.
        :type event: QCloseEvent
        :return: None
        """
        event.ignore()
        self.hide()


if __name__ == "__main__":
    app = QApplication([])
    queue = Queue()
    main_window = ChatWindow()
    main_window.attach_queue(queue)
    QTimer.singleShot(50, lambda: main_window.show())

    QTimer.singleShot(300, lambda: queue.put({"role": "user", "content": "Hello, how are you?"}))
    QTimer.singleShot(500, lambda: queue.put(
        {"role": "assistant", "content": "I'm doing well, thank you!", "model": "gpt-4"}))
    QTimer.singleShot(530, lambda: queue.put(
        {"role": "assistant", "content": "I'm doing well, thank you!", "model": "gpt-4"}))
    QTimer.singleShot(540, lambda: queue.put(
        {"role": "assistant", "content": "I'm doing well, thank you!", "model": "gpt-4"}))
    QTimer.singleShot(4830, lambda: queue.put(
        {"role": "assistant", "content": "I'm doing well, thank you!", "model": "gpt-4"}))
    main_window.jarvis_waveform.update_icon_path("icons/listening.png")
    sys.exit(app.exec())
