import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import pytz
import os

# --- 設定 ---
SHEET_URL = st.secrets["private_sheet_url"]
SPOON_TO_GRAM = 11  # 1匙 = 11克
HOME_IMAGE_PATH = "home_cat.jpg" # 照片檔名

# --- 連接 Google Sheets 函式 ---
def get_data():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    return sheet, data

# --- 介面開始 ---
st.set_page_config(page_title="貓咪生活日記", page_icon="🐾", layout="wide")

# 嘗試連線
try:
    sheet, data = get_data()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"資料庫連線失敗，請檢查 Secrets 設定。\n錯誤訊息: {e}")
    st.stop()

# --- 側邊欄 ---
with st.sidebar:
    st.header("🐾 選單")
    
    # 取得貓咪列表
    cat_list = df['Name'].unique().tolist() if not df.empty else []
    
    # 【新增】將「主畫面」加入選項的最前面
    menu_options = ["🏠 主畫面"] + cat_list
    
    # 讓使用者選擇
    selected_option = st.selectbox("請選擇", menu_options)
    
    st.divider()
    
    # 新增貓咪功能保留在下方
    with st.expander("➕ 新增其他貓咪"):
        new_cat = st.text_input("輸入新名字")
        if st.button("確認新增"):
            if new_cat and new_cat not in cat_list:
                # 這裡我們用 session_state 來暫存新貓咪，讓頁面重整後自動跳轉
                st.session_state['new_cat_name'] = new_cat
                st.success(f"準備新增 {new_cat}，請去右邊輸入第一筆紀錄！")
                time.sleep(1)
                st.rerun()

# 檢查是否有剛新增的貓咪 (讓使用者不用重新選)
if 'new_cat_name' in st.session_state:
    current_cat = st.session_state['new_cat_name']
    # 清除暫存，避免下次卡住
    del st.session_state['new_cat_name']
    is_home = False
else:
    # 判斷是否為主畫面
    if selected_option == "🏠 主畫面":
        is_home = True
        current_cat = None
    else:
        is_home = False
        current_cat = selected_option

# ==========================================
# 🏠 顯示主畫面 (照片模式)
# ==========================================
if is_home:
    st.title("🐈 貓咪生活日記")
    st.write("### Welcome Home! 🐾")
    
    # 檢查照片是否存在，存在就顯示
    if os.path.exists(HOME_IMAGE_PATH):
        st.image(HOME_IMAGE_PATH, use_container_width=True, caption="我們這一家 ❤️")
    else:
        # 如果使用者忘記上傳照片，顯示提示
        st.info(f"請確認已將照片 `{HOME_IMAGE_PATH}` 上傳至 GitHub 的專案資料夾中。")
        st.write("(目前顯示預設畫面)")

