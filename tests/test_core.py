import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from shiba_studio.core import (validate_url, UserError, format_choices, publish_file,
                              check_folder, verify_output, safe_name)


class CoreTests(unittest.TestCase):
    def test_supported_urls_and_host_spoofing(self):
        expected = 'https://www.youtube.com/watch?v=BaW_jenozKc'
        for url in (expected, 'https://youtu.be/BaW_jenozKc?t=3',
                    'https://www.youtube.com/shorts/BaW_jenozKc'):
            self.assertEqual(validate_url(url), expected)
        for url in ('https://youtube.com.evil.org/watch?v=BaW_jenozKc',
                    'https://evil.org/youtube.com', 'file:///tmp/video',
                    'https://youtube.com/playlist?list=123', 'https://youtu.be/no',
                    'https://user@youtube.com/watch?v=BaW_jenozKc'):
            with self.assertRaises(UserError):
                validate_url(url)

    def test_format_rows_preserve_audio_containers_and_exclude_drm(self):
        def f(fid, v, a, ext, **kw):
            return dict(format_id=fid, vcodec=v, acodec=a, ext=ext, **kw)
        rows = format_choices({'formats': [
            f('v','avc1','none','mp4',height=1080,fps=30),
            f('a','none','aac','m4a',abr=128), f('w','none','opus','webm'),
            f('d','avc1','none','mp4',has_drm=True),
            f('s','none','none','mhtml'), f('x','vp9','none','webm')]})
        self.assertEqual({r['id'] for r in rows}, {'v','a','w'})
        self.assertEqual(rows[0]['kind'], 'video')
        self.assertEqual(rows[0]['label'], 'MP4 1080 30fps +音訊')
        self.assertEqual(next(r for r in rows if r['id']=='a')['label'], 'M4A 音訊 · 128 kbps')
        self.assertEqual(next(r for r in rows if r['id']=='w')['label'], 'WEBM 音訊 · 碼率未知')
        self.assertEqual(next(r for r in rows if r['id']=='w')['ext'], 'webm')

    def test_output_publish_never_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            src = folder/'source'; src.write_bytes(b'new')
            original = folder/'movie.mp4'; original.write_bytes(b'original')
            target = publish_file(src, folder, 'movie.mp4')
            self.assertEqual(original.read_bytes(), b'original')
            self.assertEqual(target.name, 'movie (1).mp4')
            self.assertEqual(target.read_bytes(), b'new')

    def test_folder_rejects_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'file'; p.touch()
            with self.assertRaises(UserError):
                check_folder(str(p))

    def test_verification_requires_audio_and_video_for_video_result(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'x.mp4'; p.write_bytes(b'x')
            audio_only = subprocess.CompletedProcess([],0,json.dumps({'streams':[{'codec_type':'audio'}]}),'')
            with patch('shiba_studio.core.tool',return_value='ffprobe'), patch('shiba_studio.core.run_process',return_value=audio_only):
                verify_output(p, 'audio')
                with self.assertRaises(UserError):
                    verify_output(p, 'video')
            p.write_bytes(b'')
            with self.assertRaises(UserError):
                verify_output(p, 'audio')

    def test_filename_is_safe(self):
        self.assertNotIn('/', safe_name('../../hello:world'))
        self.assertEqual(safe_name('...'), 'YouTube影片')

    def test_network_error_is_not_mistaken_for_private_video(self):
        from shiba_studio.core import friendly_error
        self.assertIn('連線失敗', friendly_error(Exception('Unable to download webpage: failed to resolve host')))

    def test_http_403_has_actionable_error(self):
        from shiba_studio.core import friendly_error
        message = friendly_error(Exception('ERROR: unable to download video data: HTTP Error 403: Forbidden'))
        self.assertIn('HTTP 403', message)
        self.assertIn('更新下載元件', message)

    def test_external_disk_without_hardlinks(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            src = folder/'source'; src.write_bytes(b'payload')
            with patch('shiba_studio.core.os.link',side_effect=OSError('not supported')):
                target = publish_file(src,folder,'output.m4a')
                second = publish_file(src,folder,'output.m4a')
            self.assertEqual(target.read_bytes(),b'payload')
            self.assertNotEqual(target,second)


if __name__ == '__main__':
    unittest.main()
