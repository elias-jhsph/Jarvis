from pocketsphinx import LiveSpeech
import pvporcupine
import atexit
from connections import ConnectionKeyError, get_pico_key, get_pico_stop_path
from audio_player import start_audio_stream, stop_audio_stream, get_next_audio_frame

import logger_config
logger = logger_config.get_logger()


def pocketsphinx_wake_word_detection(wake_word: str, stop_event) -> bool:
    """
    Detects wake word using pocketsphinx.

    :param wake_word: Wake word to be detected.
    :type wake_word: str
    :param stop_event: The event to stop the wake word detection process.
    :type stop_event: threading.Event
    :return: True if wake word is detected, otherwise False.
    :rtype: bool
    """
    speech = LiveSpeech()
    for phrase in speech:
        if str(phrase).lower() == wake_word.lower():
            return True
        if stop_event.is_set():
            break
    return False


def stop_word_detection(stop_event, skip_event):
    """
    Detects the stop word and stops the Jarvis process.

    :param stop_event: The event to stop the process.
    :type stop_event: threading.Event
    :param skip_event: The event to skip the process.
    :type skip_event: threading.Event
    :return: None
    """
    try:
        free_wake = False
        handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                    keyword_paths=[get_pico_stop_path()])
        atexit.register(handle.delete)
    except ConnectionKeyError as e:
        free_wake = True

    if not free_wake:
        start_audio_stream(handle.sample_rate, handle.frame_length)
        logger.info("Interrupter listening...")
        while not stop_event.is_set():
            pcm = get_next_audio_frame(handle)
            if pcm is not None:
                keyword_index = handle.process(pcm)
            if keyword_index >= 0:
                logger.info("Stop word detected! Interrupting process...")
                skip_event.set()
                stop_event.wait(timeout=3)
                skip_event.wait(timeout=1)
                skip_event.clear()
                logger.info("Stop word detection looping...")
        stop_audio_stream()
        atexit.unregister(handle.delete)
        handle.delete()
    else:
        while not stop_event.is_set():
            while not skip_event.is_set():
                logger.info("Interrupter listening...")
                if pocketsphinx_wake_word_detection("interrupt", skip_event):
                    logger.info("Stop word detected! Interrupting process...")
                    skip_event.set()
                    stop_event.wait(timeout=3)
            skip_event.wait(timeout=1)
            skip_event.clear()
            logger.info("Stop word detection looping...")
    logger.info("Stop word detection finished.")
    return
