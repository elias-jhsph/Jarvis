import json
import os
import re
import shutil
import sys
import subprocess
import multiprocessing
import time
import atexit
import datetime
import pvporcupine
import openai
from tiktoken import encoding_for_model
from gpt_interface import get_assistant_history, get_model, generate_simple_response
from connections import get_openai_key, get_pico_key, get_pico_wake_path, get_gcp_data, get_subroutine_path, \
    ConnectionKeyError
from text_speech import text_to_speech
from audio_player import play_audio_file, get_next_audio_frame, start_audio_stream, stop_audio_stream
from audio_listener import listen_to_user, convert_to_text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    path_to_subroutine = os.path.dirname(get_subroutine_path())
except ConnectionKeyError:
    path_to_subroutine = None
session_name = "jarvis_subroutine"
current_process = None
shell_profile = "~/.bash_profile"
if getattr(sys, 'frozen', False):
    subroutine_log = os.path.join(sys._MEIPASS, "database/subroutine_log.txt")
    subroutine_chat_data = os.path.join(sys._MEIPASS, "database/subroutine_chat_history.json")
    subroutine_checks = os.path.join(sys._MEIPASS, "database/subroutine_checks")
else:
    subroutine_log = os.path.join(os.path.dirname(__file__), "database/subroutine_log.txt")
    subroutine_chat_data = os.path.join(os.path.dirname(__file__), "database/subroutine_chat_history.json")
    subroutine_checks = os.path.join(os.path.dirname(__file__), "database/subroutine_checks")
if not os.path.exists(subroutine_checks):
    os.mkdir(subroutine_checks)
base_model = "text-davinci-003"
chat_model = "gpt-3.5-turbo"
enc = encoding_for_model(base_model)
api_key = get_openai_key()
ansi_escape = re.compile(r'\033\[[0-9;]+m')


