import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from PIL import Image, ExifTags
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import io

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 設定區 ---
GOOGLE_FORM_URL = "https://forms.gle/1KHVtYzo785LnVKb7"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
TASK_SOP = {
    "開店-儀容自檢": "📋 重點：確認穿著制服、配戴名牌。",
    "開店-環境清掃": "🧹 重點：櫃台、地面、玻璃清潔。",
    "營業-零用金確認": "💰 重點：清點收銀機金額。",
    "營業-隨機抽盤": "📱 重點：挑選 3-5 樣商品核對。",
    "閉店-庫存表上傳": "📊 重點：執行日結，產出報表。"
}
REQUIRED_TASKS = list(TASK_SOP.keys())
STORE_LIST = ["文賢店", "東門店", "小西門店", "永康店", "歸仁店", "安中店", "鹽行店", "五甲店"]

# --- 雲端連線 ---
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    return creds

def get_data():
    """v4.3 絕對防禦版核心"""
    MUST_HAVE_COLS = ["時間", "日期", "門市", "員工姓名", "任務項目", "照片", "確認"]
    try:
        creds = init_connection()
        client = gspread.authorize(creds)
        sheet = client.open("馬尼通訊即時回報系統_DB").get_worksheet(0)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty: return pd.DataFrame(columns=MUST_HAVE_COLS)

        df.columns = [str(c).strip() for c in df.columns]
        rename_map = {
            "時間戳記": "時間", "Timestamp": "時間",
            "請問您所屬的門市": "門市", "請問您所屬的門市？": "門市",
            "您的姓名": "員工姓名", "員工姓名 (請填全名)": "員工姓名",
            "今日執行項目": "任務項目", "任務項目 (請選擇)": "任務項目",
            "上傳照片": "照片", "照片 (如有)": "照片"
        }
        new_columns = {}
        for col in df.columns:
            for key in rename_map:
                if key in col: 
                    new_columns[col] = rename_map[key]
                    break
        df.rename(columns=new_columns, inplace=True)

        current_cols = df.columns.tolist()
        for col in MUST_HAVE_COLS:
            if col not in current_cols: df[col] = None 
                
        if "時間" in df.columns:
            df["時間"] = pd.to_datetime(df["時間"], errors='coerce')
            df["日期"] = df["時間"].dt.strftime("%Y-%m-%d")
            df["日期"] = df["日期"].fillna(datetime.now().strftime("%Y-%m-%d"))
        else:
            df["日期"] = datetime.now().strftime("%Y-%m-%d")
            
        return df
    except:
        return pd.DataFrame(columns=MUST_HAVE_COLS)

def get_tw_time():
    return datetime.now(timezone.utc) + timedelta(hours=8)

def download_image_and_check_exif(drive_url):
    if not drive_url or "drive.google.com" not in str(drive_url):
        return True, "無照片或非 Drive 連結", None
    try:
        file_id = drive_url.split("id=")[-1] if "id=" in drive_url else drive_url.split("/")[-2]
        creds = init_connection()
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO(request.execute())
        image = Image.open(file_content)
        exif_data = image._getexif()
        check_msg = "⚠️ 警告：無 EXIF 時間"
        is_today = True 
        if exif_data:
            for tag, value in exif_data.items():
                if ExifTags.TAGS.get(tag, tag) == "DateTimeOriginal":
                    date_obj = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    today_str = get_tw_time().strftime("%Y-%m-%d")
                    photo_date = date_obj.strftime("%Y-%m-%d")
                    if photo_date == today_str:
                        check_msg = f"✅ 拍攝於今日 ({photo_date})"
                        is_today = True
                    else:
                        check_msg = f"❌ 異常：拍攝於 {photo_date} (非今日)"
                        is_today = False
                    break
        return is_today, check_msg, image
    except Exception as e:
        return True, f"讀取失敗: {str(e)}", None

