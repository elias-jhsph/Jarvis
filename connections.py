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

    server_access.set_password("jarvis_app", "data", base64.b64encode(json.dumps(server_info).encode()).decode())

#####REMOVE#####

import keyring as server_access

connections_ring = {}


def get_connection_ring():
    global connections_ring
    if connections_ring == {}:
        connection_data = server_access.get_password("jarvis_app", "data")
        if connection_data is not None:
            connections_ring = json.loads(base64.b64decode(connection_data).decode())
        else:
            connections_ring = {"user": "User"}
    return connections_ring


def set_connection_ring(data):
    global connections_ring
    connections_ring = data
    return


get_connection_ring()


def get_connection(key):
    get_connection_ring()
    if key in connections_ring:
        return connections_ring[key]
    return None


def get_connections_zip():
    global connections_ring
    get_connection_ring()
    return base64.b64encode(json.dumps(connections_ring).encode()).decode()


def set_connection(key, value):
    global connections_ring
    connections_ring[key] = value
    connections_ring_ready = base64.b64encode(json.dumps(connections_ring).encode()).decode()
    server_access.set_password("jarvis_app", "data", connections_ring_ready)


class ConnectionKeyError(Exception):
    def __init__(self, key_name):
        self.key_name = key_name
        super().__init__(f"Connection key '{self.key_name}' is missing. Please call the matching set function.")


def get_pico_key():
    pico_key = get_connection('pico')
    if pico_key is None:
        raise ConnectionKeyError('pico')
    return pico_key


def get_openai_key():
    openai_key = get_connection('openai')
    if openai_key is None:
        raise ConnectionKeyError('openai')
    return openai_key


def get_pico_path():
    os_key = get_connection('os')
    if os_key is None:
        raise ConnectionKeyError('os')
    return os.getcwd() + "/Jarvis_en_" + os_key + "_v2_1_0.ppn"


def get_mj_key():
    mj_key = get_connection('mj_key')
    if mj_key is None:
        raise ConnectionKeyError('mj_key')
    return mj_key


def get_mj_secret():
    mj_secret = get_connection('mj_secret')
    if mj_secret is None:
        raise ConnectionKeyError('mj_secret')
    return mj_secret


def get_emails():
    emails = get_connection('emails')
    if emails is None:
        raise ConnectionKeyError('emails')
    return emails


def get_user():
    user = get_connection('user')
    if user is None:
        raise ConnectionKeyError('user')
    return user


def get_gcp_data():
    gcp = get_connection('gcp')
    if gcp is None:
        raise ConnectionKeyError('gcp')
    return gcp


def get_google():
    google_key = get_connection('google')
    if google_key is None:
        raise ConnectionKeyError('google')
    return google_key


def get_google_cx():
    google_key = get_connection('google_cx')
    if google_key is None:
        raise ConnectionKeyError('google_cx')
    return google_key


class ConnectionKeyInvalid(Exception):
    def __init__(self, key_name):
        self.key_name = key_name
        super().__init__(f"Connection key '{self.key_name}' is invalid. Please provide a valid value.")


# API validation functions
def is_valid_pico_key(pico_key):
    import pvporcupine
    handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                keyword_paths=[get_pico_path()])
    del handle
    return


def is_valid_openai_key(openai_key):
    url = "https://api.openai.com/v1/files"
    headers = {"Authorization": f"Bearer {openai_key}"}
    response = requests.get(url, headers=headers)
    return response.status_code == 200


# Setters with advanced input validation
def set_pico_key(pico_key):
    try:
        is_valid_pico_key(pico_key)
    except Exception as e:
        raise ConnectionKeyInvalid('Pico')
    set_connection('pico', pico_key)


def set_openai_key(openai_key):
    if not is_valid_openai_key(openai_key):
        raise ConnectionKeyInvalid('OpenAI')
    set_connection('openai', openai_key)


def set_pico_path(pico_path):
    if not os.path.exists(pico_path):
        raise ConnectionKeyInvalid('PICO Model file')
    os_key = pico_path.split("Jarvis_en_")[-1].split("_v2_1_0.ppn")[0]
    set_connection('os', os_key)


def set_mj_key_and_secret(mj_key, mj_secret):
    try:
        from mailjet_rest import Client
        mailjet = Client(auth=(mj_key, mj_secret), version='v3.1')
        result = mailjet.contact.get()
    except Exception as e:
        raise ConnectionKeyInvalid('Mailjet')
    set_connection('mj_key', mj_key)
    set_connection('mj_secret', mj_secret)


def set_emails(emails):
    emails = re.sub(", ",",",emails).split(",")
    for email in emails:
        if email.find("@") < 0:
            raise ConnectionKeyInvalid('Bad Email')
    set_connection('emails', emails)


def set_user(user):
    if len(user) == 0:
        raise ConnectionKeyInvalid('User Name')
    set_connection('user', user)


def set_gcp_data(gcp_data_path, data=False):
    if not data:
        if not os.path.exists(gcp_data_path):
            raise ConnectionKeyInvalid('GCP json file')
        with open(gcp_data_path, 'r') as file:
            gcp_data = json.load(file)
    else:
        gcp_data = gcp_data_path
    try:
        from google.cloud import texttospeech
        from google.oauth2 import service_account
        sa_creds = service_account.Credentials.from_service_account_info(gcp_data)
        client = texttospeech.TextToSpeechClient(credentials=sa_creds)
        synthesis_input = texttospeech.SynthesisInput(text="test")
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
    set_connection('gcp', gcp_data)


def set_google_key_and_ck(google_key, google_cx):
    try:
        from googleapiclient.discovery import build
        service = build("customsearch", "v1", developerKey=google_key)
        res = service.cse().list(q='test', cx=google_cx).execute()
    except Exception as e:
        raise ConnectionKeyInvalid('Google')
    set_connection('google', google_key)
    set_connection('google_cx', google_cx)


def find_setters_that_throw_errors():
    getters = [
        'get_pico_key', 'get_openai_key', 'get_pico_path', 'get_mj_key', 'get_mj_secret',
        'get_emails', 'get_user', 'get_gcp_data', 'get_google', 'get_google_cx'
    ]

    setters = [
        'set_pico_key', 'set_openai_key', 'set_pico_path', 'set_mj_key_and_secret', 'set_emails',
        'set_user', 'set_gcp_data', 'set_google_key_and_ck'
    ]

    error_setters = []

    for setter in setters:
        getter_name = setter.replace("set_", "get_")
        if getter_name in getters:
            try:
                value = eval(getter_name + "()")
                if getter_name == "get_emails":
                    value = ','.join(value)
                    eval(setter + f"({value!r})")
                elif getter_name == "get_gcp_data":
                    eval(setter + f"({value}, data=True)")
                else:
                    eval(setter + f"({value!r})")
            except Exception as e:
                error_setters.append(setter)
        else:
            if setter == "set_mj_key_and_secret":
                try:
                    set_mj_key_and_secret(get_mj_key(), get_mj_secret())
                except Exception as e:
                    error_setters.append(setter)
            else:
                try:
                    set_google_key_and_ck(get_google(), get_google_cx())
                except Exception as e:
                    error_setters.append(setter)

    return error_setters

