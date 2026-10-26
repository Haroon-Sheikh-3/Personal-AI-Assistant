from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_tavily import TavilySearch
from langchain_core.tools import Tool, tool
from dotenv import load_dotenv
from datetime import datetime, timedelta
import webbrowser
import json
import dateparser
from plyer import notification
import os
import shutil
import subprocess
from send2trash import send2trash
from fuzzywuzzy import fuzz
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
import winsound
import re
import requests
import comtypes
from pycaw.pycaw import AudioUtilities
import screen_brightness_control as sbc
import psutil
import winreg
import glob



load_dotenv()


def save_to_txt(data: str, filename: str = "research_output.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"--- Research Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"

    with open(filename, "a", encoding="utf-8") as f:
        f.write(formatted_text)

    return f"Data successfully saved to {filename}"


save_tool = Tool(
    name="save_text_to_file",
    func=save_to_txt,
    description="Saves structured research data to a text file",
)

# Wikipedia tool
api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=500)
wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

# Tavily search tool
search_tool = TavilySearch(
    max_results=3,
    topic="general",
)


# OPEN WEBSITE
@tool
def open_website_tool(url: str) -> str:
    """Opens any website given a full URL, e.g. https://example.com"""
    webbrowser.open(url)
    return f"Opened {url}"


# GOOGLE SEARCH
@tool
def google_search_tool(query: str) -> str:
    """Searches Google for a given query and opens the results in the browser"""
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Searched Google for {query}"


# YOUTUBE SEARCH / PLAY
@tool
def youtube_search_tool(query: str) -> str:
    """Searches YouTube for a given query and opens the top result directly so it
    starts playing, rather than just showing a list of search results."""
    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    try:
        resp = requests.get(
            search_url,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
        )
        match = re.search(r"watch\?v=([A-Za-z0-9_-]{11})", resp.text)

        if match:
            webbrowser.open(f"https://www.youtube.com/watch?v={match.group(1)}")
            return f"Playing the top YouTube result for '{query}'"

        webbrowser.open(search_url)
        return f"Searched YouTube for '{query}' (couldn't isolate a direct video, opened search results instead)"

    except Exception as e:
        webbrowser.open(search_url)
        return f"Searched YouTube for '{query}' (direct play failed: {e}, opened search results instead)"


# OPEN GMAIL
@tool
def open_gmail(_: str = "") -> str:
    """Opens Gmail in the browser"""
    webbrowser.open("https://mail.google.com")
    return "Opened Gmail"


# main.py imports this under the name gmail_tool
gmail_tool = open_gmail


# ADD NOTES
def add_note(note: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("notes.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {note}\n")
    return f"Note saved: {note}"

add_note_tool = Tool(
    name="add_note",
    func=add_note,
    description="Saves a note the user wants to remember",
)


# VIEW NOTES
def view_notes(_: str = "") -> str:
    try:
        with open("notes.txt", "r", encoding="utf-8") as f:
            content = f.read()
        return content if content else "No notes found."
    except FileNotFoundError:
        return "No notes found."

view_notes_tool = Tool(
    name="view_notes",
    func=view_notes,
    description="Shows all previously saved notes",
)


# REMINDERS
REMINDERS_FILE = "reminders.json"


def _load_reminders():
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2)


@tool
def add_reminder(text: str) -> str:
    """Sets a reminder with a natural language time, e.g. 'call mom tomorrow at 5pm' or 'submit report in 2 hours'"""
    parsed_time = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    if not parsed_time:
        return f"Couldn't understand the time in: '{text}'. Try being more specific, e.g. 'call mom tomorrow at 5pm'."

    reminders = _load_reminders()
    reminders.append({
        "message": text,
        "due_time": parsed_time.strftime("%Y-%m-%d %H:%M:%S"),
        "notified": False
    })
    _save_reminders(reminders)
    return f"Reminder set for {parsed_time.strftime('%Y-%m-%d %H:%M')}: {text}"


@tool
def view_reminders(_: str = "") -> str:
    """Shows all currently set reminders"""
    reminders = _load_reminders()
    if not reminders:
        return "No reminders found."
    return "\n".join(f"- [{r['due_time']}] {r['message']}" for r in reminders)



