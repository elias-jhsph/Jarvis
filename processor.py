import re
import json
import html
import logging
from mailjet_rest import Client
from connections import get_mj_key, get_mj_secret, get_emails
from gpt_interface import generate_response, get_last_response, stream_response, resolve_stream_response
from streaming_response_audio import stream_audio_response
from internet_helper import create_internet_context
from text_speech import text_to_speech

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_up_query(raw_query):
    """
    Clean up the query string by removing extra characters before the actual query.

    :param raw_query: str, the raw query string
    :return: str, cleaned-up query string
    """
    raw_query = raw_query[raw_query[:50].lower().find("the following") + 13:]
    return re.sub("^[^a-z|A-Z]+", "", raw_query)


def clean_up_reminder(raw_query):
    """
    Clean up the reminder string by removing extra characters before the actual reminder.

    :param raw_query: str, the raw reminder string
    :return: str, cleaned-up reminder string
    """
    raw_query = raw_query[raw_query[:50].lower().find("following reminder") + 18:]
    return re.sub("^[^a-z|A-Z]+", "", raw_query)


def remove_code_blocks(text):
    """
    Remove code blocks from the text string.

    :param text: str, the text containing code blocks
    :return: str, text with code blocks removed
    """
    return re.sub("`|\\(\\)", "",
                  re.sub("```[^```]+```", "(FYI I had some code here that I am not reading to save time)", text))


def processor(raw_query, return_audio_file=False, stop_audio_event=None):
    """
    Process the raw query and determine the appropriate action.

    :param return_audio_file: bool, whether to see if there is some temp audio to play
    :param raw_query: str, the raw query string
    :param stop_audio_event: threading.Event, event to stop audio streaming
    :return: str, the result of processing the query
    """
    # Handle email-related queries
    if (raw_query[:50].lower().find("last response") >= 0 or
        raw_query[:50].lower().find("last thing") >= 0 or
        raw_query[:50].lower().find("last question") >= 0 or
        raw_query[:50].lower().find("last message") >= 0)\
            and raw_query[:50].lower().find("email") >= 0:
        query, result = get_last_response()
        if return_audio_file:
            return None, False
        return email_processor("Jarvis responding to question: "+query, result)

    email_internet_search_texts = ["email me the following internet search",
                                   "send me the following internet search",
                                   "email me an internet search for the following",
                                   "email me a web search for the following",
                                   "email me a search for the following",
                                   "email me an internet search for",
                                   "email me a web search for",
                                   "email me a search for",
                                   ]
    wants_email_internet = None
    for test in email_internet_search_texts:
        if raw_query[:50].lower().find(test) >= 0:
            wants_email_internet = test
            break
    if wants_email_internet:
        raw_query = raw_query[raw_query[:50].lower().find(test) + len(test):]
        query = re.sub("^[^a-z|A-Z]+", "", raw_query)
        if return_audio_file:
            return text_to_speech('Searching the internet for your query, "'+query+'". This may take some time.'), False
        response, data = internet_processor(query)
        return email_processor("Jarvis searched for: " + query, response + "\n\n```" +
                               json.dumps(data,indent=5) + "```"), False

    # Handle reminder-related queries
    if raw_query[:50].lower().find("following reminder") >= 0:
        reminder = clean_up_reminder(raw_query)
        if return_audio_file:
            return text_to_speech("Emailing you the following reminder: "+reminder), False
        return email_processor("Jarvis reminder: " + reminder, reminder), False

    # Handle other queries
    if raw_query[:50].lower().find("the following") >= 0:
        # Email-related queries
        if raw_query[:50].lower().find("email me the following") >= 0 or \
                raw_query[:50].lower().find("email the following") >= 0:
            query = clean_up_query(raw_query)
            if return_audio_file:
                return text_to_speech("Emailing you the answer to: "+query), False
            return email_processor("Jarvis responding to question: "+query, generate_response(query)), False

        # Internet search-related queries
        if raw_query[:50].lower().find("internet search me the following") >= 0 or \
            raw_query[:50].lower().find("internet search the following") >= 0 or \
                raw_query[:50].lower().find("internet search for the following") >= 0 or \
                raw_query[:50].lower().find("search the internet for the following") >= 0 or \
                raw_query[:50].lower().find("search the following") >= 0:
            query = clean_up_query(raw_query)
            if return_audio_file:
                return [text_to_speech('Searching the internet for your query, "'+query+'". This may take some time.'),
                        "audio_files/searching.wav"], True
            response, data = internet_processor(query, stop_audio_event=stop_audio_event), True
            return response
        if return_audio_file:
            return None
        return "I think I misheard you, try again."
    elif raw_query[:50].lower().find("internet search for") >= 0 or \
            raw_query[:50].lower().find("search the internet for") >= 0:
        raw_query = raw_query[raw_query[:25].lower().find(" for") + 13:]
        query = re.sub("^[^a-z|A-Z]+", "", raw_query)
        if return_audio_file:
            return [text_to_speech('Searching the internet for your query, "'+query+'". This may take some time.'),
                    "audio_files/searching.wav"], True
        response, data = internet_processor(query, stop_audio_event=stop_audio_event), True
        return response, True
    else:
        if return_audio_file:
            return None, True
        return resolve_stream_response(*stream_audio_response(stream_response(raw_query),
                                       stop_audio_event=stop_audio_event)), True


def convert_to_pretty_html(text):
    """
    Convert a plain text string to a formatted HTML string.

    :param text: str, the plain text string
    :return: str, the formatted HTML string
    """

    def escape_html(text):
        """
        Escape special characters in the text string for use in HTML.

        :param text: str, the text string
        :return: str, the escaped text string
        """
        return html.escape(text)

    def wrap_with_tag(text, tag):
        """
        Wrap a text string with an HTML tag.

        :param text: str, the text string
        :param tag: str, the HTML tag
        :return: str, the wrapped text string
        """
        return f"<{tag}>{text}</{tag}>"

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
    api_key = get_mj_key()
    api_secret = get_mj_secret()
    mailjet = Client(auth=(api_key, api_secret), version='v3.1')
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
    emails = list(set([email]))
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


def internet_processor(raw_query, stop_audio_event=None):
    """
    Process an internet search query.

    :param raw_query: str, the raw query string
    :param stop_audio_event: threading.Event, the event to set when the audio should stop playing
    :return: str, the result of processing the internet search query
    """
    context, data = create_internet_context(raw_query, result_number=5)
    return resolve_stream_response(*stream_audio_response(stream_response(context, query_history_role="assistant"),
                                                          stop_audio_event=stop_audio_event)), data

