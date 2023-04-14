from pocketsphinx import LiveSpeech
import pvporcupine
import atexit
from connections import ConnectionKeyError, get_pico_key, get_pico_stop_path
from audio_player import start_audio_stream, stop_audio_stream, get_next_audio_frame

import logger_config
logger = logger_config.get_logger()


def pocketsphinx_wake_word_detection(wake_word, stop_event):
    """
    Detects wake word using pocketsphinx.
    :param wake_word:
    :param stop_event:
    :return:
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
    Detects the stop word and stops the jarvis process.

    :param stop_event: The event to stop the process.
    :param skip_event: The event to skip the process.
    :return:
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
        while stop_event.is_set() is False:
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
        while stop_event.is_set() is False:
            while skip_event.is_set() is False:
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
