# 階段 06 驗收紀錄：下載與後續網路邊界

工作編號與狀態：06 下載與後續網路邊界｜完成  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 修正或確認的具體問題

1. **`download()` 傳給 `yt-dlp` 的網址曾繞過正規化**：原 `download(url, ...)` 在 `extract()` 之後直接將原始 `url` 傳入 `ydl.extract_info(url, download=True)`；現已改為全程使用 `safe_url = validate_url(url)`。
2. **缺少 Extractor 白名單與明確 TLS／Cookie 邊界**：`ydl_options()` 未限定 `allowed_extractors: ['youtube']`、未明確設定 `nocheckcertificate: False` 與 `cookiefile: None`。
3. **格式中繼資料協定未篩選**：`format_choices()` 與音訊配對未過濾非 HTTP(S) 的 `url` 欄位。

## 2. 官方來源查證（2026-11-15）

- `allowed_extractors` 與 YouTube extractor 限制：`https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py`、`https://github.com/yt-dlp/yt-dlp/issues/6971`（確認 `['youtube']` 僅允許 `YoutubeIE`，不退回 `GenericIE`）。
- EJS 與 Deno 權限行為：`https://github.com/yt-dlp/yt-dlp/wiki/ejs`（確認搭配 `remote_components: set()` 停用遠端腳本下載；使用 Deno 時 JS 解題腳本在受限權限下執行，無檔案系統或網路存取權限）。

## 3. 實際修改檔案與原因

- `shiba_studio/core.py`：新增 `allowed_extractors: ['youtube']`、`nocheckcertificate: False`、`cookiefile: None`、`is_http_format_url()`，並於 `download()` 全程傳遞 `safe_url = validate_url(url)`。
- `tests/test_network_boundaries.py`：補齊網址正規化追蹤、Extractor 設定與非 HTTP 協定過濾測試。

## 4. 測試結果

- 執行命令：`PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH" .venv/bin/python -B -m unittest discover -s tests -v`
- 實際結果：**50 項測試全數通過（`OK`，耗時 `0.496s`）**（含 `tests/test_network_boundaries.py` 3 項）。

## 5. 是否符合本步完成條件

- 符合。所有下載呼叫使用正規化輸入、Extractor 與協定邊界有測試保護。
