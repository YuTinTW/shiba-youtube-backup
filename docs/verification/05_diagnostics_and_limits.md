# 階段 05 驗收紀錄：診斷遮蔽與資源限制

工作編號與狀態：05 診斷遮蔽與資源限制｜完成  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 修正或確認的具體問題

1. **診斷記錄未集中遮蔽與截斷**：原 `core.py`、`app.py` 與 `gui.py` 直接將第三方錯誤、URL 查詢參數、本機家目錄路徑與例外文字寫入 `diagnostic.log`，亦未在寫入前截斷超長訊息或預先檢查輪替大小。
2. **事件佇列與子程序輸出無上限**：原 `gui.py` 的 `events` 佇列無容量上限，`reader()` / `errors()` 直接逐行讀取無長度上限，且無工作總時限看門狗。
3. **下載前未檢查可用磁碟空間**：`download()` 未依預估影音大小與基本門檻檢查儲存位置可用空間。

## 2. 實際修改檔案與原因

- `shiba_studio/core.py`：
  - 新增 `sanitize_diagnostic()`：集中遮蔽 URL 內嵌帳號密碼、敏感查詢參數（`token`、`sig`、`key`、`auth`、`cookie` 等）、HTTP 認證標頭與本機家目錄路徑（`/Users/...`），並限制單筆上限 `2000` 字元（附 `... [TRUNCATED]`）。
  - 新增 `check_disk_space()`：於 `download()` 下載每項前檢查可用磁碟空間（至少 `100 MB`；已知預估大小時依 `1.2x + 50 MB` 檢查）。
  - 更新 `ydl_options()` 的 Logger 與 `download()` 的診斷輸出，一律經 `sanitize_diagnostic()` 處理。
- `app.py`：`run_worker()` 輸出 `diagnostic` 事件前先呼叫 `sanitize_diagnostic()`。
- `shiba_studio/gui.py`：
  - `self.events` 改為有界佇列 `queue.Queue(maxsize=256)`，並新增 `enqueue_bounded()`：佇列滿時不阻塞 pipe，可丟棄非關鍵進度／診斷，但確保 `formats`、`result`、`error`、`worker_exit` 關鍵事件不被丟棄。
  - 新增 `iter_bounded_lines()`（單行上限 `65536` bytes），超長行截斷後持續排空至換行符，避免 pipe 死鎖。
  - 新增背景工作逾時看門狗（讀取 `180` 秒、下載 `14400` 秒），逾時安全終止程序；`poll()` 限制單次最多處理 `64` 筆；`handle()` 寫入 `diagnostic.log` 前再次執行 `sanitize_diagnostic()` 並於寫入前檢查輪替大小。
- `tests/test_diagnostics.py`：新增 7 項診斷遮蔽、截斷、有界佇列、有界行讀取、日誌失敗不鎖死與磁碟空間檢查測試。
- `docs/verification/05_diagnostics_and_limits.md`：記錄階段 05 驗收結果。

## 3. 環境與程式版本

- Python：`/opt/anaconda3/bin/python3`（`3.14.6`），macOS `26.7.1`（`arm64`）。

## 4. 安全測試與回歸測試結果

- 執行命令：
  ```sh
  export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  /opt/anaconda3/bin/python3 -B -m unittest discover -s tests -v
  ```
- 實際結果：**47 通過、0 失敗、0 跳過（`OK`，耗時 `0.289s`）**。
  - 新增 `tests/test_diagnostics.py`（7 項全過）。
  - 原有 `test_core.py`（9）、`test_file_safety.py`（8）、`test_worker_and_tools.py`（7）、`test_updater.py`（7）、`test_pipeline.py`（3）、`test_edit_shortcuts.py`（3）、`test_scroll.py`（3）全數通過。

## 5. 未驗證事項與阻擋

- 真實極大影片長時間下載逾時與真實視窗下大量進度事件的流暢度，需待階段 07／08 實測。

## 6. 是否符合本步完成條件

- 符合。敏感測試值不落盤、有界佇列與行讀取避免記憶體耗盡與死鎖、日誌寫入失敗不鎖死介面或掩蓋下載結果。

## 7. 下一個可執行工作

- **階段 06：下載與後續網路邊界**（檢查 `core.py` 的 `validate_url()`、`extract()`、`download()`、`ydl_options()` 與後續請求／重新導向邊界）。
