# Jarvis Voice Assistant App - README

This README provides instructions on how to install, set up, and use a simple voice assistant app built using Python. The app listens for commands and performs various tasks using a voice recognition system that responds to the wake word "Jarvis." Once activated, the app processes natural language queries to chatGPT and understands some custom commands, allowing you to perform actions such as sending query results and reminders to your email, searching the internet, or emailing you an internet search report.

## Installation

1. Clone or download the repository.
2. Set up the environment using a virtual environment:
```
brew install portaudio
pip install -r requirements.txt
```
3. Package the app:
   (Make sure to set PUBLIC to True in setup because the keys are not bundled in this app)
```
python setup.py py2app
dmgbuild -s settings.py -D app=dist/Jarvis.app "Jarvis" dist/jarvis_installer.dmg
```
4. Run the app. (Installer is now in the dist folder)
5. Get all the api keys you need (links at the bottom will help)
   (If you didn't get a file with api keys in it, you may want to run the settings_menu.py file on its own to add them to your keychain before trying to run the app)

   
## Usage

The app automatically listens for the wake word "Jarvis." Once activated, you can use the following voice commands to perform various actions:

- "Email me the following internet search"
- "Send me the following internet search"
- "Email me an internet search for the following"
- "Email me the following"

- "Search the internet for the following"
- "Internet search me the following"
- "Internet search for the following"
- "Search the following"

- "Email me the following reminder"

In addition to these specific voice commands, you can also speak more generally, and the app will try to interpret your request. You don't need to use any commands other than the wake word and speaking - the app listens and responds automatically.

## Settings Menu

The app includes a settings menu that can be accessed by clicking on the "Settings" menu item. The settings menu allows you to add the following settings and access keys:

- User: Set the user's name.
- Emails: Set the email addresses that the app can send emails to.
- Mailjet Key and Secret: Set the Mailjet API key and secret for sending emails (If you want to send emails).
- OpenAI Key: Set the OpenAI API key for natural language processing.
- Pico Key: Set the Pico API key for wake word detection conversion.
- Pico Path: Set the file path for the Pico wake word detection engine.
- Google Key: Set the Google API key for internet search queries.
- GCP JSON Path: Set the file path for the Google Cloud Platform JSON key file (GCP Must have access to text to speech API).

## Acknowledgements

The following links were helpful in creating this app:

- Python Speech Recognition Tutorial https://realpython.com/python-speech-recognition/
- Google Cloud Text-to-Speech https://console.cloud.google.com/speech/text-to-speech?authuser=3&project=jarvis-380702
- Picovoice Wake Word Detection https://console.picovoice.ai/ppn https://picovoice.ai/docs/quick-start/porcupine-python/
- OpenAI Speech-to-Text https://platform.openai.com/docs/guides/speech-to-text/prompting
- Creating a macOS Menu Bar App https://camillovisini.com/article/create-macos-menu-bar-app-pomodoro/
- Python Sounddevice Issues https://github.com/spatialaudio/python-sounddevice/issues/130
