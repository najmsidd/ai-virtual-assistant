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

model_path = r"C:/Users/najms/AppData/Local/nomic.ai/GPT4All/Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf"

model = GPT4All(model_name=model_path)

st.title("Virtual AI Assistant (Local GPT)")

if "chat" not in st.session_state:
    st.session_state.chat = []

if not os.path.exists("memory.json"):
    with open("memory.json", "w") as f:
        json.dump({"tasks":[]}, f)

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
- type: one of ["email", "calendar", "url_summary", "pdf_summary", "reminder", "general"]
- to (for emails)
- subject (for emails)
- body (for emails)
- person (for calendar)
- date (for calendar/reminder)
- time (for calendar/reminder)
- url (for url_summary)
- task (for reminder)
- prompt (for general chat or unknown)

If any field is not needed, return it as null.

Message: "{user_input}"
Return JSON only.
"""
    with model.chat_session() as session:
        result = session.generate(prompt=prompt)

    try:
        data = json.loads(result)
    except:
        data = {"type": "general", "prompt": user_input}

    return data

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
                st.markdown(f"**Reminder:** {task['task']} on {task['date']} at {task['time']}")

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
                "type" : summary,
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
                "type" : "email",
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
        time = task["time"]

        with open("memory.json", "r+") as f:
            data = json.load(f)
            data["tasks"].append({
                "type" : "calendar",
                "person" : person,
                "date" : date,
                "time" : time
            })
        
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        log_to_google_sheets(["Calendar", person, date, time])

        response = f"Meeting with {person} scheduled on {date} at {time} "
    
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
                    "type" : "url_summary",
                    "url" : url,
                    "summary" : summary
                })
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()

            log_to_google_sheets(["URL Summary", url, "N/A", summary[:100]])

            response = summary

        except Exception as e:
            response = f"Failed to fetch or summarize URL. Error: {e}"

    elif task["type"] == "reminder":
        reminder = task["task"]
        date = task["date"]
        time = task["time"]
        with open("memory.json", "r+") as f:
            data = json.load(f)
            data["tasks"].append({
                "type" : "reminder",
                "task": reminder,
                "date": date,
                "time": time
            })
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        log_to_google_sheets(["Reminder", reminder, date, time])
        response = f"Reminder set for {reminder} at {date} on {time}"

    else:
        with model.chat_session() as session:
            response = session.generate(prompt=user_input)

    st.session_state.chat.append(("You", user_input))
    st.session_state.chat.append(("Assistant", response))

for sender,msg in st.session_state.chat:
    st.markdown(f"**{sender}**: {msg}")





