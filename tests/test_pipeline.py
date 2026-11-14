"""以本機合成影音測試真實 FFmpeg，下載介面用測試替身。
不代表 YouTube 網路下載已驗證。
"""
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from shiba_studio import core


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), '需要 FFmpeg 與 ffprobe')
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.video = self.folder/'fixture.mp4'
        self.audio = self.folder/'fixture.m4a'
        core.run_process([core.tool('ffmpeg'),'-v','error','-f','lavfi','-i',
                          'color=c=orange:s=160x90:r=10','-t','0.3','-an','-c:v','libx264',str(self.video)])
        core.run_process([core.tool('ffmpeg'),'-v','error','-f','lavfi','-i',
                          'sine=frequency=440','-t','0.3','-vn','-c:a','aac',str(self.audio)])

    def tearDown(self):
        self.tmp.cleanup()

    def exercise(self, bad_audio=False, selected=None):
        video, audio = self.video, self.audio
        class Downloader:
            def __init__(self,opts): self.opts = opts
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def extract_info(self,url,download):
                is_video = self.opts['format']=='v'
                ext = 'mp4' if is_video else 'm4a'
                target = self.opts['outtmpl'].replace('%(ext)s',ext)
                if bad_audio and not is_video:
                    Path(target).write_bytes(b'not audio')
                else:
                    shutil.copyfile(video if is_video else audio,target)
                return {'path':target}
            def prepare_filename(self,result): return result['path']
        module = types.ModuleType('yt_dlp'); module.YoutubeDL = Downloader
        info = {'title':'測試影片','id':'BaW_jenozKc','formats':[
            {'format_id':'a','vcodec':'none','acodec':'aac','ext':'m4a','abr':128}]}
        rows = [{'id':'v','kind':'video','ext':'mp4'}, {'id':'a','kind':'audio','ext':'m4a'}]
        events=[]
        with patch.dict(sys.modules,{'yt_dlp':module}), patch.object(core,'ydl_options',return_value={}), \
             patch.object(core,'extract',return_value=(info,rows)):
            core.download('https://www.youtube.com/watch?v=BaW_jenozKc',str(self.folder),selected or ['v'],events.append)
        return events

    def test_completion_follows_real_merge_and_verification(self):
        events = self.exercise()
        result = events[-1]
        self.assertEqual(result['status'],'done')
        core.verify_output(result['outputs'][0],'video')
        stages = [e['stage'] for e in events if e['event']=='stage']
        self.assertLess(stages.index('merging'),stages.index('verifying'))
        self.assertTrue(any(e['event']=='item_done' for e in events[:-1]))

    def test_merge_failure_never_reports_done(self):
        events = self.exercise(bad_audio=True)
        self.assertEqual(events[-1]['status'],'error')
        self.assertEqual(events[-1]['outputs'],[])
        self.assertFalse(any(e['event']=='item_done' for e in events))

    def test_partial_success_keeps_valid_output(self):
        events = self.exercise(bad_audio=True,selected=['v','a'])
        self.assertEqual(events[-1]['status'],'error')
        # 再讓影片失敗但音訊有效，檢查部分成功分支。
        original = core.verify_output
        def verify(path,kind):
            if kind=='video': raise core.UserError('測試：影片驗證失敗')
            return original(path,kind)
        with patch.object(core,'verify_output',side_effect=verify):
            events = self.exercise(selected=['v','a'])
        self.assertEqual(events[-1]['status'],'partial')
        self.assertEqual(len(events[-1]['outputs']),1)
        self.assertTrue(Path(events[-1]['outputs'][0]).is_file())


if __name__=='__main__': unittest.main()
