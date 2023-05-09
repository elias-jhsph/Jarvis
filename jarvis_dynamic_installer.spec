# Jarvis.spec
# -*- mode: python ; coding: utf-8 -*-
import os
import platform
import re
import shutil
import subprocess
import sys
import warnings

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Modify connections
public = True

answer = input("Do you want to create a public installer? (y/n): ")
if answer.lower() == "n":
    public = False
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
    subprocess.run(["python", "EXCLUDE.py"])
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

app_name = "Jarvis"
script_name = "jarvis.py"

audio_files = [(os.path.join("audio_files", file), "audio_files") for file in os.listdir("audio_files")]
free_audio_files = [(os.path.join("free_audio_files", file), "free_audio_files") for file in os.listdir("free_audio_files")]
icons = [(os.path.join("icons", file), "icons") for file in os.listdir("icons")]
pico_models_list = [(os.path.join("pico_models", file), "pico_models") for file in pico_models_list]
whisper_models_list = [(os.path.join("whisper_models", file), "whisper_models") for file in whisper_models_list]

# Collect model data
en_core_web_sm_data = collect_data_files('en_core_web_sm', include_py_files=True)
pvp_data = collect_data_files('pvporcupine')
pyside_core_datas = collect_data_files('PySide6.QtWebEngineCore', subdir='Qt/translations')
whisper_datas = collect_data_files('whisper')

# Patch 3.9 python for mac osx
activated_patch = False
# detect if this is running on an x86 mac osx machine and temporarily remove torch hook
if platform.machine() == "x86_64" and platform.system() == "Darwin" \
        and os.path.exists("venv/lib/python3.9/site-packages/"):
    warnings.warn("Detected x86_64 mac osx machine with python 3.9! Patching torch hook.")
    torch_hook_path = "venv/lib/python3.9/site-packages/_pyinstaller_hooks_contrib/hooks/stdhooks/hook-torch.py"
    ignore_path = "venv/lib/python3.9/site-packages/_pyinstaller_hooks_contrib/hooks/stdhooks/hook-ignore_torch.py"
    if os.path.exists(torch_hook_path):
        activated_patch = True
        os.rename(torch_hook_path, ignore_path)
    from PyInstaller.utils.hooks import collect_all
    sys.setrecursionlimit(5000)
    tmp_ret = collect_all('torch')
    torch_datas = tmp_ret[0]
    torch_binaries = tmp_ret[1]
    torch_hiddenimports = tmp_ret[2]
else:
    torch_datas = []
    torch_binaries = []
    torch_hiddenimports = []


# Add collected data to the datas list
manual_datas = en_core_web_sm_data + pvp_data + pyside_core_datas + whisper_datas + torch_datas

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

# Binaries
ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True).stdout.decode("utf-8").strip()
if ffmpeg_path == "":
    raise FileNotFoundError("ffmpeg not found! Please install ffmpeg and try again.")
ffmpeg_binary = [(ffmpeg_path, 'ffmpeg')]
# find /usr/local -name "libportaudio.dylib*"
portaudio_path = subprocess.run(["find", "/usr/local", "-name",
                                 "libportaudio.dylib*"], capture_output=True).stdout.decode("utf-8").strip()
portaudio_path = portaudio_path.split("\n")[0]
if portaudio_path == "":
    raise FileNotFoundError("portaudio not found! Please install portaudio and try again.")
portaudio_binary = [(portaudio_path, 'portaudio')]

a = Analysis(
    ["jarvis.py", "audio_player.py", "internet_helper.py", "logger_config.py",
     "streaming_response_audio.py", "animation.py", "connections.py", "processor.py",
     "text_speech.py", "assistant_history.py", "jarvis_interrupter.py", "settings.py",
     "viewer_window.py", "audio_listener.py", "gpt_interface.py", "jarvis_process.py", "settings_menu.py"],
    pathex=[],
    binaries=torch_binaries + ffmpeg_binary + portaudio_binary,
    datas=data_files,
    hiddenimports=["tqdm"]+torch_hiddenimports,
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
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,
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
    strip=True,
    upx=True,
    upx_exclude=[],
    name='Jarvis',
    debug=False,
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

if activated_patch:
    os.rename(ignore_path, torch_hook_path)
