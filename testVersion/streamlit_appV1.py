import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from google import genai
from google.genai import types
import json
from datetime import datetime
from streamlit_javascript import st_javascript

# --- 頁面設定 ---
st.set_page_config(page_title="Eatficiency-飲食記錄家", page_icon="💰", layout="wide")

# 模擬行動裝置偵測
ua_string = st_javascript("navigator.userAgent")
is_mobile = ua_string and ("mobi" in ua_string.lower() or "android" in ua_string.lower() or "iphone" in ua_string.lower())

# --- 讀取設定 ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    MONTHLY_BUDGET = st.secrets.get("MONTHLY_BUDGET", 15000)
except KeyError:
    st.error("請在 Streamlit Secrets 中設定 GOOGLE_API_KEY")
    st.stop()

client = genai.Client(api_key=GOOGLE_API_KEY)
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 輔助函式 ---
def get_expenses():
    try:
        df = conn.read(ttl="0")
        if df.empty:
            return pd.DataFrame(columns=["user_name", "date", "foodname", "amount", "category", "calories", "health_score", "advice"])
        return df
    except:
        return pd.DataFrame(columns=["user_name", "date", "foodname", "amount", "category", "calories", "health_score", "advice"])

def save_to_sheets(new_data):
    df = get_expenses()
    new_row = pd.DataFrame([new_data])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)

def analyze_with_gemini(text_content=None, image_content=None):
    today = datetime.now().strftime('%Y-%m-%d')
    base_prompt = f"今天是 {today}。你是一個精準的飲食記帳與健康理財助手。請分析使用者提供的資料，辨識【食物名稱】、【花費金額】、【熱量】、【類別】、【健康度評分】、【建議】。請務必只回傳純 JSON，不要包含 Markdown 或其他解釋文字。格式：{{'date': '{today}', 'foodname': '...', 'amount': 0, 'category': '...', 'calories': 0, 'health_score': 0, 'advice': '...'}}"
    
    try:
        contents = [base_prompt]
        if image_content: 
            contents.append(types.Part.from_bytes(data=image_content, mime_type='image/png')) # 改用 png 試試，或嘗試自動偵測
        if text_content: contents.append(f"\n\n額外資訊：{text_content}")
        
        response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=contents)
        raw_text = response.text.strip()
        
        # 嘗試提取 JSON 部分
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_text = raw_text[start_idx:end_idx+1]
            return json.loads(json_text)
        else:
            return json.loads(raw_text)
            
    except Exception as e:
        print(f"DEBUG: AI Error: {e}") # 添加日誌
        st.error(f"AI 辨識失敗: {e}")
        return None

# --- 初始化 Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "你好！請告訴我你吃了什麼，或是上傳收據，我幫你記錄！"}]

# --- 側邊欄：導航與統計 ---
with st.sidebar:
    st.markdown("### 💰 Eatficiency-飲食記錄家")
    user_name = st.text_input("使用者名稱", key="user_name")
    
    st.divider()
    
    # 預算顯示 (Sidebar)
    st.markdown("📊 **本月預算**")
    df_all = get_expenses()
    total_spent = 0
    if not df_all.empty and 'date' in df_all.columns:
        df_all['date'] = pd.to_datetime(df_all['date'])
        total_spent = df_all[df_all['date'].dt.strftime('%Y-%m') == datetime.now().strftime('%Y-%m')]['amount'].astype(int).sum()
    
    st.markdown(f"`${int(total_spent):,} / ${int(MONTHLY_BUDGET):,}`")
    st.progress(min(total_spent / MONTHLY_BUDGET, 1.0))
    
    st.divider()
    page = st.radio("功能導航", ["📝 聊天記錄", "📋 歷史清單"])



