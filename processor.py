import re
import json
import html
import logging
from mailjet_rest import Client
from connections import get_mj_key, get_mj_secret, get_emails, \
    ConnectionKeyError, get_user
from gpt_interface import generate_response, get_last_response, \
    stream_response, resolve_stream_response, get_model, generate_simple_response, get_assistant_history
from streaming_response_audio import stream_audio_response, set_rt_text_queue
from internet_helper import create_internet_context
from text_speech import text_to_speech
from audio_player import play_audio_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    free = False
    mj_key = get_mj_key()
    mj_secret = get_mj_secret()
except ConnectionKeyError:
    free = True
    import os
    import sys
    import uuid
    import subprocess
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.headerregistry import Address
    user_name = get_user()

set_text_queue = False


def clean_up_query(raw_query):
    """
    Clean up the query string by removing extra characters before the actual query.

    :param raw_query: str, the raw query string
    :return: str, cleaned-up query string
    :rtype: str
    """
    raw_query = raw_query[raw_query[:50].lower().find("the following") + 13:]
    return re.sub("^[^a-z|A-Z]+", "", raw_query)


def clean_up_reminder(raw_query):
    """
    Clean up the reminder string by removing extra characters before the actual reminder.

    :param raw_query: str, the raw reminder string
    :return: str, cleaned-up reminder string
    :rtype: str
    """
    raw_query = raw_query[raw_query[:50].lower().find("reminder") + 8:]
    query = re.sub("^[^a-z|A-Z]+", "", raw_query)
    reg = clean_up_query(raw_query)
    if len(reg) < len(query):
        return reg
    return query


def clean_up_search_smart(raw_query):
    """
    Clean up the search smart query string by removing extra characters before the actual query.

    :param raw_query: the raw query string
    :type raw_query: str
    :return: cleaned-up query string
    :rtype: str
    """
    output, reason = generate_simple_response([{"role": "system", "content": f'Return ONLY the part of this query that '
                                                                             f'is the query and omit the part of this '
                                                                             f'query that requests any kind of search '
                                                                             f'(Do not surround the response in '
                                                                             f'quotes): "{raw_query}"'}])
    if reason == "stop":
        return output
    logger.warning("Could not clean up search smart query! got back:"+output)
    return ""


def remove_code_blocks(text):
    """
    Remove code blocks from the text string.

    :param text: str, the text containing code blocks
    :return: str, text with code blocks removed
    """
    return re.sub("`|\\(\\)", "",
                  re.sub("```[^```]+```", "(FYI I had some code here that I am not reading to save time)", text))


def internet_words_in(raw_query):
    """
    Check if the raw query contains any words related to the internet.

    :param raw_query: str, the raw query string
    :return: bool, True if the query contains internet words, False otherwise
    """
    internet_words = ["internet", "google", "search", "lookup", "look up", "website", "web"]
    for word in internet_words:
        if len(re.findall("^"+word+"| "+word, raw_query)) > 0:
            return True
    return False


def last_response_words_in(raw_query):
    """
    Check if the raw query contains any words related to the last response.

    :param raw_query: str, the raw query string
    :return: bool, True if the query contains last response words, False otherwise
    """
    last_response_words = ["response", "thing", "question", "message", "answer", "reply", "result", "output"]
    for word in last_response_words:
        if len(re.findall("^"+word+"| "+word, raw_query)) > 0:
            return True
    return False


def get_model_name():
    """
    Gets model name
    :return: str, name of model
    """
    return get_model()['name']


