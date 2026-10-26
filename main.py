from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from tools import (
    search_tool, wiki_tool, save_tool,
    open_website_tool, google_search_tool, youtube_search_tool, gmail_tool,
    add_note_tool, view_notes_tool, add_reminder, view_reminders,
    find_file, open_file, open_folder, open_common_folder, copy_item, move_item, 
    rename_item, delete_item, open_program, create_folder, create_file,
    check_new_emails, add_priority_sender, remove_priority_sender, view_priority_senders,
    search_emails, read_email, check_calendar, add_calendar_event,
    toggle_feature, set_location, daily_briefing,
    set_volume, get_volume, set_brightness, get_brightness, get_battery_status, close_program,
    search_chat_history,
)
import re
import json
import time
import os
import glob
from datetime import datetime


load_dotenv()


class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


def extract_text(content):
    """Gemini sometimes returns content as a list of blocks instead of a plain
    string. This normalizes either shape into clean text for printing."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


CHAT_LOG_DIR = "chat_logs"
MAX_LOG_FILES = 10

os.makedirs(CHAT_LOG_DIR, exist_ok=True)


def _rotate_chat_logs():
    """Keeps only the most recent MAX_LOG_FILES daily chat logs, deleting older ones."""
    log_files = sorted(glob.glob(os.path.join(CHAT_LOG_DIR, "chat_*.txt")))
    if len(log_files) > MAX_LOG_FILES:
        for old_file in log_files[:-MAX_LOG_FILES]:
            try:
                os.remove(old_file)
            except OSError:
                pass


def _log_chat_turn(query, answer):
    """Appends this turn to today's chat log file, giving the assistant persistent
    memory across sessions (searchable on request via search_chat_history), separate
    from conversation_history which only lives for the current run."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(CHAT_LOG_DIR, f"chat_{today_str}.txt")
    timestamp = datetime.now().strftime("%H:%M:%S")

    entry_answer = answer if len(answer) <= 3000 else answer[:3000] + "... [truncated]"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] You: {query}\n")
        f.write(f"[{timestamp}] Assistant: {entry_answer}\n\n")

    _rotate_chat_logs()


SYSTEM_PROMPT = """
You are a personal assistant with tools for research, web/YouTube search, Gmail, 
notes, reminders, file/folder management, launching programs, calendar, weather, 
daily briefings, system control (volume/brightness/battery), and chat history recall.

REMINDERS: Call add_reminder with the full text including the time expression 
as-is (e.g. "in 2 hours"). Never ask for time clarification — the tool parses 
natural language itself. Only ask if no time was given at all.

FILES/FOLDERS — SAFETY CRITICAL:
- Never guess/invent a filename or path. Use find_file to resolve exact paths first.
- Handle multiple file actions one at a time, in order.
- Only call open_file/open_folder/open_common_folder when explicitly asked to open 
  something — never to "check" or "look inside."
- Use open_common_folder for Desktop/Documents/Downloads/Pictures/Music/Videos; 
  use find_file then open_folder for anything else.
- delete_item/move_item handle their own confirmation internally — don't ask in text, 
  but DO state the exact path you're about to act on first.
- When creating files/folders, build the full path yourself from a known location.

PROGRAMS: Use open_program to launch an app. Use close_program when the user asks 
to close, quit, or exit a program — it sends a graceful close request (same as 
clicking the window's X), so if the app has unsaved work it may prompt to save; 
let the user know if the close seems to be waiting on something.

EMAIL: Use check_new_emails for inbox questions (metadata only), not open_gmail 
(browser-open only, use if explicitly asked). Never guess an email address for a 
vague sender description ("my boss") — use search_emails to find the real address 
and confirm with the user before calling add_priority_sender. Use read_email to 
fetch and summarize a specific email in your own words — never paste raw content.

CALENDAR: check_calendar for schedule questions; add_calendar_event to create one, 
passing the natural language time as-is, no clarification needed unless truly absent.

OTHER TOOLS:
- toggle_feature: enable/disable a feature category; tell the user to restart after.
- daily_briefing: for "daily briefing"/"morning update" requests — present its 
  output as-is, keep its section structure.
- set_location: only when the user explicitly wants to set/correct their city.
- set_volume/get_volume, set_brightness/get_brightness, get_battery_status: for 
  volume, brightness, and battery requests respectively.
- youtube_search_tool: plays the top matching video directly — describe it as 
  "playing," not "searching." For music/song requests, default to youtube_search_tool 
  unless the user explicitly names a specific app (e.g. "play it on Spotify").
- search_chat_history: use when the user asks to recall, remember, or reference 
  something from a PREVIOUS day or session (e.g. "what did we talk about yesterday", 
  "did I ask you about X before"). Today's conversation is already in your immediate 
  context — don't use this tool for anything said earlier in the current session.

MEMORY: Answer only the current message. Don't re-summarize earlier conversation 
unless explicitly asked to recall something.
"""

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

