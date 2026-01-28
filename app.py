import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from PIL import Image, ExifTags
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import io
import requests # 用於下載 Drive 圖片

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 設定區 (請修改這裡) ---
# https://forms.gle/1KHVtYzo785LnVKb7
GOOGLE_FORM_URL = "https://forms.gle/1KHVtYzo785LnVKb7" 

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
TASK_SOP = {
    "開店-儀容自檢": "📋 執行重點：全體員工皆需執行。確認穿著制服、配戴名牌，頭髮梳理整齊。",
    "開店-環境清掃": "🧹 執行重點：門市公用事項。櫃台桌面擦拭、店內地面掃拖、玻璃門清潔。",
    "營業-零用金確認": "💰 執行重點：門市公用事項。清點收銀機內零用金，確認金額正確無誤。",
    "營業-隨機抽盤": "📱 執行重點：門市公用事項。隨機挑選 3-5 樣高單價商品，核對數量。",
    "閉店-庫存表上傳": "📊 執行重點：門市公用事項。執行日結作業，產出今日庫存報表。"
}
REQUIRED_TASKS = list(TASK_SOP.keys())
STORE_LIST = ["文賢店", "東門店", "小西門店", "永康店", "歸仁店", "安中店", "鹽行店", "五甲店"]

# --- 雲端連線 ---
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    return creds

def get_data():
    """讀取 Google Sheet (表單回應)"""
    creds = init_connection()
    client = gspread.authorize(creds)
    # 注意：這裡讀取的是 '表單回應 1'，請確認您的試算表分頁名稱正確
    try:
        sheet = client.open("馬尼通訊即時回報系統_DB").worksheet("表單回應 1")
    except:
        # 如果找不到，嘗試讀取第一個分頁
        sheet = client.open("馬尼通訊即時回報系統_DB").sheet1
        
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # 資料清理與格式化
    if not df.empty:
        # 產生「日期」欄位 (從時間欄位擷取)
        # Google Form 時間格式通常是 "M/D/YYYY HH:MM:SS" 或 "YYYY/MM/DD"
        if "時間" in df.columns:
            df["時間"] = pd.to_datetime(df["時間"], errors='coerce')
            df["日期"] = df["時間"].dt.strftime("%Y-%m-%d")
            # 填補空值
            df["日期"] = df["日期"].fillna(datetime.now().strftime("%Y-%m-%d"))
        else:
            # 若無時間欄位，給予今日日期
            df["日期"] = datetime.now().strftime("%Y-%m-%d")
            
    return df

def get_tw_time():
    return datetime.now(timezone.utc) + timedelta(hours=8)

def download_image_and_check_exif(drive_url):
    """
    後台專用：從 Drive URL 下載圖片並檢查 EXIF
    回傳: (是否通過, 訊息, 圖片物件)
    """
    if not drive_url or "drive.google.com" not in str(drive_url):
        return True, "無照片或非 Drive 連結", None
    
    try:
        # 1. 取得 File ID
        file_id = drive_url.split("id=")[-1] if "id=" in drive_url else drive_url.split("/")[-2]
        
        # 2. 使用 API 下載圖片
        creds = init_connection()
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO(request.execute())
        
        # 3. 檢查 EXIF
        image = Image.open(file_content)
        exif_data = image._getexif()
        
        check_msg = "⚠️ 警告：無拍攝時間資訊"
        is_today = True # 預設通過 (避免誤判)
        
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

# --- 主程式 ---

if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "front_end"

# 讀取資料
try:
    df_logs = get_data()
except Exception as e:
    st.error(f"資料庫連線失敗: {e} \n請確認試算表名稱為 '馬尼通訊即時回報系統_DB' 且分頁為 '表單回應 1'")
    df_logs = pd.DataFrame()

# 側邊欄
st.sidebar.title("馬尼通訊管理系統")
with st.sidebar.expander("ℹ️ 系統資訊", expanded=False):
    st.markdown("v4.0 (Google Forms 整合版)")
    if st.session_state.current_page == "front_end":
        if st.button("🔐 進入管理後台"):
            st.session_state.current_page = "backend_login"
            st.rerun()

