"""僅轉換輸出尺寸及 ICNS 格式，不修改原始圖示。"""
from pathlib import Path
import subprocess
import struct
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def make_icon():
    with tempfile.TemporaryDirectory(prefix='shiba-icon-') as temporary:
        iconset = Path(temporary)/'AppIcon.iconset'
        iconset.mkdir()
        for n in (16,32,128,256,512):
            for retina in (False,True):
                size = n*2 if retina else n
                name = 'icon_{}x{}{}.png'.format(n,n,'@2x' if retina else '')
                subprocess.run(['sips','-z',str(size),str(size),str(ROOT/'resources/app_icon.png'),
                                '--out',str(iconset/name)],check=True,stdout=subprocess.DEVNULL)
        output = ROOT/'resources/AppIcon.icns'
        result = subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(output)],capture_output=True)
        if result.returncode:
            # 有些受限環境的 iconutil 無法載入圖像服務。直接封裝現有 PNG；
            # 不重新繪圖或改寫像素。格式標籤對照 PIL/IcnsImagePlugin.py。
            mapping = {'ic07':'icon_128x128.png','ic08':'icon_256x256.png',
                       'ic09':'icon_512x512.png','ic10':'icon_512x512@2x.png',
                       'ic11':'icon_16x16@2x.png','ic12':'icon_32x32@2x.png',
                       'ic13':'icon_128x128@2x.png','ic14':'icon_256x256@2x.png'}
            chunks = []
            for tag,name in mapping.items():
                data = (iconset/name).read_bytes()
                chunks.append(tag.encode('ascii')+struct.pack('>I',8+len(data))+data)
            payload = b''.join(chunks)
            output.write_bytes(b'icns'+struct.pack('>I',8+len(payload))+payload)
    print('已產生 resources/AppIcon.icns')


if __name__=='__main__':
    make_icon()
