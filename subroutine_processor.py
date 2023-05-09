import os
import multiprocessing
import sys
import time
import openai
from PySide6.QtWidgets import QFileDialog, QApplication
from tiktoken import encoding_for_model
from connections import get_openai_key, get_subroutine_path, ConnectionKeyError
from text_speech import text_to_speech
from audio_player import play_audio_file
from subroutine_process import run_subroutine_process, open_subroutine_process, kill_subroutine_process, \
    get_user_response, get_user_preferences_for_new_subroutine, save_subroutine_files, is_there_a_stored_subroutine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up OpenAI API
base_model = "text-davinci-003"
chat_model = "gpt-3.5-turbo"
enc = encoding_for_model(base_model)
api_key = get_openai_key()

try:
    path_to_subroutine = os.path.dirname(get_subroutine_path())
except ConnectionKeyError:
    path_to_subroutine = None

current_process = None


def subroutine_processor(raw_query, subroutine_queue, jarvis_stop_event=multiprocessing.Event(),
                         jarvis_skip_event=multiprocessing.Event()):
    """
    Process the raw query and determine the appropriate action to take

    :param raw_query: str, the raw query string
    :param subroutine_queue: queue.Queue, queue to track subroutine process
    :param jarvis_stop_event: multiprocessing.Event, event to stop Jarvis
    :param jarvis_skip_event: multiprocessing.Event, event to skip Jarvis
    :return: queue.Queue, the updated subroutine queue
    """
    if path_to_subroutine is None:
        logger.warning("Could not find subroutine path! Skipping...")
        play_audio_file(text_to_speech("I'm sorry, you need to add a valid subroutine path in the settings menu. "
                                       "Try again after you've done that. Keep in mind you will need to select 'stop"
                                       " listening' before your path update will take effect."))
        return subroutine_queue
    prompt = f'If you had to classify whether the user wanted to "create", "check", "stop", "cancel", ' \
             f'"restart", "continue", "open", "kill", "save", "complete" or ' \
             f'"unrelated" a subroutine based on the following query "{raw_query}" which would you choose? Please ' \
             f'limit your response to one of the eleven words: '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=20,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    text = response.choices[0].text.lower()
    reason = response.choices[0].finish_reason
    if reason != "stop":
        logger.warning("Could not clean up search smart query! got back:" + text)
        play_audio_file(text_to_speech("I'm sorry, I didn't understand your subroutine request. Lets start over."))
        return subroutine_queue
    return subroutine_processor_switcher(text, subroutine_queue, jarvis_stop_event, jarvis_skip_event)


