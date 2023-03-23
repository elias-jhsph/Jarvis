import os
import sys
import signal
import time
import subprocess
import rumps
import jarvis_process
import logger_config

logger = logger_config.get_logger()


class JarvisApp:
    """Main class for the Jarvis application."""

    def __init__(self):
        self.config = {
            "app_name": "Jarvis",
            "start": "Start Listening",
            "pause": "Pause Listening",
            "continue": "Continue Listening",
            "stop": "Stop Listening",
            "quit": "Quit",
            "break_message": "Stopped",
        }
        self.app = rumps.App(self.config["app_name"], "🌐", quit_button=None)
        self._set_up_menu()
        self.start_pause_button = rumps.MenuItem(title=self.config["start"], callback=self.start_listener)
        self.stop_button = rumps.MenuItem(title=self.config["stop"], callback=self.stop_listener)
        self.quit_button = rumps.MenuItem(title=self.config["quit"], callback=self.quit_listener)
        self.settings_button = rumps.MenuItem(title='Settings', callback=self.settings_listener)
        self.app.menu = [
            self.start_pause_button,
            self.stop_button,
            self.settings_button,
            self.quit_button
        ]
        self.ps = None
        self.jarvis_process_path = None
        self._set_environment()
        logger.info("Testing microphone")
        jarvis_process.test_mic()

    def settings_listener(self, sender):
        """Opens the settings pop-up menu."""
        settings_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings_menu.py')
        subprocess.Popen([sys.executable, settings_script_path])

    def _set_up_menu(self):
        """Sets up the app's menu."""
        logger.info("Setting up menu")
        self.app.title = ""

    def _set_environment(self):
        """Sets the environment for the Jarvis process."""
        logger.info("Setting environment")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.jarvis_process_path = os.path.join(current_dir, 'jarvis_process.py')
        lib_dir = os.path.join(current_dir, '..', 'Frameworks')
        numpy_dir = os.path.join(current_dir, 'Resources', 'lib', 'python3.10', 'numpy', '.dylibs')

        if 'DYLD_LIBRARY_PATH' in os.environ:
            os.environ['DYLD_LIBRARY_PATH'] = f"{lib_dir}:{numpy_dir}:{os.environ['DYLD_LIBRARY_PATH']}"
        else:
            os.environ['DYLD_LIBRARY_PATH'] = f"{lib_dir}:{numpy_dir}"

    def start_listener(self, sender):
        """Starts or continues the listening process."""
        logger.info("Starting listener")
        if sender.title.lower().startswith(("start", "continue")):
            if self.ps is None or self.ps.poll() is not None:
                logger.info("Booting process...")
                self.ps = subprocess.Popen([sys.executable, self.jarvis_process_path], env=os.environ.copy())
            else:
                if self.ps is not None and self.ps.poll() is None:
                    os.kill(self.ps.pid, signal.SIGCONT)
                else:
                    self.ps = subprocess.Popen([sys.executable, self.jarvis_process_path], env=os.environ.copy())
            sender.title = self.config["pause"]
        else:
            sender.title = self.config["continue"]
            if self.ps is not None:
                os.kill(self.ps.pid, signal.SIGSTOP)

    def stop_listener(self, sender):
        """Stops the listening process."""
        logger.info("Stopping listener")
        self._safe_kill()
        self.start_pause_button.title = self.config["start"]

    def quit_listener(self, sender):
        """Quits the application."""
        logger.info("Quitting application")
        self._safe_kill()
        rumps.quit_application()

    def run(self):
        """Runs the app."""
        logger.info("Running app")
        self.app.run()

    def _safe_kill(self):
        """Safely kills the Jarvis process."""
        logger.info("Safely killing process")
        if self.ps is not None:
            self.ps.terminate()
            time.sleep(4)
            if self.ps.poll() is None:
                logger.warning("Had to hard kill process!")
                self.ps.kill()
            self.ps = None


if __name__ == '__main__':
    logger.info("Starting app...")
    app = JarvisApp()
    app.run()
