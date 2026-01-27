import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 設定全域變數 ---
# 應回報的標準任務清單 (用於自動計算未回報扣點)
REQUIRED_TASKS = [
    "開店-儀容自檢",
    "開店-環境清掃",
    "營業-零用金確認",
    "營業-隨機抽盤",
    "閉店-庫存表上傳"
]

# 門市清單
STORE_LIST = [
    "文賢店", "東門店", "小西門店", "永康店", 
    "歸仁店", "安中店", "鹽行店", "五甲店"
]

# --- 2. 後端數據初始化 ---
if 'mani_live_logs' not in st.session_state:
    st.session_state.mani_live_logs = pd.DataFrame(columns=[
        "時間", "門市", "員工員編", "任務項目", "狀態", "上傳照片", "系統計點"
    ])

# 登入狀態初始化
if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False

# --- 3. 側邊欄：導航 ---
st.sidebar.title("馬尼通訊管理系統")
# 需求1: 預設呈現畫面為「門市記錄回報」，名稱變更
view_mode = st.sidebar.radio("功能選單", ["門市記錄回報", "管理後台"], index=0, key="nav_radio")

# --- 4. 功能一：門市記錄回報 (公開) ---
if view_mode == "門市記錄回報":
    st.header("📋 門市每日職責回報")
    
    with st.form("task_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            # 需求4: 預設為空白 (index=None 在新版 Streamlit 支援，若舊版會報錯，這裡用空白選項處理)
            selected_store = st.selectbox(
                "所屬門市 (必選)", 
                ["請選擇..."] + STORE_LIST, 
                key="input_store"
            )
            emp_id = st.text_input("員工編號", key="input_emp_id")
        
        with col2:
            task_type = st.selectbox("回報項目", REQUIRED_TASKS, key="input_task")
        
        # 需求5: 解決相機不穩問題，改用檔案上傳 (手機端會自動跳出 拍照/圖庫 選項)
        st.info("💡 提示：手機點擊下方 Browse files 可直接開啟相機拍照。")
        photo = st.file_uploader("上傳現場照片 (必填)", type=['jpg', 'png', 'jpeg'], key="uploader")
        
        submit = st.form_submit_button("確認提交")
        
        if submit:
            # 驗證邏輯
            if selected_store == "請選擇...":
                st.error("❌ 錯誤：請選擇所屬門市！")
            elif not photo:
                st.error("❌ 錯誤：必須上傳照片！")
            elif not emp_id:
                st.error("❌ 錯誤：請輸入員工編號！")
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 寫入資料
                new_data = {
                    "時間": now, 
                    "門市": selected_store, 
                    "員工員編": emp_id,
                    "任務項目": task_type, 
                    "狀態": "✅ 已提交", 
                    "上傳照片": "有 (已上傳)", 
                    "系統計點": 0 # 提交時預設不扣點，扣點由後台審核或缺漏計算
                }
                st.session_state.mani_live_logs = pd.concat(
                    [st.session_state.mani_live_logs, pd.DataFrame([new_data])], 
                    ignore_index=True
                )
                st.success(f"[{selected_store}] {task_type} 提交成功！")

# --- 5. 功能二：管理後台 (需密碼) ---
elif view_mode == "管理後台":
    st.header("🔐 管理後台")

    # --- 密碼驗證邏輯 ---
    if not st.session_state.is_admin_logged_in:
        password = st.text_input("請輸入管理員密碼", type="password", key="admin_pass")
        if st.button("登入"):
            if password == "1234":  # 預設密碼，可自行修改
                st.session_state.is_admin_logged_in = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤")
        st.stop()  # 密碼未通過前，停止執行下方代碼

    # --- 登入後顯示內容 ---
    if st.button("登出管理後台"):
        st.session_state.is_admin_logged_in = False
        st.rerun()
    
    st.divider()

    # 1. 儀表板數據
    if not st.session_state.mani_live_logs.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("今日回報總數", len(st.session_state.mani_live_logs))
        
        # 計算實際扣分總和 (包含人工扣點 + 預計的缺漏扣點需要另外算，這裡先顯示已記錄的)
        real_penalty = st.session_state.mani_live_logs["系統計點"].sum()
        c2.metric("目前系統記點總和", real_penalty)
        
        c3.metric("有回報的門市數", st.session_state.mani_live_logs["門市"].nunique())
    else:
        st.info("尚無資料")

    # 2. 需求3: 自動計算未回報扣點 (缺漏檢查)
    st.subheader("⚠️ 每日未回報檢核 (自動計算)")
    
    with st.expander("查看全台門市缺漏狀況", expanded=True):
        if st.session_state.mani_live_logs.empty:
            st.warning("尚無任何回報數據，所有門市皆視為全缺。")
        else:
            # 取得今日已回報的數據 (這裡簡化，假設 log 都是今日的)
            # 建立一個樞紐分析表概念：門市 vs 已完成任務
            report_status = []
            
            for store in STORE_LIST:
                # 篩選該門市的紀錄
                store_logs = st.session_state.mani_live_logs[
                    st.session_state.mani_live_logs["門市"] == store
                ]
                completed_tasks = store_logs["任務項目"].unique().tolist()
                
                # 比對標準清單，找出缺漏
                missing_tasks = [t for t in REQUIRED_TASKS if t not in completed_tasks]
                missing_count = len(missing_tasks)
                penalty_points = missing_count * -1  # 一項未回報記一點 (這裡用負分表示扣分)
                
                report_status.append({
                    "門市": store,
                    "已完成項數": len(completed_tasks),
                    "未完成項數": missing_count,
                    "未完成項目明細": ", ".join(missing_tasks) if missing_tasks else "無",
                    "自動試算扣點": penalty_points
                })
            
            status_df = pd.DataFrame(report_status)
            
            # 依照扣點排序 (扣分最多的排前面)
            st.dataframe(
                status_df.sort_values("自動試算扣點"), 
                column_config={
                    "自動試算扣點": st.column_config.NumberColumn(format="%d 點")
                },
                use_container_width=True
            )
            st.caption("註：此表格為系統自動試算，若需正式寫入扣分紀錄，請在下方人工確認。")

    st.divider()

    # 3. 門市即時回報列表
    st.subheader("📢 門市即時回報列表")
    st.dataframe(
        st.session_state.mani_live_logs.sort_values(by="時間", ascending=False), 
        use_container_width=True
    )

    # 4. 抽查與人工記點
    st.subheader("🔍 抽查與人工記點")
    if not st.session_state.mani_live_logs.empty:
        col_audit_1, col_audit_2 = st.columns([2, 1])
        with col_audit_1:
            row_to_audit = st.selectbox(
                "選擇要審核的紀錄 (依時間倒序)", 
                st.session_state.mani_live_logs.index,
                format_func=lambda x: f"{st.session_state.mani_live_logs.at[x, '時間']} - {st.session_state.mani_live_logs.at[x, '門市']} - {st.session_state.mani_live_logs.at[x, '任務項目']}",
                key="audit_select"
            )
        with col_audit_2:
            audit_action = st.selectbox("執行動作", ["無", "照片模糊 (扣1點)", "回報不實 (扣2點)", "撤銷扣分"], key="audit_action")
        
        if st.button("更新評分", key="update_score"):
            current_points = st.session_state.mani_live_logs.at[row_to_audit, "系統計點"]
            
            if audit_action == "照片模糊 (扣1點)":
                st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = current_points - 1
                st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "⚠️ 照片模糊"
            elif audit_action == "回報不實 (扣2點)":
                st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = current_points - 2
                st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "❌ 回報不實"
            elif audit_action == "撤銷扣分":
                st.session_state.mani_live_logs.at[row_to_audit, "系統計點"] = 0
                st.session_state.mani_live_logs.at[row_to_audit, "狀態"] = "✅ 已修正"
            
            st.success("評分已更新！")
            st.rerun()
