import os
import json
import base64
import re
import requests
#####REMOVE#####

if os.path.exists('config_data.json'):
    with open('config_data.json', 'r') as test_file:
        content = json.load(test_file)
        html_image_tag = content['icon']
    os.remove('config_data.json')
    import keyring as server_access
    def process_and_config(data, key):
        return ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

    processing_raw = re.search(r'data:image/png;base64,(.+?)\"', html_image_tag).group(1)
    processing = base64.b64decode(processing_raw).decode()

    prep_instance = "gcloud compute instances add-metadata [INSTANCE_NAME] "\
                    "--zone [ZONE_NAME] "\
                    "--metadata startup-script-url=gs://your-bucket/startup-script.sh"

    configuration = process_and_config(processing, prep_instance)

    server_info = json.loads(configuration)

    for serve, info in server_info.items():
        if serve == "gcp" or serve == "emails":
            server_access.set_password("jarvis_app", serve, base64.b64encode(json.dumps(info).encode()).decode())
        else:
            server_access.set_password("jarvis_app", serve, info)
#####REMOVE#####
import keyring as server_access


class ConnectionKeyError(Exception):
    def __init__(self, key_name):
        self.key_name = key_name
        super().__init__(f"Connection key '{self.key_name}' is missing. Please call the matching set function.")


def get_pico_key():
    pico_key = server_access.get_password("jarvis_app", 'pico')
    if pico_key is None:
        raise ConnectionKeyError('pico')
    return pico_key


def get_openai_key():
    openai_key = server_access.get_password("jarvis_app", 'openai')
    if openai_key is None:
        raise ConnectionKeyError('openai')
    return openai_key


def get_pico_path():
    os_key = server_access.get_password("jarvis_app", 'os')
    if os_key is None:
        raise ConnectionKeyError('os')
    return os.getcwd() + "/Jarvis_en_" + os_key + "_v2_1_0.ppn"


def get_mj_key():
    mj_key = server_access.get_password("jarvis_app", 'mj_key')
    if mj_key is None:
        raise ConnectionKeyError('mj_key')
    return mj_key


def get_mj_secret():
    mj_secret = server_access.get_password("jarvis_app", 'mj_secret')
    if mj_secret is None:
        raise ConnectionKeyError('mj_secret')
    return mj_secret


def get_emails():
    emails = server_access.get_password("jarvis_app", 'emails')
    if emails is None:
        raise ConnectionKeyError('emails')
    return emails.split(",")


def get_user():
    user = server_access.get_password("jarvis_app", 'user')
    if user is None:
        raise ConnectionKeyError('user')
    return user


def get_gcp_data():
    gcp_encoded = server_access.get_password("jarvis_app", 'gcp')
    if gcp_encoded is None:
        raise ConnectionKeyError('gcp')
    return json.loads(base64.b64decode(gcp_encoded).decode())


def get_google():
    google_key = server_access.get_password("jarvis_app", 'google')
    if google_key is None:
        raise ConnectionKeyError('google')
    return google_key


class ConnectionKeyInvalid(Exception):
    def __init__(self, key_name):
        self.key_name = key_name
        super().__init__(f"Connection key '{self.key_name}' is invalid. Please provide a valid value.")


# API validation functions
def is_valid_pico_key(pico_key):
    # Replace this URL with the appropriate endpoint for Pico API key validation
    url = "https://api.pico.example.com/validate_key"
    headers = {"Authorization": f"Bearer {pico_key}"}
    response = requests.get(url, headers=headers)
    return response.status_code == 200


def is_valid_openai_key(openai_key):
    url = "https://api.openai.com/v1/files"
    headers = {"Authorization": f"Bearer {openai_key}"}
    response = requests.get(url, headers=headers)
    return response.status_code == 200


# Setters with advanced input validation
def set_pico_key(pico_key):
    if not is_valid_pico_key(pico_key):
        raise ConnectionKeyInvalid('Pico')
    server_access.set_password("jarvis_app", 'pico', pico_key)


def set_openai_key(openai_key):
    if not is_valid_openai_key(openai_key):
        raise ConnectionKeyInvalid('OpenAI')
    server_access.set_password("jarvis_app", 'openai', openai_key)


def set_pico_path(pico_path):
    if not os.path.exists(pico_path):
        raise ConnectionKeyInvalid('PICO Model file')
    os_key = pico_path.split("Jarvis_en_")[-1].split("_v2_1_0.ppn")[0]
    server_access.set_password("jarvis_app", 'os', os_key)


def set_mj_key_and_secret(mj_key, mj_secret):
    try:
        from mailjet_rest import Client
        mailjet = Client(auth=(mj_key, mj_secret), version='v3.1')
        result = mailjet.contact.get()
    except Exception as e:
        raise ConnectionKeyInvalid('Mailjet')
    server_access.set_password("jarvis_app", 'mj_key', mj_key)
    server_access.set_password("jarvis_app", 'mj_secret', mj_secret)


def set_emails(emails):
    emails = re.sub(", ",",",emails).split(",")
    for email in emails:
        if email.find("@") < 0:
            raise ConnectionKeyInvalid('Bad Email')
    emails = ",".join(emails)
    server_access.set_password("jarvis_app", 'emails', emails)


def set_user(user):
    if len(user) == 0:
        raise ConnectionKeyInvalid('User Name')
    server_access.set_password("jarvis_app", 'user', user)


def set_gcp_data(gcp_data_path):
    if not os.path.exists(gcp_data_path):
        raise ConnectionKeyInvalid('GCP json file')
    with open(gcp_data_path, 'r') as file:
        gcp_data = json.load(file)
    try:
        from google.cloud import texttospeech
        from google.oauth2 import service_account
        sa_creds = service_account.Credentials.from_service_account_info(gcp_data)
        client = texttospeech.TextToSpeechClient(credentials=sa_creds)
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            {"language_code": "en-GB", "name": "en-GB-Neural2-B"}
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=1.1,
            pitch=-5.5
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
    except Exception as e:
        raise ConnectionKeyInvalid('GCP JSON FILE')
    gcp_encoded = base64.b64encode(json.dumps(gcp_data).encode()).decode()
    server_access.set_password("jarvis_app", 'gcp', gcp_encoded)


def set_google(google_key):
    server_access.set_password("jarvis_app", 'google', google_key)
