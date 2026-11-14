"""在具備 Tkinter 與完整依賴的 macOS Python 環境內執行。"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def run(*args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity', help='Developer ID Application 簽署身分；省略為測試版')
    parser.add_argument('--notary-profile', help='已存於 keychain 的 notarytool profile 名稱')
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise SystemExit('本設定僅供 arm64 macOS 建置；尚未驗證 Intel。')
    if args.notary_profile and not args.identity:
        raise SystemExit('公證需要先提供 Developer ID 簽署身分。')
    missing = [name for name in ('tkinter','yt_dlp','yt_dlp_ejs','PyInstaller')
               if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit('缺少打包依賴：' + ', '.join(missing) + '。請參照 README。')
    # 真正建立視窗，避免只檢查 import 卻忽略 Tcl/Tk 初始化失敗。
    import tkinter
    try:
        root = tkinter.Tk(); root.withdraw(); root.update(); root.destroy()
    except Exception as e:
        raise SystemExit('Tkinter 無法啟動，停止打包：' + str(e))
    manifest = {}
    for name in ('ffmpeg','ffprobe','deno'):
        p = ROOT/'tools'/name
        if not p.is_file() or not os.access(p, os.X_OK):
            raise SystemExit('請在 tools/ 放入已確認授權且可再散佈的 ' + name)
        arch = subprocess.check_output(['lipo','-archs',str(p)],text=True)
        if 'arm64' not in arch:
            raise SystemExit(name+' 不包含 arm64 架構。')
        manifest[name] = {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'arch':arch.strip()}
    if not (ROOT/'licenses/TOOLS_REVIEWED.json').exists():
        raise SystemExit('尚未整理工具授權。請依 licenses/README.md 完成 TOOLS_REVIEWED.json。')
    out = ROOT/'dist'; out.mkdir(exist_ok=True)
    run(sys.executable,ROOT/'scripts/make_icon.py')
    env = os.environ.copy()
    if args.identity:
        env['SHIBA_SIGN_IDENTITY'] = args.identity
    run(sys.executable,'-m','PyInstaller','--noconfirm','--clean',ROOT/'ShibaStudio.spec',cwd=ROOT,env=env)
    app = out/'柴犬Youtube影片備份器.app'
    run('codesign','--verify','--deep','--strict','--verbose=2',app)
    if args.notary_profile:
        with tempfile.TemporaryDirectory(prefix='shiba-notary-') as temporary:
            archive = Path(temporary)/'ShibaStudio.zip'
            run('ditto','-c','-k','--keepParent',app,archive)
            run('xcrun','notarytool','submit',archive,'--keychain-profile',args.notary_profile,'--wait')
        run('xcrun','stapler','staple',app)
        run('xcrun','stapler','validate',app)
        run('spctl','--assess','--type','execute','--verbose=2',app)
    # 不覆蓋舊成品；每次產出加上時間戳記。
    import datetime
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    label = '待公證' if args.identity else '未公證測試版'
    dmg = out/('柴犬Youtube影片備份器-0.1.0-arm64-{}-{}.dmg'.format(label,stamp))
    with tempfile.TemporaryDirectory(prefix='shiba-dmg-') as temporary:
        stage = Path(temporary)
        shutil.copytree(app,stage/app.name,symlinks=True)
        (stage/'Applications').symlink_to('/Applications')
        (stage/'安裝說明.txt').write_text(
            '請將柴犬Youtube影片備份器拖曳到 Applications 資料夾，再退出磁碟映像檔。\n'
            '此成品尚須完成安裝與實機驗證；未公證版本可能被 macOS 阻擋。\n',encoding='utf-8')
        run('hdiutil','create','-volname','柴犬Youtube影片備份器','-srcfolder',stage,'-format','UDZO',dmg)
    if args.identity:
        run('codesign','--force','--sign',args.identity,'--timestamp',dmg)
    if args.notary_profile:
        run('xcrun','notarytool','submit',dmg,'--keychain-profile',args.notary_profile,'--wait')
        run('xcrun','stapler','staple',dmg)
        run('xcrun','stapler','validate',dmg)
        run('spctl','--assess','--type','open','--context','context:primary-signature','--verbose=2',dmg)
    manifest.update({'app':str(app),'dmg':str(dmg),'notarization_requested':bool(args.notary_profile),
                     'note':'建立檔案不等於已完成啟動、下載或拖曳安裝驗證。'})
    (out/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('已建立：',app,dmg,sep='\n')


if __name__ == '__main__':
    main()
