"""
background_services.py

Runs the assistant's always-on background features (reminders + Gmail priority
checking) WITHOUT the interactive chat loop. This is meant to be launched
automatically by Windows Task Scheduler at log on, so reminders and priority
email alerts keep working even if you never open a chat terminal.

This script does NOT use the LLM/agent at all -- it just reads/writes the
same JSON files tools.py uses, and fires real Windows notifications, exactly
like main.py did before. Nothing about how reminders/priority emails behave
has changed, this is purely a relocation.
"""

import json
import threading
import time
from datetime import datetime

from dotenv import load_dotenv
from plyer import notification
import winsound

from tools import check_priority_emails_background

load_dotenv()

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)


def check_reminders():
    while True:
        try:
            with open("reminders.json", "r", encoding="utf-8") as f:
                reminders = json.load(f)

            updated = False
            for r in reminders:
                if not r["notified"]:
                    due = datetime.strptime(r["due_time"], "%Y-%m-%d %H:%M:%S")
                    if datetime.now() >= due:
                        notification.notify(
                            title="Reminder",
                            message=r["message"],
                            timeout=10
                        )
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                        r["notified"] = True
                        updated = True

            if updated:
                with open("reminders.json", "w", encoding="utf-8") as f:
                    json.dump(reminders, f, indent=2)

        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[Reminder checker error] {e}")

        time.sleep(30)


def check_emails_periodically():
    while True:
        check_priority_emails_background()
        time.sleep(60)


if __name__ == "__main__":
    threads_started = []

    if config.get("reminders", True):
        t = threading.Thread(target=check_reminders, daemon=True)
        t.start()
        threads_started.append("reminders")

    if config.get("gmail", True):
        t = threading.Thread(target=check_emails_periodically, daemon=True)
        t.start()
        threads_started.append("gmail priority checker")

    print(f"Background services running: {', '.join(threads_started) if threads_started else 'none enabled in config.json'}")

    # Keep the main thread alive forever so the daemon threads keep running.
    while True:
        time.sleep(3600)
