"""階段 02 檔案保全、競態清理與路徑邊界安全測試。"""
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from shiba_studio import core


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'downloads'
        self.folder.mkdir()
        self.outside = self.root / 'outside'
        self.outside.mkdir()
        self.existing = self.folder / 'keep.mp4'
        self.existing.write_bytes(b'existing-user-content')
        self.existing_hash = sha256_file(self.existing)
        self.existing_dir = self.folder / 'user_dir'
        self.existing_dir.mkdir()
        self.existing_nested = self.existing_dir / 'note.txt'
        self.existing_nested.write_bytes(b'nested-keep')
        self.nested_hash = sha256_file(self.existing_nested)

    def tearDown(self):
        self.tmp.cleanup()

    def assert_existing_untouched(self):
        self.assertTrue(self.existing.is_file())
        self.assertEqual(sha256_file(self.existing), self.existing_hash)
        self.assertTrue(self.existing_nested.is_file())
        self.assertEqual(sha256_file(self.existing_nested), self.nested_hash)

    def test_existing_numbered_files_skip_to_next_available(self):
        (self.folder / 'clip.mp4').write_bytes(b'v0')
        (self.folder / 'clip (1).mp4').write_bytes(b'v1')
        src = self.root / 'src.mp4'
        src.write_bytes(b'v2')
        target = core.publish_file(src, self.folder, 'clip.mp4')
        self.assertEqual(target.name, 'clip (2).mp4')
        self.assertEqual((self.folder / 'clip.mp4').read_bytes(), b'v0')
        self.assertEqual((self.folder / 'clip (1).mp4').read_bytes(), b'v1')
        self.assertEqual(target.read_bytes(), b'v2')
        self.assert_existing_untouched()

    def test_dangling_symlink_target_is_never_followed_or_overwritten(self):
        outside_target = self.outside / 'secret.mp4'
        dangling = self.folder / 'video.mp4'
        dangling.symlink_to(outside_target)
        src = self.root / 'src.mp4'
        src.write_bytes(b'payload')

        for link_mode in ('hardlink', 'copy'):
            if link_mode == 'hardlink':
                target = core.publish_file(src, self.folder, 'video.mp4')
                self.assertEqual(target.name, 'video (1).mp4')
            else:
                with patch('shiba_studio.core.os.link', side_effect=OSError('EXDEV')):
                    target = core.publish_file(src, self.folder, 'video.mp4')
                self.assertEqual(target.name, 'video (2).mp4')
            self.assertFalse(outside_target.exists())
        self.assert_existing_untouched()

    def test_symlink_folder_and_invalid_names_are_rejected(self):
        sym_folder = self.root / 'sym_downloads'
        sym_folder.symlink_to(self.folder)
        src = self.root / 'src.mp4'
        src.write_bytes(b'payload')
        with self.assertRaises(core.UserError):
            core.publish_file(src, sym_folder, 'ok.mp4')
        for bad_name in ('', '.', '..', '../evil.mp4', 'sub/evil.mp4'):
            with self.assertRaises(core.UserError):
                core.publish_file(src, self.folder, bad_name)
        self.assert_existing_untouched()

    def test_copy_failure_cleans_own_partial_file_only(self):
        src = self.root / 'src.mp4'
        src.write_bytes(b'payload')
        with patch('shiba_studio.core.os.link', side_effect=OSError('EXDEV')), \
             patch('shiba_studio.core.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                core.publish_file(src, self.folder, 'broken.mp4')
        self.assertFalse((self.folder / 'broken.mp4').exists())
        self.assert_existing_untouched()

    def test_copy_failure_does_not_unlink_replaced_file_in_race(self):
        src = self.root / 'src.mp4'
        src.write_bytes(b'payload')
        victim_replacement = b'replaced-by-another-process'

        def replace_and_fail(incoming, output):
            target = self.folder / 'race.mp4'
            other = self.folder / '.other_tmp'
            other.write_bytes(victim_replacement)
            os.replace(other, target)
            raise OSError('simulated copy failure after replacement')

        with patch('shiba_studio.core.os.link', side_effect=OSError('EXDEV')), \
             patch('shiba_studio.core.shutil.copyfileobj', side_effect=replace_and_fail):
            with self.assertRaises(OSError):
                core.publish_file(src, self.folder, 'race.mp4')

        target = self.folder / 'race.mp4'
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), victim_replacement)
        self.assert_existing_untouched()

    def test_cleanup_error_does_not_mask_original_error_or_touch_existing(self):
        src = self.root / 'src.mp4'
        src.write_bytes(b'payload')
        with patch('shiba_studio.core.os.link', side_effect=OSError('EXDEV')), \
             patch('shiba_studio.core.shutil.copyfileobj', side_effect=OSError('write error')), \
             patch('shiba_studio.core.os.unlink', side_effect=PermissionError('unlink denied')):
            with self.assertRaises(OSError) as ctx:
                core.publish_file(src, self.folder, 'broken2.mp4')
        self.assertIn('write error', str(ctx.exception))
        self.assert_existing_untouched()

    def test_concurrent_publish_same_name_never_overwrites(self):
        src = self.root / 'src.mp4'
        src.write_bytes(b'concurrent-data')
        results = []
        errors = []
        barrier = threading.Barrier(6)

        def worker(use_copy):
            try:
                barrier.wait(timeout=5)
                if use_copy:
                    with patch('shiba_studio.core.os.link', side_effect=OSError('EXDEV')):
                        results.append(core.publish_file(src, self.folder, 'same.mp4'))
                else:
                    results.append(core.publish_file(src, self.folder, 'same.mp4'))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i % 2 == 1,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 6)
        self.assertEqual(len(set(results)), 6)
        for p in results:
            self.assertEqual(p.read_bytes(), b'concurrent-data')
        self.assert_existing_untouched()

    def test_download_rejects_escaped_prepare_filename_and_sanitizes_ext(self):
        outside_file = self.outside / 'escaped.mp4'
        outside_file.write_bytes(b'outside-secret')
        outside_hash = sha256_file(outside_file)

        class EscapingDownloader:
            def __init__(self, opts):
                self.opts = opts
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def extract_info(self, url, download):
                return {'ext': 'mp4'}
            def prepare_filename(self, result):
                return str(outside_file)

        module = types.ModuleType('yt_dlp')
        module.YoutubeDL = EscapingDownloader
        info = {'title': '測試', 'id': 'BaW_jenozKc', 'formats': []}
        rows = [{'id': 'a', 'kind': 'audio', 'ext': '../../evil'}]
        events = []

        with patch.dict(sys.modules, {'yt_dlp': module}), \
             patch.object(core, 'ydl_options', return_value={}), \
             patch.object(core, 'extract', return_value=(info, rows)):
            core.download('https://www.youtube.com/watch?v=BaW_jenozKc',
                          str(self.folder), ['a'], events.append)

        self.assertEqual(events[-1]['status'], 'error')
        self.assertEqual(events[-1]['outputs'], [])
        self.assertEqual(sha256_file(outside_file), outside_hash)
        self.assertEqual(core.safe_ext('../../evil.m4a'), 'evilm4a')
        self.assertEqual(core.safe_ext('...'), 'bin')
        self.assert_existing_untouched()


if __name__ == '__main__':
    unittest.main()