def processor(raw_query, stop_audio_event, skip=None, text_queue=None):
    """
    Process the raw query and determine the appropriate action.

    :param raw_query: str, the raw query string
    :param stop_audio_event: threading.Event, event to stop audio streaming
    :param skip: threading.Event, event to skip audio streaming
    :param text_queue: queue.Queue, queue to put text to be spoken
    :return: str, the result of processing the query
    """
    global set_text_queue
    if not set_text_queue:
        set_text_queue = True
        set_rt_text_queue(text_queue)

    test_str = raw_query[:50].lower()
    # Handle emailing last response
    if test_str.find("last") >= 0 and last_response_words_in(test_str) and test_str.find("email") >= 0:
        query, result = get_last_response()
        return email_processor("Jarvis responding to question: "+query['content'][:150]+"...", result['content'])

    # Handle email queries
    if test_str.find("the following") >= 0:
        # Handle emailing
        if test_str.find("email") >= 0:
            # Handle emailing a reminder
            if test_str.find("reminder") >= 0:
                reminder = clean_up_reminder(raw_query)
                if not re.search('[a-zA-Z]', reminder):
                    return "I'm so sorry I didn't catch that. I think I cut you off."
                file = text_to_speech("Emailing you the following reminder: " + reminder)
                stop_audio_event.set()
                play_audio_file(file, blocking=True, destroy=True, added_stop_event=skip)
                if skip.is_set():
                    return "Sorry."
                output = email_processor("Jarvis reminder: " + reminder[:200]+"...", reminder)
                if skip.is_set():
                    return "Sorry."
                file = text_to_speech(output, model=get_model()['name'])
                if skip.is_set():
                    return "Sorry."
                play_audio_file(file, blocking=True, destroy=True, added_stop_event=skip)
                if skip.is_set():
                    return "Sorry."
                return output
            # Handle emailing an internet query
            if internet_words_in(test_str):
                query = clean_up_query(raw_query)
                if not re.search('[a-zA-Z]', query):
                    return "I'm so sorry I didn't catch that. I think I cut you off."
                file = text_to_speech('Searching the internet for your query, "' + query +
                                      '". I will let you know when I am done working on that email.')
                stop_audio_event.set()
                play_audio_file(file, blocking=False, destroy=True, added_stop_event=skip)
                if skip.is_set():
                    return "Sorry."
                response, data = internet_processor(query, stream=False, skip=skip)
                if skip.is_set():
                    return "Sorry."
                output = email_processor("Jarvis searched for: " + query, response + "\n\n```" +
                                         json.dumps(data, indent=5) + "```")
                if skip.is_set():
                    return "Sorry."
                file = text_to_speech(output, model=get_model()['name'])
                if skip.is_set():
                    return "Sorry."
                play_audio_file(file, blocking=True, destroy=True, added_stop_event=skip)
                if skip.is_set():
                    return "Sorry."
                return output
            # Handle emailing a response to a question
            else:
                query = clean_up_query(raw_query)
                if not re.search('[a-zA-Z]', query):
                    return "I'm so sorry I didn't catch that. I think I cut you off."
                file = text_to_speech("Emailing you my response to: " + query)
                stop_audio_event.set()
                play_audio_file(file, blocking=False, destroy=True, added_stop_event=skip)
                if skip.is_set():
                    return "Sorry."
                output = email_processor("Jarvis responding to question: " + query, generate_response(query))
                if skip.is_set():
                    return "Sorry."
                file = text_to_speech(output, model=get_model()['name'])
                if skip.is_set():
                    return "Sorry."
                play_audio_file(file, blocking=True, destroy=True, added_stop_event=skip)
                if skip.is_set():
                    return "Sorry."
                return output
        elif internet_words_in(test_str):
            query = clean_up_query(raw_query)
            if not re.search('[a-zA-Z]', query):
                return "I'm so sorry I didn't catch that. I think I cut you off."
            file = text_to_speech('Searching the internet for your query, "' + query + '". This may take some time.')
            stop_audio_event.set()
            if skip.is_set():
                return "Sorry."
            stop_flag = play_audio_file([file, "audio_files/searching.wav"], loops=[1, 7],
                                        blocking=False, destroy=[True, False], added_stop_event=skip)
            if skip.is_set():
                return "Sorry."
            response, data = internet_processor(query, stop_audio_event=stop_flag, skip=skip)
            if skip.is_set():
                return "Sorry."
            return response

    # Handle internet queries
    if internet_words_in(test_str):
        query = clean_up_search_smart(raw_query)
        if not re.search('[a-zA-Z]', query):
            return "I'm so sorry I didn't catch that. I think I cut you off."
        if skip.is_set():
            return "Sorry."
        file = text_to_speech('Searching the internet for your query, "'+query+'". This may take some time.')
        stop_audio_event.set()
        if skip.is_set():
            return "Sorry."
        stop_flag = play_audio_file([file, "audio_files/searching.wav"], loops=[1, 7],
                                    blocking=False, destroy=[True, False], added_stop_event=skip)
        if skip.is_set():
            return "Sorry."
        response, data = internet_processor(query, stop_audio_event=stop_flag, skip=skip)
        if skip.is_set():
            return "Sorry."
        return response

    if not re.search('[a-zA-Z]', raw_query):
        return "I'm so sorry I didn't catch that. I think I cut you off."
    return resolve_stream_response(*stream_audio_response(stream_response(raw_query),
                                   stop_audio_event=stop_audio_event, skip=skip), get_model()["name"])


