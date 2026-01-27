import streamlit as st
import pandas as pd
from datetime import datetime

# --- 0. 頁面設定 (必須放第一行) ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 1. 後端數據初始化 (目前為暫存，重整會消失) ---
if 'mani_live_logs' not in st.session_state:
    st.session_state.mani_live_logs = pd.DataFrame(columns=[
        "時間", "門市", "員工員編", "任務項目", "狀態", "上傳照片", "系統計點"
    ])

# --- 側邊欄：權限切換 ---
st.sidebar.title("馬尼通訊管理後台")
view_mode = st.sidebar.selectbox("切換介面", ["門市同仁回報端", "老闆即時監控端"])

# --- 2. 門市同仁回報端 (前端) ---
if view_mode == "門市同仁回報端":
    st.header("📋 門市每日職責回報")
    
    with st.form("task_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            store_name = st.selectbox("所屬門市", ["台南總店", "永康店", "西門店", "安平店"])
            emp_id = st.text_input("員工編號")
        with col2:
            task_type = st.selectbox("回報項目", ["開店-儀容自檢", "開店-環境清掃", "營業-零用金確認", "營業-隨機抽盤", "閉店-庫存表上傳"])
        
        # 核心：強制即時拍照 (Streamlit Camera Input)
        photo = st.camera_input("請即時拍照存證 (必填)")
        
        submit = st.form_submit_button("確認提交 (Submit)")
        
        if submit:
            if not photo or not emp_id:
                st.error("❌ 錯誤：請務必輸入員編並拍攝現場照片！")
            else:
                # 自動抓取系統即時時間
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 預設計點邏輯 (逾時判斷範例)
                points = 0
                current_hour = datetime.now().hour
                # 範例：開店任務若超過中午12點扣分
                if "開店" in task_type and (current_hour >= 12 and datetime.now().minute > 15):
                    points = -5 # 逾時自動標記扣點
                
                # 寫入即時 Log
                new_data = {
                    "時間": now, "門市": store_name, "員工員編": emp_id,
                    "任務項目": task_type, "狀態": "✅ 已提交", "上傳照片": "有", "系統計點": points
                }
                st.session_state.mani_live_logs = pd.concat([st.session_state.mani_live_logs, pd.DataFrame([new_data])], ignore_index=True)
                st.success(f"成功提交！時間：{now}")

# --- 3. 老板即時監控端 (後端) ---
else:
    st.header("📊 老闆即時監控儀表板")
    
    # 頂部數據摘要
    c1, c2, c3 = st.columns(3)
    c1.metric("今日回報總數", len(st.session_state.mani_live_logs))
    c2.metric("異常紀錄數", len(st.session_state.mani_live_logs[st.session_state.mani_live_logs["系統計點"] < 0]))
    c3.metric("目前在線門市", st.session_state.mani_live_logs["門市"].nunique())
    
    st.divider()
    
    # 顯示即時 Log 表
    st.subheader("📢 全台門市即時回報串聯")
    st.dataframe(st.session_state.mani_live_logs.sort_values(by="時間", ascending=False), use_container_width=True)
    
    # 快速審核功能
    st.subheader("🔍 抽查與人工扣點")
    if not st.session_state.mani_live_logs.empty:
        # 使用 index 來選取要修改的行
        row_to_audit = st.selectbox("選擇要審核的紀錄 (Index)", st.session_state.mani_live_logs.index)
        audit_res = st.radio("審核結果", ["合格", "不實回報 (扣5點)", "照片模糊 (扣2點)"], key="audit_radio")
        
        if st.button("確認評分"):
            if "不實" in audit_res:
                st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] -= 5
                st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "❌ 判定不實"
            elif "模糊" in audit_res:
                st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] -= 2
                st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "⚠️ 照片模糊"
                
            st.success(f"評分已更新！目前分數：{st.session_state.mani_live_logs.at[row_to_audit, '系統計點']}")
            st.rerun() # 重新執行以刷新表格顯示
