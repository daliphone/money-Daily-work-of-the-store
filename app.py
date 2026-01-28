import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image, ExifTags

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 設定全域變數 ---
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

# --- 輔助函式：檢查照片 EXIF 時間 ---
def check_is_photo_today(uploaded_file):
    try:
        # 重點修正：先將指標歸零，以免讀取失敗
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        exif_data = image._getexif()
        
        # 讀取完畢後，務必將指標再次歸零，讓後續程式能存檔
        uploaded_file.seek(0)
        
        if not exif_data:
            return True, "⚠️ 警告：無法讀取拍攝時間，本次放行。"

        # Tag 36867 = DateTimeOriginal
        date_taken_str = None
        for tag, value in exif_data.items():
            decoded = ExifTags.TAGS.get(tag, tag)
            if decoded == "DateTimeOriginal":
                date_taken_str = value
                break
        
        if date_taken_str:
            # EXIF 時間格式通常為 "YYYY:MM:DD HH:MM:SS"
            try:
                date_obj = datetime.strptime(date_taken_str, "%Y:%m:%d %H:%M:%S")
                today_str = datetime.now().strftime("%Y-%m-%d")
                photo_date_str = date_obj.strftime("%Y-%m-%d")
                
                if photo_date_str == today_str:
                    return True, "✅ 照片為今日拍攝"
                else:
                    return False, f"❌ 錯誤：照片拍攝於 {photo_date_str}，非今日！"
            except ValueError:
                return True, "⚠️ 日期格式解析失敗，放行。"
        else:
            return True, "⚠️ 照片無日期資訊，放行。"
            
    except Exception as e:
        # 發生錯誤也記得歸零
        uploaded_file.seek(0)
        return True, f"⚠️ 讀取錯誤，略過檢查: {e}"

# --- 2. 後端數據初始化 (含自動修復) ---
if 'mani_live_logs' not in st.session_state:
    st.session_state.mani_live_logs = pd.DataFrame(columns=[
        "時間", "門市", "員工姓名", "任務項目", "狀態", "照片物件", "系統計點", "日期"
    ])

# 自動修復機制：防止舊版 DataFrame 缺少欄位導致後台崩潰
expected_columns = ["時間", "門市", "員工姓名", "任務項目", "狀態", "照片物件", "系統計點", "日期"]
current_columns = st.session_state.mani_live_logs.columns.tolist()
missing_columns = [col for col in expected_columns if col not in current_columns]

if missing_columns:
    # 如果發現缺欄位，自動補上
    for col in missing_columns:
        st.session_state.mani_live_logs[col] = None
    # 填補日期欄位 (若舊資料無日期，用時間推算)
    if "日期" in missing_columns and not st.session_state.mani_live_logs.empty:
        st.session_state.mani_live_logs["日期"] = pd.to_datetime(st.session_state.mani_live_logs["時間"]).dt.strftime("%Y-%m-%d")

if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False

# --- 3. 側邊欄 ---
st.sidebar.title("馬尼通訊管理系統")

with st.sidebar.expander("ℹ️ 系統資訊與版本紀錄", expanded=False):
    st.markdown("""
    **版本資訊：v1.4.2 (修復顯示版)**
    - **2026/01/30 更新：**
      1. 修復：管理後台無數據問題 (增加資料結構自動校正)。
      2. 修復：照片上傳後的檔案讀取問題 (Reset Seek)。
    """)
    # 緊急重置按鈕 (若資料真的壞掉可用)
    if st.button("⚠️ 清除所有資料 (重置系統)"):
        st.session_state.clear()
        st.rerun()
        
    st.divider()
    is_admin_mode = st.toggle("開啟管理後台模式")

# --- 4. 邏輯分流 ---