def convert_to_pretty_html(text):
    """
    Convert a plain text string to a formatted HTML string.

    :param text: str, the plain text string
    :return: str, the formatted HTML string
    """

    def escape_html(text_str):
        """
        Escape special characters in the text string for use in HTML.

        :param text_str: str, the text string
        :return: str, the escaped text string
        """
        return html.escape(text_str)

    def wrap_with_tag(text_str, tag):
        """
        Wrap a text string with an HTML tag.

        :param text_str: str, the text string
        :param tag: str, the HTML tag
        :return: str, the wrapped text string
        """
        return f"<{tag}>{text_str}</{tag}>"

    # Split the text into lines
    lines = text.split("\n")

    # Create an empty list to store the formatted lines
    formatted_lines = []

    # Iterate through the lines
    for line in lines:
        # Check for code blocks
        if line.startswith("```"):
            # Remove the backticks
            line = line.replace("```", "")

            # Check if the line is empty, which means it's the end of the code block
            if not line.strip():
                formatted_lines.append("</pre></code>")
            else:
                formatted_lines.append(f"<code><pre>{escape_html(line)}")
        else:
            # Escape special characters and wrap the line with <p> tags
            line = wrap_with_tag(escape_html(line), "p")

            # Replace tabs with the corresponding HTML entity
            line = line.replace("\t", "&emsp;")

            # Add the formatted line to the list
            formatted_lines.append(line)

    # Join the lines and return the result
    pretty_html = "\n".join(formatted_lines)

    # Add CSS styles to customize the appearance of the text and code blocks
    styles = """
        <style>
            body {
                font-family: Arial, sans-serif;
            }
            code {
                display: block;
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-family: "Courier New", monospace;
                white-space: pre-wrap;
            }
        </style>
        """

    # Combine the styles with the formatted HTML content
    return f"{styles}\n{pretty_html}"


def email_processor(subject, text):
    """
    Send an email containing the specified subject and text.

    :param subject: str, the subject of the email
    :param text: str, the content of the email
    :return: str, the result of sending the email
    """
    text = convert_to_pretty_html(text)
    if free:
        return free_email_processor(subject, text, get_emails())
    mailjet = Client(auth=(mj_key, mj_secret), version='v3.1')
    emails = list(set(get_emails()))
    email_list_list = [emails]
    for emails in email_list_list:
        logger.info(f"SENDING TO {str(emails)}")
        email_list = []
        for email in emails:
            email_list.append({"Email": email})
        data = {
            'Messages': [
                {
                    "From": {
                        "Email": "jarvis@eliaswestonfarber.com",
                        "Name": "Jarvis"
                    },
                    "To": email_list,
                    "Subject": subject,
                    "TextPart": text,
                    "HTMLPart": text,
                    "CustomID": "Jarvis Response"
                }
            ]
        }

        result = mailjet.send.create(data=data)
        if result.status_code != 200:
            return "I am so sorry but I was unable to send you that email."
    return "Sent!"


