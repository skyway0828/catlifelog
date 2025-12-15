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
SPOON_TO_GRAM = 11
HOME_IMAGE_PATH = "home_cat.jpg"

# --- 1. 連接 Google Sheets (只做一次) ---
@st.cache_resource
def init_connection():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    return client

# --- 2. 讀取生活紀錄 (啟動時只讀這個) ---
@st.cache_data(ttl=5)
def get_life_data():
    client = init_connection()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    return sheet, data

# --- 3. 讀取病歷資料 (點擊分頁才讀這個) ---
@st.cache_data(ttl=5)
def get_medical_data():
    client = init_connection()
    spreadsheet = client.open_by_url(SHEET_URL)
    try:
        sheet_med = spreadsheet.worksheet("Medical_Logs")
        data_med = sheet_med.get_all_records()
    except:
        sheet_med = None
        data_med = []
    return sheet_med, data_med

# --- 介面開始 ---
st.set_page_config(page_title="貓咪生活日記", page_icon="🐾", layout="wide")

# 先讀取主要資料 (生活紀錄)，讓選單可以先跑出來
try:
    sheet, data = get_life_data()
    df = pd.DataFrame(data)
except Exception as e:
    st.cache_data.clear()
    st.error("連線忙碌中，請重新整理。")
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
# 🏠 主畫面
# ==========================================
if is_home:
    st.title("🐈 貓咪生活日記")
    
    if os.path.exists(HOME_IMAGE_PATH):
        try:
            image = Image.open(HOME_IMAGE_PATH)
            rotated_image = image.rotate(-90, expand=True)
            st.image(rotated_image, use_container_width=True, caption="我們這一家 ❤️")
        except:
            st.warning("照片讀取錯誤")
    
    with st.sidebar:
        st.divider()
        with st.expander("➕ 新增其他貓咪"):
            new_cat = st.text_input("輸入新名字")
            if st.button("確認新增"):
                if new_cat and new_cat not in cat_list:
                    st.session_state['new_cat_name'] = new_cat
                    st.success(f"準備新增 {new_cat}")
                    time.sleep(1)
                    st.rerun()
        
        # 備份功能 (只有在需要備份時才去抓病歷資料，加快主畫面顯示)
        if not df.empty:
            st.divider()
            st.subheader("💾 資料備份")
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            tw_tz_backup = pytz.timezone('Asia/Taipei')
            now_str = datetime.now(tw_tz_backup).strftime("%Y%m%d")
            
            # 生活紀錄備份
            st.download_button(label="📥 下載生活紀錄", data=csv_data, file_name=f"貓咪日記_{now_str}.csv", mime="text/csv")
            
            # 病歷備份 (按鈕按下去前不讀取，或是做成另一個按鈕)
            # 為了效能，這裡我們做個簡單的檢查
            if st.checkbox("也顯示病歷備份按鈕"):
                _, data_med_backup = get_medical_data()
                df_med_backup = pd.DataFrame(data_med_backup)
                if not df_med_backup.empty:
                    csv_med = df_med_backup.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(label="📥 下載病歷資料", data=csv_med, file_name=f"貓咪病歷_{now_str}.csv", mime="text/csv")

