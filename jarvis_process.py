if __name__ == "__main__":
    import sys
    import subprocess_access
    subprocess_access.setter(sys.argv[1])
import ctypes.util
import functools
import os
import pvporcupine
import pygame
import struct
import time
import datetime

from connections import ConnectionKeyError

# Configure logging
import logger_config
logger = logger_config.get_logger()

# Set last time of request
last_time = datetime.datetime.now() - datetime.timedelta(minutes=5)


def import_pyaudio():
    """
    Import pyaudio with a patched version of ctypes.util.find_library.
    """
    logger.info("Attempting to import pyaudio using patched `ctypes.util.find_library`...")
    _find_library_original = ctypes.util.find_library

    @functools.wraps(_find_library_original)
    def _find_library_patched(name):
        """
        Patched version of ctypes.util.find_library to help importing pyaudio.

        :param name: str, the name of the library to find
        :return: str, the path to the library, if found, otherwise the result of the original find_library function
        """
        if name == "portaudio":
            return "libportaudio.so.2"
        else:
            return _find_library_original(name)

    ctypes.util.find_library = _find_library_patched

    import pyaudio

    logger.info("pyaudio import successful!")
    logger.info("Restoring original `ctypes.util.find_library`...")
    ctypes.util.find_library = _find_library_original
    del _find_library_patched
    logger.info("Original `ctypes.util.find_library` restored.")

    return pyaudio


if os.getcwd() != '/Users/eliasweston-farber/Desktop/Jarvis':
    pyaudio = import_pyaudio()
    from audio_listener import prep_mic, listen_to_user, convert_to_text
else:
    import pyaudio
    from audio_listener import prep_mic, listen_to_user, convert_to_text


def get_next_audio_frame(handle, audio_stream):
    """
    Read the next frame from the audio stream.

    :param handle: The Porcupine handle
    :param audio_stream: The pyaudio.PyAudio stream
    :return: tuple, the unpacked PCM data
    """

    pcm = audio_stream.read(handle.frame_length)
    pcm = struct.unpack_from("h" * handle.frame_length, pcm)
    return pcm


def wait(sound):
    """
    Wait for the sound to finish playing.

    :param sound: The pygame.mixer.music instance
    """
    while sound.get_busy():
        pygame.time.wait(100)


def jarvis_process():
    """
    Main function to run the Jarvis voice assistant process.
    """
    audio_stream = None
    try:
        from connections import get_pico_key, get_pico_path
        from processor import processor
        from text_speech import text_to_speech

        global last_time

        handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                    keyword_paths=[get_pico_path()])

        pa = pyaudio.PyAudio()

        pygame.mixer.init(channels=1, buffer=8196)
        sound = pygame.mixer.music
        sound.load("audio_files/tone_one.wav")
        sound.play()
        wait(sound)

        prep_mic()

        audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                               frames_per_buffer=handle.frame_length, input_device_index=None)

        try:
            while True:
                keyword_index = handle.process(get_next_audio_frame(handle, audio_stream))
                if keyword_index >= 0:
                    audio_stream.stop_stream()
                    try:
                        logger.info("listening...")
                        query_audio = listen_to_user()
                        logger.info("adjusting mic for next time...")
                        prep_mic()
                        gap = datetime.datetime.now() - last_time
                        last_time = datetime.datetime.now()
                        if gap.seconds > 60 * 5:
                            sound.load("audio_files/hmm.wav")
                            sound.play()
                            wait(sound)
                        sound.load('audio_files/beeps.wav')
                        sound.play(loops=7)
                        try:
                            logger.info("Recognizing...")
                            query = convert_to_text(query_audio)
                            logger.info("Query: %s", query)
                            logger.info("Processing...")
                            audio_info = processor(query, return_audio_file=True)
                            if audio_info:
                                logger.info("Playing temporary audio...")
                                if isinstance(audio_info, list):
                                    sound.load(audio_info[0])
                                    sound.play()
                                    wait(sound)
                                    sound.load(audio_info[1])
                                    sound.play(loops=7)
                                else:
                                    sound.load(audio_info)
                                    sound.play()
                            text = processor(query)
                        except TypeError as e:
                            logger.error(e)
                            text = "I am so sorry, my circuits are all flustered, ask me again please."
                        logger.info("Text: %s", text)

                        logger.info("Making audio response")
                        audio_path = text_to_speech(text)
                        sound.fadeout(500)
                        sound.load(audio_path)
                        sound.play()
                        wait(sound)
                        os.remove(audio_path)
                        time.sleep(0.1)
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        with open("inner_error.log", "w") as file:
                            file.write(str(e))
                        audio_stream.stop_stream()
                        pygame.mixer.init(channels=1, buffer=8196)
                        sound = pygame.mixer.music
                        sound.load('audio_files/minor_error.wav')
                        sound.play()
                        wait(sound)

                    audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                                           frames_per_buffer=handle.frame_length, input_device_index=None)
        except Exception as e:
            logger.error(e, exc_info=True)
            with open("outer_error.log", "w") as file:
                file.write(str(e))
            audio_stream.stop_stream()
            pygame.mixer.init(channels=1, buffer=8196)
            sound = pygame.mixer.music
            sound.load('audio_files/major_error.wav')
            sound.play()
            wait(sound)
    except ConnectionKeyError as e:
        logger.error(e, exc_info=True)
        if audio_stream:
            audio_stream.stop_stream()
        pygame.mixer.init(channels=1, buffer=8196)
        sound = pygame.mixer.music
        sound.load('audio_files/connection_error.wav')
        sound.play(-1)
        wait(sound)


def test_mic():
    """
    Test the microphone before running the Jarvis voice assistant process.
    """
    from connections import get_pico_key, get_pico_path
    logger.info("Testing mic...")
    handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                keyword_paths=[get_pico_path()])

    pa = pyaudio.PyAudio()

    prep_mic()

    audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                           frames_per_buffer=handle.frame_length, input_device_index=None)
    time.sleep(1)
    audio_stream.stop_stream()
    logger.info("Mic tested.")


if __name__ == "__main__":
    jarvis_process()

