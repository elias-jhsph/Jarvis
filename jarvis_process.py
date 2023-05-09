import os
import sys

import pvporcupine
import time
import datetime
import re
import atexit
import threading
import multiprocessing

from audio_player import play_audio_file, get_next_audio_frame, start_audio_stream, stop_audio_stream
from audio_listener import prep_mic, listen_to_user, convert_to_text
from connections import ConnectionKeyError, get_pico_key, get_pico_wake_path, get_gcp_data
from processor import processor, get_model_name, get_chat_history
from subroutine_processor import subroutine_processor
from text_speech import text_to_speech

# Configure logging
import logger_config

logger = logger_config.get_logger()

# Set last time of request
last_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
free_tts = False


def check_tts(path: str) -> str:
    """
    Switch the audio path to a free version if the user has a free key.

    :param path: str, the path to the audio file
    :return: str, the path to the audio file
    """
    global free_tts
    if free_tts:
        path = re.sub("audio_files/", "audio_files_free/", path)
    return path


def jarvis_process(jarvis_stop_event: threading.Event, jarvis_skip_event: threading.Event,
                   queue: multiprocessing.Queue, text_queue: multiprocessing.Queue) -> None:
    """
    Main function to run the Jarvis voice assistant process.

    1. Initialize global variables and attempt to get GCP data. If unsuccessful, use the free text-to-speech service.
    2. Set up wake word detection using either Porcupine (default) or Pocketsphinx (fallback).
    3. Define a helper function graceful_skip_loop to handle user-requested skips gracefully.
    4. Play an initial audio file as a tone.
    5. Prepare the microphone and start the audio stream.
    6. Enter the main loop that listens for the wake word and processes user input:
        a. Set the system state to "standby" and listen for the wake word.
        b. If the wake word is detected, stop the audio stream and process the user input:
            i. Listen to the user's query.
            ii. Recognize the query and convert it to text.
            iii. Process the text query and generate a response.
            iv. Create an audio response using text-to-speech and play it back.
            v. Prepare the microphone for the next round and set the system state to "standby."
    7. Handle exceptions and errors at various levels, playing appropriate error audio files.
    8. Perform cleanup, unregistering resources, and deleting the Porcupine handle if necessary.
    9. Log that the Jarvis process has finished.

    :param jarvis_stop_event: threading.Event, the event to stop the process
    :param jarvis_skip_event: threading.Event, the event to skip the current process
    :param queue: multiprocessing.Queue, the queue to send messages to the GUI
    :param text_queue: multiprocessing.Queue, the queue to send messages to the GUI
    :return: None
    """
    try:
        global last_time
        global free_tts

        logs_path = "logs/"
        if getattr(sys, 'frozen', False):
            logs_path = os.path.join(sys._MEIPASS, "logs")

        # Attempt to get GCP data, if unsuccessful use free text-to-speech service
        try:
            get_gcp_data()
        except ConnectionKeyError as e:
            free_tts = True
            logger.info("Using free text to speech service.")

        # Initialize wake word detection
        try:
            free_wake = False
            handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                        keyword_paths=[get_pico_wake_path()])
            atexit.register(handle.delete)
        except ConnectionKeyError as e:
            free_wake = True
            from pocketsphinx import LiveSpeech

            def pocketsphinx_wake_word_detection(wake_word, stop_event, sub_queue):
                """
                Detects wake word using pocketsphinx.
                :param wake_word:
                :param stop_event:
                :param sub_queue:
                :return:
                """
                speech = LiveSpeech()
                for phrase in speech:
                    if not sub_queue.is_empty():
                        return sub_queue.get()
                    if str(phrase).lower() == wake_word.lower():
                        return ""
                    if stop_event.is_set():
                        break
                return False

        def graceful_skip_loop():
            """
            Gracefully skip the loop if the user requests it.
            """
            if jarvis_skip_event.is_set():
                logger.info("Skipping...")
                queue.put("standby")
                play_audio_file("audio_files/tone_one.wav", blocking=True)
                stop_audio_stream()
                if not free_wake:
                    start_audio_stream(handle.sample_rate, handle.frame_length)
                return True
            else:
                return False

        # Play an initial audio file
        play_audio_file("audio_files/tone_one.wav", blocking=False, delay=3.5)

        # Prepare the microphone and start audio stream
        prep_mic()
        if not free_wake:
            start_audio_stream(handle.sample_rate, handle.frame_length)

        # Prep subroutine multiprocessing queue
        subroutine_queue = None

        # Main loop for processing user input
        try:
            queue.put("standby")
            logger.info("Listening for wake word...")
            detected = False
            while not jarvis_stop_event.is_set():
                text_queue.put({"finished": False, "clear": True})

                # Clear skip event if set
                if jarvis_skip_event.is_set():
                    jarvis_skip_event.clear()

                # Detect wake word
                pocketsphinx_collected_message = ""
                if free_wake:
                    pocketsphinx_collected_message = pocketsphinx_wake_word_detection("Jarvis",
                                                                                      jarvis_stop_event,
                                                                                      subroutine_queue)
                    if pocketsphinx_collected_message == "":
                        detected = True
                else:
                    pcm = get_next_audio_frame(handle)
                    if pcm is not None:
                        keyword_index = handle.process(pcm)
                    if keyword_index >= 0:
                        detected = True
                if subroutine_queue is not None or pocketsphinx_collected_message != "":
                    if not subroutine_queue.empty() or pocketsphinx_collected_message != "":
                        if pocketsphinx_collected_message != "":
                            message = pocketsphinx_collected_message
                        else:
                            message = subroutine_queue.get()
                        if message == "pause":
                            logger.info("Pausing for subroutine...")
                            subroutine_queue.put("go")
                            time.sleep(2)
                            # wait for subroutine to finish
                            while not subroutine_queue.empty() and \
                                    not jarvis_stop_event.is_set() and \
                                    not jarvis_skip_event.is_set():
                                time.sleep(0.1)
                            message = subroutine_queue.get()
                            if message != "resume":
                                logger.error("Subroutine did not return resume message.")
                                play_audio_file(check_tts('audio_files/major_error.wav'))
                # Process user input if wake word detected
                if detected:
                    detected = False
                    stop_audio_stream()

                    try:
                        if graceful_skip_loop():
                            continue

                        # Listen to user query
                        logger.info("listening...")
                        queue.put("listening")
                        query_audio = listen_to_user()
                        if graceful_skip_loop():
                            continue
                        queue.put("processing")

                        # Calculate gap between queries
                        gap = datetime.datetime.now() - last_time
                        last_time = datetime.datetime.now()

                        # Play audio file based on gap duration (commented out)
                        # if gap.seconds > 60 * 5:
                        #     play_audio_file(check_tts("audio_files/hmm.wav"))

                        # Play beeping sound while processing
                        beeps_stop_event = play_audio_file("audio_files/beeps.wav", loops=7, blocking=False,
                                                           added_stop_event=jarvis_skip_event)
                        try:
                            # Recognize user query
                            logger.info("Recognizing...")
                            query = convert_to_text(query_audio)
                            if graceful_skip_loop():
                                continue
                            if not re.search('[a-zA-Z]', query):
                                raise Exception("No text found in audio")
                            logger.info("Query: %s", query)

                            # Process user query
                            logger.info("Processing...")
                            if query.lower().find("subroutine") != -1:
                                beeps_stop_event.set()
                                subroutine_queue = subroutine_processor(query, subroutine_queue,
                                                                        jarvis_stop_event=jarvis_stop_event,
                                                                        jarvis_skip_event=jarvis_skip_event)
                                text = None
                            else:
                                text_queue.put({"role": "user", "content": query})
                                text = processor(query, beeps_stop_event, skip=jarvis_skip_event, text_queue=text_queue)
                            if graceful_skip_loop():
                                continue
                        except TypeError as e:
                            logger.error(e, exc_info=True)
                            with open(logs_path+"processor_error.log", "w") as file:
                                file.write(str(e))
                            text = "I am so sorry, my circuits are all flustered, ask me again please."
                        logger.info("Text: %s", text)

                        # Play audio response
                        if not graceful_skip_loop():
                            if beeps_stop_event.is_set() is False:
                                logger.info("Making audio response")
                                audio_path = text_to_speech(text, model=get_model_name())
                                beeps_stop_event.set()
                                if graceful_skip_loop():
                                    continue
                                text_queue.put({"role": "assistant", "content": text, "model": get_model_name()})
                                play_audio_file(audio_path, added_stop_event=jarvis_skip_event)
                                os.remove(audio_path)
                                time.sleep(0.1)

                        # Prepare microphone for next round
                        logger.info("Adjusting mic...")
                        prep_mic()
                        queue.put("standby")
                        logger.info("Finished processing")
                        play_audio_file("audio_files/tone_one.wav", blocking=True)
                        logger.info("Listening for wake word...")
                        text_queue.put({"finished": True, "results": get_chat_history(limit=2)})
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        with open(logs_path+"inner_error.log", "w") as file:
                            file.write(str(e))
                        stop_audio_stream()
                        play_audio_file(check_tts('audio_files/minor_error.wav'))
                    if not free_wake:
                        start_audio_stream(handle.sample_rate, handle.frame_length)
                if free_wake:
                    if pocketsphinx_thread.is_alive() is False:
                        # create pocketsphinx thread
                        pocketsphinx_thread = threading.Thread(target=pocketsphinx_wake_word_detection,
                                                               args=("Jarvis", jarvis_stop_event))
                        pocketsphinx_thread.start()
            stop_audio_stream()
        except Exception as e:
            logger.error(e, exc_info=True)
            with open(logs_path+"outer_error.log", "w") as file:
                file.write(str(e))
            stop_audio_stream()
            play_audio_file(check_tts('audio_files/major_error.wav'))
    except ConnectionKeyError as e:
        logger.error(e, exc_info=True)
        stop_audio_stream()
        play_audio_file(check_tts('audio_files/connection_error.wav'))

    # Cleanup
    if subroutine_queue is not None:
        subroutine_queue.put("user kill")
    if not free_wake:
        atexit.unregister(handle.delete)
        handle.delete()
    logger.info("Jarvis process finished.")
    return


def test_mic() -> None:
    """
    Test the microphone before running the Jarvis voice assistant process.

    :return: None
    """
    logger.info("Testing mic...")
    try:
        handle = pvporcupine.create(access_key=get_pico_key(), keywords=['Jarvis'],
                                    keyword_paths=[get_pico_wake_path()])
        prep_mic()
        start_audio_stream(handle.sample_rate, handle.frame_length)
        time.sleep(1)
        stop_audio_stream()
        logger.info("Mic tested.")
        logger.info("listening...")
        query_audio = listen_to_user()
        logger.info("Recognizing...")
        query = convert_to_text(query_audio)
        logger.info("Heard: %s", query)
    except ConnectionKeyError as e:
        logger.warning("Could not test mic because pico key is not set.")
    return


