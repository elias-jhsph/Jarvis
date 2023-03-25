import requests
from bs4 import BeautifulSoup
import openai
from connections import get_openai_key, get_google
from googleapiclient.discovery import build
import tiktoken

# Set up OpenAI API
openai.api_key = get_openai_key()
base_model = "text-davinci-002"
medium_model = "text-davinci-003"
enc = tiktoken.encoding_for_model(medium_model)

# Set up Google API
service = build("customsearch", "v1", developerKey=get_google())


def search(search_term, **kwargs):
    return service.cse().list(q=search_term, cx="43f9ec6b2e16a410c", **kwargs).execute()


def refine_query(query):
    response = openai.Completion.create(
        engine=medium_model,
        prompt=f"Please help me improve this search query for better results: '{query}'. Add context and keywords you "
               "think help better capture the idea behind the query. The response you send "
               "will go directly into google. Here is a helpful reminder of google tools you can use.\n"
               'Quotes (""): Use quotes to search for an exact phrase or word order.\n'
               "Minus (-): Exclude a specific word from your search.\n"
               "Asterisk (*): Use as a placeholder for unknown words.\n"
               "OR: Search for multiple terms or phrases.\n"
               "intitle: (intitle:): Search for words specifically in the title of webpages.\n"
               "intext: (intext:): Search for words specifically in the body of webpages.\n"
               "Note: Do not be so specific in your search that you miss the general point of the query. Also "
               "DO NOT SURROUND THE ENTIRE QUERY BY QUOTES.\n Query:",
        max_tokens=50,
        n=1,
        stop=None,
        temperature=0.8,
    )
    refined_query = response.choices[0].text.strip()
    return refined_query


