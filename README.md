# 🤖 Personal AI Assistant

A free, local, PC-based AI agent built with LangChain and Groq that actually *does*
things on your computer — not just answers questions. Manages files, checks email,
sets reminders, controls your system, and more, all through natural conversation
in your terminal.

> 🚧 **Work in progress.** This is an actively evolving personal/learning project,
> not a finished product. Features are being added and refined regularly, things
> may break, and the code is not yet polished. Built in the open as a way to learn
> AI agent development from scratch.

Built with an eye toward eventually being usable by non-technical people too, not
just developers.

## 💡 Why this exists

Most "AI assistants" just talk. This one acts: it opens and closes real programs,
reads and searches your actual inbox, moves files on your real filesystem, and
controls your actual system volume — with safety rails (confirmations, a file-path
whitelist, no permanent deletes) so it doesn't do anything destructive by accident.

## ✨ Features

- 🔎 **Research** — web search (Tavily), Wikipedia, save findings to a file
- 🌐 **Browser** — open websites, search Google, search *and play* YouTube videos, open Gmail
- 📝 **Notes** — quick timestamped notes
- ⏰ **Reminders** — natural-language time parsing ("in 20 minutes", "tomorrow at 5pm"),
  real Windows notifications + sound, runs in the background even when you're not
  actively chatting
- 📁 **File & folder management** — find (fuzzy search), open, copy, move, rename,
  delete (to Recycle Bin, never permanent), create — with confirmation prompts for
  anything destructive and a safe-folder whitelist
- 🚀 **Launch & close programs** — finds apps via the Windows registry and install
  folders (handles auto-updating apps like Discord that change version folders);
  closing sends a graceful close request first, so apps with unsaved work can
  prompt you, and only force-closes apps known to just minimize to the tray
- 📧 **Gmail** — check unread mail, full mailbox search, read & summarize a specific
  email, flag priority senders (with background monitoring + notifications)
- 📅 **Calendar** — check upcoming events, add new ones with natural-language time
- ☀️ **Daily briefing** — weather, today's reminders, unread priority emails, and
  today's events, combined into one summary
- 🌦️ **Weather** — auto-detects your location (or set it manually), no API key needed
- 🔊 **System control** — volume (incl. mute), screen brightness, battery status
- 🧠 **Chat history** — every conversation is logged to a daily file and searchable
  on request ("what did we talk about yesterday?"), so context persists across
  sessions without bloating every request with old data
- 🎚️ **Feature toggles** — turn any category on/off via `config.json` or just by
  asking in chat

## 🛡️ Reliability

Built to survive the realities of running on **free API tiers**:

- **Three-tier model fallback** — if Groq hits a rate limit, it silently retries
  with a more capable (but slower) Groq model, then falls back to Google Gemini
  before giving up
- **Dynamic tool loading** — only sends the tool categories relevant to each
  message instead of all of them every time, cutting token usage significantly
- **Duplicate-action protection** — if a retry happens after a tool already ran
  successfully (e.g. an app already opened), it won't fire that tool again
- **Malformed tool-call detection** — catches when a model hallucinates a fake
  function call instead of actually invoking a tool, and retries properly instead
  of showing you garbage

## 🛠️ Setup

See [`SETUP.md`](./SETUP.md) for full step-by-step instructions, including:

1. Installing Python & dependencies (`pip install -r requirements.txt`)
2. Getting free API keys (Groq, Tavily, Gemini)
3. Setting up Gmail/Calendar OAuth
4. Running it (`python main.py`)
5. (Optional) Setting up background reminders/email-checking via Windows Task
   Scheduler, so they keep working even when you're not actively chatting

## ⚙️ Tech stack

- **LangChain** (`create_agent`) for the agent loop
- **Groq** (`llama-3.3-70b-versatile`, `openai/gpt-oss-120b`) as the primary LLM,
  free tier
- **Google Gemini** (`gemini-3.1-flash-lite`) as a fallback LLM, free tier
- **Tavily** for web search, **Wikipedia** via `langchain-community`
- **Google APIs** (Gmail + Calendar) via OAuth2
- **Open-Meteo** for weather (no API key required)
- **pycaw**, **screen-brightness-control**, **psutil** for system control
- **dateparser**, **plyer**, **send2trash**, **fuzzywuzzy** for reminders,
  notifications, safe deletion, and fuzzy file matching

## 🗺️ Project status

**Phase 1 (core capabilities)** is essentially complete and actively being
hardened. **Phase 2** (voice commands, a system tray presence) is being explored
next, alongside rounding out the remaining backlog (to-do lists, clipboard tools,
and more).

This is Windows-only for now (`os.startfile`, `winsound`, registry lookups), with
cross-platform support a possible future goal.

## 📓 A note on the code

This project was built by a beginner, largely through iterative AI-assisted
development — asking Claude to write, explain, and debug the code. It's a learning
project first, and the codebase reflects that: functional and continuously
improving, not polished or "best practice" throughout.

## 📄 License

Personal project — no license specified yet.
