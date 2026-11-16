"""QQ phone → Windows lyrics, without a phone APK or third-party Python packages."""
import ctypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from core import Playback, adb_run, devices, fetch_lyrics, line_at, locate_adb, parse_lrc, sample

DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'QQPhoneLyrics'
DEFAULTS = dict(color='#72e6d3', secondary='#b8c6d9', background='#111827',
                opacity=0.92, font_size=30, transparent=True, topmost=True,
                clickthrough=False, direct_lyrics=False, offset=0.0, adb='', geometry='960x150+200+650')


class App:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.config = DEFAULTS.copy()
        try:
            self.config.update(json.loads((DATA / 'settings.json').read_text(encoding='utf-8')))
        except (OSError, ValueError):
            pass
        self.root = tk.Tk()
        self.root.title('手机 QQ · 桌面歌词控制台')
        self.root.geometry('650x740')
        self.root.minsize(590, 630)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.playback = None
        self.key = None
        self.generation = 0
        self.rows = []
        self.serial = ''
        self.demo = False
        self.editing = False
        self.save_timer = None
        self.last_line = None
        self.lyric = tk.Toplevel(self.root)
        self.lyric.title('拖动标题栏移动歌词 · 拖动边框缩放 · 完成后点击控制台「完成调整」')
        self.lyric.minsize(300, 100)
        self.lyric.overrideredirect(True)
        try:
            self.lyric.geometry(self.config['geometry'])
        except tk.TclError:
            self.lyric.geometry(DEFAULTS['geometry'])
        self.line = tk.Label(self.lyric, text='手机 QQ · 等待连接', anchor='center', wraplength=920)
        self.line.pack(expand=True, fill='both', padx=12)
        self.next_line = tk.Label(self.lyric, text='拖动歌词移动位置 · 右键打开控制台', anchor='center')
        self.next_line.pack(fill='x', pady=(0, 10))
        self.move_handle = tk.Label(self.lyric, text='✥ 拖动', cursor='fleur', font=('Microsoft YaHei UI', 10))
        self.move_handle.bind('<ButtonPress-1>', self.drag_start)
        self.move_handle.bind('<B1-Motion>', self.drag_move)
        self.resize_handle = tk.Label(self.lyric, text='↘', cursor='size_nw_se', font=('Microsoft YaHei UI', 16, 'bold'))
        self.resize_handle.bind('<ButtonPress-1>', self.resize_start)
        self.resize_handle.bind('<B1-Motion>', self.resize_move)
        for widget in (self.lyric, self.line, self.next_line):
            widget.bind('<ButtonPress-1>', self.drag_start)
            widget.bind('<B1-Motion>', self.drag_move)
            widget.bind('<Button-3>', lambda e: self.show())
            widget.bind('<Control-MouseWheel>', self.zoom_font)
        self.lyric.bind('<Configure>', self.on_geometry)
        self.build_controls()
        self.apply()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.tick)
        threading.Thread(target=self.poll, daemon=True).start()

    def build_controls(self):
        panel = ttk.Frame(self.root, padding=18)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='手机播放，歌词留在桌面', font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='USB / 无线 ADB · 手机无需安装 App', foreground='#526174').pack(anchor='w', pady=(4, 14))
        self.status = tk.StringVar(value='正在检查 ADB…')
        ttk.Label(panel, textvariable=self.status, wraplength=590).pack(anchor='w', pady=4)
        self.song_text = tk.StringVar(value='尚未读取到 QQ 音乐播放信息')
        ttk.Label(panel, textvariable=self.song_text, wraplength=590).pack(anchor='w', pady=4)
        self.source_text = tk.StringVar(value='歌词源：QQ 音乐优先，网易云备用；可加载本地 LRC')
        ttk.Label(panel, textvariable=self.source_text, wraplength=590).pack(anchor='w', pady=4)
        row = ttk.Frame(panel); row.pack(fill='x', pady=8)
        ttk.Button(row, text='选择 adb.exe', command=self.choose_adb).pack(side='left')
        ttk.Button(row, text='无线连接', command=self.wireless).pack(side='left', padx=6)
        ttk.Button(row, text='预览效果', command=self.toggle_demo).pack(side='left')
        self.edit_button = ttk.Button(row, text='调整位置和大小', command=lambda: self.set_editing(not self.editing))
        self.edit_button.pack(side='left', padx=6)
        ttk.Separator(panel).pack(fill='x', pady=10)
        colors = ttk.Frame(panel); colors.pack(fill='x')
        for text, key in [('歌词颜色', 'color'), ('下一句颜色', 'secondary'), ('背景颜色', 'background')]:
            ttk.Button(colors, text=text, command=lambda k=key: self.choose_color(k)).pack(side='left', padx=(0, 8))
        self.variables = {}
        self.scale_labels = {}
        for label, key, low, high in [('整体透明度（文字与背景）', 'opacity', 0.15, 1), ('字号', 'font_size', 16, 72),
                                      ('同步偏移（秒，正数让歌词提前）', 'offset', -10, 10)]:
            frame = ttk.Frame(panel); frame.pack(fill='x', pady=7)
            ttk.Label(frame, text=label).pack(anchor='w')
            var = tk.DoubleVar(value=self.config[key]); self.variables[key] = var
            value = ttk.Label(frame, width=7); value.pack(side='right')
            self.scale_labels[key] = value
            def update(v, k=key, variable=var, target=value):
                self.config[k] = variable.get(); target.configure(text=f'{variable.get():.2f}'); self.apply()
            ttk.Scale(frame, from_=low, to=high, variable=var, command=update).pack(fill='x', expand=True)
            value.configure(text=f'{var.get():.2f}')
        for text, key in [('直接显示手机通知歌词（QQ 音乐需开启通知栏歌词）', 'direct_lyrics'),
                           ('背景完全透明（只留下歌词）', 'transparent'), ('歌词始终置顶', 'topmost'),
                           ('鼠标穿透（在此处取消；也可按 Ctrl+Alt+L 恢复）', 'clickthrough')]:
            var = tk.BooleanVar(value=self.config[key]); self.variables[key] = var
            ttk.Checkbutton(panel, text=text, variable=var,
                            command=lambda k=key, v=var: self.set_option(k, v.get())).pack(anchor='w', pady=4)
        row = ttk.Frame(panel); row.pack(fill='x', pady=12)
        ttk.Button(row, text='加载本地 LRC', command=self.load_lrc).pack(side='left')
        ttk.Button(row, text='重新匹配歌词', command=self.retry).pack(side='left', padx=8)
        ttk.Button(row, text='恢复歌词位置', command=lambda: self.lyric.geometry(DEFAULTS['geometry'])).pack(side='left')
        ttk.Label(panel, text='调整位置和大小：点击上方按钮 → 左上角拖动、右下角缩放 → 完成调整。\n'
                  'Ctrl + 鼠标滚轮调整字号，也可使用字号滑块。Ctrl+Alt+L 进入调整模式。\n'
                  '设置自动保存，关闭控制台会退出程序。',
                  wraplength=590, foreground='#526174').pack(anchor='w', pady=8)
        if os.name == 'nt':
            self.hotkey_ok = bool(ctypes.windll.user32.RegisterHotKey(None, 1, 0x0001 | 0x0002 | 0x4000, ord('L')))
            if not self.hotkey_ok:
                self.status.set('Ctrl+Alt+L 被其他程序占用；请从控制台取消穿透。')

    def show(self):
        self.root.deiconify(); self.root.lift()

    def set_editing(self, enabled):
        self.editing = bool(enabled)
        # Stay frameless in both modes: native Windows chrome cannot be color-keyed.
        self.lyric.overrideredirect(True)
        if self.editing:
            self.move_handle.place(x=8, y=2)
            self.resize_handle.place(relx=1, rely=1, x=-6, y=-2, anchor='se')
        else:
            self.move_handle.place_forget()
            self.resize_handle.place_forget()
        self.edit_button.configure(text='完成调整' if self.editing else '调整位置和大小')
        self.apply()
        self.lyric.deiconify(); self.lyric.lift()

    def on_geometry(self, event):
        if event.widget != self.lyric:
            return
        width = max(100, event.width - 24)
        self.line.configure(wraplength=width)
        self.next_line.configure(wraplength=width)
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(300, self.save_geometry)

    def save_geometry(self):
        self.save_timer = None
        self.save()

    def zoom_font(self, event):
        size = max(16, min(72, round(self.config['font_size']) + (2 if event.delta > 0 else -2)))
        self.config['font_size'] = size
        self.variables['font_size'].set(size)
        self.scale_labels['font_size'].configure(text=f'{size:.2f}')
        self.apply()
        return 'break'

    def set_option(self, key, value):
        self.config[key] = value
        if key == 'direct_lyrics':
            self.generation += 1; self.key = None; self.rows = []; self.last_line = None
            self.demo = False
        self.apply()

    def apply(self):
        c = self.config
        self.lyric.configure(bg=c['background'])
        self.line.configure(bg=c['background'], fg=c['color'], font=('Microsoft YaHei UI', int(c['font_size']), 'bold'))
        self.next_line.configure(bg=c['background'], fg=c['secondary'], font=('Microsoft YaHei UI', max(12, int(c['font_size']*.53))))
        self.move_handle.configure(bg=c['background'], fg=c['secondary'])
        self.resize_handle.configure(bg=c['background'], fg=c['secondary'])
        self.lyric.attributes('-alpha', 1.0 if self.editing else float(c['opacity']))
        self.lyric.attributes('-topmost', bool(c['topmost']))
        if os.name == 'nt':
            self.lyric.attributes('-transparentcolor', c['background'] if c['transparent'] else '')
            self.lyric.update_idletasks()
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [ctypes.c_void_p]; user32.GetParent.restype = ctypes.c_void_p
            hwnd = user32.GetParent(self.lyric.winfo_id())
            getstyle = user32.GetWindowLongPtrW; getstyle.argtypes = [ctypes.c_void_p, ctypes.c_int]; getstyle.restype = ctypes.c_ssize_t
            setstyle = user32.SetWindowLongPtrW; setstyle.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]; setstyle.restype = ctypes.c_ssize_t
            style = getstyle(hwnd, -20)
            style = style | 0x20 if c['clickthrough'] and not self.editing else style & ~0x20
            setstyle(hwnd, -20, style)
        self.save()

    def save(self):
        self.config['geometry'] = self.lyric.geometry()
        (DATA / 'settings.json').write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding='utf-8')

    def drag_start(self, event):
        self.drag = (event.x_root, event.y_root, self.lyric.winfo_x(), self.lyric.winfo_y())
        return 'break'

    def drag_move(self, event):
        x, y, ox, oy = self.drag
        self.lyric.geometry(f'+{max(0, ox+event.x_root-x)}+{max(0, oy+event.y_root-y)}')
        return 'break'

    def resize_start(self, event):
        self.resize_origin = (event.x_root, event.y_root, self.lyric.winfo_width(), self.lyric.winfo_height())
        return 'break'

    def resize_move(self, event):
        x, y, width, height = self.resize_origin
        width = max(300, width + event.x_root - x)
        height = max(100, height + event.y_root - y)
        self.lyric.geometry(f'{width}x{height}')
        return 'break'

    def choose_color(self, key):
        chosen = colorchooser.askcolor(self.config[key], parent=self.root)[1]
        if chosen:
            self.config[key] = chosen; self.apply()

    def choose_adb(self):
        path = filedialog.askopenfilename(title='选择 Android platform-tools 中的 adb.exe', filetypes=[('ADB', 'adb.exe')])
        if path:
            self.config['adb'] = path; self.save()

    def wireless(self):
        win = tk.Toplevel(self.root); win.title('Android 无线调试'); win.geometry('520x300')
        ttk.Label(win, text='手机「开发者选项 → 无线调试」\n先用配对页面地址和配对码配对，再用无线调试主页地址连接。\n两个端口通常不同；手机和电脑须在同一局域网。', wraplength=480).pack(pady=12)
        address = tk.StringVar(); code = tk.StringVar()
        ttk.Label(win, text='IP:端口').pack(); ttk.Entry(win, textvariable=address, width=40).pack()
        ttk.Label(win, text='配对码（仅配对时填写）').pack(); ttk.Entry(win, textvariable=code, show='*', width=25).pack()
        result = tk.StringVar(); ttk.Label(win, textvariable=result, wraplength=480).pack(pady=8)
        def run(pair):
            addr = address.get().strip(); pin = code.get().strip(); adb = locate_adb(self.config['adb'])
            if not adb or not addr or (pair and not pin):
                result.set('请填写地址，并确认已配置 ADB；配对时还需配对码。'); return
            def work():
                try:
                    args = ['pair', addr, pin] if pair else ['connect', addr]
                    self.events.put(('wireless', result, adb_run(adb, args, timeout=25)))
                except Exception as exc:
                    self.events.put(('wireless', result, str(exc)))
            result.set('正在连接…'); threading.Thread(target=work, daemon=True).start()
        row = ttk.Frame(win); row.pack()
        ttk.Button(row, text='配对', command=lambda: run(True)).pack(side='left', padx=5)
        ttk.Button(row, text='连接', command=lambda: run(False)).pack(side='left')

    def poll(self):
        while not self.stop.is_set():
            try:
                adb = locate_adb(self.config['adb'])
                if not adb:
                    raise RuntimeError('找不到 ADB：请点击「选择 adb.exe」，或使用 tools 中的 ADB。')
                found = devices(adb)
                if not found:
                    raise RuntimeError('等待手机：请连接 USB、开启 USB 调试并在手机允许授权。离线模拟器会被忽略。')
                # Prefer a real USB device; deduplicate wireless / USB connections by choosing one.
                serial = next((d for d in found if not d.startswith('emulator-') and ':' not in d),
                              next((d for d in found if not d.startswith('emulator-')), found[0]))
                playback = sample(adb, serial)
                self.events.put(('sample', playback, serial))
            except Exception as exc:
                self.events.put(('error', str(exc)))
            self.stop.wait(0.4 if self.config.get('direct_lyrics') else 0.8)

    def lookup(self):
        if not self.playback:
            return
        self.generation += 1; generation = self.generation
        title, artist = self.playback.title, self.playback.artist
        self.source_text.set('正在匹配歌词…')
        def work():
            try:
                result = fetch_lyrics(title, artist, DATA / 'cache')
                self.events.put(('lyrics', generation, result))
            except Exception as exc:
                self.events.put(('lyrics_error', generation, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def retry(self):
        self.demo = False
        if self.playback:
            self.lookup()

    def load_lrc(self):
        path = filedialog.askopenfilename(filetypes=[('LRC 歌词', '*.lrc'), ('文本', '*.txt')])
        if not path:
            return
        try:
            raw = Path(path).read_bytes()
            try:
                text = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = raw.decode('gb18030')
            rows = parse_lrc(text)
            if not rows:
                raise ValueError('文件中没有 [00:12.34] 格式的时间轴。')
            self.generation += 1; self.rows = rows; self.last_line = None
            self.source_text.set('本地歌词：' + Path(path).name + '（切歌后自动重新匹配）')
        except Exception as exc:
            messagebox.showerror('无法加载歌词', str(exc))

    def toggle_demo(self):
        self.demo = not self.demo; self.generation += 1; self.key = None; self.last_line = None
        if self.demo:
            self.playback = Playback('桌面歌词预览', '手机 QQ', 0, True)
            self.rows = [(0, '让喜欢的歌，留在你的桌面'), (4, '自由调整颜色与透明度'), (8, '手机播放 · 电脑显示歌词'), (12, '拖动歌词移动位置，右键打开控制台')]
            self.source_text.set('预览模式：再次点击「预览效果」返回手机同步')
        else:
            self.rows = []; self.playback = None

    def tick(self):
        if os.name == 'nt' and getattr(self, 'hotkey_ok', False):
            from ctypes import wintypes
            msg = wintypes.MSG()
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                self.set_editing(True); self.show()
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == 'wireless':
                try: event[1].set(event[2])
                except tk.TclError: pass
            elif kind == 'sample' and not self.demo:
                p, serial = event[1:]
                self.status.set('已连接：' + serial + (' · 播放中' if p and p.playing else ' · 已暂停 / 等待 QQ 音乐'))
                self.playback = p
                if p:
                    if self.config.get('direct_lyrics'):
                        self.song_text.set('手机媒体信息：' + p.artist)
                        self.source_text.set('手机通知歌词：原样同步当前句，无需联网匹配；同步偏移不适用于此模式')
                    else:
                        self.song_text.set(p.title + ' — ' + p.artist)
                        key = (p.title, p.artist)
                        if key != self.key:
                            self.key = key; self.rows = []; self.last_line = None; self.lookup()
            elif kind == 'error' and not self.demo:
                self.status.set(event[1]); self.playback = None
            elif kind == 'lyrics' and event[1] == self.generation:
                self.rows = parse_lrc(event[2]['lrc']); self.last_line = None
                self.source_text.set('歌词来源：' + event[2]['source'] + ' · 匹配：' + event[2]['matched'])
            elif kind == 'lyrics_error' and event[1] == self.generation:
                self.source_text.set('自动匹配失败，可加载本地 LRC。' + event[2])
        p = self.playback
        if p and self.config.get('direct_lyrics') and not self.demo:
            pair = (p.title or '♪', p.artist)
        elif p:
            position = p.now() + self.config['offset']
            if self.demo:
                position %= 16
            index = line_at(self.rows, position)
            current = self.rows[index][1] if index >= 0 else p.title
            following = self.rows[index+1][1] if index+1 < len(self.rows) else p.artist
            if not self.rows:
                current, following = p.title, p.artist + ' · 等待歌词 / 可加载本地 LRC'
            pair = (current or '♪', following)
        else:
            pair = ('等待手机 QQ 音乐', '连接手机后播放一首歌曲；设置在控制台调整')
        if pair != self.last_line:
            self.line.configure(text=pair[0]); self.next_line.configure(text=pair[1]); self.last_line = pair
        self.root.after(60, self.tick)

    def close(self):
        self.stop.set(); self.save()
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        if os.name == 'nt' and getattr(self, 'hotkey_ok', False):
            ctypes.windll.user32.UnregisterHotKey(None, 1)
        self.root.destroy()


if __name__ == '__main__':
    app = App()
    if '--edit' in sys.argv:
        app.set_editing(True)
    app.root.mainloop()
