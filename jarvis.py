import rumps
import subprocess
import os
import signal


class JarvisApp(object):
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
        self.set_up_menu()
        self.start_pause_button = rumps.MenuItem(title=self.config["start"], callback=self.start_listener)
        self.stop_button = rumps.MenuItem(title=self.config["stop"], callback=self.stop_listener)
        self.quit_button = rumps.MenuItem(title=self.config["quit"], callback=self.quit_listener)
        self.app.menu = [self.start_pause_button, self.stop_button, self.quit_button]
        self.ps = None
        try:
            from jarvis_process import booting_test, jarvis_process
            booting_test()
        except Exception as e:
            rumps.notification("Error", "Failed to boot!", str(e), sound=True)

    def set_up_menu(self):
        self.app.title = ""

    def start_listener(self, sender):
        if sender.title.lower().startswith(("start", "continue")):
            if self.ps is None or self.ps.poll() is not None:
                print("booting process...")
                self.ps = subprocess.Popen(['python3', 'jarvis_process.py'])
            else:
                if self.ps is not None and self.ps.poll() is None:
                    os.kill(self.ps.pid, signal.SIGCONT)
                else:
                    self.ps = subprocess.Popen(['python3', 'jarvis_process.py'])
            sender.title = self.config["pause"]
        else:
            sender.title = self.config["continue"]
            if self.ps is not None:
                os.kill(self.ps.pid, signal.SIGSTOP)

    def stop_listener(self, sender):
        if self.ps is not None:
            self.ps.kill()
            self.ps = None
        self.start_pause_button.title = self.config["start"]

    def quit_listener(self, sender):
        if self.ps is not None:
            self.ps.kill()
            self.ps = None
        rumps.quit_application()

    def run(self):
        self.app.run()


if __name__ == '__main__':
    app = JarvisApp()
    app.run()
