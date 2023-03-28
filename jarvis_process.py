import ctypes.util
import functools
import os
import pvporcupine
import struct
import time
import datetime
import threading
import wave

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


def play_audio_file(file_path, player, blocking=True, loops=1, delay=0):
    """
    Play an audio file using pyaudio.

    :param file_path: str, path to the audio file
    :param player: pyaudio.PyAudio instance
    :param blocking: bool, whether the audio playback should block the main thread (default: True)
    :param loops: int, the number of times to loop the audio file (default: 1)
    :param delay: float, the delay in seconds before starting playback (default: 0)
    :return: threading.Event, an event to signal stopping the playback (only for non-blocking mode)
    """
    stop_event = threading.Event()

    if blocking:
        time.sleep(delay)
        _play_audio_file_blocking(file_path, player, stop_event, loops, 0)
    else:
        playback_thread = threading.Thread(target=_play_audio_file_blocking,
                                           args=(file_path, player, stop_event, loops, delay))
        playback_thread.start()

    return stop_event


def _play_audio_file_blocking(file_path, player, stop_event, loops, delay):
    """
    Play an audio file using pyaudio, blocking the calling thread until playback is complete or stopped.

    :param file_path: str, path to the audio file
    :param player: pyaudio.PyAudio instance
    :param stop_event: threading.Event, an event to signal stopping the playback
    :param loops: int, the number of times to loop the audio file
    :param delay: float, the delay in seconds before starting playback
    """

    chunk = 1024
    if not stop_event.is_set():
        time.sleep(delay)
        for loop in range(loops):
            with wave.open(file_path, 'rb') as wf:
                stream = player.open(format=player.get_format_from_width(wf.getsampwidth()),
                                     channels=wf.getnchannels(),
                                     rate=wf.getframerate(),
                                     output=True)

                data = wf.readframes(chunk)
                while data:
                    if not stop_event.is_set():
                        stream.write(data)
                        data = wf.readframes(chunk)
                    else:
                        fade_out_duration = 1  # seconds
                        fade_out_steps = int(wf.getframerate() / chunk * fade_out_duration)
                        fade_out_step_size = 1 / fade_out_steps
                        sample_width = wf.getsampwidth()

                        for step in range(fade_out_steps):
                            factor = 1 - step * fade_out_step_size
                            num_samples = len(data) // sample_width
                            unpack_format = f"{num_samples}h"
                            samples = struct.unpack(unpack_format, data)
                            faded_samples = [int(sample * factor) for sample in samples]
                            faded_data = struct.pack(unpack_format, *faded_samples)
                            stream.write(faded_data)
                            data = wf.readframes(chunk)

                        break

                stream.stop_stream()
                stream.close()


def jarvis_process(stop_event, queue):
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

        play_audio_file("audio_files/tone_one.wav", pa, blocking=False, delay=2)

        prep_mic()

        audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                               frames_per_buffer=handle.frame_length, input_device_index=None)

        try:
            queue.put("standby")
            while stop_event.is_set() is False:
                keyword_index = handle.process(get_next_audio_frame(handle, audio_stream))
                if keyword_index >= 0:
                    audio_stream.stop_stream()
                    try:
                        logger.info("listening...")
                        queue.put("listening")
                        query_audio = listen_to_user()
                        queue.put("processing")
                        logger.info("adjusting mic for next time...")
                        prep_mic()
                        gap = datetime.datetime.now() - last_time
                        last_time = datetime.datetime.now()
                        if gap.seconds > 60 * 5:
                            play_audio_file("audio_files/hmm.wav", pa)
                        stop_event = play_audio_file("audio_files/beeps.wav", pa, loops=7, blocking=False)
                        try:
                            logger.info("Recognizing...")
                            query = convert_to_text(query_audio)
                            logger.info("Query: %s", query)
                            logger.info("Processing...")
                            audio_info, streamed = processor(query, return_audio_file=True)
                            if audio_info:
                                stop_event.set()
                                logger.info("Playing temporary audio...")
                                if isinstance(audio_info, list):
                                    play_audio_file(audio_info[0], pa)
                                    stop_event = play_audio_file(audio_info[1], pa, loops=7, blocking=False)
                                else:
                                    stop_event = play_audio_file(audio_info, pa, blocking=False)
                                text, streamed = processor(query, stop_audio_event=stop_event)
                            if streamed and not audio_info:
                                stop_event.set()
                                text, streamed = processor(query)
                            else:
                                text, streamed = processor(query)
                            print("MADE IT")
                        except TypeError as e:
                            logger.error(e, exc_info=True)
                            with open("processor_error.log", "w") as file:
                                file.write(str(e))
                            text = "I am so sorry, my circuits are all flustered, ask me again please."
                        logger.info("Text: %s", text)
                        if not streamed:
                            logger.info("Making audio response")
                            audio_path = text_to_speech(text)
                            stop_event.set()
                            play_audio_file(audio_path, pa)
                            os.remove(audio_path)
                            time.sleep(0.1)
                        queue.put("standby")
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        with open("inner_error.log", "w") as file:
                            file.write(str(e))
                        audio_stream.stop_stream()
                        play_audio_file('audio_files/minor_error.wav', pa)

                    audio_stream = pa.open(rate=handle.sample_rate, channels=1, format=pyaudio.paInt16, input=True,
                                           frames_per_buffer=handle.frame_length, input_device_index=None)
            audio_stream.stop_stream()
        except Exception as e:
            logger.error(e, exc_info=True)
            with open("outer_error.log", "w") as file:
                file.write(str(e))
            audio_stream.stop_stream()
            play_audio_file('audio_files/major_error.wav', pa)
    except ConnectionKeyError as e:
        logger.error(e, exc_info=True)
        if audio_stream:
            audio_stream.stop_stream()
        play_audio_file('audio_files/connection_error.wav', pa)


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