# ==========================================
# 🐾 顯示貓咪紀錄介面 (原本的功能)
# ==========================================
else:
    st.subheader(f"🐾 {current_cat}")

    tw_tz = pytz.timezone('Asia/Taipei')
    now_tw = datetime.now(tw_tz)

    col_date, col_hour, col_min = st.columns([2, 1, 1])
    with col_date:
        date_input = st.date_input("日期", now_tw)
    with col_hour:
        hours = [f"{i:02d}" for i in range(24)]
        hour_val = st.selectbox("時", hours, index=now_tw.hour)
    with col_min:
        mins = [f"{i:02d}" for i in range(60)]
        min_val = st.selectbox("分", mins, index=now_tw.minute)

    time_str = f"{hour_val}:{min_val}"

    type_options = ["餵食", "餵藥", "體重", "排便", "其他"]
    record_type = st.radio("類型", type_options, horizontal=True, label_visibility="collapsed") 

    help_text = ""
    if record_type == "餵食": help_text = "輸入湯匙數 (如 0.5)"
    elif record_type == "體重": help_text = "輸入公斤數 (如 5.2)"
    elif record_type == "餵藥": help_text = "輸入藥名 (如 抗生素)"
    elif record_type == "其他": help_text = "輸入標題 (如 剪指甲、吐毛)"

    content_val = st.text_input("內容 / 數值", placeholder=help_text)
    note_val = st.text_input("備註說明 (選填)")

    if st.button("💾 儲存紀錄", type="primary", use_container_width=True):
        if not content_val:
            st.warning("請輸入內容！")
        else:
            final_content = content_val.replace("。", ".").replace("．", ".")
            row_data = [
                current_cat,
                date_input.strftime("%Y-%m-%d"),
                time_str,
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
        # 篩選該貓咪
        df_cat = df[df['Name'] == current_cat].copy()
        
        # 如果該貓咪還沒有資料 (剛新增的狀況)
        if df_cat.empty:
            st.info("這位主子還沒有紀錄喔，趕快輸入第一筆吧！")
        else:
            try:
                df_cat['DateTime'] = pd.to_datetime(df_cat['Date'] + ' ' + df_cat['Time'])
                df_cat = df_cat.sort_values(by='DateTime', ascending=False)
            except:
                df_cat = df_cat.sort_values(by=['Date', 'Time'], ascending=[False, False])
            
            display_cols = ['Date', 'Time', 'Type', 'Content', 'Note']
            df_display = df_cat[display_cols].reset_index(drop=True)

            # --- 單日回顧 ---
            target_date_str = date_input.strftime("%Y-%m-%d")
            st.divider()
            st.subheader(f"📊 單日回顧 ({target_date_str})")
            
            df_today = df_cat[df_cat['Date'] == target_date_str]
            food_total = 0.0
            food_others = []
            meds = []
            toilets = []
            weights = []
            others_list = []
            
            for _, row in df_today.iterrows():
                t = row['Type']
                c = str(row['Content'])
                note_suffix = f" ({row['Note']})" if row['Note'] else ""
                
                if t == "餵食":
                    try: food_total += float(c)
                    except: food_others.append(c)
                elif t == "餵藥": meds.append(f"{row['Time']} {c}{note_suffix}")
                elif t == "排便": toilets.append(f"{row['Time']} {c}{note_suffix}")
                elif t == "體重": weights.append(f"{c} kg")
                elif t == "其他" or t == "備註": 
                    others_list.append(f"{row['Time']} {c}{note_suffix}")

            c1, c2 = st.columns(2)
            with c1:
                food_msg = "(無)"
                if food_total > 0:
                    grams = round(food_total * SPOON_TO_GRAM, 2)
                    food_msg = f"**{round(food_total, 3)} 匙** ({grams}g)"
                if food_others: food_msg += f" + {','.join(food_others)}"
                st.info(f"🍖 食量: {food_msg}")
                st.warning(f"💊 用藥: {', '.join(meds) if meds else '(無)'}")

            with c2:
                st.success(f"💩 排便: {', '.join(toilets) if toilets else '(無)'}")
                weight_msg = weights[0] if weights else "(無)"
                st.error(f"⚖️ 體重: {weight_msg}")
                others_msg = ", ".join(others_list) if others_list else "(無)"
                st.info(f"📝 其他: {others_msg}")

            # --- 管理與修改 ---
            st.divider()
            with st.expander("🛠️ 管理與修改 (點此展開)", expanded=False):
                edit_limit = st.number_input("欲載入最近幾筆紀錄？", min_value=10, max_value=1000, value=20, step=10)
                st.caption(f"目前顯示最近 {edit_limit} 筆。")
                
                recent_records = df_cat.head(edit_limit).copy()
                recent_records['Label'] = recent_records.apply(
                    lambda x: f"{x['Date']} {x['Time']} | {x['Type']} | {x['Content']}", axis=1
                )
                
                selected_label = st.selectbox("選擇要操作的項目:", recent_records['Label'].tolist())
                
                if selected_label:
                    target_row = recent_records[recent_records['Label'] == selected_label].iloc[0]
                    col_edit_1, col_edit_2 = st.columns(2)
                    with col_edit_1:
                        new_content_edit = st.text_input("修改內容/數值", value=target_row['Content'])
                    with col_edit_2:
                        new_note_edit = st.text_input("修改備註說明", value=target_row['Note'])
                    
                    col_btn_1, col_btn_2 = st.columns([1, 1])
                    with col_btn_1:
                        if st.button("🗑️ 刪除此紀錄", type="primary"):
                            with st.spinner("正在刪除..."):
                                try:
                                    row_to_delete = None
                                    for i, record in enumerate(data):
                                        if (record['Name'] == current_cat and 
                                            record['Date'] == target_row['Date'] and 
                                            str(record['Time']) == str(target_row['Time']) and 
                                            record['Type'] == target_row['Type'] and 
                                            str(record['Content']) == str(target_row['Content'])):
                                            row_to_delete = i + 2
                                            break
                                    if row_to_delete:
                                        sheet.delete_rows(row_to_delete)
                                        st.success("已刪除！")
                                        time.sleep(1)
                                        st.rerun()
                                    else: st.error("找不到原始資料。")
                                except Exception as e: st.error(f"刪除失敗: {e}")

                    with col_btn_2:
                        if st.button("✏️ 確認修改"):
                            with st.spinner("正在更新..."):
                                try:
                                    row_to_update = None
                                    for i, record in enumerate(data):
                                        if (record['Name'] == current_cat and 
                                            record['Date'] == target_row['Date'] and 
                                            str(record['Time']) == str(target_row['Time']) and 
                                            record['Type'] == target_row['Type'] and 
                                            str(record['Content']) == str(target_row['Content'])):
                                            row_to_update = i + 2
                                            break
                                    if row_to_update:
                                        sheet.update_cell(row_to_update, 5, new_content_edit)
                                        sheet.update_cell(row_to_update, 6, new_note_edit)
                                        st.success("更新成功！")
                                        time.sleep(1)
                                        st.rerun()
                                    else: st.error("找不到原始資料。")
                                except Exception as e: st.error(f"更新失敗: {e}")

            # --- 歷史紀錄 (分頁) ---
            st.divider()
            st.subheader("📉 歷史紀錄")
            
            # 使用 V20 經典設定 (無強制寬度，讓手機自動適應)
            col_config_def = {
                "Date": st.column_config.Column("日期", width="small"),
                "Time": st.column_config.Column("時間", width="small"),
                "Type": st.column_config.Column("類型", width="small"),
                "Content": st.column_config.Column("內容/數值", width="small"),
                "Note": st.column_config.Column("備註", width="small")
            }

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["全部", "食量統計", "體重", "排便", "用藥", "其他"])
            
            with tab1:
                st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=col_config_def)

            with tab2: # 食量
                df_food = df_cat[df_cat['Type'] == '餵食'].copy()
                if not df_food.empty:
                    df_food['Val'] = pd.to_numeric(df_food['Content'], errors='coerce').fillna(0)
                    stats = df_food.groupby('Date')['Val'].sum().reset_index().sort_values('Date', ascending=False)
                    stats['Grams'] = stats['Val'] * SPOON_TO_GRAM
                    stats.columns = ['日期', '總匙數', '總克數']
                    st.dataframe(stats, use_container_width=True, hide_index=True, column_config={
                        "日期": st.column_config.Column(width="small"),
                        "總匙數": st.column_config.Column(width="small"),
                        "總克數": st.column_config.Column(width="small")
                    })
                else:
                    st.write("尚無資料")

            with tab3: # 體重
                st.dataframe(df_display[df_display['Type']=='體重'], use_container_width=True, hide_index=True, column_config=col_config_def)
                if not df_display[df_display['Type']=='體重'].empty:
                    chart_df = df_display[df_display['Type']=='體重'].copy()
                    chart_df['WeightNum'] = pd.to_numeric(chart_df['Content'], errors='coerce')
                    st.line_chart(chart_df, x='Date', y='WeightNum')

            with tab4: # 排便
                st.dataframe(df_display[df_display['Type']=='排便'], use_container_width=True, hide_index=True, column_config=col_config_def)

            with tab5: # 用藥
                st.dataframe(df_display[df_display['Type']=='餵藥'], use_container_width=True, hide_index=True, column_config=col_config_def)

            with tab6: # 其他
                others_filter = df_display[df_display['Type'].isin(['其他', '備註'])]
                st.dataframe(others_filter, use_container_width=True, hide_index=True, column_config=col_config_def)