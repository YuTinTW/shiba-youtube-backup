# 階段 01 驗收紀錄：建立環境與測試基準

工作編號與狀態：01 建立環境與測試基準｜完成基準盤點（GUI 視窗實機啟動於目前受限環境受阻）  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 修正或確認的具體問題

- 確認專案目前未納入 Git 版控，已為 17 個核心程式、腳本、設定與測試檔建立 SHA-256 基準。
- 確認 `/usr/bin/python3` 為 `3.9.6`，不符合 3.11+ 需求；日常啟動腳本 `啟動柴犬存檔室.command` 使用 `/opt/anaconda3/bin/python3`（`3.14.6`），搭配專案內 `.runtime-packages/` 與 Homebrew 工具。
- 確認 `pyinstaller` 目前未安裝於選用 Python 環境（對階段 09 封裝有影響，對階段 01～08 無阻擋）。
- 確認在目前受限執行環境中，Tk 視窗初始化無法連線 `com.apple.hiservices-xpcservice`，無法由自動化命令完成真實視窗啟動。

## 2. 實際修改檔案與原因

- 新增 `docs/verification/01_environment_baseline.md`：記錄階段 01 實測環境、檔案雜湊基準、測試結果與阻擋事項。
- 未修改任何應用程式碼、測試檔、啟動腳本或 `SECURITY.md`。

## 3. 環境與程式版本（實測取得）

| 項目 | 實測路徑／版本 |
| --- | --- |
| 作業系統 | macOS 26.7.1（Build `25G241`），`arm64` |
| 系統預設 Python | `/usr/bin/python3` — Python `3.9.6` |
| 選用 Python | `/opt/anaconda3/bin/python3` — Python `3.14.6` |
| Tk / Tcl | `TkVersion: 8.6` / `TclVersion: 8.6` |
| `yt-dlp` | `2026.11.04.232659dev`（`.runtime-packages/yt_dlp/__init__.py`） |
| `yt-dlp-ejs` | `0.8.0`（`.runtime-packages/yt_dlp_ejs/__init__.py`） |
| `pyinstaller` | 未安裝（`NOT INSTALLED`） |
| `ffmpeg` | `/opt/homebrew/bin/ffmpeg` — `8.1.2` |
| `ffprobe` | `/opt/homebrew/bin/ffprobe` — `8.1.2` |
| `deno` | `/opt/homebrew/bin/deno` — `2.9.4`（`aarch64-apple-darwin`） |

## 4. 檔案 SHA-256 基準

```text
05f7904a6e7d89fda900f3682823feaa5519541ed3189350d334f4c706567527  app.py
9851685a493af247d469b619d2ac2c617eaf550c7ba5a10086636441564f182e  requirements.txt
236a5a4d97abfbc9ae565e62eee5f6e8b04259a231fb95af22f4b865928e6e05  ShibaStudio.spec
365eaf87d9cb19ed32f9eb40b1ced308cd3efcaa23f95eb71c3b0f52c207abce  SECURITY.md
16a53c67fe66bac75854669f0b0f40ed06d2b4c3ecfadb384df1e919e9123b4b  README.md
7bb243b6064ac09a2cc7314afa050144192bc35daba23aba82f9e8b3bed9db7a  啟動柴犬存檔室.command
d563ebfb93c8fe6082a565948e398138f481fda423ac7169ac29cc044fa224a8  更新下載元件.command
f80790a9b63b852f9d8fa237b00b624311158b32dfac032389b46923125f4410  shiba_studio/__init__.py
733e1ec096f1c9e252e2482b0043ba6ac3c04395aa24b91613bf71aa0299505c  shiba_studio/core.py
5d6932c09d4c0d8eeafb5d7887d311b474b7015a056100303391427e5b7e3b65  shiba_studio/gui.py
5105a7b2530b36e8d3fca2b53ead1d9ca1b1510b6c76cc6b3fd69dacf069f0b5  scripts/build_macos.py
fed759f3b9b50752d3a6b18465a9e076bb0de4bc7238ba815a3ce66b925edcc0  scripts/make_icon.py
976dd58a73f11477ea1a288034f004b9169ab2ce924126b2cee471013463d4f7  tests/test_core.py
9849bad0fed4a2eb53e1bc3c0f2b654c747c895399c01250ef69e13ccd21e39e  tests/test_pipeline.py
522bdf5029a9f47a977b2e31faebe437fbf2ed3766c98238c9ed96367eaa9cf1  tests/test_edit_shortcuts.py
0d440048b9662cecd46fb33a8fdec2943bb4c6a1cccb37614438f6033db69fce  tests/test_scroll.py
518f9a6c9bd10a1a56073039ddac9a7427745bcb5c470c4b33c814fadfb62d22  resources/entitlements.plist
```

## 5. 測試與啟動驗證

### 回歸測試（既有 18 個方法）

- 執行環境與命令：
  ```sh
  export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  /opt/anaconda3/bin/python3 -B -m unittest discover -s tests -v
  ```
- 預期結果：執行既有 18 個單元與整合測試，確認各自通過／失敗／跳過狀態。
- 實際結果：`Ran 18 tests in 0.259s` — **18 通過、0 失敗、0 跳過（`OK`）**。
  - `tests/test_core.py`：9 項通過（含網址驗證、檔名、同名不覆寫、資料夾檢查、串流驗證、403／網路錯誤、無硬連結複製）
  - `tests/test_edit_shortcuts.py`：3 項通過（中英文快捷鍵分派邏輯，不含真實 Tk 視窗）
  - `tests/test_pipeline.py`：3 項通過（合成影音真實 FFmpeg 合併／ffprobe 驗證、合併失敗、部分成功；下載使用替身）
  - `tests/test_scroll.py`：3 項通過（清單捲動邏輯）

### GUI 視窗啟動嘗試

- 執行命令：
  ```sh
  export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  /opt/anaconda3/bin/python3 -B -c 'from shiba_studio.gui import Studio; app = Studio(); app.update(); app.after(200, app.destroy); app.mainloop()'
  ```
- 實際結果：**受阻（未通過）**。程序於視窗初始化時卡住並輸出：
  `Error received in message reply handler: Connection invalid` / `Connection Invalid error for service com.apple.hiservices-xpcservice.`，隨後手動終止（exit code 9）。

## 6. 未驗證事項與阻擋

- 真實 macOS GUI 視窗啟動與渲染無法在目前受限命令環境執行（`com.apple.hiservices-xpcservice` 連線無效），須於本機桌面環境實測。
- 真實 YouTube 網路連線與下載、獨立 `.venv/` 與 `PyInstaller` 封裝尚未在本階段執行。

## 7. 是否符合本步完成條件

- 已建立環境、版本、檔案 SHA-256 與 18 項測試的完整可追溯基準；GUI 實機啟動依規定明確標示為「受阻」，未以 `import` 成功替代視窗啟動。

## 8. 下一個可執行工作

- **階段 02：檔案保全與清理驗證**（優先檢查 `shiba_studio/core.py` 的 `publish_file()`、`check_folder()`、`safe_name()`、`download()` 及相關安全測試）。
