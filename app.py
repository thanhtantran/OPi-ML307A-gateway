import subprocess
import time

import streamlit as st

from config import DELETE_IMPORTED_SMS, SERIAL_PORT, SERIAL_BAUD
from ml307 import ML307, ML307Error
from sms_db import delete_sms_by_id, init_db, list_outbox, list_sms, queue_sms, reset_outbox_to_queue
from listener import start_listener

st.set_page_config(layout="wide", page_title="OPi-ML307A SMS Gateway")
st.title("📡 OPi-ML307A SMS Gateway")

init_db()

# Start listener threads once per Streamlit session
if "listener_started" not in st.session_state:
    try:
        modem = ML307(port=SERIAL_PORT, baud=SERIAL_BAUD)
        modem.init()
        start_listener(modem)
        st.session_state["listener_started"] = True
        st.session_state["modem_error"] = None
    except ML307Error as e:
        st.session_state["listener_started"] = False
        st.session_state["modem_error"] = str(e)

if st.session_state.get("modem_error"):
    st.error(f"❌ Không kết nối được modem: {st.session_state['modem_error']}")

with st.sidebar:
    st.header("✉️ Gửi SMS")
    number = st.text_input("Số điện thoại", placeholder="+84901234567")
    text = st.text_area("Nội dung tin nhắn", height=100)

    if st.button("Gửi SMS", type="primary"):
        if number and text:
            outbox_id = queue_sms(number, text)
            st.success(f"✅ Đã thêm vào hàng đợi (mã #{outbox_id})")
        else:
            st.error("⚠️ Vui lòng nhập số điện thoại và nội dung")

st.caption(f"Cổng serial: {SERIAL_PORT} · Tự động xóa SMS sau khi import: {'Có' if DELETE_IMPORTED_SMS else 'Không'}.")

summary_col1, summary_col2, summary_col3 = st.columns(3)
outbox_rows = list_outbox(limit=100)
sms_rows = list_sms(limit=100)

summary_col1.metric("Tin nhắn chờ gửi", sum(1 for row in outbox_rows if row[3] == "QUEUE"))
summary_col2.metric("Tin nhắn gửi thành công", sum(1 for row in outbox_rows if row[3] == "SENT"))
summary_col3.metric("Tin nhắn lỗi", sum(1 for row in outbox_rows if row[3] == "FAILED"))

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Hàng đợi gửi")
    if outbox_rows:
        status_icon = {"QUEUE": "⏳", "PROCESSING": "🔄", "SENT": "✅", "FAILED": "❌"}
        for row in outbox_rows[:30]:
            outbox_id, phone, body, status, error, modem_sms_id, created_at, updated_at = row
            with st.container():
                st.markdown(
                    f"{status_icon.get(status, '📨')} **#{outbox_id} · {phone}**"
                    f"  \\nTạo lúc: {created_at} · Cập nhật: {updated_at}"
                )
                st.text(body)
                if error:
                    st.caption(f"Phản hồi modem: {error}")
                if status in ("FAILED", "QUEUE"):
                    if st.button("📤 Gửi ngay", key=f"resend_{outbox_id}"):
                        reset_outbox_to_queue(outbox_id)
                        st.rerun()
                st.divider()
    else:
        st.info("Chưa có tin nhắn nào trong hàng đợi")

with col2:
    st.subheader("📨 Nhật ký SMS")
    inbox = [row for row in sms_rows if row[1] == "IN"]
    sent_log = [row for row in sms_rows if row[1] == "OUT"]

    tab1, tab2 = st.tabs(["📩 Đã nhận", "📤 Đã gửi"])

    with tab1:
        if inbox:
            select_all_inbox = st.checkbox("Chọn tất cả", key="select_all_inbox")
            selected_ids = []

            if selected_ids or select_all_inbox:
                pass  # button rendered after loop below

            for sms in inbox[:20]:
                sms_db_id, direction, number, text, status, ref, ts = sms
                col_check, col_content = st.columns([0.05, 0.95])
                with col_check:
                    checked = st.checkbox("Chọn", value=select_all_inbox, key=f"inbox_{sms_db_id}", label_visibility="collapsed")
                    if checked:
                        selected_ids.append((sms_db_id, ref))
                with col_content:
                    st.markdown(f"**{number}** - {ts}")
                    if ref is not None:
                        st.caption(f"Modem SMS index: {ref}")
                    st.text(text)
                    if status:
                        st.caption(f"Trạng thái: {status}")
                st.divider()

            if selected_ids:
                if st.button(f"🗑️ Xóa {len(selected_ids)} SMS đã chọn", key="del_inbox", type="primary"):
                    for db_id, modem_ref in selected_ids:
                        delete_sms_by_id(db_id)
                    st.success("Đã xóa thành công")
                    st.rerun()
        else:
            st.info("Chưa có tin nhắn nào")

    with tab2:
        if sent_log:
            select_all_sent = st.checkbox("Chọn tất cả", key="select_all_sent")
            selected_sent_ids = []

            for sms in sent_log[:20]:
                sms_db_id, direction, number, text, status, ref, ts = sms
                col_check, col_content = st.columns([0.05, 0.95])
                with col_check:
                    checked = st.checkbox("Chọn", value=select_all_sent, key=f"sent_{sms_db_id}", label_visibility="collapsed")
                    if checked:
                        selected_sent_ids.append(sms_db_id)
                with col_content:
                    st.markdown(f"**{number}** - {ts}")
                    if ref is not None:
                        st.caption(f"Outbox ref: {ref}")
                    st.text(text)
                    if status:
                        st.caption(f"Trạng thái: {status}")
                st.divider()

            if selected_sent_ids:
                if st.button(f"🗑️ Xóa {len(selected_sent_ids)} SMS đã chọn", key="del_sent", type="primary"):
                    for db_id in selected_sent_ids:
                        delete_sms_by_id(db_id)
                    st.success("Đã xóa thành công")
                    st.rerun()
        else:
            st.info("Chưa có lịch sử gửi")

time.sleep(2)
st.rerun()
