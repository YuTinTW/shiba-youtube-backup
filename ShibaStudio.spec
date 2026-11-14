# PyInstaller 設定：使用目前目錄為專案根目錄。
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root = Path(SPECPATH)
datas, binaries, hiddenimports = collect_all('yt_dlp')
ejs_data, ejs_bin, ejs_import = collect_all('yt_dlp_ejs')
datas += ejs_data + [(str(root / 'resources'), 'resources'), (str(root / 'licenses'), 'licenses')]
binaries += ejs_bin + [(str(root/'tools'/name), 'tools') for name in ('ffmpeg','ffprobe','deno')]
hiddenimports += ejs_import
identity = os.environ.get('SHIBA_SIGN_IDENTITY') or None
a = Analysis([str(root/'app.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, excludes=['pytest','IPython','numpy','PIL'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ShibaStudio', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          argv_emulation=False, target_arch='arm64', codesign_identity=identity,
          entitlements_file=str(root/'resources/entitlements.plist') if identity else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ShibaStudio')
app = BUNDLE(coll, name='柴犬Youtube影片備份器.app', icon=str(root/'resources/AppIcon.icns'),
             bundle_identifier='local.shibastudio.desktop',
             info_plist={'CFBundleShortVersionString':'0.1.0','CFBundleVersion':'1',
                         'LSMinimumSystemVersion':'26.0','NSHighResolutionCapable':True,
                         'NSHumanReadableCopyright':'Third-party notices: licenses/'})
