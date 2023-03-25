import json
import base64

access = None


def getter():
    global access
    return access


def setter(in_str):
    global access
    access = json.loads(base64.b64decode(in_str).decode())