# --- 主介面：聊天區域 ---
if page == "📝 聊天記錄":
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message:
                st.image(message["image"], caption="已上傳的圖片", width=200)
            # 如果是辨識結果，顯示編輯表單 (需在存檔時處理)
            if "data" in message:
                res = message["data"]
                with st.form(key=f"form_{message.get('id')}"):
                    c1, c2 = st.columns(2)
                    date = c1.text_input("日期", value=res.get('date'))
                    foodname = c2.text_input("品名", value=res.get('foodname'))
                    c3, c4 = st.columns(2)
                    amount = c3.number_input("金額", value=int(res.get('amount', 0)), step=1)
                    category = c4.selectbox("類別", ["中式", "西式", "日式", "其他"], index=["中式", "西式", "日式", "其他"].index(res.get('category', '其他')) if res.get('category') in ["中式", "西式", "日式", "其他"] else 3)
                    
                    if st.form_submit_button("✅ 確認存檔"):
                        save_to_sheets({**res, "date": date, "foodname": foodname, "amount": amount, "category": category, "user_name": user_name})
                        st.success("記錄成功！")
                        st.session_state.messages.append({"role": "assistant", "content": f"💡 健康/理財建議：{res.get('advice', '無建議')}"})
                        st.rerun()

    # 輸入區
    with st.container():
        if is_mobile:
            uploaded_file = st.camera_input("拍照")
        else:
            uploaded_file = st.file_uploader("上傳收據", type=['jpg', 'jpeg', 'png'])
        
        prompt = st.chat_input("描述消費內容 (或輸入 '預算統計')...")
        
        if prompt or uploaded_file:
            # 偵測預算統計指令
            if prompt and prompt.strip() == "預算統計":
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    df_all = get_expenses()
                    total_spent = 0
                    if not df_all.empty:
                        df_all['date'] = pd.to_datetime(df_all['date'])
                        total_spent = df_all[df_all['date'].dt.strftime('%Y-%m') == datetime.now().strftime('%Y-%m')]['amount'].astype(int).sum()
                    
                    stats_msg = f"📊 **本月預算統計**\n\n已花費 / 預算上限: **${total_spent:,} / ${MONTHLY_BUDGET:,}**"
                    st.markdown(stats_msg)
                    st.progress(min(total_spent / MONTHLY_BUDGET, 1.0))
                    st.session_state.messages.append({"role": "assistant", "content": stats_msg})
                st.rerun()
                
            else:
                # 原有的辨識邏輯
                img_bytes = uploaded_file.getvalue() if uploaded_file else None
                
                new_msg = {"role": "user", "content": prompt or "上傳了圖片"}
                if img_bytes: new_msg["image"] = img_bytes
                st.session_state.messages.append(new_msg)
                
                with st.chat_message("user"):
                    st.markdown(new_msg["content"])
                    if img_bytes: st.image(img_bytes, caption="已上傳的圖片", width=200)
                
                with st.chat_message("assistant"):
                    with st.spinner("AI 思考中..."):
                        result = analyze_with_gemini(text_content=prompt, image_content=img_bytes)
                        if result:
                            st.markdown("辨識結果：")
                            msg = {"role": "assistant", "content": "請確認辨識結果並存檔", "data": result, "id": datetime.now().timestamp()}
                            st.session_state.messages.append(msg)
                            st.rerun()
                        else:
                            st.error("辨識失敗，請手動輸入資訊。")
                            # 顯示一個空白表單供手動輸入
                            manual_data = {"date": datetime.now().strftime('%Y-%m-%d'), "foodname": "", "amount": 0, "category": "其他", "advice": "無"}
                            msg = {"role": "assistant", "content": "辨識失敗，請手動輸入資料：", "data": manual_data, "id": datetime.now().timestamp()}
                            st.session_state.messages.append(msg)
                            st.rerun()

# --- 顯示歷史清單頁面 ---
elif page == "📋 歷史清單":
    st.header("📋 歷史消費記錄")
    st.dataframe(get_expenses().iloc[::-1], use_container_width=True)
