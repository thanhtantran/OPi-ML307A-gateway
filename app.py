import time

import streamlit as st

from sms_db import init_db, list_outbox, list_sms, queue_sms

st.set_page_config(layout="wide", page_title="OPi-ML307A SMS Gateway")
st.title("📡 OPi-ML307A SMS Gateway")

init_db()

with st.sidebar:
    st.header("✉️ Gửi SMS")
    number = st.text_input("Số điện thoại", placeholder="+84901234567")
    text = st.text_area("Nội dung tin nhắn", height=100)

    if st.button("Gửi SMS", type="primary"):
        if number and text:
            outbox_id = queue_sms(number, text)
            st.success(f"✅ Đã thêm tin nhắn vào hàng đợi (mã #{outbox_id})")
        else:
            st.error("⚠️ Vui lòng nhập số điện thoại và nội dung")

st.caption("ML307 không hỗ trợ GPS trong dự án này. Giao diện chỉ giữ lại chức năng SMS.")

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
        status_icon = {
            "QUEUE": "⏳",
            "PROCESSING": "🔄",
            "SENT": "✅",
            "FAILED": "❌",
        }
        for row in outbox_rows[:30]:
            outbox_id, phone, body, status, error, created_at, updated_at = row
            with st.container():
                st.markdown(
                    f"{status_icon.get(status, '📨')} **#{outbox_id} · {phone}**"
                    f"  \\nTạo lúc: {created_at} · Cập nhật: {updated_at}"
                )
                st.text(body)
                if error:
                    st.caption(f"Lỗi modem: {error}")
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
            for sms in inbox[:20]:
                with st.container():
                    st.markdown(f"**{sms[2]}** - {sms[6]}")
                    st.text(sms[3])
                    st.divider()
        else:
            st.info("Chưa có tin nhắn nào")

    with tab2:
        if sent_log:
            for sms in sent_log[:20]:
                with st.container():
                    st.markdown(f"**{sms[2]}** - {sms[6]}")
                    st.text(sms[3])
                    if sms[4]:
                        st.caption(f"Trạng thái: {sms[4]}")
                    st.divider()
        else:
            st.info("Chưa có lịch sử gửi")

# Auto refresh
start = time.time()
while time.time() - start < 2:
    time.sleep(0.1)
st.rerun()
