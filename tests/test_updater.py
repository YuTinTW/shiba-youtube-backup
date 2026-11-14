"""階段 04 下載元件更新切換、恢復、互斥鎖與可追溯性測試（隔離目錄執行）。"""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from shiba_studio import updater


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runtime = self.root / '.runtime-packages'
        self.runtime.mkdir()
        (self.runtime / 'marker.txt').write_text('original-v1', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def _ok_pip(self, python_exe, staging_dir, package_spec, allow_pre=False, extra_args=()):
        (staging_dir / 'yt_dlp').mkdir(parents=True, exist_ok=True)
        (staging_dir / 'yt_dlp' / '__init__.py').write_text('# new', encoding='utf-8')
        dist = staging_dir / 'yt_dlp-2026.11.10.dist-info'
        dist.mkdir(parents=True, exist_ok=True)
        (dist / 'RECORD').write_text('yt_dlp/__init__.py,sha256=abc,5\n', encoding='utf-8')
        return subprocess.CompletedProcess([], 0)

    def _ok_verify(self, python_exe, staging_dir):
        return {'yt_dlp': '2026.11.10', 'dists': {'yt-dlp': '2026.11.10', 'yt-dlp-ejs': '0.8.0'}}

    def test_pip_failure_leaves_original_untouched_and_cleans_staging(self):
        def fail_pip(*args, **kwargs):
            return subprocess.CompletedProcess([], 1)

        with self.assertRaises(updater.UpdateError):
            updater.update_runtime_packages(
                self.root, pip_runner=fail_pip, verify_runner=self._ok_verify)

        self.assertEqual((self.runtime / 'marker.txt').read_text(encoding='utf-8'), 'original-v1')
        self.assertEqual([p for p in self.root.glob('.runtime-update.*') if p.is_dir()], [])

    def test_verify_failure_never_activates_staging(self):
        def fail_verify(python_exe, staging_dir):
            raise updater.UpdateError('新元件匯入檢查失敗')

        with self.assertRaises(updater.UpdateError):
            updater.update_runtime_packages(
                self.root, pip_runner=self._ok_pip, verify_runner=fail_verify)

        self.assertEqual((self.runtime / 'marker.txt').read_text(encoding='utf-8'), 'original-v1')
        self.assertEqual([p for p in self.root.glob('.runtime-update.*') if p.is_dir()], [])

    def test_backup_failure_leaves_original_untouched(self):
        def fail_backup_move(src, dst):
            raise OSError('backup move denied')

        with self.assertRaises(updater.UpdateError):
            updater.update_runtime_packages(
                self.root, pip_runner=self._ok_pip, verify_runner=self._ok_verify,
                mover=fail_backup_move)

        self.assertEqual((self.runtime / 'marker.txt').read_text(encoding='utf-8'), 'original-v1')
        self.assertEqual([p for p in self.root.glob('.runtime-update.*') if p.is_dir()], [])

    def test_switch_failure_restores_original_packages(self):
        calls = []

        def flaky_move(src, dst):
            calls.append((Path(src), Path(dst)))
            if len(calls) == 2:
                raise OSError('switch failed')
            shutil.move(str(src), str(dst))

        with self.assertRaises(updater.UpdateError) as ctx:
            updater.update_runtime_packages(
                self.root, pip_runner=self._ok_pip, verify_runner=self._ok_verify,
                mover=flaky_move)

        self.assertIn('已還原原有元件', str(ctx.exception))
        self.assertEqual((self.runtime / 'marker.txt').read_text(encoding='utf-8'), 'original-v1')
        self.assertEqual([p for p in self.root.glob('.runtime-update.*') if p.is_dir()], [])

    def test_switch_and_restore_failure_preserves_backup_and_reports_path(self):
        calls = []

        def double_fail_move(src, dst):
            calls.append((Path(src), Path(dst)))
            if len(calls) == 1:
                shutil.move(str(src), str(dst))
                return
            raise OSError('disk error during switch and restore')

        with self.assertRaises(updater.UpdateError) as ctx:
            updater.update_runtime_packages(
                self.root, pip_runner=self._ok_pip, verify_runner=self._ok_verify,
                mover=double_fail_move)

        msg = str(ctx.exception)
        self.assertIn('手動將', msg)
        backups = list(self.root.glob('.runtime-backup.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'packages' / 'marker.txt').read_text(encoding='utf-8'),
                         'original-v1')

    def test_concurrent_update_lock_rejects_second_updater(self):
        lock_path = self.root / '.runtime-update.lock'
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(updater.UpdateError) as ctx:
                updater.update_runtime_packages(
                    self.root, pip_runner=self._ok_pip, verify_runner=self._ok_verify)
            self.assertIn('另一個更新程序', str(ctx.exception))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_successful_update_writes_manifest_and_defaults_to_stable_policy(self):
        old_backup = self.root / '.runtime-backup.old'
        old_backup.mkdir()
        captured = {}

        def record_pip(python_exe, staging_dir, package_spec, allow_pre=False, extra_args=()):
            captured['allow_pre'] = allow_pre
            captured['package_spec'] = package_spec
            return self._ok_pip(python_exe, staging_dir, package_spec, allow_pre, extra_args)

        res = updater.update_runtime_packages(
            self.root, pip_runner=record_pip, verify_runner=self._ok_verify)

        self.assertFalse(captured['allow_pre'])
        self.assertEqual(captured['package_spec'], updater.DEFAULT_PACKAGE)
        self.assertEqual(res['status'], 'updated')
        manifest_file = self.runtime / '.update-manifest.json'
        self.assertTrue(manifest_file.is_file())
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        self.assertEqual(manifest['versions']['yt_dlp'], '2026.11.10')
        self.assertIn('yt_dlp-2026.11.10.dist-info', manifest['dist_record_sha256'])
        self.assertFalse(old_backup.exists())
        self.assertEqual(len(list(self.root.glob('.runtime-backup.*'))), 1)


if __name__ == '__main__':
    unittest.main()