# --- 自動記點核心運算 ---
def calculate_missing_points(df):
    """計算所有門市的歷史缺點"""
    if df.empty: return pd.DataFrame()
    
    # 1. 找出資料庫中所有出現過的「日期」
    dates = df["日期"].unique()
    
    penalty_records = []
    
    # 2. 遍歷每一天、每一家店
    for d in dates:
        # 當日資料
        daily_data = df[df["日期"] == d]
        
        for store in STORE_LIST:
            # 該店當日完成的任務
            store_done = daily_data[daily_data["門市"] == store]["任務項目"].unique().tolist()
            
            # 找出缺少的任務
            # 邏輯：必做清單 - 已做清單
            missing_tasks = list(set(REQUIRED_TASKS) - set(store_done))
            missing_count = len(missing_tasks)
            
            if missing_count > 0:
                penalty_records.append({
                    "日期": d,
                    "門市": store,
                    "缺點數 (未回報)": missing_count,
                    "未完成項目": ", ".join(missing_tasks)
                })
                
    return pd.DataFrame(penalty_records)

# --- 主程式 ---
if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "front_end"

df_logs = get_data()

st.sidebar.title("馬尼通訊管理系統")
with st.sidebar.expander("ℹ️ 系統資訊", expanded=False):
    st.markdown("v5.0 (自動記點版)")
    if st.session_state.current_page == "front_end":
        if st.button("🔐 進入管理後台"):
            st.session_state.current_page = "backend_login"
            st.rerun()

# --- 前台 ---
if st.session_state.current_page == "front_end":
    st.header("📋 門市每日職責回報")
    selected_store = st.selectbox("🏬 請先選擇所屬門市", ["請選擇..."] + STORE_LIST)
    
    if selected_store != "請選擇...":
        st.info(f"📊 [{selected_store}] 今日作業進度", icon="📅")
        if st.button("🔄 刷新看板"): st.rerun()

        today_str = get_tw_time().strftime("%Y-%m-%d")
        if not df_logs.empty:
            daily_logs = df_logs[(df_logs["門市"] == selected_store) & (df_logs["日期"] == today_str)]
        else:
            daily_logs = pd.DataFrame()

        status_cols = st.columns(len(REQUIRED_TASKS))
        for i, task in enumerate(REQUIRED_TASKS):
            with status_cols[i]:
                if not daily_logs.empty and "任務項目" in daily_logs.columns:
                    recs = daily_logs[daily_logs["任務項目"] == task]
                else: recs = pd.DataFrame()
                    
                st.markdown(f"**{task.split('-')[1]}**")
                if task == "開店-儀容自檢":
                    if not recs.empty: st.success(f"已完成:\n{','.join(recs['員工姓名'].astype(str).unique())}")
                    else: st.warning("未打卡")
                else:
                    if not recs.empty: st.success(f"✅ 已完成")
                    else: st.error("❌ 未執行")
    
    st.divider()
    task_type = st.selectbox("📌 查詢 SOP", ["(請選擇任務查看)"] + REQUIRED_TASKS)
    if task_type != "(請選擇任務查看)": st.info(TASK_SOP[task_type])

    st.markdown("### 👉 準備好回報了嗎？")
    st.link_button("🚀 點此前往 Google 表單回報", GOOGLE_FORM_URL, type="primary")
    st.caption("💡 填寫完畢後，請點擊表單最後的連結回到此處確認看板狀態。")

