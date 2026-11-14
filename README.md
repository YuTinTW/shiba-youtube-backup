# 柴犬存檔室 0.1.0（開發中）

## 本機日常使用

1. 雙擊 `啟動柴犬存檔室.command`。
2. 複製 YouTube 網址，按「貼上網址」，或在輸入欄貼上。
3. 選擇儲存資料夾，按「讀取格式」。
4. 勾選影片畫質或純音訊，再按「下載勾選項目」。

更新下載元件時，執行 `更新下載元件.command`；成功後關閉並重新啟動 App。

本機啟動檔使用 `/opt/anaconda3/bin/python3`、專案內隱藏的 `.runtime-packages/`，以及 Homebrew 的 FFmpeg、ffprobe、Deno。`.runtime-packages/` 是目前使用中的下載套件，請勿刪除。這些啟動檔僅針對目前這台 Mac 設定。

## 檔案位置

- `啟動柴犬存檔室.command`、`更新下載元件.command`：日常啟動與更新。
- `app.py`、`shiba_studio/`：目前程式。
- `resources/`、`licenses/`：介面素材與來源記錄。
- `tests/`：自動測試。
- `scripts/`、`ShibaStudio.spec`、`requirements.txt`：開發與封裝設定。
- `docs/history/`：原始教學程式、設計提案及歷史驗證記錄。

2026-11-15 整理時已移除未使用且缺少 Tkinter 的舊 `.venv/`、過期的 `deliverables/` 原始碼壓縮包與校驗表、Python 快取、驗證用合成影音及圖示中間檔。未來需要獨立開發或打包時，可依下方說明重建 `.venv/`。

以下保留開發與封裝說明；歷史驗證狀態不代表目前版本已通過所有實機測試。

採用使用者選定的 **C 三欄配置＋A 柴犬造型**。原始教學程式保留於 `docs/history/`，新增程式由 `app.py` 啟動。

**尚未產出可安裝的 App 或 DMG。** 本環境無法連到 PyPI／YouTube，缺少封裝依賴，且可用 Tkinter 在目前執行環境初始化失敗。原始碼已完成第一版與核心測試，介面及動畫尚未實機驗證。請勿把此版本當正式發佈版。

## 新增元件與方法的用途

- `yt-dlp`：讀取影片格式及下載，取代原版的 `pytubefix`；仍保留 MP4 影片、純音訊與多選功能。
- `yt-dlp-ejs`：YouTube 解題元件，由 `yt-dlp[default]` 相依群組取得。
- Deno：執行解題所需 JavaScript 的外部工具，不是 Python 套件。
- FFmpeg：合併影像與聲音；ffprobe：檢查輸出檔案是否含必要串流。
- PyInstaller：將 Python 解譯器、Tkinter、套件與素材打包成不需另裝 Python 的 App。最終使用者不必安裝這些開發套件。
- `subprocess`：背景下載在獨立 Python 工作程序中執行，避免阻塞視窗。
- `threading`＋`queue`：讀取背景程序訊息，安全送回介面；只在主執行緒操作 Tk。
- `after`：定時更新進度、工作文字及柴犬動畫，不使用會阻塞視窗的 sleep。

## 功能與操作

1. 左欄貼上單支 YouTube 網址，選擇資料夾並按「讀取格式」。
2. 中欄勾選實際讀取到的影片／純音訊格式，可多選。影片選項會自動搭配 MP4 音訊。
3. 右欄按「下載勾選項目」。工作期間鎖定相關操作，避免重複下載。
4. 有真實總位元組數時才顯示目前串流百分比；未知大小、讀取及合併時顯示活動進度。
5. 經下載、必要合併及 ffprobe 檢查後才顯示完成；部分失敗另行標示。
6. 可開啟儲存資料夾與診斷記錄。診斷記錄位於使用者的 `~/Library/Logs/ShibaStudio/`，不寫入 App bundle。

