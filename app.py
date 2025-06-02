import streamlit as st
from gpt4all import GPT4All
import re

model_path = r"C:/Users/najms/AppData/Local/nomic.ai/GPT4All/Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf"

model = GPT4All(model_name=model_path)

st.title("Virtual AI Assistant (Local GPT)")

if "chat" not in st.session_state:
    st.session_state.chat = []

user_input = st.text_input("You", "")

if user_input:

    match = re.match(r"send email to (.+?) with subject (.+?) and body (.+)", user_input, re.IGNORECASE)

    if match:
        to_email = match.group(1)
        subject = match.group(2)
        body = match.group(3)

        response = f"Email sent to {to_email} with subject '{subject}' and body:\n'{body}'" 
    
    else:
        with model.chat_session() as session:
            response = session.generate(prompt=user_input)

    st.session_state.chat.append(("You", user_input))
    st.session_state.chat.append(("Assistant", response))

for sender,msg in st.session_state.chat:
    st.markdown(f"**{sender}**: {msg}")





