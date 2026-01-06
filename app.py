import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import pytz
import os
from PIL import Image
import altair as alt

# --- 設定 ---
SHEET_URL = st.secrets["private_sheet_url"]
SPOON_TO_GRAM = 11  # 1匙 = 11克
HOME_IMAGE_PATH = "home_cat.jpg" 

# --- 連接 Google Sheets 函式 ---
@st.cache_resource
def init_connection():
    """建立與 Google Sheets 的連線"""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    return client

def get_data():
    """讀取資料"""
    client = init_connection()
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
    st.cache_resource.clear()
    st.error(f"資料庫連線失敗，請重新整理網頁。\n錯誤訊息: {e}")
    st.stop()

# --- 側邊欄 ---
with st.sidebar:
    st.header("🐾 選單")
    cat_list = df['Name'].unique().tolist() if not df.empty else []
    menu_options = ["🏠 主畫面"] + cat_list
    selected_option = st.selectbox("請選擇", menu_options)

if 'new_cat_name' in st.session_state:
    current_cat = st.session_state['new_cat_name']
    del st.session_state['new_cat_name']
    is_home = False
else:
    if selected_option == "🏠 主畫面":
        is_home = True
        current_cat = None
    else:
        is_home = False
        current_cat = selected_option

# ==========================================
# 🏠 顯示主畫面
# ==========================================
if is_home:
    # 🔥 版本號更新 v42
    st.title("🐈 貓咪生活日記 (v42)")
    st.write("### Welcome Home! 🐾")
    
    if os.path.exists(HOME_IMAGE_PATH):
        try:
            image = Image.open(HOME_IMAGE_PATH)
            rotated_image = image.rotate(-90, expand=True)
            st.image(rotated_image, use_container_width=True, caption="我們這一家 ❤️")
        except Exception as e:
            st.error(f"圖片讀取錯誤: {e}")
    else:
        st.warning(f"找不到照片檔案 `{HOME_IMAGE_PATH}`，請確認已上傳至 GitHub。")

    with st.sidebar:
        st.divider()
        with st.expander("➕ 新增其他貓咪"):
            new_cat = st.text_input("輸入新名字")
            if st.button("確認新增"):
                if new_cat and new_cat not in cat_list:
                    st.session_state['new_cat_name'] = new_cat
                    st.success(f"準備新增 {new_cat}，請去右邊輸入第一筆紀錄！")
                    time.sleep(1)
                    st.rerun()

        if not df.empty:
            st.divider()
            st.subheader("💾 資料備份")
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            tw_tz_backup = pytz.timezone('Asia/Taipei')
            now_str = datetime.now(tw_tz_backup).strftime("%Y%m%d")
            st.download_button(
                label="📥 下載紀錄",
                data=csv_data,
                file_name=f"貓咪日記_{now_str}.csv",
                mime="text/csv"
            )

