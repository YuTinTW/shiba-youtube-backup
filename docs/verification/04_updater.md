# 階段 04 驗收紀錄：改善更新切換、恢復與可追溯性

工作編號與狀態：04 改善更新切換、恢復與可追溯性｜完成  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 修正或確認的具體問題

1. **原更新腳本缺乏互斥與可測試性**：`更新下載元件.command` 將全部邏輯寫於 zsh 內，缺少並行更新互斥鎖，也無法在隔離目錄測試 pip 失敗、匯入失敗、切換失敗與恢復失敗。
2. **預設啟用預發佈版且缺少可追溯紀錄**：原腳本無條件使用 `--upgrade --pre`，未區分穩定版與預發佈版，亦未記錄更新來源、套件版本與 `RECORD` SHA-256 摘要。
3. **切換與恢復失敗保護不足**：切換失敗且還原失敗時，原腳本未明確輸出人工恢復路徑；舊備份亦無明確保留／清理邊界。

## 2. 實際修改檔案與原因

- `shiba_studio/updater.py`：新增可測試的更新模組：
  - 使用 `.runtime-update.lock` 與 `fcntl.flock(..., LOCK_EX | LOCK_NB)` 防止並行更新。
  - 預設採穩定版策略（不加 `--pre`），僅於明確傳入 `--pre` 時才安裝預發佈版。
  - 先安裝至同檔案系統的 `.runtime-update.*` 暫存目錄，於隔離子程序驗證 `yt_dlp` 與 `yt_dlp_ejs` 可匯入並取得版本後，寫入 `.update-manifest.json`（含時間、來源 URL、版本與 `.dist-info/RECORD` SHA-256）。
  - 備份 `.runtime-packages` 至 `.runtime-backup.*` 後才切換；切換失敗立即嘗試還原，若還原也失敗則保留備份並明確輸出手動恢復路徑。
  - 切換成功後保留本次備份並清理更早的舊備份；失敗時安全清理暫存目錄。
- `更新下載元件.command`：改為呼叫 `/opt/anaconda3/bin/python3 -B -m shiba_studio.updater "$@"`。
- `tests/test_updater.py`：新增 7 項隔離目錄測試（涵蓋 pip 失敗、匯入失敗、備份失敗、切換失敗與恢復成功、雙重失敗保留備份、並行互斥鎖、穩定版策略與 manifest 寫入）。
- `docs/verification/04_updater.md`：記錄階段 04 驗收結果。

## 3. 環境與程式版本

- Python：`/opt/anaconda3/bin/python3`（`3.14.6`），macOS `26.7.1`（`arm64`）。

## 4. 安全測試與回歸測試結果

- 執行命令：
  ```sh
  export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  /opt/anaconda3/bin/python3 -B -m unittest discover -s tests -v
  ```
- 實際結果：**40 通過、0 失敗、0 跳過（`OK`，耗時 `0.279s`）**。
  - 新增 `tests/test_updater.py`（7 項全過）。
  - 原有 `test_core.py`（9）、`test_file_safety.py`（8）、`test_worker_and_tools.py`（7）、`test_pipeline.py`（3）、`test_edit_shortcuts.py`（3）、`test_scroll.py`（3）全數通過。

## 5. 未驗證事項與阻擋

- 尚未執行真實連網 PyPI 安裝（目前測試使用隔離目錄與注入替身，避免修改使用者使用中的 `.runtime-packages/`）。
- 若未指定固定鎖定檔（例如 `--require-hashes`），一般更新仍依 PyPI Simple API 與 TLS 驗證取得最新穩定版，不構成完整離線雜湊釘選。

## 6. 是否符合本步完成條件

- 符合。半成品絕不啟用、失敗保留或還原原元件、並行更新受互斥鎖保護、更新結果具備 `.update-manifest.json` 可追溯紀錄。

## 7. 下一個可執行工作

- **階段 05：診斷遮蔽與資源限制**（檢查 `gui.py` 的 `handle()`、`start()`、事件佇列與讀取執行緒，以及 `core.py` 的 Logger、進度與 `run_process()`）。
