import os
import time
import threading
import multiprocessing
import rumps
import connections
from jarvis_process import jarvis_process
import settings_menu
from concurrent.futures import ThreadPoolExecutor
import logger_config

logger = logger_config.get_logger()
executor = ThreadPoolExecutor(max_workers=1)


class JarvisApp(rumps.App):
    def __init__(self):
        rumps.App.__init__(self, "Jarvis")
        self.config = {
            "app_name": "Jarvis",
            "start": "Start Listening",
            "stop": "Stop Listening",
            "quit": "Quit",
            "break_message": "Stopped",
        }
        self.quit_button = None
        self.icon = "icons/icon.icns"
        self._set_up_menu()
        self.start_stop_button = rumps.MenuItem(title=self.config["start"], callback=self.start_stop_listener)
        self.quiting_button = rumps.MenuItem(title=self.config["quit"], callback=self.quit_listener)
        self.settings_button = rumps.MenuItem(title='Settings', callback=self.settings_listener)
        self.menu = [
            self.start_stop_button,
            self.settings_button,
            self.quiting_button
        ]
        self.ps = None
        self.settings = None
        self._set_environment()
        self.message_queue = None
        self.process_status = None
        self.icon_thread = None
        self.stop_event = multiprocessing.Event()

    def flash_icon(self):
        while self.message_queue is not None:
            if not self.message_queue.empty():
                self.process_status = self.message_queue.get()

            if self.process_status == "standby":
                if self.icon == "icons/icon.icns":
                    self.icon = "icons/listening.icns"  # Change to the second icon
                else:
                    self.icon = "icons/icon.icns"  # Change back to the first icon
                time.sleep(1.5)
            elif self.process_status == "listening":
                self.icon = "icons/listening.icns"  # Change back to the first icon
                time.sleep(1.5)
            elif self.process_status == "processing":
                if self.icon == "icons/processing_middle.icns":
                    self.icon = "icons/processing_small.icns"  # Change to the second icon
                else:
                    self.icon = "icons/processing_middle.icns"  # Change back to the first icon
                time.sleep(1.5)
            else:
                time.sleep(1)
        logger.info("Exiting icon thread")


    def settings_listener(self, sender):
        """Opens the settings pop-up menu."""
        if self.settings is None:
            self.settings = executor.submit(settings_menu.main())
        else:
            if not self.settings.running():
                self.settings = executor.submit(settings_menu.main())

    def _set_up_menu(self):
        """Sets up the app's menu."""
        logger.info("Setting up menu")
        self.title = ""

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

    def start_stop_listener(self, sender):
        """Starts or continues the listening process."""
        logger.info("Starting listener")

        if sender.title == self.config["start"]:
            if self.ps is None or not self.ps.is_alive():
                logger.info("Booting process...")
                self.message_queue = multiprocessing.Queue()
                self.icon_thread = threading.Thread(target=self.flash_icon)
                self.icon_thread.daemon = True
                self.icon_thread.start()
                self.ps = multiprocessing.Process(target=jarvis_process, args=([self.stop_event, self.message_queue]))
                self.ps.start()
            sender.title = self.config["stop"]
        else:
            sender.title = self.config["start"]
            self._safe_kill()

    def quit_listener(self, sender):
        """Quits the application."""
        logger.info("Trying to quit application")
        self._safe_kill()
        logger.info("Goodbye")
        rumps.quit_application()

    def _safe_kill(self):
        if self.ps is not None and self.ps.is_alive():
            self.stop_event.set()
            self.ps.join()
            self.message_queue = None
            time.sleep(2)
            if self.ps.is_alive():
                self.ps.terminate()
                self.ps.join()
                logger.info("Hard killed!")
            else:
                logger.info("Safe killed!")

if __name__ == '__main__':
    logger.info("Starting app...")
    app = JarvisApp()
    app.run()
