import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 設定全域變數 (任務清單與 SOP 內容) ---
# 這裡定義每個任務對應的詳細說明，會即時顯示給員工看
TASK_SOP = {
    "開店-儀容自檢": "📋 執行重點：請確認穿著制服、配戴名牌，頭髮梳理整齊，保持專業儀態。",
    "開店-環境清掃": "🧹 執行重點：櫃台桌面擦拭、店內地面掃拖、玻璃門清潔、垃圾桶清理。",
    "營業-零用金確認": "💰 執行重點：清點收銀機內零用金，確認金額正確無誤。",
    "營業-隨機抽盤": "📱 執行重點：隨機挑選 3-5 樣高單價商品或配件，核對現場數量與系統庫存是否相符。",
    "閉店-庫存表上傳": "📊 執行重點：執行日結作業，產出今日庫存報表，確認帳實相符後上傳。"
}

# 取得任務清單 (從字典的 keys 抓取)
REQUIRED_TASKS = list(TASK_SOP.keys())

STORE_LIST = [
    "文賢店", "東門店", "小西門店", "永康店", 
    "歸仁店", "安中店", "鹽行店", "五甲店"
]

# --- 2. 後端數據初始化 ---
if 'mani_live_logs' not in st.session_state:
    st.session_state.mani_live_logs = pd.DataFrame(columns=[
        "時間", "門市", "員工姓名", "任務項目", "狀態", "照片物件", "系統計點"
    ])

if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False

# --- 3. 側邊欄：系統資訊與導航 ---
st.sidebar.title("馬尼通訊管理系統")

# 需求3: 預設在閉合狀態 (expanded=False)
with st.sidebar.expander("ℹ️ 系統資訊與版本紀錄", expanded=False):
    st.markdown("""
    **版本資訊：v1.3.1**
    - **2026/01/29 更新：**
      1. 優化：選擇任務時即時顯示 SOP 內容。
      2. 修正：系統資訊預設為閉合狀態。
    - **2026/01/28 更新：**
      1. 流程分流：僅儀容自檢需拍照。
      2. 新增後台：每月統計報表。
    """)
    st.divider()
    # 管理後台開關藏在這裡
    is_admin_mode = st.toggle("開啟管理後台模式")

# --- 4. 邏輯分流 ---

