import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import pytz # 用來處理時區

# --- 設定 ---
# 請貼上你的 Google Sheet 網址
SHEET_URL = "https://docs.google.com/spreadsheets/d/你的ID/edit" 

SPOON_TO_GRAM = 11  # 1匙 = 11克

# --- 連接 Google Sheets 函式 ---
def get_data():
    """連線並讀取資料"""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    return sheet, data

# --- 介面開始 ---
st.set_page_config(page_title="🐱 貓咪生活日記", page_icon="🐾", layout="wide")

st.title("🐈 貓咪生活日記 (雲端版)")

# 嘗試連線
try:
    sheet, data = get_data()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"資料庫連線失敗，請檢查 Secrets 設定。\n錯誤訊息: {e}")
    st.stop()

# --- 側邊欄：貓咪選擇 ---
cat_list = df['Name'].unique().tolist() if not df.empty else []
with st.sidebar:
    st.header("🐾 設定")
    # 如果還沒有任何貓咪資料，提示新增
    if not cat_list:
        st.warning("目前沒有貓咪資料，請先新增！")
        selected_cat = None
    else:
        selected_cat = st.selectbox("選擇貓咪", cat_list)
    
    st.divider()
    new_cat = st.text_input("新增貓咪名字")
    if st.button("➕ 新增貓咪"):
        if new_cat and new_cat not in cat_list:
            selected_cat = new_cat
            # 在介面上給個提示，實際寫入等下面按儲存時一起做
            st.success(f"準備新增 {new_cat}，請去右邊輸入第一筆紀錄！")
            time.sleep(1)
            st.rerun()

# 如果使用者剛輸入新名字，優先使用新名字
current_cat = new_cat if new_cat else selected_cat

if not current_cat:
    st.info("👈 請先在左側新增貓咪")
    st.stop()

# --- 主畫面：新增紀錄 ---
st.subheader(f"📝 新增紀錄 ({current_cat})")

# === 【重點修正】 時間處理與選單 ===
# 1. 取得台灣時間
tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.now(tw_tz)

# 2. 建立三個欄位：日期 | 時 | 分
col_date, col_hour, col_min = st.columns([2, 1, 1])

with col_date:
    date_input = st.date_input("日期", now_tw)

with col_hour:
    # 產生 00~23 的清單
    hours = [f"{i:02d}" for i in range(24)]
    # 預設選中現在的小時
    hour_val = st.selectbox("時", hours, index=now_tw.hour)

with col_min:
    # 產生 00~59 的清單 (每一分鐘一格)
    mins = [f"{i:02d}" for i in range(60)]
    # 預設選中現在的分鐘
    min_val = st.selectbox("分", mins, index=now_tw.minute)

# 3. 組合時間字串
time_str = f"{hour_val}:{min_val}"
# =================================

type_options = ["餵食", "餵藥", "體重", "排便", "備註"]
# 使用 pills (膠囊按鈕) 或 radio，這裡維持 radio 比較穩定
record_type = st.radio("類型", type_options, horizontal=True)

help_text = ""
if record_type == "餵食": help_text = "輸入湯匙數 (如 0.5)"
elif record_type == "體重": help_text = "輸入公斤數 (如 5.2)"
elif record_type == "餵藥": help_text = "輸入藥名 (如 抗生素)"

content_val = st.text_input("內容 / 數值", placeholder=help_text)
note_val = st.text_input("備註 (選填)")

if st.button("💾 儲存紀錄", type="primary", use_container_width=True):
    if not content_val:
        st.warning("請輸入內容！")
    else:
        # 防呆
        final_content = content_val.replace("。", ".").replace("．", ".")
        
        row_data = [
            current_cat,
            date_input.strftime("%Y-%m-%d"),
            time_str, # 使用我們組合好的 HH:MM
            record_type,
            final_content,
            note_val
        ]
        
        with st.spinner('正在寫入雲端...'):
            sheet.append_row(row_data)
            st.success("✅ 儲存成功！")
            time.sleep(1)
            st.rerun()

