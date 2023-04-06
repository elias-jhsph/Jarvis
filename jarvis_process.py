import os
import pvporcupine
import time
import datetime
import re
import atexit

from audio_player import play_audio_file, get_next_audio_frame, start_audio_stream, stop_audio_stream
from audio_listener import prep_mic, listen_to_user, convert_to_text
from connections import ConnectionKeyError, get_pico_key, get_pico_path, set_connection_ring
from processor import processor, get_model_name
from text_speech import text_to_speech

# Configure logging
import logger_config
logger = logger_config.get_logger()

# Set last time of request
last_time = datetime.datetime.now() - datetime.timedelta(minutes=5)


def jarvis_process(jarvis_stop_event, queue, codes):
    """
    Main function to run the Jarvis voice assistant process.
    """
    audio_stream = None
    try:

        global last_time
        set_connection_ring(codes)

        try:
            free = False
            handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                        keyword_paths=[get_pico_path()])
            atexit.register(handle.delete)
        except ConnectionKeyError as e:
            free = True
            from pocketsphinx import LiveSpeech

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

        play_audio_file("audio_files/tone_one.wav", blocking=False, delay=2)

        prep_mic()
        if not free:
            start_audio_stream(handle.sample_rate, handle.frame_length)
        try:
            queue.put("standby")
            logger.info("Listening for wake word...")
            detected = False
            while jarvis_stop_event.is_set() is False:
                if free:
                    if pocketsphinx_wake_word_detection("Jarvis", jarvis_stop_event):
                        detected = True
                else:
                    pcm = get_next_audio_frame(handle)
                    if pcm is not None:
                        keyword_index = handle.process(pcm)
                    if keyword_index >= 0:
                        detected = True
                if detected:
                    detected = False
                    stop_audio_stream()
                    try:
                        logger.info("listening...")
                        queue.put("listening")
                        query_audio = listen_to_user()
                        queue.put("processing")
                        gap = datetime.datetime.now() - last_time
                        last_time = datetime.datetime.now()
                        # if gap.seconds > 60 * 5:
                        #     play_audio_file("audio_files/hmm.wav")
                        beeps_stop_event = play_audio_file("audio_files/beeps.wav", loops=7, blocking=False)
                        try:
                            logger.info("Recognizing...")
                            query = convert_to_text(query_audio)
                            if not re.search('[a-zA-Z]', query):
                                raise Exception("No text found in audio")
                            logger.info("Query: %s", query)
                            logger.info("Processing...")
                            text = processor(query, beeps_stop_event)
                        except TypeError as e:
                            logger.error(e, exc_info=True)
                            with open("processor_error.log", "w") as file:
                                file.write(str(e))
                            text = "I am so sorry, my circuits are all flustered, ask me again please."
                        logger.info("Text: %s", text)
                        if beeps_stop_event.is_set() is False:
                            logger.info("Making audio response")
                            audio_path = text_to_speech(text, model=get_model_name())
                            beeps_stop_event.set()
                            play_audio_file(audio_path)
                            os.remove(audio_path)
                            time.sleep(0.1)
                        logger.info("Adjusting mic...")
                        prep_mic()
                        queue.put("standby")
                        logger.info("Finished processing")
                        play_audio_file("audio_files/tone_one.wav", blocking=True)
                        logger.info("Listening for wake word...")
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        with open("inner_error.log", "w") as file:
                            file.write(str(e))
                        stop_audio_stream()
                        play_audio_file('audio_files/minor_error.wav')
                    if not free:
                        start_audio_stream(handle.sample_rate, handle.frame_length)
            stop_audio_stream()
        except Exception as e:
            logger.error(e, exc_info=True)
            with open("outer_error.log", "w") as file:
                file.write(str(e))
            stop_audio_stream()
            play_audio_file('audio_files/major_error.wav')
    except ConnectionKeyError as e:
        logger.error(e, exc_info=True)
        stop_audio_stream()
        play_audio_file('audio_files/connection_error.wav')
    if not free:
        atexit.unregister(handle.delete)
        handle.delete()
    logger.info("Jarvis process finished.")


def test_mic():
    """
    Test the microphone before running the Jarvis voice assistant process.
    """
    logger.info("Testing mic...")
    try:
        handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                    keyword_paths=[get_pico_path()])
        prep_mic()
        start_audio_stream(handle.sample_rate, handle.frame_length)
        time.sleep(1)
        stop_audio_stream()
        logger.info("Mic tested.")
    except ConnectionKeyError as e:
        logger.warning("Could not test mic because pico key is not set.")
    return
