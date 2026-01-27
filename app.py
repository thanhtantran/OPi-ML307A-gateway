import streamlit as st
import time
from sms_db import list_sms, queue_sms, init_db

st.set_page_config(layout="wide")
st.title("📡 OPi-ML307A Gateway")

init_db()

st.subheader("✉️ Queue SMS")
number = st.text_input("Phone number")
text = st.text_area("Message")

if st.button("Queue SMS"):
    queue_sms(number, text)
    st.success("Queued")

st.subheader("📨 Inbox / Outbox")
for s in list_sms():
    st.write(s)

time.sleep(5)
st.rerun()
