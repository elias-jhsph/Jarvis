from setuptools import setup

APP = ['jarvis.py']

DATA_FILES = ['Jarvis_en_linux_v2_1_0.ppn', 'go_on.wav', 'jarvis_process.py', 'minor_error.wav',
              'standard_response.wav', 'Jarvis_en_mac_v2_1_0.ppn', 'gpt_interface.py', 'keys.json', 'processing.wav',
              'text_speech.py', 'history.json', 'keys.py', 'requirements.txt', 'thinking.wav',
              'jarvis-380702-0f72cf5dc63b.json', 'listening.wav', 'roboting.mp3', 'audio_listener.py',
              'major_error.wav', 'setup.py', 'yes.wav']

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleShortVersionString': '0.2.0',
        'LSUIElement': True,
    }

}

setup(
    app=APP,
    name='Jarvis',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'], install_requires=['rumps']
)