def run_subroutine_process(subroutine_queue, predetermined_cmds, jarvis_stop_event, jarvis_skip_event):
    global session_name
    global shell_profile
    continue_subroutine = True
    if "continue" not in predetermined_cmds:
        continue_subroutine = False
        kill_subroutine_process()
        command = f"source {shell_profile} && cd {path_to_subroutine} && " \
                  f"tmux new-session -d -s {session_name} 'source venv/bin/activate && python -m autogpt --skip-news'"
        subprocess.run(command, shell=True)
        if os.path.exists(subroutine_log):
            os.remove(subroutine_log)
        if os.path.exists(subroutine_chat_data):
            os.remove(subroutine_chat_data)
        with open(subroutine_log, 'w') as file:
            pass
        command_string = f"The current subroutine is called:" \
                         f" {predetermined_cmds['subroutine_name']}.\nThe subroutine's role " \
                         f'is "{predetermined_cmds["subroutine_role"]}".\nThe subroutine\'s goals are:\n'
        for goal in predetermined_cmds["subroutine_goals"]:
            command_string += f'- "{goal}"\n'
        content = get_assistant_history().get_system().get("content", "")
        content += f"\n\n Your current goal is to monitor a subroutine for your user. The subroutine is called:" \
                   f" {predetermined_cmds['subroutine_name']}.\nThe subroutine's role " \
                   f'is "{predetermined_cmds["subroutine_role"]}".\nThe subroutine\'s goals are:\n'
        for goal in predetermined_cmds["subroutine_goals"]:
            content += f'- "{goal}"\n'
        content += f'\n\nThe subroutine\'s rules are: "{predetermined_cmds["subroutine_rules"]}"\n\n'
        content += "Based on the information from the subroutines most recent request memories from previous" \
                   " conversations with the user will be included for your reference. The most recent message is" \
                   " at the bottom of the chat history and it is from the subroutine. " \
                   "There are 6 types of responses you can provide ('y', 'input:', 'confirmation:', 'question:', " \
                   "'notification:', 'n'):\n" \
                   "- 'y' If the subroutine is proceeding along and it wants to run a command that aligns with its" \
                   "rules and goals simply respond with only 'y'\n" \
                   "- 'input' If the subroutine is proceeding along and it needs a piece of information that only" \
                   "you know about human user or thier wishes and giving information wouldn't violate the rules, " \
                   "then create a response that starts 'input: ' and add the information the subroutine needs\n" \
                   "- 'confirmation' If the subroutine is proceeding along and you feel you need to ask your user " \
                   "for confirmation before proceeding create a response that starts 'confirmation: ' and add a" \
                   "yes or no question like 'The subroutine wants to do X. Is that okay?' or 'The subroutine " \
                   "wants your address and I know your address, should I input the following: example address ?'\n" \
                   "- 'question' If the subroutine is proceeding along and you feel you need to ask your user " \
                   "to answer a question for the subroutine or give the user an opportunity to update the " \
                   "subroutine create a response that starts 'question: ' and add a question like 'What is your " \
                   "address?' or 'What is your favorite color?'\n" \
                   "- 'notification' If the subroutine is proceeding along and you feel that the subroutine has " \
                   "reached an important milestone or done something very surprising and exciting create a" \
                   "response that starts 'notification: ' and add a message like 'The subroutine has completed its" \
                   "second goal!'\n" \
                   "- 'n' If the subroutine is proceeding along and it wants to run a command that is very " \
                   " concerning you can simple respond 'n' but remember that you probably should be using a " \
                   "'confirmation' or 'question' response instead\n" \
                   "Your answer must start with 'y', 'input:', 'confirmation:', 'question:', 'notification:', or 'n' " \
                   "(Never respond with the words SYSTEM, THOUGHTS, REASONING, PLAN, or CRITICSM!"
        system_message = {"role": "system", "content": content}
        subroutine_system_data = {"subroutine_info": predetermined_cmds,
                                  "system_message": system_message,
                                  "system_data": command_string}
        with open(subroutine_chat_data, 'w') as file:
            json.dump(subroutine_system_data, file)
    else:
        command = f"source {shell_profile} && cd {path_to_subroutine} && " \
                  f"tmux ls | grep -q '{session_name}'"
        if not subprocess.run(command, shell=True).returncode == 0:
            command = f"source {shell_profile} && cd {path_to_subroutine} && " \
                      f"tmux new-session -d -s {session_name} 'source venv/bin/activate " \
                      f"&& python -m autogpt --skip-news'"
            subprocess.run(command, shell=True)
        if not os.path.exists(subroutine_log) or not os.path.exists(subroutine_chat_data):
            kill_subroutine_process()
            return None
        else:
            with open(subroutine_chat_data, 'r') as file:
                subroutine_system_data = json.load(file)
                command_string = subroutine_system_data.get("system_data")

    # Redirect the output of the tmux session to the temporary file
    redirect_output_command = f"tmux pipe-pane -t {session_name} 'cat >{subroutine_log}'"
    subprocess.run(redirect_output_command, shell=True)
    just_stop = False
    try:
        print(command_string)
        with open(subroutine_log, 'r') as log_file:
            while True:
                # Read the output of the tmux session from the temporary file
                output = log_file.readline().rstrip()
                if not subroutine_queue.empty():
                    message = subroutine_queue.get()
                    if message == "user stop":
                        just_stop = True
                        subroutine_queue = None
                        break
                    if message == "user kill":
                        kill_subroutine_process()
                        return None
                    if message == "user check":
                        check_subroutine_progress(subroutine_queue, command_string, subroutine_log,
                                                  jarvis_stop_event=jarvis_stop_event,
                                                  jarvis_skip_event=jarvis_skip_event)

                # Check if the process is asking for input
                if "Continue (y/n):" in output:
                    if "continue" not in predetermined_cmds:
                        input_to_send = "n"
                        send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                        subprocess.run(send_keys_command, shell=True)
                    else:
                        input_to_send = "y"
                        send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                        subprocess.run(send_keys_command, shell=True)
                        del predetermined_cmds["continue"]
                if not continue_subroutine:
                    if "AI Name:" in output:
                        input_to_send = predetermined_cmds["subroutine_name"]
                        send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                        subprocess.run(send_keys_command, shell=True)
                    if " is:" in output and predetermined_cmds['subroutine_name'] in output:
                            input_to_send = predetermined_cmds["subroutine_role"]
                            send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                            subprocess.run(send_keys_command, shell=True)
                    if "[94mGoal[0m 1:" in output:
                        if len(predetermined_cmds["subroutine_goals"]) >= 1:
                            input_to_send = predetermined_cmds["subroutine_goals"][0]
                            send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                            subprocess.run(send_keys_command, shell=True)
                        else:
                            send_keys_command = f"tmux send-keys -t {session_name} Enter"
                            subprocess.run(send_keys_command, shell=True)
                    if "[94mGoal[0m 2:" in output:
                        if len(predetermined_cmds["subroutine_goals"]) >= 2:
                            input_to_send = predetermined_cmds["subroutine_goals"][1]
                            send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                            subprocess.run(send_keys_command, shell=True)
                        else:
                            send_keys_command = f"tmux send-keys -t {session_name} Enter"
                            subprocess.run(send_keys_command, shell=True)
                    if "[94mGoal[0m 3:" in output:
                        if len(predetermined_cmds["subroutine_goals"]) >= 3:
                            input_to_send = predetermined_cmds["subroutine_goals"][2]
                            send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                            subprocess.run(send_keys_command, shell=True)
                        else:
                            send_keys_command = f"tmux send-keys -t {session_name} Enter"
                            subprocess.run(send_keys_command, shell=True)
                    if "[94mGoal[0m 4:" in output:
                        if len(predetermined_cmds["subroutine_goals"]) >= 4:
                            input_to_send = predetermined_cmds["subroutine_goals"][3]
                            send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                            subprocess.run(send_keys_command, shell=True)
                        else:
                            send_keys_command = f"tmux send-keys -t {session_name} Enter"
                            subprocess.run(send_keys_command, shell=True)
                    if "[94mGoal[0m 5:" in output:
                        if len(predetermined_cmds["subroutine_goals"]) >= 5:
                            input_to_send = predetermined_cmds["subroutine_goals"][4]
                            send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                            subprocess.run(send_keys_command, shell=True)
                        else:
                            send_keys_command = f"tmux send-keys -t {session_name} Enter"
                            subprocess.run(send_keys_command, shell=True)
                if "[35mInput:[0m" in output:
                    input_to_send = generate_subroutine_input(subroutine_queue, subroutine_chat_data, subroutine_log,
                                                              jarvis_stop_event=jarvis_stop_event,
                                                              jarvis_skip_event=jarvis_skip_event)
                    print(f"Input to send: {input_to_send}")
                    send_keys_command = f"tmux send-keys -t {session_name} '{input_to_send}' Enter"
                    subprocess.run(send_keys_command, shell=True)
                    if input_to_send == "n" or input_to_send == "N":
                        stop_subroutine_process()
                        break
                if jarvis_stop_event.is_set():
                    break
    finally:
        if not just_stop:
            # Clean up the temporary file and stop the tmux pipe-pane command
            stop_redirect_output_command = f"tmux pipe-pane -t {session_name}"
            subprocess.run(stop_redirect_output_command, shell=True)


