# Rebuilding the assistant on a fresh Windows install

1. **Python** - install Python 3.13 from python.org (tick "Add python.exe to PATH").
2. **Folder** - unzip so the project lives at `Desktop\bling blong`.
3. **Virtual environment + packages** (PowerShell, inside the folder):
       python -m venv venv
       .\venv\Scripts\Activate.ps1
       pip install -r requirements.txt
   If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
4. **API keys** - copy `.env.example` to `.env` and fill in:
   - GROQ_API_KEY   -> console.groq.com  (API Keys)
   - TAVILY_API_KEY -> app.tavily.com
   - GEMINI_API_KEY -> aistudio.google.com (Get API key)
5. **Gmail + Calendar** - in Google Cloud Console: enable the Gmail API and Google
   Calendar API, create an OAuth client ID (type: Desktop app), download it as
   `credentials.json` into this folder, add your Google account as a test user. Then:
       python gmail_auth_setup.py
   (creates token.json; in Testing mode it expires every 7 days - just re-run it)
6. **Run it**: `python main.py`
7. **Background reminders / priority-email alerts** - recreate the Task Scheduler task:
   - Trigger: At log on
   - Action: Start a program
       Program:   <folder>\venv\Scripts\pythonw.exe
       Arguments: background_services.py
       Start in:  <folder>
8. Priority senders were not restored - re-add them by chatting
   ("flag <email> as priority").
