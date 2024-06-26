# Jarvis Voice Assistant App - README

This README provides instructions on how to install, set up, and use a simple voice assistant app built using Python. The app listens for commands and performs various tasks using a voice recognition system that responds to the wake word "Jarvis." Once activated, the app processes natural language queries to chatGPT and understands some custom commands, allowing you to perform actions such as sending query results and reminders to your email, searching the internet, or emailing you an internet search report.

## Installation
If you want to download a .dmg file without any API keys in it you can download them from this Drive folder -> https://drive.google.com/drive/folders/1gBap6phnbj_GMxM7oLueI_UmxAVjEsb-?usp=sharing
1. Clone or download the repository.
2. Set up the environment using a virtual environment for python (Note - more than the following options may work):
- If you are on an M1 Mac I have tested this code with python 3.10.11 and macOS 13.2.1 (Make sure to use the arm arch for brew)
- If you are on an Intel Mac I have tested this code with python 3.9.0 and macOS 13.3.1 (The hook-torch.py file is temporarily removed inorder to patch an issue in pyinstaller)
```
brew install portaudio
brew install ffmpeg
brew install upx
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```
If Pyaudio doesn't install try
```
 sudo pip install --global-option='build_ext' --global-option='-I/opt/local/include' --global-option='-L/opt/local/lib' pyaudio
```
3. To package the app:
   (Make sure to select 'y' for public because the api keys are not in this repo)
```
pyinstaller jarvis_dynamic_installer.spec
dmgbuild -s settings.py -D app=dist/Jarvis.app "Jarvis" dist/jarvis_installer.dmg
```
4. Run the app. (Installer is now in the dist folder)
5. Get all the api keys you need (links at the bottom will help)
(You may want to run the settings_menu.py file on its own to add them to your keychain before trying to run the app)

   
## Usage

1. launch the app (this make take some time as the app runs self diagnostics)
2. select start listening (this also may take some time)
3. wait for the tone to play
4. now when you say the wake word "Jarvis" you can start talking to Jarvis (Note: it may help to pause very briefly between saying the wake word and starting your query)
5. At anytime if you want to view the chat select "Live Chat / History" from the menu bar
6. At anytime if you want Jarvis to stop talking select "Jarvis, Stop." from the menu bar or loudly say "Jarvis, Stop."
7. At anytime if you want Jarvis to stop listening for the wake word select "Stop Listening" from the menu bar

The app automatically listens for the wake word "Jarvis." 
Once activated, if you include the following command words towards the beginning of your query jarvis will do an internet search:
- "internet", "google", "search", "lookup", "look up", "website", "web"

If you say the word "last" and include the following command words towards the beginning of your query jarvis will tell you the last thing it told you:
- "response", "thing", "question", "message", "answer", "reply", "result", "output"

If you combine either of those specified above with the word email, Jarvis will email you the result of the query or create an email draft and open it in your default email app.

If you include the word "reminder" in your query, Jarvis will send you an email right away with what you said as the reminder or create an email draft and open it in your default email app.

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
- Pico Path to wake word .ppn: Set the file path for the Pico wake word detection engine .ppn file
    - This .ppn file needs to match your pico key to work 
- Pico Path to stop word .ppn: Set the file path for the Pico stop word detection engine .ppn file
    - This .ppn file needs to match your pico key to work 
- Google Key and CX: Set the Google API key for internet search queries
    - Technically you are not supposed to use Google search without using the API
    - If you don't add this, the googlesearch-python will be used instead
    - To get a Google api key, go to https://console.cloud.google.com/apis/credentials
    - The CX should be the custom search engine that you have access to via the Google API
- GCP JSON Path: Set the file path for the Google Cloud Platform JSON key file
    - Google text to speach sounds great but if you don't want to set this up gtts will be used instead...
    - BUT if you have a mac then the 'say' command will be used instead because it sounds better than gtts and the voice will be Tom if you have it, then if you don't have Tom it will be Samantha, and if you don't have either it will be the default voice that isn't a siri voice
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