# === 模式 A: 門市同仁回報端 ===
if not is_admin_mode:
    st.header("📋 門市每日職責回報")

    selected_store = st.selectbox("🏬 請先選擇所屬門市", ["請選擇..."] + STORE_LIST, key="store_selector")

    if selected_store != "請選擇...":
        
        # --- 看板區塊 ---
        st.info(f"📊 [{selected_store}] 今日作業進度看板", icon="📅")
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 確保資料表不為空且有日期欄位
        if not st.session_state.mani_live_logs.empty and "日期" in st.session_state.mani_live_logs.columns:
            # 處理 NaN 日期 (避免舊資料報錯)
            st.session_state.mani_live_logs["日期"] = st.session_state.mani_live_logs["日期"].fillna(today_str)
            
            daily_logs = st.session_state.mani_live_logs[
                (st.session_state.mani_live_logs["門市"] == selected_store) & 
                (st.session_state.mani_live_logs["日期"] == today_str)
            ]
        else:
            daily_logs = pd.DataFrame()

        status_cols = st.columns(len(REQUIRED_TASKS))
        for i, task in enumerate(REQUIRED_TASKS):
            with status_cols[i]:
                task_records = daily_logs[daily_logs["任務項目"] == task] if not daily_logs.empty else pd.DataFrame()
                clean_name = task.split("-")[1]
                st.markdown(f"**{clean_name}**")
                
                if task == "開店-儀容自檢":
                    if not task_records.empty:
                        names = task_records["員工姓名"].unique().tolist()
                        st.success(f"已完成：\n{', '.join(names)}")
                    else:
                        st.warning("尚無人打卡")
                else:
                    if not task_records.empty:
                        doer = task_records.iloc[0]["員工姓名"]
                        st.success(f"✅ 已完成\n({doer})")
                    else:
                        st.error("❌ 未執行")

        st.divider()

        # --- 回報操作區 ---
        col_task_select, col_sop = st.columns([1, 2])
        with col_task_select:
            task_type = st.selectbox("📌 選擇今日要執行的項目", REQUIRED_TASKS, key="task_selector")
        
        with col_sop:
            if task_type:
                st.info(TASK_SOP[task_type], icon="ℹ️")

        st.caption("👇 執行回報區")
        with st.form("task_form", clear_on_submit=True):
            emp_name = st.text_input("執行員工姓名", key="input_emp_name")
            
            photo = None
            is_checked = False
            
            if task_type == "開店-儀容自檢":
                st.markdown(f"**📸 [{task_type}] 需拍照存證：**")
                st.caption("💡 提示：點擊下方按鈕後，請選擇「相機」進行拍攝。")
                photo = st.file_uploader("點擊開啟相機 (勿上傳舊照)", type=['jpg', 'jpeg', 'png'], key="uploader")
            else:
                st.markdown(f"**✅ [{task_type}] 確認執行：**")
                is_done_today = False
                if not daily_logs.empty:
                     if task_type in daily_logs["任務項目"].values:
                         is_done_today = True
                
                if is_done_today:
                    st.warning(f"⚠️ 注意：此項目今日已有同仁回報過。")
                is_checked = st.checkbox(f"我已閱讀 SOP 並完成 [{task_type}]", key="check_exec")
            
            submit = st.form_submit_button("確認提交", use_container_width=True)
            
            if submit:
                error_msg = ""
                pass_exif = True
                exif_msg = ""

                if not emp_name:
                    error_msg = "❌ 錯誤：請輸入員工姓名！"
                elif task_type == "開店-儀容自檢":
                    if not photo:
                        error_msg = "❌ 錯誤：儀容自檢必須上傳照片！"
                    else:
                        pass_exif, exif_msg = check_is_photo_today(photo)
                        if not pass_exif:
                            error_msg = exif_msg
                        elif "警告" in exif_msg:
                            st.warning(exif_msg)

                elif task_type != "開店-儀容自檢" and not is_checked:
                    error_msg = "❌ 錯誤：請勾選確認已執行！"
                
                if error_msg:
                    st.error(error_msg)
                else:
                    now = datetime.now()
                    new_data = {
                        "時間": now.strftime("%Y-%m-%d %H:%M:%S"), 
                        "日期": now.strftime("%Y-%m-%d"),
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
                    st.rerun()

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
    
    tab1, tab2, tab3 = st.tabs(["📊 即時監控", "⚠️ 缺漏檢核", "📈 統計報表"])

    with tab1:
        st.subheader("📢 回報列表")
        # 重點修正：使用 errors='ignore' 防止因為欄位不存在而崩潰
        if "照片物件" in st.session_state.mani_live_logs.columns:
            display_df = st.session_state.mani_live_logs.drop(columns=["照片物件"])
        else:
            display_df = st.session_state.mani_live_logs
            
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
                
                # 再次確認欄位存在才讀取
                if "照片物件" in st.session_state.mani_live_logs.columns:
                    photo_obj = st.session_state.mani_live_logs.at[row_to_audit, "照片物件"]
                else:
                    photo_obj = None
                    
                task_name = st.session_state.mani_live_logs.at[row_to_audit, "任務項目"]
                
                if photo_obj:
                    # 嘗試將指標歸零，以確保能顯示
                    try:
                        photo_obj.seek(0)
                        st.image(photo_obj, caption="員工上傳之回報照片", width=300)
                    except:
                        st.error("照片讀取失敗 (可能已過期或損毀)")
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
        st.subheader("⚠️ 每日缺漏檢核")
        today_str = datetime.now().strftime("%Y-%m-%d")
        if st.session_state.mani_live_logs.empty:
            st.warning("尚無數據。")
        else:
            report_status = []
            # 確保有日期欄位
            if "日期" in st.session_state.mani_live_logs.columns:
                df_clean = st.session_state.mani_live_logs.copy()
                df_clean["日期"] = df_clean["日期"].fillna(today_str)
                today_logs = df_clean[df_clean["日期"] == today_str]
            else:
                today_logs = pd.DataFrame()
                
            for store in STORE_LIST:
                store_logs = today_logs[today_logs["門市"] == store]
                completed = store_logs["任務項目"].unique().tolist()
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