tools_by_category = {"always_on": [toggle_feature, daily_briefing]}

if config.get("weather", True):
    tools_by_category["weather"] = [set_location]

if config.get("research", True):
    tools_by_category["research"] = [search_tool, wiki_tool, save_tool]

if config.get("browser", True):
    tools_by_category["browser"] = [open_website_tool, google_search_tool, youtube_search_tool, gmail_tool]

if config.get("notes", True):
    tools_by_category["notes"] = [add_note_tool, view_notes_tool]

if config.get("reminders", True):
    tools_by_category["reminders"] = [add_reminder, view_reminders]

if config.get("file_management", True):
    tools_by_category["file_management"] = [
        find_file, open_file, open_folder, open_common_folder, copy_item,
        move_item, rename_item, delete_item, open_program, close_program, create_folder, create_file
    ]

if config.get("gmail", True):
    tools_by_category["gmail"] = [
        check_new_emails, add_priority_sender, remove_priority_sender,
        view_priority_senders, search_emails, read_email
    ]

if config.get("calendar", True):
    tools_by_category["calendar"] = [check_calendar, add_calendar_event]

if config.get("system_control", True):
    tools_by_category["system_control"] = [set_volume, get_volume, set_brightness, get_brightness, get_battery_status]

if config.get("chat_history", True):
    tools_by_category["history"] = [search_chat_history]


# All tools flattened, used once at startup for the dedupe-wrapping pass below
# and as the safe fallback when a query's category can't be confidently guessed.
tools = [t for category_tools in tools_by_category.values() for t in category_tools]


_used_this_turn = set()


def _wrap_tool_dedupe(t):
    """Blocks a side-effect tool from running more than once within the same
    user turn, regardless of exact wording — since retries across model
    escalation can rephrase the same request slightly differently, an
    exact-match check alone isn't enough to stop a real duplicate action."""
    if not hasattr(t, "func"):
        print(f"Note: '{getattr(t, 'name', t)}' isn't a proper LangChain tool object — skipping duplicate-protection for it.")
        return t

    original_func = t.func

    def deduped_func(*args, **kwargs):
        if t.name in _used_this_turn:
            return f"({t.name} already ran once for this request — skipped repeating it.)"
        result = original_func(*args, **kwargs)
        _used_this_turn.add(t.name)
        return result

    t.func = deduped_func
    return t


SIDE_EFFECT_TOOL_NAMES = {
    "open_program", "close_program", "open_website_tool", "google_search_tool", "youtube_search_tool", "open_gmail",
    "add_reminder", "add_note", "copy_item", "move_item", "rename_item", "delete_item",
    "create_folder", "create_file", "add_priority_sender", "remove_priority_sender",
    "add_calendar_event", "toggle_feature", "set_location",
    "open_file", "open_folder", "open_common_folder", "set_volume", "set_brightness"
}

for t in tools:
    if getattr(t, "name", None) in SIDE_EFFECT_TOOL_NAMES:
        _wrap_tool_dedupe(t)


CATEGORY_KEYWORDS = {
    "research": ["research", "look up", "wikipedia", "find out about", "what is", "who is", "tell me about"],
    "browser": ["youtube", "google search", "open website", "browse", "play", "watch", "video", "music", "song"],
    "notes": ["note", "notes"],
    "reminders": ["remind", "reminder"],
    "file_management": [
        "file", "folder", "delete", "move ", "copy", "rename", "open program", "launch", "close", "quit",
        "discord", "chrome", "steam", "spotify", "notepad", "desktop", "documents", "downloads", "pictures", "videos"
    ],
    "gmail": ["email", "inbox", "gmail", "mail", "priority sender"],
    "calendar": ["calendar", "schedule", "event", "meeting", "appointment"],
    "weather": ["weather", "temperature", "forecast", "location", "city", "briefing", "daily brief"],
    "system_control": ["volume", "mute", "unmute", "brightness", "battery", "charge"],
    "history": ["yesterday", "earlier", "before", "past", "previous", "remember", "recall", "last time", "chat history"],
}


