"""階段 06 下載網址正規化追蹤、Extractor 白名單與異常中繼資料邊界測試。"""
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from shiba_studio import core


class NetworkBoundaryTests(unittest.TestCase):
    def test_ydl_options_enforces_youtube_extractor_tls_and_no_remote_ejs(self):
        with patch('shiba_studio.core.tool', side_effect=lambda name: '/usr/local/bin/' + name):
            opts = core.ydl_options(lambda e: None)
        self.assertEqual(opts['allowed_extractors'], ['youtube'])
        self.assertFalse(opts['nocheckcertificate'])
        self.assertIsNone(opts['cookiefile'])
        self.assertTrue(opts['noplaylist'])
        self.assertEqual(opts['remote_components'], set())

    def test_download_passes_only_normalized_url_to_all_yt_dlp_calls(self):
        seen_urls = []
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            audio_fixture = folder / 'sample.m4a'
            audio_fixture.write_bytes(b'fake-audio')

            class TrackingDownloader:
                def __init__(self, opts):
                    self.opts = opts
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def extract_info(self, url, download):
                    seen_urls.append((url, download))
                    if not download:
                        return {
                            'id': 'BaW_jenozKc',
                            'title': 'Demo',
                            'formats': [
                                {'format_id': '140', 'vcodec': 'none', 'acodec': 'aac',
                                 'ext': 'm4a', 'abr': 128, 'url': 'https://example.invalid/audio'}
                            ],
                        }
                    target = self.opts['outtmpl'].replace('%(ext)s', 'm4a')
                    shutil.copyfile(audio_fixture, target)
                    return {'path': target}
                def prepare_filename(self, result):
                    return result['path']

            module = types.ModuleType('yt_dlp')
            module.YoutubeDL = TrackingDownloader
            events = []
            with patch.dict(sys.modules, {'yt_dlp': module}), \
                 patch('shiba_studio.core.preflight'), \
                 patch('shiba_studio.core.ydl_options', return_value={}), \
                 patch('shiba_studio.core.verify_output'):
                core.download('https://youtu.be/BaW_jenozKc?t=42', str(folder), ['140'], events.append)

            self.assertEqual(events[-1]['status'], 'done')
            self.assertEqual(
                seen_urls,
                [
                    ('https://www.youtube.com/watch?v=BaW_jenozKc', False),
                    ('https://www.youtube.com/watch?v=BaW_jenozKc', True),
                ],
            )

    def test_format_choices_excludes_non_http_format_urls(self):
        rows = core.format_choices({
            'formats': [
                {'format_id': 'bad1', 'vcodec': 'none', 'acodec': 'aac',
                 'ext': 'm4a', 'url': 'file://local/demo'},
                {'format_id': 'bad2', 'vcodec': 'avc1', 'acodec': 'none',
                 'ext': 'mp4', 'height': 720, 'url': 'ftp://example.invalid/v.mp4'},
                {'format_id': 'good', 'vcodec': 'none', 'acodec': 'aac',
                 'ext': 'm4a', 'abr': 128, 'url': 'https://example.invalid/audio'},
            ]
        })
        self.assertEqual([r['id'] for r in rows], ['good'])


if __name__ == '__main__':
    unittest.main()