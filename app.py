import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from PIL import Image, ExifTags, ImageOps
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import gc

# --- 1. 頁面設定 ---
st.set_page_config(page_title="馬尼通訊即時管理系統", layout="wide")

# --- 全域變數 ---
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
    creds = init_connection()
    client = gspread.authorize(creds)
    sheet = client.open("馬尼通訊即時回報系統_DB").sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty and "日期" in df.columns:
        df["日期"] = df["日期"].astype(str)
    return df

def compress_image(image_file, max_width=800):
    """
    僅針對「檔案上傳」的高畫質照片進行壓縮。
    網頁相機照片不使用此函式，以避免記憶體爆量。
    """
    try:
        image = Image.open(image_file)
        image = ImageOps.exif_transpose(image) # 轉正
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        image.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=50, optimize=True)
        output.seek(0)
        
        del image
        gc.collect()
        return output
    except Exception as e:
        return None

def upload_to_drive(file_obj, filename, mime_type='image/jpeg'):
    creds = init_connection()
    service = build('drive', 'v3', credentials=creds)
    folder_id = st.secrets["drive_folder_id"]
    
    file_metadata = {'name': filename, 'parents': [folder_id]}
    
    # 使用 resumable 上傳，並直接讀取 file_obj，不進行額外處理
    media = MediaIoBaseUpload(file_obj, mimetype=mime_type, resumable=True)
    
    file = service.files().create(
        body=file_metadata, media_body=media, fields='id, webViewLink'
    ).execute()
    
    permission = {'type': 'anyone', 'role': 'reader'}
    service.permissions().create(fileId=file.get('id'), body=permission).execute()
    return file.get('webViewLink')

def save_data(row_data):
    creds = init_connection()
    client = gspread.authorize(creds)
    sheet = client.open("馬尼通訊即時回報系統_DB").sheet1
    sheet.append_row(row_data)

def get_tw_time():
    return datetime.now(timezone.utc) + timedelta(hours=8)

def check_is_photo_today(uploaded_file):
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        exif_data = image._getexif()
        uploaded_file.seek(0)
        del image
        gc.collect()
        
        if not exif_data: return True, "⚠️ 警告：無法讀取拍攝時間，本次放行。"

        date_taken_str = None
        for tag, value in exif_data.items():
            if ExifTags.TAGS.get(tag, tag) == "DateTimeOriginal":
                date_taken_str = value
                break
        
        if date_taken_str:
            date_obj = datetime.strptime(date_taken_str, "%Y:%m:%d %H:%M:%S")
            today_str = get_tw_time().strftime("%Y-%m-%d")
            if date_obj.strftime("%Y-%m-%d") == today_str:
                return True, "✅ 照片為今日拍攝"
            else:
                return False, f"❌ 錯誤：照片拍攝於 {date_obj.strftime('%Y-%m-%d')}，非今日！"
        return True, "⚠️ 無日期資訊，放行。"
    except:
        uploaded_file.seek(0)
        return True, "⚠️ 讀取錯誤，略過檢查。"

# --- 主程式 ---

if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "front_end"

try:
    df_logs = get_data()
except:
    df_logs = pd.DataFrame(columns=["時間", "日期", "門市", "員工姓名", "任務項目", "狀態", "照片連結", "系統計點"])

# 側邊欄
st.sidebar.title("馬尼通訊管理系統")
with st.sidebar.expander("ℹ️ 系統資訊", expanded=False):
    st.markdown("v2.5 (直通上傳版)")
    if st.session_state.current_page == "front_end":
        if st.button("🔐 進入管理後台"):
            st.session_state.current_page = "backend_login"
            st.rerun()

