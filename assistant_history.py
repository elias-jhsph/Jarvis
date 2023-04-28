import datetime
import json
import os
import re
import sys
import warnings
from typing import List

import chromadb
from chromadb.config import Settings


def get_time() -> tuple:
    """
    Get the current time as a string.

    :return: A tuple containing two strings: the current time and the current UTC time.
    :rtype: tuple
    """
    return (
        f"On {datetime.datetime.now().strftime('%A, %B %-d, %Y at %-I:%M %p')}: ",
        str(datetime.datetime.utcnow()),
    )


def _strip_entry(entry: dict):
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
        return {"role": entry["role"], "content": entry["content"]}


class AssistantHistory:
    """
    A class to manage the Assistant's conversation history, including storing, reducing,
    and gathering conversation context for future queries.

    :param username: The username of the current user.
    :type username: str
    :param system: The system message.
    :type system: str
    :param tokenizer: A function to tokenize a string.
    :type tokenizer: function
    :param summarizer: A function to summarize a string.
    :type summarizer: function
    :param max_tokens: The maximum number of tokens allowed for the conversation history.
    :type max_tokens: int
    :param embedder: A function to embed a string.
    :type embedder: function, optional
    :param persist_directory: The directory to store the database in.
    :type persist_directory: str, optional
    :param chroma_db_impl: The database implementation to use.
    :type chroma_db_impl: str, optional
    :param model_injection: Whether to inject the model name into the history.
    :type model_injection: bool, optional
    :param time_injection: Whether to inject the time into the history.
    :type time_injection: bool, optional
    """

    def __init__(
        self,
        username: str,
        system: str,
        tokenizer: callable,
        summarizer: callable,
        max_tokens: int,
        summary_max_tokens: int,
        embedder: callable = None,
        persist_directory: str = "database",
        chroma_db_impl: str = "duckdb+parquet",
        model_injection: bool = True,
        time_injection: bool = True,
    ):
        """
        Initialize an instance of AssistantHistory.
        """
        self.model_injection = model_injection
        self.time_injection = time_injection
        self.persist_directory = persist_directory
        if getattr(sys, 'frozen', False):
            self.persist_directory = os.path.join(sys._MEIPASS, self.persist_directory)
        self.chroma_db_impl = chroma_db_impl
        self.client = chromadb.Client(
            Settings(
                chroma_db_impl=self.chroma_db_impl,
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
            )
        )
        # Load metadata from disk, or create a new metadata file if it doesn't exist.
        if os.path.exists(os.path.join(self.persist_directory, "AssistantHistoryMetadata.json")):
            with open(os.path.join(self.persist_directory, "AssistantHistoryMetadata.json"), "r") as f:
                metadata = json.load(f)
        else:
            metadata = {"current_id": "0", "current_summary_id": "0", "to_summarize": None}
        self.next_id = int(metadata["current_id"]) + 1
        self.next_summary_id = int(metadata["current_summary_id"]) + 1
        self.to_summarize = metadata["to_summarize"]

        # Load long-term memory from disk, or create a new LTM file if it doesn't exist.
        if os.path.exists(os.path.join(self.persist_directory, "AssistantHistoryLTM.json")):
            with open(os.path.join(self.persist_directory, "AssistantHistoryLTM.json"), "r") as f:
                ltm = json.load(f)
        else:
            ltm = {"long_term_memory": ""}
        self.long_term_memory = ltm["long_term_memory"]

        # Set instance variables based on input parameters.
        self.username = username
        self.fixed_user = username + "'" if username[-1] == "s" else username + "'s"
        self.system_raw = system
        self.embedder = embedder
        self.max_tokens = max_tokens
        self.summary_max_tokens = summary_max_tokens
        self.tokenizer = tokenizer
        self.summarizer = summarizer

        # Create history and summaries collections using the chromadb client.
        if self.embedder:
            self.history = self.client.get_or_create_collection(
                name="history", embedding_function=self.embedder
            )
            self.summaries = self.client.get_or_create_collection(
                name="summaries", embedding_function=self.embedder
            )
        else:
            self.history = self.client.get_or_create_collection(name="history")
            self.summaries = self.client.get_or_create_collection(name="summaries")

        if self.next_id > 1:
            # Check whether the next summary ID is in the history database.
            expected_summaries = ((self.next_id - 1) / 2)
            if expected_summaries > self.next_summary_id - 1 and self.to_summarize is None:
                warnings.warn(
                    "Summary ID number is less than expected. Adding last two entries to summary queue."
                )
                last_two = self.get_history_from_id_and_earlier(n_results=2)
                self.to_summarize = (last_two[1], last_two[0])
                self.save_metadata()

            # Delete extra summaries if the next summary ID is greater than the expected number of summaries.
            expected_history = ((self.next_summary_id - 1) * 2)
            if expected_history > self.next_id - 1:
                warnings.warn(
                    "History ID number is less than expected. Attempting to fix."
                )
                while expected_history > self.next_id - 1:
                    expected_history = ((self.next_summary_id - 1) * 2)
                    self.summaries.delete([str(self.next_summary_id - 1)])
                    self.next_summary_id -= 1
                self.save_metadata()
            self.current_user_query = None

            # Check whether the next summary ID is in the summaries database.
            # If it's not, attempt to fix by decrementing the ID until a valid summary is found.
            # Also, check whether the next ID is in the history database.
            # If it's not, decrement the ID until a valid entry is found.
            check_summary = self.summaries.get([str(self.next_summary_id - 1)], include=["documents", "metadatas"])
            if len(check_summary["ids"]) == 0:
                warnings.warn(
                    "Summary ID is not in the database. "
                    "This is likely because the database was not properly closed. Attempting to fix."
                )
                found = False
                while not found:
                    history_check = self.history.get([str(self.next_id - 1)], include=["documents", "metadatas"])
                    if len(history_check["ids"]) == 0:
                        self.next_id -= 1
                        metadata["current_id"] = str(self.next_id - 1)
                    else:
                        found = True
                found = False
                while not found:
                    summary_check = self.summaries.get([str(self.next_summary_id - 1)], include=["documents", "metadatas"])
                    if len(summary_check["ids"]) == 0:
                        self.next_summary_id -= 1
                        metadata["current_summary_id"] = str(self.next_summary_id - 1)
                    else:
                        found = True
                if not str(self.next_id - 1) in summary_check["metadatas"][0]["source_ids"].split(","):
                    last_two = self.get_history_from_id_and_earlier(n_results=2)
                    self.to_summarize = (last_two[1], last_two[0])
                else:
                    self.to_summarize = None
                metadata["to_summarize"] = self.to_summarize
                self.save_metadata()

    def reload_from_disk(self):
        """
        Reload the Assistant's conversation history from disk.

        :return: None
                """
        self.client = chromadb.Client(Settings(chroma_db_impl=self.chroma_db_impl,
                                               persist_directory=self.persist_directory,
                                               anonymized_telemetry=False
                                               ))
        if os.path.exists(os.path.join(self.persist_directory, "AssistantHistoryMetadata.json")):
            with open(os.path.join(self.persist_directory, "AssistantHistoryMetadata.json"), "r") as f:
                metadata = json.load(f)
        else:
            metadata = {"current_id": "0", "current_summary_id": "0", "to_summarize": None}
        self.next_id = int(metadata["current_id"]) + 1
        self.next_summary_id = int(metadata["current_summary_id"]) + 1
        self.to_summarize = metadata["to_summarize"]

        if os.path.exists(os.path.join(self.persist_directory, "AssistantHistoryLTM.json")):
            with open(os.path.join(self.persist_directory, "AssistantHistoryLTM.json"), "r") as f:
                ltm = json.load(f)
        else:
            ltm = {"long_term_memory": ""}
        self.long_term_memory = ltm["long_term_memory"]

        if self.embedder:
            self.history = self.client.get_or_create_collection(name="history", embedding_function=self.embedder)
            self.summaries = self.client.get_or_create_collection(name="summaries", embedding_function=self.embedder)
        else:
            self.history = self.client.get_or_create_collection(name="history")
            self.summaries = self.client.get_or_create_collection(name="summaries")
        self.current_user_query = None

    def create_chat_id(self):
        """
        Get the current set ID.

        :return: The current set ID.
        :rtype: str
        """
        new_id = self.next_id
        self.next_id = new_id + 1
        self.save_metadata()
        return str(new_id)

    def create_summary_id(self):
        """
        Get the current summary ID.

        :return: The current summary ID.
        :rtype: str
        """
        new_id = self.next_summary_id
        self.next_summary_id = new_id + 1
        self.save_metadata()
        return str(new_id)

    def save_ltm(self):
        """
        Save the long term memory to a file.
        """
        with open(os.path.join(self.persist_directory, "AssistantHistoryLTM.json"), "w") as f:
            json.dump({"long_term_memory": self.long_term_memory}, f)

    def count_tokens_text(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        :param text: A string containing the text to count tokens for.
        :type text: str
        :return: The number of tokens in the given text.
        :rtype: int
        """
        return len(self.tokenizer(text))

    def count_tokens_context(self, ls: list) -> int:
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

    def add_user_query(self, query: str, role: str = "user") -> None:
        """
        Add a user query to the conversation history.

        :param query: The user query to be added.
        :type query: str
        :param role: The role the query will have - defaults to "user".
        :type role: str
        """
        time_str, utc_time = get_time()
        if self.time_injection:
            query = time_str + query
        self.current_user_query = {"role": role, "content": query, "utc_time": utc_time}

    def add_assistant_response(self, response: str, model: str) -> None:
        """
        Add an assistant response to the conversation history.

        :param response: The assistant response to be added.
        :type response: str
        :param model: The model that generated the response.
        :type model: str
        """
        if self.current_user_query is None:
            raise ValueError("No user query found. Add a user query before adding an assistant response.")
        time_str, utc_time = get_time()
        self.current_user_query['id'] = self.create_chat_id()
        if self.time_injection:
            response = time_str + response
        if self.model_injection:
            response = "Source AI Model: " + model + " - " + response
        assistant_response = {"role": "assistant", "content": response,
                              "id": self.create_chat_id(), "utc_time": utc_time,
                              "pair_id": self.current_user_query['id']}
        self.current_user_query['pair_id'] = assistant_response['id']
        user_query_metadata = {"role": self.current_user_query['role'],
                               "pair_id": self.current_user_query['pair_id'],
                               "utc_time": self.current_user_query['utc_time'],
                               "num_tokens": self.count_tokens_text(self.current_user_query['content'])}
        assistant_response_metadata = {"role": assistant_response['role'],
                                       "pair_id": assistant_response['pair_id'],
                                       "utc_time": assistant_response['utc_time'],
                                       "model": model,
                                       "num_tokens": self.count_tokens_text(assistant_response['content'])}
        self.history.add(
            embeddings=[self.embedder(self.current_user_query['content']),
                        self.embedder(assistant_response['content'])],
            metadatas=[user_query_metadata, assistant_response_metadata],
            documents=[self.current_user_query['content'], assistant_response['content']],
            ids=[self.current_user_query['id'], assistant_response['id']],
        )
        self.to_summarize = (self.current_user_query.copy(), assistant_response.copy())
        self.save_metadata()
        self.current_user_query = None
        self.client.persist()

    def reset_add(self) -> None:
        """
        Reset the current user query.
        """
        self.current_user_query = None

    def get_system(self) -> dict:
        """
        Generate a system message containing user's AI Assistant's name and the current date time.

        :return: A dictionary containing the role and content of the system message.
        :rtype: dict
        """
        system_raw = self.system_raw
        system = re.sub("FIXED_USER_INJECTION", self.fixed_user, system_raw)
        system = re.sub("DATETIME_INJECTION", datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"), system)
        system = re.sub("LONG_TERM_MEMORY_INJECTION", self.long_term_memory, system)
        return {"role": "system", "content": system}

    def reduce_context(self) -> None:
        """
        Reduce the conversation history by summarizing it.
        """
        to_reduce = [_strip_entry(self.to_summarize[0]), _strip_entry(self.to_summarize[1])]
        new_summary = self.summarizer(to_reduce)
        new_summary_metadata = {"role": "assistant",
                                "source_ids": ",".join([self.to_summarize[0]['id'], self.to_summarize[1]['id']]),
                                "utc_time": self.to_summarize[0]['utc_time'],
                                "num_tokens": self.count_tokens_text(new_summary['content'])}
        self.summaries.add(
            embeddings=[self.embedder(new_summary['content'])],
            metadatas=[new_summary_metadata.copy()],
            documents=[new_summary['content']],
            ids=[self.create_summary_id()],
        )
        self.long_term_memory = self.summarizer(
            self.gather_context("", only_summaries=True,
                                max_tokens=(self.summary_max_tokens -
                                            self.count_tokens_text(self.long_term_memory))))["content"]
        self.save_ltm()

    def load_metadata(self):
        """
        Load metadata from the JSON file.
        """
        try:
            with open(os.path.join(self.persist_directory, "AssistantHistoryMetadata.json"), "r") as f:
                data = json.load(f)
                self.next_id = data["next_id"]
                self.next_summary_id = data["next_summary_id"]
                self.history.load(os.path.join(self.persist_directory, "AssistantHistory"),
                                  embeddings_storage=os.path.join(self.persist_directory, "embeddings"))
                self.summaries.load(os.path.join(self.persist_directory, "AssistantSummaries"),
                                    embeddings_storage=os.path.join(self.persist_directory, "embeddings"))
        except FileNotFoundError:
            pass

    def save_metadata(self):
        """
        Save metadata to the JSON file.
        """
        with open(os.path.join(self.persist_directory, "AssistantHistoryMetadata.json"), "w") as f:
            json.dump({"current_id": self.next_id-1, "current_summary_id": self.next_summary_id-1,
                       "to_summarize": self.to_summarize}, f)

    def gather_context(self, query: str, minimum_recent_history_length: int = 2, max_tokens: int = None,
                       only_summaries: bool = False, only_role_and_content: bool = True,
                       distance_cut_off: float = None, query_max_size: int = 30) -> List[dict]:
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
        :param only_role_and_content: Whether to only include 'role' and 'content' in context entries, defaults to True
        :type only_role_and_content: bool, optional
        :param distance_cut_off: The maximum distance between the query and the context entry, defaults to None
        :type distance_cut_off: float, optional
        :param query_max_size: The maximum number results to return from full context query, defaults to 30
        :type query_max_size: int, optional
        :return: A list of relevant context entries for the given query
        :rtype: List[dict]
        """
        if max_tokens is None:
            max_tokens = int(0.85 * self.max_tokens)
        if not only_summaries:
            context_list = []
            id_added = []
            summary_ids = []
            token_count = 0

            # Add the most recent history entries
            if minimum_recent_history_length > 0:
                recent_ids = list(range(self.next_id - (minimum_recent_history_length * 2), self.next_id))
                recent_ids = [str(x) for x in recent_ids]
                result = self.history.get(recent_ids, include=['documents', 'metadatas'])
                for id in recent_ids:
                    try:
                        result_pos = result["ids"].index(id)
                        entry = result["metadatas"][result_pos]
                        entry["content"] = result["documents"][result_pos]
                        if token_count + entry["num_tokens"] > max_tokens:
                            break
                        context_list.append(entry)
                        id_added.append(id)
                        token_count += entry["num_tokens"]
                    except ValueError:
                        continue

            # If the context is too short, query the full history
            if token_count > max_tokens:
                query_size = query_max_size
                if query_size > self.next_id - 1:
                    query_size = self.next_id - 1
                query_results = self.history.search(query, n_results=query_size)
                for id in query_results["ids"][0]:
                    if id not in id_added:
                        result_pos = query_results["ids"][0].index(id)
                        entry = query_results["metadatas"][0][result_pos]
                        if token_count + entry["num_tokens"] > max_tokens:
                            break
                        if distance_cut_off is not None:
                            if query_results["distances"][0]["result_pos"] < distance_cut_off:
                                break
                        if entry["role"] == "user":
                            entry["content"] = query_results["documents"][0][result_pos]
                            id_added.append(id)
                            context_list.insert(0, entry)
                            token_count += entry["num_tokens"]
                            matched_data = self.history.get(entry["pair_id"],
                                                            include=['documents', 'metadatas'])
                            match_entry = matched_data["metadatas"][0]
                            match_entry["content"] = matched_data["documents"][0]
                            if token_count + match_entry["num_tokens"] > max_tokens:
                                break
                            id_added.append(entry["pair_id"])
                            context_list.insert(1, match_entry)
                            token_count += match_entry["num_tokens"]
                        if entry["role"] == "assistant":
                            entry["content"] = query_results["documents"][0][result_pos]
                            id_added.append(id)
                            context_list.insert(0, entry)
                            token_count += entry["num_tokens"]
                            matched_data = self.history.get(entry["pair_id"],
                                                            include=['documents', 'metadatas'])
                            match_entry = matched_data["metadatas"][0]
                            match_entry["content"] = matched_data["documents"][0]
                            if token_count + match_entry["num_tokens"] > max_tokens:
                                break
                            id_added.append(entry["pair_id"])
                            context_list.insert(0, match_entry)
                            token_count += match_entry["num_tokens"]

                # If the context is still too short, query the summaries
                if token_count > max_tokens:
                    query_size = query_max_size
                    if query_size > self.next_summary_id - 1:
                        query_size = self.next_summary_id - 1
                    query_summaries = self.summaries.search(query, n_results=query_size)
                    for id in query_summaries["ids"][0]:
                        if id not in summary_ids:
                            result_pos = query_summaries["ids"][0].index(id)
                            entry = query_summaries["metadatas"][0][result_pos]
                            if token_count + entry["num_tokens"] > max_tokens:
                                break
                            if distance_cut_off is not None:
                                if query_summaries["distances"][0]["result_pos"] < distance_cut_off:
                                    break
                            if not (entry["source_ids"].split(",")[0] in id_added and
                                    entry["source_ids"].split(",")[1] in id_added):
                                entry["content"] = query_summaries["documents"][0][result_pos]
                                summary_ids.append(id)
                                summary_ids.insert(0, entry)
                                token_count += entry["num_tokens"]

            else:
                context_list = []
                summary_ids = []
                id_added = []
                token_count = 0
        else:
            context_list = []
            summary_ids = []
            id_added = []
            token_count = 0

        # Add the summaries if there is any space left
        current_summary_id = self.next_summary_id - 1
        while current_summary_id > 0:
            if current_summary_id not in summary_ids:
                result = self.summaries.get(str(current_summary_id), include=['documents', 'metadatas'])
                entry = result["metadatas"][0]
                entry["content"] = result["documents"][0]
                if token_count + entry["num_tokens"] > max_tokens:
                    break
                if not (entry["source_ids"].split(",")[0] in id_added and
                        entry["source_ids"].split(",")[1] in id_added):
                    context_list.insert(0, entry)
                    summary_ids.append(result["ids"][0])
                    token_count += entry["num_tokens"]
            current_summary_id -= 1

        if only_role_and_content:
            context_list = [_strip_entry(entry) for entry in context_list]

        return [self.get_system()] + context_list

    def get_history(self):
        """
        Returns the history of the chat assistant

        :return: The complete history
        :rtype: list
        """
        return self.history

    def get_history_from_id_and_earlier(self, id=None, n_results=10, reload_disk=False):
        """
        Returns the history of the chat assistant from a given id and earlier

        :param id: The id to start from
        :type id: int
        :param n_results: The number of results to return
        :type n_results: int
        :param reload_disk: If the history should be reloaded from disk
        :type reload_disk: bool
        :return: The history
        :rtype: list
        """
        if reload_disk:
            self.reload_from_disk()
        if id is None:
            id = self.next_id-1
        else:
            id = int(id)
        target_ids = list(range(id, id-n_results, -1))
        target_ids = [str(x) for x in target_ids if x > 0]
        output = []
        results = self.history.get(target_ids, include=['documents', 'metadatas'])
        for tid in target_ids:
            if tid in results["ids"]:
                pos = results["ids"].index(tid)
                entry = results["metadatas"][pos]
                entry["content"] = results["documents"][pos]
                entry["id"] = tid
                output.append(entry)
        return output
