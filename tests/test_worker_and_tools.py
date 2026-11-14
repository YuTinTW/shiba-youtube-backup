"""階段 03 外部工具邊界、參數陣列、Worker 請求與 GUI 事件驗證測試。"""
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import app as app_entry
from shiba_studio import core, gui


class FakeVar:
    def __init__(self, value=''):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class FakeProgress:
    def __init__(self):
        self.stopped = 0
        self.config = {}
    def stop(self):
        self.stopped += 1
    def configure(self, **kw):
        self.config.update(kw)
    def start(self, interval):
        pass


class FakeShiba:
    def __init__(self):
        self.states = []
    def set_state(self, s):
        self.states.append(s)


class FakeStudio:
    """不啟動真實 Tk 視窗，僅驗證 Studio.poll / Studio.handle 控制流。"""
    def __init__(self, log_path):
        self.events = queue.Queue()
        self.process = object()
        self.busy = True
        self.got_terminal = False
        self.loaded_url = ''
        self.choices = []
        self.title_text = FakeVar()
        self.status = FakeVar()
        self.detail = FakeVar()
        self.progress_text = FakeVar()
        self.progress = FakeProgress()
        self.shiba = FakeShiba()
        self.log_path = log_path
        self.after_calls = []

    def after(self, ms, fn):
        self.after_calls.append((ms, fn))

    def lock(self, busy):
        self.busy = busy

    def fail(self, text):
        gui.Studio.fail(self, text)

    def activity(self, text):
        self.progress.start(90)
        self.progress_text.set(text)

    def handle(self, e):
        return gui.Studio.handle(self, e)

    def poll(self):
        return gui.Studio.poll(self)


class WorkerAndToolsTests(unittest.TestCase):
    def test_tool_rejects_unlisted_and_frozen_never_falls_back_to_path(self):
        with self.assertRaises(core.UserError):
            core.tool('curl')
        with tempfile.TemporaryDirectory() as d:
            with patch.object(sys, 'frozen', True, create=True), \
                 patch.object(sys, '_MEIPASS', d, create=True), \
                 patch('shiba_studio.core.shutil.which', return_value='/usr/bin/ffmpeg'):
                with self.assertRaises(core.UserError):
                    core.tool('ffmpeg')

    def test_run_process_preserves_arg_array_with_spaces_chinese_quotes_and_dash(self):
        with tempfile.TemporaryDirectory() as d:
            special = Path(d) / '-中文 "檔名" $(id).txt'
            special.write_text('ok', encoding='utf-8')
            res = core.run_process([sys.executable, '-c',
                                    'import sys; print(sys.argv[1])', str(special)])
            self.assertEqual(res.stdout.strip(), str(special))

    def test_run_process_timeout_and_nonzero_exit_raise_user_error(self):
        with patch('shiba_studio.core.subprocess.run',
                   side_effect=subprocess.TimeoutExpired(['x'], 1)):
            with self.assertRaises(core.UserError):
                core.run_process(['x'], timeout=1)
        with patch('shiba_studio.core.subprocess.run',
                   side_effect=subprocess.CalledProcessError(2, ['x'])):
            with self.assertRaises(core.UserError):
                core.run_process(['x'])

    def test_verify_output_resolves_leading_dash_filename(self):
        with tempfile.TemporaryDirectory() as d:
            old_cwd = os.getcwd()
            try:
                os.chdir(d)
                dash_file = Path('-evil.mp4')
                dash_file.write_bytes(b'data')
                ok_res = subprocess.CompletedProcess(
                    [], 0, json.dumps({'streams': [{'codec_type': 'audio'}]}), '')
                with patch('shiba_studio.core.tool', return_value='ffprobe'), \
                     patch('shiba_studio.core.run_process', return_value=ok_res) as mocked:
                    core.verify_output('-evil.mp4', 'audio')
                passed_arg = mocked.call_args[0][0][-1]
                self.assertTrue(os.path.isabs(passed_arg))
                self.assertFalse(passed_arg.startswith('-'))
            finally:
                os.chdir(old_cwd)

    def test_worker_request_rejects_malformed_and_oversized_inputs(self):
        bad_inputs = [
            '',
            'not-json',
            '[]',
            '123',
            json.dumps({'action': 'shell', 'url': 'https://youtu.be/BaW_jenozKc'}),
            json.dumps({'action': 'read', 'url': 123}),
            json.dumps({'action': 'read', 'url': 'https://youtu.be/' + 'a' * 3000}),
            json.dumps({'action': 'download', 'url': 'https://youtu.be/BaW_jenozKc',
                        'folder': 123, 'selected': ['1']}),
            json.dumps({'action': 'download', 'url': 'https://youtu.be/BaW_jenozKc',
                        'folder': '/tmp', 'selected': []}),
            json.dumps({'action': 'download', 'url': 'https://youtu.be/BaW_jenozKc',
                        'folder': '/tmp', 'selected': [1]}),
            '{' + '"a":"' + ('x' * (app_entry.MAX_WORKER_REQUEST_BYTES + 10)) + '"}',
        ]
        for raw in bad_inputs:
            out = io.StringIO()
            rc = app_entry.run_worker(stdin=io.StringIO(raw + '\n'), stdout=out)
            self.assertEqual(rc, 1)
            events = [json.loads(line) for line in out.getvalue().strip().splitlines()]
            self.assertEqual(events[-1]['event'], 'error')

    def test_worker_env_strips_injection_vars_when_frozen(self):
        base = {
            'PATH': '/usr/bin',
            'PYTHONPATH': '/tmp/evil',
            'PYTHONHOME': '/tmp/evil_home',
            'PYTHONSTARTUP': '/tmp/evil_startup.py',
            'DYLD_INSERT_LIBRARIES': '/tmp/evil.dylib',
            'SSL_CERT_FILE': '/etc/ssl/cert.pem',
        }
        frozen_env = gui.worker_env(base, frozen=True)
        self.assertNotIn('PYTHONPATH', frozen_env)
        self.assertNotIn('PYTHONHOME', frozen_env)
        self.assertNotIn('PYTHONSTARTUP', frozen_env)
        self.assertNotIn('DYLD_INSERT_LIBRARIES', frozen_env)
        self.assertEqual(frozen_env['SSL_CERT_FILE'], '/etc/ssl/cert.pem')
        self.assertEqual(frozen_env['PATH'], '/usr/bin')

    def test_gui_poll_survives_malformed_and_unknown_events_and_unlocks_on_exit(self):
        with tempfile.TemporaryDirectory() as d:
            studio = FakeStudio(Path(d) / 'diag.log')
            studio.events.put('not-a-dict')
            studio.events.put({'event': 'unknown_event', 'foo': 'bar'})
            studio.events.put({'event': 'stage', 'text': 123})
            studio.events.put({'event': 'progress', 'text': 'ok', 'percent': 'bad', 'bytes': 'bad'})
            studio.events.put({'event': 'formats', 'title': 1, 'url': None, 'choices': 'bad'})
            studio.events.put({'event': 'result', 'status': 'done', 'outputs': 'bad', 'errors': []})
            studio.events.put({'event': 'worker_exit', 'code': 1})
            studio.poll()
            self.assertEqual(len(studio.after_calls), 1)
            self.assertFalse(studio.busy)
            self.assertEqual(studio.status.get(), '無法完成')


if __name__ == '__main__':
    unittest.main()
