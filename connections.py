import os
import json
import base64
import re
import sys

import requests

#####REMOVE#####
config_path = "config_data.json"
if getattr(sys, 'frozen', False):
    config_path = os.path.join(sys._MEIPASS, config_path)
if os.path.exists(config_path):
    with open(config_path, 'r') as test_file:
        content = json.load(test_file)
        html_image_tag = content['icon']
    os.remove(config_path)
    import keyring as server_access


    def process_and_config(data, key):
        return ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))


    processing_raw = re.search(r'data:image/png;base64,(.+?)\"', html_image_tag).group(1)
    processing = base64.b64decode(processing_raw).decode()

    prep_instance = "gcloud compute instances add-metadata [INSTANCE_NAME] " \
                    "--zone [ZONE_NAME] " \
                    "--metadata startup-script-url=gs://your-bucket/startup-script.sh"

    configuration = process_and_config(processing, prep_instance)

    server_info = json.loads(configuration)
    if getattr(sys, 'frozen', False):
        for server_info_key in server_info:
            if server_info_key.find("_path") >= 0 or \
                    server_info_key.find("_wake") >= 0 or \
                    server_info_key.find("_stop") >= 0:
                server_info[server_info_key] = os.path.join(sys._MEIPASS, server_info[server_info_key])

    server_access.set_password("jarvis_app", "data", base64.b64encode(json.dumps(server_info).encode()).decode())

#####REMOVE#####
import keyring as server_access

# Set up the connection ring
connections_ring = {}


def get_connection_ring():
    """
    Get the connection ring from the server.

    :return: The connection ring.
    :rtype: dict
    """
    global connections_ring
    if connections_ring == {}:
        connection_data = server_access.get_password("jarvis_app", "data")
        if connection_data is not None:
            connections_ring = json.loads(base64.b64decode(connection_data).decode())
        else:
            connections_ring = {"user": "User"}
    return connections_ring


def set_connection_ring(data):
    """
    Set the connection ring on the server.

    :param data: The connection ring.
    :type data: dict
    :return: None
        """
    global connections_ring
    connections_ring = data
    return


# Update the connection ring
get_connection_ring()


def get_connection(key):
    """
    Get a connection from the connection ring.

    :param key: The key of the connection.
    :type key: str
    :return: The connection.
    :rtype: str
    """
    get_connection_ring()
    if key in connections_ring:
        return connections_ring[key]
    return None


def get_connections_zip():
    """
    Get the connection ring as a compressed string.

    :return: The connection ring as a compressed string.
    :rtype: str
    """
    global connections_ring
    get_connection_ring()
    return base64.b64encode(json.dumps(connections_ring).encode()).decode()


def set_connection(key, value):
    """
    Set a connection in the connection ring.

    :param key: The key of the connection.
    :type key: str
    :param value: The value of the connection.
    :type value: Any
    :return: None
        """
    global connections_ring
    connections_ring[key] = value
    connections_ring_ready = base64.b64encode(json.dumps(connections_ring).encode()).decode()
    server_access.set_password("jarvis_app", "data", connections_ring_ready)


class ConnectionKeyError(Exception):
    """
    Exception raised when a connection key is missing.
    """

    def __init__(self, key_name):
        """
        Initialize the exception.

        :param key_name: The name of the missing key.
        :type key_name: str
        """
        self.key_name = key_name
        super().__init__(f"Connection key '{self.key_name}' is missing. Please call the matching set function.")


def get_pico_key():
    """
    Get the pico key.

    :return: The pico key.
    :rtype: str
    """
    pico_key = get_connection('pico')
    if pico_key is None:
        raise ConnectionKeyError('pico')
    return pico_key


def get_openai_key():
    """
    Get the openai key.

    :return: The openai key.
    :rtype: str
    """
    openai_key = get_connection('openai')
    if openai_key is None:
        raise ConnectionKeyError('openai')
    return openai_key


def get_pico_wake_path():
    """
    Get the pico wake path.

    :return: The pico wake path.
    :rtype: str
    """
    path = get_connection('pico_wake')
    if path is None:
        raise ConnectionKeyError('pico_wake')
    return path