#SEARCH FILE/FOLDER
@tool
def find_file(filename: str) -> str:
    """Searches the user's home directory for a file or folder matching the given name (fuzzy match allowed) and returns the best matches"""
    home_dir = os.path.expanduser("~")
    matches = []
    skip_dirs = {"AppData", "node_modules", ".git", "venv", "__pycache__", ".cache"}
    start_time = time.time()
    max_seconds = 10

    for root, dirs, files in os.walk(home_dir):
        if time.time() - start_time > max_seconds:
            break

        dirs[:] = [d for d in dirs if d not in skip_dirs]

        # check folder names too
        for d in dirs:
            score = fuzz.partial_ratio(filename.lower(), d.lower())
            if score >= 70:
                matches.append((score, os.path.join(root, d)))

        # check file names
        for file in files:
            score = fuzz.partial_ratio(filename.lower(), file.lower())
            if score >= 70:
                matches.append((score, os.path.join(root, file)))

        if len(matches) >= 20:
            break

    if not matches:
        return f"No files or folders found matching '{filename}'."

    matches.sort(reverse=True)
    top_matches = [path for score, path in matches[:5]]
    return "Found:\n" + "\n".join(top_matches)


# OPEN COMMON FOLDER
COMMON_FOLDERS = {
    "desktop": "Desktop",
    "documents": "Documents",
    "downloads": "Downloads",
    "pictures": "Pictures",
    "music": "Music",
    "videos": "Videos",
}

@tool
def open_common_folder(folder_name: str) -> str:
    """Opens a common user folder like desktop, documents, downloads, pictures, music, or videos"""
    home_dir = os.path.expanduser("~")
    key = folder_name.lower().strip()

    if key not in COMMON_FOLDERS:
        return f"'{folder_name}' isn't a recognized common folder. Try desktop, documents, downloads, pictures, music, or videos."

    full_path = os.path.join(home_dir, COMMON_FOLDERS[key])
    try:
        os.startfile(full_path)
        return f"Opened {COMMON_FOLDERS[key]} folder"
    except Exception as e:
        return f"Could not open folder: {e}"



#OPEN FILE
@tool
def open_file(path:str) ->str:
    """Opens a file with its default program, given the full file path"""
    try:
        os.startfile(path)
        return f"Opened {path}"
    except Exception as e:
        return f"Could not open the file: {e}"


#OPEN FOLDER
@tool
def open_folder(path:str) ->str:
    """Opens a folder in File Explorer, given the full folder path"""
    try:
        os.startfile(path)
        return f"Opened folder {path}"
    except Exception as e:
        return f"Could not open folder: {e}"
    

#COPY FUNCION
@tool 
def copy_item(source:str, destination:str) ->str:
    """Copies a file or folder from source path to destination path"""
    try:
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return f"Copied {source} to {destination}"
    except Exception as e:
        return f"Could not copy: {e}"
    
#MOVE WITH CONFIRMATION
@tool
def move_item(source:str, destination:str)->str:
    """Moves a file or folder from source path to destination path. Always asks the user to confirm first."""
    confirm = input(f"\n⚠️ Confirm: move '{source}' to '{destination}'? (yes/no): ")
    if confirm.lower() not in ["yes","y"]:
        return "Move cancelled by user."
    try:
        shutil.move(source, destination)
        return f"Moved {source} to {destination}"
    except Exception as e:
        return f"Could not move: {e}"
    

#RENAME FUNCTION
@tool 
def rename_item(path:str, new_name:str) ->str:
    """Renames a file or folder. 'path' is the full current path, 'new_name' is just the new filename or foldername (not a full path)"""
    try:
        directory = os.path.dirname(path)
        new_path = os.path.join(directory, new_name)
        os.rename(path, new_path)
        return f"Renamed {path} to {new_path}"
    except Exception as e:
        return f"Could not rename: {e}"



# DELETE FILE OR FOLDER (safe delete via Recycle Bin, with confirmation)
SAFE_FOLDERS = ["Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"]

