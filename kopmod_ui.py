import os, copy, json, queue, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import kopmod


class ConfigTab:
    BODY = (('gravity', 'Surface gravity', 'g   0 = like Kerbin for its size'), ('rotation', 'Day length', 'hours'),
            ('initial_rotation', 'Starting rotation', '°'), ('albedo', 'Albedo', ''))
    ORBIT = (('sma', 'Semi-major axis', 'km'), ('ecc', 'Eccentricity', ''), ('inc', 'Inclination', '°'),
             ('lan', 'Ascending node', '°'), ('argpe', 'Argument of periapsis', '°'), ('mean_anomaly', 'Mean anomaly at epoch', 'rad'))
    ATMO = (('pressure', 'Pressure at the surface', 'kPa'), ('temperature', 'Temperature there', 'K'),
            ('atmo_height', 'Atmosphere height', 'km'), ('molar_mass', 'Molar mass', 'kg/mol'), ('adiabatic', 'Adiabatic index', ''))

    def __init__(self, app, ui, S, title='Config', kind='body'):
        self.app, self.ui, self.S, self.kind = app, ui, S, kind
        self.vars, self.checks, self.entries = {}, {}, {}
        self.mute = 0
        self.commits = []
        self.bodies = (None, {})
        self.after_id = None
        self.texts, self.tree, self.defs = {}, None, {}
        self.opt_key, self.opt_rows = None, {}
        labels = getattr(S, 'KOP_LABELS', {})
        lab = lambda k, d: labels.get(k, d)
        sf = ui.ScrollFrame(app.nb)
        app.nb.add(sf, text=title)
        p = sf.inner
        ttk.Label(p, text='Everything KSP needs for this %s. Fill in what you would write into a config; mass, '
                          'orbit, atmosphere curves, time warp, biomes and paths are worked out for you. Export to mod '
                          'writes it all into your mod: textures in Textures, the config in Configs%s.' % (
                              kind, ', Scatterer files in Scatterer' if getattr(S, 'KOP_ATMO', True) else ''),
                  style='Dim.TLabel', wraplength=540, justify='left').pack(anchor='w', pady=(8, 0))
        app.section(p, 'Body')
        g = self.grid(p)
        ttk.Label(g, text='Display name').grid(row=0, column=0, sticky='w', padx=8, pady=3)
        self.v_disp = tk.StringVar()
        en = ttk.Entry(g, textvariable=self.v_disp, width=30)
        en.grid(row=0, column=1, columnspan=2, sticky='w', pady=3)
        en.bind('<Return>', self.commit_text)
        en.bind('<FocusOut>', self.commit_text)
        self.v_disp.trace_add('write', self.live_text)
        ttk.Label(g, text='Description').grid(row=1, column=0, sticky='nw', padx=8, pady=3)
        self.desc = tk.Text(g, height=5, width=46, wrap='word', bg=ui.FIELD, fg=ui.FG, insertbackground=ui.FG, relief='flat',
                            font=(ui.FONT, 9), padx=6, pady=4)
        self.desc.grid(row=1, column=1, columnspan=2, sticky='we', pady=3)
        self.desc.bind('<FocusOut>', self.commit_text)
        self.desc.bind('<KeyRelease>', self.live_text)
        g = self.grid(p)
        self.radius_lab = None
        body = list(self.BODY)
        if getattr(S, 'KOP_RADIUS', False):
            body.insert(0, ('radius', 'Radius', 'km'))
        else:
            ttk.Label(g, text='Radius').grid(row=0, column=0, sticky='w', padx=8, pady=3)
            self.radius_lab = ttk.Label(g, text='')
            self.radius_lab.grid(row=0, column=1, columnspan=2, sticky='w', pady=3)
        for i, (k, l, unit) in enumerate(body):
            self.num(g, 1 + i, k, lab(k, l), unit)
        self.check(p, 'tidally_locked', 'Tidally locked (always shows the same side to what it orbits)')
        self.info_body = self.info(p)
        app.section(p, 'Orbit')
        g = self.grid(p)
        ttk.Label(g, text='Orbits around').grid(row=0, column=0, sticky='w', padx=8, pady=3)
        self.v_parent = tk.StringVar()
        self.parent_cb = ttk.Combobox(g, textvariable=self.v_parent, width=24)
        self.parent_cb.grid(row=0, column=1, columnspan=2, sticky='w', pady=3)
        for ev in ('<<ComboboxSelected>>', '<Return>', '<FocusOut>'):
            self.parent_cb.bind(ev, self.commit_text)
        self.v_parent.trace_add('write', self.live_text)
        ttk.Label(g, text='referenceBody: pick a body from your mod or type a name', style='Dim.TLabel').grid(
            row=1, column=1, columnspan=2, sticky='w')
        g = self.grid(p)
        for i, (k, l, unit) in enumerate(self.ORBIT):
            self.num(g, i, k, lab(k, l), unit)
        self.info_orbit = self.info(p)
        self.info_atmo = None
        if getattr(S, 'KOP_ATMO', True):
            app.section(p, 'Atmosphere (Kopernicus)')
            ttk.Label(p, text='The air you can fly in. How it looks from space (Scatterer) is on the Atmosphere tab.',
                      style='Dim.TLabel', wraplength=540).pack(anchor='w', padx=8)
            self.check(p, 'atmo', 'The %s has an atmosphere you can fly in' % kind)
            g = self.grid(p)
            for i, (k, l, unit) in enumerate(self.ATMO):
                self.num(g, i, k, lab(k, l), unit)
            self.info_atmo = self.info(p)
        for title, key, text, fields in getattr(S, 'KOP_SECTIONS', ()):
            app.section(p, title)
            self.check(p, key, text)
            g = self.grid(p)
            for i, (k, l, unit) in enumerate(fields):
                self.num(g, i, k, l, unit)
        self.info_pqs = None
        if getattr(S, 'KOP_GROUND', True):
            app.section(p, 'Ground')
            g = self.grid(p)
            ttk.Label(g, text='Close-up ground textures').grid(row=0, column=0, sticky='w', padx=8, pady=3)
            self.v_ground = tk.StringVar()
            cb = ttk.Combobox(g, textvariable=self.v_ground, values=list(kopmod.GROUND), width=22, state='readonly')
            cb.grid(row=0, column=1, sticky='w', pady=3)
            cb.bind('<<ComboboxSelected>>', self.commit_text)
            self.info_pqs = self.info(p)
        else:
            self.v_ground = tk.StringVar(value='Moho rock')
        app.section(p, 'Biomes')
        self.check(p, 'biomes', getattr(S, 'KOP_BIOMES_LABEL', 'Make a biome map from the build\'s heights'))
        self.info_biomes = self.info(p)
        app.section(p, 'Kopernicus options')
        ttk.Label(p, text='Every line of the config, plus the other options from the Kopernicus wiki. Untick a line to '
                          'leave it out, or type a value to use instead of the worked-out one. The extra options are off '
                          'until you tick them.', style='Dim.TLabel', wraplength=540, justify='left').pack(anchor='w', padx=8)
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        self.opts_btn = ttk.Button(r, text='Show the options ▸', command=self.toggle_opts)
        self.opts_btn.pack(side='left', padx=8)
        ttk.Button(r, text='Reset all options', command=self.reset_opts).pack(side='left')
        self.opts_count = ttk.Label(r, text='', style='Dim.TLabel')
        self.opts_count.pack(side='left', padx=10)
        hold = ttk.Frame(p)
        hold.pack(fill='x')
        self.opts_frame = ttk.Frame(hold)
        app.section(p, 'Mod folder')
        r = ttk.Frame(p)
        r.pack(fill='x')
        self.v_mod = tk.StringVar()
        en = ttk.Entry(r, textvariable=self.v_mod, width=52)
        en.pack(side='left', padx=(8, 6))
        en.bind('<Return>', self.commit_text)
        en.bind('<FocusOut>', self.commit_text)
        self.v_mod.trace_add('write', self.live_text)
        ttk.Button(r, text='Browse…', command=self.browse).pack(side='left')
        self.info_mod = self.info(p)
        r = ttk.Frame(p)
        r.pack(fill='x', pady=(6, 0))
        self.export_btn = ttk.Button(r, text='Export to mod…', style='Accent.TButton', command=self.export)
        self.export_btn.pack(side='left', padx=8)
        self.info_build = ttk.Label(r, text='', style='Dim.TLabel', wraplength=380, justify='left')
        self.info_build.pack(side='left', padx=6)
        app.section(p, 'What gets written')
        r = ttk.Frame(p)
        r.pack(fill='x')
        self.v_show = tk.StringVar()
        self.show_cb = ttk.Combobox(r, textvariable=self.v_show, width=32, state='readonly')
        self.show_cb.pack(side='left', padx=(8, 6))
        self.show_cb.bind('<<ComboboxSelected>>', lambda e: self.preview())
        ttk.Button(r, text='Copy', command=self.copy).pack(side='left')
        self.out = tk.Text(p, height=20, width=70, wrap='none', bg=ui.FIELD, fg=ui.FG, relief='flat', font=(ui.MONO, 9), padx=6, pady=4)
        self.out.pack(fill='x', padx=8, pady=(6, 12))
        self.page = sf
        app.nb.bind('<<NotebookTabChanged>>', self.tab_changed, add='+')

    def grid(self, p):
        g = ttk.Frame(p)
        g.pack(fill='x')
        g.columnconfigure(0, minsize=190)
        return g

    def info(self, p):
        lab = ttk.Label(p, text='', style='Dim.TLabel', wraplength=540, justify='left')
        lab.pack(anchor='w', padx=8, pady=(2, 0))
        return lab

    @staticmethod
    def fmt(v):
        return '%.10g' % v

    def planet(self):
        P = self.app.P
        P['planet'] = kopmod.planet_entry(P.get('planet'), kopmod.planet_base(self.S))
        return P['planet']

    def num(self, g, row, key, label, unit):
        ttk.Label(g, text=label).grid(row=row, column=0, sticky='w', padx=8, pady=3)
        v = tk.StringVar()
        en = ttk.Entry(g, textvariable=v, width=16, justify='right')
        en.grid(row=row, column=1, sticky='w', pady=3)
        note = ttk.Label(g, text=unit, style='Dim.TLabel')
        note.grid(row=row, column=2, sticky='w', padx=(6, 0))

        def commit(_e=None, key=key, v=v, live=False):
            if self.mute or str(en.cget('state')) == 'disabled':
                return
            e = self.planet()
            if v.get().strip() == self.fmt(e[key]):
                return
            try:
                x = float(v.get().replace(',', '.'))
            except ValueError:
                if not live:
                    v.set(self.fmt(e[key]))
                return
            if live and x == e[key]:
                return
            e[key] = x
            self.app.P['planet'] = kopmod.planet_entry(e, kopmod.planet_base(self.S))
            if not live:
                v.set(self.fmt(self.app.P['planet'][key]))
            self.changed()
        en.bind('<Return>', commit)
        en.bind('<FocusOut>', commit)
        v.trace_add('write', lambda *_a, c=commit: c(live=True))
        self.commits.append(commit)
        self.vars[key] = v
        self.entries[key] = (en, note, unit)

    def check(self, p, key, label):
        v = tk.BooleanVar()

        def flip(key=key, v=v):
            self.planet()[key] = bool(v.get())
            self.changed()
        ttk.Checkbutton(p, text=label, variable=v, command=flip).pack(anchor='w', padx=8, pady=(4, 0))
        self.checks[key] = v

    def tab_changed(self, _e=None):
        try:
            if self.app.nb.select() == str(self.page):
                self.sync()
        except tk.TclError:
            pass

    def show_locked(self, shown, locked, set_all):
        e = self.planet()
        self.mute += 1
        try:
            for k, (en, note, unit) in self.entries.items():
                en.configure(state='normal')
                if k in locked or set_all:
                    self.vars[k].set(self.fmt(shown[k] if k in locked else e[k]))
                en.configure(state='disabled' if k in locked else 'normal')
                note.configure(text=(unit.split('   ')[0] + '  (%s)' % locked[k]) if k in locked else unit)
        finally:
            self.mute -= 1

    def sync(self):
        self.show_locked(kopmod.entry(self.S, self.app.P), self.S.kop_locked(self.app.P), False)
        self.schedule()

    def refresh(self):
        e = self.planet()
        if not e['mod']:
            e['mod'] = self.S.game_mod_dir()
        self.show_locked(kopmod.entry(self.S, self.app.P), self.S.kop_locked(self.app.P), True)
        self.mute += 1
        try:
            for k, v in self.checks.items():
                v.set(bool(e[k]))
            self.v_disp.set(e['display_name'] or self.app.P['name'])
            self.desc.delete('1.0', 'end')
            self.desc.insert('1.0', e['description'])
            self.v_parent.set(e['parent'])
            self.v_ground.set(e['ground'])
            self.v_mod.set(e['mod'])
        finally:
            self.mute -= 1
        self.schedule()

    def live_text(self, *_a):
        if not self.mute:
            self.commit_text()

    def commit_all(self):
        for c in self.commits:
            c()
        self.commit_text()
        for path, row in self.opt_rows.items():
            if row[1] is not None:
                self.opt_commit(path)

    def commit_text(self, _e=None):
        if self.mute:
            return
        e = self.planet()
        new = {'display_name': self.v_disp.get().strip(), 'description': ' '.join(self.desc.get('1.0', 'end').split()),
               'parent': self.v_parent.get().strip() or 'Sun', 'mod': self.v_mod.get().strip(), 'ground': self.v_ground.get()}
        if new['display_name'] == self.app.P['name']:
            new['display_name'] = ''
        if any(e.get(k) != v for k, v in new.items()):
            e.update(new)
            self.changed()

    def changed(self):
        self.app.dirty = True
        self.app.update_title()
        self.schedule()

    def schedule(self):
        if self.after_id:
            self.app.after_cancel(self.after_id)
        self.after_id = self.app.after(250, self.update)

    def mod_bodies(self, mod):
        if self.bodies[0] != mod:
            self.bodies = (mod, kopmod.mod_bodies(mod) if mod and os.path.isdir(mod) else {})
            self.parent_cb.configure(values=sorted(self.bodies[1], key=str.lower) or ['Sun'])
        return self.bodies[1]

    def update(self):
        self.after_id = None
        P = self.app.P
        e = self.planet()
        mod = e['mod']
        ok = bool(mod) and os.path.isdir(mod)
        bodies = self.mod_bodies(mod) if ok else {}
        if self.radius_lab is not None:
            self.radius_lab.configure(text='%s km  (set on the %s tab)' % ('{:,.3g}'.format(float(P['radius']) / 1000.0),
                                                                           'Planet' if self.kind == 'planet' else 'Body'))
        mpath = mod if ok else os.path.join(self.S.TOOL, 'GameData', 'MyMod')
        try:
            self.texts, self.tree, self.defs, n, build = kopmod.preview_texts(self.S, P, mpath, bodies)
        except Exception as ex:
            self.texts, self.tree, self.defs = {'Error': str(ex)}, None, {}
            n, build = None, None
        if n:
            shown = kopmod.entry(self.S, P)
            dn = (shown['display_name'] or '').strip()
            self.info_body.configure(text='Mass %.4g kg (%.3g × %s), density %.0f kg/m³%s' % (
                n['mass'], n['mass_ref'], n['ref'], n['density'],
                ('\nOther configs (referenceBody, Scatterer) must use the name %s, not the display name %s.' % (P['name'], dn))
                if dn and dn != P['name'] else ''))
            if n['period']:
                d = n['period'] / 21600.0
                self.info_orbit.configure(text='%.4g Gm from %s · one orbit takes %.1f Kerbin days (%.2f years) · sphere of influence '
                                               '%s km (Kopernicus works it out itself) · star: %s' % (
                    shown['sma'] / 1e6, shown['parent'], d, n['period'] / 31557600.0, '{:,.0f}'.format(n['soi'] / 1000),
                    kopmod.star_of(shown['parent'], bodies)))
            elif ok:
                real = [nm for nm, (_, b) in bodies.items() if any(
                    str(kopmod.cfg_get(pr, 'displayName', '')).split('^')[0].strip() == shown['parent']
                    for pr in kopmod.cfg_walk(b, 'Properties'))]
                if real:
                    self.info_orbit.configure(text='%s is only the display name of %s. referenceBody needs the name, so pick %s '
                                                   '- with a name KSP cannot find, Kopernicus fails and the game loads the stock '
                                                   'system instead.' % (shown['parent'], real[0], real[0]))
                else:
                    self.info_orbit.configure(text='%s was not found in the mod, so the orbital period cannot be worked out. If no '
                                                   'body has this name, Kopernicus fails and the game loads the stock system '
                                                   'instead.' % shown['parent'])
            else:
                self.info_orbit.configure(text='Pick the mod folder to see the orbital period.')
            if self.info_atmo is not None:
                if shown['atmo']:
                    self.info_atmo.configure(text='Pressure falls by e every %.1f km (a real gas at this temperature would take %.1f km) '
                                                  '· time warp above %s m · high flying from %s m' % (
                        n['scale_height'] / 1000, n['real_scale_height'] / 1000, '{:,}'.format(n['warp'][1]), '{:,}'.format(n['fly'])))
                else:
                    self.info_atmo.configure(text='No atmosphere you can fly in. Time warp above %s m.' % '{:,}'.format(n['warp'][1]))
            if self.info_pqs is not None:
                q = n['pqs']
                self.info_pqs.configure(text='Close-up terrain fades in below %s km and is off above %s km; seen from space from %s km. '
                                             'Time warp from %s m.' % ('{:,.1f}'.format(q['pqs_start'] / 1000), '{:,.1f}'.format(q['deactivate'] / 1000),
                                                                        '{:,.1f}'.format(q['sv_end'] / 1000), '{:,}'.format(n['warp'][1])))
        self.info_biomes.configure(text=', '.join(b[1] for b in self.S.kop_biomes(P, None, False)[0]) if e['biomes'] else 'No biomes.')
        self.info_build.configure(text=('Uses the build in out/%s.' % os.path.basename(build)) if build else 'No build yet: press Build first.')
        if not ok:
            self.info_mod.configure(text='Pick your mod\'s folder inside GameData (for example GameData/MyPlanets).')
        elif not kopmod.gamedata_rel(mod):
            self.info_mod.configure(text='This folder is not inside GameData, so the paths in the configs may be wrong.')
        else:
            self.info_mod.configure(text='%d bodies found in %s. Textures go to %s.' % (
                len(bodies), kopmod.mod_name_of(mod), os.path.relpath(kopmod.mod_tex_dir(mod), mod).replace('\\', '/')))
        nch = len(e.get('opts', {}))
        self.opts_count.configure(text='%d option%s changed' % (nch, '' if nch == 1 else 's') if nch else 'all options as worked out')
        if self.opts_frame.winfo_ismapped() and self.tree:
            self.build_opts()
        names = list(self.texts)
        self.show_cb.configure(values=names)
        if self.v_show.get() not in names:
            self.v_show.set(names[0])
        self.preview()

    def preview(self):
        self.out.configure(state='normal')
        self.out.delete('1.0', 'end')
        self.out.insert('1.0', self.texts.get(self.v_show.get(), ''))
        self.out.configure(state='disabled')

    def copy(self):
        self.app.clipboard_clear()
        self.app.clipboard_append(self.texts.get(self.v_show.get(), ''))
        self.app.status('%s copied' % self.v_show.get())

    def browse(self):
        start = self.planet()['mod'] or self.S.game_mod_dir() or kopmod.find_gamedata(self.S.TOOL)
        d = filedialog.askdirectory(parent=self.app, title='Your mod\'s folder inside GameData', initialdir=start if os.path.isdir(start) else self.S.TOOL)
        if d:
            self.v_mod.set(os.path.normpath(d))
            self.commit_text()

    def toggle_opts(self):
        if self.opts_frame.winfo_ismapped():
            self.ui.hide(self.opts_frame)
            self.opts_btn.configure(text='Show the options ▸')
        else:
            self.opts_frame.pack(fill='x', padx=8, pady=(6, 0))
            self.opts_btn.configure(text='Hide the options ▾')
            if self.tree:
                self.build_opts()

    def reset_opts(self):
        if self.planet().get('opts'):
            self.planet()['opts'] = {}
            self.opt_key = None
            self.changed()

    def build_opts(self):
        auto = kopmod.kop_paths(self.tree)
        extra = [x for x in kopmod.KOP_EXTRA if x[0] in self.defs]
        key = tuple(p for p, _, _ in auto) + tuple(p for p, _, _ in extra)
        opts = self.planet().setdefault('opts', {})
        if key != self.opt_key:
            self.opt_key = key
            for w in self.opts_frame.winfo_children():
                w.destroy()
            self.opt_rows = {}
            g = self.opts_frame
            g.columnconfigure(2, weight=1)
            group = lambda path: path.rsplit('/', 1)[0] if '/' in path else 'Body'
            rows = [(path, k, True, v is None, '') for path, k, v in auto] + \
                   [(path, path.rsplit('/', 1)[-1], False, False, h) for path, d, h in extra]
            order = []
            for row in rows:
                if group(row[0]) not in order:
                    order.append(group(row[0]))
            r = 0
            for grp in order:
                ttk.Label(g, text=grp.replace('/', ' / '), style='Head.TLabel').grid(row=r, column=0, columnspan=3, sticky='w', pady=(10, 2))
                r += 1
                for path, k, is_auto, block, help in [x for x in rows if group(x[0]) == grp]:
                    self.opt_row(g, r, path, k, is_auto, block, help)
                    r += 1
        put = lambda var, x: var.get() == x or var.set(x)
        self.mute += 1
        try:
            for path, (on_v, val_v, info, is_auto, block) in self.opt_rows.items():
                st = opts.get(path)
                put(on_v, bool(st[0]) if st else is_auto)
                if is_auto:
                    v = next((x[2] for x in auto if x[0] == path), None)
                    if val_v is not None and val_v.get().strip() != (st[1] if st and st[1] else ''):
                        val_v.set(st[1] if st and st[1] else '')
                    shown = 'block' if v is None else 'worked out: ' + (v if len(v) <= 34 else v[:32] + '…')
                    help = kopmod.KOP_HELP.get(path, '')
                    info.configure(text=shown + ('  ·  ' + help if help else ''))
                elif val_v is not None and val_v.get().strip() != (st[1] if st and st[1] else self.defs.get(path, '')):
                    val_v.set(st[1] if st and st[1] else self.defs.get(path, ''))
        finally:
            self.mute -= 1

    def opt_row(self, g, r, path, k, is_auto, block, help):
        on_v = tk.BooleanVar()
        ttk.Checkbutton(g, text=k, variable=on_v, command=lambda: self.opt_commit(path)).grid(row=r, column=0, sticky='w', pady=1)
        val_v = None
        if not block:
            val_v = tk.StringVar()
            en = ttk.Entry(g, textvariable=val_v, width=18)
            en.grid(row=r, column=1, sticky='w', padx=(6, 6), pady=1)
            en.bind('<Return>', lambda e: self.opt_commit(path))
            en.bind('<FocusOut>', lambda e: self.opt_commit(path))
            val_v.trace_add('write', lambda *_a: self.opt_commit(path))
        info = ttk.Label(g, text=help, style='Dim.TLabel', wraplength=250, justify='left')
        info.grid(row=r, column=2, sticky='w', pady=1)
        self.opt_rows[path] = (on_v, val_v, info, is_auto, block)

    def opt_commit(self, path):
        if self.mute:
            return
        on_v, val_v, info, is_auto, block = self.opt_rows[path]
        opts = self.planet().setdefault('opts', {})
        val = val_v.get().strip() if val_v is not None else ''
        if not is_auto and val == self.defs.get(path, ''):
            val = ''
        on = bool(on_v.get())
        new = None if (on == is_auto and not val) else [on, val]
        if opts.get(path) != new:
            if new is None:
                opts.pop(path, None)
            else:
                opts[path] = new
            self.changed()

    def build_stale(self, build):
        norm = getattr(self.S, 'kop_normalize', self.S.normalize)
        try:
            with open(os.path.join(build, self.app.P['name'] + '_preset.json')) as fh:
                built = norm(json.load(fh))
            now = norm(copy.deepcopy(self.app.P))
        except Exception:
            return False
        skip = ('atmosphere', 'aurora', 'clouds', 'planet', 'biome_map')
        return json.dumps({k: v for k, v in built.items() if k not in skip}, sort_keys=True, default=str) != \
            json.dumps({k: v for k, v in now.items() if k not in skip}, sort_keys=True, default=str)

    def export(self):
        self.commit_all()
        P = copy.deepcopy(self.app.P)
        mod = self.planet()['mod']
        if not mod or not os.path.isdir(mod):
            messagebox.showinfo('Mod folder', 'Pick your mod\'s folder inside GameData first.', parent=self.app)
            return
        build = self.S.kop_build(P)
        if not build:
            messagebox.showinfo('Build first', 'Press Build first - the maps come from a build.', parent=self.app)
            return
        self.app.status('Looking through the mod folder…')
        self.app.update_idletasks()
        P['planet'] = kopmod.entry(self.S, P)
        bodies = kopmod.mod_bodies(mod)
        plan = kopmod.mod_plan(P['name'], P['planet']['parent'], mod, bodies)
        files = kopmod.export_files(self.S, P, mod, build, plan)
        lines = ['%-8s %s  (%s)' % (how, os.path.relpath(path, mod), what) for path, what, how in files]
        if len(lines) > 24:
            lines = lines[:22] + ['... and %d more' % (len(lines) - 22)]
        msg = 'Export %s from the build in out/%s into %s?\n\n%s' % (P['name'], os.path.basename(build), mod, '\n'.join(lines))
        if self.build_stale(build):
            msg += '\n\nThe settings changed after this build, so the maps show the build, not the new settings.'
        if any(how != 'new' for _, _, how in files):
            msg += '\n\nFiles that are already there are backed up first.'
        if not messagebox.askyesno('Export to mod', msg, parent=self.app):
            self.app.status('Export cancelled')
            return
        self.app.save(quiet=True)
        self.export_btn.configure(state='disabled')
        q = queue.Queue()
        P = copy.deepcopy(self.app.P)

        def job():
            try:
                q.put(('done', kopmod.export_mod(self.S, P, mod, build, os.path.join(self.S.TOOL, 'backups'), log=lambda s: q.put(('log', s)))))
            except Exception as ex:
                q.put(('err', str(ex)))

        def poll():
            try:
                while True:
                    kind, data = q.get_nowait()
                    if kind == 'log':
                        self.app.log(data)
                        self.app.status(data if len(data) < 110 else '…' + data[-108:])
                        continue
                    self.export_btn.configure(state='normal')
                    self.bodies = (None, {})
                    if kind == 'err':
                        self.app.status('Export to mod failed: ' + data)
                        messagebox.showerror('Export to mod', data, parent=self.app)
                    else:
                        written, bdir = data
                        self.app.status('Exported %s into %s (%d files)' % (P['name'], kopmod.mod_name_of(mod), len(written)))
                        messagebox.showinfo('Export to mod', 'Wrote %d files into %s.%s' % (
                            len(written), mod, '\n\nThe old files are in:\n' + bdir if bdir else ''), parent=self.app)
                        self.schedule()
                    return
            except queue.Empty:
                pass
            self.app.after(100, poll)
        threading.Thread(target=job, daemon=True).start()
        self.app.status('Exporting to %s…' % kopmod.mod_name_of(mod))
        poll()
