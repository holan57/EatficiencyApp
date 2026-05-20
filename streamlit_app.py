import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from google import genai
from google.genai import types
import json
from datetime import datetime
from streamlit_javascript import st_javascript
import traceback

# --- 頁面設定 ---
st.set_page_config(page_title="Eatficiency-飲食記錄家", page_icon="💰", layout="centered")

# 檢查是否為行動裝置
ua_string = st_javascript("navigator.userAgent")
is_mobile = False 
if ua_string:
    ua_lower = ua_string.lower()
    if "mobi" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        is_mobile = True

st.markdown("### 💰 Eatficiency-飲食記錄家")
st.markdown("透過 Gemini AI 自動辨識文字或收據，並記錄至 Google Sheets。")

# 使用者名字輸入
user_name = st.sidebar.text_input("使用者名稱", key="user_name")

# --- 讀取設定 ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    MONTHLY_BUDGET = st.secrets.get("MONTHLY_BUDGET", 15000)
except KeyError:
    st.error("請在 Streamlit Secrets 中設定 GOOGLE_API_KEY")
    st.stop()

MODEL_NAME = 'gemini-2.5-flash-lite'

# 初始化 Gemini
client = genai.Client(api_key=GOOGLE_API_KEY)

@st.dialog("健康與理財建議")
def show_advice_modal(advice_text):
    st.write(advice_text)
    if st.button("關閉"):
        st.rerun()

# --- Google Sheets 連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_expenses():
    """從 Google Sheets 讀取資料"""
    try:
        df = conn.read(ttl="0")
        if df.empty:
            return pd.DataFrame(columns=["user_name", "date", "foodname", "amount", "category", "calories", "health_score", "advice"])
        return df
    except Exception:
        return pd.DataFrame(columns=["user_name", "date", "foodname", "amount", "category", "calories", "health_score", "advice"])

def save_to_sheets(new_data):
    """將新資料存入 Google Sheets"""
    df = get_expenses()
    new_row = pd.DataFrame([new_data])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)

def analyze_with_gemini(text_content=None, image_content=None):
    """使用 Gemini 分析文字與圖片"""
    today = datetime.now().strftime('%Y-%m-%d')
    base_prompt = f"""
    今天是 {today}。
    你是一個精準的飲食記帳與健康理財助手。
    請分析使用者提供的【圖片】或【文字描述】：
    1. 辨識或擷取【食物名稱】。
    2. 估算【熱量】與【金額】
    3. 給予【健康度評分】與【建議】。
    4. 如上述第一次無法辨識，讓user手動填入資訊
    請以 JSON 回傳：date, foodname, amount, category, calories, health_score, advice。
    """
    
    try:
        contents = [base_prompt]
        if image_content:
            contents.append(types.Part.from_bytes(data=image_content, mime_type='image/jpeg'))
        if text_content:
            contents.append(f"\n\n額外文字資訊：{text_content}")

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents
        )
        
        text = response.text.strip()
        clean_text = text.replace('```json', '').replace('```', '')
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"AI 辨識失敗: {e}")
        return None

# --- 側邊欄：預算與統計 ---
with st.sidebar:
    st.header("📊 預算統計")
    df_all = get_expenses()
    
    current_month = datetime.now().strftime('%Y-%m')
    if not df_all.empty and 'date' in df_all.columns:
        df_all['date'] = pd.to_datetime(df_all['date'])
        month_mask = df_all['date'].dt.strftime('%Y-%m') == current_month
        df_month = df_all[month_mask]
        
        total_spent = df_month['amount'].astype(int).sum()
    else:
        total_spent = 0
        
    remaining = MONTHLY_BUDGET - total_spent
    
    st.metric("本月已花費", f"${total_spent:,}")
    st.metric("剩餘預算", f"${remaining:,}", delta_color="normal")
    
    progress = min(total_spent / MONTHLY_BUDGET, 1.0) if MONTHLY_BUDGET > 0 else 0
    st.progress(progress, text=f"預算使用率: {progress*100:.1f}%")

# --- 主介面：新增消費 ---
tab1, tab2 = st.tabs(["📝 文字/圖片辨識", "📋 歷史紀錄"])

with tab1:
    # 建立統一的輸入區域
    with st.container(border=True):
        st.markdown("### 📝 新增消費")
        text_input = st.text_area("描述消費內容", placeholder="例如：早餐 65 元，或是上傳收據照片...", label_visibility="collapsed")
        
        if is_mobile:
            uploaded_file = st.camera_input("📷 拍照", label_visibility="collapsed")
        else:
            uploaded_file = st.file_uploader("📷 上傳收據 (選填)", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed")

        if uploaded_file:
            st.image(uploaded_file, caption="已上傳圖片", width=200)

        recognize_btn = st.button("🔍 開始辨識", type="primary", use_container_width=True)

    if recognize_btn:
        if text_input or uploaded_file:
            with st.spinner("AI 辨識中..."):
                img_bytes = uploaded_file.getvalue() if uploaded_file else None
                result = analyze_with_gemini(text_content=text_input, image_content=img_bytes)
                if result:
                    st.session_state.result = result
                else:
                    st.warning("辨識結果為空，請稍後再試。")
        else:
            st.warning("請輸入文字內容或上傳收據照片")

    # 顯示辨識結果並確認存檔
    if 'result' in st.session_state:
        st.divider()
        st.subheader("確認辨識結果")
        res = st.session_state.result
        
        c1, c2, c3, c4 = st.columns(4)
        date = c1.text_input("日期", value=res.get('date'))
        foodname = c2.text_input("品名", value=res.get('foodname'))
        amount_val = res.get('amount')
        if amount_val is None:
            amount_val = 0
        try:
            amount = c3.number_input("金額", value=int(amount_val), step=1)
        except (ValueError, TypeError):
            amount = c3.number_input("金額", value=0, step=1)
        category = c4.selectbox("類別", ["中式", "西式", "日式", "其他"], index=["中式", "西式", "日式", "其他"].index(res.get('category', '其他')) if res.get('category') in ["餐飲", "交通", "生活", "其他"] else 3)
        
        col_action1, col_action2 = st.columns(2)
        with col_action1:
            if st.button("查看建議", use_container_width=True):
                show_advice_modal(res.get('advice', '無建議'))
        with col_action2:
            if st.button("✅ 確認存檔", type="primary", use_container_width=True):
                final_data = {
                    "user_name": user_name,
                    "date": date,
                    "foodname": foodname, 
                    "amount": amount,
                    "category": category,
                    "calories": res.get('calories', 0),
                    "health_score": res.get('health_score', 0),
                    "advice": res.get('advice', '')
                }
                save_to_sheets(final_data)
                st.success("已存入 Google Sheets！")
                del st.session_state.result
                st.rerun()

with tab2:
    st.subheader("最近的消費紀錄")
    df_display = get_expenses()
    if not df_all.empty:
        # 反轉順序顯示最新的
        st.dataframe(df_display.iloc[::-1], use_container_width=True)
    else:
        st.info("尚無紀錄")
