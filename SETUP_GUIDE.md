# AI 生活費記帳助手 - 線上版設定指南

本指南將協助您將記帳程式部署至 Streamlit Cloud，並整合 Google Sheets 作為雲端資料庫。

## 1. 準備 Google Sheet
1. 建立一個新的 Google 試算表，命名為「生活費記帳」。
2. 第一列可以預先填入標題（選用）：`date`, `store`, `amount`, `category`。
3. 複製該試算表的 **網址 (URL)**。

## 2. 建立 Google Cloud 服務帳號 (API 金鑰)
1. 前往 [Google Cloud Console](https://console.cloud.google.com/)。
2. 建立新專案並 **啟用**「Google Sheets API」和「Google Drive API」。
3. 前往「**憑證**」 -> 「**建立憑證**」 -> 「**服務帳號**」。
4. 建立後，點擊該帳號進入「**金鑰**」頁籤，點擊「**新增金鑰**」 -> 「**建立新金鑰**」 -> 選擇 **JSON** 並下載。
5. **重要**：打開 JSON 檔案，複製裡面的 `client_email`。
6. 回到 Google 試算表，點擊「**共用**」，將該 Email 加入並設為「**編輯者**」。

## 3. 部署與 Secrets 設定
1. 將程式碼上傳至 GitHub。
2. 在 [Streamlit Cloud](https://share.streamlit.io/) 部署該 Repository。
3. 在 App 設定中的 **Secrets** 填入以下內容（請根據 JSON 檔案內容替換）：

```toml
# Gemini API 設定
GOOGLE_API_KEY = "您的_GEMINI_API_KEY"
MONTHLY_BUDGET = 15000

# Google Sheets 連線設定
[connections.gsheets]
spreadsheet = "您的試算表網址"
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

## 4. 本地測試 (選用)
1. 安裝套件：`pip install -r requirements.txt`
2. 建立 `.streamlit/secrets.toml` 並填入上述 Secrets 內容。
3. 執行：`streamlit run streamlit_app.py`
