import streamlit as st
from gpt4all import GPT4All
import re
import os
import json

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

with st.sidebar:
    st.subheader("Task History")
    if memory["tasks"]:
        for task in memory["tasks"]:
            if task["type"] == "email":
                st.markdown(f"**-To:** {task['to']}  \n  **-Subject:** {task['subject']}")
            elif task["type"] == "calendar":
                st.markdown(f"**Meeting with:** {task['person']}  **Date:** {task['date']}  **Time:** {task['time']}")

    else:
        st.write("No tasks added")

user_input = st.text_input("You", "")

if user_input:

    match_email = re.match(r"send email to (.+?) with subject (.+?) and body (.+)", user_input, re.IGNORECASE)

    match_calendar = re.match(r"add meeting with (.+?) on (.+?) at (.+)", user_input, re.IGNORECASE)

    if match_email:
        to_email = match_email.group(1)
        subject = match_email.group(2)
        body = match_email.group(3)

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

        response = f"Email simulated to {to_email} with subject '{subject}' and body:\n'{body}'" 

    elif match_calendar:
        person = match_calendar.group(1)
        date = match_calendar.group(2)
        time = match_calendar.group(3)

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

        response = f"Meeting with {person} scheduled on {date} at {time} "
    
    else:
        with model.chat_session() as session:
            response = session.generate(prompt=user_input)

    st.session_state.chat.append(("You", user_input))
    st.session_state.chat.append(("Assistant", response))

for sender,msg in st.session_state.chat:
    st.markdown(f"**{sender}**: {msg}")





