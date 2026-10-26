from google_auth_oauthlib.flow import InstalledAppFlow

# Keep this list identical to GMAIL_SCOPES in tools.py, or new scopes
# silently won't be requested.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GMAIL_SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as token:
    token.write(creds.to_json())

print("Authentication successful! token.json has been created.")
