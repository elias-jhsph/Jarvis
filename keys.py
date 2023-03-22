import json
import os

with open("keys.json") as f:
    key_data = json.load(f)


def get_pico_key():
    return key_data['pico']


def get_openai_key():
    return key_data['openai']


def get_pico_path():
    return os.getcwd() + "/Jarvis_en_"+key_data['os']+"_v2_1_0.ppn"


def get_mj_key():
    return key_data['mj_key']


def get_mj_secret():
    return key_data['mj_secret']


def get_emails():
    return key_data['emails']


def get_user():
    return key_data['user']


def get_gcp_path():
    return os.getcwd() + "/" + key_data['gcp']