def generate_subroutine_input(subroutine_queue, subroutine_chat_data, sub_log, jarvis_stop_event: multiprocessing.Event,
                              jarvis_skip_event: multiprocessing.Event):
    history = get_assistant_history()
    with open(subroutine_chat_data, 'r') as file:
        subroutine_system_data = json.load(file)
        system_message = subroutine_system_data.get("system_message")
        notifications = subroutine_system_data.get("notifications", [])
    system_tokens = history.count_tokens_text(system_message["content"])
    system_tokens += history.count_tokens_text(" ".join(notifications))
    model_info = get_model()
    total_tokens = model_info['max_history']-800
    with open(sub_log, 'r') as f:
        log_text = f.read()
    log_text = ansi_escape.sub('', log_text)
    available_tokens = total_tokens - (system_tokens + 200)
    half_tokens = int(available_tokens // 2)
    enc = encoding_for_model("gpt-3.5-turbo")
    tokens = enc.encode(log_text)
    if len(tokens) > half_tokens:
        tokens = tokens[:half_tokens]
        log_text = enc.decode(tokens)

    occurrences = [match.start() for match in re.finditer('SYSTEM', log_text)]
    # Find the starting index of the second to last occurrence of 'world'
    if len(occurrences) < 2:
        second_to_last_index = 0
    else:
        second_to_last_index = occurrences[-2]

    # Get the substring starting from the second to last occurrence of 'world'
    if second_to_last_index == 0:
        query_log_text = log_text
    else:
        query_log_text = log_text[second_to_last_index:]

    question = f"\n\n Given this log produce one of your standard outputs ('y', 'input:', 'confirmation:', " \
               f"'question:', 'notification:', or 'n')\n"
    if len(notifications) > 0:
        notifications_str = ""
        for notification in notifications[-4:]:
            notifications_str += f"\n- {notification}"
        question = f"\n Previous notifications (NOTE: Do not send a notification if it is at all similar " \
                   f"to any previous notification also check the current time and make sure to rarely" \
                   f" notify multiple times within 10 minutes)" \
                   f": {notifications_str}" + question
    else:
        notifications_str = ""

    input_history = [system_message] + history.gather_context(
        query_log_text, minimum_recent_history_length=0, max_tokens=half_tokens) + [{"role": "assistant",
                                                                                     "content": log_text + question}]

    def generate_response_with_backoff(input_history, retries=5, backoff_factor=3000):
        for i in range(retries):
            try:
                output, reason = generate_simple_response(input_history)
                return output, reason
            except openai.error.InvalidRequestError:
                if i == retries - 1:
                    raise
                else:
                    # exponential backoff
                    sleep_time = (backoff_factor * (i+1)) ** 0.68
                    time.sleep(sleep_time)

    output, reason = generate_response_with_backoff(input_history)

    input_to_send_to_subroutine = ''
    print("Output ----> ", output)
    time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    if "SYSTEM" in output or "THOUGHTS" in output or "REASONING" in output or "PLAN" in output or "CRITICISM" in output:
        notification_to_user(subroutine_queue, "I'm so sorry but I got confused running the subroutine. Can you help?",
                             jarvis_stop_event=jarvis_stop_event,
                             jarvis_skip_event=jarvis_skip_event)
        open_subroutine_process()
    if output == "y":
        input_to_send_to_subroutine = "y"
    if output == "n":
        input_to_send_to_subroutine = "n"
    if output.startswith("input:"):
        input_to_send_to_subroutine = output[6:].strip()
    if output.startswith("confirmation:"):
        input_to_send_to_subroutine = confirm_with_user(subroutine_queue, output[13:].strip(),
                                                        jarvis_stop_event=jarvis_stop_event,
                                                        jarvis_skip_event=jarvis_skip_event)
    if output.startswith("question:"):
        input_to_send_to_subroutine = ask_user(subroutine_queue, output[9:].strip(),
                                               query_log_text,
                                               jarvis_stop_event=jarvis_stop_event,
                                               jarvis_skip_event=jarvis_skip_event)
    if output.startswith("notification:"):
        new_notification = time_str + " " + output.strip()
        prompt = f'The previous notifications were:\n{notifications_str}\nThe new notification ' \
                 f'is:\n- {new_notification}\n\nOn a scale of 1-5, with 1 being very similar and 5 being very ' \
                 f'different, how different is the new notification from the previous notifications ' \
                 f'(respond with only a single number): '
        response = openai.Completion.create(
            engine=base_model,
            prompt=prompt,
            max_tokens=2,
            n=1,
            stop=None,
            temperature=0.8,
            api_key=api_key,
        )
        difference_raw = response.choices[0].text
        if difference_raw.strip().isdigit():
            difference = int(difference_raw.strip())
        else:
            difference = 1
        if difference > 3:
            notifications.append(new_notification)
            with open(subroutine_chat_data, 'w') as file:
                subroutine_system_data['notifications'] = notifications
                json.dump(subroutine_system_data, file)
            notification_to_user(subroutine_queue, output[13:].strip(),
                                 jarvis_stop_event=jarvis_stop_event,
                                 jarvis_skip_event=jarvis_skip_event)
        else:
            print("Notification too similar to previous notifications:", new_notification)
        input_to_send_to_subroutine = "y"
    return re.sub("\n", " ", input_to_send_to_subroutine.strip()).strip()


def confirm_with_user(subroutine_queue, output, jarvis_stop_event: multiprocessing.Event,
                      jarvis_skip_event: multiprocessing.Event):
    subroutine_queue.put("pause")
    time.sleep(6)
    message = subroutine_queue.get(timeout=60 * 4)
    if message is None:
        subroutine_queue.put("resume")
        return "n"
    if message != "go":
        subroutine_queue.put("resume")
        return "n"
    play_audio_file(text_to_speech(output))
    response_text = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                      jarvis_skip_event=jarvis_skip_event)
    prompt = f'The question "{output}" was posed to the user. The users ' \
             f'response to the question was: "{response_text}". Would you categorize this response as ' \
             f'"yes", "no", "unclear" (please respond with one of those three options): '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    answer = response.choices[0].text
    if answer != 'yes':
        subroutine_queue.put("resume")
        return "n"
    prompt = f'Example Question: The subroutine wants your address and I know your address, should I input the ' \
             f'following: 123 Example St. Example City, Example State, 12345?\n' \
             f'Example Answer: 123 Example St. Example City, Example State, 12345\n' \
             f'Example Question: The subroutine wants access to the file system, should I give it access?\n' \
             f'Example Answer: y\n' \
             f'The user answered the following question in the affirmative "{output}"? If the proposed input based on '\
             f'this question is simply to allow the subroutine to perform the requested action return with only "y", ' \
             f'otherwise return the proposed input\n' \
             f'Question: {output}\nAnswer: '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    subroutine_queue.put("resume")
    if jarvis_stop_event.is_set():
        return ""
    return response.choices[0].text


