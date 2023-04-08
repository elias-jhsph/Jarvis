import json
import os
import shutil
import re
import subprocess
import sys
import platform
import logging
from setuptools import setup, find_packages

# Set up a logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    handlers=[logging.FileHandler("setup.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Modify connections
PUBLIC = False

if PUBLIC:
    with open("connections_INTERNAL.py", "r") as f:
        code = f.read()
    with open("connections.py", "w") as f:
        f.write(re.sub("#####REMOVE#####[\s\S]+?#####REMOVE#####","",code))
    with open("connections.py", "w") as f:
        json.dump({"history": [], "reduced_history": [], "keywords": {}, "long_term_memory": ""}, f)
    shutil.rmtree("database", ignore_errors=True)
    os.mkdir("database")
else:
    import EXCLUDE
    with open("connections_INTERNAL.py", "r") as f:
        code = f.read()
    with open("connections.py", "w") as f:
        f.write(code)
    if not os.path.exists("database"):
        os.mkdir("database")

sys.setrecursionlimit(2000)

# Mapping of package names to import names or 'SKIP' if they should not be included
PACKAGE_NAME_MAPPING = {
    'google-api-core': 'SKIP',
    'google-auth': 'SKIP',
    'google-cloud-texttospeech': 'SKIP',
    'googleapis-common-protos': 'SKIP',
    'google-auth-httplib2': 'SKIP',
    'protobuf': 'SKIP',
    'proto-plus': 'proto',
    'pyobjc-core': 'objc',
    'pyobjc-framework-cocoa': 'Cocoa',
    'speechrecognition': 'speech_recognition',
    'six': 'six',
    'soundfile': 'soundfile',
    'sounddevice': 'sounddevice',
    'scikit-learn': 'sklearn',
    'threadpoolctl': 'SKIP',
    'ffmpeg-python': 'ffmpeg',
    'openai-whisper': 'whisper',
    'typing-extensions': 'typing_extensions',
    'beautifulsoup4': 'bs4',
    'google-api-python-client': 'googleapiclient',
    'jaraco.classes': 'SKIP',
    'pyqt6': 'PyQt6',
    'pyqt6-qt6': 'SKIP',
    'pyqt6-sip': 'SKIP',
    'pycryptodomex': 'Cryptodome',
    'pyyaml': 'yaml',
    'googlesearch-python': 'googlesearch',
}
ADDED_PACKAGES = ['en_core_web_sm']
INJECTED_PACKAGES = ['tiktoken_ext.openai_public']


def parse_installed_packages(file):
    """
    Parse the installed packages from a given file.

    :param file: The file containing the installed packages.
    :return: A list of package names.
    """
    with open(file, 'r') as f:
        return [line.strip() for line in f.readlines()]


def get_dependency_tree(packages):
    """
    Get the dependency tree for the given packages.

    :param packages: A list of package names.
    :return: The dependency tree as a JSON object.
    """
    command = ['pipdeptree', '--json', '--packages', ",".join(packages)]
    output = subprocess.run(command, capture_output=True)
    return json.loads(output.stdout)


def extract_import_names(dependency_tree):
    """
    Extract import names from a given dependency tree.

    :param dependency_tree: The dependency tree as a JSON object.
    :return: A sorted list of import names.
    """
    import_names = set()
    for entry in dependency_tree:
        import_names.add(entry['package']['key'])
        for dep in entry['dependencies']:
            import_names.add(dep['key'])
    return sorted(import_names)


def find_packages_improved():
    """
    Find packages to be included in the application bundle.

    :return: A list of packages to be included.
    """
    packages = extract_import_names(get_dependency_tree(parse_installed_packages('requirements.txt')))+ADDED_PACKAGES
    found_packages = find_packages("venv/lib/python3.10/site-packages")
    output = []
    for package in packages:
        if package not in found_packages:
            if package in PACKAGE_NAME_MAPPING:
                if PACKAGE_NAME_MAPPING[package] != "SKIP":
                    output.append(PACKAGE_NAME_MAPPING[package])
            else:
                recover = re.sub("-","_",package)
                if recover in found_packages:
                    output.append(recover)
                else:
                    raise Exception("Could not find package in venv: " + package + " (even when using " + recover + ")")
        else:
            output.append(package)
    logger.info("Packages to be included: %s", output)
    return output


sound_c_path = 'venv/lib/python3.10/site-packages/_soundfile_data/libsndfile_x86_64.dylib'
if platform.machine() == "arm64":
    sound_c_path = 'venv/lib/python3.10/site-packages/_soundfile_data/libsndfile_arm64.dylib'


APP = ['jarvis.py']

DATA_FILES = [
    'Jarvis_en_linux_v2_1_0.ppn', 'Jarvis_en_mac_v2_1_0.ppn', 'config_data.json', 'jarvis_process.py',
    'gpt_interface.py', 'text_speech.py', 'connections.py', 'logger_config.py', 'requirements.txt',
    'audio_listener.py', 'audio_player.py', 'icon.icns', 'processor.py', 'internet_helper.py',
    'assistant_history.py', 'logger_config.py', 'settings_menu.py', 'streaming_response_audio.py',
    ("audio_files", ['audio_files/beeps.wav', 'audio_files/booting.wav', 'audio_files/go_on.wav',
                     'audio_files/hmm.wav', 'audio_files/listening.wav', 'audio_files/major_error.wav',
                     'audio_files/mic_error.wav', 'audio_files/minor_error.wav',
                     'audio_files/ready_in.wav', 'audio_files/standard_response.wav', 'audio_files/thinking.wav',
                     'audio_files/tone_one.wav', 'audio_files/tone_two.wav', 'audio_files/yes.wav',
                     "audio_files/searching.wav", 'audio_files/connection_error.wav'
                     ]),
    ("free_audio_files", ['free_audio_files/beeps.wav', 'free_audio_files/booting.wav', 'free_audio_files/go_on.wav',
                          'free_audio_files/hmm.wav', 'free_audio_files/listening.wav', 'audio_files/major_error.wav',
                          'free_audio_files/mic_error.wav', 'free_audio_files/minor_error.wav',
                          'free_audio_files/ready_in.wav', 'free_audio_files/standard_response.wav',
                          'audio_files/thinking.wav', 'free_audio_files/tone_one.wav', 'free_audio_files/tone_two.wav',
                          'audio_files/yes.wav', "free_audio_files/searching.wav",
                          'free_audio_files/connection_error.wav'
                          ]),
    ("icons", ['icons/icon.icns', 'icons/listening.icns', 'icons/processing_middle.icns',
               'icons/processing_small.icns']),
    ("database", []),
    ('../Frameworks', [sound_c_path])
    ]

if PUBLIC:
    DATA_FILES = DATA_FILES[3:]

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleShortVersionString': '0.2.0',
        'LSUIElement': True,
        'NSMicrophoneUsageDescription': 'This app requires access to the microphone to respond to voice commands.',
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True
        },
    },
    'packages': find_packages_improved(),
    'includes': [
        'google.api_core',
        'google.auth',
        'google.cloud',
        'google.cloud.texttospeech',
        'google.protobuf',
        'google.proto',
        'google_auth_httplib2',
        'tiktoken_ext.openai_public'
    ]
}

setup(
    app=APP,
    name='Jarvis',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=['tiktoken']
)
