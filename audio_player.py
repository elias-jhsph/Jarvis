import atexit
import ctypes.util
import functools
import os
import time
import threading
import wave
import struct
from numpy import linspace, int16, sqrt, maximum, mean, square, frombuffer

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
        :type name: str
        :return: str, the path to the library, if found, otherwise the result of the original find_library function
        :rtype: str
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


def play_audio_file(file_path, blocking: bool = True, loops=1, delay: float = 0, destroy=False,
                    added_stop_event: threading.Event = None) -> threading.Event:
    """
    Play an audio file using pyaudio.

    :param file_path: path to the audio file or list of paths to play in sequence
    :type file_path: str or list of str
    :param blocking: whether the audio playback should block the main thread (default: True)
    :type blocking: bool
    :param loops: the number of times to loop the audio file (default: 1) or list of loop counts for each file
    :type loops: int or list of int
    :param delay: the delay in seconds before starting playback (default: 0)
    :type delay: float
    :param destroy: whether to destroy the file after playback (default: False) or list of destroy flags for each file
    :type destroy: bool or list of bool
    :param added_stop_event: an event to signal stopping the playback (only for non-blocking mode)
    :type added_stop_event: threading.Event
    :return: an event to signal stopping the playback (only for non-blocking mode)
    :rtype: threading.Event
    """
    stop_event = threading.Event()

    if blocking:
        time.sleep(delay)
        print(file_path, stop_event, loops, 0, destroy, added_stop_event)
        _play_audio_file_blocking(file_path, stop_event, loops, 0, destroy, added_stop_event)
    else:
        playback_thread = threading.Thread(target=_play_audio_file_blocking,
                                           args=(file_path, stop_event, loops, delay, destroy, added_stop_event))
        playback_thread.start()

    return stop_event


def _play_audio_file_blocking(file_path: str, stop_event: threading.Event, loops: int, delay: float, destroy: bool,
                              added_stop_event: threading.Event):
    """
    Play an audio file using pyaudio, blocking the calling thread until playback is complete or stopped.

    :param file_path: path to the audio file
    :type file_path: str
    :param stop_event: an event to signal stopping the playback
    :type stop_event: threading.Event
    :param loops: the number of times to loop the audio file
    :type loops: int
    :param delay: the delay in seconds before starting playback
    :type delay: float
    :param destroy: whether to destroy the file after playback
    :type destroy: bool
    :param added_stop_event: an event to signal stopping the playback
    :type added_stop_event: threading.Event
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


def fade_out(data: bytes, fade_duration: int, rms_threshold: int = 1000) -> bytes:
    """
    Fade out the audio data.

    :param data: the audio data to fade out
    :type data: bytes
    :param fade_duration: the duration of the fade in samples
    :type fade_duration: int
    :param rms_threshold: the threshold for determining if audio is present
    :type rms_threshold: int
    :return: the audio data with a fade-out applied
    :rtype: bytes
    """

    def rms(aud_data):
        return sqrt(maximum(mean(square(aud_data)), 0))

    num_samples = len(data) // 2  # Divide by 2 for 16-bit audio samples
    fade_samples = min(num_samples, fade_duration)
    audio_data = frombuffer(data, dtype=int16).copy()  # Create a writeable copy of the array

    start_fade = 0
    for i in range(0, num_samples - fade_samples, fade_samples):
        if rms(audio_data[i:i + fade_samples]) < rms_threshold:
            start_fade = i
            break

    fade = linspace(1, 0, num_samples - start_fade).astype(int16)  # Convert fade array to int16
    audio_data[start_fade:] *= fade
    return audio_data.tobytes()


def start_audio_stream(rate: int, length: int) -> None:
    """
    Start the audio stream.

    :param rate: the sampling rate of the audio stream
    :type rate: int
    :param length: the length of the audio stream in frames per buffer
    :type length: int
    """
    global audio_stream
    audio_stream = pa.open(rate=rate, channels=1, format=pyaudio.paInt16, input=True,
                           frames_per_buffer=length, input_device_index=None)


def stop_audio_stream() -> None:
    """
    Stop the audio stream.
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


def shutdown_audio() -> None:
    """
    Shutdown the audio stream and terminate the pyaudio instance.
    """
    global audio_stream
    global pa
    stop_audio_stream()
    pa.terminate()


atexit.register(shutdown_audio)