@tool
def delete_item(path:str) ->str:
    """Deletes a file or folder by sending it to the Recycle Bin. Always asks the user to confirm first. Refuses to delete anything outside common user folders (Desktop, Documents, Downloads, Pictures, Music, Videos) for safety."""
    home_dir = os.path.expanduser("~")
    normalized_path = os.path.normpath(path)

    safe_folder_paths = [os.path.normpath(os.path.join(home_dir, folder)) for folder in SAFE_FOLDERS]

    if normalized_path in safe_folder_paths:
        return f"Refused to delete '{path}' — this is one of your main folders, not something inside it. This tool only deletes files/folders located inside your safe folders, not the safe folders themselves."

    is_in_safe_folder = any(normalized_path.startswith(safe_path) for safe_path in safe_folder_paths)

    if not is_in_safe_folder:
        return (
            f"Refused to delete '{path}' — this is outside your common user folders "
            f"(Desktop, Documents, Downloads, Pictures, Music, Videos). "
            f"For safety, this tool won't delete files there."
        )

    confirm = input(f"\n⚠️  Confirm: send '{path}' to Recycle Bin? (yes/no): ")
    if confirm.lower() not in ["yes", "y"]:
        return "Delete cancelled by user."

    try:
        send2trash(path)
        return f"Send {path} to RecycleBin"
    except Exception as e:
        return f"Could not delete {e}"
    


#OPEN PROGRAM
def _find_via_registry(name: str):
    """Checks Windows' own 'App Paths' registry — the same mechanism Win+R uses
    to resolve program names. Most properly installed Windows apps register here,
    making this far more reliable than guessing folder names."""
    registry_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    exe_name = name if name.lower().endswith(".exe") else f"{name}.exe"

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, f"{registry_path}\\{exe_name}") as key:
                path, _ = winreg.QueryValueEx(key, None)
                if os.path.exists(path):
                    return path
        except FileNotFoundError:
            continue
        except OSError:
            continue

    return None


def _find_via_glob(name: str):
    """Searches common install locations using wildcards, to handle apps that
    install into version-numbered folders (e.g. Discord's app-1.0.9187 style
    folders, which change with every update)."""
    home_dir = os.path.expanduser("~")

    search_patterns = [
        os.path.join(home_dir, "AppData", "Local", name, "app-*", f"{name}.exe"),
        os.path.join(home_dir, "AppData", "Local", name, f"{name}.exe"),
        os.path.join(home_dir, "AppData", "Local", "Programs", name, f"{name}.exe"),
        os.path.join(home_dir, "AppData", "Roaming", name, f"{name}.exe"),
        os.path.join("C:\\Program Files", name, f"{name}.exe"),
        os.path.join("C:\\Program Files", name, "*", f"{name}.exe"),
        os.path.join("C:\\Program Files (x86)", name, f"{name}.exe"),
        os.path.join("C:\\Program Files (x86)", name, "*", f"{name}.exe"),
    ]

    for pattern in search_patterns:
        matches = glob.glob(pattern, recursive=False)
        if matches:
            # If multiple version folders exist, prefer the most recently modified one
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]

    return None


@tool
def open_program(name: str) -> str:
    """Launches a program or application by name, e.g. 'discord', 'chrome', 'notepad', 'steam', 'spotify'"""
    try:
        subprocess.Popen(
            name,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS
        )
        return f"Opened {name}"
    except FileNotFoundError:
        pass
    except Exception as e:
        return f"Could not open {name}: {e}"

    registry_match = _find_via_registry(name)
    if registry_match:
        try:
            subprocess.Popen(
                registry_match,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS
            )
            return f"Opened {name} from {registry_match}"
        except Exception as e:
            return f"Found {name} but could not open it: {e}"

    glob_match = _find_via_glob(name)
    if glob_match:
        try:
            subprocess.Popen(
                glob_match,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS
            )
            return f"Opened {name} from {glob_match}"
        except Exception as e:
            return f"Found {name} but could not open it: {e}"

    return f"Could not find '{name}'. Try providing the full path to the program's .exe file instead."


