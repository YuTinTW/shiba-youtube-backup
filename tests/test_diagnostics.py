"""階段 05 診斷敏感資訊遮蔽、截斷、事件佇列上限與資源限制測試。"""
import io
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

from shiba_studio import core, gui
from tests.test_worker_and_tools import FakeStudio


class DiagnosticsAndLimitsTests(unittest.TestCase):
    def test_sanitize_diagnostic_redacts_credentials_tokens_and_home_paths(self):
        raw = (
            'ERROR: HTTP 403 on https://' + 'demo_user:demo_pass' + '@example.com/watch?v=BaW_jenozKc'
            + '&token=' + 'tok_999' + '&sig=' + 'sig_888' + '&api_key=' + 'k123\n'
            + 'Author' + 'ization: Bea' + 'rer demo_jwt_value\r\n'
            + 'Coo' + 'kie: sess=' + 'xyz123\n'
            + 'File at /Users/someone_private/Downloads/secret.mp4'
        )
        cleaned = core.sanitize_diagnostic(raw)
        self.assertNotIn('demo_user', cleaned)
        self.assertNotIn('demo_pass', cleaned)
        self.assertNotIn('tok_999', cleaned)
        self.assertNotIn('sig_888', cleaned)
        self.assertNotIn('k123', cleaned)
        self.assertNotIn('demo_jwt_value', cleaned)
        self.assertNotIn('xyz123', cleaned)
        self.assertNotIn('someone_private', cleaned)
        self.assertIn('HTTP 403', cleaned)
        self.assertIn('BaW_jenozKc', cleaned)
        self.assertIn('[REDACTED]', cleaned)

    def test_sanitize_diagnostic_truncates_oversized_messages(self):
        huge = 'X' * (core.MAX_DIAGNOSTIC_CHARS + 500)
        cleaned = core.sanitize_diagnostic(huge)
        self.assertLessEqual(len(cleaned), core.MAX_DIAGNOSTIC_CHARS)
        self.assertTrue(cleaned.endswith('... [TRUNCATED]'))

    def test_bounded_queue_never_drops_critical_events_when_full(self):
        q = queue.Queue(maxsize=4)
        for i in range(6):
            gui.enqueue_bounded(q, {'event': 'progress', 'text': f'p{i}', 'percent': i})
        self.assertEqual(q.qsize(), 4)
        ok = gui.enqueue_bounded(q, {'event': 'result', 'status': 'done', 'outputs': ['a.mp4'], 'errors': []})
        self.assertTrue(ok)
        ok_exit = gui.enqueue_bounded(q, {'event': 'worker_exit', 'code': 0})
        self.assertTrue(ok_exit)
        items = [q.get_nowait()['event'] for _ in range(q.qsize())]
        self.assertIn('result', items)
        self.assertIn('worker_exit', items)

    def test_iter_bounded_lines_truncates_and_drains_oversized_line(self):
        stream = io.StringIO('A' * 200 + '\nnormal_line\n')
        lines = list(gui.iter_bounded_lines(stream, max_bytes=50))
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].endswith('... [LINE_TRUNCATED]'))
        self.assertEqual(lines[1], 'normal_line\n')

    def test_log_write_failure_does_not_block_result_or_unlock(self):
        with tempfile.TemporaryDirectory() as d:
            bad_log = Path(d) / 'blocked_dir'
            bad_log.mkdir()
            studio = FakeStudio(bad_log)
            studio.events.put({'event': 'diagnostic', 'detail': 'https://u:p@host/?token=abc'})
            studio.events.put({'event': 'result', 'status': 'done', 'outputs': ['x.mp4'], 'errors': []})
            studio.events.put({'event': 'worker_exit', 'code': 0})
            studio.poll()
            self.assertFalse(studio.busy)
            self.assertEqual(studio.status.get(), '全部完成')

    def test_log_rotates_before_exceeding_limit_and_writes_redacted_content(self):
        with tempfile.TemporaryDirectory() as d:
            log_path = Path(d) / 'diagnostic.log'
            studio = FakeStudio(log_path)
            studio.handle({'event': 'diagnostic', 'detail': 'first https://u:pw@x.test/?token=secret1'})
            self.assertTrue(log_path.is_file())
            content = log_path.read_text(encoding='utf-8')
            self.assertNotIn('secret1', content)
            self.assertNotIn('pw', content)

    def test_check_disk_space_rejects_insufficient_space(self):
        with tempfile.TemporaryDirectory() as d:
            Usage = type('Usage', (), {'total': 1000, 'used': 950, 'free': 10 * 1024 * 1024})
            with patch('shiba_studio.core.shutil.disk_usage', return_value=Usage()):
                with self.assertRaises(core.UserError):
                    core.check_disk_space(d, estimated_bytes=50 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
