#!/bin/zsh
cd -- "${0:A:h}" || exit 1

# 使用本機已有 Tkinter 的 Python 與 Homebrew 下載元件。
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONPATH="$PWD/.runtime-packages:/opt/homebrew/opt/yt-dlp/libexec/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="/opt/anaconda3/bin/python3"

if [[ ! -x "$PYTHON" ]]; then
    print '找不到 Anaconda Python：/opt/anaconda3/bin/python3'
    read '?按 Enter 關閉。'
    exit 1
fi

"$PYTHON" -c 'import tkinter, yt_dlp, yt_dlp_ejs' && "$PYTHON" app.py
result=$?
if (( result != 0 )); then
    print '\n啟動失敗，請保留上方錯誤訊息以便排查。'
    read '?按 Enter 關閉。'
fi
exit "$result"