# CLOSE PROGRAM
# Apps that minimize to the system tray when you click X instead of really quitting.
# Only these get force-closed if the polite close request doesn't end them; for
# everything else (e.g. Notepad with unsaved text) we leave any "Save changes?"
# prompt alone so no work is lost.
_TRAY_APPS = {
    "discord", "spotify", "steam", "telegram", "whatsapp", "slack",
    "teams", "skype", "zoom", "epicgameslauncher", "onedrive",
}


def _is_running(exe_name: str) -> bool:
    check = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
        capture_output=True, text=True, timeout=10
    )
    return exe_name.lower() in check.stdout.lower()


@tool
def close_program(name: str) -> str:
    """Closes a running program by name, e.g. 'discord', 'notepad', 'chrome'.
    Sends a polite close request first (same as clicking the window's X), so apps with
    unsaved work can show their own save prompt. Apps that just hide in the system tray
    instead of quitting (like Discord) are then force-closed."""
    base_name = name.lower().replace(".exe", "").strip()
    exe_name = f"{base_name}.exe"

    try:
        first = subprocess.run(
            ["taskkill", "/IM", exe_name],
            capture_output=True, text=True, timeout=10
        )
        output = (first.stdout + first.stderr).lower()

        if first.returncode != 0 and "not found" in output:
            return f"'{name}' doesn't appear to be running."

        time.sleep(1.5)

        if not _is_running(exe_name):
            return f"Closed {name}."

        if base_name in _TRAY_APPS:
            forced = subprocess.run(
                ["taskkill", "/F", "/IM", exe_name],
                capture_output=True, text=True, timeout=10
            )
            if forced.returncode == 0:
                return f"{name} only minimized to the tray, so I force-closed it."
            return f"Could not close {name}: force-close failed."

        return (f"Asked {name} to close, but it's still open - it may be waiting on a "
                f"'Save changes?' prompt. Check the window.")

    except subprocess.TimeoutExpired:
        return f"Timed out while trying to close {name}."
    except Exception as e:
        return f"Could not close {name}: {e}"


# CREATE FOLDER
@tool
def create_folder(path: str) -> str:
    """Creates a new folder at the given full path, e.g. C:\\Users\\HaroonSheikh\\Desktop\\NewFolder"""
    try:
        os.makedirs(path, exist_ok=False)
        return f"Created folder: {path}"
    except FileExistsError:
        return f"A folder already exists at: {path}"
    except Exception as e:
        return f"Could not create folder: {e}"


# CREATE FILE
@tool
def create_file(path: str, content: str = "") -> str:
    """Creates a new empty file (or with optional starter text content) at the given full path, e.g. C:\\Users\\HaroonSheikh\\Desktop\\notes.txt"""
    try:
        if os.path.exists(path):
            return f"A file already exists at: {path}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Created file: {path}"
    except Exception as e:
        return f"Could not create file: {e}"
    


#GMAIL FUNCTION

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

def get_gmail_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else: 
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)




#CHECK EMAILS
@tool
def check_new_emails(_: str = "") -> str:
    """Checks Gmail for the most recent unread emails and returns sender and subject for each"""
    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me", labelIds=["UNREAD"], maxResults=10
        ).execute()

        messages = results.get("messages", [])

        if not messages:
            return "No new unread emails."

        summary = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()

            headers = msg_data["payload"]["headers"]
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown sender")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No subject)")

            summary.append(f"From: {sender} | Subject: {subject}")

        return "New emails:\n" + "\n".join(summary)

    except Exception as e:
        return f"Could not check emails: {e}"
    




PRIORITY_SENDER_FILE = "priority_sender.json"

