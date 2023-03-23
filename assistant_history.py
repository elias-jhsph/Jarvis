import datetime
import json
import os
from collections import defaultdict
import openai
from connections import get_openai_key, get_user
import tiktoken
import spacy

# Set up logging
import logger_config
logger = logger_config.get_logger()

# Constants
user = get_user()
user_fix = user + "'" if user[-1] == "s" else user + "'s"
model = "gpt-3.5-turbo-0301"
temperature = 0.8
maximum_length_message = 500
maximum_length_history = 2700
top_p = 1
frequency_penalty = 0.19
presence_penalty = 0

nlp = spacy.load("en_core_web_sm")
openai.api_key = get_openai_key()
enc = tiktoken.encoding_for_model(model)


def get_time():
    """
    Get the current time as a string.

    :return: A string containing the current date and time.
    :rtype: str
    """
    return "On "+datetime.datetime.now().strftime("%A, %B %-d, %Y at %-I:%M %p")+": "


def summarizer(list_len_two):
    """
    Summarize a conversation by sending a query to the OpenAI API.

    :param tuple_text: A list of dictionaries containing the conversation to be summarized.
    :type tuple_text: list
    :return: A dictionary containing the role and content of the summarized conversation.
    :rtype: dict
    """
    query = [{"role": "user", "content": "Please summarize this conversation concisely (Do your best to respond only"
                                         " with your best attempt at a summary and leave out caveats, preambles, "
                                         "or next steps)"}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=list_len_two+query,
        temperature=temperature,
        max_tokens=maximum_length_message,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )
    output = response['choices'][0]['message']['content']
    return {"role": "system", "content": output}


