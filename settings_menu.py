from connections import *
import sys
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel,\
    QPushButton, QLineEdit, QFileDialog, QInputDialog, QListWidget, QStackedWidget
from PyQt5.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Settings")

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.handle_click)
        self.set_list_widget_style()
        self.setMinimumSize(250, 350)

        choices = [
            'Set User',
            'Set Emails',
            'Set Mailjet Key and Secret',
            'Set OpenAI Key',
            'Set Pico Key',
            'Set Pico Path',
            'Set Google Key',
            'Set GCP JSON Path',
        ]

        for choice in choices:
            self.list_widget.addItem(choice)

        layout.addWidget(self.list_widget)

        self.setLayout(layout)

    def set_list_widget_style(self):
        self.list_widget.setStyleSheet("""
            QListWidget::item {
                border: none;
                padding: 10px;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #505050;
                color: #ffffff;
            }
        """)

    def handle_click(self, item):
        choice = item.text()
        if choice in ['Set Pico Key', 'Set OpenAI Key', 'Set Google Key', 'Set Emails', 'Set User']:
            value, ok = QInputDialog.getText(self, f"Enter your {choice.split(' ')[1]} key:", "")
            if ok:
                globals()[choice.lower().replace(' ', '_').replace('-', '_')](value)
        elif choice == 'Set Pico Path' or choice == 'Set GCP JSON Path':
            path, _ = QFileDialog.getOpenFileName()
            if path:
                function_name = choice.lower().replace(' ', '_').replace('-', '_')
                globals()[function_name](path)
        elif 'Set Mailjet Key and Secret':
            value_key, ok_key = QInputDialog.getText(self, "Enter your Mailjet Key:", "")
            value_secret, ok_secret = QInputDialog.getText(self, "Enter your Mailjet Secret:", "")
            if ok_key and ok_secret:
                function_name = "set_mj_key_and_secret"
                globals()[function_name](value_key, value_secret)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set up the dark theme
    palette = app.palette()
    palette.setColor(palette.Window, Qt.black)
    palette.setColor(palette.WindowText, Qt.white)
    palette.setColor(palette.Base, Qt.black)
    palette.setColor(palette.AlternateBase, Qt.black)
    palette.setColor(palette.ToolTipBase, Qt.black)
    palette.setColor(palette.ToolTipText, Qt.white)
    palette.setColor(palette.Text, Qt.white)
    palette.setColor(palette.Button, Qt.black)
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.BrightText, Qt.red)
    palette.setColor(palette.Highlight, Qt.darkBlue)
    palette.setColor(palette.HighlightedText, Qt.black)
    app.setPalette(palette)

    dialog = SettingsDialog()
    dialog.exec_()


if __name__ == "__main__":
    main()