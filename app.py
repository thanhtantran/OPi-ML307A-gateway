import streamlit as st
import time
import pandas as pd
from sms_db import list_sms, queue_sms, init_db, get_latest_gps, get_all_gps_positions
from gps_module import gps_reader

st.set_page_config(layout="wide", page_title="OPi-ML307A Gateway")
st.title("📡 OPi-ML307A Gateway")

init_db()

# Start GPS reader if not already started
if not gps_reader.running:
    gps_reader.start()

# Sidebar for SMS
with st.sidebar:
    st.header("✉️ Gửi SMS")
    number = st.text_input("Số điện thoại", placeholder="+84901234567")
    text = st.text_area("Nội dung tin nhắn", height=100)
    
    if st.button("Gửi SMS", type="primary"):
        if number and text:
            queue_sms(number, text)
            st.success("✅ Đã thêm vào hàng đợi!")
        else:
            st.error("⚠️ Vui lòng nhập số điện thoại và nội dung")

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🛰️ GPS Tracking")
    
    # Get current GPS position
    current_pos = gps_reader.get_position()
    
    if current_pos['has_fix']:
        st.success(f"✅ GPS Fix: {current_pos['satellites']} vệ tinh")
        
        # Display current position info
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.metric("Vĩ độ", f"{current_pos['latitude']:.6f}°")
            st.metric("Kinh độ", f"{current_pos['longitude']:.6f}°")
        with info_col2:
            if current_pos['altitude']:
                st.metric("Độ cao", f"{current_pos['altitude']:.1f} m")
            if current_pos['speed']:
                st.metric("Tốc độ", f"{current_pos['speed']:.1f} km/h")
        
        # Display map with current position
        st.map(
            pd.DataFrame({
                'lat': [current_pos['latitude']],
                'lon': [current_pos['longitude']]
            }),
            zoom=15,
            use_container_width=True
        )
        
        # Display GPS track history
        st.subheader("📍 Lịch sử GPS")
        gps_history = get_all_gps_positions(limit=100)
        if gps_history:
            df_gps = pd.DataFrame(gps_history, columns=['lat', 'lon', 'altitude', 'speed', 'satellites', 'timestamp'])
            df_gps = df_gps[df_gps['lat'].notna() & df_gps['lon'].notna()]
            
            if not df_gps.empty:
                st.map(
                    df_gps[['lat', 'lon']],
                    zoom=12,
                    use_container_width=True
                )
                
                # Show GPS data table
                with st.expander("📊 Chi tiết GPS"):
                    st.dataframe(
                        df_gps[['lat', 'lon', 'altitude', 'speed', 'satellites', 'timestamp']].head(20),
                        use_container_width=True
                    )
    else:
        st.warning("⏳ Đang tìm kiếm tín hiệu GPS...")
        st.info("Vui lòng đợi thiết bị GPS khởi động và có tín hiệu vệ tinh")

with col2:
    st.subheader("📨 Hộp thư")
    
    # Tabs for Inbox/Outbox
    tab1, tab2 = st.tabs(["📩 Đã nhận", "📤 Đã gửi"])
    
    with tab1:
        sms_list = list_sms(limit=50)
        inbox = [s for s in sms_list if s[1] == "IN"]
        
        if inbox:
            for sms in inbox[:20]:  # Show last 20
                with st.container():
                    st.markdown(f"**{sms[2]}** - {sms[5]}")
                    st.text(sms[3])
                    st.divider()
        else:
            st.info("Chưa có tin nhắn nào")
    
    with tab2:
        sms_list = list_sms(limit=50)
        outbox = [s for s in sms_list if s[1] == "OUT"]
        
        if outbox:
            for sms in outbox[:20]:  # Show last 20
                status_color = {
                    "SENT": "✅",
                    "FAILED": "❌",
                    "DELIVERED": "📬"
                }
                status_icon = status_color.get(sms[4], "⏳")
                
                with st.container():
                    st.markdown(f"{status_icon} **{sms[2]}** - {sms[5]}")
                    st.text(sms[3])
                    if sms[4]:
                        st.caption(f"Trạng thái: {sms[4]}")
                    st.divider()
        else:
            st.info("Chưa có tin nhắn nào")

# Auto refresh
time.sleep(2)
st.rerun()
