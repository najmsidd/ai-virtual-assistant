import streamlit as st
from gpt4all import GPT4All
import re
import os
import json
import fitz
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import threading
import datetime
import time
import dateparser
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Page configuration
st.set_page_config(
    page_title="AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .chat-container {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.8rem;
        border-radius: 15px 15px 5px 15px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
    }
    
    .assistant-message {
        background: #ffffff;
        color: #333;
        padding: 0.8rem;
        border-radius: 15px 15px 15px 5px;
        margin: 0.5rem 0;
        max-width: 80%;
        border: 1px solid #e1e5e9;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    
    .task-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #28a745;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        color: black;
    }
    
    .reminder-card {
        border-left-color: #ffc107 !important;
    }
    
    .email-card {
        border-left-color: #dc3545 !important;
    }
    
    .calendar-card {
        border-left-color: #007bff !important;
    }
    
    .stats-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .upload-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px dashed #dee2e6;
        text-align: center;
        margin: 1rem 0;
    }
    
    .section-header {
        color: #495057;
        border-bottom: 2px solid #e9ecef;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize model
@st.cache_resource
def load_model():
    model_path = r"C:/Users/najms/AppData/Local/nomic.ai/GPT4All/Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf"
    return GPT4All(model_name=model_path)

model = load_model()

def reminder_checker():
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        reminders_triggered = []

        try:
            with open("memory.json", "r+") as f:
                data = json.load(f)
                new_tasks = []

                for task in data["tasks"]:
                    if task.get("type") == "reminder" and not task.get("notified"):
                        task_time = f"{task['date']} {task['time']}"
                        if task_time == now:
                            reminders_triggered.append(task)
                            task["notified"] = True
                    new_tasks.append(task)

                f.seek(0)
                json.dump({"tasks": new_tasks}, f, indent=2)
                f.truncate()

        except Exception as e:
            print("Reminder check error:", e)

        if reminders_triggered:
            print(f"[{now}] Triggered reminders: {[t['task'] for t in reminders_triggered]}")

        if reminders_triggered:
            try:
                triggered_file = "triggered_reminders.json"
                existing_triggered = []
                
                if os.path.exists(triggered_file):
                    with open(triggered_file, "r") as f:
                        try:
                            existing_triggered = json.load(f)
                        except:
                            existing_triggered = []
                
                for reminder in reminders_triggered:
                    reminder["triggered_at"] = now
                    existing_triggered.append(reminder)
                
                with open(triggered_file, "w") as f:
                    json.dump(existing_triggered, f, indent=2)
                    
            except Exception as e:
                print("Error writing triggered reminders:", e)

        time.sleep(60)

# Start reminder thread
if "reminder_thread_started" not in st.session_state:
    threading.Thread(target=reminder_checker, daemon=True).start()
    st.session_state.reminder_thread_started = True

if "displayed_reminders" not in st.session_state:
    st.session_state.displayed_reminders = set()

# Initialize session state
if "chat" not in st.session_state:
    st.session_state.chat = []

if "pending_reminders" not in st.session_state:
    st.session_state.pending_reminders = []

# Create necessary files
if not os.path.exists("memory.json"):
    with open("memory.json", "w") as f:
        json.dump({"tasks": []}, f)

if not os.path.exists("chat_memory.json"):
    with open("chat_memory.json", "w") as f:
        json.dump({"conversations": []}, f)

# Load memory
with open("memory.json", "r") as f:
    memory = json.load(f)

def save_to_chat_memory(user_message, assistant_response):
    try:
        with open("chat_memory.json", "r+") as f:
            data = json.load(f)

            conversation_entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "user": user_message,
                "assistant": assistant_response
            }

            data["conversations"].append(conversation_entry)

            if len(data["conversations"]) > 100:
                data["conversations"] = data["conversations"][-100:]
            
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
    
    except Exception as e:
        print(f"Error saving to chat memory: {e}")

