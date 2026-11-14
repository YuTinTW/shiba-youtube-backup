"""C 三欄配置；所有 Tk 元件僅在主執行緒操作。"""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .core import validate_url, check_folder, UserError, sanitize_diagnostic
from . import __version__

BG = '#ede1cf'
PANEL = '#fff5e6'
INK = '#493023'
MUTED = '#806d5b'
ORANGE = '#b85223'
GREEN = '#60845f'
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))

EVENT_QUEUE_MAXSIZE = 256
MAX_WORKER_LINE_BYTES = 65536
MAX_POLL_BATCH = 64
MAX_LOG_BYTES = 2_000_000
READ_TIMEOUT_SECONDS = 180
DOWNLOAD_TIMEOUT_SECONDS = 14400
CRITICAL_EVENTS = frozenset(('formats', 'result', 'error', 'worker_exit'))


def iter_bounded_lines(stream, max_bytes=MAX_WORKER_LINE_BYTES):
    while True:
        chunk = stream.readline(max_bytes + 1)
        if not chunk:
            break
        if len(chunk) > max_bytes and not chunk.endswith('\n'):
            # 持續排空超長行的剩餘內容，避免 pipe 緩衝區阻塞造成死鎖。
            while True:
                rest = stream.readline(max_bytes)
                if not rest or rest.endswith('\n'):
                    break
            yield chunk[:max_bytes] + '... [LINE_TRUNCATED]'
        else:
            yield chunk


def enqueue_bounded(q, payload):
    event_name = payload.get('event') if isinstance(payload, dict) else None
    critical = event_name in CRITICAL_EVENTS
    try:
        q.put_nowait(payload)
        return True
    except queue.Full:
        if not critical:
            return False
        # 關鍵終止/結果事件不可被丟棄；騰出一個位置後再放入。
        drained = []
        dropped = False
        try:
            while not q.empty():
                item = q.get_nowait()
                if not dropped and (not isinstance(item, dict) or item.get('event') not in CRITICAL_EVENTS):
                    dropped = True
                    continue
                drained.append(item)
        except queue.Empty:
            pass
        for item in drained:
            try:
                q.put_nowait(item)
            except queue.Full:
                break
        if not dropped and q.full():
            try:
                q.get_nowait()
            except queue.Empty:
                pass
        try:
            q.put_nowait(payload)
            return True
        except queue.Full:
            return False


def worker_env(base_env=None, frozen=None):
    env = dict(os.environ if base_env is None else base_env)
    for key in ('PYTHONSTARTUP', 'PYTHONINSPECT', 'PYTHONWARNINGS'):
        env.pop(key, None)
    is_frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    if is_frozen:
        for key in list(env):
            if key in ('PYTHONPATH', 'PYTHONHOME') or key.startswith('DYLD_'):
                env.pop(key, None)
    return env


def mac_edit_action(event):
    """中文輸入法可能改變 keysym；Tk Aqua 高位元組保留實體鍵碼。"""
    key = event.keysym.lower()
    actions = {'a': '<<SelectAll>>', 'c': '<<Copy>>',
               'v': '<<Paste>>', 'x': '<<Cut>>'}
    if key in actions:
        return actions[key]
    code = event.keycode
    physical = (code >> 24) & 0xff if code > 255 else code
    return {0: '<<SelectAll>>', 8: '<<Copy>>',
            9: '<<Paste>>', 7: '<<Cut>>'}.get(physical)


def command_edit(event):
    action = mac_edit_action(event)
    if action:
        event.widget.event_generate(action)
        return 'break'


