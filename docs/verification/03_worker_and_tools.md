# 階段 03 驗收紀錄：明確化外部工具、匯入與工作程序邊界

工作編號與狀態：03 明確化外部工具、匯入與工作程序邊界｜完成  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 修正或確認的具體問題

1. **`app.py` worker 請求缺乏大小與欄位結構驗證**：原程式直接 `json.loads(sys.stdin.readline())` 並索引欄位，未限制單行大小，也未檢查 JSON 物件型別及 `url`／`folder`／`selected` 型別與長度。
2. **`core.py` 工具名稱未限定白名單與相對路徑風險**：`tool()` 未限定僅允許 `ffmpeg`、`ffprobe`、`deno`；`verify_output()` 若傳入以 `-` 開頭的相對路徑，可能被外部工具誤當選項。
3. **`gui.py` 子程序環境與事件輪詢異常保護不足**：`start()` 未清理 `PYTHONSTARTUP` 等注入變數（封裝模式亦應移除 `PYTHONPATH`、`PYTHONHOME`、`DYLD_*`）；`poll()` 若在 `handle()` 處理畸形事件時拋出例外，會導致 `self.after(80, self.poll)` 不再排程而永久鎖死介面。

## 2. 實際修改檔案與原因

- `app.py`：新增 `parse_worker_request()` 與 `run_worker()`，限制單行請求上限（`16384` bytes）、驗證 `dict` 結構、允許動作（`read`／`download`）及各欄位型別與長度。
- `shiba_studio/core.py`：`tool()` 限定 `ALLOWED_TOOLS`（`ffmpeg`、`ffprobe`、`deno`）並確認非封裝模式下為真實可執行檔；`verify_output()` 先 `resolve()` 確保傳給 `ffprobe` 的為絕對路徑。
- `shiba_studio/gui.py`：新增 `worker_env()` 清理啟動注入環境變數（封裝模式移除 `PYTHONPATH`、`PYTHONHOME`、`DYLD_*`）；`poll()` 以 `try ... finally` 確保 `after(80, self.poll)` 必繼續排程且單筆異常不中斷輪詢；`handle()` 驗證 `stage`、`progress`、`formats`、`result`、`error` 欄位型別與未知事件。
- `tests/test_worker_and_tools.py`：新增 7 項工具來源、參數陣列、Worker 請求與 GUI 事件邊界測試。
- `docs/verification/03_worker_and_tools.md`：記錄階段 03 驗收結果。

## 3. 環境與程式版本

- Python：`/opt/anaconda3/bin/python3`（`3.14.6`），macOS `26.7.1`（`arm64`）。

## 4. 安全測試與回歸測試結果

- 執行命令：
  ```sh
  export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  /opt/anaconda3/bin/python3 -B -m unittest discover -s tests -v
  ```
- 實際結果：**33 通過、0 失敗、0 跳過（`OK`，耗時 `0.276s`）**。
  - 新增 `tests/test_worker_and_tools.py`（7 項全過）：
    - `test_tool_rejects_unlisted_and_frozen_never_falls_back_to_path`
    - `test_run_process_preserves_arg_array_with_spaces_chinese_quotes_and_dash`
    - `test_run_process_timeout_and_nonzero_exit_raise_user_error`
    - `test_verify_output_resolves_leading_dash_filename`
    - `test_worker_request_rejects_malformed_and_oversized_inputs`
    - `test_worker_env_strips_injection_vars_when_frozen`
    - `test_gui_poll_survives_malformed_and_unknown_events_and_unlocks_on_exit`
  - 原有 `test_core.py`（9）、`test_file_safety.py`（8）、`test_pipeline.py`（3）、`test_edit_shortcuts.py`（3）、`test_scroll.py`（3）全數通過。

## 5. 未驗證事項與阻擋

- 封裝模式（`frozen=True`）下的真實工具載入與 GUI 實機視窗，需待階段 07／09 實測。
- 背景工作程序僅為獨立程序邊界，不構成作業系統級權限沙箱。

## 6. 是否符合本步完成條件

- 符合。工具來源與參數規則明確，畸形請求或異常事件皆受控失敗並恢復介面狀態。

## 7. 下一個可執行工作

- **階段 04：改善更新切換、恢復與可追溯性**（檢查 `更新下載元件.command`、`requirements.txt` 與隔離測試）。
