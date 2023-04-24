import sys
import os
import time
import threading
import multiprocessing
import atexit

current_dir = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(current_dir, '..', 'Frameworks')
numpy_dir = os.path.join(current_dir, 'Resources', 'lib', 'python3.10', 'numpy', '.dylibs')
if 'DYLD_LIBRARY_PATH' in os.environ:
    os.environ['DYLD_LIBRARY_PATH'] = f"{lib_dir}:{numpy_dir}:{os.environ['DYLD_LIBRARY_PATH']}"
else:
    os.environ['DYLD_LIBRARY_PATH'] = f"{lib_dir}:{numpy_dir}"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
import settings_menu
import viewer_window
import connections
from jarvis_process import jarvis_process
from jarvis_interrupter import stop_word_detection

import logger_config

logger = logger_config.get_logger()


def clean_up_files() -> None:
    """
    Clean up audio and email files from previous runs.

    :return: None
    """
    folder = "audio_output"
    if not os.path.exists(folder):
        os.makedirs(folder)
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.warning(f"Deleted old audio file: {file_path}")
        except Exception as e:
            logger.exception(f"Error deleting file: {file_path}. Reason: {e}")
    folder = "email_drafts"
    if not os.path.exists(folder):
        os.makedirs(folder)
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.warning(f"Deleted old email file: {file_path}")
        except Exception as e:
            logger.exception(f"Error deleting file: {file_path}. Reason: {e}")


