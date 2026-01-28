import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from PIL import Image, ExifTags, ImageOps # 新增 ImageOps 用於轉正照片
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io # 新增 io 用於處理記憶體中的壓縮圖

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

# --- 雲端連線函式庫 ---
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
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

def compress_image(image_file):
    """
    功能：壓縮圖片並修正旋轉問題
    輸入：原始上傳檔案
    輸出：壓縮後的 BytesIO 物件 (可用於上傳)
    """
    image = Image.open(image_file)
    
    # 1. 修正手機照片旋轉問題 (EXIF Transpose)
    image = ImageOps.exif_transpose(image)
    
    # 2. 調整尺寸 (若寬度大於 1024px 則等比縮小)
    max_width = 1024
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        image = image.resize((max_width, new_height))
    
    # 3. 轉換為 RGB (避免 PNG 透明度造成存檔錯誤)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
        
    # 4. 壓縮存入記憶體
    output = io.BytesIO()
    # quality=60 可大幅減少檔案大小但肉眼幾乎看不出差異
    image.save(output, format="JPEG", quality=60, optimize=True)
    output.seek(0) # 指標歸零
    return output

def upload_to_drive(file_obj, filename, mime_type='image/jpeg'):
    """上傳到 Google Drive"""
    creds = init_connection()
    service = build('drive', 'v3', credentials=creds)
    folder_id = st.secrets["drive_folder_id"]
    
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    
    # 使用 resumable=True 對大檔案較穩定，這裡我們上傳壓縮後的流
    media = MediaIoBaseUpload(file_obj, mimetype=mime_type, resumable=True)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    permission = {'type': 'anyone', 'role': 'reader'}
    service.permissions().create(
        fileId=file.get('id'),
        body=permission
    ).execute()
    
    return file.get('webViewLink')

def save_data(row_data):
    creds = init_connection()
    client = gspread.authorize(creds)
    sheet = client.open("馬尼通訊即時回報系統_DB").sheet1
    sheet.append_row(row_data)

def get_tw_time():
    return datetime.now(timezone.utc) + timedelta(hours=8)

# --- EXIF 檢查 (輕量化版) ---
def check_is_photo_today(uploaded_file):
    try:
        uploaded_file.seek(0)
        # 這裡只讀取 Header，不載入整張圖，節省記憶體
        image = Image.open(uploaded_file)
        exif_data = image._getexif()
        uploaded_file.seek(0) # 檢查完畢務必歸零
        
        if not exif_data:
            return True, "⚠️ 警告：無法讀取拍攝時間，本次放行。"

        date_taken_str = None
        for tag, value in exif_data.items():
            decoded = ExifTags.TAGS.get(tag, tag)
            if decoded == "DateTimeOriginal":
                date_taken_str = value
                break
        
        if date_taken_str:
            try:
                date_obj = datetime.strptime(date_taken_str, "%Y:%m:%d %H:%M:%S")
                today_str = get_tw_time().strftime("%Y-%m-%d")
                photo_date_str = date_obj.strftime("%Y-%m-%d")
                if photo_date_str == today_str:
                    return True, "✅ 照片為今日拍攝"
                else:
                    return False, f"❌ 錯誤：照片拍攝於 {photo_date_str}，非今日！"
            except:
                return True, "⚠️ 日期格式解析失敗，放行。"
        else:
            return True, "⚠️ 照片無日期資訊，放行。"
    except Exception as e:
        uploaded_file.seek(0)
        return True, f"⚠️ 讀取錯誤: {e}"

# --- 主程式 ---

if 'is_admin_logged_in' not in st.session_state:
    st.session_state.is_admin_logged_in = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "front_end"

try:
    df_logs = get_data()
except Exception as e:
    st.error(f"❌ 無法連線至資料庫。\n錯誤訊息: {e}")
    df_logs = pd.DataFrame(columns=["時間", "日期", "門市", "員工姓名", "任務項目", "狀態", "照片連結", "系統計點"])

# 側邊欄
st.sidebar.title("馬尼通訊管理系統")
with st.sidebar.expander("ℹ️ 系統資訊", expanded=False):
    st.markdown("v2.2 (圖片壓縮優化版)")
    if st.session_state.current_page == "front_end":
        if st.button("🔐 進入管理後台"):
            st.session_state.current_page = "backend_login"
            st.rerun()

# --- 頁面邏輯 ---

