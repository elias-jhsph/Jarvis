import json
import subprocess
import sys
import logging
from setuptools import setup, find_packages

# Set up a logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    handlers=[logging.FileHandler("setup.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)


sys.setrecursionlimit(2000)

# Mapping of package names to import names or 'SKIP' if they should not be included
PACKAGE_NAME_MAPPING = {
    'google-api-core': 'SKIP',
    'google-auth': 'SKIP',
    'google-cloud-texttospeech': 'SKIP',
    'googleapis-common-protos': 'SKIP',
    'protobuf': 'SKIP',
    'async-timeout': 'async_timeout',
    'charset-normalizer': 'charset_normalizer',
    'proto-plus': 'proto',
    'pyasn1-modules': 'pyasn1_modules',
    'pyobjc-core': 'objc',
    'pyobjc-framework-cocoa': 'Cocoa',
    'speechrecognition': 'speech_recognition',
    'six': 'six',
    'soundfile': 'soundfile',
    'ffmpeg-python': 'ffmpeg',
    'more-itertools': 'more_itertools',
    'openai-whisper': 'whisper',
    'typing-extensions': 'typing_extensions'
}


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
    packages = extract_import_names(get_dependency_tree(parse_installed_packages('requirements.txt')))
    found_packages = find_packages("venv/lib/python3.10/site-packages")
    output = []
    for package in packages:
        if package not in found_packages:
            if package in PACKAGE_NAME_MAPPING:
                if PACKAGE_NAME_MAPPING[package] != "SKIP":
                    output.append(PACKAGE_NAME_MAPPING[package])
            else:
                raise Exception("Could not find package in venv: " + package)
        else:
            output.append(package)
    logger.info("Packages to be included: %s", output)
    return output


APP = ['jarvis.py']

DATA_FILES = [
    'Jarvis_en_linux_v2_1_0.ppn', 'jarvis_process.py', 'Jarvis_en_mac_v2_1_0.ppn', 'gpt_interface.py',
    'keys.json', 'text_speech.py', 'history.json', 'keys.py', 'logger_config.py', 'requirements.txt',
    'jarvis-380702-0f72cf5dc63b.json', 'audio_listener.py', 'setup.py', 'icon.icns', 'processor.py',
    'assistant_history.py', 'logger_config.py',
    ("audio_files", ['audio_files/beeps.wav', 'audio_files/booting.wav', 'audio_files/go_on.wav',
                     'audio_files/hmm.wav', 'audio_files/listening.wav', 'audio_files/major_error.wav',
                     'audio_files/mic_error.wav', 'audio_files/minor_error.wav', 'audio_files/processing.wav',
                     'audio_files/ready_in.wav', 'audio_files/standard_response.wav', 'audio_files/thinking.wav',
                     'audio_files/tone_one.wav', 'audio_files/tone_two.wav', 'audio_files/yes.wav']),
    ('../Frameworks', ['venv/lib/python3.10/site-packages/_soundfile_data/libsndfile_x86_64.dylib'])
    ]

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleShortVersionString': '0.2.0',
        'LSUIElement': True,
        'NSMicrophoneUsageDescription': 'This app requires access to the microphone to respond to voice commands.',
    },
    'packages': find_packages_improved(),
    'includes': [
        'google.api_core',
        'google.auth',
        'google.cloud',
        'google.cloud.texttospeech',
        'google.protobuf',
        'google.proto',
    ]
}

setup(
    app=APP,
    name='Jarvis',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=['rumps']
)
