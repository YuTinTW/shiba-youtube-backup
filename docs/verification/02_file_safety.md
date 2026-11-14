# 階段 02 驗收紀錄：檔案保全與清理驗證

工作編號與狀態：02 檔案保全與清理驗證｜完成  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 修正或確認的具體問題

1. **複製失敗清理缺乏歸屬驗證（競態風險）**：原 `shiba_studio/core.py` 的 `publish_file()` 在 `open('xb')` 複製失敗後直接呼叫 `target.unlink()`；若目標路徑在失敗前被其他程序替換，可能誤刪非本次建立的檔案。
2. **發佈目錄與目標缺乏 `O_NOFOLLOW`／`dir_fd` 防護**：`publish_file()` 未以 `dir_fd` 與 `O_NOFOLLOW` 鎖定儲存資料夾與排他建立目標，亦未拒絕含路徑分隔符或 `.`／`..` 的檔名。
3. **下載暫存路徑與副檔名中繼資料缺少邊界檢查**：`download()` 直接信任 `ydl.prepare_filename(result)` 回傳路徑且未消毒 `row['ext']`，若中繼資料異常可能造成暫存路徑逸出或畸形檔名。

## 2. 實際修改檔案與原因

- `shiba_studio/core.py`：
  - 新增 `safe_ext()` 消毒輸出副檔名，僅保留英數字（空值回落為 `'bin'`）。
  - 新增 `ensure_within_temp()` 驗證 `ydl.prepare_filename(result)` 非符號連結且 `resolve()` 後嚴格位於本次 `.shiba-*` 暫存目錄內。
  - 更新 `publish_file()`：拒絕非法檔名；以 `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` 開啟 `dir_fd`；硬連結與 `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW` 皆透過 `dir_fd` 執行；排他建立後以 `os.fstat(fd)` 記錄 `(st_dev, st_ino)`，複製失敗清理前以 `os.stat(..., dir_fd=dir_fd, follow_symlinks=False)` 確認歸屬仍相符才呼叫 `os.unlink()`。
- `tests/test_file_safety.py`：新增 8 個檔案保全、競態清理與路徑邊界安全測試。
- `docs/verification/02_file_safety.md`：記錄階段 02 驗收結果。

## 3. 環境與程式版本

- Python：`/opt/anaconda3/bin/python3`（`3.14.6`）
- 測試於 macOS `26.7.1`（`arm64`）APFS 本機暫存目錄執行，搭配 FFmpeg `8.1.2`、ffprobe `8.1.2`。

## 4. 安全測試與回歸測試結果

- 執行命令：
  ```sh
  export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
  export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  /opt/anaconda3/bin/python3 -B -m unittest discover -s tests -v
  ```
- 實際結果：**26 通過、0 失敗、0 跳過（`OK`，耗時 `0.254s`）**。
  - 新增 `tests/test_file_safety.py`（8 項全過）：
    - `test_existing_numbered_files_skip_to_next_available`（既有同名與序號檔案保全）
    - `test_dangling_symlink_target_is_never_followed_or_overwritten`（dangling symlink 不追蹤寫入）
    - `test_symlink_folder_and_invalid_names_are_rejected`（symlink 資料夾與非法檔名拒絕）
    - `test_copy_failure_cleans_own_partial_file_only`（複製失敗僅清理自身半成品）
    - `test_copy_failure_does_not_unlink_replaced_file_in_race`（同步點模擬路徑替換競態，確認不誤刪新檔案）
    - `test_cleanup_error_does_not_mask_original_error_or_touch_existing`（清理失敗不掩蓋原錯誤且不影響既有檔案）
    - `test_concurrent_publish_same_name_never_overwrites`（多執行緒並行同名發佈，包含硬連結與替代複製兩路徑）
    - `test_download_rejects_escaped_prepare_filename_and_sanitizes_ext`（攔截逸出 `temp` 的 `prepare_filename` 與畸形 `ext`）
  - 原有 `test_core.py`（9）、`test_pipeline.py`（3）、`test_edit_shortcuts.py`（3）、`test_scroll.py`（3）全數通過。

## 5. 未驗證事項與阻擋

- exFAT／外接磁碟跨檔案系統發佈僅以模擬 `os.link` 失敗測試，尚未在實體 exFAT 磁碟機實測。
- 若程序遭 `SIGKILL` 強制終止，`.shiba-*` 暫存目錄可能殘留於儲存資料夾，屬作業系統限制（不會影響使用者既有檔案）。

## 6. 是否符合本步完成條件

- 符合。既有檔案在所有失敗、競態與清理情境前後 SHA-256 皆維持不變；回歸測試可穩定重現與驗證修正。

## 7. 下一個可執行工作

- **階段 03：明確化外部工具、匯入與工作程序邊界**（檢查 `core.py` 的 `tool()`、`run_process()`、`ydl_options()`，`app.py` 與 `gui.py` 的 worker 請求／事件驗證，以及啟動腳本）。