# A. 前台回報
if st.session_state.current_page == "front_end":
    st.header("📋 門市每日職責回報")
    
    if st.button("🔄 刷新看板數據"):
        st.rerun()

    selected_store = st.selectbox("🏬 請先選擇所屬門市", ["請選擇..."] + STORE_LIST, key="store_selector")

    if selected_store != "請選擇...":
        st.info(f"📊 [{selected_store}] 今日作業進度看板 (即時同步)", icon="📅")
        
        tw_now = get_tw_time()
        today_str = tw_now.strftime("%Y-%m-%d")
        
        if not df_logs.empty and "日期" in df_logs.columns:
            df_logs["日期"] = df_logs["日期"].astype(str)
            daily_logs = df_logs[
                (df_logs["門市"] == selected_store) & 
                (df_logs["日期"] == today_str)
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

        col_task_select, col_sop = st.columns([1, 2])
        with col_task_select:
            task_type = st.selectbox("📌 選擇今日要執行的項目", REQUIRED_TASKS, key="task_selector")
        with col_sop:
            if task_type: st.info(TASK_SOP[task_type], icon="ℹ️")

        with st.form("task_form", clear_on_submit=True):
            emp_name = st.text_input("執行員工姓名")
            photo = None
            is_checked = False
            
            if task_type == "開店-儀容自檢":
                st.markdown(f"**📸 [{task_type}] 需拍照存證：**")
                photo = st.file_uploader("點擊開啟相機", type=['jpg', 'jpeg', 'png'])
            else:
                st.markdown(f"**✅ [{task_type}] 確認執行：**")
                is_checked = st.checkbox(f"我已閱讀 SOP 並完成 [{task_type}]")
            
            submit = st.form_submit_button("確認提交", use_container_width=True)
            
            if submit:
                error_msg = ""
                
                if not emp_name:
                    error_msg = "❌ 請輸入員工姓名！"
                elif task_type == "開店-儀容自檢":
                    if not photo:
                        error_msg = "❌ 必須上傳照片！"
                    else:
                        # 1. 先檢查 EXIF (使用原始檔)
                        pass_exif, exif_msg = check_is_photo_today(photo)
                        if not pass_exif: error_msg = exif_msg

                elif task_type != "開店-儀容自檢" and not is_checked:
                    error_msg = "❌ 請勾選確認已執行！"
                
                if error_msg:
                    st.error(error_msg)
                else:
                    with st.spinner("影像壓縮與上傳中..."):
                        current_tw = get_tw_time()
                        time_str = current_tw.strftime("%Y-%m-%d %H:%M:%S")
                        date_str = current_tw.strftime("%Y-%m-%d")
                        
                        photo_link = "無"
                        if photo:
                            try:
                                # 2. 進行壓縮 (關鍵步驟)
                                compressed_image = compress_image(photo)
                                file_name = f"{date_str}_{selected_store}_{emp_name}_{task_type}.jpg"
                                # 3. 上傳壓縮後的檔案
                                photo_link = upload_to_drive(compressed_image, file_name)
                            except Exception as e:
                                st.error(f"圖片處理失敗，可能是記憶體不足或檔案毀損: {e}")
                                st.stop()
                        
                        row = [
                            time_str, date_str, selected_store, emp_name, 
                            task_type, "✅ 已提交", photo_link, 0
                        ]
                        
                        save_data(row)
                        st.success("✅ 提交成功！")
                        st.rerun()

# B. 後台
elif st.session_state.current_page in ["backend_login", "backend_main"]:
    st.header("🔐 管理後台")
    
    if not st.session_state.is_admin_logged_in:
        pwd = st.text_input("密碼", type="password")
        c1, c2 = st.columns([1, 4])
        if c1.button("登入"):
            if pwd == "1234":
                st.session_state.is_admin_logged_in = True
                st.session_state.current_page = "backend_main"
                st.rerun()
            else:
                st.error("❌ 錯誤")
        if c2.button("🔙 返回前台"):
            st.session_state.current_page = "front_end"
            st.rerun()
        st.stop()

    c1, c2 = st.columns([1, 5])
    if c1.button("🔙 返回前台"):
        st.session_state.current_page = "front_end"
        st.rerun()
    if c2.button("登出"):
        st.session_state.is_admin_logged_in = False
        st.session_state.current_page = "front_end"
        st.rerun()
        
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["📊 回報列表", "⚠️ 缺漏檢核", "📈 統計報表"])
    
    with tab1:
        st.write("💡 資料來源：Google Sheets (即時同步)")
        display_df = df_logs.copy()
        st.dataframe(display_df, use_container_width=True)
        
        st.divider()
        st.subheader("🔍 照片檢視")
        if not df_logs.empty:
            options = df_logs.index.tolist()
            select_idx = st.selectbox(
                "選擇紀錄", 
                options, 
                format_func=lambda x: f"{df_logs.at[x, '日期']} {df_logs.at[x, '門市']} - {df_logs.at[x, '員工姓名']} ({df_logs.at[x, '任務項目']})"
            )
            
            link = df_logs.at[select_idx, "照片連結"]
            if "http" in str(link):
                st.image(link, caption="點擊右上角可放大", width=400)
                st.markdown(f"[🔗 點此開啟原始圖片]({link})")
            else:
                st.info("此紀錄無照片連結")

    with tab2:
        st.subheader("⚠️ 今日缺漏 (即時)")
        today_str = get_tw_time().strftime("%Y-%m-%d")
        
        report_status = []
        if not df_logs.empty and "日期" in df_logs.columns:
            today_logs = df_logs[df_logs["日期"] == today_str]
        else:
            today_logs = pd.DataFrame()
            
        for store in STORE_LIST:
            store_logs = today_logs[today_logs["門市"] == store]
            completed = store_logs["任務項目"].unique().tolist()
            store_tasks = [t for t in REQUIRED_TASKS if t != "開店-儀容自檢"]
            missing = [t for t in store_tasks if t not in completed]
            
            report_status.append({
                "門市": store,
                "未完成數": len(missing),
                "未完成項目": ", ".join(missing) if missing else "✅ All Done"
            })
        st.dataframe(pd.DataFrame(report_status), use_container_width=True)

    with tab3:
        st.subheader("📈 統計")
        if not df_logs.empty:
            rank_df = df_logs.groupby("門市").size().reset_index(name="回報次數")
            st.bar_chart(rank_df, x="門市", y="回報次數")
        else:
            st.info("尚無數據")