# --- 前台 ---
if st.session_state.current_page == "front_end":
    st.header("📋 門市每日職責回報")
    
    # 1. 門市看板
    selected_store = st.selectbox("🏬 請先選擇所屬門市 (查看進度)", ["請選擇..."] + STORE_LIST)
    
    if selected_store != "請選擇...":
        st.info(f"📊 [{selected_store}] 今日作業進度 (資料來源：Google 表單)", icon="📅")
        if st.button("🔄 刷新看板狀態"): st.rerun()

        today_str = get_tw_time().strftime("%Y-%m-%d")
        if not df_logs.empty:
            # 確保欄位名稱正確 (根據您的 Google Sheet 標題)
            # 這裡假設您已將標題改為簡稱，若無則需調整
            daily_logs = df_logs[
                (df_logs["門市"] == selected_store) & 
                (df_logs["日期"] == today_str)
            ]
        else:
            daily_logs = pd.DataFrame()

        status_cols = st.columns(len(REQUIRED_TASKS))
        for i, task in enumerate(REQUIRED_TASKS):
            with status_cols[i]:
                recs = daily_logs[daily_logs["任務項目"] == task] if not daily_logs.empty else pd.DataFrame()
                st.markdown(f"**{task.split('-')[1]}**")
                
                if task == "開店-儀容自檢":
                    if not recs.empty: st.success(f"已完成:\n{','.join(recs['員工姓名'].unique())}")
                    else: st.warning("未打卡")
                else:
                    if not recs.empty: st.success(f"✅ 已完成")
                    else: st.error("❌ 未執行")
    
    st.divider()

    # 2. 任務 SOP 提示
    task_type = st.selectbox("📌 查詢 SOP 執行重點", ["(請選擇任務查看)"] + REQUIRED_TASKS)
    if task_type != "(請選擇任務查看)":
        st.info(TASK_SOP[task_type])

    # 3. 跳轉按鈕
    st.markdown("### 👉 準備好回報了嗎？")
    st.link_button("🚀 點此前往 Google 表單回報 (不閃退)", GOOGLE_FORM_URL, type="primary")
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
    t1, t2 = st.tabs(["回報列表 & 防弊檢查", "缺漏表"])
    
    with t1:
        st.markdown("### 🔍 紀錄列表與防弊檢核")
        if not df_logs.empty:
            # 讓管理員選擇一筆資料進行深度檢查
            options = df_logs.index.tolist()
            # 倒序排列 (最新的在最上面)
            options.sort(reverse=True)
            
            select_idx = st.selectbox(
                "選擇要檢查的紀錄 (點擊後自動分析照片日期)", 
                options, 
                format_func=lambda x: f"{df_logs.at[x,'時間']} | {df_logs.at[x,'門市']} - {df_logs.at[x,'員工姓名']} ({df_logs.at[x,'任務項目']})"
            )
            
            col_img, col_info = st.columns([1, 1])
            
            with col_img:
                photo_url = df_logs.at[select_idx, "照片"]
                if photo_url:
                    st.markdown("**📸 照片預覽與 EXIF 分析：**")
                    with st.spinner("正在下載照片並檢查 EXIF..."):
                        is_ok, msg, img_obj = download_image_and_check_exif(photo_url)
                        
                    if img_obj:
                        st.image(img_obj, width=400)
                    
                    # 顯示檢查結果
                    if "異常" in msg:
                        st.error(msg)
                    elif "警告" in msg:
                        st.warning(msg)
                    else:
                        st.success(msg)
                else:
                    st.info("此紀錄無照片")

            with col_info:
                st.write("**詳細資料：**")
                st.json(df_logs.loc[select_idx].to_dict())

            st.divider()
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("目前無資料")

    with t2:
        st.write("今日缺漏")
        today_str = get_tw_time().strftime("%Y-%m-%d")
        if not df_logs.empty:
            td_logs = df_logs[df_logs["日期"] == today_str]
            res = []
            for s in STORE_LIST:
                sl = td_logs[td_logs["門市"]==s]
                comp = sl["任務項目"].unique()
                miss = [t for t in REQUIRED_TASKS if t!="開店-儀容自檢" and t not in comp]
                res.append({"門市":s, "未完成": ",".join(miss) if miss else "✅ Done"})
            st.dataframe(pd.DataFrame(res), use_container_width=True)