def _load_priority_senders():
    try:
        with open(PRIORITY_SENDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save_priority_senders(senders):
    with open(PRIORITY_SENDER_FILE, "w", encoding="utf-8") as f:
        json.dump(senders, f, indent=2)


@tool
def add_priority_sender(email: str) -> str:
    """Adds an email address to the priority senders list, so future emails from them trigger an urgent notification"""
    senders = _load_priority_senders()
    email = email.strip().lower()

    if email in senders:
        return f"{email} is already on the priority list."

    senders.append(email)
    _save_priority_senders(senders)
    return f"Added {email} to priority senders."

@tool
def remove_priority_sender(email: str) -> str:
    """Removes an email address from the priority senders list"""
    senders = _load_priority_senders()
    email = email.strip().lower()

    if email not in senders:
        return f"{email} was not on the priority list."

    senders.remove(email)
    _save_priority_senders(senders)
    return f"Removed {email} from priority senders."


@tool
def view_priority_senders(_: str = "") -> str:
    """Shows the current list of priority email senders"""
    senders = _load_priority_senders()
    if not senders:
        return "No priority senders set."
    return "Priority senders:\n" + "\n".join(f"- {s}" for s in senders)



@tool
def search_emails(query: str) -> str:
    """Searches the user's entire Gmail mailbox (including inbox, spam, and other folders) for emails matching a query. 
    Supports natural keywords (e.g. 'parking permit') or Gmail search syntax (e.g. 'from:boss@company.com', 'subject:invoice'). 
    Returns sender, subject, and date for matching emails."""
    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me", q=query, maxResults=10
        ).execute()

        messages = results.get("messages", [])

        if not messages:
            return f"No emails found matching '{query}'."

        summary = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = msg_data["payload"]["headers"]
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown sender")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No subject)")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown date")

            summary.append(f"From: {sender} | Subject: {subject} | Date: {date}\n  Message ID: {msg['id']}")

        return f"Found {len(messages)} email(s) matching '{query}':\n\n" + "\n\n".join(summary)

    except Exception as e:
        return f"Could not search emails: {e}"
    



@tool
def read_email(query_or_id: str) -> str:
    """Reads the full content of a specific email and returns it for summarization. 
    Accepts either a Gmail message ID, a search query (e.g. 'latest email from boss@company.com'), 
    or generic phrases like 'last email' / 'most recent email' to get the single newest email in the inbox."""
    try:
        service = get_gmail_service()

        generic_latest_phrases = ["last email", "latest email", "most recent email", "newest email"]
        is_generic_latest = query_or_id.strip().lower() in generic_latest_phrases

        message_id = query_or_id
        if is_generic_latest:
            results = service.users().messages().list(
                userId="me", maxResults=1
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                return "No emails found in the inbox."
            message_id = messages[0]["id"]
        elif "@" in query_or_id or len(query_or_id) < 16:
            results = service.users().messages().list(
                userId="me", q=query_or_id, maxResults=1
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                return f"No email found matching '{query_or_id}'."
            message_id = messages[0]["id"]

        msg_data = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

        headers = msg_data["payload"]["headers"]
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown sender")
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No subject)")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown date")

        body = _extract_email_body(msg_data["payload"])

        return f"From: {sender}\nSubject: {subject}\nDate: {date}\n\nContent:\n{body}"

    except Exception as e:
        return f"Could not read email: {e}"


