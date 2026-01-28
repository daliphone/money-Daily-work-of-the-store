import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 設定全域變數 (任務清單與 SOP) ---
TASK_SOP = {
    "開店-儀容自檢": "📋 執行重點：全體員工皆需執行。確認穿著制服、配戴名牌，頭髮梳理整齊。",
    "開店-環境清掃": "🧹 執行重點：門市公用事項。櫃台桌面擦拭、店內地面掃拖、玻璃門清潔。",
    "營業-零用金確認": "💰 執行重點：門市公用事項。清點收銀機內零用金，確認金額正確無誤。",
    "營業-隨機抽盤": "📱 執行重點：門市公用事項。隨機挑選 3-5 樣高單價商品，核對數量。",
    "閉店-庫存表上傳": "📊 執行重點：門市公用事項。執行日結作業，產出今日庫存報表。"
}

REQUIRED_TASKS = list(TASK_SOP.keys())

STORE_LIST = [
    "文賢店", "東門店", "小西門店", "永康店", 
    "歸仁店", "安中店", "鹽行店", "五甲店"
]

# --- 2. 後端數據初始化 ---
if 'mani_live_logs' not in st.session_state:
    st.session_state.mani_live_logs = pd.DataFrame(columns=[
        "時間", "門市", "員工姓名", "任務項目", "狀態", "照片物件", "系統計點", "日期"
    ])
    # 新增 "日期" 欄位以便篩選當日狀態

if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False

# --- 3. 側邊欄 ---
st.sidebar.title("馬尼通訊管理系統")

with st.sidebar.expander("ℹ️ 系統資訊與版本紀錄", expanded=False):
    st.markdown("""
    **版本資訊：v1.4.0**
    - **2026/01/30 更新：**
      1. 新增「門市今日任務看板」：可即時查看該店今日完成進度。
      2. 儀容自檢：列出已完成員工姓名，並強制使用相機拍攝 (不可選圖)。
      3. 其他項目：以門市為單位，顯示是否已完成。
    """)
    st.divider()
    is_admin_mode = st.toggle("開啟管理後台模式")

# --- 4. 邏輯分流 ---

# === 模式 A: 門市同仁回報端 ===
if not is_admin_mode:
    st.header("📋 門市每日職責回報")

    # 步驟 1: 先選擇門市 (這決定了下方要顯示什麼看板)
    selected_store = st.selectbox("🏬 請先選擇所屬門市", ["請選擇..."] + STORE_LIST, key="store_selector")

    # 只有選了門市才顯示看板與後續操作
    if selected_store != "請選擇...":
        
        # --- 🚀 功能：門市今日任務看板 (Dashboard) ---
        st.info(f"📊 [{selected_store}] 今日作業進度看板", icon="📅")
        
        # 取得今日日期字串
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 篩選出「這間店」+「今天」的所有紀錄
        if not st.session_state.mani_live_logs.empty:
            daily_logs = st.session_state.mani_live_logs[
                (st.session_state.mani_live_logs["門市"] == selected_store) & 
                (st.session_state.mani_live_logs["日期"] == today_str)
            ]
        else:
            daily_logs = pd.DataFrame()

        # 顯示各項任務狀態
        status_cols = st.columns(len(REQUIRED_TASKS))
        
        for i, task in enumerate(REQUIRED_TASKS):
            with status_cols[i]:
                # 找出這個任務今天的紀錄
                task_records = daily_logs[daily_logs["任務項目"] == task] if not daily_logs.empty else pd.DataFrame()
                
                # 標題
                clean_name = task.split("-")[1] # 只顯示 "-" 後面的簡稱
                st.markdown(f"**{clean_name}**")
                
                # 邏輯分流顯示
                if task == "開店-儀容自檢":
                    # 儀容自檢：顯示已完成的人名
                    if not task_records.empty:
                        names = task_records["員工姓名"].unique().tolist()
                        st.success(f"已完成：\n{', '.join(names)}")
                    else:
                        st.warning("尚無人打卡")
                else:
                    # 其他項目：顯示完成與否
                    if not task_records.empty:
                        doer = task_records.iloc[0]["員工姓名"]
                        st.success(f"✅ 已完成\n({doer})")
                    else:
                        st.error("❌ 未執行")

        st.divider()

        # --- 步驟 2: 選擇要執行的任務 ---
        col_task_select, col_sop = st.columns([1, 2])
        with col_task_select:
            task_type = st.selectbox("📌 選擇今日要執行的項目", REQUIRED_TASKS, key="task_selector")
        
        with col_sop:
            if task_type:
                st.info(TASK_SOP[task_type], icon="ℹ️")

        # --- 步驟 3: 填寫資料與提交 ---
        st.caption("👇 執行回報區")
        with st.form("task_form", clear_on_submit=True):
            emp_name = st.text_input("執行員工姓名", key="input_emp_name")
            
            # 動態顯示邏輯
            photo = None
            is_checked = False
            
            # 情境 A: 儀容自檢 (強制相機)
            if task_type == "開店-儀容自檢":
                st.markdown(f"**📸 [{task_type}] 需拍照存證：**")
                # 需求3: 僅選擇相機，不可選擇圖片上傳 -> 使用 st.camera_input
                photo = st.camera_input("請拍攝當下儀容 (無法選圖)", key="camera")
            
            # 情境 B: 其他項目 (勾選確認)
            else:
                st.markdown(f"**✅ [{task_type}] 確認執行：**")
                # 檢查是否已經有人做過 (提示用，不強制阻擋，因為可能有補做需求)
                is_done_today = False
                if not daily_logs.empty:
                     if task_type in daily_logs["任務項目"].values:
                         is_done_today = True
                
                if is_done_today:
                    st.warning(f"⚠️ 注意：此項目今日已有同仁回報過。")
                
                is_checked = st.checkbox(f"我已閱讀 SOP 並完成 [{task_type}]", key="check_exec")
            
            # 提交按鈕
            submit = st.form_submit_button("確認提交", use_container_width=True)
            
            if submit:
                error_msg = ""
                if not emp_name:
                    error_msg = "❌ 錯誤：請輸入員工姓名！"
                elif task_type == "開店-儀容自檢" and not photo:
                    error_msg = "❌ 錯誤：儀容自檢必須拍攝照片！"
                elif task_type != "開店-儀容自檢" and not is_checked:
                    error_msg = "❌ 錯誤：請勾選確認已執行！"
                
                if error_msg:
                    st.error(error_msg)
                else:
                    now = datetime.now()
                    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    date_str = now.strftime("%Y-%m-%d")
                    
                    new_data = {
                        "時間": now_str, 
                        "日期": date_str,
                        "門市": selected_store, 
                        "員工姓名": emp_name,
                        "任務項目": task_type, 
                        "狀態": "✅ 已提交", 
                        "照片物件": photo if photo else None,
                        "系統計點": 0
                    }
                    st.session_state.mani_live_logs = pd.concat(
                        [st.session_state.mani_live_logs, pd.DataFrame([new_data])], 
                        ignore_index=True
                    )
                    st.success(f"提交成功！")
                    st.rerun() # 重新整理頁面以更新上方的看板狀態

