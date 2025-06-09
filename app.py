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

model_path = r"C:/Users/najms/AppData/Local/nomic.ai/GPT4All/Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf"
model = GPT4All(model_name=model_path)

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

                # Save back updated memory
                f.seek(0)
                json.dump({"tasks": new_tasks}, f, indent=2)
                f.truncate()

        except Exception as e:
            print("Reminder check error:", e)

        # Print to console for debugging
        if reminders_triggered:
            print(f"[{now}] Triggered reminders: {[t['task'] for t in reminders_triggered]}")

        # Write triggered reminders to a file for UI pickup
        if reminders_triggered:
            try:
                # Create or append to triggered reminders file
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


if "reminder_thread_started" not in st.session_state:
    threading.Thread(target=reminder_checker, daemon=True).start()
    st.session_state.reminder_thread_started = True

if "displayed_reminders" not in st.session_state:
    st.session_state.displayed_reminders = set()

st.title("Virtual AI Assistant (Local GPT)")

if "chat" not in st.session_state:
    st.session_state.chat = []

if "pending_reminders" not in st.session_state:
    st.session_state.pending_reminders = []

if not os.path.exists("memory.json"):
    with open("memory.json", "w") as f:
        json.dump({"tasks": []}, f)

with open("memory.json", "r") as f:
    memory = json.load(f)

def log_to_google_sheets(row):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key("1T58c_RZNJ1dfB7KiidmoYE2Fn8fiwgeH4WXfdmeYUOw").sheet1

    if sheet.row_values(1) == []:
        headers = ["Take Type", "To/Person/URL", "Subject/Date", "Body/Time/Summary"]
        sheet.insert_row(headers, index=1)

    sheet.append_row(row)

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

    history_text = "\n".join(f"User: {msg}" for msg in recent_msgs)

    return f"""
You are a helpful assistant with short-term memory.

Here is the recent conversation:
{history_text}

Now respond to the user's new message:
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

had_new_reminders = check_and_display_triggered_reminders()

with st.sidebar:
    st.subheader("Task History")
    if memory["tasks"]:
        for task in memory["tasks"]:
            if task["type"] == "email":
                st.markdown(f"**-To:** {task['to']}  \n  **-Subject:** {task['subject']}")
            elif task["type"] == "calendar":
                st.markdown(f"**Meeting with:** {task['person']}  **Date:** {task['date']}  **Time:** {task['time']}")
            elif task["type"] == "url_summary":
                st.markdown(f"**Summarized URL:** {task['url']}")
            elif task["type"] == "reminder":
                status = "✅ Notified" if task.get("notified") else "⏰ Pending"
                st.markdown(f"**Reminder:** {task['task']} on {task['date']} at {task['time']} ({status})")
    else:
        st.write("No tasks added")

st.subheader("Upload PDF For Summarization")
pdf_file = st.file_uploader("Choose a PDF File", type="pdf")

if pdf_file:
    pdf_text = ""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
        for page in doc:
            pdf_text += page.get_text()

    st.markdown("Extracted PDF Text")
    st.text_area("Extracted Text", pdf_text[:2000] + "..." if len(pdf_text) > 2000 else pdf_text, height=300)

    summarize_button = st.button("Summarize")
    if summarize_button:
        with model.chat_session() as session:
            prompt = f"Summarize the following pdf content:\n\n{pdf_text[:4000]}"
            summary = session.generate(prompt=prompt)
        st.subheader("Summary")
        st.write(summary)

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

st.subheader("Chat with Assistant")

user_input = st.text_input("You", "")

if user_input:
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
                "body": body
            })

            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        log_to_google_sheets(["Email", to_email, subject, body[:100]])
        response = f"Email simulated to {to_email} with subject '{subject}' and body:\n'{body}'"

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

        # FIXED line: t instead of task
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

    st.session_state.chat.append(("You", user_input))
    st.session_state.chat.append(("Assistant", response))

for sender, msg in st.session_state.chat:
    st.markdown(f"**{sender}**: {msg}")

if st.button("🔄 Check for New Reminders"):
    st.rerun()