def ask_user(subroutine_queue, output, query_log_text, jarvis_stop_event: multiprocessing.Event,
             jarvis_skip_event: multiprocessing.Event):
    subroutine_queue.put("pause")
    time.sleep(6)
    message = subroutine_queue.get(timeout=60*4)
    if message is None:
        subroutine_queue.put("resume")
        return "n"
    if message != "go":
        subroutine_queue.put("resume")
        return "n"
    play_audio_file(text_to_speech(output), added_stop_event=jarvis_stop_event)
    response_text = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                      jarvis_skip_event=jarvis_skip_event)
    prompt = f'Example Question: The subroutine wants your address. Should I provide it? What is it?\n' \
             f'Example Answer: Yes my address is 123 Example St. Example City, Example State, 12345\n' \
             f'Example Input: 123 Example St. Example City, Example State, 12345\n\n' \
             f'Example Question: The subroutine wants access to the file system, should I give it access?\n' \
             f'Example Answer: Yes that should be fine\n' \
             f'Example Input: y\n' \
             f'If the proposed input based on this question is simply to allow the subroutine to perform the ' \
             f'requested action return with only "y", otherwise return the proposed input\n' \
             f'Question: {output}\n' \
             f'Answer: {response_text}\nInput: '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    subroutine_queue.put("resume")
    if jarvis_stop_event.is_set():
        return ""
    return response.choices[0].text


