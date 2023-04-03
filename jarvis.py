import sys
import os
import time
import threading
import multiprocessing
import atexit
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
import settings_menu
from jarvis_process import jarvis_process

import logger_config

logger = logger_config.get_logger()


def clean_up_files():
    """
    Clean up files from previous runs.
    :return:
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config = {
            "app_name": "Jarvis",
            "start": "Start Listening",
            "stop": "Stop Listening",
            "quit": "Quit",
            "break_message": "Stopped",
        }
        self.icon = "icons/icon.icns"

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.icon))
        self.tray_icon.setVisible(True)

        self.menu = QMenu()

        self.start_stop_action = QAction(self.config["start"], self)
        self.start_stop_action.triggered.connect(self.start_stop_listener)
        self.menu.addAction(self.start_stop_action)

        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.settings_listener)
        self.menu.addAction(self.settings_action)

        self.quit_action = QAction(self.config["quit"], self)
        self.quit_action.triggered.connect(self.quit_listener)
        self.menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(self.menu)

        # Your initialization code
        self.strobe_speed = 1
        self.strobe_fast_speed = 0.5
        self.ps = None
        self.settings = None
        self._set_environment()
        self.message_queue = None
        self.process_status = None
        self.icon_thread = None
        self.stop_event = multiprocessing.Event()
        clean_up_files()
        atexit.register(self.cleanup)
        logger.info("Ready!")

    def settings_listener(self):
        """Opens the settings pop-up menu."""
        if self.settings is None:
            self.settings = settings_menu.SettingsDialog()
            self.settings.finished.connect(self.on_settings_closed)
            self.settings.show()
        else:
            if not self.settings.isVisible():
                self.settings.show()

    def on_settings_closed(self):
        self.settings = None

    def _set_environment(self):
        """Sets the environment for the Jarvis process."""
        logger.info("Setting environment")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        lib_dir = os.path.join(current_dir, '..', 'Frameworks')
        numpy_dir = os.path.join(current_dir, 'Resources', 'lib', 'python3.10', 'numpy', '.dylibs')

        if 'DYLD_LIBRARY_PATH' in os.environ:
            os.environ['DYLD_LIBRARY_PATH'] = f"{lib_dir}:{numpy_dir}:{os.environ['DYLD_LIBRARY_PATH']}"
        else:
            os.environ['DYLD_LIBRARY_PATH'] = f"{lib_dir}:{numpy_dir}"

    def flash_icon(self):
        while self.message_queue is not None:
            if not self.message_queue.empty():
                self.process_status = self.message_queue.get()

            if self.process_status == "standby":
                if self.icon == "icons/icon.icns":
                    self.icon = "icons/listening.icns"  # Change to the second icon
                else:
                    self.icon = "icons/icon.icns"  # Change back to the first icon
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_speed)
            elif self.process_status == "listening":
                self.icon = "icons/listening.icns"  # Change back to the first icon
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_speed)
            elif self.process_status == "processing":
                if self.icon == "icons/processing_middle.icns":
                    self.icon = "icons/processing_small.icns"  # Change to the second icon
                else:
                    self.icon = "icons/processing_middle.icns"  # Change back to the first icon
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_speed)
            elif self.process_status == "goodbye":
                self.icon = "icons/icon.icns"
                self.tray_icon.setIcon(QIcon(self.icon))
                break
            else:
                self.tray_icon.setIcon(QIcon(self.icon))
                time.sleep(self.strobe_fast_speed)
        self.icon = "icons/icon.icns"
        self.tray_icon.setIcon(QIcon(self.icon))
        logger.info("Exiting icon thread")

    def start_stop_listener(self):
        """Starts or continues the listening process."""
        if self.start_stop_action.text() == self.config["start"]:
            if self.ps is None or not self.ps.is_alive():
                logger.info("Starting listener")
                logger.info("Booting process...")
                self.message_queue = multiprocessing.Queue()
                self.icon_thread = threading.Thread(target=self.flash_icon)
                self.icon_thread.daemon = True
                self.icon_thread.start()
                self.ps = multiprocessing.Process(target=jarvis_process,
                                                  args=([self.stop_event, self.message_queue]))
                self.ps.start()
            self.start_stop_action.setText(self.config["stop"])
        else:
            self._safe_kill()
            self.start_stop_action.setText(self.config["start"])

    def quit_listener(self):
        """Quits the application."""
        logger.info("Trying to quit application")
        self.cleanup()
        logger.info("Goodbye")
        self.quit()

    def _safe_kill(self):
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
            self.message_queue = None
            self.process_status = None

    def cleanup(self):
        """Cleans up resources."""
        self._safe_kill()
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
