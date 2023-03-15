import datetime
import json
import os.path

import openai
from keys import get_openai_key
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
assert enc.decode(enc.encode("hello world")) == "hello world"

history = None
def get_system():
    system = "You are Elias' AI Assistant named Jarvis. " \
             "You are based on the character Jarvis from the Marvel Universe. " \
             "The current date time is " + datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    if history != None:
        total = 0
        for message in history:
            total += len(enc.encode(message["content"]))
        system += ". Number of tokens in this conversation so far: "+str(total)
    return {"role": "system", "content": system}


model = "gpt-3.5-turbo-0301"
temperature = 0.8
maximum_length_message = 500
maximum_length_history = 3800
top_p = 1
frequency_penalty = 0.19
presence_penalty = 0
openai.api_key = get_openai_key()
if os.path.exists("history.json"):
    with open("history.json") as f:
        history = json.load(f)
else:
    history = [get_system()]


def get_history():
    history[0] = get_system()
    return history


def generate_response(query):
    smart_add(query, "user")
    response = openai.ChatCompletion.create(
        model=model,
        messages=get_history(),
        temperature=temperature,
        max_tokens=maximum_length_message,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )
    output = response['choices'][0]['message']['content']
    reason = response['choices'][0]["finish_reason"]
    if reason != "stop":
        if reason == "length" or reason == "null":
            del history[-1]
            return "I'm so sorry I got overwhelmed, can you put that more simply?"
        if reason == "content_filter":
            output = "I am so sorry, but if I responded to that I would have been forced to say something naughty."
    smart_add(output, "assistant")
    return output


def smart_add(query, role):
    total = len(enc.encode(query))
    if total > maximum_length_history:
        raise TypeError("That query is too long")
    for message in history:
        total += len(enc.encode(message["content"]))
    print("Tokens in history:",total)
    if total > maximum_length_history:
        first_user = None
        for i, message in enumerate(history):
            if first_user is None and message["role"] == "user":
                first_user = i
        if first_user is not None:
            del history[i]
        first_assistant = None
        for i, message in enumerate(history):
            if first_assistant is None and message["role"] == "assistant":
                first_assistant = i
        if first_assistant is not None:
            del history[i]
    history.append({"role": role, "content": query})
    with open("history.json", "w") as f:
        json.dump(history, f)
    return
