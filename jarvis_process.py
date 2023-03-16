import ctypes.util
import functools
import os

# print("Attempting to import pyaudio using patched `ctypes.util.find_library`...")
# _find_library_original = ctypes.util.find_library
# print("CWD:", os.getcwd())
#
#
# @functools.wraps(_find_library_original)
# def _find_library_patched(name):
#     if name == "portaudio":
#         return "libportaudio.so.2"
#     else:
#         return _find_library_original(name)
#
#
# ctypes.util.find_library = _find_library_patched

import pvporcupine
import pyaudio
import pygame


# print("pyaudio import successful!")
# print("Restoring original `ctypes.util.find_library`...")
# ctypes.util.find_library = _find_library_original
# del _find_library_patched
# print("Original `ctypes.util.find_library` restored.")

import struct
import time
import datetime
import random

from keys import get_pico_key, get_pico_path
from audio_listener import listen_to_user
from gpt_interface import generate_response
from text_speech import text_to_speech

last_time = datetime.datetime.now() - datetime.timedelta(minutes=5)


def booting_test():

    def wait(s):
        while s.get_busy():
            pygame.time.wait(100)

    pygame.mixer.init(channels=1, buffer=8196)
    sound = pygame.mixer.music
    sound.load('booting.wav')
    sound.play()
    wait(sound)

    handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                keyword_paths=[get_pico_path()])

    pa = pyaudio.PyAudio()
    info = pa.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    inputs = 0
    for i in range(0, numdevices):
        if pa.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels') > 0:
            inputs += 1
            print("Input Device id ", i, " - ", pa.get_device_info_by_host_api_device_index(0, i).get('name'))
    if inputs == 0:
        raise Exception("No input (microphone) devices found")
    try:
        def get_next_audio_frame():
            pcm = audio_stream.read(handle.frame_length)
            pcm = struct.unpack_from("h" * handle.frame_length, pcm)
            return pcm

        audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                               frames_per_buffer=handle.frame_length, input_device_index=None)
        handle.process(get_next_audio_frame())
        audio_stream.stop_stream()
    except Exception as e:
        print(e)
        pygame.mixer.init(channels=1, buffer=8196)
        sound = pygame.mixer.music
        sound.load('mic_error.wav')
        sound.play()
        wait(sound)
        raise Exception("Error when trying to listen to microphone.")


def jarvis_process():
    alternate_standard_files = ["yes.wav", "go_on.wav"]

    def get_next_audio_frame():
        pcm = audio_stream.read(handle.frame_length)
        pcm = struct.unpack_from("h" * handle.frame_length, pcm)
        return pcm

    def get_standard_path():
        global last_time
        gap = datetime.datetime.now() - last_time
        last_time = datetime.datetime.now()
        if gap.seconds > 60 * 5:
            return 'standard_response.wav'
        else:
            return random.choice(alternate_standard_files)

    def wait(s):
        while s.get_busy():
            pygame.time.wait(100)

    handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                keyword_paths=[get_pico_path()])

    pa = pyaudio.PyAudio()

    pygame.mixer.init(channels=1, buffer=8196)
    sound = pygame.mixer.music
    sound.load("ready_in.wav")
    sound.play()
    wait(sound)
    time.sleep(0.5)

    audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                           frames_per_buffer=handle.frame_length, input_device_index=None)

    try:
        while True:
            keyword_index = handle.process(get_next_audio_frame())
            if keyword_index >= 0:
                audio_stream.stop_stream()
                time.sleep(0.1)
                pygame.mixer.init(channels=1, buffer=8196)
                sound = pygame.mixer.music
                sound.load(get_standard_path())
                sound.play()
                wait(sound)
                time.sleep(0.2)
                try:
                    print("listening...")
                    query = listen_to_user()

                    print("query", query)
                    sound.load('processing.wav')
                    sound.play(loops=3)
                    print("processing...")
                    try:
                        text = generate_response(query)
                    except TypeError as e:
                        print(e)
                        text = "I am so sorry, my circuits are all flustered, ask me again please."
                    print("text", text)

                    print("Making audio response")
                    audio_path = text_to_speech(text)
                    sound.fadeout(500)
                    sound.load(audio_path)
                    sound.play()
                    wait(sound)
                    os.remove(audio_path)
                    time.sleep(0.1)
                except Exception as e:
                    print(e)
                    audio_stream.stop_stream()
                    pygame.mixer.init(channels=1, buffer=8196)
                    sound = pygame.mixer.music
                    sound.load('minor_error.wav')
                    sound.play()
                    wait(sound)

                audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                                       frames_per_buffer=handle.frame_length, input_device_index=None)
    except Exception as e:
        print(e)
        audio_stream.stop_stream()
        pygame.mixer.init(channels=1, buffer=8196)
        sound = pygame.mixer.music
        sound.load('major_error.wav')
        sound.play()
        wait(sound)


if __name__ == "__main__":
    jarvis_process()
