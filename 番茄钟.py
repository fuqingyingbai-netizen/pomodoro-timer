#!/usr/bin/env python3
"""桌面番茄钟 — Python tkinter 原生应用"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import json
import platform
from pathlib import Path

COLORS = {
    'work':       '#E74C3C',
    'shortBreak': '#2ECC71',
    'longBreak':  '#3498DB',
    'workLight':       '#FFF0EE',
    'shortBreakLight': '#EDFAF2',
    'longBreakLight':  '#EDF4FC',
    'text':       '#2C3E50',
    'textDim':    '#7F8C8D',
    'white':      '#FFFFFF',
    'tabBg':      '#F0F0F0',
    'dotEmpty':   '#E0E0E0',
    'hoverBg':    '#F0F0F0',
    'ringBg':     '#ECECEC',
    'cardBg':     '#FDFDFD',
}

DEFAULTS = {'work': 25, 'shortBreak': 5, 'longBreak': 15, 'longInterval': 4}
LABELS = {'work': '专注工作', 'shortBreak': '短暂休息', 'longBreak': '深度休息'}
SETTINGS_FILE = Path(__file__).parent / '.pomodoro_settings.json'


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return {**DEFAULTS, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(d):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(d, f)
    except Exception:
        pass


def play_beep():
    if platform.system() == 'Windows':
        try:
            import winsound
            for freq in (880, 1100, 1320):
                winsound.Beep(freq, 180)
        except Exception:
            pass
    else:
        print('\a')


class PomodoroApp:
    def __init__(self):
        self.settings = load_settings()
        self.mode = 'work'
        self.time_left = self.settings['work'] * 60
        self.total_time = self.time_left
        self.completed = 0
        self.running = False
        self.after_id = None
        self.topmost = False

        self.root = tk.Tk()
        self.root.title('番茄钟')
        self.root.configure(bg=COLORS['workLight'])

        w, h = 400, 560
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')
        self.root.minsize(350, 500)

        self._build_ui()
        self._bind_keys()
        self.refresh_all()

    # ================================================================
    #  UI Construction
    # ================================================================

    def _build_ui(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Outer card container
        self.card = tk.Frame(self.root, bg=COLORS['cardBg'], padx=28, pady=20)
        self.card.grid(row=0, column=0, padx=20, pady=20)

        # --- Mode tabs ---
        tab_outer = tk.Frame(self.card, bg=COLORS['tabBg'])
        tab_outer.pack(pady=(0, 16))
        tab_inner = tk.Frame(tab_outer, bg=COLORS['tabBg'])
        tab_inner.pack(padx=2, pady=2)

        self.tab_btns = {}
        tabs = [('work', '🍅 专注'), ('shortBreak', '☕ 短休'), ('longBreak', '🌿 长休')]
        for key, label in tabs:
            btn = tk.Button(tab_inner, text=label, font=('Microsoft YaHei UI', 11, 'bold'),
                            relief='flat', border=0, width=8, padx=6, pady=6,
                            command=lambda k=key: self.set_mode(k))
            btn.pack(side='left', padx=1)
            self.tab_btns[key] = btn

        # --- Canvas ring ---
        self.cs = 240  # canvas size
        self.canvas = tk.Canvas(self.card, width=self.cs, height=self.cs,
                                bg=COLORS['cardBg'], highlightthickness=0)
        self.canvas.pack(pady=(0, 14))

        # Background ring: use create_arc with style='arc'
        r = 110
        cx = cy = self.cs // 2
        self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                               start=0, extent=359.9,
                               outline=COLORS['ringBg'], width=9,
                               style='arc', tags='bg_ring')

        # Time text
        self.time_text_id = self.canvas.create_text(
            cx, cy - 8, text='25:00',
            font=('Consolas', 48, 'bold'), fill=COLORS['text'])

        # Label text
        self.label_text_id = self.canvas.create_text(
            cx, cy + 28, text=LABELS['work'],
            font=('Microsoft YaHei UI', 11), fill=COLORS['textDim'])

        # --- Session dots ---
        self.dots_frame = tk.Frame(self.card, bg=COLORS['cardBg'])
        self.dots_frame.pack(pady=(0, 4))

        self.dot_canvases = []
        self._build_dots()

        self.session_label = tk.Label(self.dots_frame, text='已完成 0 个番茄',
                                       font=('Microsoft YaHei UI', 10),
                                       fg=COLORS['textDim'], bg=COLORS['cardBg'])
        self.session_label.pack(side='left', padx=(8, 0))

        # --- Controls ---
        ctrl = tk.Frame(self.card, bg=COLORS['cardBg'])
        ctrl.pack(pady=(16, 8))

        self.btn_reset = tk.Button(ctrl, text='↺', font=('Segoe UI Symbol', 16),
                                    relief='flat', border=0, width=3, height=1,
                                    fg=COLORS['textDim'], bg=COLORS['cardBg'],
                                    activebackground=COLORS['hoverBg'],
                                    command=self.reset_timer)
        self.btn_reset.pack(side='left', padx=4)

        self.btn_start = tk.Button(ctrl, text='▶ 开始', font=('Microsoft YaHei UI', 13, 'bold'),
                                    relief='flat', border=0, width=10, height=1,
                                    padx=16, pady=8,
                                    bg=COLORS['work'], fg=COLORS['white'],
                                    activebackground=COLORS['work'],
                                    command=self.toggle_timer)
        self.btn_start.pack(side='left', padx=8)

        self.btn_skip = tk.Button(ctrl, text='⏭', font=('Segoe UI Symbol', 16),
                                   relief='flat', border=0, width=3, height=1,
                                   fg=COLORS['textDim'], bg=COLORS['cardBg'],
                                   activebackground=COLORS['hoverBg'],
                                   command=self.skip_session)
        self.btn_skip.pack(side='left', padx=4)

        # --- Footer ---
        footer = tk.Frame(self.card, bg=COLORS['cardBg'])
        footer.pack(side='bottom', pady=(12, 4))

        self.btn_topmost = tk.Button(footer, text='📌', font=('Segoe UI Symbol', 12),
                                      relief='flat', border=0, width=3, height=1,
                                      fg=COLORS['textDim'], bg=COLORS['cardBg'],
                                      activebackground=COLORS['hoverBg'],
                                      command=self.toggle_topmost)
        self.btn_topmost.pack(side='left', padx=2)

        self.btn_settings = tk.Button(footer, text='⚙', font=('Segoe UI Symbol', 12),
                                       relief='flat', border=0, width=3, height=1,
                                       fg=COLORS['textDim'], bg=COLORS['cardBg'],
                                       activebackground=COLORS['hoverBg'],
                                       command=self.show_settings)
        self.btn_settings.pack(side='left', padx=2)

        tk.Button(footer, text='—', font=('Segoe UI Symbol', 12),
                  relief='flat', border=0, width=3, height=1,
                  fg=COLORS['textDim'], bg=COLORS['cardBg'],
                  activebackground=COLORS['hoverBg'],
                  command=lambda: self.root.iconify()).pack(side='left', padx=2)

        tk.Button(footer, text='✕', font=('Segoe UI Symbol', 12),
                  relief='flat', border=0, width=3, height=1,
                  fg=COLORS['textDim'], bg=COLORS['cardBg'],
                  activebackground='#E74C3C',
                  command=self.root.destroy).pack(side='left', padx=2)

        # Drag support
        self.card.bind('<Button-1>', self._drag_start)
        self.card.bind('<B1-Motion>', self._drag_move)

    def _build_dots(self):
        """(Re)build session dot canvases to match longInterval."""
        for dc in self.dot_canvases:
            dc.destroy()
        self.dot_canvases.clear()

        for _ in range(self.settings['longInterval']):
            dc = tk.Canvas(self.dots_frame, width=14, height=14,
                           bg=COLORS['cardBg'], highlightthickness=0)
            dc.pack(side='left', padx=3)
            dc.create_oval(2, 2, 12, 12, fill=COLORS['dotEmpty'], outline='', tags='dot')
            self.dot_canvases.append(dc)

    def _drag_start(self, event):
        self._dx = event.x_root - self.root.winfo_x()
        self._dy = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        self.root.geometry(f'+{event.x_root - self._dx}+{event.y_root - self._dy}')

    def _bind_keys(self):
        r = self.root
        r.bind('<space>', lambda e: self.toggle_timer())
        r.bind('<r>', lambda e: self.reset_timer())
        r.bind('<R>', lambda e: self.reset_timer())
        r.bind('<Right>', lambda e: self.skip_session())
        r.bind('<Key-1>', lambda e: self.set_mode('work'))
        r.bind('<Key-2>', lambda e: self.set_mode('shortBreak'))
        r.bind('<Key-3>', lambda e: self.set_mode('longBreak'))

    # ================================================================
    #  Drawing
    # ================================================================

    def draw_progress(self):
        self.canvas.delete('progress')
        pct = self.time_left / self.total_time if self.total_time > 0 else 0
        if pct <= 0.001:
            return

        cx = cy = self.cs // 2
        r = 110
        extent = pct * 359.9
        x1, y1 = cx - r, cy - r
        x2, y2 = cx + r, cy + r
        self.canvas.create_arc(x1, y1, x2, y2,
                               start=90, extent=-extent,
                               outline=COLORS[self.mode], width=9,
                               style='arc', tags='progress')

    # ================================================================
    #  UI Refresh
    # ================================================================

    def refresh_mode(self):
        """Called when mode changes: update colors, labels, tab styles."""
        m = self.mode
        color = COLORS[m]
        light = COLORS[m + 'Light']

        self.root.configure(bg=light)

        # Tab buttons
        for key, btn in self.tab_btns.items():
            active = (key == m)
            btn.configure(
                bg=COLORS['white'] if active else COLORS['tabBg'],
                fg=COLORS['text'] if active else COLORS['textDim'],
                activebackground=COLORS['white'] if active else COLORS['tabBg'])

        # Start button
        self.btn_start.configure(bg=color, activebackground=color)

        # Label
        self.canvas.itemconfig(self.label_text_id, text=LABELS[m])

    def refresh_all(self):
        """Full refresh: mode colors + time + progress + dots + button text."""
        self.refresh_mode()

        m, s = divmod(self.time_left, 60)
        self.canvas.itemconfig(self.time_text_id, text=f'{m:02d}:{s:02d}')
        self.root.title(f'{m:02d}:{s:02d} - {LABELS[self.mode]} | 番茄钟')
        self.draw_progress()

        # Session dots
        interval = self.settings['longInterval']
        idx = self.completed % interval
        color = COLORS[self.mode]
        for i, dc in enumerate(self.dot_canvases):
            active = (i < idx) or (i == idx and (self.mode != 'work' or self.running))
            dc.itemconfig('dot', fill=color if active else COLORS['dotEmpty'])
        self.session_label.configure(text=f'已完成 {self.completed} 个番茄')

        # Start button text
        self.btn_start.configure(
            text='⏸ 暂停' if self.running else '▶ 开始')

        # Topmost indicator
        self.btn_topmost.configure(
            fg=COLORS['work'] if self.topmost else COLORS['textDim'])

    # ================================================================
    #  Timer Logic
    # ================================================================

    def tick(self):
        if not self.running:
            return

        self.time_left -= 1

        if self.time_left <= 0:
            self.running = False
            play_beep()

            if self.mode == 'work':
                self.completed += 1
                is_long = (self.completed % self.settings['longInterval']) == 0
                self.mode = 'longBreak' if is_long else 'shortBreak'
            else:
                self.mode = 'work'

            self.time_left = self.settings[self.mode] * 60
            self.total_time = self.time_left
            self.refresh_all()
            return

        m, s = divmod(self.time_left, 60)
        self.canvas.itemconfig(self.time_text_id, text=f'{m:02d}:{s:02d}')
        self.root.title(f'{m:02d}:{s:02d} - {LABELS[self.mode]} | 番茄钟')
        self.draw_progress()
        self.after_id = self.root.after(1000, self.tick)

    def start_timer(self):
        if self.time_left <= 0:
            self.time_left = self.total_time
        self.running = True
        self.refresh_all()
        self.after_id = self.root.after(200, self.tick)

    def stop_timer(self):
        self.running = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.refresh_all()

    def toggle_timer(self):
        if self.running:
            self.stop_timer()
        else:
            self.start_timer()

    def reset_timer(self):
        self.stop_timer()
        self.time_left = self.settings[self.mode] * 60
        self.total_time = self.time_left
        self.refresh_all()

    def skip_session(self):
        self.stop_timer()
        if self.mode == 'work':
            self.completed += 1
            is_long = (self.completed % self.settings['longInterval']) == 0
            self.mode = 'longBreak' if is_long else 'shortBreak'
        else:
            self.mode = 'work'
        self.time_left = self.settings[self.mode] * 60
        self.total_time = self.time_left
        self.refresh_all()

    def set_mode(self, mode):
        self.stop_timer()
        self.mode = mode
        self.time_left = self.settings[mode] * 60
        self.total_time = self.time_left
        self.refresh_all()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes('-topmost', self.topmost)
        self.btn_topmost.configure(
            fg=COLORS['work'] if self.topmost else COLORS['textDim'])

    # ================================================================
    #  Settings Dialog
    # ================================================================

    def show_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('设置')
        dlg.resizable(False, False)
        dlg.configure(bg=COLORS['white'])
        dlg.transient(self.root)
        dlg.grab_set()

        w, h = 320, 340
        px = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f'{w}x{h}+{px}+{py}')

        tk.Label(dlg, text='设置', font=('Microsoft YaHei UI', 15, 'bold'),
                 fg=COLORS['text'], bg=COLORS['white']).pack(pady=(16, 12))

        entries = {}
        fields = [
            ('专注时长 (分钟)', 'work', 1, 120),
            ('短休时长 (分钟)', 'shortBreak', 1, 30),
            ('长休时长 (分钟)', 'longBreak', 1, 60),
            ('长休间隔 (番茄数)', 'longInterval', 2, 10),
        ]

        for label_text, key, _, _ in fields:
            row = tk.Frame(dlg, bg=COLORS['white'])
            row.pack(fill='x', padx=24, pady=5)
            tk.Label(row, text=label_text, font=('Microsoft YaHei UI', 11),
                     fg=COLORS['textDim'], bg=COLORS['white']).pack(side='left')
            var = tk.StringVar(value=str(self.settings[key]))
            tk.Entry(row, textvariable=var, font=('Microsoft YaHei UI', 11),
                     width=6, justify='center', relief='solid', borderwidth=1).pack(side='right')
            entries[key] = var

        btn_row = tk.Frame(dlg, bg=COLORS['white'])
        btn_row.pack(pady=(16, 12))

        tk.Button(btn_row, text='取消', font=('Microsoft YaHei UI', 11),
                  relief='flat', border=0, width=8, padx=10, pady=5,
                  bg=COLORS['white'], fg=COLORS['textDim'],
                  activebackground=COLORS['hoverBg'],
                  command=dlg.destroy).pack(side='left', padx=4)

        def do_save():
            try:
                w = max(1, min(120, int(entries['work'].get())))
                s = max(1, min(30, int(entries['shortBreak'].get())))
                l = max(1, min(60, int(entries['longBreak'].get())))
                iv = max(2, min(10, int(entries['longInterval'].get())))
            except ValueError:
                messagebox.showwarning('无效输入', '请输入有效数字', parent=dlg)
                return

            self.settings = {'work': w, 'shortBreak': s, 'longBreak': l, 'longInterval': iv}
            save_settings(self.settings)

            self.stop_timer()
            self.completed = 0
            self.time_left = self.settings[self.mode] * 60
            self.total_time = self.time_left
            self._build_dots()
            self.refresh_all()
            dlg.destroy()

        tk.Button(btn_row, text='保存', font=('Microsoft YaHei UI', 11, 'bold'),
                  relief='flat', border=0, width=8, padx=10, pady=5,
                  bg=COLORS['work'], fg=COLORS['white'],
                  activebackground=COLORS['work'],
                  command=do_save).pack(side='left', padx=4)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = PomodoroApp()
    app.run()