def _extract_email_body(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        for part in payload["parts"]:
            if "parts" in part:
                result = _extract_email_body(part)
                if result:
                    return result
    else:
        if "data" in payload.get("body", {}):
            data = payload["body"]["data"]
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return "(Could not extract email body)"





LAST_EMAIL_CHECKER_FILE = "last_email_check.json"


def _get_last_check_time():
    try:
        with open(LAST_EMAIL_CHECKER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("last_check")
    except FileNotFoundError:
        return None


def _set_last_check_time(timestamp):
    with open(LAST_EMAIL_CHECKER_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_check": timestamp}, f)

def check_priority_emails_background():
    """Checks for new emails and fires notification for priority senders. Meant to run in a background thread, not as an agent tool."""
    try:
        service = get_gmail_service()
        priority_senders = _load_priority_senders()

        last_check = _get_last_check_time()
        query = f"after:{last_check}" if last_check else "newer_than:1d"

        results = service.users().messages().list(
            userId="me", q=query, maxResults=20
        ).execute()

        messages = results.get("messages", [])

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()

            headers = msg_data["payload"]["headers"]
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown sender")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No subject)")

            sender_email = sender.split("<")[-1].replace(">", "").strip().lower()

            if any(priority in sender_email for priority in priority_senders):
                notification.notify(
                    title=f"Priority Email: {sender}",
                    message=subject,
                    timeout=10
                )
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

        _set_last_check_time(int(time.time()))
    except Exception as e:
        print(f"[Email checker error] {e}")





#CALENDER FUNCTION
def get_calendar_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)



@tool
def check_calendar(_: str = "") -> str:
    """Checks the user's Google Calendar for upcoming events in the next 7 days"""
    try:
        service = get_calendar_service()

        now = datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found."

        summary = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            title = event.get("summary", "(No title)")
            summary.append(f"- {title} at {start}")

        return "Upcoming events:\n" + "\n".join(summary)

    except Exception as e:
        return f"Could not check calendar: {e}"


@tool
def add_calendar_event(text: str) -> str:
    """Creates a new calendar event. Provide the event description including a natural language time, 
    e.g. 'meeting with boss tomorrow at 3pm' or 'dentist appointment next Monday at 10am'"""
    try:
        parsed_time = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
        if not parsed_time:
            return f"Couldn't understand the time in: '{text}'. Try being more specific, e.g. 'meeting tomorrow at 3pm'."

        service = get_calendar_service()

        end_time = parsed_time + timedelta(hours=1)

        event = {
            "summary": text,
            "start": {"dateTime": parsed_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        }

        created_event = service.events().insert(calendarId="primary", body=event).execute()

        return f"Event created: '{text}' at {parsed_time.strftime('%Y-%m-%d %H:%M')}"

    except Exception as e:
        return f"Could not create event: {e}"




#FUNTION TOGGLE ON/OFF
@tool
def toggle_feature(feature_and_state: str) -> str:
    """Enables or disables a feature category. Provide the feature name and desired state, 
    e.g. 'gmail off', 'reminders on', 'file_management false'. Valid features: research, 
    browser, notes, reminders, file_management, gmail, calendar, weather, system_control, 
    chat_history. Changes take effect after restarting the assistant."""
    try:
        parts = feature_and_state.strip().lower().split()
        if len(parts) < 2:
            return "Please specify both a feature and a state, e.g. 'gmail off'."

        feature = parts[0]
        state_word = parts[1]

        valid_features = ["research", "browser", "notes", "reminders", "file_management", "gmail", "calendar", "weather", "system_control", "chat_history"]
        if feature not in valid_features:
            return f"'{feature}' isn't a recognized feature. Valid options: {', '.join(valid_features)}."

        state = state_word in ["on", "true", "enable", "enabled"]

        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        config[feature] = state
        
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        return f"{feature} has been turned {'on' if state else 'off'}. Restart the assistant for this to take effect."

    except Exception as e:
        return f"Could not update feature setting: {e}"



#DAILY BRIEFING FEATURE (weather + reminders + priority emails + calendar)

CONFIG_FILE = "config.json"

def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _auto_detect_location():
    """Free, no-key IP-based geolocation. Best-effort only — used as a fallback
    when the user hasn't set a location manually."""
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return {
                "city": data.get("city", "Unknown"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
            }
    except Exception:
        pass
    return None


def _get_location():
    """Returns the user's saved location, auto-detecting and saving it on first use."""
    config = _load_config()
    location = config.get("location")

    if location and location.get("lat") is not None and location.get("lon") is not None:
        return location

    detected = _auto_detect_location()
    if detected:
        config["location"] = detected
        _save_config(config)
        return detected

    return None


@tool
def set_location(city: str) -> str:
    """Sets the user's location for weather in the daily briefing, e.g. 'set my location to Lahore'.
    Overrides auto-detected location. Provide just the city name (optionally with country, 
    e.g. 'Lahore, Pakistan' for better accuracy)."""
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=5,
        )
        data = resp.json()
        results = data.get("results")

        if not results:
            return f"Couldn't find a location matching '{city}'. Try a different spelling or add the country, e.g. '{city}, Pakistan'."

        match = results[0]
        location = {
            "city": match.get("name"),
            "lat": match.get("latitude"),
            "lon": match.get("longitude"),
        }

        config = _load_config()
        config["location"] = location
        _save_config(config)

        return f"Location set to {location['city']}."

    except Exception as e:
        return f"Could not set location: {e}"


# WMO weather codes -> plain description (used by Open-Meteo, which needs no API key)
_WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy with frost",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "light rain showers", 81: "rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}


def _get_weather():
    """Fetches current + today's forecast via Open-Meteo (free, no API key required)."""
    location = _get_location()
    if not location:
        return None, "Couldn't determine your location for weather. Try 'set my location to <city>'."

    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["lat"],
                "longitude": location["lon"],
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
            },
            timeout=5,
        )
        data = resp.json()

        current_temp = data["current"]["temperature_2m"]
        weather_code = data["current"]["weather_code"]
        desc = _WEATHER_CODES.get(weather_code, "unknown conditions")
        high = data["daily"]["temperature_2m_max"][0]
        low = data["daily"]["temperature_2m_min"][0]

        summary = (
            f"{location['city']}: {current_temp}°C now, {desc}. "
            f"Today's high {high}°C / low {low}°C."
        )
        return summary, None

    except Exception as e:
        return None, f"Could not fetch weather: {e}"


