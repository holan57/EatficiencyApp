import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from google import genai
from google.genai import types
import json
from datetime import datetime
import traceback

# --- 頁面設定 ---
st.set_page_config(page_title="AI 生活費記帳助手", page_icon="💰", layout="centered")

st.title("💰 AI 生活費記帳助手")
st.markdown("透過 Gemini AI 自動辨識文字或收據，並記錄至 Google Sheets。")

# --- 讀取設定 ---
# 在 Streamlit Cloud 上，這些需設定於 Secrets 中
# 在本地測試時，請建立 .streamlit/secrets.toml
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    MONTHLY_BUDGET = st.secrets.get("MONTHLY_BUDGET", 15000)
except KeyError:
    st.error("請在 Streamlit Secrets 中設定 GOOGLE_API_KEY")
    st.stop()

MODEL_NAME = 'gemini-2.5-flash-lite'

# 初始化 Gemini
client = genai.Client(api_key=GOOGLE_API_KEY)

# --- Google Sheets 連線 ---
# 設定中必須包含 gsheets 相關資訊
conn = st.connection("gsheets", type=GSheetsConnection)

def get_expenses():
    """從 Google Sheets 讀取資料"""
    try:
        df = conn.read(ttl="0") # ttl="0" 確保讀取最新資料
        # 確保欄位正確
        if df.empty:
            return pd.DataFrame(columns=["date", "store", "amount", "category"])
        return df
    except Exception:
        # 如果工作表是空的或不存在，建立初始結構
        return pd.DataFrame(columns=["date", "store", "amount", "category"])

def save_to_sheets(new_data):
    """將新資料存入 Google Sheets"""
    df = get_expenses()
    # 建立新列的 DataFrame
    new_row = pd.DataFrame([new_data])
    # 合併
    updated_df = pd.concat([df, new_row], ignore_index=True)
    # 更新回 Google Sheets
    conn.update(data=updated_df)

def analyze_with_gemini(prompt_type, content):
    """使用 Gemini 分析文字或圖片"""
    today = datetime.now().strftime('%Y-%m-%d')
    base_prompt = f"""
    今天是 {today}。
    請分析這段內容，提取以下資訊：
    - date (日期，格式：YYYY-MM-DD，若內容沒提到則預設為 {today})
    - store (店家名稱或消費項目)
    - amount (總金額，整數)
    - category (消費類別，如：餐飲、交通、生活、其他)
    
    請嚴格以 JSON 格式回傳，不要有額外文字或 Markdown 標籤。
    範例：
    {{"date": "{today}", "store": "星巴克", "amount": 150, "category": "餐飲"}}
    """
    
    try:
        if prompt_type == 'image':
            contents = [base_prompt, types.Part.from_bytes(data=content, mime_type='image/jpeg')]
        else:
            contents = [f"{base_prompt}\n\n輸入內容：{content}"]

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
        # 轉為日期格式並過濾本月
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
    col1, col2 = st.columns(2)
    
    with col1:
        text_input = st.text_area("輸入消費內容", placeholder="例如：早餐 65 元")
        if st.button("文字辨識"):
            if text_input:
                with st.spinner("辨識中..."):
                    result = analyze_with_gemini('text', text_input)
                    if result:
                        st.session_state.result = result
            else:
                st.warning("請輸入內容")
                
    with col2:
        uploaded_file = st.file_uploader("上傳收據照片", type=['jpg', 'jpeg', 'png'])
        if uploaded_file:
            st.image(uploaded_file, caption="已上傳圖片", use_container_width=True)
            if st.button("圖片辨識"):
                with st.spinner("AI 辨識中..."):
                    result = analyze_with_gemini('image', uploaded_file.getvalue())
                    if result:
                        st.session_state.result = result

    # 顯示辨識結果並確認存檔
    if 'result' in st.session_state:
        st.divider()
        st.subheader("確認辨識結果")
        res = st.session_state.result
        
        c1, c2, c3, c4 = st.columns(4)
        date = c1.text_input("日期", value=res.get('date'))
        store = c2.text_input("項目", value=res.get('store'))
        amount = c3.number_input("金額", value=int(res.get('amount', 0)), step=1)
        category = c4.selectbox("類別", ["餐飲", "交通", "生活", "其他"], index=["餐飲", "交通", "生活", "其他"].index(res.get('category', '其他')) if res.get('category') in ["餐飲", "交通", "生活", "其他"] else 3)
        
        if st.button("✅ 確認存檔", type="primary"):
            final_data = {
                "date": date,
                "store": store,
                "amount": amount,
                "category": category
            }
            save_to_sheets(final_data)
            st.success("已存入 Google Sheets！")
            del st.session_state.result
            st.rerun()

with tab2:
    st.subheader("最近的消費紀錄")
    df_display = get_expenses()
    if not df_display.empty:
        # 反轉順序顯示最新的
        st.dataframe(df_display.iloc[::-1], use_container_width=True)
    else:
        st.info("尚無紀錄")