def subroutine_processor_switcher(text, subroutine_queue, jarvis_stop_event=multiprocessing.Event(),
                         jarvis_skip_event=multiprocessing.Event()):
    """
    Process the raw query and determine the appropriate action to take

    :param raw_query: str, the raw query string
    :param subroutine_queue: queue.Queue, queue to track subroutine process
    :param jarvis_stop_event: multiprocessing.Event, event to stop Jarvis
    :param jarvis_skip_event: multiprocessing.Event, event to skip Jarvis
    :return: queue.Queue, the updated subroutine queue
    """
    global current_process
    if text.find("create") != -1 and subroutine_queue is not None:
        logger.info("Subroutine create when subroutine queue is not none")
        play_audio_file(text_to_speech("I'm sorry, but there is a subroutine already running. Do you want me "
                                       "to check on its progress, delete it, "
                                       "or to cancel this request and have it continue running?"), blocking=False)
        user_response = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                          jarvis_skip_event=jarvis_skip_event)
        if user_response is None:
            play_audio_file(text_to_speech("I'm sorry, you can ask me again later."))
            return subroutine_queue
        prompt = f'If you had to classify whether the user wanted to "check", "stop", "cancel", or "unrelated"' \
                 f' a subroutine based on the following query "{user_response}" which would you choose? ' \
                 f'Please limit your response to one of the four words: '
        response = openai.Completion.create(
            engine=base_model,
            prompt=prompt,
            max_tokens=20,
            n=1,
            stop=None,
            temperature=0.8,
            api_key=api_key,
        )
        text = response.choices[0].text.lower()
        reason = response.choices[0].finish_reason
        if reason != "stop":
            logger.warning("Could not clean up search smart query! got back:" + text)
            play_audio_file(
                text_to_speech("I'm sorry, I didn't understand your subroutine request. Lets start over."))
            return subroutine_queue
        else:
            return subroutine_processor_switcher(text, subroutine_queue, jarvis_stop_event, jarvis_skip_event)

    if text.find("create") != -1 and subroutine_queue is None:
        logger.info("Subroutine create when subroutine queue is none")
        input_commands = get_user_preferences_for_new_subroutine(jarvis_stop_event=jarvis_stop_event,
                                                                 jarvis_skip_event=jarvis_skip_event)
        subroutine_queue = multiprocessing.Queue()
        current_process = create_subroutine_process(input_commands, subroutine_queue, jarvis_stop_event=jarvis_stop_event,
                                  jarvis_skip_event=jarvis_skip_event)
        play_audio_file(text_to_speech("Will do. I am starting the subroutine now!"))
        return subroutine_queue

    if text.find("stop") != -1:
        if subroutine_queue is None:
            logger.info("Subroutine stop when subroutine queue is none")
            play_audio_file(text_to_speech("There is no subroutine running at this time."))
            return subroutine_queue
        else:
            logger.info("Subroutine stop")
            play_audio_file(
                text_to_speech("Ok, I am stopping the current subroutine."))
            subroutine_queue.put("user stop")
            return subroutine_queue

    if text.find("check") != -1:
        if subroutine_queue is None:
            logger.info("Subroutine check when subroutine queue is none")
            question = "There is no subroutine running at this time. Would you like me to attempt " \
                       "to continue a stopped subroutine?"
            play_audio_file(text_to_speech(question))
            user_response = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                              jarvis_skip_event=jarvis_skip_event)
            if user_response is None:
                play_audio_file(text_to_speech("I'm sorry, you can ask me again later."))
                return subroutine_queue
            prompt = f'If you had to classify whether the user responded "yes", "no", or "unrelated" to the question' \
                     f'"{question}" when they said "{user_response}" which would you choose? Please limit your ' \
                     f'response to one of the three words: '
            response = openai.Completion.create(
                engine=base_model,
                prompt=prompt,
                max_tokens=20,
                n=1,
                stop=None,
                temperature=0.8,
                api_key=api_key,
            )
            text = response.choices[0].text.lower()
            reason = response.choices[0].finish_reason
            if reason != "stop":
                logger.warning("Could not clean up search smart query! got back:" + text)
                play_audio_file(
                    text_to_speech("I'm sorry, I didn't understand your subroutine request. Lets start over."))
                return subroutine_queue
            if text.find("yes") != -1:
                logger.info("Subroutine check when subroutine queue is none and user said yes")
                return subroutine_processor_switcher("restart", subroutine_queue, jarvis_stop_event, jarvis_skip_event)
            else:
                play_audio_file(
                    text_to_speech("Alright then, I'll cancel this request."))
                return subroutine_queue
        else:
            logger.info("Subroutine check")
            play_audio_file(text_to_speech("Ok I am checking on the current subroutine, I will be back in a moment."))
            subroutine_queue.put("user check")
            return subroutine_queue

    if text.find("unrelated") != -1:
        logger.info("Subroutine unrelated")
        play_audio_file(
            text_to_speech("I'm sorry, I got confused and thought you were asking me about subroutines. "
                           "Ask me again please and I'll try to pay better attention."))
        return subroutine_queue

    if text.find("cancel") != -1:
        logger.info("Subroutine cancel")
        play_audio_file(
            text_to_speech("Alright then, I'll cancel this request."))
        return subroutine_queue

    if text.find("restart") != -1 or text.find("continue") != -1:
        if subroutine_queue is not None:
            logger.info("Subroutine restart when subroutine queue is not none")
            play_audio_file(text_to_speech("There is a subroutine running at this time already."))
            return subroutine_queue
        else:
            if not is_there_a_stored_subroutine():
                play_audio_file(text_to_speech("I'm sorry, there isn't an incomplete subroutine in my memory."))
                return None
            logger.info("Subroutine restart")
            sub_queue = multiprocessing.Queue()
            play_audio_file(
                text_to_speech("Continuing the last subroutine."))
            current_process = create_subroutine_process({"continue": True}, sub_queue,
                                                        jarvis_stop_event=jarvis_stop_event,
                                                        jarvis_skip_event=jarvis_skip_event)
            time.sleep(1)
            if not current_process.is_alive():
                play_audio_file(text_to_speech("I'm sorry, I couldn't continue the last subroutine."))
                return None
            return sub_queue

    if text.find("open") != -1:
        if subroutine_queue is not None:
            logger.info("Subroutine open")
            play_audio_file(
                text_to_speech("Alright then, I'll open the last subroutine."))
            open_subroutine_process()
            return subroutine_queue
        else:
            logger.info("Subroutine open when subroutine queue is none")
            play_audio_file(text_to_speech("There is no subroutine running at this time but I will try and open tmux."))
            open_subroutine_process()
            return subroutine_queue

    if text.find("kill") != -1:
        if subroutine_queue is not None:
            logger.info("Subroutine kill")
            play_audio_file(
                text_to_speech("Alright then, I'll kill all subroutines."))
            subroutine_queue.put("user kill")
            kill_subroutine_process()
            time.sleep(2)
            if current_process is not None:
                current_process.terminate()
            return None
        else:
            logger.info("Subroutine kill when subroutine queue is none")
            play_audio_file(text_to_speech("There is no subroutine running at this time but I will try and kill tmux."))
            kill_subroutine_process()
            return subroutine_queue

    if text.find("save") != -1 and subroutine_queue is not None:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        folder = QFileDialog.getExistingDirectory(None, "Select folder to save files")
        if folder is None:
            play_audio_file(text_to_speech("I'm sorry, I couldn't find that folder."))
            return subroutine_queue
        else:
            subroutine_queue.put("user check")
            play_audio_file(text_to_speech("Saving now... Please wait."))
            time.sleep(10)
            result = subroutine_queue.get(timeout=60)
            save_subroutine_files(folder)
            if result == "resume":
                play_audio_file(text_to_speech("Saving complete with final check."))
            else:
                play_audio_file(text_to_speech("Saving complete."))
            return subroutine_queue

    if text.find("complete") != -1 and subroutine_queue is not None:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        folder = QFileDialog.getExistingDirectory(None, "Select folder to save files")
        if folder is None:
            play_audio_file(text_to_speech("I'm sorry, I couldn't find that folder."))
            return subroutine_queue
        else:
            subroutine_queue.put("user check")
            play_audio_file(text_to_speech("Saving now... Please wait."))
            time.sleep(10)
            result = subroutine_queue.get(timeout=80)
            save_subroutine_files(folder, cut_files=True)
            if result == "resume":
                play_audio_file(text_to_speech("Completed Subroutine with final check."))
            else:
                play_audio_file(text_to_speech("Completed Subroutine."))
            kill_subroutine_process()
            return None

    if (text.find("complete") != -1 or text.find("save") != -1) and subroutine_queue is None:
        logger.info("Subroutine complete or save when subroutine queue is none")
        play_audio_file(text_to_speech("There is no subroutine running at this time."))
        return subroutine_queue

    return subroutine_queue