def get_pico_stop_path():
    """
    Get the pico stop path.

    :return: The pico stop path.
    :rtype: str
    """
    path = get_connection('pico_stop')
    if path is None:
        raise ConnectionKeyError('pico_stop')
    return path


def get_mj_key():
    """
    Get the mj key.

    :return: The mj key.
    :rtype: str
    """
    mj_key = get_connection('mj_key')
    if mj_key is None:
        raise ConnectionKeyError('mj_key')
    return mj_key


def get_mj_secret():
    """
    Get the mj secret.

    :return: The mj secret.
    :rtype: str
    """
    mj_secret = get_connection('mj_secret')
    if mj_secret is None:
        raise ConnectionKeyError('mj_secret')
    return mj_secret


def get_emails():
    """
    Get the emails connection.

    :return: The emails connection.
    :rtype: str
    """
    emails = get_connection('emails')
    if emails is None:
        raise ConnectionKeyError('emails')
    return emails


def get_user():
    """
    Get the user connection.

    :return: The user connection.
    :rtype: str
    """
    user = get_connection('user')
    if user is None:
        raise ConnectionKeyError('user')
    return user


def get_gcp_data():
    """
    Get the gcp data connection.

    :return: The gcp data connection.
    :rtype: str
    """
    gcp = get_connection('gcp')
    if gcp is None:
        raise ConnectionKeyError('gcp')
    return gcp


def get_google_key():
    """
    Get the google connection.

    :return: The google connection.
    :rtype: str
    """
    google_key = get_connection('google_key')
    if google_key is None:
        raise ConnectionKeyError('google_key')
    return google_key


def get_google_cx():
    """
    Get the google cx connection.

    :return: The google cx connection.
    :rtype: str
    """
    google_key = get_connection('google_cx')
    if google_key is None:
        raise ConnectionKeyError('google_cx')
    return google_key


class ConnectionKeyInvalid(Exception):
    """
    Exception raised when a connection key is invalid.
    """

    def __init__(self, key_name):
        """
        Initialize the exception.

        :param key_name: The name of the invalid key.
        :type key_name: str
        """
        self.key_name = key_name
        super().__init__(f"Connection key '{self.key_name}' is invalid. Please provide a valid value.")


# API validation functions
def is_valid_pico_key(pico_key):
    """
    Check if a pico key is valid.

    :param pico_key: The pico key to check.
    :type pico_key: str
    :return: None
    """
    import pvporcupine
    handle = pvporcupine.create(access_key=pico_key, keywords=['Jarvis'],
                                keyword_paths=[get_pico_wake_path()])
    del handle
    return


def is_valid_openai_key(openai_key):
    """
    Check if an openai key is valid.

    :param openai_key: The openai key to check.
    :type openai_key: str
    :return: True if the key is valid, False otherwise.
    :rtype: bool
    """
    url = "https://api.openai.com/v1/files"
    headers = {"Authorization": f"Bearer {openai_key}"}
    response = requests.get(url, headers=headers)
    return response.status_code == 200


# Setters with advanced input validation
def set_pico_key(pico_key):
    """
    Set the pico key.

    :param pico_key: The pico key to set.
    :type pico_key: str
    :return: None
    """
    try:
        is_valid_pico_key(pico_key)
    except Exception as e:
        raise ConnectionKeyInvalid('Pico')
    set_connection('pico', pico_key)


def set_openai_key(openai_key):
    """
    Set the openai key.

    :param openai_key: The openai key to set.
    :type openai_key: str
    :return: None
    """
    if not is_valid_openai_key(openai_key):
        raise ConnectionKeyInvalid('OpenAI')
    set_connection('openai', openai_key)