def _get_today_reminders():
    try:
        with open("reminders.json", "r", encoding="utf-8") as f:
            reminders = json.load(f)
    except FileNotFoundError:
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    return [
        r for r in reminders
        if not r.get("notified") and r.get("due_time", "").startswith(today)
    ]


def _get_unread_priority_emails():
    try:
        service = get_gmail_service()
        priority_senders = _load_priority_senders()

        if not priority_senders:
            return [], None

        results = service.users().messages().list(
            userId="me", labelIds=["UNREAD"], maxResults=20
        ).execute()
        messages = results.get("messages", [])

        matches = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()

            headers = msg_data["payload"]["headers"]
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown sender")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No subject)")
            sender_email = sender.split("<")[-1].replace(">", "").strip().lower()

            if any(priority in sender_email for priority in priority_senders):
                matches.append(f"From: {sender} | Subject: {subject}")

        return matches, None

    except Exception as e:
        return [], f"Could not check priority emails: {e}"


def _get_today_events():
    try:
        service = get_calendar_service()

        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat() + "Z",
            timeMax=end_of_day.isoformat() + "Z",
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        summaries = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            title = event.get("summary", "(No title)")
            summaries.append(f"{title} at {start}")

        return summaries, None

    except Exception as e:
        return [], f"Could not check calendar: {e}"


@tool
def daily_briefing(_: str = "") -> str:
    """Gives a combined daily briefing: current weather, today's reminders, unread emails 
    from priority senders, and today's calendar events. Use this when the user asks for 
    their 'daily briefing', 'daily brief', 'morning update', or a summary of their day."""
    config = _load_config()
    lines = []

    if config.get("weather", True):
        weather_summary, weather_err = _get_weather()
        lines.append(f"Weather: {weather_summary if weather_summary else weather_err}")

    if config.get("reminders", True):
        todays_reminders = _get_today_reminders()
        if todays_reminders:
            reminder_lines = "\n".join(f"  - {r['message']} at {r['due_time']}" for r in todays_reminders)
            lines.append(f"Reminders today ({len(todays_reminders)}):\n{reminder_lines}")
        else:
            lines.append("Reminders today: none.")

    if config.get("gmail", True):
        priority_emails, email_err = _get_unread_priority_emails()
        if email_err:
            lines.append(f"Priority emails: {email_err}")
        elif priority_emails:
            email_lines = "\n".join(f"  - {e}" for e in priority_emails)
            lines.append(f"Unread priority emails ({len(priority_emails)}):\n{email_lines}")
        else:
            lines.append("Unread priority emails: none.")

    if config.get("calendar", True):
        events, cal_err = _get_today_events()
        if cal_err:
            lines.append(f"Calendar: {cal_err}")
        elif events:
            event_lines = "\n".join(f"  - {e}" for e in events)
            lines.append(f"Today's events ({len(events)}):\n{event_lines}")
        else:
            lines.append("Today's events: none.")

    return "Daily Briefing\n" + ("-" * 20) + "\n" + "\n\n".join(lines)



# SYSTEM CONTROL (volume / brightness / battery)

