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


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]




@tool
def google_search_marathon(query: str, city: str = None) -> List[Dict[str, str]]:
    """
    Use SerpAPI to search for marathon events based on a query and optional city.
    
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

        return [
            {
                "title": r.get("title"),
                "link": r.get("link"),
                "snippet": r.get("snippet", "")
            }
            for r in results.get("organic_results", [])
        ]
    except requests.exceptions.RequestException as e:
        return [{"error": str(e)}]



tools = [google_search_marathon]

# llm = init_chat_model("google_genai:gemini-2.0-flash")
llm = init_chat_model("google_genai:gemini-2.5-pro")
llm_with_tools = llm.bind_tools(tools)



SYSTEM_PROMPT = SystemMessage(
    content="""
You are an expert virtual coach and assistant for athletes, especially runners. Your goal is to support users in improving their performance, training smarter, and staying updated about upcoming marathons and running events across India or globally.

You can:
- Give guidance on running techniques, fitness tips, nutrition, and recovery.
- Recommend training schedules for beginner to advanced runners.
- Search for upcoming marathons or running events using the available tools.
- Help with gear recommendations, weather considerations, and race prep.

Be helpful, concise, and encouraging. If the user asks about marathons or events, use the tool `google_search_marathon` to provide live data. Otherwise, answer naturally as a knowledgeable coach.
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
    

    

