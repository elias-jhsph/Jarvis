import datetime
import json
import os
from collections import defaultdict
import openai
from connections import get_openai_key, get_user
import tiktoken
import spacy
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import uuid

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
    return "On " + datetime.datetime.now().strftime("%A, %B %-d, %Y at %-I:%M %p") + ": "


def _strip_entry(entry):
    """
    Remove all fields from the entry dictionary except 'role' and 'content'.

    :param entry: A dictionary containing a conversation entry.
    :type entry: dict
    :return: A new dictionary containing only the 'role' and 'content' fields from the original entry.
    :rtype: dict
    """

    if isinstance(entry, list):
        new = []
        for el in entry:
            new.append(_strip_entry(el))
        return new
    else:
        return {'role': entry['role'], 'content': entry['content']}


def get_similarity_score(query_vector, entry_vector):
    """
    Calculate the cosine similarity between two vectors.

    :param query_vector: A NumPy array representing the query vector.
    :type query_vector: np.ndarray
    :param entry_vector: A NumPy array representing the entry vector.
    :type entry_vector: np.ndarray
    :return: The cosine similarity score between the two vectors.
    :rtype: float
    """
    return cosine_similarity(query_vector.reshape(1, -1), entry_vector.reshape(1, -1))[0][0]


def get_mean_vector(doc):
    """
    Calculate the mean vector of a SpaCy document.

    :param doc: A SpaCy document object.
    :type doc: spacy.tokens.Doc
    :return: A NumPy array representing the mean vector of the document.
    :rtype: np.ndarray
    """
    vectors = [token.vector for token in doc if token.has_vector]
    return np.mean(vectors, axis=0) if vectors else np.zeros(nlp.vocab.vectors.shape[1])