class Shiba(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, width=240, height=220, bg=PANEL, highlightthickness=0)
        self.state = 'idle'
        self.tick = 0
        self.frames = {}
        path = ROOT / 'resources' / 'shiba_states.png'
        if path.exists():
            sheet = tk.PhotoImage(file=str(path))
            w, h = sheet.width() // 2, sheet.height() // 2
            for index, state in enumerate(('idle', 'working', 'done', 'error')):
                frame = tk.PhotoImage(width=w, height=h)
                x, y = (index % 2) * w, (index // 2) * h
                frame.tk.call(frame, 'copy', sheet, '-from', x, y, x+w, y+h, '-to', 0, 0)
                self.frames[state] = frame.subsample(max(1, w // 200))
            frame = self.frames['done']
            fw, fh = frame.width(), frame.height()
            x1, y1, x2, y2 = int(fw*.13), int(fh*.46), int(fw*.35), int(fh*.77)
            tail = tk.PhotoImage(width=x2-x1, height=y2-y1)
            tail.tk.call(tail, 'copy', frame, '-from', x1,y1,x2,y2,'-to',0,0)
            body = tk.PhotoImage(width=fw, height=fh)
            for a,b,c,d in ((0,0,fw,y1),(0,y1,x1,y2),(x2,y1,fw,y2),(0,y2,fw,fh)):
                body.tk.call(body,'copy',frame,'-from',a,b,c,d,'-to',a,b)
            self.done_body, self.done_tail = body, tail
            self.tail_origin = (120-fw/2+x1,110-fh/2+y1)
        self.after(240, self.animate)
        self.draw()

    def draw(self):
        self.delete('all')
        animated = self.state in ('working', 'done')
        dy = -2 if animated and self.tick % 2 else 0
        if self.state == 'done' and 'done' in self.frames:
            x, y = self.tail_origin
            self.create_image(x + (3 if self.tick%2 else -2), y + (0 if self.tick%2 else -3),
                              image=self.done_tail, anchor='nw')
            self.create_image(120,110,image=self.done_body)
        elif self.state in self.frames:
            self.create_image(120, 110 + dy, image=self.frames[self.state])
        else:
            # 缺素材時保留可辨識的像素柴犬；狀態仍由文字完整傳達。
            def rect(x, y, w, h, c):
                self.create_rectangle(x, y + dy, x+w, y+h+dy, fill=c, outline='')
            rect(64, 42, 112, 100, INK)
            rect(70, 48, 100, 88, '#d68b37')
            rect(64, 18, 28, 44, INK); rect(70, 24, 16, 32, '#d68b37')
            rect(148, 18, 28, 44, INK); rect(154, 24, 16, 32, '#d68b37')
            rect(80, 100, 80, 36, '#fff0cc')
            rect(86, 80, 10, 10, INK); rect(146, 80, 10, 10, INK)
            rect(116, 100, 14, 10, INK)
            rect(80, 140, 80, 62, INK); rect(86, 146, 68, 50, '#d68b37')
            rect(96, 164, 48, 32, '#fff0cc'); rect(86, 140, 68, 16, '#af4938')
            rect(56, 192, 128, 12, INK)
            if self.state == 'working':
                rect(54, 62, 16, 40, INK); rect(170, 62, 16, 40, INK)
                rect(66, 36, 104, 10, INK)
        if self.state == 'done' and 'done' not in self.frames:
            # 尾巴幀在畫布中切換；不以整張角色位移假冒搖尾。
            y = 150 + (self.tick % 2) * 10
            self.create_polygon(172,y, 194,y-14, 206,y, 196,y+22, 178,y+24,
                                fill='#dfa14f', outline=INK, width=4)
            self.create_rectangle(194,y,204,y+10,fill='#fff0cc',outline='')

    def animate(self):
        self.tick += 1
        if self.state in ('working', 'done'):
            self.draw()
        self.after(240, self.animate)

    def set_state(self, state):
        self.state = state
        self.draw()


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('柴犬Youtube影片備份器 ' + __version__ + '｜測試版')
        self.geometry('1220x760')
        self.minsize(1120, 700)
        self.configure(bg=BG)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue(maxsize=EVENT_QUEUE_MAXSIZE)
        self.process = None
        self.busy = False
        self.loaded_url = ''
        self.choices = []
        self.got_terminal = False
        self.url = tk.StringVar()
        self.folder = tk.StringVar(value=str(Path.home() / 'Downloads'))
        self.title_text = tk.StringVar(value='尚未讀取影片')
        self.status = tk.StringVar(value='待機中')
        self.detail = tk.StringVar(value='貼上網址，再按「讀取格式」。')
        self.progress_text = tk.StringVar(value='尚未開始')
        self.log_path = Path.home() / 'Library/Logs/ShibaStudio/diagnostic.log'
        self.style_setup()
        self.build()
        self.url.trace_add('write', self.url_changed)
        self.after(80, self.poll)

    def style_setup(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('.', font=('PingFang TC', 13), foreground=INK, background=PANEL)
        s.configure('TFrame', background=PANEL)
        s.configure('TLabel', background=PANEL, foreground=INK)
        s.configure('Title.TLabel', font=('PingFang TC', 18, 'bold'))
        s.configure('Muted.TLabel', foreground=MUTED)
        s.configure('TButton', padding=(14, 12), background='#ead6b7', foreground=INK,
                    borderwidth=2, relief='raised')
        s.map('TButton',
              background=[('pressed', '#c3a47d'), ('active', '#f2dec2'), ('disabled', '#e9dfd2')],
              foreground=[('disabled', '#9e9082'), ('pressed', INK), ('active', INK), ('focus', INK), ('!disabled', INK)])
        s.configure('Primary.TButton', background=ORANGE, foreground='white', font=('PingFang TC', 16, 'bold'))
        s.map('Primary.TButton',
              background=[('disabled', '#d8b493'), ('pressed', '#833516'), ('active', '#ce622c')],
              foreground=[('disabled', '#f4e9dc'), ('pressed', 'white'), ('active', 'white'), ('focus', 'white'), ('!disabled', 'white')])
        s.configure('TEntry', padding=9, fieldbackground='#fffdf7',
                    borderwidth=2, bordercolor='#bba98e',
                    insertwidth=3, insertcolor=ORANGE)
        s.map('TEntry',
              fieldbackground=[('disabled', '#e9dfd2'), ('focus', '#fff3d9')],
              bordercolor=[('disabled', '#c6bcae'), ('focus', ORANGE)],
              lightcolor=[('focus', ORANGE)],
              darkcolor=[('focus', ORANGE)])
        s.configure('TCheckbutton', padding=8)
        s.configure('TProgressbar', troughcolor='#dfd2bf', background=GREEN, thickness=18)

    def label(self, parent, text=None, variable=None, style=None, wrap=280):
        w = ttk.Label(parent, text=text, textvariable=variable, wraplength=wrap,
                      style=style or 'TLabel', justify='left')
        w.pack(anchor='w', fill='x', pady=5)
        return w

    def panel(self, parent, heading):
        outer = tk.Frame(parent, bg='#c6af8f', padx=2, pady=2)
        inner = ttk.Frame(outer, padding=20)
        inner.pack(fill='both', expand=True)
        self.label(inner, heading, style='Title.TLabel')
        ttk.Separator(inner).pack(fill='x', pady=(12, 18))
        return outer, inner

    def build(self):
        header = tk.Frame(self, bg=BG, padx=24, pady=20)
        header.pack(fill='x')
        tk.Label(header, text='▣  柴犬Youtube影片備份器', bg=BG, fg=INK,
                 font=('PingFang TC', 27, 'bold')).pack(side='left')
        tk.Label(header, text='迷你存檔工作台  /  0.1.0 測試版', bg=BG,
                 fg=MUTED, font=('PingFang TC', 12)).pack(side='right')
        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=18, pady=(0, 12))
        for i, weight in enumerate((35, 37, 28)):
            body.columnconfigure(i, weight=weight, uniform='columns')
        body.rowconfigure(0, weight=1)
        left_box, left = self.panel(body, '01  來源與位置')
        mid_box, mid = self.panel(body, '02  格式選擇')
        right_box, right = self.panel(body, '03  下載與狀態')
        for i, box in enumerate((left_box, mid_box, right_box)):
            box.grid(row=0, column=i, sticky='nsew', padx=6)
        self.label(left, '影片網址')
        self.url_entry = ttk.Entry(left, textvariable=self.url, cursor='xterm')
        self.url_entry.pack(fill='x', pady=6)
        self.url_entry.bind('<Return>', lambda e: self.read())
        self.setup_entry_editing(self.url_entry)
        self.paste_btn = ttk.Button(left, text='貼上網址', command=self.paste_url)
        self.paste_btn.pack(fill='x', pady=(0, 6))
        self.label(left, '支援單支 YouTube 影片網址。', style='Muted.TLabel')
        self.read_btn = ttk.Button(left, text='讀取格式', command=self.read)
        self.read_btn.pack(fill='x', pady=(10, 24))
        ttk.Separator(left).pack(fill='x', pady=12)
        self.label(left, '儲存資料夾')
        self.path_entry = ttk.Entry(left, textvariable=self.folder, cursor='xterm')
        self.path_entry.pack(fill='x', pady=6)
        self.setup_entry_editing(self.path_entry)
        self.browse_btn = ttk.Button(left, text='選擇資料夾…', command=self.browse)
        self.browse_btn.pack(fill='x', pady=10)
        self.label(left, '下載到的檔案會保留原始編碼；影片選項會自動合併聲音。', style='Muted.TLabel')
        self.open_btn = ttk.Button(left, text='開啟儲存資料夾', command=self.open_folder)
        self.open_btn.pack(side='bottom', fill='x', pady=8)
        self.label(mid, variable=self.title_text, wrap=320)
        self.label(mid, '可複選；依影片實際提供的格式列出。', style='Muted.TLabel', wrap=320)
        holder = ttk.Frame(mid)
        holder.pack(fill='both', expand=True, pady=10)
        self.format_holder = holder
        self.canvas = tk.Canvas(holder, bg=PANEL, highlightthickness=0, width=280,
                                yscrollincrement=18)
        scroll = ttk.Scrollbar(holder, command=self.canvas.yview)
        self.options = ttk.Frame(self.canvas)
        window = self.canvas.create_window((0,0), window=self.options, anchor='nw')
        self.options.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(window, width=e.width))
        # 子元件的事件會傳到視窗；涵蓋清單中的文字、勾選框及捲軸。
        self.bind('<MouseWheel>', self.scroll_formats, add='+')
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.label(self.options, '尚未讀取格式。\n讀取後會在這裡顯示影片與純音訊選項。', style='Muted.TLabel')
        self.shiba = Shiba(right)
        self.shiba.pack(fill='x', pady=4)
        self.label(right, variable=self.status, style='Title.TLabel')
        self.label(right, variable=self.detail)
        ttk.Separator(right).pack(fill='x', pady=16)
        self.label(right, '▣  工作進度', style='Muted.TLabel')
        self.progress = ttk.Progressbar(right, maximum=100)
        self.progress.pack(fill='x', pady=10)
        self.label(right, variable=self.progress_text)
        self.label(right, '此處顯示工作活動，並非音訊電平。', style='Muted.TLabel')
        self.down_btn = ttk.Button(right, text='下載勾選項目', style='Primary.TButton', command=self.download)
        self.down_btn.pack(side='bottom', fill='x', pady=10)
        self.down_btn.state(['disabled'])
        footer = tk.Frame(self, bg=BG, padx=25)
        footer.pack(fill='x', pady=(0,12))
        tk.Label(footer, text='請僅下載你有權保存的內容。', bg=BG, fg=MUTED,
                 font=('PingFang TC',11)).pack(side='left')
        ttk.Button(footer, text='診斷記錄', command=self.open_log).pack(side='right')
        self.url_entry.focus_set()

    def scroll_formats(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget is not self.format_holder:
            widget = widget.master
        if widget is None or not event.delta:
            return
        if self.canvas.yview() == (0.0, 1.0):
            return
        delta = event.delta
        if self.tk.call('tk', 'windowingsystem') != 'aqua':
            delta /= 120
        steps = max(1, min(8, round(abs(delta))))
        self.canvas.yview_scroll(-steps if delta > 0 else steps, 'units')
        return 'break'

    def setup_entry_editing(self, entry):
        if self.tk.call('tk', 'windowingsystem') == 'aqua':
            entry.bind('<Command-KeyPress>', command_edit)
        menu = tk.Menu(entry, tearoff=False)
        for label, action in (('剪下', '<<Cut>>'), ('複製', '<<Copy>>'),
                              ('貼上', '<<Paste>>'), ('全選', '<<SelectAll>>')):
            menu.add_command(label=label,
                             command=lambda a=action: entry.event_generate(a))

        def popup(event):
            entry.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return 'break'

        entry.bind('<Button-2>', popup)
        entry.bind('<Button-3>', popup)
        entry.bind('<Control-Button-1>', popup)

    def paste_url(self):
        if self.busy:
            return
        try:
            value = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo('貼上網址', '剪貼簿中沒有可貼上的文字。', parent=self)
            return
        self.url.set(value.strip())
        self.url_entry.focus_set()
        self.url_entry.icursor('end')

    def url_changed(self, *args):
        if not self.busy:
            self.refresh_download()
            if self.loaded_url and self.url.get().strip() != self.loaded_url:
                self.status.set('網址已更改')
                self.detail.set('請重新讀取格式，以免下載到上一支影片。')

    def refresh_download(self):
        valid = (not self.busy and self.loaded_url == self.url.get().strip()
                 and any(var.get() for _, var, _ in self.choices))
        self.down_btn.state(['!disabled'] if valid else ['disabled'])

    def browse(self):
        result = filedialog.askdirectory(parent=self, title='選擇儲存資料夾',
                                         initialdir=str(Path.home()))
        if result:
            self.folder.set(result)

    def open_folder(self):
        try:
            folder = check_folder(self.folder.get())
            subprocess.Popen(['/usr/bin/open', str(folder)])
        except UserError as e:
            self.fail(str(e))

    def open_log(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.touch(exist_ok=True)
        subprocess.Popen(['/usr/bin/open', '-t', str(self.log_path)])

    def fail(self, text):
        self.status.set('無法完成')
        self.detail.set(text)
        self.shiba.set_state('error')
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self.progress_text.set('未完成，請依上方說明處理。')

    def read(self):
        if self.busy:
            return
        try:
            url = validate_url(self.url.get())
        except UserError as e:
            self.fail(str(e)); return
        self.url.set(url)
        self.loaded_url = ''
        for w in self.options.winfo_children():
            w.destroy()
        self.choices = []
        self.title_text.set('正在讀取…')
        self.start({'action': 'read', 'url': url})

    def download(self):
        if self.busy:
            return
        try:
            url = validate_url(self.url.get())
            folder = check_folder(self.folder.get())
            selected = [row['id'] for row, var, _ in self.choices if var.get()]
            if not selected or url != self.loaded_url:
                raise UserError('請先讀取格式，再勾選至少一個項目。')
        except UserError as e:
            self.fail(str(e)); return
        self.start({'action': 'download', 'url': url, 'folder': str(folder), 'selected': selected})

    def lock(self, busy):
        self.busy = busy
        for widget in (self.url_entry, self.path_entry, self.paste_btn,
                       self.browse_btn, self.read_btn, self.open_btn):
            widget.state(['disabled'] if busy else ['!disabled'])
        for _, _, widget in self.choices:
            widget.state(['disabled'] if busy else ['!disabled'])
        self.refresh_download()

    def start(self, request):
        self.lock(True)
        self.got_terminal = False
        self.status.set('執行中')
        self.detail.set('正在檢查必要工具…')
        self.shiba.set_state('working')
        self.activity('準備中…')
        command = ([sys.executable, '--worker'] if getattr(sys, 'frozen', False)
                   else [sys.executable, str(ROOT / 'app.py'), '--worker'])
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                            env=worker_env())
            process = self.process
            process.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
            process.stdin.close()
        except OSError:
            self.lock(False); self.fail('無法啟動下載工作。請重新安裝 App。'); return
        timeout_sec = READ_TIMEOUT_SECONDS if request.get('action') == 'read' else DOWNLOAD_TIMEOUT_SECONDS
        done_event = threading.Event()
        def watchdog():
            if not done_event.wait(timeout_sec) and process.poll() is None:
                enqueue_bounded(self.events, {'event': 'error', 'message': '工作執行逾時，已自動中止。請稍後重試。'})
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass
        def reader():
            for line in iter_bounded_lines(process.stdout):
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        enqueue_bounded(self.events, payload)
                    else:
                        enqueue_bounded(self.events, {'event': 'diagnostic', 'detail': line})
                except ValueError:
                    enqueue_bounded(self.events, {'event': 'diagnostic', 'detail': line})
            process.wait()
            done_event.set()
            enqueue_bounded(self.events, {'event': 'worker_exit', 'code': process.returncode})
        def errors():
            for line in iter_bounded_lines(process.stderr):
                enqueue_bounded(self.events, {'event': 'diagnostic', 'detail': line})
        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=errors, daemon=True).start()
        threading.Thread(target=watchdog, daemon=True).start()

    def activity(self, text):
        self.progress.stop()
        self.progress.configure(mode='indeterminate')
        self.progress.start(90)
        self.progress_text.set(text)

    def poll(self):
        processed = 0
        try:
            while processed < MAX_POLL_BATCH:
                item = self.events.get_nowait()
                processed += 1
                try:
                    self.handle(item)
                except Exception as exc:
                    self.handle({'event': 'diagnostic', 'detail': repr(exc)})
        except queue.Empty:
            pass
        finally:
            delay = 10 if processed >= MAX_POLL_BATCH and not self.events.empty() else 80
            self.after(delay, self.poll)

    def handle(self, e):
        if not isinstance(e, dict):
            return
        event = e.get('event')
        if event in ('diagnostic', 'warning'):
            detail = sanitize_diagnostic(e.get('detail', ''))
            line = detail + '\n'
            line_bytes = len(line.encode('utf-8', errors='replace'))
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                if self.log_path.exists() and (self.log_path.stat().st_size + line_bytes) > MAX_LOG_BYTES:
                    self.log_path.replace(self.log_path.with_suffix('.previous.log'))
                with self.log_path.open('a', encoding='utf-8') as f:
                    f.write(line)
            except OSError:
                pass
        elif event == 'stage':
            text = e.get('text')
            if not isinstance(text, str) or not text:
                return
            self.status.set('執行中')
            self.detail.set(text)
            self.activity(text)
        elif event == 'progress':
            text = e.get('text')
            if not isinstance(text, str):
                return
            self.detail.set(text)
            pct = e.get('percent')
            if pct is None:
                received = e.get('bytes', 0)
                if not isinstance(received, (int, float)):
                    received = 0
                self.activity('下載中，總大小未知；已收到 {:.1f} MB'.format(received / 1e6))
            elif isinstance(pct, (int, float)):
                pct_val = max(0.0, min(100.0, float(pct)))
                self.progress.stop()
                self.progress.configure(mode='determinate', value=pct_val)
                self.progress_text.set('目前串流 {:.1f}%（尚未全部完成）'.format(pct_val))
        elif event == 'formats':
            title = e.get('title')
            url = e.get('url')
            choices = e.get('choices')
            if (not isinstance(title, str) or not isinstance(url, str)
                    or not isinstance(choices, list)
                    or any(not isinstance(r, dict) or not isinstance(r.get('id'), str)
                           or not isinstance(r.get('label'), str) for r in choices)):
                self.got_terminal = True
                self.fail('背景工作回傳異常格式資料，請重新讀取格式。')
                return
            self.title_text.set(title)
            self.loaded_url = url
            # 下載前的再次讀取只更新資料，不清除使用者勾選。
            if not self.choices:
                for w in self.options.winfo_children():
                    w.destroy()
                for row in choices:
                    var = tk.BooleanVar(value=False)
                    w = ttk.Checkbutton(self.options, text=row['label'], variable=var,
                                        command=self.refresh_download)
                    w.pack(anchor='w', fill='x', pady=5)
                    w.state(['disabled'])
                    self.choices.append((row, var, w))
                self.status.set('格式已就緒')
                self.detail.set('勾選要下載的格式，再按下載。')
                self.progress.stop()
                self.progress.configure(mode='determinate', value=0)
                self.progress_text.set('尚未開始下載')
                self.shiba.set_state('idle')
                self.got_terminal = True
        elif event == 'result':
            status = e.get('status')
            outputs = e.get('outputs')
            errors = e.get('errors')
            if (status not in ('done', 'partial', 'error')
                    or not isinstance(outputs, list)
                    or not isinstance(errors, list)):
                self.got_terminal = True
                self.fail('背景工作回傳異常結果，請查看診斷記錄。')
                return
            self.got_terminal = True
            self.progress.stop()
            self.progress.configure(mode='determinate', value=100 if status == 'done' else 0)
            if status == 'done':
                self.status.set('全部完成')
                self.detail.set('{} 個檔案已下載、完成必要合併並通過輸出檢查。'.format(len(outputs)))
                self.progress_text.set('已輸出到所選資料夾')
                self.shiba.set_state('done')
            else:
                msgs = [str(x.get('message', '處理失敗')) for x in errors if isinstance(x, dict)]
                self.fail('\n'.join(msgs) if msgs else '下載失敗，請查看診斷記錄。')
                self.status.set('部分成功' if outputs else '下載失敗')
                self.progress_text.set('成功 {} 項；失敗 {} 項'.format(len(outputs), len(errors)))
        elif event == 'error':
            msg = e.get('message')
            self.got_terminal = True
            self.fail(msg if isinstance(msg, str) and msg else '處理失敗，請查看診斷記錄。')
        elif event == 'worker_exit':
            self.process = None
            self.lock(False)
            if not self.got_terminal:
                self.fail('背景工作意外結束。請查看診斷記錄，再重新讀取格式。')

    def close(self):
        if self.busy:
            messagebox.showinfo('工作進行中', '請等目前工作結束後再關閉，避免遺失下載結果。', parent=self)
            return
        self.destroy()


def run():
    Studio().mainloop()