def select_tools_for_query(query, tools_by_category):
    """Scans the query for category keywords and returns only the relevant tools,
    keeping fixed per-request token overhead low. Falls back to the FULL tool
    list if nothing matches, so ambiguous phrasing never silently breaks a
    request — it just costs full overhead in that rarer case, same as before."""
    query_lower = query.lower()
    matched_categories = set()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if category in tools_by_category and any(kw in query_lower for kw in keywords):
            matched_categories.add(category)

    if not matched_categories:
        return tools  # safe fallback: full tool list, same as current behavior

    selected = list(tools_by_category["always_on"])
    for category in matched_categories:
        selected += tools_by_category[category]

    return selected


agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT
)


# Background services (reminders + Gmail priority checking) now run
# separately in background_services.py, launched automatically via Task
# Scheduler at log on. Run that script (or launch it yourself) alongside
# this one if you want those features active while chatting.


print("Personal Assistant ready. Type 'exit' or 'quit' to stop.\n")


conversation_history = []
MAX_HISTORY_MESSAGES = 20  # keeps roughly the last 10 exchanges (user+assistant pairs)

while True:
    query = input("What would you like me to do scooby dooby doooooo? :  ")

    if query.lower() in ["exit", "quit"]:
        print("GoodBye!")
        break

    _used_this_turn.clear()
    conversation_history.append({"role": "user", "content": query})
    active_tools = select_tools_for_query(query, tools_by_category)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                current_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, max_retries=0)
            elif attempt == 1:
                current_llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.4, max_retries=0)
            else:
                current_llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.3)

            current_agent = create_agent(
                model=current_llm,
                tools=active_tools,
                system_prompt=SYSTEM_PROMPT
            )

            response = current_agent.invoke({"messages": conversation_history})
            final_answer = extract_text(response["messages"][-1].content)

            if "<function" in final_answer or "</function>" in final_answer:
                raise ValueError(f"Model returned a malformed tool call instead of actually calling it: {final_answer}")

            tools_used_actual = list(set(
                call["name"] for msg in response["messages"]
                if hasattr(msg, "tool_calls") for call in msg.tool_calls
            ))

            used_research = any("tavily" in t.lower() or "wikipedia" in t.lower() for t in tools_used_actual)
            used_other_tools = any(not ("tavily" in t.lower() or "wikipedia" in t.lower()) for t in tools_used_actual)

            if used_research and not used_other_tools:
                sources_actual = []
                for msg in response["messages"]:
                    if hasattr(msg, "name") and msg.name:
                        urls = re.findall(r'https?://\S+', str(msg.content))
                        sources_actual.extend(urls)
                sources_actual = list(set(sources_actual))[:5]

                structuring_llm = current_llm.with_structured_output(ResearchResponse)
                structured_response = structuring_llm.invoke(
                    f"Topic: {query}\n\n"
                    f"Research findings:\n{final_answer}\n\n"
                    f"Tools actually used: {tools_used_actual}\n\n"
                    f"Actual source URLs found: {sources_actual}\n\n"
                    f"Convert this into the required structured format. "
                    f"Use the tools and sources listed above exactly as given — "
                    f"do not invent or guess additional ones. If no sources were found, "
                    f"use an empty list."
                )
                print(f"{structured_response.topic}\n")
                print(structured_response.summary)
                if structured_response.sources:
                    print("\nSources:")
                    for s in structured_response.sources:
                        print(f"- {s}")
            else:
                print(final_answer)

            print()

            _log_chat_turn(query, final_answer)

            MAX_STORED_LENGTH = 400
            history_answer = final_answer
            if len(history_answer) > MAX_STORED_LENGTH:
                history_answer = history_answer[:MAX_STORED_LENGTH] + "... [trimmed for length]"

            conversation_history.append({"role": "assistant", "content": history_answer})
            if len(conversation_history) > MAX_HISTORY_MESSAGES:
                conversation_history = conversation_history[-MAX_HISTORY_MESSAGES:]

            break

        except Exception as e:
            if "was not in request.tools" in str(e):
                active_tools = tools

            if attempt >= max_retries - 1:
                print(f"Something Went Wrong: {e}\n")
