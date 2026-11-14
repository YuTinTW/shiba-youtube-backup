import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from shiba_studio.gui import Studio


class ScrollTests(unittest.TestCase):
    def setup_view(self):
        holder = SimpleNamespace(master=None)
        child = SimpleNamespace(master=SimpleNamespace(master=holder))
        canvas = Mock()
        canvas.yview.return_value = (0.0, 0.5)
        view = SimpleNamespace(format_holder=holder, canvas=canvas,
                               winfo_containing=Mock(return_value=child), tk=Mock())
        view.tk.call.return_value = 'aqua'
        return view

    def test_scroll_over_nested_option_and_both_directions(self):
        view = self.setup_view()
        for delta, expected in ((2, -2), (-3, 3)):
            event = SimpleNamespace(x_root=100, y_root=200, delta=delta)
            self.assertEqual(Studio.scroll_formats(view, event), 'break')
            view.canvas.yview_scroll.assert_called_with(expected, 'units')

    def test_outside_list_or_zero_delta_does_not_scroll(self):
        view = self.setup_view()
        event = SimpleNamespace(x_root=100, y_root=200, delta=0)
        self.assertIsNone(Studio.scroll_formats(view, event))
        event.delta = 1
        view.winfo_containing.return_value = SimpleNamespace(master=None)
        self.assertIsNone(Studio.scroll_formats(view, event))
        view.canvas.yview_scroll.assert_not_called()

    def test_short_list_does_not_move(self):
        view = self.setup_view()
        view.canvas.yview.return_value = (0.0, 1.0)
        event = SimpleNamespace(x_root=100, y_root=200, delta=-2)
        self.assertIsNone(Studio.scroll_formats(view, event))
        view.canvas.yview_scroll.assert_not_called()
