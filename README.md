## 📦 自動 Release

每次 GitHub Action 執行成功後，會自動創建一個新的 Release，包含：

- **版本標籤**: 基於日期時間自動生成 (如 `v2026.08.03-1430`)
- **發布內容**: 
  - `ffxiv_items_all_languages.csv` - 完整 CSV 數據
  - `ffxiv_items_all_languages.json.gz` - 壓縮 JSON 數據
  - `version.txt` - 版本資訊（包含時間戳、筆數等）
- **自動清理**: 保留最近 30 個 Release

### 下載最新數據

你可以從 [Releases](https://github.com/your-username/ffxiv-item-data/releases) 頁面下載最新或歷史版本的數據檔案。