# === 模式 B: 管理後台 ===
else:
    st.header("🔐 管理後台")

    if not st.session_state.is_admin_logged_in:
        password = st.text_input("請輸入管理員密碼", type="password", key="admin_pass")
        if st.button("登入"):
            if password == "1234":
                st.session_state.is_admin_logged_in = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤")
        st.stop()

    if st.button("登出管理後台"):
        st.session_state.is_admin_logged_in = False
        st.rerun()
    
    # --- 後台分頁 ---
    tab1, tab2, tab3 = st.tabs(["📊 即時監控", "⚠️ 缺漏檢核", "📈 統計報表"])

    with tab1:
        st.subheader("📢 回報列表")
        display_df = st.session_state.mani_live_logs.drop(columns=["照片物件"])
        st.dataframe(display_df.sort_values(by="時間", ascending=False), use_container_width=True)
        
        st.divider()
        st.subheader("🔍 抽查與照片")
        if not st.session_state.mani_live_logs.empty:
            c1, c2 = st.columns([1, 1])
            with c1:
                row_to_audit = st.selectbox(
                    "選擇紀錄", 
                    st.session_state.mani_live_logs.index,
                    format_func=lambda x: f"{st.session_state.mani_live_logs.at[x, '門市']} - {st.session_state.mani_live_logs.at[x, '員工姓名']} - {st.session_state.mani_live_logs.at[x, '任務項目']}",
                    key="audit_select"
                )
                photo_obj = st.session_state.mani_live_logs.at[row_to_audit, "照片物件"]
                task_name = st.session_state.mani_live_logs.at[row_to_audit, "任務項目"]
                
                if photo_obj:
                    # 這裡 st.camera_input 產生的也是 file-like object，可以直接顯示
                    st.image(photo_obj, caption="現場拍攝照片", width=300)
                elif "儀容自檢" in task_name:
                    st.error("異常：應有照片但未找到")
                else:
                    st.info(f"此項目 [{task_name}] 為勾選確認，無須照片。")

            with c2:
                audit_action = st.selectbox("評分", ["無", "不合格 (扣1點)", "重大違規 (扣2點)", "撤銷"], key="audit_action")
                if st.button("更新"):
                    current_points = st.session_state.mani_live_logs.at[row_to_audit, "系統計點"]
                    if "不合格" in audit_action:
                        st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = current_points - 1
                        st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "⚠️ 不合格"
                    elif "重大違規" in audit_action:
                        st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = current_points - 2
                        st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "❌ 重大違規"
                    elif "撤銷" in audit_action:
                        st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = 0
                        st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "✅ 已修正"
                    st.rerun()

    with tab2:
        st.subheader("⚠️ 每日缺漏檢核 (依門市)")
        # 這裡邏輯微調：儀容自檢很難算缺漏(不知道今天幾人上班)，主要算公用任務
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if st.session_state.mani_live_logs.empty:
            st.warning("尚無數據。")
        else:
            report_status = []
            # 只檢查當天
            today_logs = st.session_state.mani_live_logs[st.session_state.mani_live_logs["日期"] == today_str]
            
            for store in STORE_LIST:
                store_logs = today_logs[today_logs["門市"] == store]
                completed = store_logs["任務項目"].unique().tolist()
                
                # 排除儀容自檢(因為是個人的)，只檢查公用任務是否缺漏
                store_tasks = [t for t in REQUIRED_TASKS if t != "開店-儀容自檢"]
                missing = [t for t in store_tasks if t not in completed]
                
                report_status.append({
                    "門市": store, 
                    "公用任務未完成數": len(missing), 
                    "未完成項目": ", ".join(missing) if missing else "All Done"
                })
            st.dataframe(pd.DataFrame(report_status), use_container_width=True)

    with tab3:
        st.subheader("📈 統計報表")
        if not st.session_state.mani_live_logs.empty:
            df_stats = st.session_state.mani_live_logs.copy()
            rank_df = df_stats.groupby("門市")["系統計點"].sum().reset_index().sort_values(by="系統計點")
            st.bar_chart(rank_df, x="門市", y="系統計點", color="#FF4B4B")
        else:
            st.info("尚無數據")
