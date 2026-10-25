import os, sys, json, copy, queue, random, threading, subprocess, time, colorsys, shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
try:
    import PIL._tkinter_finder
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain as tr

GEN = os.path.join(tr.TOOL, 'terrain.py')
RES = ['512', '1024', '2048', '4096', '8192']
LIVE_RES = ['512', '1024']
RES_INFO = {'512': 'a few seconds', '1024': 'about 10 s', '2048': 'about 30 s',
            '4096': 'about 1\u20132 min', '8192': 'about 5\u201310 min'}
BG = '#1b1f27'
PANEL = '#232934'
FIELD = '#2c3340'
FG = '#d9dee8'
DIM = '#8a93a6'
ACC = '#6fa8ff'
WARM = '#ffb36b'
LINE = '#3a4252'
NOWIN = 0x08000000 if os.name == 'nt' else 0
FONT = 'Segoe UI' if os.name == 'nt' else 'DejaVu Sans'
MONO = 'Consolas' if os.name == 'nt' else 'DejaVu Sans Mono'


SETTINGS = tr.SETTINGS_FILE

def load_settings():
    try:
        with open(SETTINGS) as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(d):
    try:
        with open(SETTINGS, 'w') as f:
            json.dump(d, f, indent=1)
    except Exception:
        pass


def open_folder(d):
    if os.name == 'nt':
        os.startfile(d)
    else:
        subprocess.Popen(['xdg-open', d])


def hexcol(c):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(v)))) for v in c)


def getp(d, path):
    for k in path:
        d = d[k]
    return d


def setp(d, path, v):
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = v



def sheet_font(size):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()



def make_style(root):
    st = ttk.Style(root)
    st.theme_use('clam')
    st.configure('.', background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=LINE, lightcolor=PANEL,
                 darkcolor=BG, troughcolor=FIELD, focuscolor=ACC, selectbackground=ACC, selectforeground='#0b1020',
                 insertcolor=FG, font=(FONT, 10))
    st.configure('TFrame', background=BG)
    st.configure('Card.TFrame', background=PANEL)
    st.configure('Bar.TFrame', background=PANEL)
    st.configure('TLabel', background=BG, foreground=FG)
    st.configure('Dim.TLabel', background=BG, foreground=DIM)
    st.configure('Bar.TLabel', background=PANEL, foreground=FG)
    st.configure('BarDim.TLabel', background=PANEL, foreground=DIM)
    st.configure('CardDim.TLabel', background=PANEL, foreground=DIM)
    st.configure('CardHead.TLabel', background=PANEL, foreground=FG, font=(FONT, 11, 'bold'))
    st.configure('Head.TLabel', background=BG, foreground=FG, font=(FONT, 11, 'bold'))
    st.configure('Title.TLabel', background=PANEL, foreground=FG, font=(FONT, 12, 'bold'))
    st.configure('TButton', background=PANEL, foreground=FG, padding=(10, 4), bordercolor=LINE)
    st.map('TButton', background=[('disabled', BG), ('active', '#2f3746')], foreground=[('disabled', '#5a6272')])
    st.configure('Accent.TButton', background='#2d5fa8', foreground='white')
    st.map('Accent.TButton', background=[('disabled', '#253246'), ('active', '#3a72c4')])
    st.configure('Small.TButton', padding=(5, 1))
    st.configure('TNotebook', background=BG, bordercolor=LINE, tabmargins=(4, 6, 4, 0))
    st.configure('TNotebook.Tab', background=PANEL, foreground=DIM, padding=(5, 5), bordercolor=LINE)
    st.map('TNotebook.Tab', background=[('selected', BG)], foreground=[('selected', FG)])
    st.configure('TLabelframe', background=BG, bordercolor=LINE)
    st.configure('TLabelframe.Label', background=BG, foreground=DIM)
    st.configure('TEntry', fieldbackground=FIELD, foreground=FG)
    st.configure('TSpinbox', fieldbackground=FIELD, foreground=FG, arrowcolor=FG, background=PANEL)
    st.configure('TCombobox', fieldbackground=FIELD, foreground=FG, arrowcolor=FG, background=PANEL)
    st.map('TCombobox', fieldbackground=[('readonly', FIELD)], foreground=[('readonly', FG)],
           selectbackground=[('readonly', FIELD)], selectforeground=[('readonly', FG)])
    st.configure('Horizontal.TScale', background=PANEL, troughcolor=FIELD, bordercolor=LINE)
    st.configure('TCheckbutton', background=BG, foreground=FG)
    st.map('TCheckbutton', background=[('active', BG)])
    st.configure('Toolbutton', background=PANEL, foreground=DIM, padding=(8, 4))
    st.map('Toolbutton', background=[('selected', '#2d5fa8'), ('active', '#2f3746')], foreground=[('selected', 'white')])
    st.configure('Horizontal.TProgressbar', background=ACC, troughcolor=FIELD, bordercolor=LINE, lightcolor=ACC, darkcolor=ACC)
    st.configure('Vertical.TScrollbar', background=PANEL, troughcolor=BG, arrowcolor=DIM, bordercolor=BG,
                 lightcolor=PANEL, darkcolor=PANEL, gripcount=0)
    st.map('Vertical.TScrollbar', background=[('active', '#3a4456')])
    root.option_add('*TCombobox*Listbox.background', FIELD)
    root.option_add('*TCombobox*Listbox.foreground', FG)
    root.option_add('*TCombobox*Listbox.selectBackground', ACC)


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=BG)
        self.vsb = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=(4, 6, 8, 12))
        self.inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.vsb.pack(side='right', fill='y')
        self.bind('<Enter>', self._on)
        self.bind('<Leave>', self._off)

    def _on(self, _e=None):
        self.canvas.bind_all('<MouseWheel>', self._wheel)
        self.canvas.bind_all('<Button-4>', lambda e: self.canvas.yview_scroll(-2, 'units'))
        self.canvas.bind_all('<Button-5>', lambda e: self.canvas.yview_scroll(2, 'units'))

    def _off(self, _e=None):
        self.canvas.unbind_all('<MouseWheel>')
        self.canvas.unbind_all('<Button-4>')
        self.canvas.unbind_all('<Button-5>')

    def _wheel(self, e):
        self.canvas.yview_scroll(-1 * int(e.delta / 120) if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1), 'units')


class Slider:
    def __init__(self, app, parent, row, label, path, lo, hi, step, isint=False, tip=None, src=None, notify=None, registry=None):
        self.app, self.path, self.lo, self.hi, self.step, self.isint = app, path, lo, hi, step, isint
        self.src = src or (lambda: app.P)
        self.notify = notify or app.changed
        self.busy = False
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(8, 8), pady=(4, 0))
        self.var = tk.DoubleVar()
        self.scale = ttk.Scale(parent, from_=lo, to=hi, orient='horizontal', variable=self.var, command=self.moved)
        self.scale.grid(row=row, column=1, sticky='ew', pady=(4, 0))
        self.scale.bind('<ButtonPress-1>', self.press, add='+')
        self.scale.bind('<ButtonRelease-1>', self.release, add='+')
        self.start = None
        self.txt = tk.StringVar()
        en = ttk.Entry(parent, textvariable=self.txt, width=9, justify='right')
        en.grid(row=row, column=2, padx=(8, 4), pady=(4, 0))
        en.bind('<Return>', self.typed)
        en.bind('<FocusOut>', self.typed)
        if tip:
            ttk.Label(parent, text=tip, style='Dim.TLabel', font=(FONT, 8)).grid(row=row + 1, column=0, columnspan=3, sticky='w', padx=(8, 0))
        (registry if registry is not None else app.sliders).append(self)

    def press(self, _e=None):
        self.start = copy.deepcopy(getp(self.src(), self.path))
        if self.registry_undo():
            self.app.snapshot()

    def release(self, _e=None):
        if self.start is not None and self.registry_undo() and getp(self.src(), self.path) == self.start and self.app.history:
            self.app.history.pop()
            if not self.app.history:
                self.app.undo_btn.configure(state='disabled')
        self.start = None

    def registry_undo(self):
        return self.src is not None and getattr(self.app, 'P', None) is self.src()

    def fmt(self, v):
        if self.isint:
            return str(int(round(v)))
        dec = max(0, -int(np.floor(np.log10(self.step)))) if self.step < 1 else 0
        return ('%.' + str(dec) + 'f') % v

    def snap(self, v):
        v = round(v / self.step) * self.step
        return int(round(v)) if self.isint else float(self.fmt(v))

    def refresh(self):
        v = getp(self.src(), self.path)
        self.busy = True
        self.var.set(min(max(v, self.lo), self.hi))
        self.txt.set(self.fmt(v))
        self.busy = False

    def moved(self, _=None):
        if self.busy:
            return
        v = self.snap(self.var.get())
        self.txt.set(self.fmt(v))
        if v != getp(self.src(), self.path):
            setp(self.src(), self.path, v)
            self.notify()

    def typed(self, _=None):
        try:
            v = self.snap(float(self.txt.get().replace(',', '.')))
        except ValueError:
            self.refresh()
            return
        self.busy = True
        self.var.set(min(max(v, self.lo), self.hi))
        self.busy = False
        self.txt.set(self.fmt(v))
        if v != getp(self.src(), self.path):
            if self.registry_undo():
                self.app.snapshot()
            setp(self.src(), self.path, v)
            self.notify()


def sv_image(h, n=256):
    c = np.array(colorsys.hsv_to_rgb(h, 1.0, 1.0), np.float32)
    sat = np.linspace(0, 1, n, dtype=np.float32)[None, :, None]
    val = np.linspace(1, 0, n, dtype=np.float32)[:, None, None]
    img = val * ((1 - sat) + sat * c[None, None, :])
    return Image.fromarray((img * 255 + 0.5).astype(np.uint8))


def hue_image(w=26, n=256):
    rows = np.array([colorsys.hsv_to_rgb(y / float(n), 1.0, 1.0) for y in range(n)], np.float32)
    return Image.fromarray((np.repeat(rows[:, None, :], w, 1) * 255 + 0.5).astype(np.uint8))


def recent_colours():
    out = []
    for c in load_settings().get('recent_colours', []):
        try:
            v = [int(max(0, min(255, x))) for x in c][:3]
            if len(v) == 3:
                out.append(v)
        except (TypeError, ValueError):
            pass
    return out[:14]


def remember_colour(rgb):
    S = load_settings()
    rc = [list(rgb)] + [c for c in recent_colours() if list(c) != list(rgb)]
    S['recent_colours'] = rc[:14]
    save_settings(S)


