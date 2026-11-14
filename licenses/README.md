# 發佈前授權清單

目前未隨附外部工具二進位檔，未宣告工具授權審查完成。

- 本專案原始碼：源自使用者提供程式，尚未選定對外開源授權。
- shiba_states.png、app_icon.png：本次透過內建 imagegen，參考使用者選定的 A 預覽產生，非第三方下載素材；提示詞見 assets-provenance.md。尚未進行商標檢索。
- 字體：執行時使用 macOS 系統字體；沒有複製系統字體檔。
- Python、Tcl/Tk：隨 Python 發行版本保留 PSF、Tcl/Tk 及其他相依授權。
- yt-dlp / yt-dlp-ejs：本體 Unlicense；EJS 及其他依賴另有 MIT / ISC 等授權。依固定版本的實際套件保留原始 notices。
- FFmpeg / ffprobe：依實際編譯選項判斷 LGPL / GPL；不得使用不可再散佈的 nonfree 組建。提供與實際二進位相符的對應原始碼及必要建置資訊，並檢查所有相依函式庫。
- Deno：本體 MIT；保留其完整 third-party notices。
- PyInstaller：有封裝程式的授權例外，但不取代各相依元件授權義務。

官方來源：
https://github.com/yt-dlp/yt-dlp#licensing
https://github.com/yt-dlp/yt-dlp/wiki/EJS
https://ffmpeg.org/legal.html
https://github.com/denoland/deno/blob/main/LICENSE.md
https://pyinstaller.org/en/stable/license.html
https://docs.python.org/3/license.html

準備 tools/ffmpeg、tools/ffprobe、tools/deno 後，將授權全文、對應原始碼資訊及建置說明存入此目錄。
另建立 TOOLS_REVIEWED.json，逐項記錄工具來源網址、版本、SHA256、編譯選項、架構、相依函式庫、授權檔、對應原始碼位置及審查日期。
建置腳本只檢查此檔案是否存在，不代表自動完成法律或安全審查；不要用空檔案跳過檢查。