# --- 後台 ---
elif st.session_state.current_page in ["backend_login", "backend_main"]:
    st.header("🔐 管理後台")
    if not st.session_state.is_admin_logged_in:
        p = st.text_input("密碼", type="password")
        if st.button("登入"): 
            if p=="1234": 
                st.session_state.is_admin_logged_in=True
                st.session_state.current_page="backend_main"
                st.rerun()
        if st.button("回前台"): 
            st.session_state.current_page="front_end"
            st.rerun()
        st.stop()

    c1, c2 = st.columns([1, 5])
    if c1.button("🔙 回前台"):
        st.session_state.current_page="front_end"
        st.rerun()
    if c2.button("登出"):
        st.session_state.is_admin_logged_in = False
        st.session_state.current_page="front_end"
        st.rerun()
    
    st.divider()
    t1, t2, t3 = st.tabs(["📝 回報稽核", "⚠️ 缺漏警示 (今日)", "📉 自動記點排行榜"])
    
    # Tab 1: 稽核 (檢查 EXIF)
    with t1:
        if not df_logs.empty:
            opts = df_logs.index.tolist()
            opts.sort(reverse=True)
            sel = st.selectbox("選擇檢查紀錄", opts, format_func=lambda x: f"{df_logs.at[x,'時間']} | {df_logs.at[x,'門市']} - {df_logs.at[x,'員工姓名']}")
            c_img, c_info = st.columns([1,1])
            with c_img:
                p_url = df_logs.at[sel, "照片"] if df_logs.at[sel, "照片"] else None
                if p_url:
                    with st.spinner("檢查 EXIF..."):
                        ok, msg, img = download_image_and_check_exif(p_url)
                    if img: st.image(img, width=400)
                    if "異常" in msg: st.error(msg)
                    elif "警告" in msg: st.warning(msg)
                    else: st.success(msg)
                else: st.info("無照片")
            with c_info: st.json(df_logs.loc[sel].astype(str).to_dict())
            st.dataframe(df_logs, use_container_width=True)
        else: st.info("目前無資料")
    
    # Tab 2: 今日缺漏
    with t2:
        today_str = get_tw_time().strftime("%Y-%m-%d")
        st.subheader(f"📅 今日 ({today_str}) 缺漏狀況")
        if not df_logs.empty:
            td = df_logs[df_logs["日期"] == today_str]
            res = []
            for s in STORE_LIST:
                sl = td[td["門市"]==s]
                # 找出沒做的
                miss = [t for t in REQUIRED_TASKS if t not in sl["任務項目"].unique()]
                # 計算今日缺點
                points = len(miss)
                # 儀容自檢如果沒人做也算缺點，但顯示上特別標註
                note = ""
                if "開店-儀容自檢" in miss: note = "(含儀容未打卡)"
                
                status = f"✅ All Done" if not miss else f"❌ 缺 {points} 項"
                
                res.append({
                    "門市": s, 
                    "狀態": status,
                    "系統自動記點": points,
                    "未完成項目": ", ".join(miss)
                })
            
            # 將有缺點的排前面
            df_res = pd.DataFrame(res).sort_values(by="系統自動記點", ascending=False)
            st.dataframe(df_res, use_container_width=True)
        else:
            st.info("今日尚無任何資料")

    # Tab 3: 自動記點統計 (新功能)
    with t3:
        st.subheader("📉 門市累計缺點排行榜 (自動計算)")
        st.caption("💡 說明：系統會自動計算歷史資料中，每日每店「未回報」的項目數量，每少一項記 1 點。")
        
        if not df_logs.empty:
            # 1. 執行運算
            df_penalty = calculate_missing_points(df_logs)
            
            if not df_penalty.empty:
                c_chart, c_data = st.columns([1, 1])
                
                with c_chart:
                    # 依門市加總缺點
                    rank_df = df_penalty.groupby("門市")["缺點數 (未回報)"].sum().reset_index()
                    rank_df = rank_df.sort_values(by="缺點數 (未回報)", ascending=False)
                    st.bar_chart(rank_df, x="門市", y="缺點數 (未回報)", color="#FF4B4B")
                
                with c_data:
                    st.write("📊 **缺點總表**")
                    st.dataframe(rank_df, use_container_width=True)
                
                st.divider()
                st.write("🔍 **每日扣分明細 (可展開查看)**")
                with st.expander("點擊查看詳細扣分紀錄"):
                    st.dataframe(df_penalty.sort_values(by="日期", ascending=False), use_container_width=True)
            else:
                st.success("🎉 太棒了！目前資料庫中沒有任何缺漏紀錄。")
        else:
            st.info("尚無資料可計算")