def get_relevant_chat_memory(current_input, limit=10):
    try:
        with open("chat_memory.json", "r") as f:
            data = json.load(f)
            conversations = data.get("conversations", [])

            if not conversations:
                return []
            
            keywords = current_input.lower().split()
            relevant_conversations = []

            for conv in conversations[-50:]:
                user_text = conv["user"].lower()
                assistant_text = conv["assistant"].lower()

                if any(keyword in user_text or keyword in assistant_text for keyword in keywords):
                    relevant_conversations.append(conv)

        return relevant_conversations[-limit:]
    except Exception as e:
        print(f"Error retrieving chat memory: {e}")
        return []

def log_to_google_sheets(row):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key("1T58c_RZNJ1dfB7KiidmoYE2Fn8fiwgeH4WXfdmeYUOw").sheet1

    if sheet.row_values(1) == []:
        headers = ["Take Type", "To/Person/URL", "Subject/Date", "Body/Time/Summary"]
        sheet.insert_row(headers, index=1)

    sheet.append_row(row)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token():
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('gmail_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service

def send_email_via_gmail(to_email, subject, body):
    try:
        if not to_email or not subject or not body:
            return "Error: Missing email details (to, subject, or body)"

        service = authenticate_gmail()

        message_text = f"""To: {to_email}
Subject: {subject}
Content-Type: text/plain; charset=utf-8

{body}"""
        
        message_bytes = message_text.encode('utf-8')
        raw_message = base64.urlsafe_b64encode(message_bytes).decode('ascii')
        
        message_body = {'raw': raw_message}
        send_message = service.users().messages().send(
            userId = "me",
            body = message_body
        ).execute()

        return f"Email successfully sent! Message ID: {send_message['id']}"
    
    except Exception as e:
        return f"Failed to send email. Error: {str(e)}"

def extract_from_text(user_input):
    prompt = f"""
You are a task extraction assistant. A user will give you a message, and you must extract the task details in JSON format.

Your job is to return a dictionary with:
- type: one of ["email", "calendar", "url_summary", "pdf_summary", "reminder", "general", "calendar_query", "memory_query"]
- to (for emails)
- subject (for emails)
- body (for emails)
- person (for calendar)
- date (for calendar/reminder/calendar_query)
- time (for calendar/reminder)
- url (for url_summary)
- task (for reminder)
- prompt (for general chat or unknown)
- query (for memory_query — the actual user question)
- filter (for memory_query — one of ["email", "calendar", "reminder", "all"])
- query_date: (if mentioned, return the date in YYYY-MM-DD format only (e.g., "2025-06-04")).
- range (for memory_query — one of ["last_week", "last_month"], optional)

Examples:

Message: "Schedule meeting with Aayush on 2025-06-10 at 15:00"
=> type: "calendar", person: "Aayush", date: "2025-06-10", time: "15:00"

Message: "What meetings do I have today?"
=> type: "calendar_query", date: "<today's date>"

Message: "What tasks did I give you last week?"
=> type: "memory_query", query: "What tasks did I give you last week?", filter: "all", range: "last_week"

Message: "Show me my email tasks from June 3, 2025"
=> type: "memory_query", query: "Show me my email tasks from June 3, 2025", filter: "email", query_date: "2025-06-03"

If any field is not needed, return it as null.

Respond ONLY with valid JSON. Do not include explanations or markdown.

Message: "{user_input}"
Return JSON only.
"""

    with model.chat_session() as session:
        result = session.generate(prompt=prompt)

    try:
        data = json.loads(result)
        if data.get("type") == "reminder":
            if not all([data.get("task"), data.get("date"), data.get("time")]):
                data["type"] = "general"
                data["prompt"] = user_input
    except:
        data = {"type": "general", "prompt": user_input}

    return data

def build_contexual_prompt(user_input, history_limit=5):
    past_user_msgs = [msg for sender, msg in st.session_state.chat if sender == "You"]
    recent_msgs = past_user_msgs[-history_limit:]

    relevant_memory = get_relevant_chat_memory(user_input)

    history_text = "\n".join(f"User: {msg}" for msg in recent_msgs)

    memory_context = ""
    if relevant_memory:
        for conv in relevant_memory:
            memory_context += f"User: {conv['user']}\nAssistant: {conv['assistant'][:200]}...\n"
    
    return f"""
You are a helpful assistant with both short-term and long-term memory.

Here is the recent conversation from this session:
{history_text}
{memory_context}

Now respond to the user's new message, taking into account both recent context and relevant past conversations:
User: {user_input}
Assistant:"""

def check_and_display_triggered_reminders():
    triggered_file = "triggered_reminders.json"
    if os.path.exists(triggered_file):
        try:
            with open(triggered_file, "r") as f:
                triggered_reminders = json.load(f)
            
            if not triggered_reminders:
                return False
            
            new_reminders = []
            for reminder in triggered_reminders:
                reminder_id = f"{reminder['task']}_{reminder['date']}_{reminder['time']}_{reminder.get('triggered_at', '')}"
                if reminder_id not in st.session_state.displayed_reminders:
                    new_reminders.append(reminder)
                    st.session_state.displayed_reminders.add(reminder_id)
            
            if new_reminders:
                for reminder in new_reminders:
                    st.success(f"🔔 **Reminder Alert**: {reminder['task']} (scheduled for {reminder['date']} at {reminder['time']})")
                    reminder_msg = f"🔔 Reminder: {reminder['task']} at {reminder['date']} {reminder['time']}"
                    st.session_state.chat.append(("Assistant", reminder_msg))
                
                with open(triggered_file, "w") as f:
                    json.dump([], f)
                
                return True  
            
        except Exception as e:
            print("Error reading triggered reminders:", e)
    
    return False

# Main UI Layout
st.markdown('<div class="main-header"><h1>🤖 AI Personal Assistant</h1><p>Your intelligent companion for productivity and organization</p></div>', unsafe_allow_html=True)

# Check for triggered reminders
had_new_reminders = check_and_display_triggered_reminders()

# Sidebar
with st.sidebar:
    st.markdown('<h2 class="section-header">📊 Dashboard</h2>', unsafe_allow_html=True)
    
    # Memory Stats
    try:
        with open("chat_memory.json", "r") as f:
            chat_data = json.load(f)
            conversation_count = len(chat_data.get("conversations", []))
    except:
        conversation_count = 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="stats-card"><h3>{len(memory["tasks"])}</h3><p>Total Tasks</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stats-card"><h3>{conversation_count}</h3><p>Conversations</p></div>', unsafe_allow_html=True)
    
    st.markdown('<h3 class="section-header">📋 Task History</h3>', unsafe_allow_html=True)
    
    if memory["tasks"]:
        # Group tasks by type
        task_types = {"email": [], "calendar": [], "reminder": [], "other": []}
        
        for task in memory["tasks"]:
            task_type = task.get("type", "other")
            if task_type in task_types:
                task_types[task_type].append(task)
            else:
                task_types["other"].append(task)
        
        # Display tasks by type
        for task_type, tasks in task_types.items():
            if tasks:
                st.markdown(f"**{task_type.title()} Tasks:**")
                for task in tasks[-3:]:  # Show last 3 tasks of each type
                    if task["type"] == "email":
                        status = "✅ Sent" if task.get("sent") else "❌ Failed" if task.get('sent') is False else "⏳ Pending"
                        st.markdown(f'<div class="task-card email-card"><strong>To:</strong> {task["to"]}<br><strong>Subject:</strong> {task["subject"]}<br><span style="font-size: 0.8em;">{status}</span></div>', unsafe_allow_html=True)
                    elif task["type"] == "calendar":
                        st.markdown(f'<div class="task-card calendar-card"><strong>Meeting:</strong> {task["person"]}<br><strong>Date:</strong> {task["date"]}<br><strong>Time:</strong> {task["time"]}</div>', unsafe_allow_html=True)
                    elif task["type"] == "reminder":
                        status = "✅ Notified" if task.get("notified") else "⏰ Pending"
                        st.markdown(f'<div class="task-card reminder-card"><strong>Task:</strong> {task["task"]}<br><strong>When:</strong> {task["date"]} at {task["time"]}<br><span style="font-size: 0.8em;">{status}</span></div>', unsafe_allow_html=True)
    else:
        st.info("No tasks added yet")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    # Chat Interface
    st.markdown('<h2 class="section-header">💬 Chat with Assistant</h2>', unsafe_allow_html=True)
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        if st.session_state.chat:
            for sender, msg in st.session_state.chat:
                if sender == "You":
                    st.markdown(f'<div class="user-message"><strong>You:</strong> {msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="assistant-message"><strong>🤖 Assistant:</strong> {msg}</div>', unsafe_allow_html=True)
    
    # Input area
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your message here...", placeholder="Ask me anything or give me a task!", key="user_input")
        submit_button = st.form_submit_button("Send 📤", use_container_width=True)
    
    # Process user input
    if submit_button and user_input:
        task = extract_from_text(user_input)

        if task["type"] == "email":
            to_email = task["to"]
            subject = task["subject"]
            body = task["body"]

            with open("memory.json", "r+") as f:
                data = json.load(f)
                data["tasks"].append({
                    "type": "email",
                    "to": to_email,
                    "subject": subject,
                    "body": body,
                    "sent": False
                })

                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()

            email_result = send_email_via_gmail(to_email, subject, body)

            with open("memory.json", "r+") as f:
                data = json.load(f)
                for i in range(len(data["tasks"]) - 1, -1, -1):
                    if (data["tasks"][i]["type"] == "email" and
                        data["tasks"][i]["to"] == to_email and
                        data["tasks"][i]["subject"] == subject):
                        data["tasks"][i]["sent"] == "successfully" in email_result.lower()
                        break

                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()

            status = "Sent" if "successfully" in email_result.lower() else "Failed"    
            log_to_google_sheets(["Email", to_email, subject, f"{body[:50]}...({status})"])
            response = email_result

        elif task["type"] == "calendar":
            person = task["person"]
            date = task["date"]
            times = task["time"]

            with open("memory.json", "r+") as f:
                data = json.load(f)
                data["tasks"].append({
                    "type": "calendar",
                    "person": person,
                    "date": date,
                    "time": times
                })

                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()

            log_to_google_sheets(["Calendar", person, date, times])
            response = f"Meeting with {person} scheduled on {date} at {times}"

        elif task["type"] == "url_summary":
            url = task["url"]
            try:
                page = requests.get(url, timeout=10)
                soup = BeautifulSoup(page.content, "html.parser")
                text = soup.get_text()
                cleaned_text = text.strip().replace('\n', ' ')
                limited_text = cleaned_text[:2000]

                with model.chat_session() as session:
                    prompt = f"Summarize the following webpage content:\n\n{limited_text}"
                    summary = session.generate(prompt=prompt)

                with open("memory.json", "r+") as f:
                    data = json.load(f)
                    data["tasks"].append({
                        "type": "url_summary",
                        "url": url,
                        "summary": summary
                    })

                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()

                log_to_google_sheets(["URL Summary", url, "N/A", summary[:100]])
                response = summary

            except Exception as e:
                response = f"Failed to fetch or summarize URL. Error: {e}"

        elif task["type"] == "reminder":
            reminder = task.get("task")
            date = task.get("date")
            times = task.get("time")

            if not reminder or not date or not times:
                response = "Could not extract proper reminder details. Please try again with more clarity."
            else:
                with open("memory.json", "r+") as f:
                    data = json.load(f)
                    data["tasks"].append({
                        "type": "reminder",
                        "task": reminder,
                        "date": date,
                        "time": times,
                        "notified": False
                    })

                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()

                log_to_google_sheets(["Reminder", reminder, date, times])
                response = f"Reminder set for '{reminder}' on {date} at {times}"
        elif task["type"] == "calendar_query":
            query_date = task.get("date") or datetime.datetime.now().strftime("%Y-%m-%d")
            if query_date == "<today's date>":
                query_date = datetime.datetime.now().strftime("%Y-%m-%d")

            with open("memory.json", "r") as f:
                data = json.load(f)

            meetings = [t for t in data["tasks"] if t["type"] == "calendar" and t["date"] == query_date]

            if meetings:
                response = f"Meetings scheduled on {query_date}:\n"
                for m in meetings:
                    response += f"- with {m['person']} at {m['time']}\n"
            else:
                response = f"No meetings found on {query_date}"

        elif task["type"] == "memory_query":
            filter_type = task.get("filter", "all")
            date = task.get("query_date")
            range_type = task.get("range")

            with open("memory.json", "r") as f:
                data = json.load(f)["tasks"]

            results = []

            for t in data:
                if filter_type != "all" and t["type"] != filter_type:
                    continue

                task_date = t.get("date")
                if not task_date:
                    continue

                if range_type == "last_week":
                    dt = dateparser.parse(task_date)
                    if not dt:
                        continue
                    if datetime.datetime.now() - dt <= datetime.timedelta(days=7):
                        results.append(t)
                
                elif date and task_date == date:
                    results.append(t)

            if results:
                response = "Here's what i found:\n"
                for r in results:
                    if r["type"] == "calendar":
                        response += f"-Meeting with {r['person']} on {r['date']} at {r['time']}\n"
                    elif r["type"] == "reminder":
                        status = "done" if r.get("notified") else "pending"
                        response += f"-Reminder: {r['task']} on {r['date']} at {r['time']} ({status})\n"
                    elif r["type"] == "email":
                        response += f"-Email to {r['to']} with subject {r['subject']}\n"
            else:
                response = "No matching tasks found"

        else:
            with model.chat_session() as session:
                contexual_prompt = build_contexual_prompt(user_input)
                response = session.generate(prompt=contexual_prompt)

        save_to_chat_memory(user_input, response)

        st.session_state.chat.append(("You", user_input))
        st.session_state.chat.append(("Assistant", response))
        st.rerun()

with col2:
    # PDF Upload Section
    st.markdown('<h3 class="section-header">📄 PDF Summarizer</h3>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        pdf_file = st.file_uploader("📁 Choose a PDF file", type="pdf", help="Upload a PDF file to get an AI-generated summary")
        st.markdown('</div>', unsafe_allow_html=True)

        if pdf_file:
            with st.spinner("Extracting text from PDF..."):
                pdf_text = ""
                with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
                    for page in doc:
                        pdf_text += page.get_text()

            with st.expander("📖 View Extracted Text", expanded=False):
                st.text_area("Extracted Text", pdf_text[:2000] + "..." if len(pdf_text) > 2000 else pdf_text, height=200)

            if st.button("🔍 Generate Summary", use_container_width=True):
                with st.spinner("Generating summary..."):
                    with model.chat_session() as session:
                        prompt = f"Summarize the following pdf content:\n\n{pdf_text[:4000]}"
                        summary = session.generate(prompt=prompt)
                
                st.success("Summary Generated!")
                st.markdown("### 📝 Summary")
                st.write(summary)

                # Save to memory
                with open("memory.json", "r+") as f:
                    data = json.load(f)
                    data["tasks"].append({
                        "type": "pdf_summary",
                        "summary": summary[:500]
                    })

                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()

                log_to_google_sheets(["PDF Summary", "N/A", "N/A", summary[:100]])

    # Quick Actions
    st.markdown('<h3 class="section-header">⚡ Quick Actions</h3>', unsafe_allow_html=True)
    
    if st.button("🔄 Check Reminders", use_container_width=True):
        st.rerun()
    
    if st.button("📊 Refresh Dashboard", use_container_width=True):
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #6c757d; font-size: 0.9em; padding: 1rem;">'
    '🤖 AI Personal Assistant - Built with Streamlit & Local LLM'
    '</div>', 
    unsafe_allow_html=True
)