def notification_to_user(subroutine_queue, output, jarvis_stop_event: multiprocessing.Event,
                         jarvis_skip_event: multiprocessing.Event):
    subroutine_queue.put("pause")
    time.sleep(6)
    message = subroutine_queue.get(timeout=60 * 4)
    if message is None:
        subroutine_queue.put("resume")
        return "n"
    if message != "go":
        subroutine_queue.put("resume")
        return "n"
    play_audio_file(text_to_speech("There is a notification for you from the subroutine. "+output),
                    added_stop_event=jarvis_stop_event)
    subroutine_queue.put("resume")
    return 'y'


def check_subroutine_progress(subroutine_queue, command_string, sub_log, jarvis_stop_event: multiprocessing.Event,
                              jarvis_skip_event: multiprocessing.Event, silent=False):
    if not silent:
        subroutine_queue.put("pause")
        time.sleep(6)
        message = subroutine_queue.get(timeout=60 * 4)
        if message is None:
            subroutine_queue.put("resume")
            return "n"
        if message != "go":
            subroutine_queue.put("resume")
            return "n"
    history = get_assistant_history()
    model_info = get_model()
    total_tokens = model_info['max_history']
    with open(sub_log, 'r') as f:
        log_text = f.read()
    log_text = ansi_escape.sub('', log_text)
    log_tokens = history.count_tokens_text(log_text)
    command_string += "\n\n Subroutine History:\n"
    command_string_tokens = history.count_tokens_text(command_string)
    system_message = history.get_system()
    system_tokens = history.count_tokens_text(system_message["content"])
    current_tokens = system_tokens + command_string_tokens + log_tokens
    enc = encoding_for_model("gpt-3.5-turbo")
    tokens = enc.encode(log_text)
    if current_tokens > total_tokens:
        tokens = tokens[:-(current_tokens+100 - total_tokens)]
        log_text = enc.decode(tokens)
    preamble = "The following is data about the current state of the subroutine that needs to be summarized...\n\n"
    postamble = "\n\n How would you summarize the current state of the subroutine? " \
                "Is it making progress? Is it going well? Be specific and read carefully."
    input_history = [system_message] + [{"role": "assistant",
                                        "content": preamble + command_string + log_text + postamble}]
    if jarvis_stop_event.is_set():
        subroutine_queue.put("resume")
    if silent:
        def generate_response_with_backoff(input_history, retries=5, backoff_factor=3000):
            for i in range(retries):
                try:
                    output, reason = generate_simple_response(input_history)
                    return output, reason
                except openai.error.InvalidRequestError:
                    if i == retries - 1:
                        raise
                    else:
                        # exponential backoff
                        sleep_time = (backoff_factor * (i + 1)) ** 0.68
                        time.sleep(sleep_time)
    else:
        try:
            output, reason = generate_simple_response(input_history)
        except openai.error.InvalidRequestError:
            play_audio_file(text_to_speech("I am so sorry but Open AI is overloaded "
                                           "right now so try again in a few minutes"), added_stop_event=jarvis_stop_event)
            subroutine_queue.put("resume")
            return
    time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I_%M %p")
    if not os.path.exists(subroutine_checks):
        os.mkdir(subroutine_checks)
    with open(os.path.join(subroutine_checks,f"Jarvis Subroutine Check at {time_str}.txt"), 'w') as f:
        f.write(output)
    if not silent:
        play_audio_file(text_to_speech(output), added_stop_event=jarvis_stop_event)
    subroutine_queue.put("resume")


