import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# --- 設定 ---
# 這裡稍後會教你怎麼在雲端設定，本地測試先用 secrets.toml
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_URL = "你的_Google_Sheet_網址_貼在這裡" # ★請記得換成你的試算表網址

SPOON_TO_GRAM = 11  # 1匙 = 11克

# --- 連接 Google Sheets 函式 ---
def get_data():
    """連線並讀取資料"""
    # 這裡的邏輯是為了配合 Streamlit Cloud 的 Secrets 管理
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
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
# 如果有新貓咪，可以用輸入框新增
with st.sidebar:
    st.header("🐾 設定")
    selected_cat = st.selectbox("選擇貓咪", cat_list) if cat_list else None
    
    new_cat = st.text_input("或新增貓咪名字")
    if st.button("新增貓咪"):
        if new_cat and new_cat not in cat_list:
            selected_cat = new_cat
            st.success(f"已新增 {new_cat}，請去右邊新增第一筆紀錄！")
            st.rerun()

if not selected_cat and not new_cat:
    st.info("👈 請先在左側新增或選擇貓咪")
    st.stop()

current_cat = selected_cat if selected_cat else new_cat

# --- 主畫面：新增紀錄 ---
st.subheader(f"📝 新增紀錄 ({current_cat})")

# 使用 Columns 排版讓手機看比較順
c1, c2 = st.columns(2)
with c1:
    date_input = st.date_input("日期", datetime.now())
with c2:
    time_input = st.time_input("時間", datetime.now())

type_options = ["餵食", "餵藥", "體重", "排便", "備註"]
record_type = st.radio("類型", type_options, horizontal=True)

# 根據類型顯示不同提示
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
        # 簡單的防呆與全形轉半形
        final_content = content_val.replace("。", ".").replace("．", ".")
        
        # 準備寫入的資料
        row_data = [
            current_cat,
            date_input.strftime("%Y-%m-%d"),
            time_input.strftime("%H:%M"),
            record_type,
            final_content,
            note_val
        ]
        
        # 寫入 Google Sheets
        with st.spinner('正在寫入雲端...'):
            sheet.append_row(row_data)
            st.success("✅ 儲存成功！")
            time.sleep(1) # 讓使用者看到成功訊息
            st.rerun() # 重新整理頁面顯示最新資料

# --- 資料處理區 ---
# 篩選當前貓咪資料
if not df.empty:
    df_cat = df[df['Name'] == current_cat].copy()
    
    # 【排序邏輯】：日期(新->舊) + 時間(新->舊)
    # 先把日期時間合併成 datetime 物件方便排序
    df_cat['DateTime'] = pd.to_datetime(df_cat['Date'] + ' ' + df_cat['Time'])
    df_cat = df_cat.sort_values(by='DateTime', ascending=False)
    
    # 準備顯示用的 DataFrame (拿掉 Name 和輔助欄位)
    display_cols = ['Date', 'Time', 'Type', 'Content', 'Note']
    df_display = df_cat[display_cols].reset_index(drop=True)

    # --- 統計資訊 (當日儀表板) ---
    target_date_str = date_input.strftime("%Y-%m-%d")
    st.divider()
    st.subheader(f"📊 單日回顧 ({target_date_str})")
    
    # 篩選當日
    df_today = df_cat[df_cat['Date'] == target_date_str]
    
    # 計算食量
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

    # 顯示統計
    col1, col2 = st.columns(2)
    with col1:
        # 食量換算
        food_msg = "(無)"
        if food_total > 0:
            grams = round(food_total * SPOON_TO_GRAM, 2)
            food_msg = f"**{round(food_total, 3)} 匙** ({grams}g)"
        if food_others:
            food_msg += f" + {','.join(food_others)}"
        st.info(f"🍖 食量: {food_msg}")
        
        st.warning(f"💊 用藥: {', '.join(meds) if meds else '(無)'}")

    with col2:
        st.success(f"💩 排便: {', '.join(toilets) if toilets else '(無)'}")
        st.error(f"⚖️ 體重: {weights[0] if weights else '(無)'}")

    # --- 分頁顯示歷史資料 ---
    st.divider()
    st.subheader("📉 歷史紀錄")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["全部", "食量統計", "體重", "排便", "用藥"])
    
    with tab1:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.caption("* 如需修改或刪除，建議直接去 Google Sheet 操作最快")

    with tab2: # 食量每日統計
        # 使用 Pandas Groupby 快速計算
        df_food = df_cat[df_cat['Type'] == '餵食'].copy()
        if not df_food.empty:
            df_food['Val'] = pd.to_numeric(df_food['Content'], errors='coerce').fillna(0)
            stats = df_food.groupby('Date')['Val'].sum().reset_index().sort_values('Date', ascending=False)
            stats['Grams'] = stats['Val'] * SPOON_TO_GRAM
            stats.columns = ['日期', '總匙數', '總克數']
            st.dataframe(stats, use_container_width=True, hide_index=True)
        else:
            st.write("尚無餵食紀錄")

    with tab3: # 體重
        st.dataframe(df_display[df_display['Type']=='體重'], use_container_width=True, hide_index=True)
        # 畫個體重圖表
        if not df_display[df_display['Type']=='體重'].empty:
            chart_data = df_display[df_display['Type']=='體重'].copy()
            chart_data['WeightNum'] = pd.to_numeric(chart_data['Content'], errors='coerce')
            st.line_chart(chart_data, x='Date', y='WeightNum')

    with tab4: # 排便
        st.dataframe(df_display[df_display['Type']=='排便'], use_container_width=True, hide_index=True)

    with tab5: # 用藥
        st.dataframe(df_display[df_display['Type']=='餵藥'], use_container_width=True, hide_index=True)

else:
    st.write("目前資料庫是空的，請新增第一筆資料！")