def extract_content(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join([p.get_text() for p in paragraphs])
        return content
    except Exception as e:
        print(f"Error extracting content from {url}: {e}")
        return ""


def summarize(content):
    response = openai.Completion.create(
        engine=base_model,
        prompt=f"Please provide a concise summary of the following content:\n{content}\n",
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.8,
    )
    summary = response.choices[0].text.strip()
    return summary


def rank_relevance(url, summary, query):
    prompt = f"Given the query '{query}', rate the relevance of this summary from 1 (not relevant) to 10 (highly " \
             f"relevant):\nURL: {url}\nSummary: {summary}\nRelevance: "
    response = openai.Completion.create(
        engine=base_model,
        prompt=prompt,
        max_tokens=2,
        n=1,
        stop=None,
        temperature=0.8,
    )
    raw = response.choices[0].text.strip()
    if raw.isdigit():
        relevance = int(raw)
    else:
        prompt = f"Given the query '{query}', rate the relevance of this summary from 1 (not relevant) to 10 (highly " \
                 f"relevant) (for example - Relevance: INSERT_NUMBER):\nURL: {url}\nSummary: {summary}\nRelevance: "
        response = openai.Completion.create(
            engine=base_model,
            prompt=prompt,
            max_tokens=2,
            n=1,
            stop=None,
            temperature=0.8,
        )
        raw = response.choices[0].text.strip()
        if raw.isdigit():
            relevance = int(raw)
        else:
            return -1
    return relevance


def synthesize_information(summaries, query):
    summaries_text = "\n".join([f"Summary {i + 1}: {summary}" for i, (url, summary) in enumerate(summaries)])
    response = openai.Completion.create(
        engine=medium_model,
        prompt=f"Given the following summaries about '{query}', please "
               f"synthesize a coherent and comprehensive response:\n{summaries_text}\n",
        max_tokens=300,
        n=1,
        stop=None,
        temperature=0.8,
    )
    synthesized_info = response.choices[0].text.strip()
    return synthesized_info


def truncate_content(content, max_tokens=3500):
    tokens = enc.encode(content)

    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
        truncated_content = enc.decode(tokens)
        return truncated_content + "(TRUNCATED)"
    else:
        return content


def search_helper(query, result_number=6):
    search_data = {"initial_query": query, "refined_query": refine_query(query), "search_results": [],
                   "ranked_summaries": [], "synthesized_information": None}

    temp = search(search_data["refined_query"], num=result_number)
    if "items" not in temp:
        search_data["refined_query"] = query
        temp = search(search_data["refined_query"], num=result_number)
    search_data["search_results"] = temp['items']

    for result in search_data["search_results"]:
        content = extract_content(result['link'])
        summary = summarize(truncate_content(content))
        search_data["ranked_summaries"].append({"url": result['link'], "content": content, "summary": summary, "snippet": result['snippet']})

    for summary_data in search_data["ranked_summaries"]:
        relevance = rank_relevance(summary_data["url"], summary_data["summary"], search_data["refined_query"])
        summary_data["relevance"] = relevance

    search_data["ranked_summaries"].sort(key=lambda x: x["relevance"], reverse=True)

    search_data["synthesized_information"] = synthesize_information(
        [(data["url"], data["summary"]) for data in search_data["ranked_summaries"]],
        search_data["refined_query"]
    )

    return search_data


def simplify_output(search_data):
    simplified_output = {k: v for k, v in search_data.items() if k != "summaries"}
    for summary_data in simplified_output["ranked_summaries"]:
        summary_data.pop("content", None)
    return simplified_output


def generate_final_prompt(simplified_output, max_tokens=1800):
    synthesized_information = simplified_output["synthesized_information"]
    ranked_summaries = simplified_output["ranked_summaries"]
    refined_query = simplified_output["refined_query"]

    ranked_summaries_text = "\n".join(
        [f"{i + 1}. {summary['url']} (Relevance: {summary['relevance']}):\n{summary['summary']}"
         for i, summary in enumerate(ranked_summaries)]
    )

    prompt = (
        f"Pretend I am an AI language model that has conducted an internet search for '{refined_query}'. "
        f"I have synthesized the following information from the search results: '{synthesized_information}'. "
        f"Here are the ranked summaries of the top search results:\n{ranked_summaries_text}\n\n"
        f"Please analyze these results and provide the most appropriate response. Consider the following options: "
        f"1. Pass along the final summary\n"
        f"2. Provide a very short final answer\n"
        f"3. Suggest specific websites for further reading\n"
        f"4. Recommend a deeper search or further inquiry\n"
        f"5. Offer color commentary on the findings\n"
        f"6. Combine any of the above options.\n"
        f"NOTE: Give me the exact response that you would have me give the user. "
        f"Assume the user doesn't have access to these results so any component you want to refer to"
        f"remember to reiterate it for the user!"
    )

    tokens = enc.encode(prompt)
    if len(tokens) > max_tokens:
        diff = len(tokens) - max_tokens
        new = enc.encode(ranked_summaries_text)
        if len(new) < diff+10:
            raise Exception("Could not shrink internet final prompt within limit!")
        prompt = (
            f"Pretend I am an AI language model that has conducted an internet search for '{refined_query}'. "
            f"I have synthesized the following information from the search results: '{synthesized_information}'. "
            f"Here are the ranked summaries of the top search results:\n{ranked_summaries_text[:-(diff+10)]}\n\n"
            f"Please analyze these results and provide the most appropriate response. Consider the following options: "
            f"1. Pass along the final summary\n"
            f"2. Provide a very short final answer\n"
            f"3. Suggest specific websites for further reading\n"
            f"4. Recommend a deeper search or further inquiry\n"
            f"5. Offer color commentary on the findings\n"
            f"6. Combine any of the above options.\n"
            f"NOTE: Give me the exact response that you would have me give the user. "
            f"Assume the user doesn't have access to these results so any component you want to refer to"
            f"remember to reiterate it for the user!"
        )
    return prompt


def create_internet_context(query, result_number=10, max_tokens=1800):
    search_data = search_helper(query, result_number=result_number)
    simplified_output = simplify_output(search_data)
    return generate_final_prompt(simplified_output, max_tokens=max_tokens), simplified_output