# ==========================================
# 🐾 貓咪個人頁面
# ==========================================
else:
    st.subheader(f"🐾 {current_cat}")
    
    main_tab1, main_tab2 = st.tabs(["📝 生活紀錄", "🏥 病歷/健檢"])

    # ----------------------------------------------------
    # TAB 1: 生活紀錄 (使用已讀取的 data)
    # ----------------------------------------------------
    with main_tab1:
        tw_tz = pytz.timezone('Asia/Taipei')
        now_tw = datetime.now(tw_tz)

        col_date, col_hour, col_min = st.columns([2, 1, 1])
        with col_date: date_input = st.date_input("日期", now_tw, key="life_date")
        with col_hour: 
            hours = [f"{i:02d}" for i in range(24)]
            hour_val = st.selectbox("時", hours, index=now_tw.hour, key="life_hour")
        with col_min: 
            mins = [f"{i:02d}" for i in range(60)]
            min_val = st.selectbox("分", mins, index=now_tw.minute, key="life_min")
        time_str = f"{hour_val}:{min_val}"

        type_options = ["餵食", "餵藥", "體重", "排便", "其他"]
        record_type = st.radio("類型", type_options, horizontal=True, label_visibility="collapsed", key="life_type") 

        help_text = ""
        if record_type == "餵食": help_text = "輸入湯匙數 (如 0.5)"
        elif record_type == "體重": help_text = "輸入公斤數 (如 5.2)"
        elif record_type == "餵藥": help_text = "輸入藥名"
        elif record_type == "其他": help_text = "輸入標題"

        content_val = st.text_input("內容 / 數值", placeholder=help_text, key="life_content")
        note_val = st.text_input("備註說明 (選填)", key="life_note")

        if st.button("💾 儲存生活紀錄", type="primary", use_container_width=True, key="save_life"):
            if not content_val:
                st.warning("請輸入內容！")
            else:
                final_content = content_val.replace("。", ".").replace("．", ".")
                row_data = [current_cat, date_input.strftime("%Y-%m-%d"), time_str, record_type, final_content, note_val]
                with st.spinner('寫入中...'):
                    sheet.append_row(row_data)
                    st.cache_data.clear() # 清除快取，下次讀取最新
                    st.success("✅ 成功！")
                    time.sleep(1)
                    st.rerun()

        if not df.empty:
            df_cat = df[df['Name'] == current_cat].copy()
            if not df_cat.empty:
                try:
                    df_cat['DateTime'] = pd.to_datetime(df_cat['Date'] + ' ' + df_cat['Time'])
                    df_cat = df_cat.sort_values(by='DateTime', ascending=False)
                except:
                    df_cat = df_cat.sort_values(by=['Date', 'Time'], ascending=[False, False])
                
                df_display = df_cat[['Date', 'Time', 'Type', 'Content', 'Note']].reset_index(drop=True)

                st.divider()
                target_date_str = date_input.strftime("%Y-%m-%d")
                st.caption(f"📊 單日回顧: {target_date_str}")
                df_today = df_cat[df_cat['Date'] == target_date_str]
                
                food_total = 0.0
                food_others = []
                meds = []
                toilets = []
                weights = []
                others_list = []
                for _, row in df_today.iterrows():
                    t, c = row['Type'], str(row['Content'])
                    ns = f" ({row['Note']})" if row['Note'] else ""
                    if t == "餵食":
                        try: food_total += float(c)
                        except: food_others.append(c)
                    elif t == "餵藥": meds.append(f"{row['Time']} {c}{ns}")
                    elif t == "排便": toilets.append(f"{row['Time']} {c}{ns}")
                    elif t == "體重": weights.append(f"{c} kg")
                    elif t == "其他" or t == "備註": others_list.append(f"{row['Time']} {c}{ns}")

                c1, c2 = st.columns(2)
                with c1:
                    food_msg = f"**{round(food_total, 3)} 匙** ({round(food_total*SPOON_TO_GRAM, 2)}g)" if food_total > 0 else "(無)"
                    if food_others: food_msg += f" + {','.join(food_others)}"
                    st.info(f"🍖 食量: {food_msg}")
                    st.warning(f"💊 用藥: {', '.join(meds) if meds else '(無)'}")
                with c2:
                    st.success(f"💩 排便: {', '.join(toilets) if toilets else '(無)'}")
                    st.error(f"⚖️ 體重: {weights[0] if weights else '(無)'}")
                    st.info(f"📝 其他: {', '.join(others_list) if others_list else '(無)'}")

                st.divider()
                with st.expander("🛠️ 管理生活紀錄 (修改/刪除)", expanded=False):
                    edit_limit = st.number_input("欲載入最近幾筆紀錄？", min_value=10, max_value=1000, value=20, step=10, key="life_limit")
                    recent_records = df_cat.head(edit_limit).copy()
                    recent_records['Label'] = recent_records.apply(lambda x: f"{x['Date']} {x['Time']} | {x['Type']} | {x['Content']}", axis=1)
                    selected_label = st.selectbox("選擇要操作的項目:", recent_records['Label'].tolist(), key="life_select")
                    
                    if selected_label:
                        target_row = recent_records[recent_records['Label'] == selected_label].iloc[0]
                        ce1, ce2 = st.columns(2)
                        with ce1: new_content_edit = st.text_input("修改內容/數值", value=target_row['Content'], key="life_edit_c")
                        with ce2: new_note_edit = st.text_input("修改備註說明", value=target_row['Note'], key="life_edit_n")
                        
                        cb1, cb2 = st.columns([1, 1])
                        with cb1:
                            if st.button("🗑️ 刪除", type="primary", key="life_del"):
                                with st.spinner("刪除中..."):
                                    try:
                                        row_to_delete = None
                                        for i, record in enumerate(data):
                                            if (record['Name'] == current_cat and record['Date'] == target_row['Date'] and str(record['Time']) == str(target_row['Time']) and record['Type'] == target_row['Type'] and str(record['Content']) == str(target_row['Content'])):
                                                row_to_delete = i + 2
                                                break
                                        if row_to_delete:
                                            sheet.delete_rows(row_to_delete)
                                            st.cache_data.clear()
                                            st.success("已刪除！")
                                            time.sleep(1)
                                            st.rerun()
                                    except: st.error("刪除失敗")
                        with cb2:
                            if st.button("✏️ 修改", key="life_upd"):
                                with st.spinner("更新中..."):
                                    try:
                                        row_to_update = None
                                        for i, record in enumerate(data):
                                            if (record['Name'] == current_cat and record['Date'] == target_row['Date'] and str(record['Time']) == str(target_row['Time']) and record['Type'] == target_row['Type'] and str(record['Content']) == str(target_row['Content'])):
                                                row_to_update = i + 2
                                                break
                                        if row_to_update:
                                            sheet.update_cell(row_to_update, 5, new_content_edit)
                                            sheet.update_cell(row_to_update, 6, new_note_edit)
                                            st.cache_data.clear()
                                            st.success("更新成功！")
                                            time.sleep(1)
                                            st.rerun()
                                    except: st.error("更新失敗")

                st.divider()
                st.caption("📉 歷史紀錄")
                col_cfg_def = {"Date": st.column_config.Column("日期", width="small"), "Time": st.column_config.Column("時間", width="small"), "Type": st.column_config.Column("類型", width="small"), "Content": st.column_config.Column("內容/數值", width="small"), "Note": st.column_config.Column("備註", width="small")}
                col_cfg_no_type = {"Date": st.column_config.Column("日期", width="small"), "Time": st.column_config.Column("時間", width="small"), "Type": None, "Content": st.column_config.Column("內容/數值", width="small"), "Note": st.column_config.Column("備註", width="small")}

                t1, t2, t3, t4, t5, t6, t7 = st.tabs(["全部", "餵食紀錄", "排便", "用藥", "其他", "食量統計", "體重"])
                
                with t1: st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=col_cfg_def)
                with t2: st.dataframe(df_display[df_display['Type']=='餵食'], use_container_width=True, hide_index=True, column_config=col_cfg_no_type)
                with t3: st.dataframe(df_display[df_display['Type']=='排便'], use_container_width=True, hide_index=True, column_config=col_cfg_no_type)
                with t4: st.dataframe(df_display[df_display['Type']=='餵藥'], use_container_width=True, hide_index=True, column_config=col_cfg_no_type)
                with t5: 
                    others_filter = df_display[df_display['Type'].isin(['其他', '備註'])]
                    st.dataframe(others_filter, use_container_width=True, hide_index=True, column_config=col_cfg_no_type)
                with t6: # 食量
                    df_food = df_cat[df_cat['Type'] == '餵食'].copy()
                    if not df_food.empty:
                        df_food['Val'] = pd.to_numeric(df_food['Content'], errors='coerce').fillna(0)
                        stats = df_food.groupby('Date')['Val'].sum().reset_index().sort_values('Date', ascending=False)
                        stats['Grams'] = stats['Val'] * SPOON_TO_GRAM
                        stats.columns = ['日期', '總匙數', '總克數']
                        st.dataframe(stats, use_container_width=True, hide_index=True, height=400, column_config={"日期": st.column_config.Column(width="small"), "總匙數": st.column_config.Column(width="small"), "總克數": st.column_config.Column(width="small")})
                        chart_data = stats.head(20).sort_values('日期', ascending=True)
                        st.bar_chart(chart_data, x="日期", y="總克數", color="#FF6347")
                    else: st.write("尚無資料")
                with t7: # 體重
                    st.dataframe(df_display[df_display['Type']=='體重'], use_container_width=True, hide_index=True, column_config=col_cfg_def)
                    if not df_display[df_display['Type']=='體重'].empty:
                        chart_df = df_display[df_display['Type']=='體重'].copy()
                        chart_df['WeightNum'] = pd.to_numeric(chart_df['Content'], errors='coerce')
                        chart = alt.Chart(chart_df).mark_line(point=True, color='#2E86C1').encode(x=alt.X('Date', title='日期'), y=alt.Y('WeightNum', title='體重 (kg)', scale=alt.Scale(domain=[5, 12], zero=False), axis=alt.Axis(tickMinStep=0.5)), tooltip=['Date', 'WeightNum']).interactive()
                        st.altair_chart(chart, use_container_width=True)
            else:
                st.info("尚無紀錄")

    # ----------------------------------------------------
    # TAB 2: 病歷/健檢 (點擊時才讀取資料)
    # ----------------------------------------------------
    with main_tab2:
        # 🔥【關鍵】這裡才呼叫讀取病歷，實現 Lazy Loading
        sheet_med, data_med = get_medical_data()
        df_med = pd.DataFrame(data_med)

        if sheet_med is None:
            st.error("⚠️ 尚未建立 `Medical_Logs` 分頁")
        else:
            st.subheader("🏥 新增病歷資料")
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                med_date = st.date_input("就診日期", datetime.now(), key="med_date")
                med_cat = st.selectbox("類別", ["看診", "年度健檢", "疫苗", "回診", "手術"], key="med_cat")
                med_weight = st.text_input("當下體重 (kg)", key="med_weight")
            with m_col2:
                med_hospital = st.text_input("醫院 / 醫師", key="med_hospital")
                med_link = st.text_input("📁 檔案連結", placeholder="Google Drive/Dropbox", key="med_link")
            
            med_detail = st.text_area("📋 病歷內容 / 醫囑", height=150, placeholder="可貼上長篇文字...", key="med_detail")

            if st.button("💾 儲存病歷", type="primary", use_container_width=True, key="save_med"):
                if not med_detail:
                    st.warning("請填寫病歷內容")
                else:
                    med_row = [current_cat, med_date.strftime("%Y-%m-%d"), med_cat, med_weight, med_hospital, med_detail, med_link]
                    with st.spinner('儲存中...'):
                        sheet_med.append_row(med_row)
                        # 🔥 清除病歷快取
                        st.cache_data.clear()
                        st.success("病歷已歸檔！")
                        time.sleep(1)
                        st.rerun()

            st.divider()
            if not df_med.empty:
                my_med_records = df_med[df_med['Name'] == current_cat].copy()
                if not my_med_records.empty:
                    my_med_records = my_med_records.sort_values(by='Date', ascending=False)
                    
                    with st.expander("🛠️ 修改或刪除病歷", expanded=False):
                        med_options = my_med_records.apply(lambda x: f"{x['Date']} | {x['Category']} | {x['Hospital']}", axis=1).tolist()
                        sel_med = st.selectbox("選擇要操作的病歷:", med_options, key="med_sel")
                        if sel_med:
                            target_med = my_med_records[my_med_records.apply(lambda x: f"{x['Date']} | {x['Category']} | {x['Hospital']}", axis=1) == sel_med].iloc[0]
                            me1, me2 = st.columns(2)
                            with me1:
                                new_med_date = st.text_input("日期", value=target_med['Date'], key="me_date")
                                new_med_cat = st.text_input("類別", value=target_med['Category'], key="me_cat")
                                new_med_w = st.text_input("體重", value=target_med['Weight'], key="me_w")
                            with me2:
                                new_med_hos = st.text_input("醫院", value=target_med['Hospital'], key="me_hos")
                                new_med_link = st.text_input("連結", value=target_med['Link'], key="me_link")
                            new_med_det = st.text_area("詳細內容", value=target_med['Details'], height=100, key="me_det")
                            mb1, mb2 = st.columns([1, 1])
                            with mb1:
                                if st.button("🗑️ 刪除", type="primary", key="med_del"):
                                    with st.spinner("刪除中..."):
                                        try:
                                            row_to_del = None
                                            for i, record in enumerate(data_med):
                                                if (record['Name'] == current_cat and record['Date'] == target_med['Date'] and record['Category'] == target_med['Category'] and str(record['Details']) == str(target_med['Details'])):
                                                    row_to_del = i + 2
                                                    break
                                            if row_to_del:
                                                sheet_med.delete_rows(row_to_del)
                                                st.cache_data.clear()
                                                st.success("已刪除！")
                                                time.sleep(1)
                                                st.rerun()
                                        except: st.error("刪除失敗")
                            with mb2:
                                if st.button("✏️ 更新", key="med_upd"):
                                    with st.spinner("更新中..."):
                                        try:
                                            row_to_upd = None
                                            for i, record in enumerate(data_med):
                                                if (record['Name'] == current_cat and record['Date'] == target_med['Date'] and record['Category'] == target_med['Category'] and str(record['Details']) == str(target_med['Details'])):
                                                    row_to_upd = i + 2
                                                    break
                                            if row_to_upd:
                                                sheet_med.update_cell(row_to_upd, 2, new_med_date)
                                                sheet_med.update_cell(row_to_upd, 3, new_med_cat)
                                                sheet_med.update_cell(row_to_upd, 4, new_med_w)
                                                sheet_med.update_cell(row_to_upd, 5, new_med_hos)
                                                sheet_med.update_cell(row_to_upd, 6, new_med_det)
                                                sheet_med.update_cell(row_to_upd, 7, new_med_link)
                                                st.cache_data.clear()
                                                st.success("更新成功！")
                                                time.sleep(1)
                                                st.rerun()
                                        except Exception as e: st.error(f"更新失敗: {e}")

                    st.divider()
                    st.subheader("🗂️ 病歷調閱")
                    for i, row in my_med_records.iterrows():
                        title_text = f"📅 {row['Date']} | {row['Category']} | 🏥 {row['Hospital']}"
                        with st.expander(title_text, expanded=False):
                            st.markdown(f"**體重:** {row['Weight']} kg")
                            st.markdown("---")
                            st.markdown(f"**詳細內容:**\n\n{row['Details']}")
                            if row['Link']:
                                st.markdown("---")
                                st.link_button("📂 開啟影像/檔案連結", row['Link'])
                else:
                    st.info("目前沒有病歷資料。")
            else:
                st.info("資料庫目前是空的。")