def open_subroutine_process():
    global session_name
    global shell_profile
    attach_command = f'tmux attach-session -t {session_name}'
    scroll_command = 'tmux setw -g mouse on'
    open_terminal_command = f"""source {shell_profile} && osascript -e 'tell application "Terminal" to do script"""\
                            f""" "{scroll_command} ; {attach_command}"' -e 'tell application "Terminal" to activate'"""
    subprocess.Popen(open_terminal_command, shell=True)


def kill_subroutine_process():
    global session_name
    global shell_profile
    open_terminal_command = f"""source {shell_profile} && tmux kill-session -t {session_name}"""
    subprocess.Popen(open_terminal_command, shell=True)


def stop_subroutine_process():
    global session_name
    global shell_profile
    intput_to_send = "\x03"
    send_keys_command = f"tmux send-keys -t {session_name} '{intput_to_send}'"
    subprocess.run(send_keys_command, shell=True)


def is_there_a_stored_subroutine():
    if not os.path.exists(subroutine_log) or not os.path.exists(subroutine_chat_data):
        return False
    return True


def save_subroutine_files(path, cut_files=False):
    with open(subroutine_chat_data, 'r') as f:
        chat_data = json.load(f)
    with open(subroutine_chat_data, 'w') as f:
        json.dump(chat_data, f, indent=4)
    folder_name = "Jarvis Subroutine "+chat_data['subroutine_info']['subroutine_name'].strip().replace("\n", " ")
    folder_path = os.path.join(path, folder_name)
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
    workspace_path = os.path.join(path_to_subroutine, "auto_gpt_workspace")
    for file in os.listdir(workspace_path):
        shutil.copy(os.path.join(workspace_path, file), folder_path)
    shutil.copy2(subroutine_chat_data, folder_path)
    shutil.copy2(subroutine_log, folder_path)
    for file in os.listdir(subroutine_checks):
        shutil.copy2(os.path.join(subroutine_checks, file), folder_path)
    if cut_files:
        shutil.rmtree(workspace_path)
        os.mkdir(workspace_path)
        os.remove(subroutine_chat_data)
        os.remove(subroutine_log)
        shutil.rmtree(subroutine_checks)
        os.mkdir(subroutine_checks)


