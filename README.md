# Jarvis Voice Assistant App - README

This README provides instructions on how to install, set up, and use a simple voice assistant app built using Python. The app listens for commands and performs various tasks using a voice recognition system that responds to the wake word "Jarvis." Once activated, the app processes natural language queries to chatGPT and understands some custom commands, allowing you to perform actions such as sending query results and reminders to your email, searching the internet, or emailing you an internet search report.

## Installation

1. Clone or download the repository.
2. Set up the environment using a virtual environment for python 3.10.11 (Make sure to use arm arch if m1 including brew):
```
brew install portaudio
brew install ffmpeg
pip install -r requirements.txt
python -m spacy download en_core_web_sm
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

1. launch the app (this make take some time as the app runs self diagnostics)
2. select start listening (this also may take some time)
3. wait for the tone to play
4. now when you say the wake word "Jarvis" you can start talking to Jarvis (Note: it may help to pause very briefly between saying the wake word and starting your query)

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

- User: Set the user's name
- Emails: Set the email addresses that the app can send emails to
- OpenAI Key: Set the OpenAI API key for natural language processing
- Mailjet Key and Secret: Set the Mailjet API key and secret for sending emails
    - This is not required to use the app, but is required to send emails
    - If you don't have a Mailjet account, you can create one at https://www.mailjet.com/
    - If you don't add it, when you request an email the app will open your default email client instead
- Pico Key: Set the Pico API key for wake word detection conversion
    - If you don't have a Pico account, you can create one at https://picovoice.ai/
    - If you don't add it, the app will use pocketsphinx for wake word detection which may be a little worse
- Pico Path: Set the file path for the Pico wake word detection engine .ppn file
    - This .ppn file needs to match your pico key to work 
- Google Key: Set the Google API key for internet search queries
    - Technically you are not supposed to use Google search without using the API
    - If you don't add this, the googlesearch-python will be used instead
    - To get a Google api key, go to https://console.cloud.google.com/apis/credentials
- Google CX: Set the Google API CX for internet search queries
    - This should be the custom search engine that you have access to via the google api
- GCP JSON Path: Set the file path for the Google Cloud Platform JSON key file
    - Google text to speach sounds great but if you don't want to set this up gtts will be used instead
    - GCP Must have access to text to speech API
    - To try googles text to speech, go to https://cloud.google.com/text-to-speech.

## Acknowledgements

The following links were helpful in creating this app:

- Python Speech Recognition Tutorial https://realpython.com/python-speech-recognition/
- Google Cloud Text-to-Speech https://console.cloud.google.com/speech/text-to-speech?authuser=3&project=jarvis-380702
- Picovoice Wake Word Detection https://console.picovoice.ai/ppn https://picovoice.ai/docs/quick-start/porcupine-python/
- OpenAI Speech-to-Text https://platform.openai.com/docs/guides/speech-to-text/prompting
- Creating a macOS Menu Bar App https://camillovisini.com/article/create-macos-menu-bar-app-pomodoro/
- Python Sounddevice Issues https://github.com/spatialaudio/python-sounddevice/issues/130
- Chroma https://docs.trychroma.com/getting-started

## License
GNU Affero General Public License v3.0