class PixelPicker(tk.Toplevel):
    Z = 11

    def __init__(self, master, img, done, fullscreen=False):
        super().__init__(master)
        self.img = img
        self.arr = np.asarray(img).astype(np.float32)
        self.done = done
        self.finished = False
        self.configure(bg='black')
        iw, ih = img.size
        if fullscreen:
            self.overrideredirect(True)
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry('%dx%d+0+0' % (sw, sh))
            dw, dh = sw, sh
        else:
            self.title('Click a colour in the picture')
            sc = min(1100.0 / iw, 760.0 / ih, 1.0 if max(iw, ih) > 300 else 4.0)
            dw, dh = max(1, int(iw * sc)), max(1, int(ih * sc))
        self.sx, self.sy = iw / float(dw), ih / float(dh)
        disp = img.resize((dw, dh), Image.LANCZOS) if (dw, dh) != (iw, ih) else img
        self.tkimg = ImageTk.PhotoImage(disp)
        self.cv = tk.Canvas(self, width=dw, height=dh, bg='black', highlightthickness=0, cursor='crosshair')
        self.cv.pack()
        self.cv.create_image(0, 0, image=self.tkimg, anchor='nw')
        self.loupe_img = None
        self.lp = self.cv.create_image(0, 0, anchor='nw')
        self.lbox = self.cv.create_rectangle(0, 0, 0, 0, outline='white', width=2)
        self.lfr = self.cv.create_rectangle(0, 0, 0, 0, outline='white', width=1)
        self.ltxt_bg = self.cv.create_rectangle(0, 0, 0, 0, fill='#101318', outline='')
        self.ltxt = self.cv.create_text(0, 0, anchor='nw', fill='white', font=(MONO, 10))
        self.cv.create_rectangle(dw // 2 - 210, 2, dw // 2 + 210, 28, fill='#101318', outline=LINE)
        self.cv.create_text(dw // 2, 15, text='Click a colour  \u00b7  Esc or right-click = cancel', fill='white',
                            font=(FONT, 11, 'bold'))
        self.cv.bind('<Motion>', self.move)
        self.cv.bind('<Button-1>', self.click)
        self.cv.bind('<Button-3>', lambda e: self.close(None))
        self.bind('<Escape>', lambda e: self.close(None))
        self.protocol('WM_DELETE_WINDOW', lambda: self.close(None))
        self.after(50, self.take_focus)

    def take_focus(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass

    def at(self, x, y):
        H, W = self.arr.shape[:2]
        return min(max(int(x * self.sx), 0), W - 1), min(max(int(y * self.sy), 0), H - 1)

    def colour(self, ix, iy):
        H, W = self.arr.shape[:2]
        a = self.arr[max(iy - 1, 0):min(iy + 2, H), max(ix - 1, 0):min(ix + 2, W)]
        return [int(round(v)) for v in a.reshape(-1, 3).mean(0)]

    def move(self, e):
        ix, iy = self.at(e.x, e.y)
        r = self.Z // 2
        H, W = self.arr.shape[:2]
        ys = np.clip(np.arange(iy - r, iy + r + 1), 0, H - 1)
        xs = np.clip(np.arange(ix - r, ix + r + 1), 0, W - 1)
        crop = self.arr[ys][:, xs].astype(np.uint8)
        big = Image.fromarray(crop).resize((self.Z * 10, self.Z * 10), Image.NEAREST)
        self.loupe_img = ImageTk.PhotoImage(big)
        cw, ch = int(self.cv.cget('width')), int(self.cv.cget('height'))
        lx = e.x + 24 if e.x + 24 + 110 < cw else e.x - 24 - 110
        ly = e.y + 24 if e.y + 24 + 140 < ch else e.y - 24 - 140
        self.cv.itemconfigure(self.lp, image=self.loupe_img)
        self.cv.coords(self.lp, lx, ly)
        self.cv.coords(self.lfr, lx, ly, lx + 110, ly + 110)
        self.cv.coords(self.lbox, lx + 50, ly + 50, lx + 60, ly + 60)
        c = self.colour(ix, iy)
        self.cv.coords(self.ltxt_bg, lx, ly + 112, lx + 110, ly + 134)
        self.cv.coords(self.ltxt, lx + 6, ly + 115)
        self.cv.itemconfigure(self.ltxt, text=hexcol(c))
        for it in (self.lp, self.lfr, self.lbox, self.ltxt_bg, self.ltxt):
            self.cv.tag_raise(it)

    def click(self, e):
        self.close(self.colour(*self.at(e.x, e.y)))

    def close(self, rgb):
        if self.finished:
            return
        self.finished = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.done(rgb)


class ColourPicker(tk.Toplevel):
    def __init__(self, app, initial, title, live=None):
        super().__init__(app)
        self.app = app
        self.live = live
        self.result = None
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app)
        self.initial = [int(round(float(v))) for v in initial][:3]
        self.rgb = list(self.initial)
        self.h, self.s, self.v = colorsys.rgb_to_hsv(*[c / 255.0 for c in self.rgb])
        body = ttk.Frame(self, padding=12)
        body.pack(fill='both')
        self.sv = tk.Canvas(body, width=256, height=256, highlightthickness=1, highlightbackground=LINE, cursor='crosshair', bg=BG)
        self.sv.grid(row=0, column=0, sticky='n')
        self.hue = tk.Canvas(body, width=26, height=256, highlightthickness=1, highlightbackground=LINE, cursor='sb_v_double_arrow', bg=BG)
        self.hue.grid(row=0, column=1, sticky='n', padx=(8, 14))
        self.hue_tk = ImageTk.PhotoImage(hue_image())
        self.hue.create_image(0, 0, image=self.hue_tk, anchor='nw')
        self.hue_mark = self.hue.create_rectangle(0, 0, 27, 4, outline='white', width=2)
        self.sv_img = self.sv.create_image(0, 0, anchor='nw')
        self.sv_mark = self.sv.create_oval(0, 0, 0, 0, outline='white', width=2)
        self.sv_mark2 = self.sv.create_oval(0, 0, 0, 0, outline='black', width=1)
        for ev in ('<Button-1>', '<B1-Motion>'):
            self.sv.bind(ev, self.sv_click)
            self.hue.bind(ev, self.hue_click)
        right = ttk.Frame(body)
        right.grid(row=0, column=2, sticky='n')
        self.cmp = tk.Canvas(right, width=150, height=56, highlightthickness=1, highlightbackground=LINE, bg=BG)
        self.cmp.grid(row=0, column=0, columnspan=4, sticky='w')
        self.cmp_old = self.cmp.create_rectangle(0, 0, 75, 57, outline='')
        self.cmp_new = self.cmp.create_rectangle(75, 0, 151, 57, outline='')
        self.cmp.tag_bind(self.cmp_old, '<Button-1>', lambda e: self.set_rgb(self.initial))
        ttk.Label(right, text='before          now', style='Dim.TLabel').grid(row=1, column=0, columnspan=4, sticky='w', pady=(2, 8))
        ttk.Label(right, text='Hex').grid(row=2, column=0, sticky='w')
        self.hexv = tk.StringVar()
        he = ttk.Entry(right, textvariable=self.hexv, width=9)
        he.grid(row=2, column=1, columnspan=3, sticky='w', pady=2)
        he.bind('<Return>', self.hex_typed)
        he.bind('<FocusOut>', self.hex_typed)
        self.chv = []
        for i, nm in enumerate('RGB'):
            ttk.Label(right, text=nm).grid(row=3 + i, column=0, sticky='w')
            v = tk.StringVar()
            sp = ttk.Spinbox(right, textvariable=v, from_=0, to=255, increment=1, width=6, command=self.ch_typed)
            sp.grid(row=3 + i, column=1, columnspan=3, sticky='w', pady=2)
            sp.bind('<Return>', self.ch_typed)
            sp.bind('<FocusOut>', self.ch_typed)
            self.chv.append(v)
        ttk.Button(right, text='Pick from screen', command=self.pick_screen).grid(row=6, column=0, columnspan=4, sticky='ew', pady=(12, 3))
        ttk.Button(right, text='Pick from picture\u2026', command=self.pick_picture).grid(row=7, column=0, columnspan=4, sticky='ew')
        low = ttk.Frame(self, padding=(12, 0, 12, 12))
        low.pack(fill='x')
        self.swatch_row(low, 'This planet', app.planet_colours(), 0)
        self.swatch_row(low, 'Recent', recent_colours(), 1)
        bar = ttk.Frame(low)
        bar.grid(row=2, column=0, columnspan=2, sticky='e', pady=(10, 0))
        ttk.Button(bar, text='Cancel', command=self.cancel).pack(side='right')
        ttk.Button(bar, text='OK', style='Accent.TButton', command=self.ok).pack(side='right', padx=6)
        self.bind('<Escape>', lambda e: self.cancel())
        self.bind('<Return>', lambda e: self.ok() if not isinstance(self.focus_get(), (ttk.Entry, ttk.Spinbox)) else None)
        self.protocol('WM_DELETE_WINDOW', self.cancel)
        self.draw_sv()
        self.refresh(notify=False)
        self.update_idletasks()
        try:
            x = app.winfo_rootx() + max(0, (app.winfo_width() - self.winfo_reqwidth()) // 2)
            y = app.winfo_rooty() + max(0, (app.winfo_height() - self.winfo_reqheight()) // 3)
            self.geometry('+%d+%d' % (x, y))
        except tk.TclError:
            pass
        self.grab_set()
        self.focus_set()

    def swatch_row(self, parent, label, cols, row):
        ttk.Label(parent, text=label, style='Dim.TLabel', width=11).grid(row=row, column=0, sticky='w', pady=(6, 0))
        fr = ttk.Frame(parent)
        fr.grid(row=row, column=1, sticky='w', pady=(6, 0))
        if not cols:
            ttk.Label(fr, text='\u2013', style='Dim.TLabel').pack(side='left')
        for c in cols[:14]:
            c = [int(round(float(v))) for v in c][:3]
            lab = tk.Label(fr, bg=hexcol(c), width=2, relief='solid', bd=1, cursor='hand2')
            lab.pack(side='left', padx=(0, 3))
            lab.bind('<Button-1>', lambda e, c=c: self.set_rgb(c))

    def draw_sv(self):
        self.sv_tk = ImageTk.PhotoImage(sv_image(self.h))
        self.sv.itemconfigure(self.sv_img, image=self.sv_tk)

    def refresh(self, notify=True):
        x, y = self.s * 255, (1 - self.v) * 255
        self.sv.coords(self.sv_mark, x - 6, y - 6, x + 6, y + 6)
        self.sv.coords(self.sv_mark2, x - 7, y - 7, x + 7, y + 7)
        hy = self.h * 255
        self.hue.coords(self.hue_mark, 1, hy - 3, 27, hy + 3)
        self.cmp.itemconfigure(self.cmp_old, fill=hexcol(self.initial))
        self.cmp.itemconfigure(self.cmp_new, fill=hexcol(self.rgb))
        self.hexv.set(hexcol(self.rgb))
        for v, c in zip(self.chv, self.rgb):
            v.set(str(c))
        if notify and self.live:
            self.live(list(self.rgb))

    def from_hsv(self):
        self.rgb = [int(round(c * 255)) for c in colorsys.hsv_to_rgb(self.h, self.s, self.v)]
        self.refresh()

    def set_rgb(self, rgb):
        self.rgb = [int(max(0, min(255, round(float(c))))) for c in rgb][:3]
        h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in self.rgb])
        if s > 0 and v > 0:
            if abs(h - self.h) > 1e-4:
                self.h = h
                self.draw_sv()
        self.s, self.v = s, v
        self.refresh()

    def sv_click(self, e):
        self.s = min(max(e.x / 255.0, 0.0), 1.0)
        self.v = 1 - min(max(e.y / 255.0, 0.0), 1.0)
        self.from_hsv()

    def hue_click(self, e):
        self.h = min(max(e.y / 256.0, 0.0), 0.999)
        self.draw_sv()
        self.from_hsv()

    def hex_typed(self, _e=None):
        t = self.hexv.get().strip().lstrip('#')
        if len(t) == 3:
            t = ''.join(ch * 2 for ch in t)
        try:
            if len(t) != 6:
                raise ValueError
            c = [int(t[i:i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            self.hexv.set(hexcol(self.rgb))
            return
        if c != self.rgb:
            self.set_rgb(c)

    def ch_typed(self, _e=None):
        try:
            c = [int(round(float(v.get().replace(',', '.')))) for v in self.chv]
        except ValueError:
            self.refresh(notify=False)
            return
        c = [max(0, min(255, x)) for x in c]
        if c != self.rgb:
            self.set_rgb(c)

    def picked(self, rgb):
        try:
            self.deiconify()
            self.lift()
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            return
        if rgb:
            self.set_rgb(rgb)

    def pick_screen(self):
        try:
            from PIL import ImageGrab
        except Exception as ex:
            messagebox.showerror('Pick from screen', 'Screen capture is not available here.\n%s' % ex, parent=self)
            return
        self.grab_release()
        self.withdraw()

        def grab():
            try:
                img = ImageGrab.grab().convert('RGB')
            except Exception as ex:
                self.picked(None)
                messagebox.showerror('Pick from screen', 'Could not capture the screen.\n%s' % ex, parent=self)
                return
            PixelPicker(self, img, self.picked, fullscreen=True)
        self.after(250, grab)

    def pick_picture(self):
        path = filedialog.askopenfilename(parent=self, title='Picture to pick a colour from',
                                          filetypes=[('Pictures', '*.png *.jpg *.jpeg *.bmp *.tga *.webp *.dds'), ('All files', '*.*')])
        if not path:
            return
        try:
            img = Image.open(path).convert('RGB')
        except Exception as ex:
            messagebox.showerror('Could not open picture', str(ex), parent=self)
            return
        self.grab_release()
        PixelPicker(self, img, self.picked, fullscreen=False)

    def ok(self):
        self.ch_typed()
        self.result = list(self.rgb)
        self.grab_release()
        self.destroy()

    def cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


def pick_colour(app, initial, title='Pick a colour', live=None, restore=None):
    snap = getattr(app, 'snapshot', None)
    if snap:
        snap()
    dlg = ColourPicker(app, initial, title, live)
    app.wait_window(dlg)
    res = dlg.result
    same = res is not None and list(res) == [int(round(float(v))) for v in initial][:3]
    if res is None or same:
        if snap and app.history:
            app.history.pop()
            if not app.history:
                app.undo_btn.configure(state='disabled')
        if restore:
            restore()
        return None
    remember_colour(res)
    return res


class Swatch:
    def __init__(self, app, parent, path):
        self.app, self.path = app, path
        self.lab = tk.Label(parent, width=6, relief='solid', bd=1, cursor='hand2')
        self.lab.bind('<Button-1>', self.pick)
        app.swatches.append(self)

    def refresh(self):
        self.lab.configure(bg=hexcol(getp(self.app.P, self.path)))

    def pick(self, _e=None):
        old = copy.deepcopy(getp(self.app.P, self.path))

        def live(v):
            setp(self.app.P, self.path, v)
            self.refresh()
            self.app.changed()

        def restore():
            live(old)
        c = pick_colour(self.app, old, live=live, restore=restore)
        if c:
            live(c)


def num(label, key, lo, hi, inc, fmt, default=0.0, isint=False, width=7):
    def g(it):
        return it[key] if isinstance(it, list) else it.get(key, default)

    def s(it, v):
        it[key] = v
    return {'label': label, 'get': g, 'set': s, 'lo': lo, 'hi': hi, 'inc': inc, 'fmt': fmt, 'int': isint, 'width': width}


def colf(label, key, default=(128, 128, 128)):
    def g(it):
        return it[key] if isinstance(it, list) else it.get(key, list(default))

    def s(it, v):
        it[key] = v
    return {'label': label, 'get': g, 'set': s, 'kind': 'color'}


def spinf(label, key, default=1):
    def g(it):
        return it.get(key, default)

    def s(it, v):
        it[key] = v
    return {'label': label, 'get': g, 'set': s, 'kind': 'choice', 'values': ['1', '-1'], 'conv': int}



class ListEditor:
    def __init__(self, app, parent, items_fn, fields, new_item, card=False, cols=5, add_text='Add', notify=None, registry=None, on_remove=None):
        self.app, self.items_fn, self.fields, self.new_item, self.card, self.cols = app, items_fn, fields, new_item, card, cols
        self.notify = notify or app.changed
        self.on_remove = on_remove
        self.frame = ttk.Frame(parent)
        self.body = ttk.Frame(self.frame)
        self.body.pack(fill='x')
        self.bar = ttk.Frame(self.frame)
        self.bar.pack(fill='x', pady=(6, 0))
        ttk.Button(self.bar, text=add_text, command=self.add).pack(side='left')
        (registry if registry is not None else app.editors).append(self)

    def rebuild(self):
        for w in self.body.winfo_children():
            w.destroy()
        items = self.items_fn()
        if not self.card:
            if items:
                for j, f in enumerate(self.fields):
                    ttk.Label(self.body, text=f['label'], style='Dim.TLabel').grid(row=0, column=j, padx=4, sticky='w')
            for i, it in enumerate(items):
                for j, f in enumerate(self.fields):
                    self.widget(self.body, it, f).grid(row=i + 1, column=j, padx=4, pady=2, sticky='w')
                ttk.Button(self.body, text='✕', width=3, style='Small.TButton',
                           command=lambda i=i: self.remove(i)).grid(row=i + 1, column=len(self.fields), padx=4)
        else:
            for i, it in enumerate(items):
                card = ttk.Frame(self.body, style='Card.TFrame', padding=8)
                card.pack(fill='x', pady=4)
                for j, f in enumerate(self.fields):
                    r, c = divmod(j, self.cols)
                    ttk.Label(card, text=f['label'], style='CardDim.TLabel').grid(row=r * 2, column=c, sticky='w', padx=4)
                    self.widget(card, it, f).grid(row=r * 2 + 1, column=c, sticky='w', padx=4, pady=(0, 6))
                ttk.Button(card, text='✕', width=3, style='Small.TButton',
                           command=lambda i=i: self.remove(i)).grid(row=1, column=self.cols, padx=(2, 0), sticky='w')

    def widget(self, parent, item, f):
        kind = f.get('kind', 'num')
        if kind == 'custom':
            return f['make'](parent, item)
        if kind == 'color':
            lab = tk.Label(parent, bg=hexcol(f['get'](item)), width=6, relief='solid', bd=1, cursor='hand2')

            def pick(_e=None, lab=lab):
                old = copy.deepcopy(f['get'](item))

                def live(v):
                    f['set'](item, v)
                    try:
                        lab.configure(bg=hexcol(v))
                    except tk.TclError:
                        pass
                    self.notify()

                def restore():
                    live(old)
                c = pick_colour(self.app, old, live=live, restore=restore)
                if c:
                    live(c)
            lab.bind('<Button-1>', pick)
            return lab
        if kind == 'choice':
            var = tk.StringVar(value=str(f['get'](item)))
            cb = ttk.Combobox(parent, textvariable=var, values=f['values'], width=f.get('width', 4), state='readonly')

            def sel(_e=None, var=var):
                self.app.snapshot()
                f['set'](item, f.get('conv', str)(var.get()))
                self.notify()
            cb.bind('<<ComboboxSelected>>', sel)
            return cb
        fmt = f['fmt']
        var = tk.StringVar(value=fmt % f['get'](item))
        sp = ttk.Spinbox(parent, textvariable=var, from_=f['lo'], to=f['hi'], increment=f['inc'], width=f['width'], format=fmt)

        def commit(_e=None, var=var):
            try:
                v = float(var.get().replace(',', '.'))
            except ValueError:
                var.set(fmt % f['get'](item))
                return
            if f.get('int'):
                v = int(round(v))
            if v != f['get'](item):
                self.app.snapshot()
                f['set'](item, v)
                self.notify()
        sp.configure(command=commit)
        sp.bind('<Return>', commit)
        sp.bind('<FocusOut>', commit)
        return sp

    def add(self):
        self.app.snapshot()
        self.items_fn().append(self.new_item())
        self.rebuild()
        self.notify()

    def remove(self, i):
        items = self.items_fn()
        if self.items_fn is self.app.stops_fn and len(items) <= 1:
            return
        self.app.snapshot()
        items.pop(i)
        if self.on_remove:
            self.on_remove(i)
        self.rebuild()
        self.notify()



FEAT_NAMES = ['Crater', 'Basin', 'Volcano', 'Mountain', 'Plateau']
PALETTES = {
    'lush': [[40, 50, 58], [86, 92, 84], [84, 106, 58], [82, 104, 56], [116, 114, 74], [124, 110, 90], [112, 106, 102]],
    'desert': [[96, 60, 44], [140, 84, 56], [176, 112, 72], [190, 132, 86], [168, 104, 70], [140, 92, 70], [196, 170, 150]],
    'grey': [[66, 66, 68], [88, 88, 88], [112, 110, 108], [128, 126, 122], [140, 138, 134], [150, 148, 144], [160, 158, 154]],
    'ice': [[120, 138, 160], [164, 180, 196], [200, 212, 224], [214, 222, 232], [226, 232, 240], [190, 200, 212], [236, 240, 246]],
    'alien': [[40, 30, 64], [70, 52, 96], [104, 70, 120], [78, 120, 112], [120, 96, 140], [150, 120, 120], [190, 176, 200]],
    'volcanic': [[24, 20, 20], [44, 34, 30], [62, 46, 38], [80, 56, 44], [70, 52, 46], [96, 72, 60], [120, 104, 96]],
    'savanna': [[44, 54, 60], [96, 96, 80], [138, 134, 78], [134, 132, 74], [150, 126, 82], [136, 112, 90], [124, 116, 108]],
}
PAL_LEVELS = (-1.0, -0.08, 0.0, 0.1, 0.35, 0.65, 0.9)


class OptSwatch:
    def __init__(self, app, parent, path, auto_rgb, auto_text='auto'):
        self.app, self.path, self.auto_rgb = app, path, auto_rgb
        self.frame = ttk.Frame(parent)
        self.lab = tk.Label(self.frame, width=6, relief='solid', bd=1, cursor='hand2')
        self.lab.pack(side='left')
        self.lab.bind('<Button-1>', self.pick)
        self.note = ttk.Label(self.frame, text=auto_text, style='Dim.TLabel')
        self.btn = ttk.Button(self.frame, text='Auto', style='Small.TButton', command=self.reset)
        app.swatches.append(self)

    def refresh(self):
        v = getp(self.app.P, self.path)
        self.lab.configure(bg=hexcol(v if v is not None else self.auto_rgb))
        self.note.pack_forget()
        self.btn.pack_forget()
        if v is None:
            self.note.pack(side='left', padx=(6, 0))
        else:
            self.btn.pack(side='left', padx=(6, 0))

    def pick(self, _e=None):
        old = copy.deepcopy(getp(self.app.P, self.path))

        def live(v):
            setp(self.app.P, self.path, v)
            self.refresh()
            self.app.changed()

        def restore():
            live(old)
        c = pick_colour(self.app, old if old is not None else self.auto_rgb, live=live, restore=restore)
        if c:
            live(c)

    def reset(self):
        self.app.snapshot()
        setp(self.app.P, self.path, None)
        self.refresh()
        self.app.changed()


def sample_line(arr, x1, y1, x2, y2, n, gain, box):
    H, W, _ = arr.shape
    out = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = int(round(x1 + (x2 - x1) * t)); y = int(round(y1 + (y2 - y1) * t))
        blk = arr[max(0, y - box):min(H, y + box + 1), max(0, x - box):min(W, x + box + 1)].reshape(-1, 3)
        out.append([int(round(v)) for v in np.clip(blk.mean(0) * gain, 0, 255)])
    return out


class SampleWin(tk.Toplevel):
    def __init__(self, app, path):
        super().__init__(app)
        self.app = app
        self.title('Colours from a picture')
        self.configure(bg=BG)
        self.src = Image.open(path).convert('RGB')
        self.arr = np.asarray(self.src).astype(np.float32)
        iw, ih = self.src.size
        self.s = min(900 / iw, 640 / ih)
        disp = self.src.resize((max(1, int(iw * self.s)), max(1, int(ih * self.s))), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(disp)
        left = ttk.Frame(self, padding=10)
        left.pack(side='left', fill='both', expand=True)
        ttk.Label(left, text='Click the LOW end, then the HIGH end of a line across the picture.',
                  style='Head.TLabel').pack(anchor='w')
        ttk.Label(left, text='For example from a beach or a valley floor up to a snowy peak. The colours along the line '
                             'become the colours by height.', style='Dim.TLabel').pack(anchor='w', pady=(0, 8))
        self.cv = tk.Canvas(left, width=disp.width, height=disp.height, bg='black', highlightthickness=0, cursor='crosshair')
        self.cv.pack()
        self.cv.create_image(0, 0, image=self.tkimg, anchor='nw')
        self.cv.bind('<Button-1>', self.click)
        right = ttk.Frame(self, padding=10)
        right.pack(side='left', fill='y')
        P = app.P
        hs = [st[0] for st in P['colors']['stops']]
        self.land = tk.BooleanVar(value=bool(P['shape']['ocean']))
        top = max([h for h in hs if h > 0] + [float(P['relief']['high']) * 0.75])
        self.n = tk.IntVar(value=6)
        self.gain = tk.DoubleVar(value=1.0)
        self.box = tk.IntVar(value=4)
        self.h0 = tk.DoubleVar(value=0.0 if self.land.get() else min(hs))
        self.h1 = tk.DoubleVar(value=round(top))
        rows = [('Colours', self.n, 2, 16, 1), ('Brightness', self.gain, 0.5, 2.0, 0.02), ('Averaging (px)', self.box, 1, 16, 1),
                ('Low end height (m)', self.h0, -30000, 30000, 100), ('High end height (m)', self.h1, -30000, 30000, 100)]
        for i, (lab, var, lo, hi, inc) in enumerate(rows):
            ttk.Label(right, text=lab).grid(row=i, column=0, sticky='w', pady=3)
            sp = ttk.Spinbox(right, textvariable=var, from_=lo, to=hi, increment=inc, width=8, command=self.draw)
            sp.grid(row=i, column=1, padx=6, pady=3)
            sp.bind('<Return>', self.draw)
            sp.bind('<FocusOut>', self.draw)
        ttk.Checkbutton(right, text='Keep the colours below 0 m\n(the sea floor)', variable=self.land,
                        command=self.draw).grid(row=5, column=0, columnspan=2, sticky='w', pady=8)
        self.strip = tk.Canvas(right, width=90, height=300, bg=BG, highlightthickness=1, highlightbackground=LINE)
        self.strip.grid(row=6, column=0, columnspan=2, pady=8)
        bar = ttk.Frame(right)
        bar.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Button(bar, text='Clear', command=self.clear).pack(side='left')
        self.use_btn = ttk.Button(bar, text='Use these colours', style='Accent.TButton', command=self.use, state='disabled')
        self.use_btn.pack(side='left', padx=6)
        self.pts = []
        self.stripimg = None
        self.transient(app)

    def click(self, e):
        if len(self.pts) >= 2:
            self.pts = []
        self.pts.append((e.x / self.s, e.y / self.s))
        self.draw()

    def clear(self):
        self.pts = []
        self.draw()

    def compute(self):
        (x1, y1), (x2, y2) = self.pts
        n = max(2, min(16, int(self.n.get())))
        cols = sample_line(self.arr, x1, y1, x2, y2, n, float(self.gain.get()), max(1, int(self.box.get())))
        h0, h1 = float(self.h0.get()), float(self.h1.get())
        if self.land.get():
            h0 = max(h0, 0.0)
        if h1 <= h0:
            h1 = h0 + 100
        new = [[round(h0 + (h1 - h0) * i / (n - 1)), c] for i, c in enumerate(cols)]
        if self.land.get():
            keep = [copy.deepcopy(st) for st in self.app.P['colors']['stops'] if st[0] < min(0.0, h0)]
            new = keep + new
        return new

    def draw(self, _e=None):
        self.cv.delete('mark')
        for x, y in self.pts:
            self.cv.create_oval(x * self.s - 5, y * self.s - 5, x * self.s + 5, y * self.s + 5, outline=ACC, width=2, tags='mark')
        self.strip.delete('all')
        if len(self.pts) == 2:
            (x1, y1), (x2, y2) = self.pts
            self.cv.create_line(x1 * self.s, y1 * self.s, x2 * self.s, y2 * self.s, fill=ACC, width=2, dash=(6, 4), tags='mark')
            try:
                st = self.compute()
            except Exception:
                return
            hs = np.array([a[0] for a in st], float)
            cs = np.array([a[1] for a in st], float)
            yy = np.linspace(hs.max(), hs.min(), 300)
            img = np.stack([np.interp(yy, hs, cs[:, i]) for i in range(3)], -1)
            img = np.repeat(img[:, None, :], 90, 1)
            self.stripimg = ImageTk.PhotoImage(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)))
            self.strip.create_image(0, 0, image=self.stripimg, anchor='nw')
            self.use_btn.configure(state='normal')
        else:
            self.use_btn.configure(state='disabled')

    def use(self):
        st = self.compute()
        self.app.snapshot()
        self.app.P['colors']['stops'] = st
        self.app.refresh_all()
        self.app.changed()
        self.destroy()


class ExportDialog(tk.Toplevel):
    KINDS = (('height', 'Height map'), ('heightfine', 'Fine height map'), ('color', 'Colour map'),
             ('normal', 'Normal map'), ('emissive', 'Emissive map (glow)'), ('preview', 'Preview sheet'), ('config', 'Kopernicus config'),
             ('atmo', 'Scatterer config'), ('clouds', 'Clouds (EVE + TVC)'), ('aurora', 'Aurora (EVE)'), ('ring', 'Ring texture'))
    SIZES = ['Same as build', '8192 × 4096', '4096 × 2048', '2048 × 1024', '1024 × 512']

    def __init__(self, app, builds):
        super().__init__(app)
        self.app = app
        self.P = copy.deepcopy(app.P)
        self.name = self.P['name']
        self.builds = builds
        self.S = load_settings()
        self.title('Export – %s' % self.name)
        self.configure(bg=BG)
        self.transient(app)
        self.resizable(False, False)
        self.q = queue.Queue()
        f = ttk.Frame(self, padding=18)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Export %s' % self.name, style='Head.TLabel').grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))
        ttk.Label(f, text='From build').grid(row=1, column=0, sticky='w', pady=4)
        self.v_build = tk.StringVar()
        labels = ['%s × %d' % (r, int(r) // 2) for r in builds]
        cb = ttk.Combobox(f, textvariable=self.v_build, values=labels, width=14, state='readonly')
        cb.grid(row=1, column=1, sticky='w', pady=4)
        cb.bind('<<ComboboxSelected>>', lambda e: self.update_rows())
        pref = app.res.get()
        self.v_build.set(labels[builds.index(pref)] if pref in builds else labels[0])
        ttk.Label(f, text='Folder').grid(row=2, column=0, sticky='w', pady=4)
        self.v_dir = tk.StringVar(value=self.S.get('export_dir') or os.path.join(tr.TOOL, 'export'))
        ttk.Entry(f, textvariable=self.v_dir, width=52).grid(row=2, column=1, columnspan=2, sticky='we', pady=4)
        ttk.Button(f, text='Browse…', command=self.browse).grid(row=2, column=3, padx=(6, 0))
        ttk.Label(f, text='File name', style='Dim.TLabel').grid(row=3, column=1, sticky='w', pady=(12, 2))
        ttk.Label(f, text='Format', style='Dim.TLabel').grid(row=3, column=2, sticky='w', pady=(12, 2))
        self.rows = {}
        defaults = {'height': True, 'heightfine': True, 'color': True, 'normal': True, 'preview': False, 'config': True, 'atmo': True, 'aurora': True, 'emissive': True, 'clouds': True, 'ring': True}
        hstem = self.stem('height')
        names = {'height': hstem, 'heightfine': hstem + 'fine', 'color': self.stem('color'), 'normal': self.stem('normal'),
                 'preview': self.name + '_preview', 'config': self.name + '_kopernicus', 'atmo': self.name + '_atmo',
                 'aurora': self.name + '_aurora', 'emissive': self.stem('emissive'), 'clouds': self.name, 'ring': self.name + '_ring'}
        for i, (k, lab) in enumerate(self.KINDS):
            on = tk.BooleanVar(value=self.S.get('on_' + k, defaults[k]))
            chk = ttk.Checkbutton(f, text=lab, variable=on)
            chk.grid(row=4 + i, column=0, sticky='w', pady=3)
            v_name = tk.StringVar(value=names[k])
            ttk.Entry(f, textvariable=v_name, width=30).grid(row=4 + i, column=1, sticky='w', pady=3)
            fl = tr.EXPORT_FORMATS[k]
            v_fmt = tk.StringVar(value=self.S.get('fmt_' + k) if self.S.get('fmt_' + k) in fl else fl[0])
            fc = ttk.Combobox(f, textvariable=v_fmt, values=fl, width=27, state='readonly')
            fc.grid(row=4 + i, column=2, sticky='w', pady=3)
            note = ttk.Label(f, text='', style='Dim.TLabel')
            note.grid(row=4 + i, column=3, sticky='w', padx=(6, 0))
            self.rows[k] = (on, chk, v_name, v_fmt, note)
        r = 4 + len(self.KINDS)
        ttk.Label(f, text='Size').grid(row=r, column=0, sticky='w', pady=(12, 4))
        self.v_size = tk.StringVar(value=self.S.get('size') if self.S.get('size') in self.SIZES else self.SIZES[0])
        ttk.Combobox(f, textvariable=self.v_size, values=self.SIZES, width=14, state='readonly').grid(row=r, column=1, sticky='w', pady=(12, 4))
        self.v_flip = tk.BooleanVar(value=self.S.get('flip', True))
        ttk.Checkbutton(f, text='Flip DDS files upside down (KSP needs this)', variable=self.v_flip).grid(row=r + 1, column=0, columnspan=3, sticky='w', pady=4)
        r += 1
        ttk.Label(f, text='Path in config').grid(row=r + 1, column=0, sticky='w', pady=4)
        self.auto_cfg = tr.default_cfg_path(self.v_dir.get())
        self.v_cfg = tk.StringVar(value=self.S.get('cfg_path') or self.auto_cfg)
        ttk.Entry(f, textvariable=self.v_cfg, width=40).grid(row=r + 1, column=1, sticky='w', pady=4)
        ttk.Label(f, text='folder under GameData where the textures go', style='Dim.TLabel').grid(row=r + 1, column=2, columnspan=2, sticky='w', padx=(6, 0))
        ttk.Label(f, text='Height map: an 8-bit greyscale DDS like the ones Kopernicus’ VertexHeightMap reads. 8 bits only '
                          'give 256 height steps, so the fine height map holds what falls between the steps. Add it as a '
                          'second VertexHeightMap and the ground is smooth instead of terraced. The Kopernicus config '
                          'has both, with the right offset and deformity, plus the colour, normal and ocean parts. '
                          'Paste its nodes into your planet’s Body. The Scatterer config is the atmo.cfg for '
                          'Scatterer/Planets/<planet>/ in your mod, plus planetsList_<planet>.cfg, the entry that tells '
                          'Scatterer to draw the planet. The emissive map is the lava glow; the Kopernicus config adds it '
                          'as VertexColorMapEmissive (Lt_Duckweed’s 001_DuckweedUtils). The aurora is two textures (<name> and <name>_top) plus an EVE '
                          'config (<name>.cfg) with the layers; its size is set on the Aurora tab. The ring texture is a '
                          'strip with alpha; the Kopernicus config then also gets the Rings node.',
                  style='Dim.TLabel', wraplength=640, justify='left').grid(row=r + 2, column=0, columnspan=4, sticky='w', pady=(8, 0))
        self.stat = ttk.Label(f, text='', style='Dim.TLabel', wraplength=640, justify='left')
        self.stat.grid(row=r + 3, column=0, columnspan=4, sticky='w', pady=(10, 0))
        bar = ttk.Frame(f)
        bar.grid(row=r + 4, column=0, columnspan=4, sticky='e', pady=(14, 0))
        self.open_btn = ttk.Button(bar, text='Open folder', command=lambda: open_folder(self.v_dir.get()), state='disabled')
        self.open_btn.pack(side='left', padx=(0, 6))
        self.go_btn = ttk.Button(bar, text='Export', style='Accent.TButton', command=self.go)
        self.go_btn.pack(side='left', padx=(0, 6))
        self.close_btn = ttk.Button(bar, text='Close', command=self.destroy)
        self.close_btn.pack(side='left')
        self.update_rows()
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = app.winfo_rootx() + max(0, (app.winfo_width() - w) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - h) // 3)
        self.geometry('+%d+%d' % (x, y))
        self.grab_set()

    def stem(self, k):
        fn = self.P['files'].get(k) or ''
        return os.path.splitext(os.path.basename(fn))[0] if fn else '%s_%s' % (self.name, k)

    def res(self):
        return self.v_build.get().split(' ')[0]

    def src(self):
        return self.app.out_path(self.res())

    def update_rows(self):
        src = self.src()
        has = {'preview': os.path.isfile(os.path.join(src, self.name + '_preview.png')), 'atmo': tr.has_atmo(self.P),
               'aurora': tr.has_aurora(self.P), 'clouds': tr.has_clouds(self.P), 'emissive': os.path.isfile(os.path.join(src, self.name + '_emissive.png')),
               'ring': tr.has_rings(self.P) and os.path.isfile(os.path.join(src, self.name + '_ring.png'))}
        for k, (on, chk, v_name, v_fmt, note) in self.rows.items():
            if has.get(k, True):
                chk.state(['!disabled'])
                note.configure(text='')
            else:
                on.set(False)
                chk.state(['disabled'])
                note.configure(text={'atmo': 'no atmosphere', 'aurora': 'no aurora', 'clouds': 'no clouds', 'emissive': 'nothing glows in this build',
                                     'ring': 'no rings in this build' if tr.has_rings(self.P) else 'no rings'}.get(k, 'not in this build'))
        st = self.app.is_stale(self.res())
        self.stat.configure(text='Note: the settings changed after this build – the export shows the build, not the new settings.' if st else '')

    def browse(self):
        d = filedialog.askdirectory(parent=self, title='Export to folder', initialdir=self.v_dir.get() if os.path.isdir(self.v_dir.get()) else tr.TOOL)
        if d:
            self.v_dir.set(d)
            new = tr.default_cfg_path(d)
            if self.v_cfg.get().strip() in ('', self.auto_cfg) or tr.gamedata_rel(d):
                self.v_cfg.set(new)
            self.auto_cfg = new

    def go(self):
        folder = self.v_dir.get().strip()
        if not folder:
            messagebox.showerror('Folder', 'Please choose a folder.', parent=self)
            return
        jobs = []
        for k, (on, chk, v_name, v_fmt, note) in self.rows.items():
            if on.get():
                base = v_name.get().strip()
                if not base or any(ch in base for ch in '\\/:*?"<>|'):
                    messagebox.showerror('File name', 'Please give the %s a valid file name.' % dict(self.KINDS)[k].lower(), parent=self)
                    return
                jobs.append((k, base, v_fmt.get()))
        if not jobs:
            messagebox.showinfo('Nothing to export', 'Tick at least one file.', parent=self)
            return
        jobs.sort(key=lambda j: j[0] == 'config')
        targets = [tr.export_target(folder, b, fm) for _, b, fm in jobs]
        if any(k == 'atmo' for k, _, _ in jobs):
            targets.append(tr.planets_file(folder, self.name))
        for k, b, fm in jobs:
            if k == 'aurora':
                targets += list(tr.aurora_files(folder, b, fm))
            if k == 'clouds':
                cf = tr.cloud_files(folder, b, tr.cloud_entry(self.P.get('clouds')))
                targets += [cf['cfg']] + [v for n, d in cf.items() if n != 'cfg' for v in d.values()]
        exist = [t for t in targets if os.path.exists(t)]
        if exist and not messagebox.askyesno('Replace files?', 'These files already exist and will be replaced:\n\n' + '\n'.join(os.path.basename(x) for x in exist), parent=self):
            return
        sz = self.v_size.get()
        size = None if sz == self.SIZES[0] else int(sz.split(' ')[0])
        if size and size > int(self.res()):
            if not messagebox.askyesno('Bigger than the build', 'This stretches the %s build to %d. It will not gain any detail, '
                                       'it only gets bigger and softer.\n\nFor real detail, build at %d first.\n\nExport anyway?'
                                       % (self.res(), size, size), parent=self):
                return
        cfg = self.v_cfg.get().strip().replace('\\', '/').strip('/')
        self.S.update({'export_dir': folder, 'size': sz, 'flip': bool(self.v_flip.get()),
                       'cfg_path': '' if cfg == self.auto_cfg else cfg})
        for k, (on, chk, v_name, v_fmt, note) in self.rows.items():
            self.S['fmt_' + k] = v_fmt.get()
            if str(chk.state()).find('disabled') < 0:
                self.S['on_' + k] = bool(on.get())
        save_settings(self.S)
        self.go_btn.configure(state='disabled')
        self.close_btn.configure(state='disabled')
        self.stat.configure(text='Exporting…')
        src, name, P, flip = self.src(), self.name, self.P, bool(self.v_flip.get())

        def job():
            try:
                w = tr.export_maps(src, name, P, jobs, folder, size, flip, log=lambda m: self.q.put(('log', m)), cfg_path=cfg)
                self.q.put(('done', w))
            except Exception as ex:
                self.q.put(('err', str(ex)))
        threading.Thread(target=job, daemon=True).start()
        self.after(100, self.poll)

    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == 'log':
                    self.app.log(data)
                elif kind == 'done':
                    self.go_btn.configure(state='normal')
                    self.close_btn.configure(state='normal')
                    self.open_btn.configure(state='normal')
                    self.stat.configure(text='Exported %d file%s to %s' % (len(data), '' if len(data) == 1 else 's', self.v_dir.get()))
                    self.app.status('Exported %s' % self.name)
                    return
                else:
                    self.go_btn.configure(state='normal')
                    self.close_btn.configure(state='normal')
                    self.stat.configure(text='Export failed: ' + data)
                    return
        except queue.Empty:
            pass
        self.after(100, self.poll)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(tr.APP_NAME)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry('%dx%d+20+20' % (min(1520, sw - 60), min(940, sh - 90)))
        self.minsize(1100, 680)
        self.configure(bg=BG)
        make_style(self)
        self.P = tr.normalize({'name': 'NewWorld'})
        self.preset_file = None
        self.dirty = False
        self.sliders, self.editors, self.swatches, self.checks, self.combos = [], [], [], [], []
        self.proc = None
        self.q = queue.Queue()
        self.view_src = None
        self.pending = None
        self.redraw_id = None
        self.res = tk.StringVar(value='2048')
        self.view = tk.StringVar(value='live')
        self.show = tk.StringVar(value='Colour')
        self.stops_fn = lambda: self.P['colors']['stops']
        self.history = []
        st = load_settings()
        self.live_size = tk.StringVar(value=str(st.get('live_size', 512)) if str(st.get('live_size', 512)) in LIVE_RES else '512')
        self.live_lock = threading.Lock()
        self.live_q = queue.Queue()
        self.live_cache = {}
        self.live_gen = 0
        self.live_req = None
        self.live_thread = None
        self.live_last = None
        self.live_after = None
        self.live_err = None
        self.live_view = None
        self.rot = [0.0, 0.0]
        self.drag = None
        self.view_geom = None
        self.feat_type = tk.StringVar(value='Crater')
        self.place_mode = tk.BooleanVar(value=False)
        self.fdrag = None
        self.adrag = None
        self.atmo_lock = threading.Lock()
        self.atmo_q = queue.Queue()
        self.atmo_gen = 0
        self.atmo_req = None
        self.atmo_thread = None
        self.atmo_img = None
        self.atmo_key = None
        self.atmo_err = None
        self.atmo_texc = {}
        self.atmo_src = None
        self.ig_cache = {}
        self.aur_lock = threading.Lock()
        self.aur_q = queue.Queue()
        self.aur_gen = 0
        self.aur_req = None
        self.aur_thread = None
        self.aur_img = None
        self.aur_key = None
        self.aur_err = None
        self.cl_lock = threading.Lock()
        self.cl_q = queue.Queue()
        self.cl_gen = 0
        self.cl_req = None
        self.cl_thread = None
        self.cl_img = None
        self.cl_key = None
        self.cl_err = None
        self.cl_prog = None
        self.cl_dt = 0.0
        self.build_ui()
        self.after(150, self.live_poll)
        self.bind('<Control-z>', self.undo)
        names = self.preset_names()
        if names:
            self.load('Terran' if 'Terran' in names else names[0])
        else:
            self.refresh_all()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.set_icon(self)

    @staticmethod
    def set_icon(win):
        if os.name != 'nt':
            return
        for base in (getattr(sys, '_MEIPASS', ''), tr.TOOL):
            ico = os.path.join(base, 'icon.ico') if base else ''
            if ico and os.path.isfile(ico):
                try:
                    win.iconbitmap(ico)
                except Exception:
                    pass
                return

    def planet_colours(self):
        return [s[1] for s in self.P['colors']['stops']]

    def preset_names(self):
        os.makedirs(tr.PRESETS, exist_ok=True)
        return sorted(f[:-5] for f in os.listdir(tr.PRESETS) if f.endswith('.json'))

    def build_ui(self):
        top = ttk.Frame(self, style='Bar.TFrame', padding=(12, 8))
        top.pack(fill='x')
        ttk.Label(top, text=tr.APP_NAME, style='Title.TLabel').pack(side='left', padx=(0, 20))
        ttk.Label(top, text='Planet', style='BarDim.TLabel').pack(side='left')
        self.pick = ttk.Combobox(top, state='readonly', width=22)
        self.pick.pack(side='left', padx=6)
        self.pick.bind('<<ComboboxSelected>>', self.on_pick)
        ttk.Button(top, text='New…', command=self.new).pack(side='left', padx=2)
        ttk.Button(top, text='Save', command=lambda: self.save()).pack(side='left', padx=2)
        ttk.Button(top, text='Save as…', command=self.save_as).pack(side='left', padx=2)
        ttk.Button(top, text='Open output folder', command=self.open_out).pack(side='right')
        self.undo_btn = ttk.Button(top, text='Undo', command=self.undo, state='disabled')
        self.undo_btn.pack(side='left', padx=(18, 2))
        ttk.Button(top, text='Surprise me', command=lambda: self.randomize('all')).pack(side='left', padx=2)
        pw = ttk.PanedWindow(self, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw, padding=(8, 4, 0, 8))
        right = ttk.Frame(pw, padding=(8, 8, 12, 8))
        pw.add(left, weight=0)
        pw.add(right, weight=1)
        self.nb = ttk.Notebook(left, width=600)
        self.nb.pack(fill='both', expand=True)
        self.tab_shape()
        self.tab_relief()
        self.tab_landforms()
        self.tab_craters()
        self.tab_lava()
        self.tab_features()
        self.tab_colours()
        self.tab_atmo()
        self.tab_clouds()
        self.tab_aurora()
        self.tab_rings()
        self.tab_body()
        vb = ttk.Frame(right)
        vb.pack(fill='x')
        self.export_btn = ttk.Button(vb, text='Export…', command=self.export)
        self.export_btn.pack(side='right')
        for val, txt in (('live', 'Live preview'), ('atmo', 'In game'), ('clouds', 'Clouds'), ('aurora', 'Aurora'), ('preview', 'Sheet'), ('flat', 'Flat map')):
            ttk.Radiobutton(vb, text=txt, value=val, variable=self.view, style='Toolbutton',
                            command=self.update_view).pack(side='left', padx=(0, 3))
        tb = ttk.Frame(right)
        tb.pack(fill='x', pady=(6, 0))
        ttk.Label(tb, text='Show', style='Dim.TLabel').pack(side='left', padx=(0, 4))
        scb = ttk.Combobox(tb, textvariable=self.show, values=['Colour', 'Height', 'Colour, no shading'], width=17, state='readonly')
        scb.pack(side='left')
        scb.bind('<<ComboboxSelected>>', lambda e: self.update_view(from_live=True))
        lcb = ttk.Combobox(tb, textvariable=self.live_size, values=LIVE_RES, width=5, state='readonly')
        lcb.pack(side='left', padx=(8, 8))
        lcb.bind('<<ComboboxSelected>>', self.live_size_changed)
        fcb = ttk.Combobox(tb, textvariable=self.feat_type, values=FEAT_NAMES, width=9, state='readonly')
        fcb.pack(side='right')
        ttk.Checkbutton(tb, text='Place features', variable=self.place_mode, style='Toolbutton',
                        command=self.place_toggled).pack(side='right', padx=(0, 4))
        self.canvas = tk.Canvas(right, bg='#0d0f14', highlightthickness=1, highlightbackground=LINE)
        self.canvas.pack(fill='both', expand=True, pady=(8, 4))
        self.canvas.bind('<Configure>', lambda e: self.schedule_redraw())
        self.canvas.bind('<ButtonPress-1>', self.drag_start)
        self.canvas.bind('<B1-Motion>', self.drag_move)
        self.canvas.bind('<ButtonRelease-1>', self.drag_end)
        self.canvas.bind('<Double-Button-1>', self.drag_reset)
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Leave>', lambda e: self.hover_lab.configure(text=''))
        self.canvas.bind('<Button-3>', self.feature_remove_click)
        hl = ttk.Frame(right)
        hl.pack(fill='x')
        self.live_lab = ttk.Label(hl, text='', style='Dim.TLabel')
        self.live_lab.pack(side='right')
        self.hover_lab = ttk.Label(hl, text='', style='Dim.TLabel', font=(MONO, 9))
        self.hover_lab.pack(side='left', fill='x', expand=True)
        sb = ttk.Frame(right)
        sb.pack(fill='x', pady=(4, 0))
        ttk.Label(sb, text='Resolution', style='Dim.TLabel').pack(side='left')
        ttk.Combobox(sb, textvariable=self.res, values=RES, width=7, state='readonly').pack(side='left', padx=6)
        self.res.trace_add('write', lambda *a: (self.update_view(), self.update_res_info()))
        self.build_btn = ttk.Button(sb, text='Build', style='Accent.TButton', command=self.build)
        self.build_btn.pack(side='left')
        self.cancel_btn = ttk.Button(sb, text='Cancel', command=self.cancel, state='disabled')
        self.cancel_btn.pack(side='left', padx=6)
        self.prog = ttk.Progressbar(sb, mode='determinate', maximum=100)
        self.prog.pack(side='left', fill='x', expand=True, padx=(6, 0))
        self.res_info = ttk.Label(right, text='', style='Dim.TLabel', wraplength=820, justify='left')
        self.res_info.pack(fill='x', pady=(6, 0))
        self.stat = ttk.Label(right, text='Ready', style='Dim.TLabel')
        self.stat.pack(fill='x', pady=(2, 0))
        self.logbox = tk.Text(right, height=6, bg=FIELD, fg=DIM, insertbackground=FG, relief='flat',
                              font=(MONO, 9), state='disabled', wrap='none')
        self.logbox.pack(fill='x', pady=(6, 0))

    def rand_bar(self, parent, text, what, hint):
        r = ttk.Frame(parent)
        r.pack(fill='x', pady=(2, 0))
        ttk.Button(r, text=text, command=lambda: self.randomize(what)).pack(side='left', padx=(0, 8))
        ttk.Label(r, text=hint, style='Dim.TLabel').pack(side='left')

    def section(self, parent, text):
        ttk.Label(parent, text=text, style='Head.TLabel').pack(anchor='w', pady=(12, 4))

    def note(self, parent, text):
        ttk.Label(parent, text=text, style='Dim.TLabel', wraplength=540, justify='left').pack(anchor='w')

    def grid_box(self, parent):
        g = ttk.Frame(parent)
        g.pack(fill='x')
        g.columnconfigure(1, weight=1)
        return g

    def check(self, parent, text, path):
        v = tk.BooleanVar()

        def flip():
            self.snapshot()
            setp(self.P, path, bool(v.get()))
            self.changed()
        cb = ttk.Checkbutton(parent, text=text, variable=v, command=flip)
        self.checks.append((v, path))
        return cb

    def swatch_row(self, parent, items):
        r = ttk.Frame(parent)
        r.pack(fill='x', pady=(6, 0))
        for i, (lab, path) in enumerate(items):
            ttk.Label(r, text=lab).pack(side='left', padx=(8 if i == 0 else 22, 10))
            Swatch(self, r, path).lab.pack(side='left')
        return r

    def tab_shape(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Shape')
        p = sf.inner
        self.rand_bar(p, 'Randomize shape', 'shape', 'new continents (new seed) and coastlines')
        self.section(p, 'Land and sea')
        self.check(p, 'Ocean (fill everything below 0 m with water)', ('shape', 'ocean')).pack(anchor='w', padx=8, pady=(0, 4))
        self.note(p, 'Without an ocean, “land” means the highlands and the rest are low basins.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Land amount', ('shape', 'land'), 0.02, 0.98, 0.01, tip='share of the surface above 0 m')
        Slider(self, g, 2, 'Continents', ('shape', 'continents'), 0, 12, 1, isint=True, tip='0 = random shapes without set continents')
        Slider(self, g, 4, 'Twist', ('shape', 'warp'), 0, 2, 0.05, tip='how bent and stretched the land masses are')
        Slider(self, g, 6, 'Continent size variety', ('shape', 'size_var'), 0, 0.9, 0.02, tip='0 = all about the same size, high = a few big ones and some small ones')
        Slider(self, g, 8, 'Land near poles ↔ equator', ('shape', 'bias'), -1, 1, 0.02, tip='negative = more land near the poles, positive = more near the equator')
        self.section(p, 'Coasts')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Coast roughness', ('shape', 'coast'), 0, 1, 0.02, tip='smooth shores ↔ ragged bays and peninsulas')
        Slider(self, g, 2, 'Islands', ('shape', 'islands'), 0, 1, 0.02)

    def tab_relief(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Relief')
        p = sf.inner
        self.rand_bar(p, 'Randomize relief', 'relief', 'new mountain, hill and plains settings')
        self.section(p, 'Height range')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Highest point (m)', ('relief', 'high'), 200, 25000, 50, tip='roughly the tallest mountains, before craters')
        Slider(self, g, 2, 'Lowest point (m)', ('relief', 'low'), -25000, -50, 50, tip='deepest ocean or lowest basin')
        self.section(p, 'Mountains')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Mountains', ('relief', 'mountains'), 0, 1.5, 0.02)
        Slider(self, g, 1, 'Mountain size', ('relief', 'mountain_size'), 0.3, 3, 0.05, tip='bigger = wider ranges with fewer, larger peaks')
        Slider(self, g, 3, 'Mountain area', ('relief', 'mountain_area'), 0, 1, 0.02)
        Slider(self, g, 4, 'Ranges along coasts', ('relief', 'ranges'), 0, 1, 0.02, tip='mountains that follow the coasts, like the Andes')
        Slider(self, g, 6, 'Sharpness', ('relief', 'sharpness'), 0.4, 3, 0.05, tip='low = rounded old mountains, high = sharp jagged peaks')
        self.section(p, 'Hills and plains')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Hills', ('relief', 'hills'), 0, 1.5, 0.02)
        Slider(self, g, 1, 'Hill size', ('relief', 'hill_size'), 0.3, 3, 0.05)
        Slider(self, g, 2, 'Flat plains', ('relief', 'plains'), 0, 1, 0.02, tip='smooths hills and mountains away in large areas')
        Slider(self, g, 4, 'Fine roughness', ('relief', 'roughness'), 0, 1.5, 0.02)
        self.section(p, 'Sea floor')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Shelf width', ('relief', 'shelf'), 0, 1, 0.02, tip='shallow sea around the coasts before the deep ocean')
        self.section(p, 'Normal map')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Relief strength', ('normal_strength',), 0, 12, 0.1, tip='how strong the bumps look in the preview')
        Slider(self, g, 2, 'Normal map scale', ('normal_scale',), 0, 255, 0.5, tip='like the Scale in GIMP’s Normal Map filter (default 10)')
        ttk.Label(g, text='The exported normal map is made the way GIMP’s Filters → Generic → Normal Map makes it from the height map.',
                  style='Dim.TLabel', wraplength=520, justify='left').grid(row=4, column=0, columnspan=3, sticky='w', padx=(8, 0), pady=(4, 0))

    def tab_landforms(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Landforms')
        p = sf.inner
        self.rand_bar(p, 'Randomize landforms', 'landforms', 'new plateaus, canyons, ridges, rivers, cracks and volcanoes')
        self.section(p, 'Rivers and valleys')
        self.note(p, 'Water runs downhill from every bit of land, gathers into rivers and ends in the sea (or the lowest '
                     'basins on a dry world). Rivers cut a channel and a valley around it. The network is worked out '
                     'on a 512 × 256 version of the planet, so it stays the same at every build size; changing the '
                     'shape or relief re-routes it (about 1–2 s).')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Rivers', ('water', 'rivers'), 0, 1, 0.02, tip='0 = none, low = only the big rivers, high = many small streams too')
        Slider(self, g, 2, 'River width (km)', ('water', 'width'), 0.2, 60, 0.1, tip='at the source; rivers get wider downstream')
        Slider(self, g, 4, 'River depth (m)', ('water', 'depth'), 0, 2000, 5)
        Slider(self, g, 5, 'Valleys', ('water', 'valleys'), 0, 1, 0.02, tip='how deep the land is worn down around the rivers')
        Slider(self, g, 7, 'Valley width (× river)', ('water', 'valley_width'), 1, 40, 0.5)
        Slider(self, g, 8, 'River colour amount', ('colors', 'river_amount'), 0, 1, 0.02, tip='0 = only the carved valleys show')
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Label(r, text='River colour').pack(side='left', padx=(8, 10))
        OptSwatch(self, r, ('colors', 'river_color'), [52, 118, 138], 'auto = shallow water colour, or a darker ground on a dry world').frame.pack(side='left')
        self.section(p, 'Plateaus')
        self.note(p, 'Big raised tablelands with flat tops and steep, ragged edges, like mesas. On an ocean world only on land.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Plateaus', ('plateaus', 'amount'), 0, 1, 0.02, tip='0 = none, higher = more of the surface')
        Slider(self, g, 2, 'Height (m)', ('plateaus', 'height'), 0, 15000, 50)
        Slider(self, g, 3, 'Size', ('plateaus', 'size'), 0.3, 3, 0.05)
        Slider(self, g, 4, 'Edge steepness', ('plateaus', 'edge'), 0, 1, 0.02, tip='low = gentle slopes up, high = cliffs')
        Slider(self, g, 6, 'Flat tops', ('plateaus', 'flat'), 0, 1, 0.02, tip='how much of the hills and mountains on top are smoothed away')
        self.section(p, 'Canyons')
        self.note(p, 'Big rift valleys with flat floors and ragged walls, like Valles Marineris. They taper off at both ends.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Canyons', ('relief', 'canyons'), 0, 1, 0.02, tip='0 = none, higher = more and longer canyons')
        Slider(self, g, 2, 'Depth (m)', ('relief', 'canyon_depth'), 0, 15000, 50)
        Slider(self, g, 3, 'Width (km)', ('relief', 'canyon_width'), 2, 800, 1)
        self.section(p, 'Equatorial ridge')
        self.note(p, 'One long mountain wall running around the planet, like the ridge on Iapetus or the ones that make '
                     'Pan and Atlas look like walnuts. Craters still cut into it.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Height (m)', ('ridge', 'height'), 0, 30000, 100, tip='0 = no ridge')
        Slider(self, g, 2, 'Width (km)', ('ridge', 'width'), 1, 1500, 1, tip='at the foot of the main wall')
        Slider(self, g, 4, 'Length (° around)', ('ridge', 'coverage'), 5, 360, 1, tip='360 = all the way around, less = an arc that fades out at both ends')
        Slider(self, g, 6, 'Centre longitude (°)', ('ridge', 'lon'), 0, 360, 1, tip='middle of the arc, and the point the tilt turns around')
        Slider(self, g, 8, 'Latitude shift (°)', ('ridge', 'lat'), -60, 60, 0.5, tip='moves the whole ridge north (+) or south (−)')
        Slider(self, g, 10, 'Tilt (°)', ('ridge', 'tilt'), -60, 60, 0.5, tip='tilts the ridge against the equator')
        Slider(self, g, 12, 'Gaps', ('ridge', 'segments'), 0, 1, 0.02, tip='0 = one unbroken wall, higher = broken into shorter pieces')
        Slider(self, g, 14, 'Ragged', ('ridge', 'ragged'), 0, 1, 0.02, tip='how much the height, width and crest vary along the ridge')
        Slider(self, g, 16, 'Wander', ('ridge', 'wander'), 0, 1, 0.02, tip='0 = a clean line, higher = weaves north and south')
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Button(r, text='New ridge shape', command=self.ridge_seed).pack(side='left', padx=8)
        self.section(p, 'Cracks')
        self.note(p, 'For icy moons and cracked crusts: long crossing lines like Europa’s, or a network of polygon cells. '
                     'Each crack is a groove, with raised edges if you like, and its own colour.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Cracks', ('cracks', 'amount'), 0, 1, 0.02, tip='0 = none, higher = longer lines / more of the cells')
        self.combo(g, 2, 'Kind', ('cracks', 'style'), [('lines', 'Long lines'), ('cells', 'Polygon cells')])
        Slider(self, g, 3, 'Lines', ('cracks', 'count'), 1, 16, 1, isint=True, tip='long lines only')
        Slider(self, g, 5, 'Bend', ('cracks', 'curvy'), 0, 1, 0.02, tip='long lines only: 0 = straight arcs')
        Slider(self, g, 7, 'Cell size (km)', ('cracks', 'cell_size'), 5, 3000, 5, tip='polygon cells only')
        Slider(self, g, 9, 'Width (km)', ('cracks', 'width'), 0.2, 100, 0.1)
        Slider(self, g, 10, 'Depth (m)', ('cracks', 'depth'), 0, 5000, 10)
        Slider(self, g, 11, 'Raised edges', ('cracks', 'ridges'), 0, 1.5, 0.02, tip='ridges along both sides of each crack')
        Slider(self, g, 13, 'Crack colour amount', ('colors', 'crack_amount'), 0, 1, 0.02)
        self.swatch_row(p, [('Crack colour', ('colors', 'crack_color'))])
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Button(r, text='New crack pattern', command=self.crack_seed).pack(side='left', padx=8)
        self.section(p, 'Volcanoes')
        self.note(p, 'Big shield volcanoes with a crater at the top, scattered at random. Place your own on the Features tab.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Count', ('volcanoes', 'count'), 0, 40, 1, isint=True)
        Slider(self, g, 1, 'Size (km wide)', ('volcanoes', 'size_km'), 5, 2000, 5)
        Slider(self, g, 2, 'Height (m)', ('volcanoes', 'height'), 100, 30000, 100)
        Slider(self, g, 3, 'Summit crater', ('volcanoes', 'caldera'), 0, 1, 0.02)
        Slider(self, g, 4, 'Size variety', ('volcanoes', 'size_var'), 0, 0.9, 0.02)
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Button(r, text='New volcano places', command=self.volcano_seed).pack(side='left', padx=8)

    def combo(self, parent, row, label, path, options):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(8, 8), pady=(4, 0))
        var = tk.StringVar()
        names = [n for _, n in options]
        cb = ttk.Combobox(parent, textvariable=var, values=names, width=16, state='readonly')
        cb.grid(row=row, column=1, sticky='w', pady=(4, 0))

        def sel(_e=None):
            v = dict((n, k) for k, n in options).get(var.get())
            if v is not None and v != getp(self.P, path):
                self.snapshot()
                setp(self.P, path, v)
                self.changed()
        cb.bind('<<ComboboxSelected>>', sel)
        self.combos.append((var, path, dict(options)))

    def tab_rings(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Rings')
        self.rings_tab = sf
        p = sf.inner
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(2, 0))
        self.ring_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text='This planet has rings', variable=self.ring_on, command=self.ring_toggle).pack(side='left')
        ttk.Button(top, text='Randomize rings', command=lambda: self.randomize('rings')).pack(side='right')
        ttk.Button(top, text='New pattern', command=self.ring_new_pattern).pack(side='right', padx=6)
        self.ring_cv = tk.Canvas(p, width=560, height=300, bg='#0d0f14', highlightthickness=1, highlightbackground=LINE)
        self.ring_cv.pack(anchor='w', pady=(8, 4))
        self.ring_strip = tk.Canvas(p, width=560, height=24, bg='#0d0f14', highlightthickness=1, highlightbackground=LINE)
        self.ring_strip.pack(anchor='w')
        lr = ttk.Frame(p)
        lr.pack(fill='x')
        ttk.Label(lr, text='inner edge', style='Dim.TLabel').pack(side='left')
        ttk.Label(lr, text='outer edge', style='Dim.TLabel').pack(side='left', padx=(450, 0))
        self.note(p, 'The picture uses the live preview’s colour map (turn on Live preview once to fill it).')
        self.section(p, 'Size and tilt')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Inner edge (planet radii)', ('rings', 'inner'), 1.0, 6.0, 0.01)
        Slider(self, g, 1, 'Outer edge (planet radii)', ('rings', 'outer'), 1.1, 10.0, 0.01)
        Slider(self, g, 2, 'Tilt (°)', ('rings', 'angle'), 0, 90, 0.5, tip='against the equator; goes into the config as angle')
        Slider(self, g, 4, 'View from (°)', ('rings', 'view'), 2, 80, 1, tip='only for this picture')
        self.section(p, 'Structure')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Wide zones', ('rings', 'zones'), 1, 8, 1, isint=True)
        Slider(self, g, 1, 'Ringlets', ('rings', 'ringlets'), 0, 1, 0.05)
        Slider(self, g, 2, 'Ringlet detail', ('rings', 'detail'), 0.3, 3, 0.05)
        Slider(self, g, 3, 'Opacity', ('rings', 'opacity'), 0, 1, 0.05)
        Slider(self, g, 4, 'Soft edges', ('rings', 'edge'), 0, 1, 0.05)
        Slider(self, g, 5, 'Colour variation', ('rings', 'variation'), 0, 1, 0.05)
        self.section(p, 'Gaps')
        ttk.Label(p, text='Position 0 = inner edge, 1 = outer edge. Width in the same units. Depth 1 = empty.',
                  style='Dim.TLabel', wraplength=520).pack(anchor='w')
        ge = ListEditor(self, p, lambda: self.P['rings']['gaps'],
                        [num('Position', 0, 0, 1, 0.005, '%.3f', width=8), num('Width', 1, 0.001, 0.3, 0.001, '%.3f', width=8),
                         num('Depth', 2, 0, 1, 0.05, '%.2f')],
                        lambda: [round(random.uniform(0.2, 0.9), 3), 0.01, 1.0], add_text='Add gap')
        ge.frame.pack(fill='x', pady=6)
        self.gap_ed = ge
        ttk.Button(ge.bar, text='Random gaps', command=self.ring_random_gaps).pack(side='left', padx=6)
        self.section(p, 'Colours')
        ttk.Label(p, text='Left on auto, the ring colours come from the planet’s colour stops.', style='Dim.TLabel').pack(anchor='w')
        self.ring_cols = ttk.Frame(p)
        self.ring_cols.pack(fill='x', pady=(4, 0))
        self.section(p, 'Texture and Kopernicus config')
        g = ttk.Frame(p)
        g.pack(fill='x')
        ttk.Label(g, text='Texture width').pack(side='left', padx=(8, 8))
        self.ring_size = tk.StringVar(value='2048')
        rc = ttk.Combobox(g, textvariable=self.ring_size, values=['1024', '2048', '4096'], width=6, state='readonly')
        rc.pack(side='left')
        rc.bind('<<ComboboxSelected>>', self.ring_size_changed)
        ttk.Label(p, text='Build writes the ring texture with the other maps; Export saves it as DDS (BC3 / DXT5 with '
                          'alpha, or BC7) or PNG and adds the Rings node to the Kopernicus config. The left end of the '
                          'file is the outer edge of the ring, which is how Kopernicus maps it. Or paste this into the '
                          'planet’s Body node:',
                  style='Dim.TLabel', wraplength=520, justify='left').pack(anchor='w', pady=(6, 4))
        self.ring_cfg = tk.Text(p, height=13, width=64, bg=FIELD, fg=FG, insertbackground=FG, relief='flat', font=(MONO, 9))
        self.ring_cfg.pack(anchor='w')
        ttk.Button(p, text='Copy config', command=self.ring_copy).pack(anchor='w', pady=(6, 0))
        self.swatches.append(type('R', (), {'refresh': lambda s=None: self.ring_refresh()})())
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.ring_schedule(), add='+')

    def ring_visible(self):
        try:
            return self.nb.select() == str(self.rings_tab)
        except (tk.TclError, AttributeError):
            return False

    def ring_schedule(self, delay=150):
        if not self.ring_visible():
            return
        if getattr(self, 'ring_after', None):
            self.after_cancel(self.ring_after)
        self.ring_after = self.after(delay, self.ring_draw)

    def ring_refresh(self):
        r = self.P['rings']
        self.ring_on.set(bool(r.get('enabled')))
        self.ring_size.set(str(r.get('size', 2048)))
        for w in self.ring_cols.winfo_children():
            w.destroy()
        for i, (k, lab) in enumerate((('inner_color', 'Inner'), ('middle_color', 'Middle'), ('outer_color', 'Outer'))):
            ttk.Label(self.ring_cols, text=lab).grid(row=0, column=i * 2, sticky='w', padx=(8, 6))
            self.ring_colour_pick(self.ring_cols, k).grid(row=0, column=i * 2 + 1, sticky='w', padx=(0, 18))
        self.ring_text()
        self.ring_schedule(10)

    def ring_colour_pick(self, parent, k):
        fr = ttk.Frame(parent)
        r = self.P['rings']
        auto = tr.ring_colours(self.P, tr.ring_entry(r))[('inner_color', 'middle_color', 'outer_color').index(k)]
        auto = [int(round(float(v))) for v in auto]
        lab = tk.Label(fr, bg=hexcol(r.get(k) or auto), width=6, relief='solid', bd=1, cursor='hand2')
        lab.pack(side='left')

        def pick(_e=None):
            old = copy.deepcopy(r.get(k))

            def live(v):
                r[k] = v
                lab.configure(bg=hexcol(v))
                self.changed()

            def restore():
                r[k] = old
            c = pick_colour(self, old or auto, live=live, restore=restore)
            if c:
                r[k] = c
            self.ring_refresh()
            self.changed()

        def reset():
            r[k] = None
            self.ring_refresh()
            self.changed()
        lab.bind('<Button-1>', pick)
        if r.get(k):
            ttk.Button(fr, text='↺', width=2, style='Small.TButton', command=reset).pack(side='left', padx=(4, 0))
        else:
            ttk.Label(fr, text='auto', style='Dim.TLabel').pack(side='left', padx=(6, 0))
        return fr

    def ring_path(self):
        S = load_settings()
        cfg = (S.get('cfg_path') or tr.default_cfg_path(S.get('export_dir') or os.path.join(tr.TOOL, 'export'))).strip().replace('\\', '/').strip('/')
        return (cfg + '/' if cfg else '') + self.P['name'] + '_ring'

    def ring_text(self):
        self.ring_cfg.configure(state='normal')
        self.ring_cfg.delete('1.0', 'end')
        self.ring_cfg.insert('1.0', tr.ring_snippet(self.P, self.ring_path()))
        self.ring_cfg.configure(state='disabled')

    def ring_copy(self):
        self.clipboard_clear()
        self.clipboard_append(tr.ring_snippet(self.P, self.ring_path()))
        self.status('Ring config copied')

    def ring_draw(self):
        self.ring_after = None
        try:
            e = tr.ring_entry(self.P['rings'])
            col, a = tr.ring_profile(self.P, 1024)
            L = self.live_last
            if L is not None:
                tex = np.clip(L['col'].astype(np.float32) * tr.shade_map(L['gx'], L['gy'], float(self.P['normal_strength']))[..., None], 0, 255).astype(np.uint8)
            else:
                st = self.P['colors']['stops']
                mid = st[len(st) // 2][1]
                tex = np.broadcast_to(np.array(mid, np.uint8), (256, 512, 3))
            img = tr.ring_scene(tex, col, a, e)
            if not e['enabled']:
                img = Image.blend(img, Image.new('RGB', img.size, (13, 15, 20)), 0.55)
                d = ImageDraw.Draw(img)
                d.text((12, 10), 'Rings are off – tick “This planet has rings”', fill=(220, 225, 235), font=sheet_font(15))
            self.ring_img = ImageTk.PhotoImage(img)
            self.ring_cv.delete('all')
            self.ring_cv.create_image(0, 0, image=self.ring_img, anchor='nw')
            stp = np.concatenate([col, (a * 255)[:, None]], 1)
            ch = np.array([13, 15, 20], np.float32)
            rgb = stp[:, :3] * (stp[:, 3:] / 255) + ch * (1 - stp[:, 3:] / 255)
            strip = Image.fromarray(np.repeat(rgb[None], 24, 0).clip(0, 255).astype(np.uint8)).resize((560, 24), Image.LANCZOS)
            self.ring_strip_img = ImageTk.PhotoImage(strip)
            self.ring_strip.delete('all')
            self.ring_strip.create_image(0, 0, image=self.ring_strip_img, anchor='nw')
        except Exception as ex:
            self.ring_cv.delete('all')
            self.ring_cv.create_text(280, 150, text='Could not draw the rings: %s' % ex, fill=DIM)
        self.ring_text()

    def ring_toggle(self):
        self.snapshot()
        self.P['rings']['enabled'] = bool(self.ring_on.get())
        self.changed()

    def ring_size_changed(self, _e=None):
        self.P['rings']['size'] = int(self.ring_size.get())
        self.changed()

    def ring_new_pattern(self):
        self.snapshot()
        self.P['rings']['pattern'] = int(self.P['rings'].get('pattern', 0)) + 1
        self.changed()
        self.ring_schedule(10)

    def ring_random_gaps(self):
        self.snapshot()
        k = random.randint(1, 4)
        gaps = [[round(random.uniform(0.35, 0.75), 3), round(random.uniform(0.02, 0.05), 3), round(random.uniform(0.85, 1.0), 2)]]
        for _ in range(k - 1):
            gaps.append([round(random.uniform(0.12, 0.96), 3), round(random.uniform(0.003, 0.012), 3), round(random.uniform(0.6, 1.0), 2)])
        self.P['rings']['gaps'] = sorted(gaps)
        self.gap_ed.rebuild()
        self.changed()
        self.ring_schedule(10)

    def crack_seed(self):
        self.snapshot()
        self.P['cracks']['seed'] = random.randint(1, 99999)
        self.changed()

    def ridge_seed(self):
        self.snapshot()
        self.P['ridge']['seed'] = random.randint(1, 99999)
        self.changed()

    def tab_craters(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Craters')
        p = sf.inner
        self.rand_bar(p, 'Randomize craters', 'craters', 'new crater pattern and settings')
        self.section(p, 'Craters')
        self.note(p, 'Many small ones, few big ones, like real cratered worlds. Rims are soft, never outlined. '
                     'Craters smaller than about a pixel are left out of the smaller previews.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Count', ('craters', 'count'), 0, 20000, 50, isint=True, tip='0 = no craters')
        Slider(self, g, 2, 'Smallest (km wide)', ('craters', 'min_km'), 0.2, 50, 0.1)
        Slider(self, g, 3, 'Largest (km wide)', ('craters', 'max_km'), 1, 1500, 1)
        Slider(self, g, 4, 'Small vs big', ('craters', 'size_mix'), 1.0, 3.0, 0.05, tip='higher = more small craters, fewer big ones')
        Slider(self, g, 6, 'Depth', ('craters', 'depth'), 0, 2.5, 0.05, tip='1 = about as deep as real craters of that size')
        self.section(p, 'Age')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Fresh craters', ('craters', 'fresh'), 0, 1, 0.02, tip='0 = all old and worn down, 1 = all sharp and young')
        Slider(self, g, 2, 'Bright ejecta', ('craters', 'ejecta'), 0, 1, 0.02, tip='light blankets around young craters')
        Slider(self, g, 4, 'Ray streaks', ('craters', 'rays'), 0, 1, 0.02, tip='how much of the ejecta runs out in soft rays')
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(10, 0))
        ttk.Button(r, text='New crater pattern', command=self.crater_seed).pack(side='left', padx=8)
        self.section(p, 'Crater colours')
        self.note(p, 'Also used by the craters and basins you place yourself. Click a colour box to change it.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Floor colour amount', ('colors', 'crater_floor_amount'), 0, 1, 0.02, tip='dark (or light) floors, strongest in big craters and basins')
        self.swatch_row(p, [('Floor colour', ('colors', 'crater_floor'))])
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Label(r, text='Ejecta colour').pack(side='left', padx=(8, 10))
        OptSwatch(self, r, ('colors', 'ejecta_color'), [214, 210, 202], 'auto = a lighter version of the ground').frame.pack(side='left')

    LAVA_MODE_NAMES = (('star', 'Star-facing side'), ('all', 'All over'))
    LAVA_STYLE_NAMES = (('plates', 'Torn plates'), ('flowed', 'Flowed and cooled'))

    def tab_lava(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Lava')
        p = sf.inner
        A = ('lava',)
        self.section(p, 'Lava plates')
        self.note(p, 'Everything that glows ends up in one emissive map: the lava plates, a lava ocean, and glowing '
                     'cracks and volcanoes further down.')
        self.note(p, 'A crust torn into plates with glowing lava between them, like the worlds close to their star: '
                     'the plates get smaller and the lava channels wider towards the hottest point, where the crust '
                     'is melted into an open lava sea with floating rafts. “All over” tears the whole crust, for '
                     'tidally heated moons. The glow is written as an emissive map.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Amount', A + ('amount',), 0, 1, 0.01, tip='0 = no lava plates')
        self.combo(g, 2, 'Style', A + ('style',), list(self.LAVA_STYLE_NAMES))
        ttk.Label(g, text='Torn plates: the settings below. Flowed and cooled: the “Flowed lava” part.',
                  style='Dim.TLabel', font=(FONT, 8)).grid(row=3, column=0, columnspan=3, sticky='w', padx=(8, 0))
        self.combo(g, 4, 'Where', A + ('mode',), list(self.LAVA_MODE_NAMES))
        Slider(self, g, 5, 'Seed', A + ('seed',), 1, 999, 1, isint=True, tip='a new pattern of plates, or of the flow')
        self.section(p, 'Flowed lava')
        self.note(p, 'For the style “Flowed and cooled”, like Anneheg in the Kcalbeloh System. The lava fills the low '
                     'ground: everything below the lava level, or the whole sea when the planet has an ocean (the '
                     'Kopernicus config then writes the ocean in the lava colours). Its surface is worked out as if '
                     'it had really flowed: currents, eddies and streams along the shores stretch it into streaks and '
                     'fold it into swirls. Where it is still molten it glows, red at the shore and hotter further out, '
                     'with floes of crust on it; everywhere else it has cooled into rock that keeps the flow lines. '
                     'Amount = how molten it is. Changing the flow works the currents out again (a second or two).')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Lava level (m)', A + ('level',), -15000, 15000, 10, tip='without an ocean: lava fills everything below this height, with a flat surface')
        Slider(self, g, 2, 'Flow', A + ('flow',), 0, 3, 0.05, tip='how far the lava has flowed: low = soft streaks, high = folded swirls')
        Slider(self, g, 4, 'Eddy size', A + ('flow_size',), 0.2, 5, 0.05, tip='size of the currents and swirls')
        Slider(self, g, 5, 'Along the shores', A + ('shore_flow',), 0, 2, 0.05, tip='how much the lava streams along the coasts and around the highlands')
        Slider(self, g, 7, 'Hot from the shore (km)', A + ('heat_km',), 1, 1000, 1, tip='how far out the lava gets hotter; small seas stay redder')
        Slider(self, g, 9, 'Crust floes', A + ('floes',), 0, 1, 0.01, tip='dark floes of cooled crust drifting on the lava')
        Slider(self, g, 11, 'Glowing cracks', A + ('veins',), 0, 1, 0.01, tip='thin bright cracks through the floes')
        Slider(self, g, 13, 'Shore glow reach (km)', A + ('glow_km',), 0.5, 200, 0.5, tip='how far the glow reaches onto the rock; its strength is “Heated plate edges” below')
        Slider(self, g, 15, 'Flow lines on the rock', A + ('cooled',), 0, 1, 0.01, tip='the swirled flow lines frozen into the rock, 0 = off')
        Slider(self, g, 17, 'Flow ridges (m)', A + ('relief',), 0, 1500, 10, tip='height of the frozen flow ridges on land, 0 = flat')
        self.swatch_row(p, [('Flow line colour', A + ('cooled_color',))])
        self.section(p, 'Hottest point')
        self.note(p, 'This and the next parts are for the style “Torn plates”.')
        self.note(p, 'For “Star-facing side”: the point that faces the star (map middle = longitude 180), and how far '
                     'the torn crust reaches from it.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Latitude (°)', A + ('lat',), -90, 90, 0.5)
        Slider(self, g, 1, 'Longitude (°)', A + ('lon',), 0, 360, 0.5)
        Slider(self, g, 2, 'Reach (°)', A + ('spread',), 5, 180, 1, tip='90 = the whole day side')
        self.section(p, 'Plates')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Plate size (km)', A + ('plate_km',), 3, 800, 1, tip='at the edge of the torn area')
        Slider(self, g, 2, 'Smaller towards the centre', A + ('shrink',), 0, 1, 0.01, tip='0 = all the same size, 1 = broken into many small pieces')
        Slider(self, g, 4, 'Ragged edges', A + ('jagged',), 0, 1, 0.01)
        Slider(self, g, 5, 'Tilt (m)', A + ('tilt',), 0, 8000, 50, tip='how far the plates are tipped and pushed up, ripped up look')
        self.section(p, 'Lava channels')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Width (km)', A + ('crack_km',), 0.5, 60, 0.1, tip='at the edge of the torn area')
        Slider(self, g, 2, 'Wider towards the centre', A + ('widen',), 0, 6, 0.05)
        Slider(self, g, 3, 'Depth (m)', A + ('depth',), 0, 6000, 50, tip='how far the lava lies below the plates')
        self.section(p, 'Lava sea and pools')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Lava sea (°)', A + ('core',), 0, 60, 0.5, tip='radius of the open lava at the hottest point, 0 = none')
        Slider(self, g, 2, 'Lava sea depth (m)', A + ('core_depth',), 0, 6000, 50)
        Slider(self, g, 3, 'Floating rafts', A + ('rafts',), 0, 1, 0.01, tip='bits of crust drifting on the open lava')
        Slider(self, g, 5, 'Lava pools', A + ('pools',), 0, 40, 1, isint=True, tip='round lakes of lava, inside the torn area')
        Slider(self, g, 7, 'Pool size (km)', A + ('pool_km',), 2, 600, 1)
        self.section(p, 'Lava ocean')
        self.note(p, 'Fills everything below sea level with lava instead of water, with floating crust and glowing '
                     'shores. Needs “Ocean” on the Shape tab. The Kopernicus config writes the ocean in the lava '
                     'colours, with the glow on the ocean surface too.')
        r = ttk.Frame(p)
        r.pack(fill='x')
        self.check(r, 'Lava ocean', ('lava_ocean', 'enabled')).pack(side='left', padx=8)
        g = self.grid_box(p)
        O = ('lava_ocean',)
        Slider(self, g, 0, 'Floating crust', O + ('crust',), 0, 1, 0.01, tip='0 = open lava, 1 = mostly crusted over')
        Slider(self, g, 2, 'Crust plate size (km)', O + ('crust_km',), 2, 500, 1)
        Slider(self, g, 3, 'Glowing shores', O + ('shore',), 0, 1, 0.01, tip='hot rock along the coast')
        Slider(self, g, 5, 'Ocean glow', O + ('glow',), 0, 2, 0.01)
        self.section(p, 'More glow')
        self.note(p, 'Glowing lava in the cracks (Landforms tab), in the volcanoes (Relief and Features tabs) and in '
                     'the rivers (Landforms tab), in the colour map and the emissive map.')
        g = self.grid_box(p)
        E = ('emission',)
        Slider(self, g, 0, 'Glowing cracks', E + ('cracks',), 0, 2, 0.01, tip='0 = off')
        Slider(self, g, 2, 'Glowing volcanoes', E + ('volcanoes',), 0, 2, 0.01, tip='lava in the calderas, 0 = off')
        Slider(self, g, 4, 'Lava flows', E + ('flows',), 0, 1, 0.01, tip='glowing streams down the volcano slopes')
        Slider(self, g, 6, 'Lava rivers', E + ('rivers',), 0, 2, 0.01,
               tip='the rivers (Landforms tab) carry glowing lava instead of water, 0 = off')
        self.section(p, 'Colours and glow')
        self.note(p, 'Used by all the lava: plates, lava ocean, cracks and volcanoes.')
        self.swatch_row(p, [('Lava', A + ('color',)), ('Hottest lava', A + ('hot_color',)), ('Crust', A + ('crust_color',))])
        g = self.grid_box(p)
        Slider(self, g, 0, 'Darker crust', A + ('crust_amount',), 0, 1, 0.01, tip='how much the plates take the crust colour')
        Slider(self, g, 2, 'Heated plate edges', A + ('edge_glow',), 0, 1, 0.01, tip='a soft glow on the plates next to the lava')
        Slider(self, g, 4, 'Plate glow', A + ('glow',), 0, 2, 0.01,
               tip='brightness of the lava plates in the emissive map (VertexColorMapEmissive, Additive)')

    def tab_colours(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Colours')
        p = sf.inner
        self.rand_bar(p, 'Randomize colours', 'colours', 'a new palette (earthy, desert, grey, icy, alien, volcanic)')
        self.section(p, 'Colour by height')
        self.note(p, 'Each colour sits at its height in metres. Heights in between blend smoothly. Under an ocean '
                     'these are the sea floor colours. Click any colour box for the colour picker: colour square, '
                     'hex, eyedropper for anything on your screen, colours from a picture, recent colours.')
        ed = ListEditor(self, p, self.stops_fn,
                        [num('Height (m)', 0, -30000, 30000, 50, '%.0f', width=9), colf('Colour', 1)],
                        lambda: [0.0, [128, 128, 120]], add_text='Add colour', notify=self.changed)
        ed.frame.pack(fill='x', pady=6)
        ttk.Button(ed.bar, text='Sort', command=self.sort_stops).pack(side='left', padx=6)
        ttk.Button(ed.bar, text='Colours from picture…', command=self.sample).pack(side='left')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Height blur (m)', ('colors', 'jitter'), 0, 1500, 10, tip='mixes the colours up and down a bit so they don’t follow contour lines')
        self.section(p, 'Patches')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Patches', ('colors', 'patches'), 0, 1.5, 0.02)
        Slider(self, g, 1, 'Patch size', ('colors', 'patch_size'), 0.3, 3, 0.05)
        self.swatch_row(p, [('Patch colour', ('colors', 'patch_color'))])
        self.section(p, 'Climate')
        self.note(p, 'A dry belt on both sides of the equator (deserts, like Earth’s at about 25°) and a colder '
                     'colour towards the poles (tundra). Land only.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Dry belt', ('colors', 'dry', 'amount'), 0, 1, 0.02, tip='0 = off')
        Slider(self, g, 2, 'Dry belt at (° latitude)', ('colors', 'dry', 'lat'), 0, 80, 0.5)
        Slider(self, g, 3, 'Dry belt width (°)', ('colors', 'dry', 'width'), 2, 45, 0.5)
        self.swatch_row(p, [('Dry colour', ('colors', 'dry', 'color'))])
        g = self.grid_box(p)
        Slider(self, g, 0, 'Cold tint', ('colors', 'cold', 'amount'), 0, 1, 0.02, tip='0 = off')
        Slider(self, g, 2, 'Cold from (° latitude)', ('colors', 'cold', 'lat'), 10, 89, 0.5)
        self.swatch_row(p, [('Cold colour', ('colors', 'cold', 'color'))])
        self.section(p, 'Rock on steep slopes')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Rock starts at (°)', ('colors', 'rock_slope', 0), 0, 60, 0.5)
        Slider(self, g, 1, 'All rock at (°)', ('colors', 'rock_slope', 1), 1, 80, 0.5)
        Slider(self, g, 2, 'Rock amount', ('colors', 'rock_amount'), 0, 1, 0.02)
        self.swatch_row(p, [('Rock colour', ('colors', 'rock'))])
        self.section(p, 'Ice and snow')
        g = self.grid_box(p)
        Slider(self, g, 0, 'North cap from (° latitude)', ('colors', 'cap_north'), 30, 90, 0.5, tip='90 = no cap')
        Slider(self, g, 2, 'South cap from (° latitude)', ('colors', 'cap_south'), 30, 90, 0.5, tip='90 = no cap')
        Slider(self, g, 4, 'Cap edge raggedness', ('colors', 'cap_ragged'), 0, 1, 0.02)
        Slider(self, g, 5, 'Sea ice', ('colors', 'sea_ice'), 0, 1, 0.02, tip='1 = the caps reach as far over the sea as over land')
        Slider(self, g, 7, 'Snow line (m)', ('colors', 'snow_line'), 0, 30000, 50, tip='snow above this height (lower towards the poles), set it high for none')
        Slider(self, g, 9, 'No snow on slopes over (°)', ('colors', 'snow_slope'), 5, 90, 0.5)
        self.swatch_row(p, [('Ice colour', ('colors', 'ice'))])
        self.section(p, 'Water')
        self.note(p, 'Only used with an ocean.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Deep colour from (m)', ('colors', 'water_depth'), 20, 5000, 10, tip='how deep the water must be to show the full deep colour')
        self.swatch_row(p, [('Shallow', ('colors', 'shallow')), ('Deep', ('colors', 'deep'))])
        self.section(p, 'Volcanic rock')
        self.note(p, 'Colour of the volcanoes, the random ones and the ones you place.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Amount', ('colors', 'volcano_amount'), 0, 1, 0.02)
        self.swatch_row(p, [('Volcanic rock', ('colors', 'volcano_color'))])
        self.section(p, 'Final look')
        self.note(p, 'For the whole colour map.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Brightness', ('colors', 'brightness'), -0.5, 0.5, 0.01)
        Slider(self, g, 1, 'Contrast', ('colors', 'contrast'), 0.4, 2, 0.01)
        Slider(self, g, 2, 'Saturation', ('colors', 'saturation'), 0, 2, 0.01, tip='0 = grey, 1 = as set, 2 = very colourful')

    def tab_features(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Features')
        p = sf.inner
        self.section(p, 'Your own features')
        self.note(p, 'Craters, basins, volcanoes, mountains and plateaus exactly where you want them. Turn on Place features '
                     '(above the preview), pick the kind, then click the flat map or the globe to add one. Drag to '
                     'move it, right-click to remove it. Height 0 = a size that fits how wide it is. '
                     'Longitude is counted from the left edge of the map.')
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(8, 4))
        ttk.Label(r, text='Kind to add').pack(side='left', padx=(8, 8))
        cb = ttk.Combobox(r, textvariable=self.feat_type, values=FEAT_NAMES, width=10, state='readonly')
        cb.pack(side='left')
        ttk.Checkbutton(r, text='Place on the map', variable=self.place_mode, style='Toolbutton',
                        command=self.place_toggled).pack(side='left', padx=10)
        ed = ListEditor(self, p, lambda: self.P['features'],
                        [{'label': 'Kind', 'kind': 'choice', 'values': FEAT_NAMES, 'width': 9,
                          'get': lambda it: it['type'].capitalize(), 'set': lambda it, v: it.__setitem__('type', v.lower())},
                         num('Latitude', 'lat', -90, 90, 0.5, '%.1f'),
                         num('Longitude', 'lon', 0, 360, 0.5, '%.1f'),
                         num('Size (km)', 'size', 1, 5000, 5, '%.0f'),
                         num('Height or depth (m)', 'height', 0, 30000, 100, '%.0f', width=8),
                         num('Fresh', 'fresh', 0, 1, 0.05, '%.2f', width=5)],
                        self.new_feature, card=True, cols=3, add_text='Add feature', notify=self.changed)
        ed.frame.pack(fill='x', pady=6)
        self.feat_ed = ed
        self.note(p, 'Fresh: for craters and basins, 1 = sharp and young with bright ejecta, 0 = old and worn down. '
                     'A plateau rises by its height above the ground around it, with a flat top and steep, ragged edges.')

    def new_feature(self):
        t = self.feat_type.get().lower()
        f = tr.default_feature(t if t in tr.FEATURE_TYPES else 'crater', float(self.P['radius']))
        f['lon'] = round((float(self.P['preview']['view_lon']) + self.rot[0]) % 360, 1)
        f['lat'] = round(max(-60.0, min(60.0, float(self.P['preview']['view_lat']) + self.rot[1])), 1)
        return f

    ATMO_TIPS = {'HR': 'HR – how fast the air thins out with height (km)',
                 'HM': 'HM – how fast the haze thins out with height (km)',
                 'm_mieG': 'm_mieG – how strongly the haze glows when you look towards the sun',
                 'atmosphereStartRadiusScale': 'atmosphereStartRadiusScale – below 1 the air starts under the ground',
                 'averageGroundReflectance': 'averageGroundReflectance – light bounced back up from the ground',
                 'godrayStrength': 'godrayStrength – only in game, not in this preview'}
    TINT = 'The planet’s colours'

    def tab_atmo(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Atmosphere')
        p = sf.inner
        A = ('atmosphere',)
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(2, 0))
        self.atmo_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text='Scatterer atmosphere', variable=self.atmo_on, command=self.atmo_toggle).pack(side='left')
        ttk.Button(top, text='Load from Scatterer config…', command=self.atmo_load).pack(side='right')
        self.note(p, 'The values are the ones in Scatterer’s atmo.cfg. The “In game” view on the right shows the planet '
                     'with this atmosphere the way KSP’s map view shows it, relief and all.')
        vr = ttk.Frame(p)
        vr.pack(fill='x', pady=(8, 0))
        ttk.Label(vr, text='Show').pack(side='left', padx=(8, 8))
        self.atmo_view = tk.StringVar(value='planet')
        for val, txt in (('planet', 'Whole planet'), ('limb', 'Day-side edge'), ('sunset', 'Sunset edge')):
            ttk.Radiobutton(vr, text=txt, value=val, variable=self.atmo_view, style='Toolbutton',
                            command=self.atmo_view_changed).pack(side='left', padx=(0, 4))
        ttk.Button(vr, text='In game view', command=self.atmo_show).pack(side='right')
        vr2 = ttk.Frame(p)
        vr2.pack(fill='x', pady=(6, 0))
        ttk.Label(vr2, text='In game view also shows').pack(side='left', padx=(8, 8))
        self.ig_clouds = tk.BooleanVar(value=True)
        self.ig_aurora = tk.BooleanVar(value=True)
        self.ig_glow = tk.BooleanVar(value=True)
        self.ig_show_glow = True
        for txt, var in (('Clouds', self.ig_clouds), ('Aurora', self.ig_aurora), ('Lava glow', self.ig_glow)):
            ttk.Checkbutton(vr2, text=txt, variable=var, command=self.ingame_toggles).pack(side='left', padx=(0, 10))
        g = self.grid_box(p)
        Slider(self, g, 0, 'Sun angle (°)', A + ('sun_angle',), 0, 170, 1,
               tip='only for the picture: 0 = sun behind you, 90 = from the side, 150 = from behind the planet')
        pr = ttk.Frame(p)
        pr.pack(fill='x', pady=(8, 0))
        ttk.Label(pr, text='Start from').pack(side='left', padx=(8, 8))
        self.atmo_preset = tk.StringVar(value='Kerbin (stock)')
        ttk.Combobox(pr, textvariable=self.atmo_preset, values=[self.TINT] + list(tr.ATMO_PRESETS),
                     width=20, state='readonly').pack(side='left')
        ttk.Button(pr, text='Apply', command=self.atmo_apply_preset).pack(side='left', padx=6)
        self.atmo_fit = tk.BooleanVar(value=True)
        ttk.Checkbutton(pr, text='Fit to this planet’s size', variable=self.atmo_fit).pack(side='left', padx=(6, 0))
        self.note(p, 'The stock values are the ones Scatterer ships for Kerbin, Duna, Eve and Laythe. Fit to size scales '
                     'them so the air looks the same on this planet as on the original. “The planet’s colours” takes '
                     'Kerbin’s air (Duna’s on a world without an ocean) and tints the sky like the ground.')
        self.section(p, 'Planet')
        self.note(p, 'Scatterer takes the radius from the planet itself; here it is the radius on the Planet tab.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Air starts at (× radius)', A + ('atmosphereStartRadiusScale',), 0.95, 1.05, 0.001,
               tip=self.ATMO_TIPS['atmosphereStartRadiusScale'])
        self.section(p, 'Rayleigh scattering – the colour of the sky')
        self.note(p, 'm_betaR: how strongly the air scatters red, green and blue. Bigger = thicker, brighter air.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Scale height (km)', A + ('HR',), 0.05, 100, 0.01, tip=self.ATMO_TIPS['HR'])
        for i, c in enumerate(('Red', 'Green', 'Blue')):
            Slider(self, g, 2 + i, c, A + ('m_betaR', i), 0, 0.15, 0.00001, notify=self.atmo_colours_changed)
        cr = ttk.Frame(p)
        cr.pack(fill='x', pady=(6, 0))
        self.atmo_sky_sw = tk.Label(cr, width=6, relief='solid', bd=1, cursor='hand2')
        self.atmo_sky_sw.pack(side='left', padx=(8, 6))
        self.atmo_sky_sw.bind('<Button-1>', lambda e: self.atmo_pick_colour('m_betaR'))
        ttk.Button(cr, text='Sky colour…', command=lambda: self.atmo_pick_colour('m_betaR')).pack(side='left')
        ttk.Button(cr, text='Match the planet', command=self.atmo_match).pack(side='left', padx=6)
        self.section(p, 'Mie scattering – haze')
        self.note(p, 'BETA_MSca: how much haze or dust there is, for red, green and blue.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Scale height (km)', A + ('HM',), 0.02, 60, 0.01, tip=self.ATMO_TIPS['HM'])
        for i, c in enumerate(('Red', 'Green', 'Blue')):
            Slider(self, g, 2 + i, c, A + ('BETA_MSca', i), 0, 0.15, 0.00001, notify=self.atmo_colours_changed)
        Slider(self, g, 5, 'Glow towards the sun', A + ('m_mieG',), 0, 0.99, 0.01, tip=self.ATMO_TIPS['m_mieG'])
        cr = ttk.Frame(p)
        cr.pack(fill='x', pady=(6, 0))
        self.atmo_haze_sw = tk.Label(cr, width=6, relief='solid', bd=1, cursor='hand2')
        self.atmo_haze_sw.pack(side='left', padx=(8, 6))
        self.atmo_haze_sw.bind('<Button-1>', lambda e: self.atmo_pick_colour('BETA_MSca'))
        ttk.Button(cr, text='Haze colour…', command=lambda: self.atmo_pick_colour('BETA_MSca')).pack(side='left')
        ttk.Button(cr, text='Grey haze', command=self.atmo_grey_haze).pack(side='left', padx=6)
        self.section(p, 'Absorbing layer (ozone)')
        self.atmo_oz = tk.BooleanVar(value=False)
        ttk.Checkbutton(p, text='useOzone – a layer that swallows some colours (ozone, methane…)', variable=self.atmo_oz,
                        command=lambda: self.atmo_flag('useOzone', self.atmo_oz)).pack(anchor='w', padx=(8, 0))
        g = self.grid_box(p)
        for i, c in enumerate(('Red', 'Green', 'Blue')):
            Slider(self, g, i, 'Absorbs ' + c.lower(), A + ('ozoneAbsorption', i), 0, 0.01, 0.000001)
        Slider(self, g, 3, 'Height (km)', A + ('ozoneHeight',), 0, 300, 0.5, tip='ozoneHeight – the middle of the layer')
        Slider(self, g, 5, 'Half thickness (km)', A + ('ozoneFalloff',), 0.5, 200, 0.5, tip='ozoneFalloff')
        self.section(p, 'Light')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Light from below', A + ('averageGroundReflectance',), 0, 1, 0.01, tip=self.ATMO_TIPS['averageGroundReflectance'])
        Slider(self, g, 2, 'Godrays', A + ('godrayStrength',), 0, 1, 0.05, tip=self.ATMO_TIPS['godrayStrength'])
        self.atmo_ms = tk.BooleanVar(value=True)
        ttk.Checkbutton(p, text='multipleScattering – light that bounces around more than once (softer, brighter)',
                        variable=self.atmo_ms, command=lambda: self.atmo_flag('multipleScattering', self.atmo_ms)).pack(anchor='w', padx=(8, 0), pady=(4, 0))
        self.section(p, 'Seen from orbit (the last config point)')
        g = self.grid_box(p)
        L = A + ('configPoints', -1)
        for i, (k, lab, lo, hi, st, tip) in enumerate((
                ('skyExposure', 'Sky brightness', 0.005, 1.0, 0.005, 'skyExposure – the glow around the planet'),
                ('scatteringExposure', 'Haze over the planet', 0.005, 1.0, 0.005, 'scatteringExposure – the light the air adds over the ground'),
                ('extinctionThickness', 'Shade from the air', 0, 1.5, 0.01, 'extinctionThickness – how much the air darkens the ground below'),
                ('extinctionTint', 'Coloured shade', 0, 1, 0.01, 'extinctionTint – 0 = grey, 1 = in the colours of the air'),
                ('skyAlpha', 'Sky opacity', 0, 1, 0.01, 'skyAlpha'),
                ('skyExtinctionTint', 'Sky shade colour', 0, 1, 0.01, 'skyExtinctionTint – tints the stars behind the air; not in the picture'))):
            Slider(self, g, i * 2, lab, L + (k,), lo, hi, st, tip=tip, notify=self.atmo_point_changed)
        self.section(p, 'Config points')
        self.note(p, 'Scatterer blends between these by the camera’s height above the ground (in metres). Below the first '
                     'point it uses the first, above the last the last; the map view always uses the last one.')
        pts = ListEditor(self, p, lambda: self.P['atmosphere']['configPoints'],
                         [num('altitude', 'altitude', -1e6, 1e9, 1000, '%.0f', width=10),
                          num('skyExposure', 'skyExposure', 0, 5, 0.01, '%.3f'),
                          num('scatteringExposure', 'scatteringExposure', 0, 5, 0.01, '%.3f'),
                          num('skyAlpha', 'skyAlpha', 0, 1, 0.05, '%.2f'),
                          num('skyExtinctionTint', 'skyExtinctionTint', 0, 1, 0.05, '%.2f'),
                          num('extinctionThickness', 'extinctionThickness', 0, 2, 0.05, '%.2f'),
                          num('extinctionTint', 'extinctionTint', 0, 1, 0.05, '%.2f'),
                          num('postProcessAlpha', 'postProcessAlpha', 0, 1, 0.05, '%.2f'),
                          num('postProcessDepth', 'postProcessDepth', 0, 5, 0.05, '%.2f')],
                         self.atmo_new_point, card=True, cols=4, add_text='Add config point', notify=self.atmo_points_changed,
                         registry=[])
        pts.frame.pack(fill='x', pady=6)
        self.atmo_pts = pts
        self.section(p, 'Sun and planet list')
        g = ttk.Frame(p)
        g.pack(fill='x')
        self.v_atmo_sun = tk.StringVar()
        self.v_atmo_casters = tk.StringVar()
        ttk.Label(g, text='Sun (mainSunCelestialBody)').grid(row=0, column=0, sticky='w', padx=8, pady=4)
        e1 = ttk.Entry(g, textvariable=self.v_atmo_sun, width=20)
        e1.grid(row=0, column=1, sticky='w', pady=4)
        ttk.Label(g, text='Sun colour').grid(row=1, column=0, sticky='w', padx=8, pady=4)
        self.atmo_sun_sw = Swatch(self, g, A + ('sun_color',))
        self.atmo_sun_sw.lab.grid(row=1, column=1, sticky='w', pady=4)
        ttk.Label(g, text='Eclipse casters (moons)').grid(row=2, column=0, sticky='w', padx=8, pady=4)
        e2 = ttk.Entry(g, textvariable=self.v_atmo_casters, width=30)
        e2.grid(row=2, column=1, sticky='w', pady=4)
        for w in (e1, e2):
            w.bind('<Return>', self.atmo_commit_entries)
            w.bind('<FocusOut>', self.atmo_commit_entries)
        self.atmo_cloud = tk.BooleanVar(value=True)
        self.atmo_flat = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text='usesCloudIntegration (EVE clouds get lit by the atmosphere)', variable=self.atmo_cloud,
                        command=lambda: self.atmo_flag('cloud_integration', self.atmo_cloud)).grid(row=3, column=0, columnspan=2, sticky='w', padx=8, pady=2)
        ttk.Checkbutton(g, text='flatScaledSpaceModel (on for Kerbin, Eve and Laythe, off for Duna)', variable=self.atmo_flat,
                        command=lambda: self.atmo_flag('flat_model', self.atmo_flat)).grid(row=4, column=0, columnspan=2, sticky='w', padx=8, pady=2)
        self.section(p, 'Other Scatterer values')
        self.note(p, 'These go into atmo.cfg as they are (rim, shine, cloud and scaled-texture settings). '
                     'One “key = value” per line.')
        self.atmo_extra = tk.Text(p, height=10, width=64, bg=FIELD, fg=FG, insertbackground=FG, relief='flat', font=(MONO, 9), tabs=('0.9c',))
        self.atmo_extra.pack(anchor='w', pady=(4, 0))
        self.atmo_extra.bind('<FocusOut>', self.atmo_commit_extra)
        self.section(p, 'Scatterer config')
        self.note(p, 'atmo.cfg – goes into GameData/<your mod>/Scatterer/Planets/<planet>/ (any .cfg name works):')
        self.atmo_cfg = tk.Text(p, height=14, width=64, bg=FIELD, fg=FG, insertbackground=FG, relief='flat', font=(MONO, 9), tabs=('0.9c',))
        self.atmo_cfg.pack(anchor='w', pady=(4, 0))
        br = ttk.Frame(p)
        br.pack(fill='x', pady=(6, 0))
        ttk.Button(br, text='Copy', command=lambda: self.atmo_copy('atmo')).pack(side='left')
        ttk.Button(br, text='Save atmo.cfg…', command=self.atmo_save).pack(side='left', padx=6)
        ttk.Label(p, text='Planet list entry – Scatterer only draws planets that are in its list:',
                  style='Dim.TLabel', wraplength=540).pack(anchor='w', pady=(10, 0))
        self.atmo_pl = tk.Text(p, height=12, width=64, bg=FIELD, fg=FG, insertbackground=FG, relief='flat', font=(MONO, 9), tabs=('0.9c',))
        self.atmo_pl.pack(anchor='w', pady=(4, 0))
        ttk.Button(p, text='Copy', command=lambda: self.atmo_copy('list')).pack(anchor='w', pady=(6, 12))
        self.swatches.append(type('A', (), {'refresh': lambda s=None: self.atmo_refresh()})())

    def atmo_e(self):
        return self.P['atmosphere']

    def atmo_refresh(self):
        e = self.atmo_e()
        self.atmo_on.set(bool(e.get('enabled')))
        self.atmo_view.set(e.get('view', 'planet'))
        self.atmo_oz.set(bool(e.get('useOzone')))
        self.atmo_ms.set(bool(e.get('multipleScattering')))
        self.atmo_cloud.set(bool(e.get('cloud_integration')))
        self.atmo_flat.set(bool(e.get('flat_model')))
        self.v_atmo_sun.set(e.get('sun', 'Sun'))
        self.v_atmo_casters.set(e.get('eclipse_casters', ''))
        self.atmo_pts.rebuild()
        self.atmo_extra.delete('1.0', 'end')
        self.atmo_extra.insert('1.0', '\n'.join('%s = %s' % (k, v) for k, v in e.get('extra') or []))
        self.atmo_swatches()
        self.atmo_text()

    def atmo_swatches(self):
        e = self.atmo_e()
        self.atmo_sky_sw.configure(bg=hexcol(tr.colour_from_beta(e['m_betaR'])))
        self.atmo_haze_sw.configure(bg=hexcol(tr.colour_from_beta(e['BETA_MSca'])))

    def atmo_text(self):
        self.atmo_text_after = None
        for box, txt in ((self.atmo_cfg, tr.atmo_cfg(self.P)), (self.atmo_pl, tr.atmo_planets(self.P))):
            box.configure(state='normal')
            box.delete('1.0', 'end')
            box.insert('1.0', txt)
            box.configure(state='disabled')

    def atmo_copy(self, which):
        self.atmo_commit_entries()
        self.atmo_commit_extra()
        self.clipboard_clear()
        self.clipboard_append(tr.atmo_cfg(self.P) if which == 'atmo' else tr.atmo_planets(self.P))
        self.status('Scatterer config copied' if which == 'atmo' else 'Planet list entry copied')

    def atmo_dirty(self):
        if getattr(self, 'atmo_text_after', None):
            self.after_cancel(self.atmo_text_after)
        self.atmo_text_after = self.after(250, self.atmo_text)

    def atmo_colours_changed(self):
        self.atmo_swatches()
        self.changed()

    def atmo_point_changed(self):
        if getattr(self, 'atmo_pts_after', None):
            self.after_cancel(self.atmo_pts_after)
        self.atmo_pts_after = self.after(400, self.atmo_pts.rebuild)
        self.changed()

    def atmo_points_changed(self):
        pts = self.atmo_e()['configPoints']
        if not pts:
            pts.append(dict(tr.ATMO_POINT))
        order = sorted(pts, key=lambda q: float(q.get('altitude', 0)))
        if order != pts:
            pts[:] = order
            self.after_idle(self.atmo_pts.rebuild)
        for sl in self.sliders:
            if sl.path[:2] == ('atmosphere', 'configPoints'):
                sl.refresh()
        self.changed()

    def atmo_new_point(self):
        pts = self.atmo_e()['configPoints']
        q = dict(pts[-1] if pts else tr.ATMO_POINT)
        q['altitude'] = float(q.get('altitude', 0)) + 50000.0
        return q

    def atmo_flag(self, key, var):
        self.snapshot()
        self.atmo_e()[key] = bool(var.get())
        self.changed()

    def atmo_commit_entries(self, _e=None):
        e = self.atmo_e()
        new = {'sun': self.v_atmo_sun.get().strip() or 'Sun',
               'eclipse_casters': ', '.join(tr.atmo_casters({'eclipse_casters': self.v_atmo_casters.get()}))}
        if any(e.get(k) != v for k, v in new.items()):
            self.snapshot()
            e.update(new)
            self.changed()
        self.v_atmo_sun.set(e['sun'])
        self.v_atmo_casters.set(e['eclipse_casters'])

    def atmo_commit_extra(self, _e=None):
        out = []
        for line in self.atmo_extra.get('1.0', 'end').splitlines():
            line = line.split('//', 1)[0].strip()
            if '=' in line:
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip()
                if k and k not in tr.ATMO_VALUES and k not in ('name', 'configPoints'):
                    out.append([k, v])
        if out != self.atmo_e().get('extra'):
            self.snapshot()
            self.atmo_e()['extra'] = out
            self.changed()

    def atmo_pick_colour(self, key):
        e = self.atmo_e()
        old = list(e[key])

        def live(v):
            e[key] = tr.beta_from_colour(v, old)
            self.refresh_atmo_sliders()
            self.changed()

        def restore():
            e[key] = old
            self.refresh_atmo_sliders()
            self.changed()
        c = pick_colour(self, tr.colour_from_beta(old), title='Sky colour' if key == 'm_betaR' else 'Haze colour', live=live, restore=restore)
        if c:
            live(c)

    def planet_tint(self):
        L = self.live_last
        return tr.planet_tint(self.P, L['col'] if L is not None else None)

    def atmo_match(self):
        self.snapshot()
        e = self.atmo_e()
        e['m_betaR'] = tr.beta_from_colour(self.planet_tint(), e['m_betaR'])
        self.refresh_atmo_sliders()
        self.changed()
        self.status('Sky colour now matches the planet’s ground')

    def atmo_grey_haze(self):
        self.snapshot()
        e = self.atmo_e()
        m = float(np.mean(e['BETA_MSca']))
        e['BETA_MSca'] = [m, m, m]
        self.refresh_atmo_sliders()
        self.changed()

    def refresh_atmo_sliders(self):
        for sl in self.sliders:
            if sl.path[0] == 'atmosphere':
                sl.refresh()
        self.atmo_swatches()

    def atmo_values(self, name):
        R = float(self.P['radius']) / 1000.0
        fit = bool(self.atmo_fit.get())
        if name in tr.ATMO_PRESETS:
            return tr.atmo_preset(name, R, fit)
        v = tr.atmo_preset('Kerbin (stock)' if self.P['shape']['ocean'] else 'Duna (stock)', R, fit)
        v['m_betaR'] = tr.beta_from_colour(self.planet_tint(), v['m_betaR'])
        return v

    def atmo_apply_preset(self):
        self.snapshot()
        e = self.atmo_e()
        name = self.atmo_preset.get()
        e.update(self.atmo_values(name))
        self.P['atmosphere'] = tr.atmo_entry(e)
        self.atmo_refresh()
        self.refresh_atmo_sliders()
        self.changed()
        self.status('Atmosphere values from “%s” – Undo goes back' % name)

    def atmo_fresh(self):
        e = dict(self.atmo_e())
        d = tr.atmo_entry({})
        return all(e.get(k) == d[k] for k in tr.ATMO_VALUES + ('configPoints', 'extra'))

    def atmo_toggle(self):
        self.snapshot()
        e = self.atmo_e()
        e['enabled'] = bool(self.atmo_on.get())
        if e['enabled'] and self.atmo_fresh():
            found = tr.find_atmo_cfg(self.P['name']) if tr.game_mod_dir() else ''
            if found and messagebox.askyesno('Scatterer config found',
                                             'Your mod already has a Scatterer config for %s:\n\n%s\n\nStart from its values?'
                                             % (self.P['name'], tr.nice(found)), parent=self):
                self.atmo_read_file(found)
            else:
                name = 'Kerbin (stock)' if self.P['shape']['ocean'] else self.TINT
                self.atmo_preset.set(name)
                e.update(self.atmo_values(name))
                e['flat_model'] = bool(self.P['shape']['ocean'])
                self.P['atmosphere'] = tr.atmo_entry(e)
            self.atmo_refresh()
            self.refresh_atmo_sliders()
        self.changed()
        if self.atmo_e()['enabled'] and self.view.get() != 'atmo':
            self.atmo_show()

    def ingame_toggles(self):
        if self.view.get() == 'atmo':
            self.update_view()

    def atmo_show(self):
        if self.place_mode.get():
            self.place_mode.set(False)
        self.view.set('atmo')
        self.update_view()

    def atmo_view_changed(self):
        self.atmo_e()['view'] = self.atmo_view.get()
        self.changed()
        if self.view.get() != 'atmo':
            self.atmo_show()

    def atmo_read_file(self, path):
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                txt = f.read()
        except OSError as ex:
            messagebox.showerror('Could not read', str(ex), parent=self)
            return False
        e, nm = tr.atmo_from_cfg(txt, self.P['name'])
        if e is None:
            messagebox.showerror('No atmosphere', 'There is no Scatterer Atmo node in\n%s' % path, parent=self)
            return False
        old = self.atmo_e()
        for k in ('enabled', 'sun', 'sun_color', 'eclipse_casters', 'cloud_integration', 'flat_model', 'sun_angle', 'view'):
            e[k] = old.get(k, e[k])
        e['enabled'] = True
        d = os.path.dirname(path)
        root = d
        for _ in range(4):
            if os.path.basename(root).lower() == 'scatterer':
                break
            root = os.path.dirname(root)
        else:
            root = d
        item, _ = tr.find_planets_item(nm or self.P['name'], root)
        if item:
            e.update(item)
        self.P['atmosphere'] = tr.atmo_entry(e)
        self.status('Loaded the atmosphere of %s from %s' % (nm or '?', os.path.basename(path)))
        return True

    def atmo_load(self):
        found = tr.find_atmo_cfg(self.P['name']) if tr.game_mod_dir() else ''
        sd = tr.scatterer_dir(tr.game_mod_dir())
        init = os.path.dirname(found) if found else (sd or tr.TOOL)
        path = filedialog.askopenfilename(parent=self, title='Scatterer atmosphere config', initialdir=init,
                                          initialfile=os.path.basename(found) if found else '',
                                          filetypes=[('Config', '*.cfg'), ('All files', '*.*')])
        if not path:
            return
        self.snapshot()
        if not self.atmo_read_file(path):
            self.drop_snapshot()
            return
        self.atmo_refresh()
        self.refresh_atmo_sliders()
        self.changed()
        if self.view.get() != 'atmo':
            self.atmo_show()

    def drop_snapshot(self):
        if self.history:
            self.history.pop()
        if not self.history:
            self.undo_btn.configure(state='disabled')

    def atmo_save(self):
        self.atmo_commit_entries()
        self.atmo_commit_extra()
        name = self.P['name']
        mod = tr.game_mod_dir()
        found = tr.find_atmo_cfg(name) if mod else ''
        sd = tr.scatterer_dir(mod)
        init = os.path.dirname(found) if found else (os.path.join(sd, 'Planets', name) if sd else os.path.join(tr.TOOL, 'export'))
        idir = init
        while idir and not os.path.isdir(idir):
            idir = os.path.dirname(idir)
        path = filedialog.asksaveasfilename(parent=self, title='Save Scatterer atmosphere', initialdir=idir or tr.TOOL,
                                            initialfile='atmo.cfg', defaultextension='.cfg',
                                            filetypes=[('Config', '*.cfg'), ('All files', '*.*')])
        if not path:
            return
        stamp = time.strftime('%Y%m%d_%H%M%S')
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            backed = self.atmo_backup(path, stamp)
            with open(path, 'w', newline='\n') as f:
                f.write(tr.atmo_cfg(self.P))
        except OSError as ex:
            messagebox.showerror('Could not save', str(ex), parent=self)
            return
        msg = 'Saved %s' % path + (' (old file backed up)' if backed else '')
        root = os.path.dirname(path)
        r2 = root
        for _ in range(4):
            if os.path.basename(r2).lower() == 'scatterer':
                root = r2
                break
            r2 = os.path.dirname(r2)
        item, where = tr.find_planets_item(name, root)
        if item:
            msg += ' – %s is already in the planet list (%s)' % (name, os.path.basename(where))
        else:
            pl = tr.planets_file(root, name)
            if messagebox.askyesno('Planet list', 'Scatterer only draws planets that are in its planet list, and %s isn’t '
                                   'in one in this folder yet.\n\nSave %s next to it?' % (name, tr.nice(pl)), parent=self):
                try:
                    self.atmo_backup(pl, stamp)
                    with open(pl, 'w', newline='\n') as f:
                        f.write(tr.atmo_planets(self.P))
                    msg += ' and %s' % os.path.basename(pl)
                except OSError as ex:
                    messagebox.showerror('Could not save', str(ex), parent=self)
        self.status(msg)
        self.log(msg)

    def atmo_backup(self, path, stamp):
        if not os.path.isfile(path):
            return False
        b = tr.backup_dir(self.P['name'], stamp)
        os.makedirs(b, exist_ok=True)
        shutil.copy2(path, os.path.join(b, os.path.basename(path)))
        return True

    def atmo_built(self):
        if self.is_stale() is not False:
            return None
        d = self.out_path()
        n = self.P['name']
        f = os.path.join(d, n + '_color.png')
        hf = os.path.join(d, n + '_height.png')
        if not (os.path.isfile(f) and os.path.isfile(hf)):
            return None
        key = ('build', f, os.path.getmtime(f), os.path.getmtime(hf))
        if self.atmo_texc.get('key') != key:
            try:
                c = np.asarray(Image.open(f).convert('RGB'))
                hm, _ = tr.load_height(d, n)
                tex, gx, gy = tr.atmo_texture(c, hm, self.P)
                self.atmo_texc = {'key': key, 'tex': tex, 'gx': gx, 'gy': gy}
            except Exception:
                self.atmo_texc = {}
                return None
        T = self.atmo_texc
        return T['tex'], T['gx'], T['gy'], key

    def atmo_texture(self):
        b = self.atmo_built()
        if b is not None:
            self.atmo_src = 'build'
            return b
        self.atmo_src = 'live'
        L = self.live_last
        if L is None:
            return None
        key = ('live', L['key'], L['W'])
        if self.atmo_texc.get('key') != key:
            self.atmo_texc = {'key': key, 'tex': L['col'].astype(np.float32) / 255, 'gx': L['gx'], 'gy': L['gy']}
        T = self.atmo_texc
        return T['tex'], T['gx'], T['gy'], key

    def atmo_size(self):
        cw, ch = max(10, self.canvas.winfo_width()), max(10, self.canvas.winfo_height())
        w, h = max(200, cw - 16), max(150, ch - 16)
        k = min(1.0, 1300.0 / w, 820.0 / h)
        return int(w * k), int(h * k)

    def ingame_any(self):
        P = self.P
        return tr.has_atmo(P) or tr.has_clouds(P) or tr.has_aurora(P) or bool(getattr(self, 'ig_show_glow', None) and self.ig_glow_on() and self.ingame_em()[0] is not None)

    def ig_glow_on(self):
        return bool(self.ig_glow.get()) if hasattr(self, 'ig_glow') else True

    def ingame_em(self):
        if self.atmo_src == 'build':
            f = os.path.join(self.out_path(), self.P['name'] + '_emissive.png')
            if os.path.isfile(f):
                return f, ('emb', f, os.path.getmtime(f))
            return None, None
        L = self.live_last
        if L is not None and L.get('em') is not None:
            return L['em'], ('eml', L['key'], L['W'])
        return None, None

    def ingame_extras(self, P, cancel):
        cl = None
        if tr.has_clouds(P) and (self.ig_clouds.get() if hasattr(self, 'ig_clouds') else True):
            ck = json.dumps(['c', P['clouds']], sort_keys=True)
            cl = self.ig_cache.get(ck)
            if cl is None:
                cl = tr.ingame_clouds(P, 1024, cancel=cancel, workers=tr.THREADS)
                self.ig_cache = {k: v for k, v in self.ig_cache.items() if not k.startswith('["c"')}
                self.ig_cache[ck] = cl
        em_src, ekey = self.ingame_em() if self.ig_glow_on() else (None, None)
        au = tr.has_aurora(P) and (self.ig_aurora.get() if hasattr(self, 'ig_aurora') else True)
        gk = json.dumps(['g', P['aurora'] if au else None, str(ekey)], sort_keys=True)
        gl = self.ig_cache.get(gk, False)
        if gl is False:
            em = None
            if isinstance(em_src, str):
                em = np.asarray(Image.open(em_src).convert('RGB'))
            elif em_src is not None:
                em = em_src
            Q = P if au else dict(P, aurora=dict(P['aurora'], enabled=False))
            gl = tr.ingame_glow(Q, em, 1024, cancel=cancel)
            self.ig_cache = {k: v for k, v in self.ig_cache.items() if not k.startswith('["g"')}
            self.ig_cache[gk] = gl
        return cl, gl

    def ingame_key(self):
        P = self.P
        sh = [bool(self.ig_clouds.get()) if hasattr(self, 'ig_clouds') else True,
              bool(self.ig_aurora.get()) if hasattr(self, 'ig_aurora') else True, self.ig_glow_on()]
        return [P.get('clouds') if tr.has_clouds(P) else None, P.get('aurora') if tr.has_aurora(P) else None,
                str(self.ingame_em()[1]), sh]

    def atmo_request(self, quick_only=False):
        if not self.ingame_any():
            return
        t = self.atmo_texture()
        if t is None:
            return
        tex, gx, gy, tkey = t
        w, h = self.atmo_size()
        P = tr.normalize(copy.deepcopy(self.P))
        key = json.dumps([P['atmosphere'], P['radius'], P['normal_strength'], P['preview'], self.rot, w, h, str(tkey), self.ingame_key()],
                         sort_keys=True, default=str)
        if self.atmo_key == key and not quick_only:
            return
        r = self.atmo_req
        if r is not None and r[1] == key and r[-1] == quick_only:
            return
        self.atmo_err = None
        with self.atmo_lock:
            self.atmo_gen += 1
            self.atmo_req = (self.atmo_gen, key, P, tex, gx, gy, w, h, tuple(self.rot), quick_only)
            if self.atmo_thread is None:
                self.atmo_thread = threading.Thread(target=self.atmo_worker, daemon=True)
                self.atmo_thread.start()

    def atmo_worker(self):
        while True:
            with self.atmo_lock:
                req = self.atmo_req
                if req is None:
                    self.atmo_thread = None
                    return
            gen, key, P, tex, gx, gy, w, h, rot, quick_only = req

            def cancel(gen=gen):
                r = self.atmo_req
                if r is None or r[0] != gen:
                    raise tr.Cancelled()
            try:
                passes = ((3, 6),) if quick_only else ((3, 6), (1, 14))
                cl, gl = self.ingame_extras(P, cancel)
                for sc, steps in passes:
                    t0 = time.time()
                    im = tr.render_ingame(P, tex, gx, gy, w=max(60, w // sc), h=max(40, h // sc), steps=steps, rot=rot,
                                          cancel=cancel, bg=(13, 15, 20), clouds=cl, glow=gl)
                    if sc > 1:
                        im = im.resize((w, h), Image.BILINEAR)
                    self.atmo_q.put((gen, key, im, sc == 1, time.time() - t0, None))
            except tr.Cancelled:
                continue
            except Exception as ex:
                self.atmo_q.put((gen, key, None, True, 0, str(ex)))
            with self.atmo_lock:
                if self.atmo_req is not None and self.atmo_req[0] == gen:
                    self.atmo_req = None

    def atmo_poll(self):
        got = False
        try:
            while True:
                gen, key, im, final, dt, err = self.atmo_q.get_nowait()
                if gen != self.atmo_gen:
                    continue
                if err:
                    self.atmo_err = err
                else:
                    self.atmo_img = im
                    self.atmo_err = None
                    if final:
                        self.atmo_key = key
                got = True
        except queue.Empty:
            pass
        if got and self.view.get() == 'atmo':
            self.atmo_present()

    def atmo_present(self):
        if self.atmo_err:
            self.view_src = None
            self.status('Could not draw the atmosphere: %s' % self.atmo_err[:120])
        else:
            self.view_src = self.atmo_img
        self.redraw()

    def atmo_drag_start(self, e):
        if self.view.get() != 'atmo' or not self.ingame_any():
            return False
        self.snapshot()
        self.adrag = (e.x, float(self.atmo_e()['sun_angle']), False)
        return True

    def atmo_drag_move(self, e):
        x0, a0, _ = self.adrag
        a = round(max(0.0, min(170.0, a0 + (e.x - x0) * 0.4)))
        if a != self.atmo_e()['sun_angle']:
            self.atmo_e()['sun_angle'] = a
            self.adrag = (x0, a0, True)
            self.atmo_request(quick_only=True)
            self.status('Sun angle %d°' % a)

    def atmo_drag_end(self):
        moved = self.adrag[2]
        self.adrag = None
        if moved:
            for sl in self.sliders:
                if sl.path == ('atmosphere', 'sun_angle'):
                    sl.refresh()
            self.changed()
        else:
            self.drop_snapshot()

    AURORA_SIZE_NAMES = (('1024', '1024 × 512'), ('2048', '2048 × 1024'), ('4096', '4096 × 2048'), ('8192', '8192 × 4096'))

    def tab_aurora(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Aurora')
        p = sf.inner
        A = ('aurora',)
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(2, 0))
        self.aur_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text='Aurora (EVE cloud layers)', variable=self.aur_on, command=self.aurora_toggle).pack(side='left')
        ttk.Button(top, text='Aurora view', command=self.aurora_show).pack(side='right')
        self.note(p, 'Polar lights around the magnetic poles, made of glowing curtains with rays. Export writes two '
                     'textures (the lower, main colour and the top fringe) and an EVE config that stacks them as '
                     'several thin layers, so the aurora has height and depth. Needs EVE and StockVolumetricClouds. '
                     'The Aurora view shows both poles seen from above.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Seed', A + ('seed',), 1, 999, 1, isint=True, tip='a different pattern of curtains with the same settings')
        self.section(p, 'Where')
        r = ttk.Frame(p)
        r.pack(fill='x')
        self.check(r, 'North pole', A + ('north',)).pack(side='left', padx=(8, 16))
        self.check(r, 'South pole', A + ('south',)).pack(side='left')
        g = self.grid_box(p)
        Slider(self, g, 0, 'North magnetic tilt (°)', A + ('north_tilt',), 0, 40, 0.5,
               tip='how far the magnetic pole sits from the north pole')
        Slider(self, g, 2, 'North tilt towards (lon °)', A + ('north_lon',), 0, 360, 1)
        Slider(self, g, 3, 'South magnetic tilt (°)', A + ('south_tilt',), 0, 40, 0.5)
        Slider(self, g, 4, 'South tilt towards (lon °)', A + ('south_lon',), 0, 360, 1)
        Slider(self, g, 5, 'Oval size (°)', A + ('oval',), 3, 45, 0.5,
               tip='distance of the main curtain from the magnetic pole (Earth: about 20°)')
        Slider(self, g, 7, 'Wobble (°)', A + ('wobble',), 0, 15, 0.1, tip='how far the oval bends in and out')
        Slider(self, g, 9, 'Dark centre (°)', A + ('polar_gap',), 0, 30, 0.5,
               tip='0 = off; keeps the area right around the magnetic pole free of glow')
        self.section(p, 'Curtains')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Curtains', A + ('curtains',), 1, len(tr.AURORA_CURTAINS), 1, isint=True,
               tip='parallel arcs, the first is the brightest')
        Slider(self, g, 2, 'Spacing', A + ('spread',), 0.2, 3, 0.05, tip='how far apart the curtains are')
        Slider(self, g, 4, 'Width (°)', A + ('width',), 0.3, 6, 0.05)
        Slider(self, g, 5, 'Gaps', A + ('patchy',), 0, 1, 0.01, tip='0 = unbroken arcs, 1 = short broken pieces')
        Slider(self, g, 7, 'Rays', A + ('rays',), 0, 1, 0.01, tip='the vertical streaks in the curtains')
        Slider(self, g, 9, 'Diffuse glow', A + ('glow',), 0, 0.6, 0.01, tip='a soft haze along the oval')
        Slider(self, g, 11, 'Brightness', A + ('brightness',), 0.1, 1, 0.01)
        self.section(p, 'Colours')
        self.note(p, 'Main = the curtain, edge = its lower fringe, core = the brightest parts. The top layers are '
                     'the high part of the aurora (red and purple on Earth).')
        self.swatch_row(p, [('Main', A + ('color',)), ('Edge', A + ('edge_color',)), ('Core', A + ('core_color',))])
        self.swatch_row(p, [('Top', A + ('top_color',)), ('Top edge', A + ('top_edge_color',)), ('Top core', A + ('top_core_color',))])
        self.section(p, 'In game')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Layers', A + ('layers',), 1, 16, 1, isint=True, tip='more layers = more depth from the side')
        Slider(self, g, 2, 'Top layers', A + ('top_layers',), 0, 16, 1, isint=True, tip='how many of the highest layers use the top colours')
        Slider(self, g, 4, 'Lowest layer (m)', A + ('altitude',), 1000, 200000, 500)
        Slider(self, g, 5, 'Layer spacing (m)', A + ('spacing',), 0, 20000, 100)
        Slider(self, g, 6, 'Opacity', A + ('opacity',), 0, 255, 1, isint=True, tip='alpha of the lowest layer (_Color)')
        Slider(self, g, 8, 'Highest layer opacity', A + ('fade',), 0, 1, 0.01, tip='as a part of the lowest layer’s opacity')
        Slider(self, g, 10, 'Drift speed', A + ('speed',), -60, 60, 0.5, tip='EVE speed, how fast the aurora drifts around the pole')
        self.combo(g, 12, 'Texture size', A + ('size',), [(int(k), n) for k, n in self.AURORA_SIZE_NAMES])
        self.section(p, 'EVE config')
        self.note(p, 'Goes into a .cfg anywhere in your mod (for example Configs/…/Clouds/). Export writes it with the '
                     'right texture paths; the paths here use “Path in config” from the last export.')
        self.aur_cfg = tk.Text(p, height=14, width=64, bg=FIELD, fg=FG, insertbackground=FG, relief='flat', font=(MONO, 9), tabs=('0.9c',))
        self.aur_cfg.pack(anchor='w', pady=(4, 0))
        ttk.Button(p, text='Copy', command=self.aurora_copy).pack(anchor='w', pady=(6, 12))
        self.swatches.append(type('A', (), {'refresh': lambda s=None: self.aurora_refresh()})())

    def aurora_e(self):
        return self.P['aurora']

    def aurora_refresh(self):
        self.aur_on.set(bool(self.aurora_e().get('enabled')))
        self.aurora_text()

    def aurora_tex_names(self):
        S = load_settings()
        n = self.P['name']
        base = S.get('cfg_path') or tr.default_cfg_path(S.get('export_dir') or '')
        return tr.tex_path('', n + '_aurora', base), tr.tex_path('', n + '_aurora_top', base)

    def aurora_cfg_text(self):
        lo, hi = self.aurora_tex_names()
        return tr.aurora_cfg(self.P, self.P['name'], lo, hi)

    def aurora_text(self):
        self.aur_text_after = None
        if not hasattr(self, 'aur_cfg'):
            return
        self.aur_cfg.configure(state='normal')
        self.aur_cfg.delete('1.0', 'end')
        self.aur_cfg.insert('1.0', self.aurora_cfg_text())
        self.aur_cfg.configure(state='disabled')

    def aurora_dirty(self):
        if getattr(self, 'aur_text_after', None):
            self.after_cancel(self.aur_text_after)
        self.aur_text_after = self.after(300, self.aurora_text)

    def aurora_copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.aurora_cfg_text())
        self.status('EVE aurora config copied')

    def aurora_toggle(self):
        self.snapshot()
        self.aurora_e()['enabled'] = bool(self.aur_on.get())
        self.changed()
        if self.aurora_e()['enabled'] and self.view.get() != 'aurora':
            self.aurora_show()

    def aurora_show(self):
        if hasattr(self, 'place_mode') and self.place_mode.get():
            self.place_mode.set(False)
        self.view.set('aurora')
        self.update_view()

    def aurora_size(self):
        cw, ch = max(10, self.canvas.winfo_width()), max(10, self.canvas.winfo_height())
        return int(max(160, min(700, (cw - 40) / 2, ch - 20)))

    def aurora_request(self):
        if not tr.has_aurora(self.P):
            return
        S = self.aurora_size()
        P = tr.normalize(copy.deepcopy(self.P))
        bg, bkey = self.aurora_bg()
        key = json.dumps([P['aurora'], S, str(bkey)], sort_keys=True, default=str)
        if self.aur_key == key:
            return
        r = self.aur_req
        if r is not None and r[1] == key:
            return
        self.aur_err = None
        with self.aur_lock:
            self.aur_gen += 1
            self.aur_req = (self.aur_gen, key, P, bg, S)
            if self.aur_thread is None:
                self.aur_thread = threading.Thread(target=self.aurora_worker, daemon=True)
                self.aur_thread.start()

    def aurora_worker(self):
        while True:
            with self.aur_lock:
                req = self.aur_req
                if req is None:
                    self.aur_thread = None
                    return
            gen, key, P, bg, S = req

            def cancel(gen=gen):
                r = self.aur_req
                if r is None or r[0] != gen:
                    raise tr.Cancelled()
            try:
                for W in (512, 1024 if S < 520 else 2048):
                    t0 = time.time()
                    low, top = tr.aurora_maps(P, W, cancel=cancel)
                    im = tr.aurora_preview(P, low, top, bg, S)
                    self.aur_q.put((gen, key, im, W >= 1024, time.time() - t0, None))
            except tr.Cancelled:
                continue
            except Exception as ex:
                self.aur_q.put((gen, key, None, True, 0, str(ex)))
            with self.aur_lock:
                if self.aur_req is not None and self.aur_req[0] == gen:
                    self.aur_req = None

    def aurora_poll(self):
        got = False
        try:
            while True:
                gen, key, im, final, dt, err = self.aur_q.get_nowait()
                if gen != self.aur_gen:
                    continue
                if err:
                    self.aur_err = err
                else:
                    self.aur_img = im
                    self.aur_err = None
                    if final:
                        self.aur_key = key
                got = True
        except queue.Empty:
            pass
        if got and self.view.get() == 'aurora':
            if self.aur_err:
                self.view_src = None
                self.status('Could not draw the aurora: %s' % self.aur_err[:120])
            else:
                self.view_src = self.aur_img
            self.redraw()

    def aurora_view(self):
        if not tr.has_aurora(self.P):
            self.view_src = None
            if not self.proc:
                self.status('No aurora yet – tick “Aurora” on the Aurora tab')
        else:
            self.aurora_request()
            self.view_src = self.aur_img
            if not self.proc:
                self.status('Aurora: north pole (left) and south pole (right) seen from above, all layers together')
        self.update_export_state()
        self.redraw()

    CLOUD_SIZE_NAMES = ((2048, '2048 × 1024'), (4096, '4096 × 2048'), (8192, '8192 × 4096'), (16384, '16384 × 8192'))

    def tab_clouds(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Clouds')
        p = sf.inner
        A = ('clouds',)
        top = ttk.Frame(p)
        top.pack(fill='x', pady=(2, 0))
        self.cl_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text='Volumetric clouds (EVE + True Volumetric Clouds)', variable=self.cl_on, command=self.clouds_toggle).pack(side='left')
        ttk.Button(top, text='Clouds view', command=self.clouds_show).pack(side='right')
        self.rand_bar(p, 'Randomize clouds', 'clouds', 'new wind, swirls, layers and cloud cover')
        self.note(p, 'Swirled, streaky clouds made the same way as Edmunds’: the wind carries the clouds around eddies '
                     'and along bands, so they come out in curls, long streaks and thin fibres. A fair-weather layer is '
                     'always there, weather systems build up and fade away again over the hours, and a high cirrus layer '
                     'sits on top. Export writes the coverage and cloud type maps, the maps for scaled space and the '
                     'EVE config. Needs EVE, True Volumetric Clouds and StockVolumetricClouds.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Seed', A + ('seed',), 1, 999, 1, isint=True, tip='a new pattern of clouds')
        self.combo(g, 2, 'Map size', A + ('size',), list(self.CLOUD_SIZE_NAMES))
        self.section(p, 'Wind and swirls')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Swirls', A + ('swirl',), 0, 3, 0.01, tip='how strongly eddies curl the clouds up')
        Slider(self, g, 2, 'Swirl size', A + ('swirl_size',), 0.25, 4, 0.05, tip='bigger = fewer, larger eddies')
        Slider(self, g, 4, 'Wind', A + ('wind',), 0, 3, 0.01, tip='east-west winds that stretch the clouds into long bands')
        Slider(self, g, 6, 'Wind bands', A + ('bands',), 1, 8, 1, isint=True, tip='3 = like Earth: trade winds, westerlies, polar winds')
        Slider(self, g, 8, 'Streaks', A + ('streaks',), 0, 1, 0.01, tip='thin fibres along the wind')
        Slider(self, g, 10, 'Broken up', A + ('breakup',), 0, 1, 0.01, tip='holes and gaps inside the cloud fields')
        self.section(p, 'Fair weather')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Cover (% of the planet)', A + ('fair_pct',), 0, 100, 1, tip='the fair-weather clouds cover this much of the planet, 0 = no fair-weather layer')
        Slider(self, g, 2, 'Small cumulus', A + ('speckle',), 0, 1, 0.01, tip='fields of little puffy clouds around the big ones')
        self.section(p, 'Weather systems')
        self.note(p, 'Big cloud masses that come and go. Each one fades in, stays for a while and fades out again; '
                     'they take turns, spread evenly over the cycle.')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Systems', A + ('systems',), 0, 4, 1, isint=True, tip='0 = none')
        Slider(self, g, 2, 'Cover (% of the planet)', A + ('system_pct',), 0, 100, 1, tip='how much of the planet each system covers, 0 = no weather systems')
        Slider(self, g, 6, 'Lasts (hours)', A + ('duration',), 0.5, 100, 0.5)
        Slider(self, g, 7, 'Comes back every (hours)', A + ('repeat',), 1, 200, 0.5)
        Slider(self, g, 8, 'Fade in and out (hours)', A + ('fade',), 0, 50, 0.5)
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(4, 0))
        self.cl_meas = ttk.Label(p, text='', style='Dim.TLabel', wraplength=540, justify='left')
        self.cl_meas.pack(anchor='w', padx=8, pady=(6, 0))
        self.cl_sys = tk.BooleanVar(value=True)
        ttk.Checkbutton(r, text='Show a weather system in the Clouds view (as at one moment in game)', variable=self.cl_sys,
                        command=self.clouds_request).pack(side='left', padx=8)
        self.section(p, 'Cirrus')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Cover (% of the planet)', A + ('cirrus_pct',), 0, 100, 1, tip='thin, high, hair-like clouds, 0 = none')
        Slider(self, g, 2, 'Cirrus height (m)', A + ('cirrus_altitude',), 1000, 60000, 100)
        self.section(p, 'In game')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Cloud base (m)', A + ('base',), 0, 40000, 100)
        Slider(self, g, 1, 'Cloud height', A + ('height',), 0.2, 4, 0.05, tip='1 = as tall as Edmunds’ clouds (up to about 5.7 km above the base)')
        Slider(self, g, 3, 'Drift speed', A + ('speed',), -200, 200, 0.5, tip='EVE speed')
        Slider(self, g, 5, 'Brightness from orbit', A + ('brightness',), 50, 1500, 1, isint=True, tip='_Color of the scaled-space layer, Edmunds uses 512')
        self.swatch_row(p, [('Cloud colour', A + ('color',))])
        self.section(p, 'EVE config')
        self.note(p, 'Export writes it with the texture paths. The paths here use “Path in config” from the last export.')
        self.cl_cfg = tk.Text(p, height=12, width=64, bg=FIELD, fg=FG, insertbackground=FG, relief='flat', font=(MONO, 9), tabs=('0.9c',))
        self.cl_cfg.pack(anchor='w', pady=(4, 0))
        ttk.Button(p, text='Copy', command=self.clouds_copy).pack(anchor='w', pady=(6, 12))
        self.swatches.append(type('C', (), {'refresh': lambda s=None: self.clouds_refresh()})())

    def clouds_refresh(self):
        self.cl_on.set(bool(self.P['clouds'].get('enabled')))
        self.clouds_text()

    def clouds_cfg_text(self):
        S = load_settings()
        base = S.get('cfg_path') or tr.default_cfg_path(S.get('export_dir') or '')
        return tr.cloud_cfg(self.P, self.P['name'], tr.tex_path('', self.P['name'], base))

    def clouds_text(self):
        self.cl_text_after = None
        if not hasattr(self, 'cl_cfg'):
            return
        self.cl_cfg.configure(state='normal')
        self.cl_cfg.delete('1.0', 'end')
        self.cl_cfg.insert('1.0', self.clouds_cfg_text())
        self.cl_cfg.configure(state='disabled')

    def clouds_dirty(self):
        if getattr(self, 'cl_text_after', None):
            self.after_cancel(self.cl_text_after)
        self.cl_text_after = self.after(400, self.clouds_text)

    def clouds_copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.clouds_cfg_text())
        self.status('EVE cloud config copied')

    def clouds_toggle(self):
        self.snapshot()
        self.P['clouds']['enabled'] = bool(self.cl_on.get())
        self.changed()
        if self.P['clouds']['enabled'] and self.view.get() != 'clouds':
            self.clouds_show()

    def clouds_show(self):
        if hasattr(self, 'place_mode') and self.place_mode.get():
            self.place_mode.set(False)
        self.view.set('clouds')
        self.update_view()

    def clouds_request(self):
        if not tr.has_clouds(self.P):
            return
        P = tr.normalize(copy.deepcopy(self.P))
        bg, bkey = self.aurora_bg()
        sysv = bool(self.cl_sys.get()) if hasattr(self, 'cl_sys') else True
        key = json.dumps([P['clouds'], sysv, str(bkey)], sort_keys=True, default=str)
        if self.cl_key == key:
            return
        r = self.cl_req
        if r is not None and r[1] == key:
            return
        self.cl_err = None
        self.cl_prog = ('clouds', 0.0)
        with self.cl_lock:
            self.cl_gen += 1
            self.cl_req = (self.cl_gen, key, P, bg, sysv)
            if self.cl_thread is None:
                self.cl_thread = threading.Thread(target=self.clouds_worker, daemon=True)
                self.cl_thread.start()

    def clouds_image(self, P, cov, bg, sysv):
        W = 1024
        if bg is None:
            base = np.zeros((W // 2, W, 3), np.uint8) + np.array([40, 60, 90], np.uint8)
        else:
            base = np.asarray(Image.fromarray(np.asarray(bg, np.uint8)).resize((W, W // 2), Image.BILINEAR))
        show = {k: v for k, v in cov.items() if not k.startswith('sys') or (sysv and k == 'sys0')}
        comp = tr.cloud_composite(P, show, (base.astype(np.float32) * 0.75).astype(np.uint8))
        z = np.zeros(comp.shape[:2], np.float32)
        pv = P['preview']
        sheet = Image.new('RGB', (1024 + 512 + 24, 512), (13, 15, 20))
        sheet.paste(tr.render_globe(comp, z, z, 512, float(pv['tilt']), float(pv['view_lat']) + self.rot[1],
                                     float(pv['view_lon']) + self.rot[0], 0.0), (0, 0))
        sheet.paste(Image.fromarray(comp), (512 + 24, 0))
        return sheet

    def clouds_worker(self):
        while True:
            with self.cl_lock:
                req = self.cl_req
                if req is None:
                    self.cl_thread = None
                    return
            gen, key, P, bg, sysv = req

            def cancel(gen=gen):
                r = self.cl_req
                if r is None or r[0] != gen:
                    raise tr.Cancelled()
            try:
                t0 = time.time()
                for W in (512, 1024):
                    def prog(stage, f, W=W, gen=gen):
                        self.cl_q.put((gen, key, None, -1, ('wind' if stage == 'wind' else 'clouds %d px' % W, f)))
                    cov, typ = tr.cloud_maps(P, W, cancel=cancel, progress=prog, workers=tr.THREADS)
                    im = self.clouds_image(P, cov, bg, sysv)
                    im.meas = {k: tr.cloud_cover_frac(v.astype(np.float32) / 255) for k, v in cov.items()}
                    im.meas['total'] = tr.cloud_total(cov)
                    self.cl_q.put((gen, key if W == 1024 else None, im, time.time() - t0, None))
            except tr.Cancelled:
                continue
            except Exception as ex:
                self.cl_q.put((gen, key, None, 0, str(ex)))
            with self.cl_lock:
                if self.cl_req is not None and self.cl_req[0] == gen:
                    self.cl_req = None

    def clouds_poll(self):
        got = False
        try:
            while True:
                gen, key, im, dt, err = self.cl_q.get_nowait()
                if gen != self.cl_gen:
                    continue
                if dt == -1:
                    self.cl_prog = err
                    if self.view.get() == 'clouds':
                        self.clouds_label()
                        if self.view_src is None:
                            self.redraw()
                    continue
                if err:
                    self.cl_err = err
                    self.cl_prog = None
                else:
                    self.cl_img = im
                    self.cl_err = None
                    self.clouds_meas(getattr(im, 'meas', None))
                    if key is not None:
                        self.cl_key = key
                        self.cl_prog = None
                        self.cl_dt = dt
                got = True
        except queue.Empty:
            pass
        if got and self.view.get() == 'clouds':
            if self.cl_err:
                self.view_src = None
                self.status('Could not draw the clouds: %s' % self.cl_err[:120])
            else:
                self.view_src = self.cl_img
            self.clouds_label()
            self.redraw()

    def clouds_meas(self, m):
        if not m or not hasattr(self, 'cl_meas'):
            return
        sy = [v for k, v in m.items() if k.startswith('sys')]
        parts = []
        if 'fair' in m:
            parts.append('fair weather %d %%' % round(m['fair'] * 100))
        if sy:
            parts.append('weather systems %d %% each' % round(sum(sy) / len(sy) * 100))
        if 'cirrus' in m:
            parts.append('cirrus %d %%' % round(m['cirrus'] * 100))
        txt = 'Cover now: ' + (' · '.join(parts) if parts else 'no clouds')
        if parts:
            txt += '\nAll together (with one weather system): %d %% of the planet has clouds' % round(m.get('total', 0) * 100)
        self.cl_meas.configure(text=txt)

    def clouds_label(self):
        p = getattr(self, 'cl_prog', None)
        if not tr.has_clouds(self.P):
            txt = ''
        elif self.cl_err:
            txt = 'clouds failed'
        elif p is not None:
            stage, f = p
            txt = ('working out the wind… %d%%' if stage == 'wind' else 'making the clouds… %d%%') % int(f * 100)
            if self.cl_img is not None:
                txt = 'updating · ' + txt
        elif self.cl_req is not None:
            txt = 'updating…'
        else:
            txt = 'clouds 1024 px · %.1f s' % getattr(self, 'cl_dt', 0)
        self.live_lab.configure(text=txt)
        if not self.proc and self.view.get() == 'clouds':
            if p is not None and p[0] == 'wind':
                self.status('Clouds: working out the wind (%d%%), only when the seed or the wind settings change' % int(p[1] * 100))
            elif p is not None:
                self.status('Clouds: drawing the cloud layers (%d%%)' % int(p[1] * 100))
            elif not self.cl_err and self.cl_img is not None:
                self.status('Clouds over the planet' + (' with one weather system' if self.cl_sys.get() else ', fair weather and cirrus only'))

    def clouds_view(self):
        if not tr.has_clouds(self.P):
            self.view_src = None
            if not self.proc:
                self.status('No clouds yet – tick “Volumetric clouds” on the Clouds tab')
        else:
            self.clouds_request()
            self.view_src = self.cl_img
            if not self.proc and self.cl_img is None:
                self.status('Clouds: starting…')
        self.clouds_label()
        self.update_export_state()
        self.redraw()

    def aurora_bg(self):
        L = self.live_last
        if L is None:
            return None, None
        return L['col'], (L['key'], L['W'])

    def tab_body(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text='Planet')
        p = sf.inner
        self.section(p, 'Name and randomness')
        g = ttk.Frame(p)
        g.pack(fill='x')
        self.v_name = tk.StringVar()
        self.v_seed = tk.StringVar()
        self.v_radius = tk.StringVar()
        ttk.Label(g, text='Name').grid(row=0, column=0, sticky='w', padx=8, pady=4)
        en = ttk.Entry(g, textvariable=self.v_name, width=24)
        en.grid(row=0, column=1, sticky='w', pady=4)
        en.bind('<Return>', self.commit_name)
        en.bind('<FocusOut>', self.commit_name)
        ttk.Label(g, text='Seed').grid(row=1, column=0, sticky='w', padx=8, pady=4)
        es = ttk.Entry(g, textvariable=self.v_seed, width=10)
        es.grid(row=1, column=1, sticky='w', pady=4)
        es.bind('<Return>', self.commit_seed)
        es.bind('<FocusOut>', self.commit_seed)
        ttk.Button(g, text='New random seed', command=self.random_seed).grid(row=1, column=2, padx=6)
        ttk.Label(g, text='Radius (m)').grid(row=2, column=0, sticky='w', padx=8, pady=4)
        er = ttk.Entry(g, textvariable=self.v_radius, width=12)
        er.grid(row=2, column=1, sticky='w', pady=4)
        er.bind('<Return>', self.commit_radius)
        er.bind('<FocusOut>', self.commit_radius)
        ttk.Label(g, text='for crater sizes and slopes', style='Dim.TLabel').grid(row=2, column=2, sticky='w', padx=6)
        self.section(p, 'File names')
        self.note(p, 'Starting names for Export. You choose the folder and the format each time you export.')
        g = ttk.Frame(p)
        g.pack(fill='x', pady=4)
        self.v_files = {}
        for i, (k, lab) in enumerate((('height', 'Height map'), ('color', 'Colour map'), ('normal', 'Normal map'))):
            ttk.Label(g, text=lab).grid(row=i, column=0, sticky='w', padx=8, pady=4)
            v = tk.StringVar()
            e = ttk.Entry(g, textvariable=v, width=40)
            e.grid(row=i, column=1, sticky='w', pady=4)
            e.bind('<Return>', self.commit_files)
            e.bind('<FocusOut>', self.commit_files)
            self.v_files[k] = v
        self.section(p, 'Preview camera')
        g = self.grid_box(p)
        Slider(self, g, 0, 'Tilt', ('preview', 'tilt'), -90, 90, 1)
        Slider(self, g, 1, 'View latitude', ('preview', 'view_lat'), -90, 90, 1)
        Slider(self, g, 2, 'View longitude', ('preview', 'view_lon'), 0, 360, 5)

    def snapshot(self):
        self.history.append(copy.deepcopy(self.P))
        del self.history[:-40]
        self.undo_btn.configure(state='normal')

    def undo(self, e=None):
        if e is not None and isinstance(self.focus_get(), (ttk.Entry, ttk.Spinbox, tk.Entry)):
            return
        if not self.history:
            return
        self.P = self.history.pop()
        if not self.history:
            self.undo_btn.configure(state='disabled')
        self.refresh_all()
        self.changed(snap=False)
        self.status('Undone')

    def palette(self, name=None):
        name = name or random.choice(list(PALETTES))
        R = random.uniform
        hi = float(self.P['relief']['high']); lo = float(self.P['relief']['low'])
        shift = [R(-10, 10) for _ in range(3)]
        st = []
        for lev, c in zip(PAL_LEVELS, PALETTES[name]):
            h = lev * (-lo if lev < 0 else hi)
            st.append([round(h / 10) * 10, [int(max(0, min(255, round(v + shift[k] + R(-8, 8))))) for k, v in enumerate(c)]])
        C = self.P['colors']
        C['stops'] = st
        top = PALETTES[name][-1]
        C['rock'] = [int(max(0, min(255, v * 0.85 + 10))) for v in PALETTES[name][4]]
        C['patch_color'] = [int(max(0, min(255, v + R(-25, 25)))) for v in PALETTES[name][3]]
        if name == 'ice':
            C['ice'] = [int(min(255, v + 6)) for v in top]
            C['cap_north'] = round(R(50, 70)); C['cap_south'] = round(R(50, 70))
        elif name in ('desert', 'volcanic', 'grey'):
            C['ice'] = [int(R(228, 245)), int(R(228, 245)), int(R(232, 250))]
            C['cap_north'] = random.choice([90, 90, round(R(78, 86))]); C['cap_south'] = random.choice([90, 90, round(R(78, 86))])
        else:
            C['ice'] = [int(R(228, 245)), int(R(232, 248)), int(R(238, 252))]
            C['cap_north'] = round(R(66, 80)); C['cap_south'] = round(R(66, 80))
        C['snow_line'] = round(hi * R(0.65, 0.95) / 50) * 50 if name not in ('desert', 'volcanic', 'grey') else 99999
        if name == 'alien':
            C['shallow'] = [int(R(60, 140)), int(R(100, 160)), int(R(110, 170))]
            C['deep'] = [int(R(20, 60)), int(R(20, 50)), int(R(50, 90))]
        else:
            C['shallow'] = [int(R(40, 70)), int(R(105, 135)), int(R(125, 150))]
            C['deep'] = [int(R(10, 22)), int(R(26, 44)), int(R(58, 84))]
        return name

    def randomize(self, what):
        self.commit_entries()
        self.snapshot()
        P = self.P
        R = random.uniform
        if what == 'all':
            P['shape']['ocean'] = random.random() < 0.55
            P['relief']['high'] = round(R(2500, 9000) / 50) * 50
            P['relief']['low'] = -round(R(2000, 7000) / 50) * 50
        if what in ('shape', 'all'):
            P['seed'] = random.randint(1, 99999)
            sh = P['shape']
            sh['land'] = round(R(0.2, 0.55) if sh['ocean'] else R(0.3, 0.7), 2)
            sh['continents'] = random.choice([0, 1, 2, 3, 4, 5, 6, 7, 8])
            sh['warp'] = round(R(0.2, 0.9), 2)
            sh['coast'] = round(R(0.25, 0.85), 2)
            sh['islands'] = round(R(0.0, 0.6), 2)
        if what in ('relief', 'all'):
            Rl = P['relief']
            Rl['mountains'] = round(R(0.2, 1.0), 2)
            Rl['mountain_size'] = round(R(0.7, 1.6), 2)
            Rl['mountain_area'] = round(R(0.2, 0.8), 2)
            Rl['ranges'] = round(R(0.0, 0.8), 2)
            Rl['hills'] = round(R(0.15, 0.8), 2)
            Rl['hill_size'] = round(R(0.6, 1.6), 2)
            Rl['plains'] = round(R(0.0, 0.7), 2)
            Rl['roughness'] = round(R(0.1, 0.7), 2)
            Rl['shelf'] = round(R(0.05, 0.5), 2)
            Rl['sharpness'] = round(R(0.7, 1.8), 2)
        if what in ('landforms', 'all'):
            Rl = P['relief']
            Rk = float(P['radius']) / 1000
            Rl['canyons'] = random.choice([0, 0, 0, round(R(0.2, 0.7), 2)])
            Rl['canyon_depth'] = round(R(1500, 6000) / 50) * 50
            Rl['canyon_width'] = round(max(5.0, Rk * R(0.08, 0.25)))
            Wt = P['water']
            Wt['rivers'] = round(R(0.3, 0.7), 2) if P['shape']['ocean'] and random.random() < 0.7 else random.choice([0, 0, round(R(0.2, 0.5), 2)])
            Wt['width'] = round(max(0.5, Rk * R(0.004, 0.012)), 1)
            Wt['depth'] = round(R(30, 200) / 5) * 5
            Wt['valleys'] = round(R(0.3, 0.8), 2)
            Wt['valley_width'] = round(R(5, 14) * 2) / 2
            PL = P['plateaus']
            PL['amount'] = random.choice([0, 0, round(R(0.2, 0.6), 2)])
            PL['height'] = round(R(800, 3500) / 50) * 50
            PL['size'] = round(R(0.7, 1.6), 2)
            PL['edge'] = round(R(0.2, 0.7), 2)
            CK = P['cracks']
            CK['seed'] = random.randint(1, 99999)
            CK['amount'] = random.choice([0, 0, 0, 0, round(R(0.3, 0.8), 2)]) if P['shape']['ocean'] else random.choice([0, 0, round(R(0.3, 0.8), 2)])
            CK['style'] = random.choice(['lines', 'lines', 'cells'])
            CK['count'] = random.randint(4, 12)
            CK['curvy'] = round(R(0.1, 0.6), 2)
            CK['width'] = round(max(0.5, Rk * R(0.01, 0.03)), 1)
            CK['depth'] = round(R(100, 600) / 10) * 10
            CK['ridges'] = round(R(0.0, 0.8), 2)
            CK['cell_size'] = round(max(10.0, Rk * R(0.3, 1.0)) / 5) * 5
            RG = P['ridge']
            RG['seed'] = random.randint(1, 99999)
            RG['height'] = 0.0 if P['shape']['ocean'] or random.random() < 0.85 else round(min(25000.0, Rk * R(0.01, 0.03) * 1000) / 100) * 100
            RG['width'] = float(round(max(2.0, Rk * R(0.03, 0.08))))
            RG['coverage'] = random.choice([360.0, 360.0, float(round(R(120, 300)))])
            RG['lon'] = float(random.randint(0, 359))
            RG['lat'] = 0.0
            RG['tilt'] = random.choice([0.0, 0.0, round(R(-8, 8), 1)])
            RG['segments'] = random.choice([0.0, round(R(0.1, 0.6), 2)])
            RG['ragged'] = round(R(0.3, 0.8), 2)
            RG['wander'] = round(R(0.1, 0.5), 2)
            V = P['volcanoes']
            V['seed'] = random.randint(1, 99999)
            V['count'] = random.choice([0, 0, 1, 2, 3, 5])
            V['size_km'] = round(max(10.0, float(P['radius']) / 1000 * R(0.2, 0.6)) / 5) * 5
            V['height'] = round(min(25000.0, V['size_km'] * R(15, 40)) / 100) * 100
            V['caldera'] = round(R(0.2, 0.8), 2)
        if what in ('craters', 'all'):
            C = P['craters']
            C['seed'] = random.randint(1, 99999)
            if what == 'craters' or not P['shape']['ocean']:
                C['count'] = random.choice([0, 300, 800, 1500, 3000, 6000]) if what == 'all' else int(R(300, 6000))
            else:
                C['count'] = random.choice([0, 0, 0, 100])
            C['min_km'] = round(R(1, 5), 1)
            C['max_km'] = round(R(40, 250))
            C['size_mix'] = round(R(1.5, 2.2), 2)
            C['depth'] = round(R(0.6, 1.3), 2)
            C['fresh'] = round(R(0.1, 0.7), 2)
            C['ejecta'] = round(R(0.2, 0.8), 2)
            C['rays'] = round(R(0.2, 0.8), 2)
        if what in ('clouds', 'all'):
            K = P['clouds']
            K['seed'] = random.randint(1, 999)
            K['swirl'] = round(R(0.5, 1.7), 2)
            K['swirl_size'] = round(R(0.6, 1.9), 2)
            K['wind'] = round(R(0.3, 1.8), 2)
            K['bands'] = random.choice([2, 3, 3, 3, 4, 5])
            K['streaks'] = round(R(0.35, 0.95), 2)
            K['breakup'] = round(R(0.2, 0.8), 2)
            K['fair_pct'] = float(round(R(15, 60)))
            K['speckle'] = round(R(0.1, 0.8), 2)
            K['systems'] = random.choice([0, 1, 2, 3, 3, 4])
            K['system_pct'] = float(round(R(20, 50)))
            K['cirrus_pct'] = random.choice([0.0, float(round(R(8, 35))), float(round(R(8, 35)))])
        if what in ('colours', 'all'):
            self.palette()
            C = P['colors']
            C['patches'] = round(R(0.15, 0.7), 2)
            C['patch_size'] = round(R(0.6, 1.6), 2)
            C['jitter'] = round(R(60, 300) / 10) * 10
            C['dry']['amount'] = random.choice([0, 0, round(R(0.3, 0.8), 2)]) if P['shape']['ocean'] else 0
            C['cold']['amount'] = random.choice([0, round(R(0.2, 0.6), 2)]) if P['shape']['ocean'] else 0
            C['sea_ice'] = round(R(0.3, 1.0), 2)
            C['crater_floor_amount'] = random.choice([0, 0, round(R(0.2, 0.6), 2)])
            fl = [s_[1] for s_ in C['stops']]
            C['crater_floor'] = [int(max(0, min(255, v * R(0.55, 0.8)))) for v in fl[min(1, len(fl) - 1)]]
            C['dry']['color'] = [int(R(160, 200)), int(R(130, 165)), int(R(85, 120))]
        if what == 'rings':
            r = P['rings']
            r.update({'zones': random.randint(2, 6), 'ringlets': round(R(0.3, 0.9), 2), 'detail': round(R(0.6, 1.8), 2),
                      'opacity': round(R(0.6, 0.95), 2), 'edge': round(R(0.1, 0.6), 2), 'variation': round(R(0.2, 0.6), 2),
                      'pattern': random.randint(0, 9999)})
            k = random.randint(1, 3)
            gaps = [[round(R(0.35, 0.75), 3), round(R(0.02, 0.05), 3), round(R(0.85, 1.0), 2)]]
            for _ in range(k - 1):
                gaps.append([round(R(0.12, 0.96), 3), round(R(0.003, 0.012), 3), round(R(0.6, 1.0), 2)])
            r['gaps'] = sorted(gaps)
        self.refresh_all()
        self.changed(snap=False)
        msg = 'Randomized %s – Undo goes back' % ('everything' if what == 'all' else what)
        self.after(300, lambda: self.status(msg))

    def volcano_seed(self):
        self.snapshot()
        self.P['volcanoes']['seed'] = random.randint(1, 99999)
        self.changed()

    def sample(self):
        path = filedialog.askopenfilename(parent=self, title='Picture to take the colours from',
                                          filetypes=[('Pictures', '*.png *.jpg *.jpeg *.bmp *.tga *.webp *.dds'), ('All files', '*.*')])
        if path:
            try:
                SampleWin(self, path)
            except Exception as ex:
                messagebox.showerror('Could not open picture', str(ex), parent=self)

    def place_toggled(self):
        if self.place_mode.get():
            if self.view.get() != 'live':
                self.view.set('live')
                self.update_view()
            self.status('Place features: click the map or the globe to add a %s, drag to move, right-click to remove'
                        % self.feat_type.get().lower())
        else:
            self.status('Live preview – press Build for the full-size maps')
        self.redraw()

    def placing(self):
        return self.place_mode.get() and self.view.get() == 'live' and self.live_view is not None

    def globe_xy(self, lat, lon):
        pv = self.P['preview']
        t = np.radians(float(pv['tilt']))
        a = np.radians(max(-90.0, min(90.0, float(pv['view_lat']) + self.rot[1])))
        la = np.radians(lat)
        dl = np.radians(lon - float(pv['view_lon']) - self.rot[0])
        u2 = np.cos(la) * np.sin(dl); z3 = np.cos(la) * np.cos(dl); y3 = np.sin(la)
        v2 = y3 * np.cos(a) - z3 * np.sin(a)
        z = y3 * np.sin(a) + z3 * np.cos(a)
        u = u2 * np.cos(t) + v2 * np.sin(t)
        v = -u2 * np.sin(t) + v2 * np.cos(t)
        return (u + 1) / 2 * 512, (1 - v) / 2 * 512, z

    def feature_near(self, lat, lon):
        best, bd = None, None
        R = float(self.P['radius']) / 1000.0
        for i, f in enumerate(self.P['features']):
            a = np.radians([lat, f['lat']]); b = np.radians([lon, f['lon']])
            d = np.degrees(np.arccos(np.clip(np.sin(a[0]) * np.sin(a[1]) + np.cos(a[0]) * np.cos(a[1]) * np.cos(b[0] - b[1]), -1, 1)))
            lim = max(3.0, min(40.0, np.degrees(float(f['size']) * 0.5 / R) * 0.7))
            if d <= lim and (bd is None or d < bd):
                best, bd = i, d
        return best

    def feature_remove_click(self, e):
        if not self.placing():
            return
        mp = self.map_point(self.sheet_xy(e))
        if mp is None:
            return
        i = self.feature_near(*mp)
        if i is None:
            return
        self.snapshot()
        kind = self.P['features'][i]['type']
        self.P['features'].pop(i)
        self.feat_ed.rebuild()
        self.changed()
        self.redraw()
        self.status('Removed a %s – Undo brings it back' % kind)

    def feature_marks(self):
        if self.view_geom is None:
            return
        s, ox, oy = self.view_geom
        cv = self.canvas
        R = float(self.P['radius']) / 1000.0
        act = self.fdrag[0] if self.fdrag is not None else -1
        for i, f in enumerate(self.P['features']):
            col = WARM if i == act else '#ffffff'
            lat, lon = float(f['lat']), float(f['lon'])
            ang = min(80.0, np.degrees(float(f['size']) * 0.5 / R))
            ry = max(5.0, ang / 180.0 * 512) * s
            rx = min(ry / max(np.cos(np.radians(lat)), 0.08), 512 * s)
            cx, cy = ox + (536 + lon / 360.0 * 1024) * s, oy + (90 - lat) / 180.0 * 512 * s
            for dx in (-1024 * s, 0, 1024 * s):
                x = cx + dx
                if ox + 536 * s - rx <= x <= ox + 1560 * s + rx:
                    cv.create_oval(x - rx, cy - ry, x + rx, cy + ry, outline=col, width=2, dash=(4, 3))
                    cv.create_text(x, cy, text=f['type'][0].upper(), fill=col, font=(FONT, 9, 'bold'))
            gx, gy, z = self.globe_xy(lat, lon)
            if z > 0.05:
                gr = max(5.0, 256 * np.sin(np.radians(min(80.0, ang)))) * s * max(z, 0.3) ** 0.5
                cv.create_oval(ox + gx * s - gr, oy + gy * s - gr, ox + gx * s + gr, oy + gy * s + gr, outline=col, width=2, dash=(4, 3))
        cv.create_rectangle(ox + 536 * s, oy, ox + 1560 * s, oy + 512 * s, outline=ACC, width=1)

    def crater_seed(self):
        self.snapshot()
        self.P['craters']['seed'] = random.randint(1, 99999)
        self.changed(snap=False)

    def sort_stops(self):
        self.P['colors']['stops'].sort(key=lambda s: s[0])
        for e in self.editors:
            e.rebuild()
        self.changed()

    def refresh_all(self):
        for s in self.sliders:
            s.refresh()
        for e in self.editors:
            e.rebuild()
        for s in self.swatches:
            s.refresh()
        for v, path in self.checks:
            v.set(bool(getp(self.P, path)))
        for v, path, names in self.combos:
            v.set(names.get(getp(self.P, path), ''))
        self.v_name.set(self.P['name'])
        self.v_seed.set(str(self.P['seed']))
        self.v_radius.set('%.0f' % float(self.P['radius']))
        for k, v in self.v_files.items():
            v.set(self.P['files'].get(k, '') or '')
        self.pick.configure(values=self.preset_names())
        self.pick.set(self.P['name'])
        self.update_title()
        self.update_view()
        self.update_res_info()

    def update_res_info(self):
        r = self.res.get()
        txt = '%s × %d  ·  %s' % (r, int(r) // 2, RES_INFO.get(r, ''))
        n = int(self.P['craters']['count'])
        if n > 3000:
            txt += '  ·  many craters: a bit longer'
        if r == '8192':
            txt += '  ·  big in game'
        self.res_info.configure(text=txt)

    def update_title(self):
        self.title('%s %s – %s%s' % (tr.APP_NAME, tr.APP_VERSION, self.P['name'], ' *' if self.dirty else ''))

    def changed(self, snap=None):
        self.dirty = True
        self.update_title()
        self.update_res_info()
        if hasattr(self, 'atmo_cfg'):
            self.atmo_dirty()
        if hasattr(self, 'aur_cfg'):
            self.aurora_dirty()
        if hasattr(self, 'cl_cfg'):
            self.clouds_dirty()
        if hasattr(self, 'ring_cv'):
            self.ring_schedule()
        if self.view.get() in ('live', 'atmo', 'aurora', 'clouds'):
            if self.pending:
                self.after_cancel(self.pending)
            self.pending = self.after(120, self.update_view)
        else:
            self.update_stale()

    def commit_name(self, _e=None):
        new = self.v_name.get().strip()
        old = self.P['name']
        if not new or new == old:
            self.v_name.set(old)
            return
        for k, v in list(self.P['files'].items()):
            if v and old in v:
                self.P['files'][k] = v.replace(old, new)
        self.P['name'] = new
        for k, v in self.v_files.items():
            if old in v.get():
                v.set(v.get().replace(old, new))
        self.changed()

    def commit_seed(self, _e=None):
        try:
            s = int(self.v_seed.get())
        except ValueError:
            self.v_seed.set(str(self.P['seed']))
            return
        if s != self.P['seed']:
            self.snapshot()
            self.P['seed'] = s
            self.changed()

    def commit_radius(self, _e=None):
        try:
            r = float(self.v_radius.get().replace(',', '.'))
            if r < 1000:
                raise ValueError
        except ValueError:
            self.v_radius.set('%.0f' % float(self.P['radius']))
            return
        if r != float(self.P['radius']):
            self.snapshot()
            self.P['radius'] = r
            self.changed()

    def random_seed(self):
        self.snapshot()
        self.P['seed'] = random.randint(1, 99999)
        self.v_seed.set(str(self.P['seed']))
        self.changed()

    def commit_files(self, _e=None):
        new = {k: v.get().strip() for k, v in self.v_files.items()}
        new = {k: v for k, v in new.items() if v}
        if new != {k: v for k, v in self.P['files'].items() if v}:
            self.P['files'] = new
            self.changed()

    def commit_entries(self):
        self.commit_name()
        self.commit_seed()
        self.commit_radius()
        self.commit_files()
        self.focus_set()

    def ask_save(self):
        if not self.dirty:
            return True
        r = messagebox.askyesnocancel('Unsaved changes', 'Save the changes to %s first?' % self.P['name'], parent=self)
        if r is None:
            return False
        if r:
            return self.save()
        return True

    def on_pick(self, _e=None):
        name = self.pick.get()
        if name == self.P['name'] and self.preset_file:
            return
        if not self.ask_save():
            self.pick.set(self.P['name'])
            return
        self.load(name)

    def load(self, name):
        path = os.path.join(tr.PRESETS, name + '.json')
        try:
            with open(path) as f:
                raw = json.load(f)
        except Exception as ex:
            messagebox.showerror('Could not load', str(ex), parent=self)
            return
        raw.setdefault('name', name)
        self.P = tr.normalize(raw)
        self.preset_file = path
        self.dirty = False
        self.history = []
        self.stop_live()
        self.live_last = None
        self.rot = [0.0, 0.0]
        self.atmo_img = None
        self.atmo_key = None
        self.atmo_texc = {}
        self.undo_btn.configure(state='disabled')
        self.refresh_all()

    def save(self, quiet=False):
        self.commit_entries()
        name = self.P['name'].strip()
        if not name or any(ch in name for ch in '\\/:*?"<>|'):
            messagebox.showerror('Name', 'Please give the planet a valid name.', parent=self)
            return False
        path = os.path.join(tr.PRESETS, name + '.json')
        if os.path.exists(path) and os.path.abspath(path) != os.path.abspath(self.preset_file or ''):
            if not messagebox.askyesno('Overwrite', '%s already exists. Overwrite it?' % name, parent=self):
                return False
        self.P = tr.normalize(self.P)
        with open(path, 'w') as f:
            json.dump(self.P, f, indent=1)
        self.preset_file = path
        self.dirty = False
        for e in self.editors:
            e.rebuild()
        self.pick.configure(values=self.preset_names())
        self.pick.set(name)
        self.update_title()
        if not quiet:
            self.status('Saved %s' % os.path.relpath(path, tr.TOOL))
        return True

    def new(self):
        if not self.ask_save():
            return
        name = simpledialog.askstring('New planet', 'Name (for example Lazarus30).\nIt starts as a copy of %s with a new seed.' % self.P['name'], parent=self)
        if not name:
            return
        name = name.strip()
        if os.path.exists(os.path.join(tr.PRESETS, name + '.json')):
            messagebox.showerror('New', '%s already exists.' % name, parent=self)
            return
        P = copy.deepcopy(self.P)
        P['name'] = name
        P['seed'] = random.randint(1, 99999)
        P['craters']['seed'] = random.randint(1, 99999)
        P['files'] = {'height': name + '_height.dds', 'color': name + '_color.dds', 'normal': name + '_normal.dds'}
        self.P = tr.normalize(P)
        self.preset_file = None
        self.dirty = True
        self.history = []
        self.undo_btn.configure(state='disabled')
        self.refresh_all()
        self.save()

    def save_as(self):
        name = simpledialog.askstring('Save as', 'New name:', parent=self, initialvalue=self.P['name'])
        if not name or name.strip() == self.P['name']:
            return
        self.v_name.set(name.strip())
        self.commit_name()
        self.preset_file = None
        self.save()

    def out_path(self, res=None):
        res = int(res or self.res.get())
        n = self.P['name']
        return os.path.join(tr.OUTROOT, n if res == 4096 else '%s_%d' % (n, res))

    def open_out(self):
        d = self.out_path()
        if not os.path.isdir(d):
            d = tr.OUTROOT
        os.makedirs(d, exist_ok=True)
        open_folder(d)

    def is_stale(self, res=None):
        f = os.path.join(self.out_path(res), self.P['name'] + '_preset.json')
        if not os.path.isfile(f):
            return None
        try:
            with open(f) as fh:
                built = tr.normalize(json.load(fh))
        except Exception:
            return None
        a = {k: v for k, v in built.items() if k not in ('atmosphere', 'aurora', 'clouds')}
        b = {k: v for k, v in tr.normalize(copy.deepcopy(self.P)).items() if k not in ('atmosphere', 'aurora', 'clouds')}
        return json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)

    def update_stale(self):
        if self.proc:
            return
        if self.view.get() in ('preview', 'flat') and self.is_stale():
            self.status('Settings changed since this build – press Build to update')

    def live_key(self):
        return json.dumps({k: v for k, v in self.P.items() if k not in ('atmosphere', 'rings')}, sort_keys=True, default=str)

    def update_view(self, from_live=False):
        self.pending = None
        v = self.view.get()
        if v == 'aurora':
            self.live_lab.configure(text='')
            self.aurora_view()
            return
        if v == 'clouds':
            self.live_lab.configure(text='')
            self.clouds_view()
            return
        if v == 'atmo':
            key = self.live_key()
            if self.atmo_src != 'build' and not from_live:
                self.request_live(key)
            if not self.ingame_any():
                self.view_src = None
                if not self.proc:
                    self.status('Nothing to show yet – tick an atmosphere, clouds or an aurora (or add glowing lava)')
            else:
                self.atmo_request()
                self.view_src = self.atmo_img
                if not self.proc:
                    bits = [t for t, on in (('atmosphere', tr.has_atmo(self.P)), ('clouds', tr.has_clouds(self.P) and self.ig_clouds.get()),
                                            ('aurora', tr.has_aurora(self.P) and self.ig_aurora.get()),
                                            ('lava glow', self.ig_glow.get() and self.ingame_em()[0] is not None)) if on]
                    self.status('In game: the planet as KSP’s map view shows it' + (' with ' + ', '.join(bits) if bits else '') +
                                ' · drag left or right to move the sun')
            self.update_live_label(key)
            self.update_export_state()
            self.redraw()
            return
        if v == 'live':
            key = self.live_key()
            L = self.live_last
            if L is not None:
                col, hm, gx, gy = L['col'], L['hm'], L['gx'], L['gy']
                em = L.get('em')
                k = float(self.P['normal_strength'])
                ocean = (hm < 0).astype(np.float32) if self.P['shape']['ocean'] else None
                mode = self.show.get()
                if mode == 'Height':
                    g = np.asarray(tr.height_grey(hm)).astype(np.float32)
                    sh = np.clip(g[..., None] * tr.shade_map(gx, gy, k * 0.6)[..., None], 0, 255)
                    tex = np.repeat(sh, 3, -1).astype(np.uint8)
                    flat = Image.fromarray(tex)
                    gtex = tex
                    gx2, gy2 = gx * 0, gy * 0
                    ocean = None
                    em = None
                elif mode == 'Colour, no shading':
                    flat = Image.fromarray(col)
                    gtex, gx2, gy2 = col, gx, gy
                    em = None
                else:
                    fl = col.astype(np.float32) * tr.shade_map(gx, gy, k)[..., None]
                    if em is not None:
                        fl = fl + em.astype(np.float32) * np.float32(0.7)
                    flat = Image.fromarray(np.clip(fl, 0, 255).astype(np.uint8))
                    gtex, gx2, gy2 = col, gx, gy
                if flat.size != (1024, 512):
                    flat = flat.resize((1024, 512), Image.LANCZOS if flat.size[0] > 1024 else Image.BICUBIC)
                sheet = Image.new('RGB', (1024 + 512 + 24, 512 + 34), (13, 15, 20))
                sheet.paste(flat, (512 + 24, 0))
                d = ImageDraw.Draw(sheet)
                f17 = sheet_font(17)
                hint = 'drag to turn · double-click resets'
                d.text((256 - d.textlength(hint, font=f17) / 2, 518), hint, fill=DIM, font=f17)
                rng = 'height %.0f m to %.0f m' % (float(hm.min()), float(hm.max()))
                d.text((536, 518), rng, fill=DIM, font=f17)
                self.live_view = {'tex': gtex, 'gx': gx2, 'gy': gy2, 'ocean': ocean, 'k': k, 'sheet': sheet, 'hm': hm, 'em': em}
                sheet = sheet.copy()
                sheet.paste(self.globe(512), (0, 0))
                self.view_src = sheet
            else:
                self.view_src = None
                self.live_view = None
            if not self.proc and not self.place_mode.get():
                self.status('Live preview – press Build for the full-size maps')
            if not from_live:
                self.request_live(key)
            self.update_live_label(key)
        else:
            self.live_lab.configure(text='')
            f = os.path.join(self.out_path(), self.P['name'] + ('_preview.png' if v == 'preview' else '_color.png'))
            if os.path.isfile(f):
                try:
                    self.view_src = Image.open(f).convert('RGB')
                    self.view_src.load()
                except Exception:
                    self.view_src = None
                if not self.proc:
                    self.status('Settings changed since this build – press Build to update' if self.is_stale()
                                else 'Showing build at %s' % self.res.get())
            else:
                self.view_src = None
                if not self.proc:
                    self.status('Nothing built at %s yet – press Build' % self.res.get())
        self.update_export_state()
        self.redraw()

    def globe(self, S):
        lv = self.live_view
        pv = self.P['preview']
        vlat = max(-90.0, min(90.0, float(pv['view_lat']) + self.rot[1]))
        return tr.render_globe(lv['tex'], lv['gx'], lv['gy'], S, float(pv['tilt']), vlat, float(pv['view_lon']) + self.rot[0],
                               lv['k'], ocean=lv['ocean'], emis=lv.get('em'))

    def sheet_xy(self, e):
        if self.view_geom is None:
            return None
        s, ox, oy = self.view_geom
        return (e.x - ox) / s, (e.y - oy) / s

    def map_point(self, p):
        if p is None:
            return None
        x, y = p
        if 536 <= x < 1560 and 0 <= y < 512:
            return float(90.0 - (y + 0.5) / 512.0 * 180.0), float(((x - 536 + 0.5) / 1024.0 * 360.0) % 360.0)
        u = (x + 0.5) / 512.0 * 2 - 1
        v = 1 - (y + 0.5) / 512.0 * 2
        r2 = u * u + v * v
        if r2 >= 1:
            return None
        z = np.sqrt(1 - r2)
        pv = self.P['preview']
        t = np.radians(float(pv['tilt']))
        a = np.radians(max(-90.0, min(90.0, float(pv['view_lat']) + self.rot[1])))
        u2 = u * np.cos(t) - v * np.sin(t)
        v2 = u * np.sin(t) + v * np.cos(t)
        y3 = v2 * np.cos(a) + z * np.sin(a)
        z3 = -v2 * np.sin(a) + z * np.cos(a)
        lat = np.degrees(np.arcsin(max(-1.0, min(1.0, y3))))
        lon = (np.degrees(np.arctan2(u2, z3)) + float(pv['view_lon']) + self.rot[0]) % 360
        return float(lat), float(lon)

    def hover(self, e):
        if self.view.get() != 'live' or self.live_view is None:
            return
        mp = self.map_point(self.sheet_xy(e))
        if mp is None:
            self.hover_lab.configure(text='')
            return
        hm = self.live_view['hm']
        H, W = hm.shape
        r = min(H - 1, max(0, int((90 - mp[0]) / 180 * H)))
        c = int(mp[1] / 360 * W) % W
        h = float(hm[r, c])
        txt = 'latitude %6.1f°   map longitude %6.1f°   height %7.0f m' % (mp[0], mp[1], h)
        if self.P['shape']['ocean'] and h < 0:
            txt += '  (under water)'
        self.hover_lab.configure(text=txt)

    def drag_start(self, e):
        self.drag = None
        self.fdrag = None
        self.adrag = None
        if self.atmo_drag_start(e):
            return
        if self.view.get() != 'live' or self.live_view is None:
            return
        p = self.sheet_xy(e)
        if self.place_mode.get():
            mp = self.map_point(p)
            if mp is None:
                return
            self.snapshot()
            i = self.feature_near(*mp)
            if i is None:
                t = self.feat_type.get().lower()
                f = tr.default_feature(t if t in tr.FEATURE_TYPES else 'crater', float(self.P['radius']))
                f['lat'], f['lon'] = round(mp[0], 1), round(mp[1], 1)
                self.P['features'].append(f)
                i = len(self.P['features']) - 1
                self.fdrag = [i, True]
                self.status('Added a %s at %.1f°, %.1f° – drag to move it, settings on the Features tab' % (t, f['lat'], f['lon']))
            else:
                self.fdrag = [i, False]
            self.redraw()
            return
        if p and (p[0] - 256) ** 2 + (p[1] - 256) ** 2 <= 256 ** 2:
            self.drag = (p[0], p[1], self.rot[0], self.rot[1])

    def drag_move(self, e):
        if self.adrag is not None:
            self.atmo_drag_move(e)
            return
        if self.fdrag is not None:
            mp = self.map_point(self.sheet_xy(e))
            if mp is not None:
                f = self.P['features'][self.fdrag[0]]
                f['lat'], f['lon'] = round(mp[0], 1), round(mp[1], 1)
                self.fdrag[1] = True
                self.redraw(fast=True)
            return
        if self.drag is None:
            return
        p = self.sheet_xy(e)
        if not p:
            return
        x0, y0, r0, r1 = self.drag
        self.rot[0] = (r0 - (p[0] - x0) * 0.35) % 360
        self.rot[1] = max(-180.0, min(180.0, r1 + (p[1] - y0) * 0.35))
        if not getattr(self, 'spin_pending', False):
            self.spin_pending = True
            self.after_idle(lambda: self.respin(True))

    def drag_end(self, _e=None):
        if self.adrag is not None:
            self.atmo_drag_end()
            return
        if self.fdrag is not None:
            i, moved = self.fdrag
            self.fdrag = None
            if moved:
                self.feat_ed.rebuild()
                self.changed()
            elif self.history:
                self.history.pop()
                if not self.history:
                    self.undo_btn.configure(state='disabled')
            self.redraw()
            return
        if self.drag is not None:
            self.drag = None
            self.respin(False)

    def drag_reset(self, e):
        if self.place_mode.get():
            return
        p = self.sheet_xy(e)
        if self.view.get() == 'live' and self.live_view is not None and p and (p[0] - 256) ** 2 + (p[1] - 256) ** 2 <= 256 ** 2:
            self.rot = [0.0, 0.0]
            self.respin(False)

    def respin(self, quick):
        self.spin_pending = False
        lv = self.live_view
        if lv is None or self.view.get() != 'live':
            return
        sph = self.globe(256 if quick else 512)
        if quick:
            sph = sph.resize((512, 512), Image.BILINEAR)
        sheet = lv['sheet'].copy()
        sheet.paste(sph, (0, 0))
        self.view_src = sheet
        self.redraw(fast=quick)

    def update_live_label(self, key=None):
        v = self.view.get()
        if v not in ('live', 'atmo') or (v == 'atmo' and not self.ingame_any()):
            txt = ''
        elif v == 'atmo' and self.atmo_src == 'build':
            txt = 'ground from the %s build' % self.res.get()
        elif self.proc:
            txt = 'preview waits while building'
        elif self.live_err:
            txt = 'preview failed: %s' % self.live_err[:60]
        else:
            key = key or self.live_key()
            L = self.live_last
            if L is not None and L['key'] == key:
                txt = ('%d px · %.1f s' % (L['W'], L['dt'])) if L['dt'] >= 0.05 else '%d px' % L['W']
                if L['W'] < self.live_target():
                    txt += ' – sharpening…'
            else:
                txt = 'updating…'
        self.live_lab.configure(text=txt)

    def live_target(self):
        try:
            return int(self.live_size.get())
        except ValueError:
            return 512

    def live_size_changed(self, _e=None):
        S = load_settings()
        S['live_size'] = self.live_target()
        save_settings(S)
        self.update_view()

    def request_live(self, key):
        if self.view.get() not in ('live', 'atmo'):
            return
        if self.live_after:
            self.after_cancel(self.live_after)
        self.live_after = self.after(200, lambda: self.start_live(key))

    def start_live(self, key):
        self.live_after = None
        if self.proc:
            self.update_live_label(key)
            return
        sizes = (256, self.live_target())
        L = self.live_last
        if L is not None and L['key'] == key and L['W'] >= sizes[-1]:
            return
        P = tr.normalize(copy.deepcopy(self.P))
        if L is not None and L['hk'] == tr.height_key(P) and L['W'] >= sizes[0]:
            sizes = sizes[1:]
        r = self.live_req
        if r is not None and r[1] == key and r[3] == sizes:
            return
        self.live_err = None
        with self.live_lock:
            self.live_gen += 1
            self.live_req = (self.live_gen, key, P, sizes)
            if self.live_thread is None:
                self.live_thread = threading.Thread(target=self.live_worker, daemon=True)
                self.live_thread.start()
        self.update_live_label(key)

    def stop_live(self):
        with self.live_lock:
            self.live_gen += 1
            self.live_req = None

    def live_worker(self):
        while True:
            with self.live_lock:
                req = self.live_req
                if req is None:
                    self.live_thread = None
                    return
            gen, key, P, sizes = req

            def cancel(gen=gen):
                r = self.live_req
                if r is None or r[0] != gen:
                    raise tr.Cancelled()
            try:
                hk = tr.height_key(P)
                for W in sizes:
                    if W != sizes[-1] and ('H', hk, sizes[-1]) in self.live_cache:
                        continue
                    t0 = time.time()
                    col, hm, gx, gy, em = tr.live_maps(P, W, self.live_cache, cancel, workers=tr.THREADS)
                    self.live_q.put((gen, key, hk, W, (col, hm, gx, gy, em), None, time.time() - t0))
            except tr.Cancelled:
                continue
            except Exception as ex:
                self.live_q.put((gen, key, '', 0, None, str(ex), 0))
            with self.live_lock:
                if self.live_req is not None and self.live_req[0] == gen:
                    self.live_req = None

    def live_poll(self):
        got = False
        try:
            while True:
                gen, key, hk, W, maps, err, dt = self.live_q.get_nowait()
                if maps is None:
                    if gen == self.live_gen:
                        self.live_err = err
                        got = True
                elif gen == self.live_gen:
                    col, hm, gx, gy, em = maps
                    self.live_last = {'key': key, 'hk': hk, 'W': W, 'col': col, 'hm': hm, 'gx': gx, 'gy': gy, 'em': em, 'dt': dt}
                    got = True
        except queue.Empty:
            pass
        except tk.TclError:
            return
        if got:
            if self.view.get() in ('live', 'atmo'):
                self.update_view(from_live=True)
            else:
                self.update_live_label()
        self.atmo_poll()
        self.aurora_poll()
        self.clouds_poll()
        try:
            self.after(100, self.live_poll)
        except tk.TclError:
            pass

    def schedule_redraw(self):
        if self.redraw_id:
            self.after_cancel(self.redraw_id)
        self.redraw_id = self.after(60, self.redraw)
        if self.view.get() == 'clouds':
            if getattr(self, 'cl_resize', None):
                self.after_cancel(self.cl_resize)
            self.cl_resize = self.after(400, self.clouds_request)
        if self.view.get() == 'aurora':
            if getattr(self, 'aur_resize', None):
                self.after_cancel(self.aur_resize)
            self.aur_resize = self.after(400, self.aurora_request)
        if self.view.get() == 'atmo':
            if getattr(self, 'atmo_resize', None):
                self.after_cancel(self.atmo_resize)
            self.atmo_resize = self.after(400, self.atmo_request)

    def redraw(self, fast=False):
        self.redraw_id = None
        self.canvas.delete('all')
        cw, ch = max(10, self.canvas.winfo_width()), max(10, self.canvas.winfo_height())
        if self.view_src is None:
            self.view_geom = None
            msg = 'Making the preview…' if self.view.get() == 'live' else 'No picture yet'
            if self.view.get() == 'atmo':
                msg = 'Drawing the planet as in game…' if self.ingame_any() else 'Nothing to show yet – tick an atmosphere, clouds or an aurora'
            if self.view.get() == 'clouds':
                cp = getattr(self, 'cl_prog', None)
                msg = ('Working out the wind… %d%%' % int(cp[1] * 100) if cp and cp[0] == 'wind' else
                       'Making the clouds… %d%%' % int(cp[1] * 100) if cp else 'Making the clouds…')
                if not tr.has_clouds(self.P):
                    msg = 'No clouds – tick “Volumetric clouds” on the Clouds tab'
            if self.view.get() == 'aurora':
                msg = 'Drawing the aurora…' if tr.has_aurora(self.P) else 'No aurora – tick “Aurora” on the Aurora tab'
            self.canvas.create_text(cw // 2, ch // 2, text=msg, fill=DIM, font=(FONT, 12))
            return
        iw, ih = self.view_src.size
        s = min((cw - 16) / iw, (ch - 16) / ih)
        w2, h2 = max(1, int(iw * s)), max(1, int(ih * s))
        im = self.view_src.resize((w2, h2), Image.BILINEAR if fast else Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(im)
        self.canvas.create_image(cw // 2, ch // 2, image=self.tkimg)
        self.view_geom = (w2 / float(iw), cw // 2 - w2 / 2.0, ch // 2 - h2 / 2.0)
        if self.placing():
            self.feature_marks()

    def status(self, t):
        self.stat.configure(text=t)

    def log(self, line):
        self.logbox.configure(state='normal')
        self.logbox.insert('end', line + '\n')
        self.logbox.see('end')
        self.logbox.configure(state='disabled')

    def builds(self):
        return [r for r in RES[::-1] if os.path.isfile(os.path.join(self.out_path(r), self.P['name'] + '_height.png'))]

    def update_export_state(self):
        self.export_btn.configure(state='normal' if self.builds() and not self.proc else 'disabled')

    def set_busy(self, busy):
        self.build_btn.configure(state='disabled' if busy else 'normal')
        self.cancel_btn.configure(state='normal' if busy else 'disabled')
        self.update_export_state()

    def run(self, args, done):
        if self.proc:
            return
        cmd = ([sys.executable] if tr.FROZEN else [sys.executable, '-u', GEN]) + args
        self.log('> ' + ' '.join(args[:1] + [os.path.basename(a) for a in args[1:]]))
        try:
            env = dict(os.environ, PYTHONUNBUFFERED='1')
            self.proc = subprocess.Popen(cmd, cwd=tr.TOOL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL, text=True, bufsize=1, creationflags=NOWIN, env=env)
        except Exception as ex:
            messagebox.showerror('Could not start', str(ex), parent=self)
            return
        self.done_cb = done
        self.stop_live()
        self.update_live_label()
        threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()
        self.set_busy(True)
        self.after(100, self.poll)

    def reader(self, p):
        for line in p.stdout:
            self.q.put(line.rstrip('\n'))
        p.wait()
        self.q.put(None)

    def poll(self):
        finished = False
        try:
            while True:
                line = self.q.get_nowait()
                if line is None:
                    finished = True
                    break
                self.log(line)
                self.progress(line)
        except queue.Empty:
            pass
        if finished:
            rc = self.proc.returncode
            self.proc = None
            self.set_busy(False)
            self.done_cb(rc)
            if self.view.get() == 'live':
                self.update_view()
        else:
            self.after(100, self.poll)

    def progress(self, line):
        w = line.split()
        try:
            if w and w[0] == 'height' and w[-1].endswith('%'):
                pct = int(w[-1].rstrip('%'))
                self.prog['value'] = 0.6 * pct
                self.status('Shaping the ground – %d%%' % pct)
            elif w and w[0] == 'color' and w[-1].endswith('%'):
                pct = int(w[-1].rstrip('%'))
                self.prog['value'] = 60 + 0.25 * pct
                self.status('Colouring – %d%%' % pct)
            elif 'color' in w and 'done' in w:
                self.prog['value'] = 86
                self.status('Saving the maps')
            elif 'files' in w and 'done' in w:
                self.prog['value'] = 92
                self.status('Making the preview sheet')
            elif 'DONE' in w:
                self.prog['value'] = 100
        except (ValueError, IndexError):
            pass

    def build(self):
        if not self.save(quiet=True):
            return
        self.prog['value'] = 0
        self.status('Starting…')
        self.run(['make', self.preset_file, '--res', self.res.get()], self.built)

    cancelled = False

    def built(self, rc):
        if self.cancelled:
            self.cancelled = False
            self.status('Cancelled')
        elif rc == 0:
            self.prog['value'] = 100
            self.view.set('preview')
            self.update_view()
            self.status('Done – %s at %s' % (self.P['name'], self.res.get()))
        else:
            self.status('Build failed – see the log below')

    def cancel(self):
        if self.proc:
            self.cancelled = True
            self.proc.terminate()

    def export(self):
        self.commit_entries()
        b = self.builds()
        if not b:
            messagebox.showinfo('Build first', 'Press Build first – Export saves the files of a build.', parent=self)
            return
        ExportDialog(self, b)

    def close(self):
        if self.proc:
            if not messagebox.askyesno('Building', 'A build is running. Stop it and quit?', parent=self):
                return
            self.proc.terminate()
        if not self.ask_save():
            return
        self.destroy()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in tr.COMMANDS:
        tr.main()
        return
    if os.name == 'nt':
        try:
            import ctypes
            if tr.FROZEN:
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == '__main__':
    main()
