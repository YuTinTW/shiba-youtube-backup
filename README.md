# 柴犬Youtube影片備份器 0.1.0

macOS 桌面端 YouTube 單支影片與純音訊備份工具（Apple Silicon 測試版）。

## 一般使用者下載與安裝

前往 [GitHub Releases](https://github.com/YuTinTW/shiba-youtube-backup/releases) 下載最新 `.dmg` 安裝檔：

- **適用環境**：Apple Silicon（M1 / M2 / M3 / M4）Mac、**macOS 26.0 以上**（不支援 Intel Mac）。
- **安裝步驟**：
  1. 下載 `.dmg` 並雙擊打開。
  2. 將 **「柴犬Youtube影片備份器」** 拖曳到 **Applications（應用程式）** 資料夾，再退出磁碟映像檔。
  3. 雙擊「應用程式」內的 **柴犬Youtube影片備份器** 啟動。
- **首次開啟若被系統阻擋**：本測試版尚未經 Apple Developer ID 簽署公證，初次執行會觸發 macOS Gatekeeper 提示。請打開 **「系統設定 → 隱私權與安全性」**，捲到最下方點 **「仍要打開」** 即可。
- **v0.1.0 DMG SHA-256**：`6294b6fc44d2220d47a1cfa868b9e4e73ec5506d3c1993b107b5539d3909351b`

## 功能與操作

1. 左欄貼上單支 YouTube 網址，選擇儲存資料夾並按「讀取格式」。
2. 中欄勾選實際讀取到的 MP4 畫質或純音訊格式（可多選；影片選項會自動合併 MP4 音訊）。
3. 右欄按「下載勾選項目」，經下載、合併與 `ffprobe` 串流檢查後輸出；遇到同名檔案會自動遞增序號，不覆蓋既有檔案。
4. 診斷記錄寫入 `~/Library/Logs/ShibaStudio/diagnostic.log`（已遮蔽敏感查詢參數、憑證與家目錄使用者名稱）。

不提供播放清單、進行中的直播、錄音、播放控制、MP3 轉檔或下載歷史。
