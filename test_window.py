"""Run on Windows with a desktop session: python -m unittest test_window -v."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.patch.start()
        self.window = app.App()
        self.window.stop.set()
        self.window.root.update()

    def tearDown(self):
        self.window.close()
        self.patch.stop()
        self.temp.cleanup()

    def test_edit_mode_restores_transparency_and_clickthrough_preference(self):
        w = self.window
        w.config.update(transparent=True, clickthrough=True, opacity=0.42)
        w.set_editing(True)
        self.assertTrue(w.lyric.overrideredirect())
        self.assertEqual(w.move_handle.winfo_manager(), 'place')
        self.assertEqual(w.resize_handle.winfo_manager(), 'place')
        self.assertEqual(w.lyric.attributes('-transparentcolor'), w.config['background'])
        self.assertAlmostEqual(w.lyric.attributes('-alpha'), 1)
        self.assertEqual(w.edit_button.cget('text'), '完成调整')
        w.set_editing(False)
        self.assertEqual(w.move_handle.winfo_manager(), '')
        self.assertEqual(w.resize_handle.winfo_manager(), '')
        self.assertTrue(w.lyric.overrideredirect())
        self.assertEqual(w.lyric.attributes('-transparentcolor'), w.config['background'])
        self.assertAlmostEqual(w.lyric.attributes('-alpha'), 0.42, places=2)
        self.assertTrue(w.config['clickthrough'])

    def test_move_resize_persists_and_font_zoom_changes_actual_font(self):
        w = self.window
        w.set_editing(True)
        w.root.update()
        time.sleep(0.15)
        w.root.update()
        w.lyric.geometry('700x210+90+110')
        w.root.update()
        time.sleep(0.15)
        w.root.update()
        w.save_geometry()
        stored = json.loads((app.DATA / 'settings.json').read_text(encoding='utf-8'))
        self.assertTrue(stored['geometry'].startswith('700x210'))
        self.assertIn('+90+110', stored['geometry'])
        previous = round(w.config['font_size'])
        w.zoom_font(SimpleNamespace(delta=120))
        self.assertEqual(w.config['font_size'], previous+2)
        self.assertEqual(w.variables['font_size'].get(), previous+2)
        self.assertIn(str(previous+2), w.line.cget('font'))

    def test_custom_resize_handle(self):
        w = self.window
        w.set_editing(True)
        w.root.update()
        width, height = w.lyric.winfo_width(), w.lyric.winfo_height()
        w.resize_start(SimpleNamespace(x_root=100, y_root=100))
        self.assertEqual(w.resize_move(SimpleNamespace(x_root=150, y_root=130)), 'break')
        w.root.update()
        self.assertEqual(w.lyric.winfo_width(), width+50)
        self.assertEqual(w.lyric.winfo_height(), height+30)


if __name__ == '__main__':
    unittest.main()