def create_subroutine_process(predetermined_cmds, subroutine_queue, jarvis_stop_event=multiprocessing.Event(),
                              jarvis_skip_event=multiprocessing.Event()):
    process = multiprocessing.Process(target=run_subroutine_process,
                                              args=(subroutine_queue,
                                                    predetermined_cmds,
                                                    jarvis_stop_event,
                                                    jarvis_skip_event))
    process.start()
    return process


if __name__ == "__main__":
    logger.info("Starting Jarvis")
    jarvis_stop_event = multiprocessing.Event()
    jarvis_skip_event = multiprocessing.Event()
    jarvis_stop_event.clear()
    jarvis_skip_event.clear()
    subroutine_queue = subroutine_processor_switcher("restart", None, jarvis_stop_event, jarvis_skip_event)
    # while True:
    #     try:
    #         subroutine_queue = subroutine_processor_switcher(get_user_response(timeout=60,
    #                                                                            jarvis_stop_event=jarvis_stop_event,
    #                                                                            jarvis_skip_event=jarvis_skip_event),
    #                                                                            subroutine_queue,
    #                                                                            jarvis_stop_event,
    #                                                                            jarvis_skip_event)
    #     except Exception as e:
    #         logger.error("Exception in main loop: " + str(e))
    #         play_audio_file(text_to_speech("I'm sorry, I ran into an error."))
    #         subroutine_queue = None
    #         time.sleep(1)
    #         continue