# --- 前台 ---
if st.session_state.current_page == "front_end":
    st.header("📋 門市每日職責回報")
    if st.button("🔄 刷新看板"): st.rerun()

    selected_store = st.selectbox("🏬 請先選擇所屬門市", ["請選擇..."] + STORE_LIST, key="store_selector")

    if selected_store != "請選擇...":
        # 看板邏輯
        st.info(f"📊 [{selected_store}] 今日作業進度", icon="📅")
        today_str = get_tw_time().strftime("%Y-%m-%d")
        
        if not df_logs.empty and "日期" in df_logs.columns:
            df_logs["日期"] = df_logs["日期"].astype(str)
            daily_logs = df_logs[(df_logs["門市"] == selected_store) & (df_logs["日期"] == today_str)]
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

        # 回報區
        c1, c2 = st.columns([1, 2])
        task_type = c1.selectbox("📌 選擇今日要執行的項目", REQUIRED_TASKS)
        if task_type: c2.info(TASK_SOP[task_type])

        with st.form("task_form", clear_on_submit=True):
            emp_name = st.text_input("執行員工姓名")
            photo = None
            is_checked = False
            
            if task_type == "開店-儀容自檢":
                st.markdown(f"**📸 [{task_type}] 需拍照存證：**")
                
                # --- v2.5 重要修改 ---
                use_webcam = st.toggle("📷 使用「網頁輕量相機」 (推薦)")
                
                if use_webcam:
                    st.warning("⚠️ 若點擊下方按鈕沒反應，請點選 LINE 右上角『使用預設瀏覽器開啟』(Chrome/Safari)。")
                    photo = st.camera_input("請拍攝儀容")
                else:
                    st.caption("ℹ️ 從圖庫上傳：適合已用原相機拍好的照片。")
                    photo = st.file_uploader("選擇照片", type=['jpg', 'jpeg', 'png'])
            
            else:
                st.markdown(f"**✅ [{task_type}] 確認執行：**")
                is_checked = st.checkbox("我已閱讀 SOP 並完成")
            
            if st.form_submit_button("確認提交"):
                err = ""
                if not emp_name: err = "❌ 缺姓名"
                elif task_type == "開店-儀容自檢":
                    if not photo: err = "❌ 缺照片"
                    elif not use_webcam:
                        # 只有上傳檔案才檢查 EXIF
                        ok, msg = check_is_photo_today(photo)
                        if not ok: err = msg
                elif not is_checked: err = "❌ 請勾選確認"
                
                if err:
                    st.error(err)
                else:
                    try:
                        with st.spinner("資料上傳中 (請勿關閉)..."):
                            curr = get_tw_time()
                            link = "無"
                            if photo:
                                final_file = None
                                
                                # --- v2.5 核心修改：直通模式 ---
                                if use_webcam:
                                    # 網頁相機照片：完全不處理，直接轉傳 (最省記憶體)
                                    # st.camera_input 回傳的就是 BytesIO，直接用
                                    final_file = photo
                                else:
                                    # 檔案上傳：可能很大，必須壓縮
                                    final_file = compress_image(photo)
                                
                                if final_file:
                                    fname = f"{curr.strftime('%Y-%m-%d')}_{selected_store}_{emp_name}_{task_type}.jpg"
                                    link = upload_to_drive(final_file, fname)
                                    
                                    # 釋放記憶體
                                    del final_file
                                    gc.collect()
                            
                            row = [curr.strftime("%Y-%m-%d %H:%M:%S"), curr.strftime("%Y-%m-%d"), 
                                   selected_store, emp_name, task_type, "✅ 已提交", link, 0]
                            save_data(row)
                            st.success("✅ 成功！")
                            st.rerun()
                    except Exception as e:
                        st.error(f"上傳失敗: {e} (建議使用網頁相機或降低畫質)")
                        gc.collect()

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
    
    st.divider()
    t1, t2 = st.tabs(["回報列表", "缺漏表"])
    
    with t1:
        st.dataframe(df_logs, use_container_width=True)
        if not df_logs.empty:
            opts = df_logs.index.tolist()
            idx = st.selectbox("查看照片", opts, format_func=lambda x: f"{df_logs.at[x,'門市']} {df_logs.at[x,'員工姓名']}")
            link = df_logs.at[idx, "照片連結"]
            if "http" in str(link): st.markdown(f"[📷 點此開啟照片]({link})")
            else: st.info("無照片")
            
    with t2:
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