# === 模式 A: 門市同仁回報端 ===
if not is_admin_mode:
    st.header("📋 門市每日職責回報")
    
    with st.form("task_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            selected_store = st.selectbox("所屬門市 (必選)", ["請選擇..."] + STORE_LIST, key="input_store")
            emp_name = st.text_input("員工姓名", key="input_emp_name")
        
        with col2:
            # 任務選擇
            task_type = st.selectbox("回報項目", REQUIRED_TASKS, key="input_task")
            
            # 需求2: 及時顯示該回報項目內容 (SOP)
            # 使用 info 框框顯示對應的 SOP 文字
            if task_type:
                st.info(TASK_SOP[task_type], icon="ℹ️")
        
        st.divider()
        
        # --- 動態顯示邏輯 ---
        photo = None
        is_checked = False
        
        # 需求1: 只有「開店-儀容自檢」顯示拍照
        if task_type == "開店-儀容自檢":
            st.markdown("#### 📸 拍照存證")
            st.caption("此項目規定必須 **拍照回報**。")
            photo = st.file_uploader("請上傳儀容自拍 (必填)", type=['jpg', 'png', 'jpeg'], key="uploader")
        
        # 其餘項目顯示勾選
        else:
            st.markdown(f"#### ✅ 確認執行")
            st.caption(f"請確認您已完成上述「{task_type}」之工作內容。")
            is_checked = st.checkbox(f"我確認已完成 [{task_type}]", key="check_exec")
            
        submit = st.form_submit_button("確認提交", use_container_width=True)
        
        if submit:
            # 驗證邏輯
            error_msg = ""
            if selected_store == "請選擇...":
                error_msg = "❌ 錯誤：請選擇所屬門市！"
            elif not emp_name:
                error_msg = "❌ 錯誤：請輸入員工姓名！"
            
            # 針對不同任務類型的驗證
            elif task_type == "開店-儀容自檢" and not photo:
                error_msg = "❌ 錯誤：儀容自檢必須上傳照片！"
            elif task_type != "開店-儀容自檢" and not is_checked:
                error_msg = "❌ 錯誤：請勾選確認已執行！"
            
            if error_msg:
                st.error(error_msg)
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 寫入資料
                new_data = {
                    "時間": now, 
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
                st.success(f"[{selected_store}] {emp_name} - {task_type} 提交成功！")

# === 模式 B: 管理後台 ===
else:
    st.header("🔐 管理後台")

    # 密碼驗證
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
    tab1, tab2, tab3 = st.tabs(["📊 即時監控與審核", "⚠️ 缺漏檢核表", "📈 統計報表 (月/週)"])

    with tab1:
        st.subheader("📢 門市即時回報列表")
        display_df = st.session_state.mani_live_logs.drop(columns=["照片物件"])
        st.dataframe(display_df.sort_values(by="時間", ascending=False), use_container_width=True)
        
        st.divider()
        st.subheader("🔍 抽查與人工記點")
        if not st.session_state.mani_live_logs.empty:
            c1, c2 = st.columns([1, 1])
            with c1:
                row_to_audit = st.selectbox(
                    "選擇紀錄", 
                    st.session_state.mani_live_logs.index,
                    format_func=lambda x: f"{st.session_state.mani_live_logs.at[x, '門市']} - {st.session_state.mani_live_logs.at[x, '任務項目']}",
                    key="audit_select"
                )
                photo_obj = st.session_state.mani_live_logs.at[row_to_audit, "照片物件"]
                task_name = st.session_state.mani_live_logs.at[row_to_audit, "任務項目"]
                
                if photo_obj:
                    st.image(photo_obj, caption="員工上傳之回報照片", width=300)
                elif "儀容自檢" in task_name:
                    st.error("異常：此項目應有照片但未找到")
                else:
                    st.info(f"此項目 [{task_name}] 為勾選確認，依規定無須照片。")

            with c2:
                audit_action = st.selectbox("執行動作", ["無", "照片模糊 (扣1點)", "回報不實 (扣2點)", "撤銷扣分"], key="audit_action")
                if st.button("更新評分"):
                    current_points = st.session_state.mani_live_logs.at[row_to_audit, "系統計點"]
                    if "扣1點" in audit_action:
                        st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = current_points - 1
                        st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "⚠️ 扣1點"
                    elif "扣2點" in audit_action:
                        st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = current_points - 2
                        st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "❌ 扣2點"
                    elif "撤銷" in audit_action:
                        st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = 0
                        st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "✅ 已修正"
                    st.rerun()

    with tab2:
        st.subheader("⚠️ 每日未回報檢核")
        if st.session_state.mani_live_logs.empty:
            st.warning("尚無數據。")
        else:
            report_status = []
            for store in STORE_LIST:
                store_logs = st.session_state.mani_live_logs[st.session_state.mani_live_logs["門市"] == store]
                completed = store_logs["任務項目"].unique().tolist()
                missing = [t for t in REQUIRED_TASKS if t not in completed]
                penalty = len(missing) * -1
                report_status.append({
                    "門市": store, "未完成數": len(missing), 
                    "未完成項目": ", ".join(missing), "自動試算扣點": penalty
                })
            st.dataframe(pd.DataFrame(report_status).sort_values("自動試算扣點"), use_container_width=True)

    with tab3:
        st.subheader("📈 門市績效統計報表")
        if not st.session_state.mani_live_logs.empty:
            df_stats = st.session_state.mani_live_logs.copy()
            st.write("#### 🏆 門市扣分排行榜")
            rank_df = df_stats.groupby("門市")["系統計點"].sum().reset_index().sort_values(by="系統計點")
            st.bar_chart(rank_df, x="門市", y="系統計點", color="#FF4B4B")
            
            st.write("#### 📊 違規類型統計")
            penalty_df = df_stats[df_stats["系統計點"] < 0]
            if not penalty_df.empty:
                st.bar_chart(penalty_df["狀態"].value_counts())
            else:
                st.success("目前無違規紀錄")
        else:
            st.info("尚無數據")