# --- 資料處理區 ---
if not df.empty:
    # 篩選當前貓咪
    df_cat = df[df['Name'] == current_cat].copy()
    
    # 【排序邏輯】：日期(新->舊) + 時間(新->舊)
    # 將日期與時間合併成一個 datetime 物件來排序，確保跨日或同日時間準確
    try:
        df_cat['DateTime'] = pd.to_datetime(df_cat['Date'] + ' ' + df_cat['Time'])
        # ascending=False 代表降冪 (大->小，即 新->舊)
        df_cat = df_cat.sort_values(by='DateTime', ascending=False)
    except:
        # 萬一舊資料格式有誤，就不排 DateTime，直接排 Date
        df_cat = df_cat.sort_values(by=['Date', 'Time'], ascending=[False, False])
    
    display_cols = ['Date', 'Time', 'Type', 'Content', 'Note']
    df_display = df_cat[display_cols].reset_index(drop=True)

    # --- 統計資訊 (單日回顧) ---
    target_date_str = date_input.strftime("%Y-%m-%d")
    st.divider()
    st.subheader(f"📊 單日回顧 ({target_date_str})")
    
    df_today = df_cat[df_cat['Date'] == target_date_str]
    
    food_total = 0.0
    food_others = []
    meds = []
    toilets = []
    weights = []
    
    for _, row in df_today.iterrows():
        t = row['Type']
        c = str(row['Content'])
        if t == "餵食":
            try:
                food_total += float(c)
            except:
                food_others.append(c)
        elif t == "餵藥": meds.append(f"{row['Time']} {c}")
        elif t == "排便": toilets.append(f"{row['Time']} {c}")
        elif t == "體重": weights.append(f"{c} kg")

    c1, c2 = st.columns(2)
    with c1:
        food_msg = "(無)"
        if food_total > 0:
            grams = round(food_total * SPOON_TO_GRAM, 2)
            food_msg = f"**{round(food_total, 3)} 匙** ({grams}g)"
        if food_others:
            food_msg += f" + {','.join(food_others)}"
        st.info(f"🍖 食量: {food_msg}")
        
        st.warning(f"💊 用藥: {', '.join(meds) if meds else '(無)'}")

    with c2:
        st.success(f"💩 排便: {', '.join(toilets) if toilets else '(無)'}")
        st.error(f"⚖️ 體重: {weights[0] if weights else '(無)'}")

    # --- 歷史紀錄 (分頁) ---
    st.divider()
    st.subheader("📉 歷史紀錄")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["全部", "食量統計", "體重", "排便", "用藥"])
    
    with tab1:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.caption("* 如需修改，請至 Google Sheet 操作")

    with tab2: # 食量
        df_food = df_cat[df_cat['Type'] == '餵食'].copy()
        if not df_food.empty:
            df_food['Val'] = pd.to_numeric(df_food['Content'], errors='coerce').fillna(0)
            stats = df_food.groupby('Date')['Val'].sum().reset_index().sort_values('Date', ascending=False)
            stats['Grams'] = stats['Val'] * SPOON_TO_GRAM
            stats.columns = ['日期', '總匙數', '總克數']
            st.dataframe(stats, use_container_width=True, hide_index=True)
        else:
            st.write("尚無資料")

    with tab3: # 體重
        st.dataframe(df_display[df_display['Type']=='體重'], use_container_width=True, hide_index=True)
        # 簡單圖表
        if not df_display[df_display['Type']=='體重'].empty:
            chart_df = df_display[df_display['Type']=='體重'].copy()
            chart_df['WeightNum'] = pd.to_numeric(chart_df['Content'], errors='coerce')
            st.line_chart(chart_df, x='Date', y='WeightNum')

    with tab4: # 排便
        st.dataframe(df_display[df_display['Type']=='排便'], use_container_width=True, hide_index=True)

    with tab5: # 用藥
        st.dataframe(df_display[df_display['Type']=='餵藥'], use_container_width=True, hide_index=True)

else:
    st.write("目前資料庫是空的，請新增第一筆資料！")