def get_system():
    """
    Generate a system message containing user's AI Assistant's name and the current date time.

    :return: A dictionary containing the role and content of the system message.
    :rtype: dict
    """
    system = (f"You are {user_fix} AI Assistant named Jarvis. "
              "You are based on the character Jarvis from the Marvel Universe. "
              "The current date time is "
              + datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"))
    return {"role": "system", "content": system}


def extract_keywords(text):
    """
    Extract and store keywords from the given text.

    :param text: A string containing the text to extract keywords from.
    :type text: str
    :return:
    """
    output = []
    doc = nlp(text.lower())
    for token in doc:
        if token.is_alpha and not token.is_stop:
            output.append(token)
    return output


class AssistantHistory:
    """
    A class to manage the Assistant's conversation history, including storing, reducing,
    and gathering conversation context for future queries.

    :param max_tokens: The maximum number of tokens allowed for the conversation history.
    :type max_tokens: int
    """

    def __init__(self, max_tokens=maximum_length_history):
        self.max_tokens = max_tokens
        self.tokenizer = enc.encode
        self.history = []
        self.reduced_history = []
        self.keywords = defaultdict(list)
        self.current_user_query = None

    def count_tokens_text(self, text):
        """
        Count the number of tokens in the given text.

        :param text: A string containing the text to count tokens for.
        :type text: str
        :return: The number of tokens in the given text.
        :rtype: int
        """
        return len(self.tokenizer(text))

    def count_tokens_context(self, ls):
        """
        Count the total number of tokens in a list of conversation entries.

        :param ls: A list of conversation entries.
        :type ls: list
        :return: The total number of tokens in the given list of entries.
        :rtype: int
        """
        total = 0
        for el in ls:
            total += self.count_tokens_text(el['content'])
        return total

    def add_user_query(self, query):
        """
        Add a user query to the conversation history.

        :param query: The user query to be added.
        :type query: str
        """
        self.current_user_query = {"role": "user", "content": get_time() + query}

    def add_assistant_response(self, response):
        """
        Add an assistant response to the conversation history.

        :param response: The assistant response to be added.
        :type response: str
        """
        if self.current_user_query is None:
            raise ValueError("No user query found. Add a user query before adding an assistant response.")
        assistant_response = {"role": "assistant", "content": get_time() + response}
        self._update_keywords(response, self.current_user_query)
        self._update_keywords(response, assistant_response)
        self.history.append((self.current_user_query, assistant_response))
        self.current_user_query = None

    def reset_add(self):
        """
        Reset the current user query.
        """
        self.current_user_query = None

    def reduce_context(self):
        """
        Reduce the conversation history by summarizing it.
        """
        for entry in self.history[len(self.reduced_history):]:
            self.reduced_history.append(summarizer([entry[0], entry[1]]))

    def _update_keywords(self, text, entry):
        """
        Extract and store keywords from the given text and associate them with the entry.

        :param text: A string containing the text to extract keywords from.
        :type text: str
        :param entry: A dictionary containing the role and content of a conversation entry.
        :type entry: dict
        """
        doc = nlp(text.lower())
        for token in doc:
            if token.is_alpha and not token.is_stop:
                self.keywords[token.lemma_].append(entry)

    def gather_context(self, query, minimum_recent_history_length=1, max_tokens=2500):
        """
        Gather context from the conversation history based on the provided query.

        :param query: The user query to gather context for.
        :type query: str
        :param minimum_recent_history_length: The minimum number of recent history entries to include.
        :type minimum_recent_history_length: int
        :param max_tokens: The maximum number of tokens allowed for the gathered context.
        :type max_tokens: int
        :return: A list of conversation entries to be used as context for the provided query.
        :rtype: list
        """
        recent_history = []
        if minimum_recent_history_length > 0:
            recent_history = [item for tup in self.history[-minimum_recent_history_length:] for item in tup]

        query_keywords = extract_keywords(query)
        keyword_context = []
        for keyword in query_keywords:
            if str(keyword) in self.keywords.keys():
                keyword_context.extend(entry for entry in self.keywords[str(keyword)] if entry not in recent_history)

        combined_context = keyword_context + recent_history

        # Ensure the combined context does not exceed the max_tokens limit
        token_count = self.count_tokens_text(query) + self.count_tokens_context(combined_context)
        while token_count > max_tokens:
            if len(keyword_context) > 0:
                combined_context.pop(0)  # Remove the oldest keyword context entry
                token_count - self.count_tokens_text(keyword_context.pop(0)['content'])  # Keep keyword_context in sync
            elif len(recent_history) > 0:
                combined_context.pop(len(keyword_context))  # Remove the oldest recent history entry
                token_count - self.count_tokens_text(recent_history.pop(0)['content'])  # Keep recent_history in sync
            else:
                break

        # Backfill with more history context if there is room within the max_tokens limit
        backfilled_history = self.reduced_history[:-minimum_recent_history_length]
        for entry in reversed(backfilled_history):
            test_token = self.count_tokens_text(entry['content'])
            if token_count + test_token <= max_tokens:
                token_count += test_token
                combined_context.insert(0, entry)
            else:
                break

        return [get_system()]+combined_context

    def get_history(self):
        """
        Returns the history of the chat assistant

        :return: The complete history
        :rtype: list
        """
        return self.history

    def save_history_to_json(self, file_name):
        """
        Saves the chat history as a json file

        :param file_name: A path to store history as a json file
        :type file_name: str
        """
        file_name_temp = file_name[:-5]+"_temp.json"
        with open(file_name_temp, "w") as f:
            json.dump({"history": self.history,
                       "reduced_history": self.reduced_history,
                       "keywords": self.keywords}, f, indent=5)
        os.rename(file_name_temp, file_name)

    def load_history_from_json(self, file_name):
        """
        Loads the chat history from a json file

        :param file_name: A path to load json history file
        :type file_name: str
        """
        with open(file_name, "r") as f:
            raw = json.load(f)
            self.history = raw["history"]
            self.reduced_history = raw["reduced_history"]
            default_factory = list
            self.keywords = defaultdict(default_factory, raw["keywords"])
