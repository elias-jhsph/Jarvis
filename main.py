import pvporcupine
import pyaudio
import pygame
import struct
import os
import time
import datetime
import random

from keys import get_pico_key, get_pico_path
from audio_listener import listen_to_user
from gpt_interface import generate_response
from text_speech import text_to_speech

last_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
alternate_standard_files = ["yes.wav", "go_on.wav"]

def get_next_audio_frame():
    pcm = audio_stream.read(handle.frame_length)
    pcm = struct.unpack_from("h" * handle.frame_length, pcm)
    return pcm


def get_standard_path():
    global last_time
    gap = datetime.datetime.now() - last_time
    last_time = datetime.datetime.now()
    if gap.seconds > 60*5:
        return 'standard_response.wav'
    else:
        return random.choice(alternate_standard_files)



def wait(sound):
    while sound.get_busy():
        pygame.time.wait(100)


if __name__ == '__main__':
    try:
        handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                    keyword_paths=[get_pico_path()])

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                               frames_per_buffer=handle.frame_length, input_device_index=None)
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
                time.sleep(0.1)
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
