import atexit
import ctypes.util
import functools
import os
import time
import threading
import wave
import struct
import numpy as np

# Configure logging
import logger_config
logger = logger_config.get_logger()


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
else:
    import pyaudio
pa = pyaudio.PyAudio()
audio_stream = None


def play_audio_file(file_path, blocking=True, loops=1, delay=0, destroy=False, added_stop_event=None):
    """
    Play an audio file using pyaudio.

    :param file_path: str, path to the audio file
    :param blocking: bool, whether the audio playback should block the main thread (default: True)
    :param loops: int, the number of times to loop the audio file (default: 1)
    :param delay: float, the delay in seconds before starting playback (default: 0)
    :param destroy: bool, whether to destroy the file after playback (default: False)
    :param added_stop_event: threading.Event, an event to signal stopping the playback (only for non-blocking mode)
    :return: threading.Event, an event to signal stopping the playback (only for non-blocking mode)
    """
    stop_event = threading.Event()

    if blocking:
        time.sleep(delay)
        _play_audio_file_blocking(file_path, stop_event, loops, 0, destroy, added_stop_event)
    else:
        playback_thread = threading.Thread(target=_play_audio_file_blocking,
                                           args=(file_path, stop_event, loops, delay, destroy, added_stop_event))
        playback_thread.start()

    return stop_event


def _play_audio_file_blocking(file_path, stop_event, loops, delay, destroy, added_stop_event):
    """
    Play an audio file using pyaudio, blocking the calling thread until playback is complete or stopped.

    :param file_path: str, path to the audio file
    :param stop_event: threading.Event, an event to signal stopping the playback
    :param loops: int, the number of times to loop the audio file
    :param delay: float, the delay in seconds before starting playback
    :param destroy: bool, whether to destroy the file after playback
    :param added_stop_event: threading.Event, an event to signal stopping the playback

    """
    global pa
    global audio_stream
    stream = None
    if isinstance(file_path, list):
        if isinstance(loops, list) and isinstance(destroy, list):
            for i, file in enumerate(file_path):
                _play_audio_file_blocking(file, stop_event, loops[i], delay, destroy[i], added_stop_event)
        elif isinstance(loops, list):
            for i, file in enumerate(file_path):
                _play_audio_file_blocking(file, stop_event, loops[i], delay, destroy, added_stop_event)
        else:
            for file in file_path:
                _play_audio_file_blocking(file, stop_event, loops, delay, destroy, added_stop_event)
        return
    else:
        chunk = 8196
        if audio_stream is not None:
            logger.warning("Audio stream already exists, closing it...")
            stop_audio_stream()
        added_stop = False
        if added_stop_event is not None:
            if added_stop_event.is_set():
                added_stop = True
        if not stop_event.is_set() and not added_stop:
            time.sleep(delay)
            for loop in range(loops):
                with wave.open(file_path, 'rb') as wf:
                    stream = pa.open(format=pa.get_format_from_width(wf.getsampwidth()),
                                     channels=wf.getnchannels(),
                                     rate=wf.getframerate(),
                                     output=True,
                                     frames_per_buffer=chunk)

                    data = wf.readframes(chunk)
                    while data:
                        if added_stop_event is not None:
                            if added_stop_event.is_set():
                                added_stop = True
                        if not stop_event.is_set() and not added_stop:
                            stream.write(data)
                            data = wf.readframes(chunk)
                        else:
                            data = fade_out(data, 400)  # Adjust fade_duration for a very short fade-out
                            stream.write(data)
                            break
        if stream is not None:
            try:
                stream.stop_stream()
            finally:
                stream.close()
        if destroy:
            os.remove(file_path)


def fade_out(data, fade_duration, rms_threshold=1000):
    """
    Fade out the audio data.
    :param data:
    :param fade_duration:
    :param rms_threshold:
    :return:
    """
    def rms(aud_data):
        return np.sqrt(np.maximum(np.mean(np.square(aud_data)), 0))

    num_samples = len(data) // 2  # Divide by 2 for 16-bit audio samples
    fade_samples = min(num_samples, fade_duration)
    audio_data = np.frombuffer(data, dtype=np.int16).copy()  # Create a writeable copy of the array

    start_fade = 0
    for i in range(0, num_samples - fade_samples, fade_samples):
        if rms(audio_data[i:i + fade_samples]) < rms_threshold:
            start_fade = i
            break

    fade = np.linspace(1, 0, num_samples - start_fade).astype(np.int16)  # Convert fade array to int16
    audio_data[start_fade:] *= fade
    return audio_data.tobytes()


def start_audio_stream(rate, length):
    """
    Start the audio stream.
    :param rate:
    :param length:
    :return:
    """
    global audio_stream
    audio_stream = pa.open(rate=rate, channels=1, format=pyaudio.paInt16, input=True,
                           frames_per_buffer=length, input_device_index=None)


def stop_audio_stream():
    """
    Stop the audio stream.
    :return:
    """
    global audio_stream
    if audio_stream is not None:
        try:
            audio_stream.stop_stream()
            audio_stream.close()
        except Exception as e:
            logger.error(f"Failed to stop the audio stream: {e}")
        finally:
            audio_stream = None


def get_next_audio_frame(handle):
    """
    Read the next frame from the audio stream.

    :param handle: The Porcupine handle
    :return: tuple, the unpacked PCM data
    """
    global audio_stream
    try:
        pcm = audio_stream.read(handle.frame_length, exception_on_overflow=False)
    except pyaudio.PyAudioError as e:
        logger.error(f"Input overflow error while reading from the audio stream: {e}")
        return None

    pcm = struct.unpack_from("h" * handle.frame_length, pcm)
    return pcm


def shutdown_audio():
    """
    Shutdown the audio stream and terminate the pyaudio instance.

    :return:
    """
    global audio_stream
    global pa
    stop_audio_stream()
    pa.terminate()


atexit.register(shutdown_audio)