不提供播放清單、進行中的直播、錄音、播放控制、MP3 轉檔或下載歷史。保留原始編碼，不保證所有 MP4 都能由每一版 QuickTime 播放。下載工具仍可能因網站調整而需要更新。

## 開發環境啟動

以下指令必須在**含可正常啟動 Tkinter 的 Python 3.11 以上環境**執行。本機目前預設 Python 不符合 Tkinter 條件。

```sh
python3 -m tkinter
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

開發時另需可執行的 `ffmpeg`、`ffprobe`、`deno`，可由 PATH 尋找。正式 App 僅使用 bundle 內的工具，不依賴 Homebrew 路徑。

目前鎖定套件版本是候選建置組合，不代表已完成相容性驗證。實際網路檢查使用本機既有 yt-dlp 2026.07.04，因 DNS 失敗，未成功讀取影片。

## 測試

```sh
python3 -m unittest discover -s tests -v
```

核心測試不需 GUI。整合測試需要本機 FFmpeg／ffprobe，使用合成影音與下載替身，實際執行合併及驗證；不能當成 YouTube 真實下載成功的證據。

## 建置 App／DMG（目前未成功執行）

本設定只以 **macOS 26、arm64** 為候選目標，Info.plist 暫設最低 26.0；不是已驗證支援聲明。未驗證 Intel 或其他 macOS。

1. 使用能正常啟動 Tkinter 的 arm64 Python 環境，安裝 requirements.txt。
2. 在 `tools/` 放入可再散佈的 arm64 `ffmpeg`、`ffprobe`、`deno`。所有動態相依套件也要一併處理。不要使用指向開發機的 wrapper／符號連結冒充獨立工具。
3. 依 `licenses/README.md` 完成授權及來源清單。
4. 執行測試，再執行：

```sh
.venv/bin/python scripts/build_macos.py
```

腳本會先檢查必要模組、實際建立 Tk 視窗、檢查工具架構與授權記錄，再執行 PyInstaller。產出預定為 `dist/柴犬存檔室.app` 與帶版本／時間的 DMG；DMG 內有 `/Applications` 捷徑及安裝說明。

圖示已生成 PNG 及 ICNS；可用 `python3 scripts/make_icon.py` 重建。受限環境的 iconutil 若失敗，會改以現有 PNG 建立 ICNS 容器，不修改原始像素。

正式簽署及公證需要使用者的 Developer ID 憑證與已設好的 keychain profile；不要把憑證密碼寫在程式碼內：

```sh
.venv/bin/python scripts/build_macos.py --identity 'Developer ID Application: 實際身分' --notary-profile '實際profile名稱'
```

腳本會先提交 App 公證、附加票據，再封裝 DMG 並提交公證。這段流程尚未驗證。未提供憑證的版本不是 Developer ID 簽署版，且未公證，可能被 Gatekeeper 阻擋。

建置成功後仍必須實際掛載 DMG、拖曳安裝、退出 DMG，再從安裝位置啟動與下載，並在乾淨 Mac 環境驗證。建置腳本成功不等於完成交付驗收。

## 交付檔案

- `app.py`：應用程式與背景工作入口。
- `shiba_studio/core.py`：網址、格式、下載、合併、輸出與錯誤處理。
- `shiba_studio/gui.py`：三欄介面、操作鎖定、進度與柴犬狀態。
- `resources/`：四狀態 sprite sheet、PNG／ICNS 圖示及簽署設定。
- `ShibaStudio.spec`、`scripts/`：封裝設定及建置步驟。
- `licenses/`：素材來源、提示詞及待完成的工具授權清單。
- `docs/history/`：原始教學程式、設計稿與歷史驗證記錄。

官方依據：
https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26
https://github.com/yt-dlp/yt-dlp/wiki/EJS
https://ffmpeg.org/legal.html
https://pyinstaller.org/en/stable/usage.html
https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