class JarvisApp(QApplication):
    """
    Main application class for Jarvis.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("CWD " + os.getcwd())
        self.config = {
            "app_name": "Jarvis",
            "start": "Start Listening",
            "stop": "Stop Listening",
            "quit": "Quit",
            "settings": "Settings",
            "break_message": "Stopped",
            "interrupt": "Jarvis, Stop.",
            "viewer": "Live Chat / History",
        }
        self.codes = connections.get_connection_ring()

        self.menu = QMenu()

        self.start_stop_action = QAction(self.config["start"], self)
        self.start_stop_action.triggered.connect(self.start_stop_listener)
        self.menu.addAction(self.start_stop_action)

        self.interrupt_action = QAction(self.config["interrupt"], self)
        self.interrupt_action.triggered.connect(self.interrupt_listener)
        self.menu.addAction(self.interrupt_action)

        self.settings_action = QAction(self.config["settings"], self)
        self.settings_action.triggered.connect(self.settings_listener)
        self.menu.addAction(self.settings_action)

        self.viewer_action = QAction(self.config["viewer"], self)
        self.viewer_action.triggered.connect(self.viewer_listener)
        self.menu.addAction(self.viewer_action)

        self.quit_action = QAction(self.config["quit"], self)
        self.quit_action.triggered.connect(self.quit_listener)
        self.menu.addAction(self.quit_action)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setContextMenu(self.menu)

        # Initialize variables
        self.strobe_speed = 1
        self.strobe_fast_speed = 0.5
        self.ps = None
        self.ps_interrupter = None
        self.settings = settings_menu.SettingsDialog()
        self.viewer = viewer_window.ChatWindow()
        self._set_environment()
        self.message_queue = None
        self.chat_queue = None
        self.process_status = None
        self.stop_event = multiprocessing.Event()
        self.skip_event = multiprocessing.Event()
        self.icon_thread = None
        self.animation_thread = None
        clean_up_files()
        atexit.register(self.cleanup)
        logger.info("Ready!")
        self.icon = "icons/icon.icns"
        self.tray_icon.setIcon(QIcon(self.icon))
        self.tray_icon.setVisible(True)
        self.tray_icon.show()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(lambda: self.viewer.jarvis_waveform.update_icon_path(self.icon))
        self.update_timer.start(300)

    def settings_listener(self) -> None:
        """Opens the settings pop-up menu."""
        if not self.settings.isVisible():
            self.settings.update_item_colors()
            self.settings.show()

    def viewer_listener(self) -> None:
        """Opens the settings pop-up menu."""
        if not self.viewer.isVisible():
            self.viewer.show()

    def on_settings_closed(self) -> None:
        """Updates the settings when the settings pop-up menu is closed."""
        self.settings = None
        self.settings = connections.get_connection_ring()

    def interrupt_listener(self) -> None:
        """Interrupts the current process."""
        logger.info("Interrupting process")
        self.skip_event.set()

    def flash_icon(self) -> None:
        default_icon = "icons/icon.icns"
        while self.message_queue is not None:
            if not self.message_queue.empty():
                self.process_status = self.message_queue.get()
            if self.process_status == "standby":
                self.skip_event.clear()
                if self.icon == default_icon:
                    self.icon = "icons/listening.icns"  # Change to the second icon
                else:
                    self.icon = default_icon  # Change back to the first icon
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_speed)
            elif self.process_status == "listening":
                self.icon = "icons/listening.icns"  # Change back to the first icon
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_speed)
            elif self.process_status == "processing":
                if self.icon == "icons/processing_middle.icns":
                    self.icon = "icons/processing_small.icns"
                    # Change to the second icon
                else:
                    self.icon = "icons/processing_middle.icns"
                    # Change back to the first icon
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_speed)
            elif self.process_status == "goodbye":
                self.icon = default_icon
                self.tray_icon.setIcon(QIcon(self.icon))
                break
            else:
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_fast_speed)
        self.icon = default_icon
        self.tray_icon.setIcon(QIcon(self.icon))
        logger.info("Exiting icon thread")

    def start_stop_listener(self) -> None:
        """Starts or continues the listening process."""
        if self.start_stop_action.text() == self.config["start"]:
            if self.ps is None or not self.ps.is_alive():
                self.settings.warning_label.setVisible(False)
                logger.info("Starting listener")
                logger.info("Booting process...")
                self.message_queue = multiprocessing.Queue()
                self.icon_thread = threading.Thread(target=self.flash_icon)
                self.icon_thread.daemon = True
                self.icon_thread.start()
                self.chat_queue = multiprocessing.Queue()
                self.stop_event = multiprocessing.Event()
                self.ps = multiprocessing.Process(target=jarvis_process,
                                                  args=([self.stop_event, self.skip_event,
                                                         self.message_queue, self.chat_queue]))
                self.ps_interrupter = multiprocessing.Process(target=stop_word_detection,
                                                              args=([self.stop_event, self.skip_event]))
                self.viewer.attach_queue(self.chat_queue)
                self.ps.start()
                self.ps_interrupter.start()
                self.start_stop_action.setText(self.config["stop"])
        else:
            self.settings.warning_label.setVisible(False)
            self._safe_kill()
            self.start_stop_action.setText(self.config["start"])

    def quit_listener(self) -> None:
        """Quits the application."""
        logger.info("Trying to quit application")
        self.cleanup()
        logger.info("Goodbye")
        self.quit()

    def _safe_kill(self) -> None:
        if self.ps is not None and self.ps.is_alive():
            self.stop_event.set()
            self.message_queue.put("goodbye")
            time.sleep(1)
            if self.ps.is_alive():
                self.ps.terminate()
                time.sleep(1)
                if self.ps.is_alive():
                    self.ps.kill()
                    logger.info("Hard killed!")
                else:
                    logger.info("Medium killed!")
            else:
                logger.info("Safe killed!")
            if self.ps_interrupter.is_alive():
                self.ps_interrupter.terminate()
                time.sleep(1)
                if self.ps_interrupter.is_alive():
                    self.ps_interrupter.kill()
                    logger.info("Hard killed interrupter!")
                else:
                    logger.info("Medium killed interrupter!")
            self.message_queue = None
            self.chat_queue = None
            self.process_status = None
            time.sleep(1)

    def cleanup(self) -> None:
        """Cleans up resources."""
        self._safe_kill()
        self.viewer.jarvis_waveform.force_close()
        logger.info("Cleaning up resources")
        if self.message_queue is not None:
            self.message_queue.close()
            self.message_queue.join_thread()
        if self.icon_thread is not None:
            self.icon_thread.join()


if __name__ == '__main__':
    logger.info("Starting app...")
    app = JarvisApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())
