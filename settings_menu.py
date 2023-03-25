from connections import *
import sys
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, \
    QFileDialog, QInputDialog, QListWidget, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class SettingsDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Settings")

        layout = QVBoxLayout()

        # Add a centered title "Settings"
        title = QLabel("Settings")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.handle_click)
        self.set_list_widget_style()
        self.setMinimumSize(250, 480)

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

        # Add warning label
        self.warning_label = QLabel("Must select 'Stop Listening'\nfor changes to take effect!")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        self.warning_label.setVisible(False)  # Set visibility to False by default
        layout.addWidget(self.warning_label)

        self.setLayout(layout)

        # Set initial button colors
        self.update_item_colors()

    def update_item_colors(self):
        error_setters = find_setters_that_throw_errors()

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            choice = item.text()
            function_name = choice.lower().replace(' ', '_').replace('-', '_').replace('mailjet', 'mj')
            if function_name == "set_google_key":
                function_name = "set_google"
            if function_name == "set_gcp_json_path":
                function_name = "set_gcp_data"
            if function_name in error_setters:
                button_color = "#8b0000"  # red
            else:
                button_color = "#2e8b57"  # green

            item.setForeground(QColor(button_color))

    def set_list_widget_style(self):
        self.list_widget.setStyleSheet("""
            QListWidget::item {
                border: none;
                padding: 10px;
                margin: 5px;  /* Add margin to increase spacing between buttons */
            }
            QListWidget::item:hover {
                background-color: rgba(60, 60, 60, 180);  /* Translucent gray on mouse hover */
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #000000;
                color: #ffffff;
            }
        """)

    def handle_click(self, item):
        choice = item.text()
        try:
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
            self.warning_label.setVisible(True)
            self.update_item_colors()
            self.list_widget.clearSelection()
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", f"The value was invalid and not updated.\nError: {str(e)}")


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