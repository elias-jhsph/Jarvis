import speech_recognition as sr
import os
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

r = sr.Recognizer()
mic = sr.Microphone()
r.non_speaking_duration = 0.2
r.pause_threshold = 0.8


def listen_to_user():
    with mic as source:
        audio = r.listen(source)
    print("recognizing text...")
    text = r.recognize_whisper(audio)
    return text