# ==========================================
# 🐾 顯示貓咪紀錄介面
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

    # 輸入選項：其他 -> 注意
    type_options = ["餵食", "餵藥", "體重", "排便", "其他", "注意"]
    record_type = st.radio("類型", type_options, horizontal=True, label_visibility="collapsed") 

    help_text = ""
    if record_type == "餵食": help_text = "輸入湯匙數 (如 0.5)"
    elif record_type == "體重": help_text = "輸入公斤數 (如 5.2)"
    elif record_type == "餵藥": help_text = "輸入藥名 (如 抗生素)"
    elif record_type == "其他": help_text = "輸入雜項 (如 剪指甲、喝水、洗澡)"
    elif record_type == "注意": help_text = "輸入症狀 (如 嘔吐、精神差、拉血)"

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
        df_cat = df[df['Name'] == current_cat].copy()
        
        if not df_cat.empty:
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
            notices_list = []
            
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
                elif t == "注意": notices_list.append(f"{row['Time']} {c}{note_suffix}")

            c1, c2 = st.columns(2)
            with c1:
                # 左欄：食量、用藥、其他(互換後)
                food_msg = "(無)"
                if food_total > 0:
                    grams = round(food_total * SPOON_TO_GRAM, 2)
                    food_msg = f"**{round(food_total, 3)} 匙** ({grams}g)"
                if food_others: food_msg += f" + {','.join(food_others)}"
                st.info(f"🍖 食量: {food_msg}")
                st.warning(f"💊 用藥: {', '.join(meds) if meds else '(無)'}")
                
                # 🔥【修改】其他移來這裡
                others_msg = ", ".join(others_list) if others_list else "(無)"
                st.info(f"📝 其他: {others_msg}")

            with c2:
                # 右欄：排便、體重、注意(互換後)
                st.success(f"💩 排便: {', '.join(toilets) if toilets else '(無)'}")
                weight_msg = weights[0] if weights else "(無)"
                st.error(f"⚖️ 體重: {weight_msg}")
                
                # 🔥【修改】注意移來這裡
                notices_msg = ", ".join(notices_list) if notices_list else "(無)"
                st.error(f"⚠️ 注意: {notices_msg}")

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
            
            col_config_default = {
                "Date": st.column_config.Column("日期", width="small"),
                "Time": st.column_config.Column("時間", width="small"),
                "Type": st.column_config.Column("類型", width="small"),
                "Content": st.column_config.Column("內容/數值", width="small"),
                "Note": st.column_config.Column("備註", width="small")
            }

            col_config_no_type = {
                "Date": st.column_config.Column("日期", width="small"),
                "Time": st.column_config.Column("時間", width="small"),
                "Type": None,
                "Content": st.column_config.Column("內容/數值", width="small"),
                "Note": st.column_config.Column("備註", width="small")
            }

            # 順序：食量統計 -> 其他 -> 注意 -> 體重
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
                ["全部", "餵食紀錄", "排便", "用藥", "食量統計", "其他", "注意", "體重"]
            )
            
            with tab1: # 全部
                st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=col_config_default)

            with tab2: # 餵食紀錄
                st.dataframe(df_display[df_display['Type']=='餵食'], use_container_width=True, hide_index=True, column_config=col_config_no_type)

            with tab3: # 排便
                st.dataframe(df_display[df_display['Type']=='排便'], use_container_width=True, hide_index=True, column_config=col_config_no_type)

            with tab4: # 用藥
                st.dataframe(df_display[df_display['Type']=='餵藥'], use_container_width=True, hide_index=True, column_config=col_config_no_type)

            with tab5: # 食量統計
                df_food = df_cat[df_cat['Type'] == '餵食'].copy()
                if not df_food.empty:
                    df_food['Val'] = pd.to_numeric(df_food['Content'], errors='coerce').fillna(0)
                    stats = df_food.groupby('Date')['Val'].sum().reset_index().sort_values('Date', ascending=False)
                    stats['Grams'] = stats['Val'] * SPOON_TO_GRAM
                    stats.columns = ['日期', '總匙數', '總克數']
                    
                    st.dataframe(
                        stats, 
                        use_container_width=True, 
                        hide_index=True, 
                        height=400,
                        column_config={
                            "日期": st.column_config.Column(width="small"),
                            "總匙數": st.column_config.Column(width="small"),
                            "總克數": st.column_config.Column(width="small")
                        }
                    )
                    st.write("---")
                    st.caption("📈 近 20 天食量趨勢")
                    chart_data = stats.head(20).sort_values('日期', ascending=True)
                    st.bar_chart(chart_data, x="日期", y="總克數", color="#FF6347") 
                else:
                    st.write("尚無資料")

            with tab6: # 其他
                others_filter = df_display[df_display['Type'].isin(['其他', '備註'])]
                st.dataframe(others_filter, use_container_width=True, hide_index=True, column_config=col_config_no_type)

            with tab7: # 注意 (新增)
                st.dataframe(df_display[df_display['Type']=='注意'], use_container_width=True, hide_index=True, column_config=col_config_no_type)

            with tab8: # 體重
                st.dataframe(df_display[df_display['Type']=='體重'], use_container_width=True, hide_index=True, column_config=col_config_default)
                if not df_display[df_display['Type']=='體重'].empty:
                    chart_df = df_display[df_display['Type']=='體重'].copy()
                    chart_df['WeightNum'] = pd.to_numeric(chart_df['Content'], errors='coerce')
                    
                    st.write("---")
                    st.caption("📈 體重趨勢圖 (5kg - 12kg)")
                    
                    chart = alt.Chart(chart_df).mark_line(point=True, color='#2E86C1').encode(
                        x=alt.X('Date', title='日期'),
                        y=alt.Y('WeightNum', 
                                title='體重 (kg)', 
                                scale=alt.Scale(domain=[5, 12], zero=False), 
                                axis=alt.Axis(tickMinStep=0.5)
                        ),
                        tooltip=['Date', 'WeightNum']
                    ).interactive()
                    
                    st.altair_chart(chart, use_container_width=True)
        
        else:
            st.info("這位主子還沒有紀錄喔，趕快輸入第一筆吧！")

    else:
        st.write("目前資料庫是空的，請新增第一筆資料！")