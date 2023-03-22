import tiktoken
import time
import openai
import atexit
from concurrent.futures import ThreadPoolExecutor
from keys import get_openai_key
from assistant_history import AssistantHistory

# Set up logging
import logger_config
logger = logger_config.get_logger()

# Constants
history_changed = False
model = "gpt-3.5-turbo-0301"
temperature = 0.8
maximum_length_message = 500
maximum_length_history = 2800
top_p = 1
frequency_penalty = 0.19
presence_penalty = 0
history_path = "history.json"

openai.api_key = get_openai_key()
enc = tiktoken.encoding_for_model(model)
assert enc.decode(enc.encode("hello world")) == "hello world"

# Setup background task system
executor = ThreadPoolExecutor(max_workers=1)
tasks = []

# Load Assistant History
history_access = AssistantHistory()
history_access.load_history_from_json(history_path)


def refresh_assistant():
    """
    Updates the conversation history.
    """
    global history_changed
    if history_changed:
        logger.info("Refreshing history...")
        history_access.reduce_context()
        history_access.save_history_to_json(history_path)
        logger.info("History saved")
    history_changed = False


def background_refresh_assistant():
    """
    Run the refresh_assistant function in the background and handle exceptions.

    This function is intended to be used with ThreadPoolExecutor to prevent blocking the main thread
    while refreshing conversation history.
    """
    try:
        refresh_assistant()
    except Exception as e:
        logger.exception("Error reducing history in background:", e)


def generate_response(query):
    """
    Generate a response to the given query.

    :param query: The user's input query.
    :type query: str
    :return: The AI Assistant's response.
    :rtype: str
    """
    safe_wait()
    history_access.add_user_query(query)
    response = openai.ChatCompletion.create(
        model=model,
        messages=history_access.gather_context(query)+[{"role": "user", "content": query}],
        temperature=temperature,
        max_tokens=maximum_length_message,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )
    output = response['choices'][0]['message']['content']
    reason = response['choices'][0]["finish_reason"]
    if reason != "stop":
        if reason == "length":
            history_access.add_assistant_response(output)
            return output + "... I'm sorry, I have been going on and on haven't I?"
        if reason == "null":
            history_access.reset_add()
            return "I'm so sorry I got overwhelmed, can you put that more simply?"
        if reason == "content_filter":
            history_access.add_assistant_response(output)
            output = "I am so sorry, but if I responded to that I would have been forced to say something naughty."
    schedule_refresh_assistant()
    return output


def schedule_refresh_assistant():
    """
    This function runs the refresh_history function in the background to prevent
    blocking the main thread while updating the conversation history.
    """
    global executor, tasks, history_changed
    history_changed = True
    tasks.append(executor.submit(background_refresh_assistant))
    return


def get_last_response():
    """
    Get the last response in the conversation history.

    :return: A tuple containing the last user query and the last AI Assistant response.
    :rtype: tuple
    """
    return history_access.get_history()[-1][1]


def safe_wait():
    """
    Waits until all scheduled tasks are completed to run
    """
    global tasks
    if tasks:
        logger.info("Waiting for background tasks...")
        for task in tasks:
            task.result()
        tasks = []
        logger.info("Completed background tasks not generating...")


def shutdown_executor():
    """
    Helps with grateful shutdown of executor in case of termination
    """
    global executor
    if executor is not None:
        executor.shutdown(wait=True)
        executor = None


atexit.register(shutdown_executor)
