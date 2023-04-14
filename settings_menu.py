from connections import *
import sys
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, \
    QFileDialog, QInputDialog, QListWidget, QMessageBox, QListWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class SettingsDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Jarvis Settings")

        layout = QVBoxLayout()

        # Add a centered title "Settings"

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.handle_click)
        self.set_list_widget_style()
        self.setMinimumSize(350, 500)

        choices = [
            'Set User',
            'Set Emails',
            'Set OpenAI API Key',
            'Set Mailjet Key and Secret (Optional)',
            'Set Pico API Key (Optional)',
            'Set Pico Path to wake word .ppn (Optional)',
            'Set Pico Path to stop word .ppn (Optional)',
            'Set Google Key and CX (Optional)',
            'Set GCP JSON Path (Recommended)',
        ]

        for choice in choices:
            item = QListWidgetItem(choice)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(choice)

        layout.addWidget(self.list_widget)

        # Add warning label
        self.warning_label = QLabel("Must select 'Stop Listening'\nfor changes to take effect!")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        self.warning_label.setVisible(False)  # Set visibility to False by default
        layout.addWidget(self.warning_label)

        self.setLayout(layout)

        # Set initial button colors
        self.update_item_colors()


    def update_item_colors(self):
        error_setters = find_setters_that_throw_errors()

        function_mapping = {
            'Set User': 'set_user',
            'Set Emails': 'set_emails',
            'Set OpenAI API Key': 'set_openai_key',
            'Set Mailjet Key and Secret (Optional)': 'set_mj_key_and_secret',
            'Set Pico API Key (Optional)': 'set_pico_key',
            'Set Pico Path to wake word .ppn (Optional)': 'set_pico_wake_path',
            'Set Pico Path to stop word .ppn (Optional)': 'set_pico_stop_path',
            'Set Google Key and CX (Optional)': 'set_google_key_and_ck',
            'Set GCP JSON Path (Recommended)': 'set_gcp_data'
        }

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            choice = item.text()
            function_name = function_mapping[choice]

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
                background-color: gray;
                color: #ffffff;
            }
        """)

    def handle_click(self, item):
        choice = item.text()

        # Define the function name mapping
        function_mapping = {
            'Set User': set_user,
            'Set Emails': set_emails,
            'Set OpenAI API Key': set_openai_key,
            'Set Mailjet Key and Secret (Recommended)': set_mj_key_and_secret,
            'Set Pico API Key (Optional)': set_pico_key,
            'Set Pico Path to wake word .ppn (Optional)': set_pico_wake_path,
            'Set Pico Path to stop word .ppn (Optional)': set_pico_stop_path,
            'Set Google Key and CX (Optional)': set_google_key_and_ck,
            'Set GCP JSON Path (Optional)': set_gcp_data
        }

        try:
            if choice.find('Path') != -1:
                path, _ = QFileDialog.getOpenFileName()
                if path:
                    function_mapping[choice](path)
            elif choice == 'Set Mailjet Key and Secret (Recommended)':
                value_key, ok_key = QInputDialog.getText(self, "Enter your Mailjet Key:", "")
                value_secret, ok_secret = QInputDialog.getText(self, "Enter your Mailjet Secret:", "")
                if ok_key and ok_secret:
                    function_mapping[choice](value_key, value_secret)
            elif choice == 'Set Google Key and CX (Optional)':
                value_key, ok_key = QInputDialog.getText(self, "Enter your Google Key:", "")
                value_secret, ok_secret = QInputDialog.getText(self, "Enter your Google CX:", "")
                if ok_key and ok_secret:
                    function_mapping[choice](value_key, value_secret)
            else:
                input_dialog = QInputDialog(self)
                input_dialog.setInputMode(QInputDialog.InputMode.TextInput)
                input_dialog.setWindowTitle(f"Update {choice.split(' ')[1]}")
                input_dialog.setLabelText(f"Enter your {choice.split(' ')[1]} key:          ")
                input_dialog.setMinimumWidth(input_dialog.width() * 4)  # Make it twice as wide

                ok = input_dialog.exec()
                value = input_dialog.textValue()

                if ok:
                    function_mapping[choice](value)
            self.warning_label.setVisible(True)
            self.update_item_colors()
            self.list_widget.clearSelection()
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", f"The value was invalid and not updated.\nError: {str(e)}")


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setStyle("Fusion")

    # Set up the dark theme
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, Qt.GlobalColor.black)
    palette.setColor(palette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.Base, Qt.GlobalColor.black)
    palette.setColor(palette.ColorRole.AlternateBase, Qt.GlobalColor.black)
    palette.setColor(palette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
    palette.setColor(palette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.Button, Qt.GlobalColor.black)
    palette.setColor(palette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(palette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(palette.ColorRole.Highlight, Qt.GlobalColor.gray)
    palette.setColor(palette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

    dialog = SettingsDialog()
    dialog.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
