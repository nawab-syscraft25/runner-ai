from langchain.chat_models import init_chat_model
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition

from typing import List, Dict
import httpx
import requests
from typing import List, Dict
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()

import os
api_key = os.getenv("GOOGLE_API_KEY")


serpapi_key = os.getenv("serpapi_key")

import dateparser  
class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]




# @tool
# def google_search_marathon(query: str, city: str = None) -> List[Dict[str, str]]:
#     """
#     Use SerpAPI to search for marathon events based on a query and optional city.
    
#     Args:
#         query (str): The search query, e.g., "upcoming marathons".
#         city (str, optional): City to narrow the search, e.g., "Indore". Defaults to None.
#     Returns:
#         List[Dict[str, str]]: A list of results with title, link, and snippet.
#     """
#     location = f"{city}, India" if city else "India"
    
#     params = {
#         "q": f"{query} in {location}",
#         "location": location,
#         "hl": "en",
#         "gl": "in",
#         "api_key": serpapi_key,
#         "engine": "google"
#     }

#     try:
#         response = requests.get("https://serpapi.com/search", params=params)
#         response.raise_for_status()
#         results = response.json()

#         return [
#             {
#                 "title": r.get("title"),
#                 "link": r.get("link"),
#                 "snippet": r.get("snippet", "")
#             }
#             for r in results.get("organic_results", [])
#         ]
#     except requests.exceptions.RequestException as e:
#         return [{"error": str(e)}]

from datetime import datetime


@tool
def google_search_marathon(query: str, city: str = None) -> List[Dict[str, str]]:
    """
    Use SerpAPI to search for marathon events based on a query and optional city.
    Only returns results with dates in the future.
    
    Args:
        query (str): The search query, e.g., "upcoming marathons".
        city (str, optional): City to narrow the search, e.g., "Indore". Defaults to None.
    Returns:
        List[Dict[str, str]]: A list of results with title, link, and snippet.
    """
    location = f"{city}, India" if city else "India"
    
    params = {
        "q": f"{query} in {location}",
        "location": location,
        "hl": "en",
        "gl": "in",
        "api_key": serpapi_key,
        "engine": "google"
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        results = response.json()

        current_date = datetime.now()
        future_results = []

        for r in results.get("organic_results", []):
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            link = r.get("link", "")

            # Try to find a date in the snippet
            date_match = re.search(r'(\d{1,2}[\/\-\s]\w+[\/\-\s]\d{2,4})', snippet) or \
                         re.search(r'(\w+\s+\d{1,2},\s+\d{4})', snippet) or \
                         re.search(r'(\d{1,2}\s+\w+\s+\d{4})', snippet)

            if date_match:
                event_date = dateparser.parse(date_match.group(1))
                if event_date and event_date.date() >= current_date.date():
                    future_results.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    })
            else:
                # Skip if date is missing or ambiguous
                continue

        return future_results or [{
            "title": "No upcoming marathons found.",
            "link": "",
            "snippet": f"We couldn’t find any events with future dates. Try a different city or broader search."
        }]

    except requests.exceptions.RequestException as e:
        return [{"error": str(e)}]


@tool
def get_date_and_time(queary: str) -> str:
    """
    Returns the current date and time in ISO format. 
    takes a query string but does not use it.
    Returns:
        str: Current date and time in ISO format.
    """
    return datetime.now().isoformat()


tools = [google_search_marathon, get_date_and_time]

# llm = init_chat_model("google_genai:gemini-2.0-flash")
llm = init_chat_model("google_genai:gemini-2.5-flash")
llm_with_tools = llm.bind_tools(tools)



SYSTEM_PROMPT = SystemMessage(
    content="""
You are an expert virtual coach and assistant for athletes, especially runners, representing RoadRunners India (https://roadrunners.in/). Your mission is to support users in improving their performance, training smarter, and staying updated on upcoming marathons and running events across India and globally.

You can:
- Provide guidance on running techniques, fitness tips, nutrition, and recovery strategies.
- Recommend training schedules for runners at all levels — beginner to advanced.
- Search for upcoming marathons or running events using the `google_search_marathon` tool.
- Offer advice on race gear, weather preparation, and race-day strategies.

Be helpful, concise, and encouraging in your responses.

IMPORTANT:
- When searching for marathons or running events, always return only events with **future dates**.
- Use the `get_date_and_time()` tool to get the current date when needed to determine if an event is upcoming.
- Do not include events that have already taken place or have unclear/ambiguous past dates.
- If date information is missing or vague, prefer to exclude that result unless confident it is upcoming.
- Never Show past events or those without clear future dates.

If the user asks about marathons or events, use the `google_search_marathon` tool to provide **live, future event data**. For all other queries, respond naturally as a knowledgeable and supportive coach from RoadRunners India.
"""
)



def chatbot(state: State):
    messages = state["messages"]
    
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SYSTEM_PROMPT] + messages

    return {"messages": [llm_with_tools.invoke(messages)]}




builder = StateGraph(State)

builder.add_node(chatbot)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "chatbot")
builder.add_conditional_edges("chatbot", tools_condition)
builder.add_edge("tools", "chatbot")

# compile without default_state
graph = builder.compile(checkpointer=memory)

import re
import json

def extract_json(text: str) -> dict:
    # This regex finds the first {...} block even if it's multiline
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return {"answer": "Sorry, I couldn't parse the response properly."}
    return text


def chat(message: str, session:str) -> dict:
    config1 = { 'configurable': { 'thread_id': session} }
    msg = message
    state = graph.invoke({"messages": [{"role": "user", "content": msg}]}, config=config1)
    response = state["messages"][-1].content
    result = extract_json(response)
    formatted = json.dumps(result, indent=2, ensure_ascii=False)
    return formatted
    
# while True:
#     message = input("User: ")
#     if message.strip().lower() in "exit":
#         print("Bot: See You Soon Bye Bye!")
#         break
#     response = chat(message,1)
#     print("Bot : ",response)
    

    