def test_email(email):
    """
    Send a test email to the specified email address.

    :param email: str, the email address to send the test email to
    :return: str, the result of sending the test email
    """
    api_key = get_mj_key()
    api_secret = get_mj_secret()
    mailjet = Client(auth=(api_key, api_secret), version='v3.1')
    emails = list({email})
    email_list_list = [emails]
    for emails in email_list_list:
        logger.info(f"SENDING TO {str(emails)}")
        email_list = []
        for email in emails:
            email_list.append({"Email": email})
        data = {
            'Messages': [
                {
                    "From": {
                        "Email": "jarvis@eliaswestonfarber.com",
                        "Name": "Jarvis"
                    },
                    "To": email_list,
                    "Subject": "Testing",
                    "TextPart": "Test",
                    "HTMLPart": "Test",
                    "CustomID": "Jarvis Response"
                }
            ]
        }

        result = mailjet.send.create(data=data)
        if result.status_code != 200:
            return "I am so sorry but I was unable to send you that email."
    return "Sent!"


def internet_processor(raw_query, stop_audio_event=None, stream=True, skip=None):
    """
    Process an internet search query.

    :param raw_query: str, the raw query string
    :param stop_audio_event: threading.Event, the event to set when the audio should stop playing
    :param stream: bool, whether to stream the response audio
    :param skip: threading.Event, the event to set when the audio should skip this response
    :return: str, the result of processing the internet search query
    """
    context, data = create_internet_context(raw_query, result_number=5, skip=skip)
    if skip:
        if skip.is_set():
            return "Sorry.", None
    if stream:
        return resolve_stream_response(*stream_audio_response(
            stream_response(context, query_history_role="assistant", query_role="system"),
            stop_audio_event=stop_audio_event,
            skip=skip), get_model()['name']), data
    else:
        return generate_response(context, query_history_role="assistant", query_role="system"), data


def free_email_processor(subject, text, recipients):
    """
    Create an email draft containing the specified subject and text.

    :param subject: str, the subject of the email
    :param text: str, the content of the email
    :param recipients: list, a list of recipient email addresses
    :return: str, the result of creating the email draft
    """
    from_email = Address(recipients[0], user_name)
    to_emails = [Address(email) for email in recipients]

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = str(from_email)
    msg['To'] = ', '.join(str(addr) for addr in to_emails)

    text_part = MIMEText(text, 'html')
    msg.attach(text_part)
    email_folder = "email_drafts/"
    if getattr(sys, 'frozen', False):
        email_folder = os.path.join(sys._MEIPASS, email_folder)
    eml_filename = email_folder+str(uuid.uuid4())+'email_draft.eml'
    with open(eml_filename, 'w', encoding='utf-8') as eml_file:
        eml_file.write(msg.as_string())

    try:
        if sys.platform == 'win32':
            os.startfile(eml_filename)
        elif sys.platform == 'darwin':
            subprocess.run(['open', eml_filename])
        elif sys.platform.startswith('linux'):
            subprocess.run(['xdg-open', eml_filename])
        else:
            raise NotImplementedError("Unsupported platform")

        return "Email draft created and opened!"
    except Exception as e:
        return f"I am so sorry, but I was unable to create and open the email draft. Error: {e}"


def get_chat_history(id=None, limit=10, reload_disk=False):
    """
    Get the chat history for the specified user ID.

    :param id: str, the user ID to get the chat history for
    :param limit: int, the maximum number of chat history entries to return
    :param reload_disk: bool, whether to reload the chat history from disk
    :return: list, a list of chat history entries
    """
    output = get_assistant_history().get_history_from_id_and_earlier(id=id, n_results=limit, reload_disk=reload_disk)
    return output