def set_pico_wake_path(pico_path):
    """
    Set the pico wake path.

    :param pico_path: The pico wake path to set.
    :type pico_path: str
    :return: None
    """
    if not os.path.exists(pico_path) or not pico_path.endswith('.ppn'):
        if getattr(sys, 'frozen', False):
            pico_path = os.path.join(sys._MEIPASS, pico_path)
            if not os.path.exists(pico_path) or not pico_path.endswith('.ppn'):
                raise ConnectionKeyInvalid('PICO Model file')
        else:
            raise ConnectionKeyInvalid('PICO Model file')
    set_connection('pico_wake', pico_path)


def set_pico_stop_path(pico_path):
    """
    Set the pico stop path.

    :param pico_path: The pico stop path to set.
    :type pico_path: str
    :return: None
    """
    if not os.path.exists(pico_path) or not pico_path.endswith('.ppn'):
        if getattr(sys, 'frozen', False):
            pico_path = os.path.join(sys._MEIPASS, pico_path)
            if not os.path.exists(pico_path) or not pico_path.endswith('.ppn'):
                raise ConnectionKeyInvalid('PICO Model file')
        else:
            raise ConnectionKeyInvalid('PICO Model file')
    set_connection('pico_stop', pico_path)


def set_mj_key_and_secret(mj_key, mj_secret):
    """
    Set the mj key and secret.

    :param mj_key: The mj key to set.
    :type mj_key: str
    :param mj_secret: The mj secret to set.
    :type mj_secret: str
    :return: None
    """
    try:
        from mailjet_rest import Client
        mailjet = Client(auth=(mj_key, mj_secret), version='v3.1')
        result = mailjet.contact.get()
    except Exception as e:
        raise ConnectionKeyInvalid('Mailjet')
    set_connection('mj_key', mj_key)
    set_connection('mj_secret', mj_secret)


def set_emails(emails):
    """
    Set the emails.

    :param emails: The emails to set.
    :type emails: str
    :return: None
    """
    emails = re.sub(", ", ",", emails).split(",")
    for email in emails:
        if email.find("@") < 0:
            raise ConnectionKeyInvalid('Bad Email')
    set_connection('emails', emails)


def set_user(user):
    """
    Set the user.

    :param user: The user to set.
    :type user: str
    :return: None
    """
    if len(user) == 0:
        raise ConnectionKeyInvalid('User Name')
    set_connection('user', user)


def set_gcp_data(gcp_data_path, data=False):
    """
    Set the gcp data.

    :param gcp_data_path: The gcp data path to set.
    :type gcp_data_path: str
    :param data: Whether the data is already loaded or not.
    :type data: bool
    :return: None
    """
    if not data:
        if not os.path.exists(gcp_data_path):
            if getattr(sys, 'frozen', False):
                gcp_data_path = os.path.join(sys._MEIPASS, gcp_data_path)
                if not os.path.exists(gcp_data_path):
                    raise ConnectionKeyInvalid('GCP json file')
            else:
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
    """
    Set the google key and cx.

    :param google_key: The google key to set.
    :type google_key: str
    :param google_cx: The google cx to set.
    :type google_cx: str
    :return: None
    """
    try:
        from googleapiclient.discovery import build
        service = build("customsearch", "v1", developerKey=google_key)
        res = service.cse().list(q='test', cx=google_cx).execute()
    except Exception as e:
        raise ConnectionKeyInvalid('Google')
    set_connection('google_key', google_key)
    set_connection('google_cx', google_cx)


def find_setters_that_throw_errors():
    """
    Find setters that throw errors.

    :return: List of setters that throw errors.
    :rtype: list
    """
    getters = [
        'get_pico_key', 'get_openai_key', 'get_pico_wake_path', 'get_pico_stop_path', 'get_mj_key',
        'get_mj_secret', 'get_emails', 'get_user', 'get_gcp_data', 'get_google_key', 'get_google_cx'
    ]

    setters = [
        'set_pico_key', 'set_openai_key', 'set_pico_wake_path', 'set_pico_stop_path',
        'set_mj_key_and_secret', 'set_emails', 'set_user', 'set_gcp_data', 'set_google_key_and_ck'
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
                    set_google_key_and_ck(get_google_key(), get_google_cx())
                except Exception as e:
                    error_setters.append(setter)

    return error_setters
