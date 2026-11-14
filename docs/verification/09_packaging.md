# 階段 09 驗收紀錄：獨立 App／DMG 封裝與安裝

工作編號與狀態：09 獨立 App／DMG 封裝與安裝｜完成（未公證測試版）  
記錄日期：2026-11-15（Asia/Taipei）

## 1. 環境與依賴

- 目標平台：macOS `26.7.1`（`arm64`），`LSMinimumSystemVersion: 26.0`
- 打包環境：`.venv`（Python `3.14.6`、`yt-dlp 2026.11.04.232659`、`yt-dlp-ejs 0.8.0`、`PyInstaller 6.22.3`）
- 隨附獨立工具（皆經 `lipo -archs` 確認 `arm64` 與 `otool -L` 確認無 Homebrew 動態連結）：
  - `tools/deno`（`2.9.8`）
  - `tools/ffmpeg`（`9.0.2`）
  - `tools/ffprobe`（`9.0.2`）
- 授權紀錄：`licenses/TOOLS_REVIEWED.json`

## 2. 成品與校驗

- App：`dist/柴犬Youtube影片備份器.app`（本機 ad-hoc 簽章，`codesign --verify --deep --strict` 通過；未公證）
- DMG：`dist/柴犬Youtube影片備份器-0.1.0-arm64-未公證測試版-20261115-020259.dmg`（`149004589` bytes）
- DMG SHA-256：`6294b6fc44d2220d47a1cfa868b9e4e73ec5506d3c1993b107b5539d3909351b`

## 3. 實機驗收結果

- 使用者實機掛載 DMG、拖曳至 `/Applications`、退出 DMG 並從 `/Applications` 啟動，實測讀取格式、下載合併與播放皆正常；後續已依需求將顯示與成品名稱改為「柴犬Youtube影片備份器」並重新打包與重測全部 50 項自動測試通過。

## 4. 未完成與限制

- 尚未取得 Apple Developer ID 憑證與公證（階段 10）；從網路下載仍會觸發 macOS Gatekeeper 警告，須手動於「系統設定 → 隱私權與安全性」允許開啟。
- 尚未在 Intel Mac 或低於 macOS 26.0 的系統驗證。
