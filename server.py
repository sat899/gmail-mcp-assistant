import os.path
import base64
from email.message import EmailMessage
from fastmcp import FastMCP
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.compose']

# Initialize FastMCP
mcp = FastMCP("Gmail Assistant")

def get_gmail_service():
    """Handles Gmail Auth (Standard Logic)"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

@mcp.tool()
def get_unread_emails(max_results: int = 5):
    """Fetches a list of unread emails from the user's inbox."""
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', q='is:unread', maxResults=max_results).execute()
    messages = results.get('messages', [])
    
    email_list = []
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = m['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
        
        email_list.append({
            "id": msg['id'],
            "threadId": msg['threadId'],
            "from": sender,
            "subject": subject,
            "snippet": m.get('snippet', '')
        })
    return email_list

@mcp.tool()
def create_draft_reply(thread_id: str, reply_text: str):
    """Creates a draft reply for a specific thread."""
    service = get_gmail_service()
    
    # Get the original message to extract the 'To' address and 'Subject'
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    original_msg = thread['messages'][-1] # Get the latest message in thread
    headers = original_msg['payload']['headers']
    
    target_email = next(h['value'] for h in headers if h['name'] == 'From')
    subject = next(h['value'] for h in headers if h['name'] == 'Subject')
    if not subject.startswith("Re:"):
        subject = f"Re: {subject}"

    # Build the email
    message = EmailMessage()
    message.set_content(reply_text)
    message['To'] = target_email
    message['Subject'] = subject
    message['In-Reply-To'] = original_msg.get('id')
    message['References'] = original_msg.get('id')

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {'message': {'threadId': thread_id, 'raw': encoded_message}}
    
    draft = service.users().drafts().create(userId='me', body=create_message).execute()
    return f"Success: Draft created (ID: {draft['id']}) in reply to {target_email}"

if __name__ == "__main__":
    mcp.run()