def get_user_response(timeout=60, jarvis_stop_event=multiprocessing.Event(), jarvis_skip_event=multiprocessing.Event()):
    """
    Get user response to a question

    :param timeout: int, number of seconds to wait for user response
    :param jarvis_stop_event: multiprocessing.Event, event to stop audio streaming
    :param jarvis_skip_event: multiprocessing.Event, event to skip audio streaming
    :return: str, the user response
    """
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
    except Exception as e:
        free_wake = True
        from pocketsphinx import LiveSpeech

        def pocketsphinx_wake_word_detection(wake_word, stop_event, timeout):
            """
            Detects wake word using pocketsphinx.
            :param wake_word:
            :param stop_event:
            :return:
            """
            start = time.time()
            speech = LiveSpeech()
            for phrase in speech:
                if time.time() - start > timeout:
                    return False
                if str(phrase).lower() == wake_word.lower():
                    return True
                if stop_event.is_set():
                    break
            return False

    if not free_wake:
        # create pocketsphinx thread
        start_audio_stream(handle.sample_rate, handle.frame_length)
    logger.info("Subroutine listening for wake word...")
    detected = False
    start = time.time()
    while not jarvis_stop_event.is_set() and time.time() - start < timeout:
        # Clear skip event if set
        if jarvis_skip_event.is_set():
            jarvis_skip_event.clear()

        # Detect wake word
        if free_wake:
            result = pocketsphinx_wake_word_detection("Jarvis", jarvis_stop_event, timeout)
            if result is False:
                return None
            else:
                detected = True
        if not free_wake:
            pcm = get_next_audio_frame(handle)
            if pcm is not None:
                keyword_index = handle.process(pcm)
            if keyword_index >= 0:
                detected = True
        # Process user input if wake word detected
        if detected:
            detected = False
            stop_audio_stream()
            if jarvis_skip_event.is_set() or jarvis_stop_event.is_set():
                play_audio_file(text_to_speech("Canceling request."))
                return None
            # Listen to user query
            logger.info("Subroutine listening...")
            query_audio = listen_to_user()
            if jarvis_skip_event.is_set() or jarvis_stop_event.is_set():
                play_audio_file(text_to_speech("Canceling request."))
                return None
            query = convert_to_text(query_audio)
            if jarvis_skip_event.is_set() or jarvis_stop_event.is_set():
                play_audio_file(text_to_speech("Canceling request."))
                return None
            return query

    # Cleanup
    if not free_wake:
        atexit.unregister(handle.delete)
        handle.delete()
    logger.info("Subroutine question timeout.")
    return None


