import os, copy, queue, threading
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import biomemaker as bmk
import kopmod


class BiomeWindow(tk.Toplevel):
    def __init__(self, app, ui, S):
        super().__init__(app)
        self.app, self.ui, self.S = app, ui, S
        self.configure(bg=ui.BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry('%dx%d+50+40' % (min(1480, sw - 80), min(900, sh - 110)))
        st = ttk.Style(self)
        st.configure('Card.TCheckbutton', background=ui.PANEL)
        st.map('Card.TCheckbutton', background=[('active', ui.PANEL)])
        self.q = queue.Queue()
        self.gen = 0
        self.after_id = None
        self.layers = self.idx = self.G = self.base = self.relief = None
        self.layer_key = None
        self.history = []
        self.cards = []
        self.last_stroke = None
        self.img_box = None
        self.name = None
        self.v_tool = tk.StringVar(value='look')
        self.v_paint = tk.StringVar()
        self.v_brush = tk.DoubleVar(value=50.0)
        self.v_alpha = tk.DoubleVar(value=0.6)
        self.v_borders = tk.BooleanVar(value=True)
        self.v_relief = tk.BooleanVar(value=True)
        self.build()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Control-z>', self.undo)
        self.load()
        self.after(100, self.poll)

    def build(self):
        ui = self.ui
        pw = ttk.PanedWindow(self, orient='horizontal')
        pw.pack(fill='both', expand=True)
        left = ttk.Frame(pw, padding=(8, 8, 0, 8))
        right = ttk.Frame(pw, padding=(8, 8, 12, 8))
        pw.add(left, weight=0)
        pw.add(right, weight=1)
        sf = ui.ScrollFrame(left)
        sf.pack(fill='both', expand=True)
        sf.configure(width=600)
        sf.canvas.configure(width=580)
        p = self.panel = sf.inner
        self.head = ttk.Label(p, text='', style='Dim.TLabel', wraplength=560, justify='left')
        self.head.pack(anchor='w', pady=(4, 0))
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(8, 0))
        ttk.Button(r, text='Suggest biomes', command=self.suggest).pack(side='left', padx=(8, 6))
        ttk.Button(r, text='Add biome', command=self.add).pack(side='left')
        ttk.Label(p, text='Painting', style='Head.TLabel').pack(anchor='w', pady=(14, 4))
        r = ttk.Frame(p)
        r.pack(fill='x')
        for val, txt in (('look', 'Look'), ('paint', 'Paint'), ('erase', 'Erase')):
            ttk.Radiobutton(r, text=txt, value=val, variable=self.v_tool, style='Toolbutton', command=self.tool_changed).pack(side='left', padx=(8 if val == 'look' else 0, 4))
        ttk.Label(r, text='with').pack(side='left', padx=(10, 6))
        self.paint_cb = ttk.Combobox(r, textvariable=self.v_paint, width=24, state='readonly')
        self.paint_cb.pack(side='left')
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Label(r, text='Brush size').pack(side='left', padx=(8, 8))
        self.brush_scale = ttk.Scale(r, from_=1, to=500, orient='horizontal', variable=self.v_brush, length=260,
                                     command=lambda v: self.brush_text())
        self.brush_scale.pack(side='left')
        self.brush_lab = ttk.Label(r, text='', style='Dim.TLabel')
        self.brush_lab.pack(side='left', padx=6)
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        ttk.Button(r, text='Clear all painting', command=self.clear_paint).pack(side='left', padx=8)
        ttk.Label(p, text='Painted areas win over the rules. Erase brings back what the rules give there.',
                  style='Dim.TLabel', wraplength=560).pack(anchor='w', padx=8, pady=(4, 0))
        ttk.Label(p, text='Biomes', style='Head.TLabel').pack(anchor='w', pady=(14, 4))
        ttk.Label(p, text='Each spot gets the first biome in the list whose rules fit it, so the order counts: put the special '
                          'ones first and a catch-all last. Leave a field empty for no limit.',
                  style='Dim.TLabel', wraplength=560, justify='left').pack(anchor='w', padx=8)
        self.cards_frame = ttk.Frame(p)
        self.cards_frame.pack(fill='x', pady=(6, 0))
        self.canvas = tk.Canvas(right, bg='#0d0f14', highlightthickness=1, highlightbackground=ui.LINE, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.show())
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Button-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<Leave>', lambda e: (self.readout.configure(text=''), self.brush_mark()))
        r = ttk.Frame(right)
        r.pack(fill='x', pady=(6, 0))
        ttk.Label(r, text='Show biomes').pack(side='left')
        ttk.Scale(r, from_=0, to=1, orient='horizontal', variable=self.v_alpha, length=160, command=lambda v: self.show()).pack(side='left', padx=6)
        ttk.Checkbutton(r, text='Borders', variable=self.v_borders, command=self.show).pack(side='left', padx=8)
        ttk.Checkbutton(r, text='Relief', variable=self.v_relief, command=self.show).pack(side='left')
        ttk.Button(r, text='Copy Biomes node', command=self.copy_cfg).pack(side='right')
        ttk.Button(r, text='Save biome map…', command=self.save_png).pack(side='right', padx=6)
        self.legend = ttk.Frame(right)
        self.legend.pack(fill='x', pady=(6, 0))
        self.readout = ttk.Label(right, text='', style='Dim.TLabel')
        self.readout.pack(fill='x', pady=(4, 0))
        self.stat = ttk.Label(right, text='', style='Dim.TLabel', wraplength=820, justify='left')
        self.stat.pack(fill='x', pady=(2, 0))

    def brush_text(self):
        r = float(self.v_brush.get())
        self.brush_lab.configure(text=('%.0f km' if r >= 10 else '%.2g km') % r)

    def status(self, t):
        self.stat.configure(text=t)

    def load(self):
        P = self.app.P
        self.name = P['name']
        self.P_ref = P
        self.title('Biome Map Maker - %s' % self.name)
        self.bm = bmk.bm_entry(P.get('biome_map'))
        self.build_dir = self.S.kop_build(P)
        self.layers = self.idx = self.base = self.relief = None
        self.history = []
        R = float(self.S.bio_radius(P))
        top = np.pi * R / 1000.0 / 4
        self.brush_scale.configure(from_=top / 100, to=top)
        self.v_brush.set(float('%.2g' % (top / 6)))
        self.brush_text()
        if not self.build_dir:
            self.head.configure(text='No build of %s yet. Press Build first: the biomes come from the heights and colours of a build.' % self.name)
            self.rebuild_cards()
            self.show()
            return
        self.head.configure(text='Uses the build in out/%s. Export to mod on the Config tab writes these biomes and their map.' % os.path.basename(self.build_dir))
        self.status('Reading the build…')
        self.gen += 1
        g, P2, b = self.gen, copy.deepcopy(P), self.build_dir

        def job():
            try:
                L = self.S.bio_layers(P2, b, bmk.W_MAP)
                col = Image.open(os.path.join(b, P2['name'] + '_color.png')).convert('RGB').resize((bmk.W_MAP, bmk.W_MAP // 2), Image.BOX)
                self.q.put(('layers', g, (L, np.asarray(col))))
            except Exception as ex:
                self.q.put(('err', g, str(ex)))
        threading.Thread(target=job, daemon=True).start()

    def poll(self):
        if not self.winfo_exists():
            return
        if self.app.P is not self.P_ref or self.app.P.get('name') != self.name:
            self.load()
        try:
            while True:
                kind, g, data = self.q.get_nowait()
                if g != self.gen:
                    continue
                if kind == 'layers':
                    self.layers, self.base = data
                    self.relief = bmk.relief(self.layers['h'])
                    if not self.bm['biomes']:
                        self.bm = bmk.suggest(self.S, self.app.P, self.build_dir)
                        self.store(snap=False)
                        self.status('Suggested biomes for %s from its build. Change them as you like.' % self.name)
                    else:
                        self.status('')
                    self.rebuild_cards()
                    self.recalc()
                elif kind == 'idx':
                    self.idx, self.G = data
                    self.show()
                    self.update_legend()
                else:
                    self.status('Error: ' + data)
        except queue.Empty:
            pass
        self.after(80, self.poll)

    def store(self, snap=True):
        if snap:
            self.history.append(copy.deepcopy(self.app.P.get('biome_map')))
            del self.history[:-40]
        self.app.P['biome_map'] = copy.deepcopy(self.bm)
        self.app.dirty = True
        self.app.update_title()
        ct = getattr(self.app, 'cfg_tab', None)
        if ct is not None:
            ct.schedule()

    def changed(self, rebuild=False, snap=True):
        self.store(snap)
        if rebuild:
            self.rebuild_cards()
        self.update_paint_list()
        self.schedule()

    def schedule(self, ms=150):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.after_id = self.after(ms, self.recalc)

    def recalc(self):
        self.after_id = None
        if self.layers is None:
            return
        self.gen += 1
        g, L, bm = self.gen, self.layers, copy.deepcopy(self.bm)

        def job():
            try:
                self.q.put(('idx', g, bmk.assign(L, bm)))
            except Exception as ex:
                self.q.put(('err', g, str(ex)))
        threading.Thread(target=job, daemon=True).start()

    def undo(self, e=None):
        if e is not None and isinstance(self.focus_get(), (ttk.Entry, tk.Entry)):
            return
        if not self.history:
            return
        self.bm = bmk.bm_entry(self.history.pop())
        self.store(snap=False)
        self.rebuild_cards()
        self.update_paint_list()
        self.schedule(0)

    def suggest(self):
        if not self.build_dir or self.layers is None:
            messagebox.showinfo('Biomes', 'Press Build first: the suggestions come from a build.', parent=self)
            return
        if self.bm['biomes'] and not messagebox.askyesno('Suggest biomes', 'Replace your biomes and painting with suggested ones?', parent=self):
            return
        self.history.append(copy.deepcopy(self.app.P.get('biome_map')))
        self.bm = bmk.suggest(self.S, self.app.P, self.build_dir)
        self.changed(rebuild=True, snap=False)
        self.status('Suggested %d biomes.' % len(self.bm['biomes']))

    def add(self):
        self.bm['biomes'].insert(0, bmk.biome_entry({'id': bmk.new_id(self.bm), 'name': 'New biome %d' % (len(self.bm['biomes']) + 1)}))
        self.changed(rebuild=True)

    def remove(self, i):
        b = self.bm['biomes'].pop(i)
        self.bm['strokes'] = [s for s in self.bm['strokes'] if s[0] != b['id']]
        self.changed(rebuild=True)

    def move(self, i, d):
        j = i + d
        bl = self.bm['biomes']
        if 0 <= j < len(bl):
            bl[i], bl[j] = bl[j], bl[i]
            self.changed(rebuild=True)

    def where_opts(self):
        keys = getattr(self.S, 'BIO_WHERE', tuple(k for k, v in bmk.WHERE))
        return [(k, v) for k, v in bmk.WHERE if k in keys]

    def feature_labels(self):
        return ['All placed features'] + [f[0] for f in (self.layers or {}).get('features', [])]

    def rebuild_cards(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        self.cards = []
        cols = bmk.colours(self.bm['biomes'])
        wo = self.where_opts()
        for i, (b, col) in enumerate(zip(self.bm['biomes'], cols)):
            self.card(i, b, col, wo)
        self.update_paint_list()
        self.update_legend()

    def entry(self, parent, b, key, width=7):
        v = tk.StringVar(value='' if b[key] is None else '%g' % b[key])
        en = ttk.Entry(parent, textvariable=v, width=width, justify='right')

        def commit(_e=None):
            new = bmk.num_or_none(v.get())
            if key == 'value':
                new = 1.0 if new is None else new
            if new != b[key]:
                b[key] = new
                self.changed()
            v.set('' if b[key] is None else '%g' % b[key])
        en.bind('<Return>', commit)
        en.bind('<FocusOut>', commit)
        return en

    def card(self, i, b, col, wo):
        ui = self.ui
        c = ttk.Frame(self.cards_frame, style='Card.TFrame', padding=8)
        c.pack(fill='x', pady=4, padx=(8, 0))
        sw = tk.Label(c, bg=ui.hexcol(col), width=3, relief='solid', bd=1, cursor='hand2')
        sw.grid(row=0, column=0, sticky='w', padx=(0, 6))
        sw.bind('<Button-1>', lambda e: self.pick(b, col))
        v_name = tk.StringVar(value=b['name'])
        en = ttk.Entry(c, textvariable=v_name, width=26)
        en.grid(row=0, column=1, columnspan=3, sticky='w')

        def commit_name(_e=None):
            n = ' '.join(v_name.get().split()) or b['name']
            if n != b['name']:
                b['name'] = n
                self.changed()
            v_name.set(b['name'])
        en.bind('<Return>', commit_name)
        en.bind('<FocusOut>', commit_name)
        ttk.Label(c, text='Science', style='CardDim.TLabel').grid(row=0, column=4, sticky='e', padx=(10, 4))
        self.entry(c, b, 'value', 5).grid(row=0, column=5, sticky='w')
        bar = ttk.Frame(c, style='Card.TFrame')
        bar.grid(row=0, column=6, sticky='e', padx=(10, 0))
        ttk.Button(bar, text='▲', width=3, style='Small.TButton', command=lambda: self.move(i, -1)).pack(side='left')
        ttk.Button(bar, text='▼', width=3, style='Small.TButton', command=lambda: self.move(i, 1)).pack(side='left', padx=2)
        ttk.Button(bar, text='✕', width=3, style='Small.TButton', command=lambda: self.remove(i)).pack(side='left')
        area = ttk.Label(c, text='', style='CardDim.TLabel')
        area.grid(row=0, column=7, sticky='w', padx=(8, 0))
        ttk.Label(c, text='Where', style='CardDim.TLabel').grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 0))
        v_where = tk.StringVar(value=dict(bmk.WHERE)[b['where']])
        cb = ttk.Combobox(c, textvariable=v_where, values=[t for k, t in wo], width=20, state='readonly')
        cb.grid(row=1, column=2, columnspan=3, sticky='w', pady=(6, 0))
        extra = ttk.Frame(c, style='Card.TFrame')
        extra.grid(row=1, column=5, columnspan=3, sticky='w', pady=(6, 0), padx=(6, 0))

        def show_extra():
            for w in extra.winfo_children():
                w.destroy()
            if b['where'] == 'features':
                fl = self.feature_labels()
                v_f = tk.StringVar(value=fl[b['feature'] + 1] if 0 <= b['feature'] + 1 < len(fl) else fl[0])
                fc = ttk.Combobox(extra, textvariable=v_f, values=fl, width=28, state='readonly')
                fc.pack(side='left')

                def pick_f(_e=None):
                    b['feature'] = fl.index(v_f.get()) - 1
                    self.changed()
                fc.bind('<<ComboboxSelected>>', pick_f)
            elif b['where'] == 'craters':
                ttk.Label(extra, text='at least', style='CardDim.TLabel').pack(side='left', padx=(0, 4))
                self.entry(extra, b, 'crater_km', 6).pack(side='left')
                ttk.Label(extra, text='km across', style='CardDim.TLabel').pack(side='left', padx=(4, 0))

        def pick_where(_e=None):
            b['where'] = next(k for k, t in wo if t == v_where.get())
            show_extra()
            self.changed()
        cb.bind('<<ComboboxSelected>>', pick_where)
        show_extra()
        for row, (lab, k0, k1, unit) in enumerate((('Height', 'hmin', 'hmax', 'm'), ('Slope', 'slopemin', 'slopemax', '°'),
                                                    ('Latitude', 'latmin', 'latmax', '°')), start=2):
            ttk.Label(c, text=lab, style='CardDim.TLabel').grid(row=row, column=0, columnspan=2, sticky='w', pady=(4, 0))
            ttk.Label(c, text='from', style='CardDim.TLabel').grid(row=row, column=2, sticky='e', pady=(4, 0), padx=(0, 4))
            self.entry(c, b, k0).grid(row=row, column=3, sticky='w', pady=(4, 0))
            ttk.Label(c, text='to', style='CardDim.TLabel').grid(row=row, column=4, sticky='e', pady=(4, 0), padx=(0, 4))
            self.entry(c, b, k1).grid(row=row, column=5, sticky='w', pady=(4, 0))
            ttk.Label(c, text=unit, style='CardDim.TLabel').grid(row=row, column=6, sticky='w', pady=(4, 0), padx=(4, 0))
        v_both = tk.BooleanVar(value=b['both'])

        def flip_both():
            b['both'] = bool(v_both.get())
            self.changed()
        ttk.Checkbutton(c, text='N and S', variable=v_both, command=flip_both, style='Card.TCheckbutton').grid(
            row=4, column=7, sticky='w', pady=(4, 0), padx=(4, 0))
        self.cards.append((b['id'], area))

    def pick(self, b, col):
        c = self.ui.pick_colour(self.app, list(col))
        if c:
            b['color'] = [int(x) for x in c][:3]
            self.changed(rebuild=True)

    def update_paint_list(self):
        names = [b['name'] for b in self.bm['biomes']]
        self.paint_cb.configure(values=names)
        if self.v_paint.get() not in names:
            self.v_paint.set(names[0] if names else '')

    def update_legend(self):
        for w in self.legend.winfo_children():
            w.destroy()
        bl = self.bm['biomes']
        if self.idx is None or self.idx.shape[0] != bmk.W_MAP // 2:
            return
        fr, none = bmk.areas(self.idx, len(bl), self.G)
        cols = bmk.colours(bl)
        for (bid, lab), f in zip(self.cards, fr):
            try:
                lab.configure(text='%.1f %%' % (100 * f))
            except tk.TclError:
                pass
        r = None
        for i, (b, c, f) in enumerate(zip(bl, cols, fr)):
            if i % 4 == 0:
                r = ttk.Frame(self.legend)
                r.pack(fill='x')
            tk.Label(r, bg=self.ui.hexcol(c), width=2, relief='solid', bd=1).pack(side='left', padx=(0, 4), pady=2)
            ttk.Label(r, text='%s  %.1f %%' % (b['name'], 100 * f), width=28).pack(side='left')
        if none > 0.0005 and bl:
            ttk.Label(self.legend, text='%.1f %% of the planet fits no biome; it goes to the last one (%s).' % (100 * none, bl[-1]['name']),
                      style='Dim.TLabel').pack(anchor='w', pady=(2, 0))

    def show(self):
        self.canvas.delete('all')
        cw, ch = max(10, self.canvas.winfo_width()), max(10, self.canvas.winfo_height())
        s = min((cw - 16) / 2.0, ch - 16)
        w, h = max(2, int(s * 2)), max(1, int(s))
        self.img_box = ((cw - w) // 2, (ch - h) // 2, w, h)
        if self.base is None:
            return
        img = self.base.astype(np.float32)
        if self.v_relief.get() and self.relief is not None and self.relief.shape == img.shape[:2]:
            sh = self.relief[..., None]
            img = img * (0.5 + sh) + (sh - 0.5) * 90.0
        if self.idx is not None and self.idx.shape == self.base.shape[:2] and self.bm['biomes']:
            bc = bmk.image(self.idx, self.bm['biomes'], fill_last=False).astype(np.float32)
            a = float(self.v_alpha.get())
            img = img * (1 - a) + bc * a
            if self.v_borders.get():
                k = self.idx
                edge = np.zeros(k.shape, bool)
                edge[:, :-1] |= k[:, :-1] != k[:, 1:]
                edge[:-1] |= k[:-1] != k[1:]
                img[edge] = 255
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(im)
        self.canvas.create_image(self.img_box[0], self.img_box[1], image=self.tkimg, anchor='nw')

    def at(self, e):
        if not self.img_box:
            return None
        x0, y0, w, h = self.img_box
        if not (x0 <= e.x < x0 + w and y0 <= e.y < y0 + h):
            return None
        return 90.0 - (e.y - y0) / h * 180.0, (e.x - x0) / w * 360.0

    def brush_mark(self, e=None):
        self.canvas.delete('brush')
        if e is None or self.v_tool.get() == 'look' or not self.img_box:
            return
        ll = self.at(e)
        if ll is None:
            return
        R = float(self.layers['R']) / 1000.0 if self.layers else 1000.0
        x0, y0, w, h = self.img_box
        a = np.degrees(float(self.v_brush.get()) / R)
        ry = a / 180.0 * h
        rx = min(w / 2.0, a / 360.0 * w / max(np.cos(np.radians(ll[0])), 0.02))
        self.canvas.create_oval(e.x - rx, e.y - ry, e.x + rx, e.y + ry, outline='#ffffff', width=1, tags='brush')

    def hover(self, e):
        self.brush_mark(e)
        ll = self.at(e)
        if ll is None or self.layers is None:
            self.readout.configure(text='')
            return
        la, lo = ll
        H = bmk.W_MAP // 2
        r, c = min(H - 1, int((90.0 - la) / 180.0 * H)), min(bmk.W_MAP - 1, int(lo / 360.0 * bmk.W_MAP))
        name = ''
        if self.idx is not None and self.bm['biomes']:
            k = int(self.idx[r, c])
            name = self.bm['biomes'][k]['name'] if k >= 0 else 'no biome'
        self.readout.configure(text='%.1f° %s, %.1f° E   height %.0f m   slope %.0f°   %s' % (
            abs(la), 'N' if la >= 0 else 'S', lo, self.layers['h'][r, c], self.layers['slope'][r, c], name))

    def tool_changed(self):
        self.canvas.configure(cursor='crosshair' if self.v_tool.get() == 'look' else 'pencil')
        if self.v_tool.get() == 'look':
            self.brush_mark()

    def press(self, e):
        ll = self.at(e)
        if ll is None:
            return
        if self.v_tool.get() == 'look':
            H = bmk.W_MAP // 2
            if self.idx is not None and self.bm['biomes']:
                k = int(self.idx[min(H - 1, int((90.0 - ll[0]) / 180.0 * H)), min(bmk.W_MAP - 1, int(ll[1] / 360.0 * bmk.W_MAP))])
                if k >= 0:
                    self.v_paint.set(self.bm['biomes'][k]['name'])
                    self.status('%s: selected for painting.' % self.bm['biomes'][k]['name'])
            return
        self.history.append(copy.deepcopy(self.app.P.get('biome_map')))
        self.last_stroke = None
        self.stroke(ll)

    def drag(self, e):
        if self.v_tool.get() == 'look':
            return
        ll = self.at(e)
        if ll is not None:
            self.stroke(ll)
        self.brush_mark(e)

    def stroke(self, ll):
        r = float(self.v_brush.get())
        if self.last_stroke is not None:
            R = float(self.layers['R']) / 1000.0 if self.layers else 1000.0
            la0, lo0 = np.radians(self.last_stroke)
            la1, lo1 = np.radians(ll)
            d = R * np.arccos(np.clip(np.sin(la0) * np.sin(la1) + np.cos(la0) * np.cos(la1) * np.cos(lo1 - lo0), -1, 1))
            if d < r * 0.4:
                return
        if self.v_tool.get() == 'erase':
            bid = 0
        else:
            bid = next((b['id'] for b in self.bm['biomes'] if b['name'] == self.v_paint.get()), None)
            if bid is None:
                self.status('Pick the biome to paint with first.')
                return
        self.bm['strokes'].append([bid, round(ll[0], 3), round(ll[1] % 360.0, 3), round(r, 2)])
        self.last_stroke = ll
        self.store(snap=False)
        if bid and self.idx is not None and self.G is not None and self.layers is not None:
            pos = next((i for i, b in enumerate(self.bm['biomes']) if b['id'] == bid), -1)
            m = bmk.caps(self.G, [ll], [r * 1000.0 / float(self.layers['R'])])
            self.idx = self.idx.copy()
            self.idx[m] = pos
            self.show()
            self.brush_mark()
        self.schedule(120)

    def clear_paint(self):
        if self.bm['strokes']:
            self.bm['strokes'] = []
            self.changed()

    def save_png(self):
        if self.idx is None:
            return
        p = filedialog.asksaveasfilename(parent=self, title='Save biome map', initialfile=self.name + '_biomes.dds',
                                         defaultextension='.dds', filetypes=[('DDS with an 8-bit palette', '*.dds'), ('PNG image', '*.png')])
        if p:
            img = bmk.image(self.idx, self.bm['biomes'])
            if p.lower().endswith('.dds'):
                kopmod.save_palette_dds(img, p)
            else:
                Image.fromarray(img).save(p)
            self.status('Saved %s' % p)

    def copy_cfg(self):
        self.clipboard_clear()
        self.clipboard_append(bmk.biomes_cfg(self.app.P))
        self.status('Biomes node copied')

    def close(self):
        self.destroy()
