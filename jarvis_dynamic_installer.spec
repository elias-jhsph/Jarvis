# Jarvis.spec
# -*- mode: python ; coding: utf-8 -*-
import os
import platform
import re
import shutil
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Modify connections
public = False

answer = input("Do you want to create a public installer? (y/n): ")
if answer.lower() == "n":
    public = True
    print("Creating an internal installer...")
    if not os.path.exists("connections_INTERNAL.py") or not os.path.exists("EXCLUDE.py"):
        raise Exception("connections_INTERNAL.py or EXCLUDE.py does not exist. "
                        "Please create them to make an internal installer.")

# Check if we are packaging for the public or for internal use
if public:
    # Remove the internal connections file
    with open("connections_INTERNAL.py", "r") as f:
        code = f.read()
    with open("connections.py", "w") as f:
        f.write(re.sub("#####REMOVE#####[\s\S]+?#####REMOVE#####", "", code))

    # Remove the private database
    shutil.rmtree("database", ignore_errors=True)
    os.mkdir("database")
    if not os.path.exists("database"):
        os.mkdir("database")

    # Remove the private pico models
    if not os.path.exists("pico_models_PRIVATE"):
        os.mkdir("pico_models_PRIVATE")
    for file in os.listdir("pico_models"):
        shutil.copyfile(os.path.join("pico_models", file), os.path.join("pico_models_PRIVATE", file))
    shutil.rmtree("pico_models", ignore_errors=True)
    os.mkdir("pico_models")
    pico_models_list = []

    # Remove the private logs
    if not os.path.exists("logs"):
        os.mkdir("logs")
else:
    import EXCLUDE
    with open("connections_INTERNAL.py", "r") as f:
        code = f.read()
    with open("connections.py", "w") as f:
        f.write(code)
    if not os.path.exists("database"):
        os.mkdir("database")
    if not os.path.exists("logs"):
        os.mkdir("logs")
    if not os.path.exists("pico_models"):
        os.mkdir("pico_models")
    pico_models_list = []
    for file in os.listdir("pico_models"):
        pico_models_list.append(os.path.join(os.getcwd(), "pico_models", file))

if not os.path.exists("whisper_models"):
    os.mkdir("whisper_models")
whisper_models_list = []
for file in os.listdir("whisper_models"):
    whisper_models_list.append(os.path.join(os.getcwd(), "whisper_models", file))

sound_c_path = 'venv/lib/python3.10/site-packages/_soundfile_data/libsndfile_x86_64.dylib'
if platform.machine() == "arm64":
    sound_c_path = 'venv/lib/python3.10/site-packages/_soundfile_data/libsndfile_arm64.dylib'

app_name = "Jarvis"
script_name = "jarvis.py"

audio_files = [(os.path.join("audio_files", file), "audio_files") for file in ['beeps.wav', 'booting.wav', 'go_on.wav',
                     'hmm.wav', 'listening.wav', 'major_error.wav', 'mic_error.wav', 'minor_error.wav',
                     'ready_in.wav', 'standard_response.wav', 'thinking.wav', 'tone_one.wav', 'tone_two.wav',
                     'yes.wav', 'searching.wav', 'connection_error.wav']]

free_audio_files = [(os.path.join("free_audio_files", file), "free_audio_files") for file in ['beeps.wav', 'booting.wav', 'go_on.wav',
                          'hmm.wav', 'listening.wav', 'major_error.wav', 'mic_error.wav', 'minor_error.wav',
                          'ready_in.wav', 'standard_response.wav', 'thinking.wav', 'tone_one.wav', 'tone_two.wav',
                          'yes.wav', 'searching.wav', 'connection_error.wav']]

icons = [(os.path.join("icons", file), "icons") for file in ['icon.icns', 'listening.icns', 'processing_middle.icns',
               'processing_small.icns']]

pico_models_list = [(os.path.join("pico_models", file), "pico_models") for file in pico_models_list]

whisper_models_list = [(os.path.join("whisper_models", file), "whisper_models") for file in whisper_models_list]

# Collect model data
en_core_web_sm_data = collect_data_files('en_core_web_sm', include_py_files=True)
pvp_data = collect_data_files('pvporcupine')
pyside_core_datas = collect_data_files('PySide6.QtWebEngineCore', subdir='Qt/translations')
whisper_datas = collect_data_files('whisper')


# Add collected data to the datas list
manual_datas = en_core_web_sm_data + pvp_data + pyside_core_datas + whisper_datas

data_files = [
    ("config_data.json", "."),
    ("requirements.txt", "."),
    ("style.qss", "."),
    ("LICENSE", "database/"),
    ("LICENSE", "logs/"),
    ("LICENSE", "email_drafts/"),
    ("LICENSE", "audio_output/"),
] + audio_files + free_audio_files + icons + pico_models_list + whisper_models_list + manual_datas

if public:
    data_files = data_files[2:]

binaries = [
    (sound_c_path, "Frameworks/"),
]

a = Analysis(
    ["jarvis.py", "audio_player.py", "internet_helper.py", "logger_config.py",
     "streaming_response_audio.py", "animation.py", "connections.py", "processor.py",
     "text_speech.py", "assistant_history.py", "jarvis_interrupter.py", "settings.py",
     "viewer_window.py", "audio_listener.py", "gpt_interface.py", "jarvis_process.py", "settings_menu.py"],
    pathex=[],
    binaries=binaries,
    datas=data_files,
    hiddenimports=["tqdm"],
    hookspath=[],
    hooksconfig=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Jarvis',
        debug=True,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Jarvis',
    debug=True,
)
app = BUNDLE(
    coll,
    name='Jarvis.app',
    icon='icons/icon.icns',
    bundle_identifier=None,
    info_plist={
        'CFBundleShortVersionString': '0.2.0',
        'LSUIElement': True,
        'NSMicrophoneUsageDescription': 'This app requires access to the microphone to respond to voice commands.',
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True
        },
    },
)

if public:
    for file in os.listdir("pico_models_PRIVATE"):
        shutil.copyfile(os.path.join("pico_models_PRIVATE", file), os.path.join("pico_models", file))
