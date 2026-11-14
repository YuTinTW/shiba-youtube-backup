import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from shiba_studio.gui import command_edit


class EditShortcutTests(unittest.TestCase):
    def test_chinese_input_keys_use_physical_key(self):
        for code, action in ((0, '<<SelectAll>>'), (8, '<<Copy>>'),
                             (9, '<<Paste>>'), (7, '<<Cut>>')):
            with self.subTest(code=code):
                widget = Mock()
                event = SimpleNamespace(keysym='??', keycode=(code << 24) | 0x3105,
                                        widget=widget)
                self.assertEqual(command_edit(event), 'break')
                widget.event_generate.assert_called_once_with(action)

    def test_english_shortcut_dispatches_once(self):
        widget = Mock()
        event = SimpleNamespace(keysym='V', keycode=9, widget=widget)
        self.assertEqual(command_edit(event), 'break')
        widget.event_generate.assert_called_once_with('<<Paste>>')

    def test_other_command_keys_pass_through(self):
        widget = Mock()
        event = SimpleNamespace(keysym='q', keycode=(12 << 24) | ord('q'), widget=widget)
        self.assertIsNone(command_edit(event))
        widget.event_generate.assert_not_called()