def _get_volume_interface():
    # The agent runs tools on a different thread than the main script, and Windows
    # COM must be initialized once per thread before pycaw can be used.
    try:
        comtypes.CoInitialize()
    except OSError:
        pass  # already initialized on this thread
    speakers = AudioUtilities.GetSpeakers()
    return speakers.EndpointVolume


@tool
def set_volume(percent: str) -> str:
    """Sets the system volume to a specific percentage (0-100), e.g. '50'.
    Also accepts 'mute' or 'unmute' as the value."""
    try:
        volume = _get_volume_interface()

        if percent.strip().lower() == "mute":
            volume.SetMute(1, None)
            return "Volume muted."
        if percent.strip().lower() == "unmute":
            volume.SetMute(0, None)
            return "Volume unmuted."

        level = int(percent.strip().rstrip("%"))
        if not 0 <= level <= 100:
            return "Volume must be between 0 and 100."

        volume.SetMasterVolumeLevelScalar(level / 100, None)
        return f"Volume set to {level}%."

    except ValueError:
        return f"'{percent}' isn't a valid volume level. Use a number 0-100, or 'mute'/'unmute'."
    except Exception as e:
        return f"Could not set volume: {e}"


@tool
def get_volume(_: str = "") -> str:
    """Gets the current system volume level and mute status."""
    try:
        volume = _get_volume_interface()
        level = round(volume.GetMasterVolumeLevelScalar() * 100)
        muted = "muted" if volume.GetMute() else "not muted"
        return f"Current volume: {level}% ({muted})."
    except Exception as e:
        return f"Could not get volume: {e}"


@tool
def set_brightness(percent: str) -> str:
    """Sets the screen brightness to a specific percentage (0-100), e.g. '70'."""
    try:
        level = int(percent.strip().rstrip("%"))
        if not 0 <= level <= 100:
            return "Brightness must be between 0 and 100."

        sbc.set_brightness(level)
        return f"Brightness set to {level}%."

    except ValueError:
        return f"'{percent}' isn't a valid brightness level. Use a number 0-100."
    except Exception as e:
        return f"Could not set brightness: {e}. Note: this may not work on desktop monitors without DDC/CI support."


@tool
def get_brightness(_: str = "") -> str:
    """Gets the current screen brightness level."""
    try:
        level = sbc.get_brightness()[0]
        return f"Current brightness: {level}%."
    except Exception as e:
        return f"Could not get brightness: {e}. Note: this may not work on desktop monitors without DDC/CI support."


@tool
def get_battery_status(_: str = "") -> str:
    """Gets the current battery percentage and charging status. Only relevant for laptops."""
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected - this may be a desktop PC."

        charging = "charging" if battery.power_plugged else "not charging"
        return f"Battery: {battery.percent}% ({charging})."

    except Exception as e:
        return f"Could not get battery status: {e}"



# CHAT HISTORY SEARCH (reads the daily logs main.py writes to chat_logs/)

CHAT_LOG_DIR = "chat_logs"


@tool
def search_chat_history(query: str) -> str:
    """Searches past daily chat logs for a keyword, phrase, or day (e.g. 'yesterday').
    Use this when the user asks to recall, remember, or reference something from a
    previous day - today's conversation is already in context, no need to search for that."""
    if not os.path.isdir(CHAT_LOG_DIR):
        return "No chat history has been saved yet."

    log_files = sorted(glob.glob(os.path.join(CHAT_LOG_DIR, "chat_*.txt")), reverse=True)
    if not log_files:
        return "No chat history has been saved yet."

    query_lower = query.lower().strip()

    if "yesterday" in query_lower:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        target = os.path.join(CHAT_LOG_DIR, f"chat_{yesterday}.txt")
        if not os.path.exists(target):
            return "There's no saved chat from yesterday."
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        return content[-3000:] if len(content) > 3000 else content

    matches = []
    for filepath in log_files:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                date_label = os.path.basename(filepath).replace("chat_", "").replace(".txt", "")
                context = "".join(lines[max(0, i - 1):i + 2]).strip()
                matches.append(f"[{date_label}]\n{context}")

    if not matches:
        return f"No matches found for '{query}' in saved chat history."

    result = "\n\n".join(matches[:8])
    return result[:3000] + "... [truncated]" if len(result) > 3000 else result