def get_user_preferences_for_new_subroutine(jarvis_stop_event=multiprocessing.Event(),
                              jarvis_skip_event=multiprocessing.Event()):
    play_audio_file(text_to_speech("Ok what do you want the name of the subroutine to be?"))
    subroutine_name = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                        jarvis_skip_event=jarvis_skip_event)
    if subroutine_name is None or jarvis_stop_event.is_set():
        return None
    prompt = f'Return the title that the user wanted to give the subroutine based on the following response' \
             f' "{subroutine_name}" (remember if the whole thing looks like a name return the whole response): '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    subroutine_name = response.choices[0].text.strip()
    logger.info("Subroutine name: " + subroutine_name)
    play_audio_file(text_to_speech(f"Ok, what do you want the role of '{subroutine_name}' to be?"))
    subroutine_role = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                        jarvis_skip_event=jarvis_skip_event)
    if subroutine_role is None or jarvis_stop_event.is_set():
        return None
    prompt = f'Return the role that the user wanted to give the subroutine based on the following response' \
             f' "{subroutine_role}" (if need be reiterate it in your own words for clarity and specificity ' \
             f'but do not start with any preamble like "The role of the subroutine..." just state the role): '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=1000,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    subroutine_role = response.choices[0].text.strip()
    logger.info("Subroutine role: " + subroutine_role)
    play_audio_file(text_to_speech(f'Since you want the subroutine to "{subroutine_role}", what goals do you want '
                                   f'it to have?'))
    subroutine_goals = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                         jarvis_skip_event=jarvis_skip_event)
    if subroutine_goals is None or jarvis_stop_event.is_set():
        return None
    prompt = f'Return the goals that the user wanted to give the subroutine based on the following response' \
             f' "{subroutine_goals}" Break these goals into 1-5 top level goals and return each goal numbered' \
             f' clearly (never greater than 5 goals, combine them if need be, do not have a sixth goal, no goal 6): '
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=1000,
        n=1,
        stop=None,
        temperature=0.8,
        api_key=api_key,
    )
    subroutine_goals = response.choices[0].text.strip()
    logger.info("Subroutine goals: " + subroutine_goals)
    play_audio_file(text_to_speech(f'The goals of the {subroutine_name} subroutine '
                                   f'will be to "{subroutine_goals}".'))

    text = subroutine_goals.replace('\n', ' ')
    text = re.sub(r'(\d+\.)', r'@@@', text)
    tasks = text.split('@@@')[1:]
    subroutine_goals = []
    for s in tasks:
        subroutine_goals.append(s.strip())
    play_audio_file(text_to_speech("Do you want me to follow any specific rules when monitoring this subroutine?"))
    subroutine_rules = get_user_response(timeout=60, jarvis_stop_event=jarvis_stop_event,
                                         jarvis_skip_event=jarvis_skip_event)
    if subroutine_rules is None or jarvis_stop_event.is_set():
        return None
    input_commands = {"subroutine_name": subroutine_name, "subroutine_role": subroutine_role,
                      "subroutine_goals": subroutine_goals, "subroutine_rules": subroutine_rules}
    print(input_commands)
    return input_commands