def summarizer(input_list):
    """
    Summarize a conversation by sending a query to the OpenAI API.

    :param input_list: A list of dictionaries containing the conversation to be summarized.
    :type input_list: list
    :return: A dictionary containing the role and content of the summarized conversation.
    :rtype: dict
    """
    query = [{"role": "user", "content": "Please summarize this conversation concisely (Do your best to respond only"
                                         " with your best attempt at a summary and leave out caveats, preambles, "
                                         "or next steps)"}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=input_list+query,
        temperature=temperature,
        max_tokens=maximum_length_message,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )
    output = response['choices'][0]['message']['content']
    return {"role": "system", "content": output}


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
        self.long_term_memory = ""
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
            if isinstance(el, list):
                for e in el:
                    total += self.count_tokens_text(e['content'])
            else:
                total += self.count_tokens_text(el['content'])
        return total

    def add_user_query(self, query, role="user"):
        """
        Add a user query to the conversation history.

        :param query: The user query to be added.
        :type query: str
        :param role: The role the query will have - defaults to "user".
        :type role: str
        """
        self.current_user_query = {"role": role, "content": get_time() + query, "id": str(uuid.uuid4())}

    def add_assistant_response(self, response):
        """
        Add an assistant response to the conversation history.

        :param response: The assistant response to be added.
        :type response: str
        """
        if self.current_user_query is None:
            raise ValueError("No user query found. Add a user query before adding an assistant response.")
        assistant_response = {"role": "assistant", "content": get_time() + response, "id": str(uuid.uuid4())}
        self._update_keywords(self.current_user_query, assistant_response)
        self.history.append((self.current_user_query, assistant_response))
        self.current_user_query = None

    def reset_add(self):
        """
        Reset the current user query.
        """
        self.current_user_query = None

    def get_system(self):
        """
        Generate a system message containing user's AI Assistant's name and the current date time.

        :return: A dictionary containing the role and content of the system message.
        :rtype: dict
        """
        system = (f"You are {user_fix} AI Assistant named Jarvis. "
                  "You are based on the character Jarvis from the Marvel Universe. "
                  "The current date time is "
                  + datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")) + ". " + self.long_term_memory
        return {"role": "system", "content": system}

    def reduce_context(self):
        """
        Reduce the conversation history by summarizing it.
        """
        for entry in self.history[len(self.reduced_history):]:
            to_reduce = [_strip_entry(entry[0]), _strip_entry(entry[1])]
            new_summary = summarizer(to_reduce)
            self.reduced_history.append(new_summary)
        self.long_term_memory = summarizer(self.gather_context("", only_summaries=True))["content"]

    def _update_keywords(self, query_entry, response_entry):
        """
        Extract and store keywords from the given text and associate them with the query and response entries.

        :param query_entry: A dictionary containing the role and content of a conversation query entry.
        :type query_entry: dict
        :param response_entry: A dictionary containing the role and content of a conversation response entry.
        :type response_entry: dict
        """
        query_entry = query_entry.copy()
        response_entry = response_entry.copy()
        combined_text = query_entry['content'] + ' ' + response_entry['content']
        doc = nlp(combined_text.lower())
        keywords = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
        named_entities = [ent.text for ent in doc.ents]
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        query_entry['keywords'] = keywords
        query_entry['named_entities'] = named_entities
        query_entry['noun_phrases'] = noun_phrases
        response_entry['keywords'] = keywords
        response_entry['named_entities'] = named_entities
        response_entry['noun_phrases'] = noun_phrases
        for keyword in keywords + named_entities + noun_phrases:
            self.keywords[keyword].append([query_entry, response_entry])

    def _update_all_keywords(self):
        """
        Rebuilds all keyword history
        """
        default_factory = list
        new_keywords = defaultdict(default_factory, {})
        for entry_pair in self.history:
            query_entry = entry_pair[0]
            response_entry = entry_pair[1]
            combined_text = query_entry['content'] + ' ' + response_entry['content']
            doc = nlp(combined_text.lower())
            keywords = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]
            named_entities = [ent.text for ent in doc.ents]
            noun_phrases = [chunk.text for chunk in doc.noun_chunks]
            query_entry['keywords'] = keywords
            query_entry['named_entities'] = named_entities
            query_entry['noun_phrases'] = noun_phrases
            response_entry['keywords'] = keywords
            response_entry['named_entities'] = named_entities
            response_entry['noun_phrases'] = noun_phrases
            for keyword in keywords + named_entities + noun_phrases:
                new_keywords[keyword].append([query_entry, response_entry])
        self.keywords = new_keywords

    def gather_context(self, query, minimum_recent_history_length=2, max_tokens=2500,
                       only_summaries=False, only_role_and_content=True):
        """
        Gathers relevant context for a given query from the chat assistant's history.

        :param query: The input query for which context is to be gathered
        :type query: str
        :param minimum_recent_history_length: The minimum number of recent history entries to include, defaults to 2
        :type minimum_recent_history_length: int, optional
        :param max_tokens: The maximum number of tokens allowed in the combined context, defaults to 2500
        :type max_tokens: int, optional
        :param only_summaries: Whether to only include summaries in the context, defaults to False
        :type only_summaries: bool, optional
        :param only_role_and_content: Whether to only include 'role' and 'content' in the context entries, defaults to True
        :type only_role_and_content: bool, optional
        :return: A list of relevant context entries for the given query
        :rtype: list
        """
        if not only_summaries:
            recent_history = []
            if minimum_recent_history_length > 0:
                recent_history = self.history[-minimum_recent_history_length:]
            ids = []
            for recent in recent_history:
                ids.append(recent[0]['id'])
                ids.append(recent[1]['id'])

            query_doc = nlp(query.lower())
            query_vector = get_mean_vector(query_doc)
            all_keywords = set([token.lemma_ for token in query_doc if token.is_alpha and not token.is_stop] +
                               [ent.text for ent in query_doc.ents] +
                               [chunk.text for chunk in query_doc.noun_chunks])

            keyword_context = []
            for keyword in all_keywords:
                if keyword in self.keywords.keys():
                    for entry_pair in self.keywords[keyword]:
                        if entry_pair[0]['id'] not in ids and entry_pair[1]['id'] not in ids:
                            keyword_context.append(entry_pair)
                            ids.append(entry_pair[0]['id'])
                            ids.append(entry_pair[1]['id'])

            # Rank context entry pairs by relevance using a scoring mechanism
            keyword_context.sort(key=lambda entry_pair: get_similarity_score(query_vector, get_mean_vector(
                nlp(entry_pair[0]['content'].lower()))), reverse=True)

            combined_context = [entry for entry_pair in keyword_context + recent_history for entry in entry_pair]

            # Ensure the combined context does not exceed the max_tokens limit
            token_count = self.count_tokens_text(query) + self.count_tokens_context(combined_context)
            while token_count > max_tokens:
                if len(keyword_context) > 0:
                    keyword_context.pop(0)
                    combined_context = [entry for entry_pair in keyword_context for entry in
                                        entry_pair] + recent_history
                    token_count = self.count_tokens_text(query) + self.count_tokens_context(combined_context)
                else:
                    break
        else:
            combined_context = []
            token_count = 0

        backfilled_history = self.reduced_history[:-minimum_recent_history_length]
        for entry in reversed(backfilled_history):
            test_token = self.count_tokens_text(entry['content'])
            if token_count + test_token <= max_tokens:
                token_count += test_token
                combined_context.insert(0, entry)
            else:
                break

        if only_role_and_content:
            combined_context = [_strip_entry(entry) for entry in combined_context]
        output_context = []
        for item in combined_context:
            if isinstance(item, list):
                for element in item:
                    output_context.append(element)
            else:
                output_context.append(item)

        return [self.get_system()] + output_context

    def get_history(self):
        """
        Returns the history of the chat assistant

        :return: The complete history
        :rtype: list
        """
        out = []
        for el in self.history:
            out.append(_strip_entry(el))
        return out

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
                       "keywords": self.keywords,
                       "long_term_memory": self.long_term_memory}, f, indent=5)
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
            self.long_term_memory = raw["long_term_memory"]
