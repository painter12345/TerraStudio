import sys, os, io, json, copy, time, math, struct, argparse, heapq
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None

APP_NAME = 'Terra Studio'
APP_VERSION = '0.1.5'
FROZEN = bool(getattr(sys, 'frozen', False))
TOOL = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
ROOT = os.path.abspath(os.path.join(TOOL, '..', '..'))
PD = os.path.join(ROOT, 'GameData', 'ActualFirstSystem', 'Textures', 'PluginData')
PRESETS = os.path.join(TOOL, 'presets')
OUTROOT = os.path.join(TOOL, 'out')
SETTINGS_FILE = os.path.join(TOOL, 'studio_settings.json')
COMMANDS = ('make', 'export', 'new')
THREADS = max(1, min(8, os.cpu_count() or 1))


def read_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def texture_dir():
    d = read_settings().get('texture_dir')
    if d and os.path.isdir(d):
        return d
    return PD if os.path.isdir(PD) else ''


def mod_root(d):
    d = os.path.abspath(d)
    parts = d.split(os.sep)
    low = [p.lower() for p in parts]
    if 'gamedata' in low:
        i = len(low) - 1 - low[::-1].index('gamedata')
        if i + 1 < len(parts):
            return os.sep.join(parts[:i + 2])
    return ''


def game_mod_dir():
    d = texture_dir()
    return mod_root(d) if d else ''


def backup_dir(body, stamp):
    return os.path.join(TOOL, 'backups', body, stamp)


def nice(p):
    try:
        return os.path.relpath(p, ROOT) if os.path.abspath(p).startswith(ROOT) else p
    except ValueError:
        return p


def gamedata_rel(d):
    d = os.path.abspath(d)
    parts = d.split(os.sep)
    low = [p.lower() for p in parts]
    if 'gamedata' in low:
        i = len(low) - 1 - low[::-1].index('gamedata')
        rest = parts[i + 1:]
        if rest:
            return '/'.join(rest)
    return ''


DEFAULTS = {
    'name': 'NewWorld',
    'seed': 1,
    'radius': 600000,
    'shape': {'ocean': True, 'land': 0.35, 'continents': 5, 'warp': 0.5, 'coast': 0.5, 'islands': 0.3,
              'size_var': 0.3, 'bias': 0.0},
    'relief': {'high': 6000.0, 'low': -4000.0, 'mountains': 0.6, 'mountain_size': 1.0, 'mountain_area': 0.5,
               'ranges': 0.5, 'hills': 0.4, 'hill_size': 1.0, 'plains': 0.3, 'roughness': 0.3, 'shelf': 0.2,
               'sharpness': 1.0, 'canyons': 0.0, 'canyon_depth': 2500.0, 'canyon_width': 60.0},
    'volcanoes': {'count': 0, 'seed': 1, 'size_km': 300.0, 'height': 8000.0, 'caldera': 0.5, 'size_var': 0.5},
    'features': [],
    'plateaus': {'amount': 0.0, 'height': 1500.0, 'size': 1.0, 'edge': 0.35, 'flat': 0.8},
    'water': {'rivers': 0.0, 'width': 4.0, 'depth': 80.0, 'valleys': 0.5, 'valley_width': 8.0},
    'cracks': {'amount': 0.0, 'style': 'lines', 'count': 8, 'curvy': 0.3, 'width': 6.0, 'depth': 300.0,
               'ridges': 0.5, 'cell_size': 250.0, 'seed': 1},
    'craters': {'count': 0, 'seed': 1, 'min_km': 4.0, 'max_km': 120.0, 'size_mix': 1.8, 'depth': 1.0,
                'fresh': 0.4, 'ejecta': 0.5, 'rays': 0.5},
    'colors': {
        'stops': [[-4000.0, [40, 50, 58]], [-200.0, [86, 92, 84]], [0.0, [84, 106, 58]], [600.0, [82, 104, 56]],
                  [1700.0, [116, 114, 74]], [2900.0, [124, 110, 90]], [4300.0, [112, 106, 102]]],
        'jitter': 250.0,
        'patches': 0.4, 'patch_size': 1.0, 'patch_color': [150, 132, 92],
        'rock': [106, 100, 94], 'rock_slope': [16.0, 32.0], 'rock_amount': 1.0,
        'ice': [236, 240, 246], 'cap_north': 72.0, 'cap_south': 72.0, 'cap_ragged': 0.5, 'sea_ice': 1.0,
        'snow_line': 5400.0, 'snow_slope': 28.0,
        'shallow': [52, 118, 138], 'deep': [16, 36, 72], 'water_depth': 600.0,
        'dry': {'amount': 0.0, 'lat': 25.0, 'width': 12.0, 'color': [178, 152, 104]},
        'cold': {'amount': 0.0, 'lat': 55.0, 'color': [116, 116, 96]},
        'crater_floor': [70, 70, 72], 'crater_floor_amount': 0.0, 'ejecta_color': None,
        'volcano_color': [64, 56, 52], 'volcano_amount': 0.5,
        'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0,
        'river_color': None, 'river_amount': 1.0, 'crack_color': [120, 76, 56], 'crack_amount': 0.7,
    },
    'normal_strength': 2.0,
    'files': {'height': '', 'color': '', 'normal': ''},
    'preview': {'tilt': 0, 'view_lat': 15, 'view_lon': 0},
}

HEIGHT_KEYS = ('seed', 'radius', 'shape', 'relief', 'craters', 'volcanoes', 'features', 'plateaus', 'water', 'cracks')
CRACK_STYLES = ('lines', 'cells')
FEATURE_TYPES = ('crater', 'basin', 'volcano', 'mountain', 'plateau')
FEATURE = {'type': 'crater', 'lat': 0.0, 'lon': 180.0, 'size': 120.0, 'height': 0.0, 'fresh': 1.0}


def feature_entry(f):
    e = dict(FEATURE)
    if isinstance(f, dict):
        e.update({k: v for k, v in f.items() if k in FEATURE})
    e['type'] = str(e['type']).lower() if str(e['type']).lower() in FEATURE_TYPES else 'crater'
    for k in ('lat', 'lon', 'size', 'height', 'fresh'):
        try:
            e[k] = float(e[k])
        except (TypeError, ValueError):
            e[k] = float(FEATURE[k])
    e['lat'] = max(-90.0, min(90.0, e['lat']))
    e['lon'] = e['lon'] % 360.0
    e['size'] = max(1.0, e['size'])
    e['fresh'] = max(0.0, min(1.0, e['fresh']))
    return e


def merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalize(P):
    rc = P.get('colors', {}) if isinstance(P.get('colors'), dict) else {}
    old_cap = rc.get('cap_lat')
    P = merge(DEFAULTS, P)
    C = P['colors']
    if old_cap is not None:
        if 'cap_north' not in rc:
            C['cap_north'] = float(old_cap)
        if 'cap_south' not in rc:
            C['cap_south'] = float(old_cap)
    C.pop('cap_lat', None)
    if C.get('ejecta_color') is not None:
        try:
            C['ejecta_color'] = [int(max(0, min(255, round(float(v))))) for v in C['ejecta_color']][:3]
        except (TypeError, ValueError):
            C['ejecta_color'] = None
    P['features'] = [feature_entry(f) for f in (P.get('features') or [])]
    v = P['volcanoes']
    v['count'] = int(max(0, v['count']))
    P['plateaus'].pop('steps', None)
    ck = P['cracks']
    ck['count'] = int(max(1, min(16, ck['count'])))
    ck['style'] = ck['style'] if ck.get('style') in CRACK_STYLES else 'lines'
    if C.get('river_color') is not None:
        try:
            C['river_color'] = [int(max(0, min(255, round(float(v))))) for v in C['river_color']][:3]
        except (TypeError, ValueError):
            C['river_color'] = None
    st = []
    for s in C.get('stops', []):
        try:
            st.append([float(s[0]), [int(max(0, min(255, round(float(c))))) for c in s[1]][:3]])
        except (TypeError, ValueError, IndexError):
            pass
    if not st:
        st = copy.deepcopy(DEFAULTS['colors']['stops'])
    st.sort(key=lambda s: s[0])
    C['stops'] = st
    rs = sorted(float(v) for v in C['rock_slope'][:2])
    C['rock_slope'] = [rs[0], max(rs[1], rs[0] + 0.5)]
    cr = P['craters']
    lo, hi = sorted([max(0.05, float(cr['min_km'])), max(0.05, float(cr['max_km']))])
    cr['min_km'], cr['max_km'] = lo, max(hi, lo * 1.01)
    cr['count'] = int(max(0, cr['count']))
    P['shape']['continents'] = int(max(0, P['shape']['continents']))
    P['shape']['ocean'] = bool(P['shape']['ocean'])
    P['radius'] = float(max(1000.0, P['radius']))
    P['seed'] = int(P['seed'])
    R = P['relief']
    R['high'] = float(max(1.0, R['high']))
    R['low'] = float(min(-1.0, R['low']))
    n = P['name']
    fl = P['files']
    for k, suf in (('height', '_height.dds'), ('color', '_color.dds'), ('normal', '_normal.dds')):
        if not fl.get(k):
            fl[k] = n + suf
    P['atmosphere'] = atmo_entry(P.get('atmosphere'))
    return P


def height_key(P):
    return json.dumps({k: P[k] for k in HEIGHT_KEYS}, sort_keys=True)


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


U = np.uint32
GX = np.array([1, -1, 1, -1, 1, -1, 1, -1, 0, 0, 0, 0, 1, -1, 0, 0], np.float32)
GY = np.array([1, 1, -1, -1, 0, 0, 0, 0, 1, -1, 1, -1, 1, 1, -1, -1], np.float32)
GZ = np.array([0, 0, 0, 0, 1, 1, -1, -1, 1, 1, -1, -1, 0, 0, 1, -1], np.float32)
OFF = np.random.default_rng(12345).uniform(-500, 500, (32, 3)).astype(np.float32)


def perlin(x, y, z, seed):
    xf = np.floor(x); yf = np.floor(y); zf = np.floor(z)
    fx = x - xf; fy = y - yf; fz = z - zf
    xi = xf.astype(np.int32).view(U); yi = yf.astype(np.int32).view(U); zi = zf.astype(np.int32).view(U)
    sd = U((seed * 0x27D4EB2F + 0x165667B1) & 0xFFFFFFFF)
    hx0 = xi * U(0x9E3779B1); hx1 = hx0 + U(0x9E3779B1)
    hy0 = yi * U(0x85EBCA77); hy1 = hy0 + U(0x85EBCA77)
    hz0 = (zi * U(0xC2B2AE3D)) ^ sd; hz1 = ((zi + U(1)) * U(0xC2B2AE3D)) ^ sd
    u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    w = fz * fz * fz * (fz * (fz * 6 - 15) + 10)
    ax = fx - 1; ay = fy - 1; az = fz - 1

    def g(hx, hy, hz, px, py, pz):
        h = hx ^ hy ^ hz
        h *= U(0x2C1B3C6D); h ^= h >> U(13); h *= U(0x297A2D39)
        h >>= U(28)
        return GX[h] * px + GY[h] * py + GZ[h] * pz
    a = g(hx0, hy0, hz0, fx, fy, fz)
    a += u * (g(hx1, hy0, hz0, ax, fy, fz) - a)
    b = g(hx0, hy1, hz0, fx, ay, fz)
    b += u * (g(hx1, hy1, hz0, ax, ay, fz) - b)
    c = g(hx0, hy0, hz1, fx, fy, az)
    c += u * (g(hx1, hy0, hz1, ax, fy, az) - c)
    d = g(hx0, hy1, hz1, fx, ay, az)
    d += u * (g(hx1, hy1, hz1, ax, ay, az) - d)
    a += v * (b - a)
    c += v * (d - c)
    a += w * (c - a)
    return a


def octaves(f0, fmax, omax=12):
    out = []
    f = float(f0)
    for i in range(omax):
        w = min(1.0, max(0.0, math.log2(fmax / f) + 1)) if fmax > 0 else 0.0
        if w <= 0:
            break
        out.append((i, f, w))
        f *= 2
    return out


def fbm(X, Y, Z, f0, fmax, seed, gain=0.5, omax=12):
    s = np.zeros(X.shape, np.float32)
    a = 1.0
    for i, f, w in octaves(f0, fmax, omax):
        o = OFF[(seed * 7 + i) % 32]
        s += np.float32(a * w) * perlin(X * np.float32(f) + o[0], Y * np.float32(f) + o[1], Z * np.float32(f) + o[2], seed * 131 + i)
        a *= gain
    return s * np.float32((1 - gain) * 2.2)


def ridged(X, Y, Z, f0, fmax, seed, gain=0.5, omax=12):
    s = np.zeros(X.shape, np.float32)
    wt = np.ones(X.shape, np.float32)
    a = 1.0
    for i, f, w in octaves(f0, fmax, omax):
        o = OFF[(seed * 5 + i) % 32]
        n = perlin(X * np.float32(f) + o[0], Y * np.float32(f) + o[1], Z * np.float32(f) + o[2], seed * 173 + i)
        n = np.clip(1 - np.sqrt(n * n + np.float32(0.004)) * 1.4, 0, 1)
        n *= n
        n *= wt
        wt = np.clip(n * 2.2, 0, 1)
        s += np.float32(a * w) * n
        a *= gain
    return s * np.float32(1 - gain)


def fib_sphere(n):
    i = np.arange(n, dtype=np.float64) + 0.5
    z = 1 - 2 * i / n
    r = np.sqrt(1 - z * z)
    t = i * math.pi * (3 - math.sqrt(5))
    return (r * np.cos(t)).astype(np.float32), (r * np.sin(t)).astype(np.float32), z.astype(np.float32)


def row_lat(H, r0, r1):
    return ((0.5 - (np.arange(r0, r1, dtype=np.float64) + 0.5) / H) * math.pi)


def rows_xyz(W, H, r0, r1):
    lat = row_lat(H, r0, r1)
    lon = (np.arange(W, dtype=np.float64) + 0.5) / W * 2 * math.pi
    cl = np.cos(lat)[:, None]
    X = (cl * np.cos(lon)[None]).astype(np.float32)
    Y = (cl * np.sin(lon)[None]).astype(np.float32)
    Z = np.repeat(np.sin(lat)[:, None], W, 1).astype(np.float32)
    return X, Y, Z


def fmax_for(W):
    return W / 16.0


class Cancelled(Exception):
    pass


LOW_W = 512
_LOW = {}


def masked(fn, m, X, Y, Z):
    if m is True or m.all():
        return fn(X, Y, Z)
    out = np.zeros(X.shape, np.float32)
    idx = np.flatnonzero(m)
    if idx.size:
        out.reshape(-1)[idx] = fn(X.reshape(-1)[idx], Y.reshape(-1)[idx], Z.reshape(-1)[idx])
    return out


def cr_weights(t):
    t2 = t * t; t3 = t2 * t
    return [(-t3 + 2 * t2 - t) * 0.5, (3 * t3 - 5 * t2 + 2) * 0.5, (-3 * t3 + 4 * t2 + t) * 0.5, (t3 - t2) * 0.5]


def cubic_rows(G, W, H, r0, r1):
    Hc, Wc = G.shape[-2:]
    fy = (np.arange(r0, r1, dtype=np.float64) + 0.5) / H * Hc - 0.5
    fx = (np.arange(W, dtype=np.float64) + 0.5) / W * Wc - 0.5
    y0 = np.floor(fy).astype(np.int64); ty = (fy - y0).astype(np.float32)
    x0 = np.floor(fx).astype(np.int64); tx = (fx - x0).astype(np.float32)
    wy = cr_weights(ty); wx = cr_weights(tx)
    ys = [np.clip(y0 + i - 1, 0, Hc - 1) for i in range(4)]
    xs = [(x0 + i - 1) % Wc for i in range(4)]
    out = []
    for g in G:
        acc = np.zeros((r1 - r0, W), np.float32)
        for j in range(4):
            gy = g[ys[j]]
            row = np.zeros((r1 - r0, W), np.float32)
            for i in range(4):
                row += gy[:, xs[i]] * wx[i][None, :]
            acc += row * wy[j][:, None]
        out.append(acc)
    return out


class Terrain:
    def __init__(self, P):
        self.P = P
        self.seed = int(P['seed'])
        sh = P['shape']
        n = int(sh['continents'])
        land = min(max(float(sh['land']), 0.02), 0.98)
        rp = np.random.default_rng([self.seed, 101])
        rs = np.random.default_rng([self.seed, 202])
        pts, sizes = [], []
        bias = min(max(float(sh['bias']), -1.0), 1.0)
        for k in range(n):
            cand = rp.normal(size=(24, 3))
            cand /= np.linalg.norm(cand, axis=1, keepdims=True)
            if bias > 0:
                cand[:, 2] *= 1 - 0.85 * bias
                cand /= np.linalg.norm(cand, axis=1, keepdims=True)
            elif bias < 0:
                z = cand[:, 2]
                cand[:, 2] = np.sign(z) * np.abs(z) ** (1.0 / (1 + 2.5 * -bias))
                cand[:, :2] *= (np.sqrt(np.clip(1 - cand[:, 2] ** 2, 0, 1)) / np.maximum(np.linalg.norm(cand[:, :2], axis=1), 1e-9))[:, None]
            if pts:
                d = cand @ np.array(pts).T
                best = int(np.argmin(d.max(1)))
            else:
                best = 0
            pts.append(cand[best])
            sizes.append(rs.random())
        self.cpts = np.array(pts, np.float32).reshape(-1, 3)
        th = math.acos(max(-1.0, 1 - 2 * land / max(n, 1))) * 1.1 if n else 0.5
        sv = min(max(float(sh['size_var']), 0.0), 0.9)
        f = np.array([1 + (2 * u - 1) * sv for u in sizes], np.float64) if sizes else np.zeros(0)
        self.cth = (f * th).astype(np.float32)
        pl = P['plateaus']
        self.lkey = json.dumps([self.seed, n, round(land, 4), float(sh['warp']), round(sv, 4), float(sh['bias']),
                                float(P['relief']['canyons']) > 0, float(pl['amount']) > 0, round(float(pl['size']), 4)])
        self.thr, self.sd = 0.0, 1.0
        self.calibrate()

    def warped(self, X, Y, Z):
        k = float(self.P['shape']['warp']) * 0.42
        if k <= 0:
            return X, Y, Z
        n = max(1, int(math.ceil(k / 0.3 - 1e-9)))
        st = np.float32(k / n)
        Xw, Yw, Zw = X, Y, Z
        for _ in range(n):
            wx = fbm(Xw, Yw, Zw, 1.0, 3.0, self.seed + 1, 0.45, 2)
            wy = fbm(Xw, Yw, Zw, 1.0, 3.0, self.seed + 2, 0.45, 2)
            wz = fbm(Xw, Yw, Zw, 1.0, 3.0, self.seed + 3, 0.45, 2)
            Xw = Xw + st * wx; Yw = Yw + st * wy; Zw = Zw + st * wz
            nr = np.sqrt(Xw * Xw + Yw * Yw + Zw * Zw) + np.float32(1e-6)
            Xw = Xw / nr; Yw = Yw / nr; Zw = Zw / nr
        return Xw, Yw, Zw

    def low(self, X, Y, Z):
        Xw, Yw, Zw = self.warped(X, Y, Z)
        if len(self.cpts):
            B = np.zeros(X.shape, np.float32)
            for c, th in zip(self.cpts, self.cth):
                d = np.clip(Xw * c[0] + Yw * c[1] + Zw * c[2], -1, 1)
                B = -smin(-B, -np.exp(-(np.arccos(d) / th) ** 2), np.float32(0.12))
        else:
            B = fbm(Xw, Yw, Zw, 0.9, 6.0, self.seed + 5, 0.5, 3) * np.float32(2.5)
        reg = fbm(Xw, Yw, Zw, 1.4, 6.0, self.seed + 21, 0.5, 3)
        pm = fbm(Xw, Yw, Zw, 1.8, 8.0, self.seed + 41, 0.5, 3)
        spn = fbm(Xw, Yw, Zw, 1.0, 3.0, self.seed + 25, 0.4, 2)
        if float(self.P['relief']['canyons']) > 0:
            cd = canyon_distance(X, Y, Z, self.seed)
            creg = fbm(X, Y, Z, 0.9, 4.0, self.seed + 29, 0.5, 2)
        else:
            cd = np.ones(X.shape, np.float32); creg = np.zeros(X.shape, np.float32)
        PL = self.P['plateaus']
        if float(PL['amount']) > 0:
            sz = max(float(PL['size']), 0.2)
            pf = fbm(Xw, Yw, Zw, 0.9 / sz, 3.6 / sz, self.seed + 71, 0.5, 3)
        else:
            pf = np.zeros(X.shape, np.float32)
        return [B, reg, pm, spn, cd, creg, pf]

    def low_grid(self):
        g = _LOW.get(self.lkey)
        if g is None:
            if len(_LOW) > 6:
                _LOW.clear()
            X, Y, Z = rows_xyz(LOW_W, LOW_W // 2, 0, LOW_W // 2)
            g = _LOW[self.lkey] = np.stack(self.low(X, Y, Z))
        return g

    def low_rows(self, W, H, r0, r1):
        out = cubic_rows(self.low_grid(), W, H, r0, r1)
        lat = np.abs(row_lat(H, r0, r1))
        polar = np.flatnonzero(lat > math.radians(86.0))
        if polar.size:
            X, Y, Z = rows_xyz(W, H, r0, r1)
            d = self.low(X[polar], Y[polar], Z[polar])
            for o, v in zip(out, d):
                o[polar] = v
        return out

    def cont(self, X, Y, Z, fmax, lowf):
        sh = self.P['shape']
        B = lowf[0].copy()
        bias = float(sh['bias'])
        if bias:
            B += np.float32(bias * 0.45) * (1 - 2 * Z * Z)
        co = float(sh['coast'])
        B += fbm(X, Y, Z, 2.4, fmax, self.seed + 7, 0.42 + 0.2 * co, 9) * np.float32(0.12 + 0.5 * co)
        isl = float(sh['islands'])
        if isl > 0:
            n = fbm(X, Y, Z, 6.0, fmax, self.seed + 9, 0.5, 6)
            B += np.float32(isl * 1.1) * smooth_relu(n - np.float32(0.08), np.float32(0.04))
        return B

    def calibrate(self):
        X, Y, Z = fib_sphere(12000)
        fm = 48.0
        lowf = self.low(X, Y, Z)
        c = self.cont(X, Y, Z, fm, lowf)
        land = min(max(float(self.P['shape']['land']), 0.0), 1.0)
        self.thr = float(np.quantile(c, 1 - land)) if 0 < land < 1 else (float(c.min()) - 1 if land >= 1 else float(c.max()) + 1)
        self.sd = float(max(c.std(), 1e-4))
        h, _ = self.raw(X, Y, Z, fm, lowf)
        pos = h[h > 0]; neg = h[h < 0]
        R = self.P['relief']
        qh = float(np.quantile(pos, 0.998)) if pos.size > 30 else 0.3
        ql = float(np.quantile(neg, 0.005)) if neg.size > 30 else -0.5
        self.kh = float(R['high']) / max(qh, 1e-4)
        self.kl = float(-R['low']) / max(-ql, 1e-4)

    def raw(self, X, Y, Z, fmax, lowf):
        P = self.P
        sh, R = P['shape'], P['relief']
        sd = self.seed
        B, reg, pm, spn = lowf[:4]
        c = self.cont(X, Y, Z, fmax, lowf)
        s = (c - np.float32(self.thr)) / np.float32(self.sd)
        sl = (B - np.float32(self.thr)) / np.float32(self.sd)
        ocean = sh['ocean']
        ms = max(float(R['mountain_size']), 0.1)
        hs = max(float(R['hill_size']), 0.1)
        mtn = float(R['mountains'])
        mount = 0
        if mtn > 0:
            ar = float(R['mountain_area'])
            t = 0.22 * (1 - 2 * min(1.0, ar * 1.3))
            mreg = ss(t - 0.25, t + 0.25, reg)
            wdt = np.float32((0.1 + 0.18 * ar) * ms)
            belt = 1 - ss(0, wdt, np.abs(spn))
            rc = float(R['ranges'])
            band = np.exp(-((sl - np.float32(0.8)) / np.float32(0.5 * ms)) ** 2) * ss(0, 0.3, s)
            mask = np.maximum(belt * mreg * np.float32(1 - 0.5 * rc), band * np.float32(rc))
            need = mask > 0.002
            if ocean:
                need &= s > 0
            M = masked(lambda x, y, z: ridged(x, y, z, 8.0 / ms, fmax, sd + 23, 0.55), need, X, Y, Z)
            sp = float(R['sharpness'])
            if abs(sp - 1) > 1e-6:
                M = M ** np.float32(sp) * np.float32(0.45 ** (1 - sp))
            mount = np.float32(mtn * 0.9) * mask * (np.float32(0.12) + M)
        hl = float(R['hills'])
        hills = 0
        if hl > 0:
            hills = np.float32(hl * 0.3) * (np.float32(0.5) + np.float32(0.5) * np.tanh(fbm(X, Y, Z, 5.0 / hs, fmax, sd + 31, 0.5, 9) * np.float32(2.2)))
        pl = float(R['plains'])
        rel = 1
        if pl > 0:
            tp = 0.24 * (1 - 2 * pl)
            rel = 1 - np.float32(0.92) * ss(tp - 0.2, tp + 0.2, pm) * np.float32(min(1.0, pl * 4))
        rg = float(R['roughness'])
        rough = 0
        if rg > 0:
            rough = np.float32(rg * 0.07) * (np.float32(0.5) + np.float32(0.5) * np.tanh(fbm(X, Y, Z, 20.0, fmax, sd + 51, 0.55, 6) * np.float32(2.2)))
        up = None
        PL = P['plateaus']
        pa = float(PL['amount'])
        if pa > 0:
            sz = max(float(PL['size']), 0.2)
            jag = fbm(X, Y, Z, 4.0 / sz, fmax, sd + 73, 0.5, 5)
            v = lowf[6] + np.float32(0.09) * jag
            t0 = np.float32(0.4 - 0.5 * min(pa, 1.0))
            e = np.float32(0.012 + 0.08 * (1 - min(max(float(PL['edge']), 0.0), 1.0)))
            up = ss(t0 - e, t0 + e * np.float32(0.6), v)
            top = ss(t0, t0 + 3 * e, v) * np.float32(min(max(float(PL['flat']), 0.0), 1.0))
            rel = rel * (1 - np.float32(0.9) * top)
            rough = rough * (1 - np.float32(0.5) * top) if rg > 0 else rough
            if ocean:
                up = up * ss(0, 0.5, s)
        relief = rel * (mount + hills)
        if ocean:
            fade = ss(0, 0.4, s)
            hland = np.float32(0.02) * np.clip(s / np.float32(0.3), 0, 1) + np.float32(0.06) * ss(0, 2.5, s) + fade * (relief + rough)
            d = -s
            dl = np.maximum(-sl, d * np.float32(0.25))
            sw = 0.1 + 1.0 * float(R['shelf'])
            fo = ss(0, 0.4, d)
            hsea = -(np.float32(0.04) * ss(0, 0.3, d) + np.float32(0.96) * ss(sw, sw + 1.2, dl))
            deep = ss(sw + 0.3, sw + 1.6, dl)
            rid = masked(lambda x, y, z: ridged(x, y, z, 1.6, fmax, sd + 61, 0.5, 7), deep > 0, X, Y, Z)
            hsea = hsea + np.float32(0.3) * rid * deep + fo * np.float32(0.25) * hills - fo * rough
            hsea = np.minimum(hsea, -np.float32(0.012) * fo)
            h = np.where(s >= 0, hland, hsea)
        else:
            base = np.where(s >= 0, np.float32(0.08) * ss(0, 2.5, s), -np.float32(0.5) * ss(0, 1.8, -s))
            h = base + relief + rough
        return np.asarray(h, np.float32), up

    def metres(self, X, Y, Z, fmax, lowf):
        h, up = self.raw(X, Y, Z, fmax, lowf)
        h = np.where(h >= 0, h * np.float32(self.kh), h * np.float32(self.kl)).astype(np.float32)
        if up is not None:
            h = h + np.float32(self.P['plateaus']['height']) * up
        R = self.P['relief']
        ca = float(R['canyons'])
        if ca > 0 and float(R['canyon_depth']) > 0:
            cd, creg = lowf[4], lowf[5]
            hw0 = max(float(R['canyon_width']), 1.0) * 500.0 / float(self.P['radius'])
            t = 0.45 - 0.6 * min(ca, 1.0)
            reg = ss(t - 0.1, t + 0.1, creg)
            hw = np.float32(hw0) * (np.float32(0.55) + np.float32(0.9) * ss(t, t + 0.35, creg))
            near = (np.abs(cd) < hw * np.float32(1.5)) & (reg > 0.002)
            jag = masked(lambda x, y, z: fbm(x, y, z, min(1.5 / hw0, fmax), fmax, self.seed + 33, 0.5, 4), near, X, Y, Z)
            d = np.abs(cd) + hw * np.float32(0.2) * jag
            prof = 1 - ss(hw * np.float32(0.45), hw, d)
            h = h - np.float32(R['canyon_depth']) * prof * reg
        return h


def canyon_distance(X, Y, Z, seed):
    def f(x, y, z):
        return fbm(x, y, z, 0.7, 1.6, seed + 27, 0.35, 2)
    c = f(X, Y, Z)
    ax = np.where(np.abs(Z) < 0.9, np.float32(0), np.float32(1))
    az = 1 - ax
    t1x = Y * az - Z * 0; t1y = Z * ax - X * az; t1z = X * 0 - Y * ax
    n1 = np.sqrt(t1x * t1x + t1y * t1y + t1z * t1z) + np.float32(1e-9)
    t1x /= n1; t1y /= n1; t1z /= n1
    t2x = Y * t1z - Z * t1y; t2y = Z * t1x - X * t1z; t2z = X * t1y - Y * t1x
    e = np.float32(0.004)
    g1 = (f(X + e * t1x, Y + e * t1y, Z + e * t1z) - c) / e
    g2 = (f(X + e * t2x, Y + e * t2y, Z + e * t2z) - c) / e
    g = np.sqrt(g1 * g1 + g2 * g2)
    return (c / np.maximum(g, np.float32(0.05))).astype(np.float32)


def smooth_relu(x, k):
    return np.float32(0.5) * (x + np.sqrt(x * x + k * k))


def crater_list(P):
    C = P['craters']
    n = int(C['count'])
    if n <= 0:
        return None
    s = int(C['seed'])
    v = np.random.default_rng([s, 1]).normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    u = np.random.default_rng([s, 2]).random(n)
    age = np.random.default_rng([s, 3]).random(n)
    a = max(0.3, float(C['size_mix']))
    lo, hi = float(C['min_km']), float(C['max_km'])
    D = (lo ** -a - u * (lo ** -a - hi ** -a)) ** (-1 / a)
    o = np.argsort(-age, kind='stable')
    return {'v': v[o].astype(np.float32), 'D': D[o], 'age': age[o], 'id': o}


def spot_window(c, ext, W, H, r0, r1, X, Y, Z):
    latc = math.asin(max(-1.0, min(1.0, float(c[2]))))
    lonc = math.atan2(float(c[1]), float(c[0])) % (2 * math.pi)
    pxr = W / (2 * math.pi)
    ra = int(math.floor((0.5 - (latc + ext) / math.pi) * H - 1))
    rb = int(math.ceil((0.5 - (latc - ext) / math.pi) * H + 1))
    ra = max(ra, r0); rb = min(rb, r1)
    if ra >= rb:
        return None
    cols = None
    if not (latc + ext >= math.pi / 2 or latc - ext <= -math.pi / 2):
        ml = max(abs(latc + ext), abs(latc - ext))
        dl = ext / max(math.cos(ml), 1e-3)
        if dl < math.pi:
            c0 = int(math.floor((lonc - dl) * pxr - 1))
            c1 = int(math.ceil((lonc + dl) * pxr + 1))
            if c1 - c0 + 1 < W:
                cols = np.arange(c0, c1 + 1) % W
    rows = slice(ra - r0, rb - r0)
    if cols is None:
        return (rows, slice(None)), X[rows], Y[rows], Z[rows]
    return np.ix_(np.arange(ra - r0, rb - r0), cols), X[rows][:, cols], Y[rows][:, cols], Z[rows][:, cols]


def lonlat_vec(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)], np.float32)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


def crater_shape(r, floor, rimw, rims, k):
    cav = r * r - 1
    rx = np.minimum(r - 1 - rimw, 0)
    rim = rims * rx * rx
    s = -smin(-cav, np.float32(-floor), k)
    return smin(s, rim, k)


def crater_depth_m(Dkm):
    return 1000.0 * min(0.196 * Dkm, 1.04 * Dkm ** 0.3)


def crater_marks(mk, idx, r, sx, sy, sz, c, dot, e_amt, rays, extr, seed, o, floor_w):
    if mk is None:
        return
    if floor_w > 0:
        f = (1 - ss(0.72, 1.0, r)) * np.float32(floor_w)
        mk[1][idx] = np.maximum(mk[1][idx], f.astype(np.float16))
    if e_amt > 0.02:
        tx = sx - c[0] * dot; ty = sy - c[1] * dot; tz = sz - c[2] * dot
        tn = np.sqrt(tx * tx + ty * ty + tz * tz) + np.float32(1e-9)
        tx /= tn; ty /= tn; tz /= tn
        st = np.clip(0.45 + 1.3 * perlin(tx * 5.5 + o[1], ty * 5.5 + o[2], tz * 5.5 + o[0], seed), 0, 1) ** 1.5
        out = np.maximum(r - 1, 0)
        blanket = np.exp(-out * 2.6)
        longr = np.exp(-out * 0.9)
        e = np.where(r < 1, np.float32(0.3) + np.float32(0.25) * r, (1 - rays) * blanket + rays * (0.35 * blanket + st * longr))
        e = e * ss(extr, extr * 0.72, r) * np.float32(e_amt)
        mk[0][idx] = np.maximum(mk[0][idx], e.astype(np.float16))


def one_crater(hm, mk, X, Y, Z, W, H, r0, c, Dk, R, deg, depth, e_amt, rays, nid, k, basin=False, depth_m=None):
    Ra = Dk * 500.0 / R
    if Ra * W / (2 * math.pi) < 0.6:
        return
    extr = 3.3 if e_amt > 0.02 else 1.95
    win = spot_window(c, Ra * extr, W, H, r0, r0 + hm.shape[0], X, Y, Z)
    if win is None:
        return
    idx, sx, sy, sz = win
    dot = np.clip(sx * c[0] + sy * c[1] + sz * c[2], -1, 1)
    r = np.arccos(dot) / np.float32(Ra)
    if not (r < extr).any():
        return
    q = np.float32(1.4 / Ra)
    o = OFF[k % 32]
    r = r * (1 + np.float32(0.07) * perlin(sx * q + o[0], sy * q + o[1], sz * q + o[2], 7001 + nid))
    if basin:
        floor = -0.5 * (1 - 0.3 * deg)
        rims = 0.4 * (1 - 0.5 * deg)
        ks = np.float32(0.35 + 0.5 * deg)
        shp = crater_shape(r, np.float32(floor), np.float32(0.9), np.float32(rims), ks)
    else:
        floor = -(0.95 - 0.4 * float(ss(8, 40, Dk))) * (1 - 0.3 * deg)
        rims = 0.7 * (1 - 0.5 * deg)
        ks = np.float32(0.22 + 0.6 * deg)
        shp = crater_shape(r, np.float32(floor), np.float32(0.7), np.float32(rims), ks)
        if Dk > 20:
            shp = shp + np.float32(0.35 * float(ss(20, 60, Dk)) * (1 - 0.5 * deg)) * np.exp(-(r / np.float32(0.22)) ** 2)
    if depth_m is None:
        dm = depth * crater_depth_m(Dk) * (1 - 0.65 * deg) / 0.95
    else:
        dm = depth_m / max(-floor, 0.05)
    hm[idx] += shp * np.float32(dm)
    crater_marks(mk, idx, r, sx, sy, sz, c, dot, e_amt, rays, extr, 9001 + nid, o, 1.0 if basin else 0.6 + 0.4 * float(ss(10, 80, Dk)))


def apply_craters(P, CR, hm, mk, X, Y, Z, W, H, r0, cancel=None):
    if CR is None:
        return
    C = P['craters']
    R = float(P['radius'])
    fresh = float(C['fresh']); depth = float(C['depth'])
    ejk = float(C['ejecta']); rays = float(C['rays'])
    for k in range(len(CR['D'])):
        if cancel is not None and k % 64 == 0:
            cancel()
        deg = float(ss(fresh - 0.15, fresh + 0.15, CR['age'][k]))
        one_crater(hm, mk, X, Y, Z, W, H, r0, CR['v'][k], float(CR['D'][k]), R, deg, depth, ejk * (1 - deg), rays,
                   int(CR['id'][k]), k)


def volcano_list(P):
    V = P['volcanoes']
    n = int(V['count'])
    if n <= 0:
        return None
    s = int(V['seed'])
    v = np.random.default_rng([s, 11]).normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    u = np.random.default_rng([s, 12]).random(n)
    sv = min(max(float(V['size_var']), 0.0), 0.9)
    f = 1 + (2 * u - 1) * sv
    return {'v': v.astype(np.float32), 'D': float(V['size_km']) * f, 'Hm': float(V['height']) * f}


def one_volcano(hm, mk, X, Y, Z, W, H, r0, c, Dk, Hm, caldera, R, nid):
    Ra = Dk * 500.0 / R
    if Ra * W / (2 * math.pi) < 0.8 or Hm == 0:
        return
    win = spot_window(c, Ra * 1.25, W, H, r0, r0 + hm.shape[0], X, Y, Z)
    if win is None:
        return
    idx, sx, sy, sz = win
    dot = np.clip(sx * c[0] + sy * c[1] + sz * c[2], -1, 1)
    r = np.arccos(dot) / np.float32(Ra)
    q = np.float32(1.6 / Ra)
    o = OFF[nid % 32]
    r = r * (1 + np.float32(0.09) * perlin(sx * q + o[0], sy * q + o[1], sz * q + o[2], 5003 + nid))
    rr = np.clip(r, 0, 1)
    cone = (1 - rr) ** np.float32(1.7)
    rc = 0.1 + 0.06 * caldera
    top = (1 - rc) ** 1.7
    cone = smin(cone, np.float32(top), np.float32(0.04))
    pit = (1 - ss(rc * 0.55, rc * 1.05, r)) * np.float32(0.12 * caldera)
    q2 = np.float32(6.0 / Ra)
    bump = perlin(sx * q2 + o[2], sy * q2 + o[0], sz * q2 + o[1], 5101 + nid) * np.float32(0.05) * (1 - rr)
    shp = cone - pit + bump * ss(1.0, 0.6, r)
    hm[idx] += shp * np.float32(Hm)
    if mk is not None:
        t = ss(1.05, 0.25, r) * np.clip(0.65 + 0.8 * perlin(sx * q2 + o[1], sy * q2 + o[2], sz * q2 + o[0], 5201 + nid), 0, 1)
        mk[2][idx] = np.maximum(mk[2][idx], t.astype(np.float16))


def one_mountain(hm, X, Y, Z, W, H, r0, c, Dk, Hm, R, nid, fmax):
    Ra = Dk * 500.0 / R
    if Ra * W / (2 * math.pi) < 0.8 or Hm == 0:
        return
    win = spot_window(c, Ra * 1.3, W, H, r0, r0 + hm.shape[0], X, Y, Z)
    if win is None:
        return
    idx, sx, sy, sz = win
    dot = np.clip(sx * c[0] + sy * c[1] + sz * c[2], -1, 1)
    r = np.arccos(dot) / np.float32(Ra)
    q = np.float32(1.3 / Ra)
    o = OFF[nid % 32]
    r = r * (1 + np.float32(0.25) * perlin(sx * q + o[0], sy * q + o[1], sz * q + o[2], 6003 + nid))
    rr = np.clip(r, 0, 1)
    env = (1 - rr * rr) ** 2
    M = ridged(sx, sy, sz, min(1.7 / Ra, fmax), fmax, 6101 + nid, 0.5)
    hm[idx] += env * (np.float32(0.55) + np.float32(0.9) * M) * np.float32(Hm / 1.0)


def plateau_levels(P, T):
    out = {}
    R = float(P['radius'])
    n = 160
    k = np.arange(n) + 0.5
    rad = np.sqrt(k / n) * 0.7
    ang = np.pi * (1 + 5 ** 0.5) * k
    for i, f in enumerate(P.get('features') or []):
        if f['type'] != 'plateau':
            continue
        c = lonlat_vec(f['lat'], f['lon'])
        Ra = float(f['size']) * 500.0 / R
        a = np.array([-c[1], c[0], 0.0]) if abs(c[2]) < 0.9 else np.array([0.0, -c[2], c[1]])
        a /= np.linalg.norm(a)
        b = np.cross(c, a)
        t = rad * Ra
        pts = (np.cos(t)[:, None] * c[None, :] + np.sin(t)[:, None] * (np.cos(ang)[:, None] * a[None, :] + np.sin(ang)[:, None] * b[None, :]))
        X, Y, Z = (pts[:, j].astype(np.float32) for j in range(3))
        h = T.metres(X, Y, Z, 48.0, T.low(X, Y, Z))
        out[i] = float(np.median(h))
    return out


def one_plateau(hm, X, Y, Z, W, H, r0, c, Dk, Hm, level, R, nid, fmax):
    Ra = Dk * 500.0 / R
    if Ra * W / (2 * math.pi) < 0.8:
        return
    win = spot_window(c, Ra * 1.5, W, H, r0, r0 + hm.shape[0], X, Y, Z)
    if win is None:
        return
    idx, sx, sy, sz = win
    dot = np.clip(sx * c[0] + sy * c[1] + sz * c[2], -1, 1)
    r = np.arccos(dot) / np.float32(Ra)
    o = OFF[nid % 32]
    q1 = np.float32(1.2 / Ra)
    q2 = np.float32(min(3.0 / Ra, fmax))
    q3 = np.float32(min(8.0 / Ra, fmax))
    jag = np.float32(0.3) * perlin(sx * q1 + o[0], sy * q1 + o[1], sz * q1 + o[2], 6203 + nid)
    jag += np.float32(0.14) * perlin(sx * q2 + o[1], sy * q2 + o[2], sz * q2 + o[0], 6211 + nid)
    jag += np.float32(0.05) * perlin(sx * q3 + o[2], sy * q3 + o[0], sz * q3 + o[1], 6217 + nid)
    r = r * (1 + jag)
    up = ss(1.02, 0.8, r)
    apron = np.float32(0.18) * ss(1.45, 1.0, r) * (1 - up)
    h = hm[idx]
    top = np.float32(level + Hm) + np.float32(0.25) * (h - np.float32(level))
    hm[idx] = h + apron * np.float32(Hm) + up * (top - h)


def apply_volcanoes(P, VL, hm, mk, X, Y, Z, W, H, r0, cancel=None):
    if VL is None:
        return
    R = float(P['radius'])
    cal = float(P['volcanoes']['caldera'])
    for k in range(len(VL['D'])):
        if cancel is not None:
            cancel()
        one_volcano(hm, mk, X, Y, Z, W, H, r0, VL['v'][k], float(VL['D'][k]), float(VL['Hm'][k]), cal, R, k)


def apply_features(P, hm, mk, X, Y, Z, W, H, r0, fmax, cancel=None, levels=None):
    R = float(P['radius'])
    ejk = float(P['craters']['ejecta']); rays = float(P['craters']['rays'])
    for k, f in enumerate(P.get('features') or []):
        if cancel is not None:
            cancel()
        c = lonlat_vec(f['lat'], f['lon'])
        D, Hm, t = float(f['size']), float(f['height']), f['type']
        nid = 300 + k
        if t == 'crater':
            deg = 1 - float(f['fresh'])
            one_crater(hm, mk, X, Y, Z, W, H, r0, c, D, R, deg, 1.0, ejk * (1 - deg), rays, nid, k,
                       depth_m=(Hm if Hm > 0 else None))
        elif t == 'basin':
            deg = 1 - float(f['fresh'])
            one_crater(hm, mk, X, Y, Z, W, H, r0, c, D, R, deg, 1.0, 0.0, rays, nid, k, basin=True,
                       depth_m=(Hm if Hm > 0 else crater_depth_m(D) * 0.6))
        elif t == 'volcano':
            one_volcano(hm, mk, X, Y, Z, W, H, r0, c, D, Hm if Hm else D * 25.0, float(P['volcanoes']['caldera']), R, nid)
        elif t == 'mountain':
            one_mountain(hm, X, Y, Z, W, H, r0, c, D, Hm if Hm else D * 20.0, R, nid, fmax)
        elif t == 'plateau' and levels and k in levels:
            one_plateau(hm, X, Y, Z, W, H, r0, c, D, Hm if Hm else D * 15.0, levels[k], R, nid, fmax)


_NET = {}
NET_W = 512


def river_network(P, cancel=None):
    Wt = P.get('water') or {}
    amt = float(Wt.get('rivers', 0))
    if amt <= 0:
        return None
    Q = copy.deepcopy(P)
    Q['water']['rivers'] = 0.0
    Q['cracks']['amount'] = 0.0
    key = height_key(Q) + json.dumps([round(amt, 4), float(Wt['width']), float(Wt['depth'])])
    got = _NET.get(key)
    if got is not None:
        return got
    hm, _ = make_height(Q, NET_W, cancel=cancel, workers=THREADS)
    net = route_rivers(hm, P)
    if len(_NET) > 4:
        _NET.clear()
    _NET[key] = net
    return net


def route_rivers(hm, P):
    H, W = hm.shape
    Rk = float(P['radius']) / 1000.0
    lat = row_lat(H, 0, H)
    dlat, dlon = math.pi / H, 2 * math.pi / W
    area_row = (Rk * Rk * dlat * dlon * np.cos(lat)).tolist()
    ocean = bool(P['shape']['ocean']) and bool((hm < 0).any())
    seed = (hm < 0) if ocean else (hm <= np.quantile(hm, 0.03))
    allseed = seed.copy()
    for dy in (-1, 0, 1):
        sh = np.roll(seed, dy, 0)
        if dy == -1:
            sh[-1] = True
        elif dy == 1:
            sh[0] = True
        for dx in (-1, 0, 1):
            allseed &= np.roll(sh, dx, 1)
    border = seed & ~allseed
    X, Y, Z = rows_xyz(W, H, 0, H)
    rng_m = float(np.percentile(hm, 99) - np.percentile(hm, 1))
    land = hm > (0 if ocean else np.quantile(hm, 0.03))
    drop = np.maximum(np.abs(np.diff(hm, axis=1, append=hm[:, :1])), np.abs(np.diff(hm, axis=0, append=hm[-1:])))
    md = float(np.median(drop[land])) if land.any() else 10.0
    J = (fbm(X, Y, Z, 9.0, 40.0, int(P['seed']) * 7 + 911, 0.55, 4) + 1) * np.float32(18 + 0.004 * rng_m)
    J += (fbm(X, Y, Z, 40.0, 80.0, int(P['seed']) * 7 + 915, 0.5, 2) + 1) * np.float32(1.5 * md)
    J += np.random.default_rng([int(P['seed']), 913]).random(J.shape).astype(np.float32) * np.float32(0.8 * md + 0.5)
    h = (hm.astype(np.float64) + J).ravel().tolist()
    fill = [0.0] * (H * W)
    lake_t = max(25.0, 4 * md)
    N = H * W
    visited = bytearray(seed.ravel().astype(np.uint8).tobytes())
    rec = [-1] * N
    heap = [(h[i], i) for i in np.flatnonzero(border.ravel()).tolist()]
    heapq.heapify(heap)
    order = []
    eps = 1e-3
    pop, push = heapq.heappop, heapq.heappush
    while heap:
        hc, c = pop(heap)
        r, x = divmod(c, W)
        for rr in (r - 1, r, r + 1):
            if rr < 0 or rr >= H:
                continue
            base = rr * W
            for xx in (x - 1, x, x + 1):
                n = base + (xx % W)
                if visited[n]:
                    continue
                visited[n] = 1
                hn = h[n]
                fh = hn if hn > hc + eps else hc + eps
                fill[n] = fh - hn
                rec[n] = c
                order.append(n)
                push(heap, (fh, n))
    acc = [area_row[i // W] for i in range(N)]
    for c in reversed(order):
        acc[rec[c]] += acc[c]
    land_area = sum(area_row[c // W] for c in order) or 1.0
    amin = land_area * 10 ** (-1.3 - 2.2 * min(max(float(P['water']['rivers']), 0.0), 1.0))
    riv = [c for c in order if acc[c] > amin and fill[c] < lake_t]
    if not riv:
        return None
    is_r = bytearray(N)
    for c in riv:
        is_r[c] = 1
    main = {}
    for c in riv:
        r = rec[c]
        m = main.get(r)
        if m is None or acc[c] > acc[m]:
            main[r] = c
    jit = np.random.default_rng([int(P['seed']), 909]).random((N, 2)) - 0.5

    def pos(c, jitter=True):
        r, x = divmod(c, W)
        la = (0.5 - (r + 0.5) / H) * math.pi
        lo = (x + 0.5) / W * 2 * math.pi
        if jitter:
            la += float(jit[c, 0]) * 0.6 * dlat
            lo += float(jit[c, 1]) * 0.6 * dlon
        cl = math.cos(la)
        return np.array([cl * math.cos(lo), cl * math.sin(lo), math.sin(la)])

    pc = {}

    def P_(c):
        v = pc.get(c)
        if v is None:
            v = pc[c] = pos(c, bool(is_r[c]))
        return v

    def curve(c):
        d = main.get(c)
        nx = rec[c]
        a = (P_(d) + P_(c)) / 2 if d is not None else P_(c)
        b = (P_(c) + P_(nx)) / 2 if is_r[nx] else P_(nx)
        return a, P_(c), b

    width = float(P['water']['width'])
    depth = float(P['water']['depth'])
    groups = []
    ts = np.linspace(0, 1, 5)
    for c in riv:
        a, m, b = curve(c)
        pts = [(1 - t) ** 2 * a + 2 * (1 - t) * t * m + t * t * b for t in ts]
        nx = rec[c]
        if not is_r[nx] and fill[nx] >= lake_t:
            pts = pts[:3]
        if is_r[nx] and main.get(nx) != c:
            a2, m2, b2 = curve(nx)
            pts.append(0.25 * a2 + 0.5 * m2 + 0.25 * b2)
        pts = np.array([q / np.linalg.norm(q) for q in pts], np.float32)
        sc = min(max((acc[c] / amin) ** 0.5, 1.0), 6.0)
        hw = width * 0.5 * sc ** 0.7 / Rk
        cen = pts.mean(0)
        cen /= np.linalg.norm(cen)
        ext = float(np.arccos(np.clip(pts @ cen, -1, 1)).max())
        groups.append({'c': cen.astype(np.float32), 'ext': ext, 'A': pts[:-1], 'B': pts[1:], 'hw': hw,
                       'dep': depth * sc ** 0.5, 'fade': float(ss(1.0, 3.0, acc[c] / amin)) ** 0.7})
    return {'groups': groups, 'amin': amin}


def seg_dist(sx, sy, sz, A, B):
    d = None
    for a, b in zip(A, B):
        ab = b - a
        L = float(ab @ ab)
        px = sx - a[0]; py = sy - a[1]; pz = sz - a[2]
        t = np.clip((px * ab[0] + py * ab[1] + pz * ab[2]) / np.float32(max(L, 1e-12)), 0, 1)
        qx = px - t * ab[0]; qy = py - t * ab[1]; qz = pz - t * ab[2]
        e = qx * qx + qy * qy + qz * qz
        d = e if d is None else np.minimum(d, e)
    return np.sqrt(d)


def apply_rivers(P, NET, hm, mk, X, Y, Z, W, H, r0, cancel=None):
    Wt = P['water']
    px = 2 * math.pi / W
    vf = max(float(Wt['valley_width']), 1.0)
    va = min(max(float(Wt['valleys']), 0.0), 1.0)
    ocean = bool(P['shape']['ocean'])
    carve = np.zeros(hm.shape, np.float32)
    r1 = r0 + hm.shape[0]
    for k, g in enumerate(NET['groups']):
        if cancel is not None and k % 256 == 0:
            cancel()
        hw0 = g['hw']
        hw = max(hw0, 0.75 * px)
        vis = min(1.0, hw0 / (0.75 * px))
        vhw = max(hw0 * vf, 2.5 * px)
        win = spot_window(g['c'], g['ext'] + max(vhw, hw * 1.3) + px, W, H, r0, r1, X, Y, Z)
        if win is None:
            continue
        idx, sx, sy, sz = win
        d = seg_dist(sx, sy, sz, g['A'], g['B'])
        if not (d < max(vhw, hw * 1.3)).any():
            continue
        chan = (1 - ss(np.float32(0.45 * hw), np.float32(1.25 * hw), d)) * np.float32(vis * (0.25 + 0.75 * g['fade']))
        here = hm[idx]
        c = chan * np.float32(g['dep'])
        if va > 0:
            val = (1 - ss(0, np.float32(vhw), d)) ** np.float32(1.5)
            c = np.maximum(c, val * np.float32(0.4 * va) * np.maximum(here, 0))
        if ocean:
            c = np.minimum(c, np.maximum(here - 2, 0))
        carve[idx] = np.maximum(carve[idx], c)
        if mk is not None:
            mk[3][idx] = np.maximum(mk[3][idx], chan.astype(np.float16))
    hm -= carve


_CRK = {}
CRK_W = 512


def crack_distance(X, Y, Z, seed, curvy):
    r = np.random.default_rng([seed, 5])
    n = r.normal(size=3)
    n /= np.linalg.norm(n)
    d = np.arcsin(np.clip(X * np.float32(n[0]) + Y * np.float32(n[1]) + Z * np.float32(n[2]), -1, 1))
    if curvy > 0:
        d = d + fbm(X, Y, Z, 1.3, 3.0, seed + 11, 0.4, 2) * np.float32(0.12 * curvy)
    return d.astype(np.float32)


def crack_fields(P):
    C = P.get('cracks') or {}
    if float(C.get('amount', 0)) <= 0 or float(C.get('depth', 0)) == 0 and float(P['colors'].get('crack_amount', 0)) == 0:
        return None
    if C['style'] == 'cells':
        return {'style': 'cells'}
    n = int(C['count'])
    sd = int(C['seed'])
    cv = min(max(float(C['curvy']), 0.0), 1.0)
    key = json.dumps([sd, n, round(cv, 4)])
    g = _CRK.get(key)
    if g is None:
        X, Y, Z = rows_xyz(CRK_W, CRK_W // 2, 0, CRK_W // 2)
        fields = []
        for k in range(n):
            fields.append(crack_distance(X, Y, Z, sd * 1000 + 17 * k + 3, cv))
            fields.append(fbm(X, Y, Z, 0.7, 1.6, sd * 1000 + 17 * k + 9, 0.5, 2))
        g = np.stack(fields)
        if len(_CRK) > 4:
            _CRK.clear()
        _CRK[key] = g
    return {'style': 'lines', 'grid': g, 'n': n}


def bilinear_rows(G, W, H, r0, r1):
    Hc, Wc = G.shape[-2:]
    fy = np.clip((np.arange(r0, r1, dtype=np.float64) + 0.5) / H * Hc - 0.5, 0, Hc - 1.0001)
    fx = (np.arange(W, dtype=np.float64) + 0.5) / W * Wc - 0.5
    y0 = np.floor(fy).astype(np.int64); ty = (fy - y0).astype(np.float32)[:, None]
    x0 = np.floor(fx).astype(np.int64); tx = (fx - x0).astype(np.float32)[None, :]
    x0 %= Wc; x1 = (x0 + 1) % Wc; y1 = np.minimum(y0 + 1, Hc - 1)
    out = []
    for g in G:
        a = g[y0][:, x0] * (1 - tx) + g[y0][:, x1] * tx
        b = g[y1][:, x0] * (1 - tx) + g[y1][:, x1] * tx
        out.append((a * (1 - ty) + b * ty).astype(np.float32))
    return out


def worley(X, Y, Z, f, seed):
    x = X * np.float32(f); y = Y * np.float32(f); z = Z * np.float32(f)
    xf = np.floor(x); yf = np.floor(y); zf = np.floor(z)
    fx = x - xf; fy = y - yf; fz = z - zf
    xi = xf.astype(np.int32).view(U); yi = yf.astype(np.int32).view(U); zi = zf.astype(np.int32).view(U)
    sd = U((seed * 0x27D4EB2F + 0x9E3779B9) & 0xFFFFFFFF)
    F1 = np.full(X.shape, np.float32(9)); F2 = np.full(X.shape, np.float32(9))
    for dx in (-1, 0, 1):
        hx = (xi + U(dx & 0xFFFFFFFF)) * U(0x9E3779B1)
        for dy in (-1, 0, 1):
            hy = (yi + U(dy & 0xFFFFFFFF)) * U(0x85EBCA77)
            for dz in (-1, 0, 1):
                h = hx ^ hy ^ ((zi + U(dz & 0xFFFFFFFF)) * U(0xC2B2AE3D)) ^ sd
                h *= U(0x2C1B3C6D); h ^= h >> U(15); h *= U(0x297A2D39); h ^= h >> U(13)
                jx = (h & U(1023)).astype(np.float32) * np.float32(1 / 1023.0)
                jy = ((h >> U(10)) & U(1023)).astype(np.float32) * np.float32(1 / 1023.0)
                jz = ((h >> U(20)) & U(1023)).astype(np.float32) * np.float32(1 / 1023.0)
                ex = np.float32(dx) + jx - fx; ey = np.float32(dy) + jy - fy; ez = np.float32(dz) + jz - fz
                d2 = ex * ex + ey * ey + ez * ez
                F2 = np.where(d2 < F1, F1, np.minimum(F2, d2))
                F1 = np.minimum(F1, d2)
    return np.sqrt(F1), np.sqrt(F2)


def apply_cracks(P, CK, hm, mk, X, Y, Z, W, H, r0, fmax):
    C = P['cracks']
    Rk = float(P['radius']) / 1000.0
    px = 2 * math.pi / W
    hw0 = max(float(C['width']), 0.1) * 0.5 / Rk
    hw = max(hw0, 0.8 * px)
    vis = np.float32(min(1.0, hw0 / (0.8 * px)))
    amt = min(max(float(C['amount']), 0.0), 1.0)
    t = 0.5 - 1.0 * amt
    sd = int(C['seed'])
    wob = fbm(X, Y, Z, min(0.35 / hw, fmax), fmax, sd * 1000 + 401, 0.5, 4) * np.float32(hw * 0.4)
    trough = np.zeros(X.shape, np.float32); ridge = np.zeros(X.shape, np.float32); cw = np.zeros(X.shape, np.float32)
    hwf = np.float32(hw)

    def add(d, m):
        np.maximum(trough, (1 - ss(0.25 * hwf, hwf, d)) * m, out=trough)
        np.maximum(ridge, np.exp(-((d - 1.8 * hwf) / (0.7 * hwf)) ** 2) * m, out=ridge)
        np.maximum(cw, (1 - ss(0.4 * hwf, 1.6 * hwf, d)) * m, out=cw)
    if CK['style'] == 'lines':
        F = bilinear_rows(CK['grid'], W, H, r0, r0 + hm.shape[0])
        for k in range(CK['n']):
            D, M = F[2 * k], F[2 * k + 1]
            m = ss(np.float32(t - 0.08), np.float32(t + 0.08), M)
            add(np.abs(D) + wob, m)
    else:
        f = Rk / max(float(C['cell_size']), 1.0)
        F1, F2 = worley(X, Y, Z, f, sd)
        e = (F2 - F1) * np.float32(0.5 / f)
        m = ss(np.float32(t - 0.08), np.float32(t + 0.08), fbm(X, Y, Z, 1.0, 3.0, sd * 1000 + 409, 0.5, 2))
        add(e + wob, m)
    hm -= np.float32(float(C['depth'])) * trough * vis
    hm += np.float32(float(C['depth']) * float(C['ridges']) * 0.8) * ridge * vis
    if mk is not None:
        np.maximum(mk[4], (cw * vis).astype(np.float16), out=mk[4])


def default_feature(t, radius):
    Rk = radius / 1000.0
    size = {'crater': 0.12, 'basin': 0.6, 'volcano': 0.4, 'mountain': 0.35, 'plateau': 0.3}[t] * Rk
    size = round(max(5.0, min(size, {'crater': 300, 'basin': 2500, 'volcano': 700, 'mountain': 800, 'plateau': 1500}[t])))
    height = {'crater': 0.0, 'basin': 0.0, 'volcano': round(min(20000, size * 25) / 100) * 100,
              'mountain': round(min(12000, size * 20) / 100) * 100, 'plateau': round(max(500, min(6000, size * 15)) / 50) * 50}[t]
    return {'type': t, 'lat': 0.0, 'lon': 180.0, 'size': float(size), 'height': float(height), 'fresh': 1.0 if t == 'crater' else 0.3}


def gblur(a, sigma):
    if sigma < 0.3:
        return a
    r = max(1, int(math.ceil(sigma * 3)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1, dtype=np.float32) / sigma) ** 2)
    k /= k.sum()
    o = np.zeros_like(a)
    for i, w in enumerate(k):
        o += np.float32(w) * np.roll(a, i - r, 1)
    p = np.pad(o, ((r, r), (0, 0)), mode='edge')
    out = np.zeros_like(a)
    for i, w in enumerate(k):
        out += np.float32(w) * p[i:i + a.shape[0]]
    return out


def slopes(hm, radius, sigma=0.0):
    h = gblur(hm, sigma) if sigma > 0 else hm
    H, W = h.shape
    lat = row_lat(H, 0, H)
    dy = radius * math.pi / H
    dx = (radius * 2 * math.pi / W) * np.maximum(np.cos(lat), 0.5 / H)
    gy = np.empty_like(h)
    gy[1:-1] = (h[:-2] - h[2:]) / np.float32(2 * dy)
    gy[0] = (h[0] - h[1]) / np.float32(dy)
    gy[-1] = (h[-2] - h[-1]) / np.float32(dy)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * dx.astype(np.float32))[:, None]
    return gx, gy


def colour_noise(P, X, Y, Z, fmax):
    sd = int(P['seed'])
    ps = max(float(P['colors']['patch_size']), 0.1)
    n1 = fbm(X, Y, Z, 3.0 / ps, fmax, sd + 101, 0.55, 5)
    n2 = fbm(X, Y, Z, 7.0 / ps, fmax, sd + 103, 0.5, 4)
    n3 = fbm(X, Y, Z, 1.6, fmax, sd + 107, 0.55, 5)
    nj = fbm(X, Y, Z, 9.0, fmax, sd + 109, 0.5, 3)
    return n1, n2, n3, nj


def colourize(P, hm, gx, gy, mk, lat, noise):
    C = P['colors']
    n1, n2, n3, nj = noise
    hj = hm + np.float32(float(C['jitter']) * 1.6) * nj
    hs = np.array([s[0] for s in C['stops']], np.float32)
    cs = np.array([s[1] for s in C['stops']], np.float32)
    if len(hs) == 1:
        col = np.broadcast_to(cs[0], hm.shape + (3,)).astype(np.float32).copy()
    else:
        col = np.stack([np.interp(hj, hs, cs[:, i]).astype(np.float32) for i in range(3)], -1)
    ocean = P['shape']['ocean']
    land = ss(-5, 5, hm) if ocean else np.ones(hm.shape, np.float32)
    latd = np.degrees(lat).astype(np.float32)
    if latd.ndim == 1:
        latd = latd[:, None]
    alat = np.abs(latd)
    pt = float(C['patches'])
    if pt > 0:
        col *= (1 + np.float32(pt * 0.3) * n2)[..., None]
        t = ss(0.02, 0.3, n1) * np.float32(pt * 0.55)
        col += (np.array(C['patch_color'], np.float32) - col) * t[..., None]
    dry = C['dry']
    da = float(dry['amount'])
    if da > 0:
        wdt = max(float(dry['width']), 1.0)
        w = np.exp(-((alat - np.float32(dry['lat'])) / np.float32(wdt)) ** 2) * np.clip(np.float32(0.6) + np.float32(1.3) * n1, 0, 1)
        w = w * np.float32(min(da, 1.0)) * land * (1 - ss(1500, 4000, hm))
        dc = np.array(dry['color'], np.float32)[None, None] * (1 + np.float32(0.08) * n2)[..., None]
        col += (dc - col) * w[..., None]
    cold = C['cold']
    ka = float(cold['amount'])
    if ka > 0:
        l0 = float(cold['lat'])
        w = ss(l0 - 8, l0 + 8, alat + np.float32(10) * n3) * np.float32(min(ka, 1.0)) * land
        kc = np.array(cold['color'], np.float32)[None, None] * (1 + np.float32(0.06) * n2)[..., None]
        col += (kc - col) * w[..., None]
    slope = np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy)))
    ra = float(C['rock_amount'])
    if ra > 0:
        w = ss(C['rock_slope'][0], C['rock_slope'][1], slope) * np.float32(min(ra, 1.0))
        rock = np.array(C['rock'], np.float32)[None, None] * (1 + np.float32(0.12) * n2)[..., None]
        col += (rock - col) * w[..., None]
    if mk is not None:
        va = float(C['volcano_amount'])
        if va > 0:
            vt = mk[2].astype(np.float32) * np.float32(min(va, 1.0))
            vc = np.array(C['volcano_color'], np.float32)[None, None] * (1 + np.float32(0.1) * n2)[..., None]
            col += (vc - col) * vt[..., None]
        fa = float(C['crater_floor_amount'])
        if fa > 0:
            cf = mk[1].astype(np.float32) * np.float32(min(fa, 1.0))
            fc = np.array(C['crater_floor'], np.float32)[None, None] * (1 + np.float32(0.08) * n2)[..., None]
            col += (fc - col) * cf[..., None]
        ra_ = float(C.get('river_amount', 1.0))
        if ra_ > 0:
            rw = mk[3].astype(np.float32) * np.float32(min(ra_, 1.0))
            if C.get('river_color') is not None:
                rc = np.array(C['river_color'], np.float32)[None, None]
            elif ocean:
                rc = np.array(C['shallow'], np.float32)[None, None]
            else:
                rc = col * np.float32(0.72)
            col += (rc - col) * rw[..., None]
        ka_ = float(C.get('crack_amount', 0.0))
        if ka_ > 0:
            kw = mk[4].astype(np.float32) * np.float32(min(ka_, 1.0))
            kc = np.array(C['crack_color'], np.float32)[None, None] * (1 + np.float32(0.08) * n2)[..., None]
            col += (kc - col) * kw[..., None]
        ej = mk[0].astype(np.float32)
        if C.get('ejecta_color') is None:
            col = col * (1 + np.float32(0.5) * ej)[..., None] + (np.float32(34) * ej)[..., None]
        else:
            ec = np.array(C['ejecta_color'], np.float32)[None, None]
            col += (ec - col) * (np.clip(ej * np.float32(1.25), 0, 1))[..., None]
    if ocean:
        d = np.maximum(-hm, 0)
        wd = max(float(C['water_depth']), 1.0)
        a = (1 - np.exp(-d / np.float32(wd)))[..., None]
        water = np.array(C['shallow'], np.float32) * (1 - a) + np.array(C['deep'], np.float32) * a
        cover = ((np.float32(0.8) + np.float32(0.2) * ss(0, wd * 0.15, d)) * ss(-8, 8, -hm))[..., None]
        col += (water - col) * cover
    cn_, cs_ = float(C['cap_north']), float(C['cap_south'])
    ice = np.zeros(hm.shape, np.float32)
    if cn_ < 90 or cs_ < 90:
        wet = np.float32(4) + np.float32(14) * np.float32(1 - min(max(float(C['sea_ice']), 0.0), 1.0))
        bonus = np.where(hm >= 0, np.float32(4) * np.clip(hm / np.float32(1500), 0, 1), -wet * np.clip(-hm / np.float32(1500), 0, 1) - (wet - 4) * ss(0, 300, -hm))
        el = alat + np.float32(float(C['cap_ragged']) * 22) * n3 + bonus
        cl = np.where(latd >= 0, np.float32(cn_), np.float32(cs_))
        ice = np.where(cl < 90, ss(cl - 3.0, cl + 3.0, el), 0).astype(np.float32)
    sl = float(C['snow_line'])
    sinl = np.sin(np.radians(alat))
    se = sl * (1 - 0.6 * sinl * sinl)
    sn = ss(se - 700, se + 700, hm + np.float32(500) * n3 + np.float32(450) * nj + np.float32(300) * n2) * (1 - ss(float(C['snow_slope']) - 8, float(C['snow_slope']) + 8, slope + np.float32(6) * n2))
    if ocean:
        sn = sn * (hm > 0)
    ice = np.maximum(ice, sn)
    icec = np.array(C['ice'], np.float32)[None, None] * (1 + np.float32(0.06) * n2 + np.float32(0.04) * nj)[..., None]
    col += (icec - col) * ice[..., None]
    br, ct, sa = float(C['brightness']), float(C['contrast']), float(C['saturation'])
    if sa != 1.0:
        g = (col[..., 0] * np.float32(0.3) + col[..., 1] * np.float32(0.59) + col[..., 2] * np.float32(0.11))[..., None]
        col = g + (col - g) * np.float32(sa)
    if ct != 1.0:
        col = (col - np.float32(128)) * np.float32(ct) + np.float32(128)
    if br != 0.0:
        col = col + np.float32(br * 128)
    return np.clip(col + 0.5, 0, 255).astype(np.uint8)


def strips(H, W, px=1 << 19):
    n = max(8, min(H, px // max(W, 1)))
    return [(r, min(H, r + n)) for r in range(0, H, n)]


def run_strips(fn, jobs, workers=None, progress=None):
    workers = workers or THREADS
    if workers <= 1 or len(jobs) <= 1:
        for i, j in enumerate(jobs):
            fn(*j)
            if progress:
                progress(i + 1, len(jobs))
        return
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(fn, *j) for j in jobs]
        for i, f in enumerate(futs):
            f.result()
            if progress:
                progress(i + 1, len(futs))


def make_height(P, W, T=None, CR=None, cancel=None, progress=None, workers=None):
    H = W // 2
    NET = river_network(P, cancel)
    CK = crack_fields(P)
    T = T or Terrain(P)
    if CR is None:
        CR = crater_list(P)
    VL = volcano_list(P)
    feats = P.get('features') or []
    levels = plateau_levels(P, T) if any(f['type'] == 'plateau' for f in feats) else None
    hm = np.zeros((H, W), np.float32)
    need = CR is not None or VL is not None or feats or NET is not None or CK is not None
    mk = np.zeros((5, H, W), np.float16) if need else None
    fm = fmax_for(W)

    def job(r0, r1):
        if cancel:
            cancel()
        X, Y, Z = rows_xyz(W, H, r0, r1)
        hm[r0:r1] = T.metres(X, Y, Z, fm, T.low_rows(W, H, r0, r1))
        sub = None if mk is None else mk[:, r0:r1]
        if CR is not None:
            apply_craters(P, CR, hm[r0:r1], sub, X, Y, Z, W, H, r0, cancel)
        if VL is not None:
            apply_volcanoes(P, VL, hm[r0:r1], sub, X, Y, Z, W, H, r0, cancel)
        if feats:
            apply_features(P, hm[r0:r1], sub, X, Y, Z, W, H, r0, fm, cancel, levels)
        if NET is not None:
            apply_rivers(P, NET, hm[r0:r1], sub, X, Y, Z, W, H, r0, cancel)
        if CK is not None:
            apply_cracks(P, CK, hm[r0:r1], sub, X, Y, Z, W, H, r0, fm)
    run_strips(job, strips(H, W), workers, progress)
    return hm, mk


def make_colour(P, hm, mk, W, cancel=None, progress=None, workers=None, noise_cache=None):
    H = W // 2
    gx, gy = slopes(hm, float(P['radius']), 0.6 * W / 2048.0 if W > 2048 else 0.0)
    if P['shape']['ocean']:
        wet = hm < 0
        gx = np.where(wet, 0, gx); gy = np.where(wet, 0, gy)
    col = np.zeros((H, W, 3), np.uint8)
    fm = fmax_for(W)
    lat = row_lat(H, 0, H)

    def job(r0, r1):
        if cancel:
            cancel()
        key = (W, r0, r1, int(P['seed']), float(P['colors']['patch_size']))
        nz = noise_cache.get(key) if noise_cache is not None else None
        if nz is None:
            X, Y, Z = rows_xyz(W, H, r0, r1)
            nz = colour_noise(P, X, Y, Z, fm)
            if noise_cache is not None:
                noise_cache[key] = nz
        col[r0:r1] = colourize(P, hm[r0:r1], gx[r0:r1], gy[r0:r1], None if mk is None else mk[:, r0:r1], lat[r0:r1], nz)
    run_strips(job, strips(H, W), workers, progress)
    return col, gx, gy


def normal_rgba(hm, radius, strength, ocean, flip=True):
    gx, gy = slopes(hm, radius, 0.5)
    if ocean:
        wet = hm < 0
        gx = np.where(wet, 0, gx); gy = np.where(wet, 0, gy)
    k = np.float32(strength)
    nx = -k * gx; ny = -k * gy
    nn = np.sqrt(nx * nx + ny * ny + 1)
    A = np.clip(128 + 127 * nx / nn + 0.5, 1, 255).astype(np.uint8)
    G = np.clip(128 + 127 * ny / nn + 0.5, 1, 255).astype(np.uint8)
    if flip:
        A = A[::-1]; G = G[::-1]
    return np.ascontiguousarray(G), np.ascontiguousarray(A)


def shade_map(gx, gy, strength, light=(-0.55, 0.55, 0.63)):
    k = np.float32(strength)
    nx = -k * gx; ny = -k * gy
    nn = np.sqrt(nx * nx + ny * ny + 1)
    L = np.array(light, np.float32); L /= np.linalg.norm(L)
    d = (nx * L[0] + ny * L[1] + L[2]) / nn
    return np.clip(d / L[2], 0.2, 1.7)


def render_globe(col, gx, gy, S, tilt, vlat, vlon, strength, light=None, ocean=None):
    H, W = col.shape[:2]
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    u = (xx + 0.5) / S * 2 - 1
    v = 1 - (yy + 0.5) / S * 2
    r2 = u * u + v * v
    m = r2 < 1
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    t = np.radians(tilt); cu, su = np.float32(np.cos(t)), np.float32(np.sin(t))
    u2 = u * cu - v * su; v2 = u * su + v * cu
    a = np.radians(vlat); cl, sl = np.float32(np.cos(a)), np.float32(np.sin(a))
    y3 = v2 * cl + z * sl; z3 = -v2 * sl + z * cl
    lat = np.arcsin(np.clip(y3, -1, 1)); dlon = np.arctan2(u2, z3)
    lon = dlon + np.radians(vlon)
    fx = (lon / (2 * np.pi)) % 1 * W - 0.5
    fy = np.clip((0.5 - lat / np.pi) * H - 0.5, 0, H - 1.001)
    x0 = np.floor(fx).astype(np.int32); y0 = fy.astype(np.int32)
    tx = (fx - x0)[..., None]; ty = (fy - y0)[..., None]
    x0 %= W; x1 = (x0 + 1) % W; y1 = np.minimum(y0 + 1, H - 1)
    c = col.astype(np.float32) if col.dtype != np.float32 else col
    cc = (c[y0, x0] * (1 - tx) + c[y0, x1] * tx) * (1 - ty) + (c[y1, x0] * (1 - tx) + c[y1, x1] * tx) * ty
    sl_, cl_ = np.sin(lat), np.cos(lat)
    sd, cd = np.sin(dlon), np.cos(dlon)
    Ex, Ey, Ez = cd, np.zeros_like(cd), -sd
    Nx, Ny, Nz = -sl_ * sd, cl_, -sl_ * cd

    def back(wx, wy, wz):
        vv2 = wy * cl - wz * sl
        zz = wy * sl + wz * cl
        return wx * cu + vv2 * su, -wx * su + vv2 * cu, zz
    ex, ey, ez = back(Ex, Ey, Ez)
    nx_, ny_, nz_ = back(Nx, Ny, Nz)
    sx = gx[y0, x0]; sy = gy[y0, x0]
    k = np.float32(strength)
    px = u - k * (sx * ex + sy * nx_)
    py = v - k * (sx * ey + sy * ny_)
    pz = z - k * (sx * ez + sy * nz_)
    pn = np.sqrt(px * px + py * py + pz * pz) + np.float32(1e-6)
    L = np.array(light or [0.55, 0.3, 0.78], np.float32); L /= np.linalg.norm(L)
    nd = np.clip((px * L[0] + py * L[1] + pz * L[2]) / pn, 0, 1)
    nd0 = np.clip(u * L[0] + v * L[1] + z * L[2], 0, 1)
    lit = np.float32(0.06) + np.float32(1.0) * nd ** np.float32(0.9) * ss(0, 0.12, nd0)
    out = cc * lit[..., None] / np.float32(255)
    if ocean is not None:
        wet = ocean[y0, x0][..., None]
        hv = np.array([L[0], L[1], L[2] + 1], np.float32); hv /= np.linalg.norm(hv)
        spec = np.clip(u * hv[0] + v * hv[1] + z * hv[2], 0, 1) ** 60 * 0.35
        out = out + wet * spec[..., None]
    out = out * (1 - 0.18 * np.exp(-z * 4))[..., None]
    o = np.zeros((S, S, 3), np.float32)
    o[m] = out[m]
    return Image.fromarray((np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8))


ATMO_POINT = {'altitude': 0.0, 'skyExposure': 0.2, 'skyAlpha': 1.0, 'skyExtinctionTint': 1.0, 'scatteringExposure': 0.2,
              'extinctionThickness': 1.0, 'postProcessAlpha': 1.0, 'postProcessDepth': 0.0, 'extinctionTint': 1.0}
ATMO_POINT_KEYS = ('altitude', 'skyExposure', 'skyAlpha', 'skyExtinctionTint', 'scatteringExposure', 'extinctionThickness',
                   'postProcessAlpha', 'postProcessDepth', 'extinctionTint')
ATMO_VALUES = ('atmosphereStartRadiusScale', 'HR', 'HM', 'm_betaR', 'BETA_MSca', 'm_mieG', 'ozoneAbsorption', 'ozoneHeight',
               'ozoneFalloff', 'useOzone', 'averageGroundReflectance', 'multipleScattering', 'godrayStrength')
ATMO_EXTRA = [['flattenScaledSpaceMesh', '0'], ['rimBlend', '20'], ['rimpower', '600'], ['specR', '0'], ['specG', '0'],
              ['specB', '0'], ['shininess', '0'], ['noonSunlightExtinctionStrength', '1'], ['cloudColorMultiplier', '1'],
              ['cloudScatteringMultiplier', '0.2'], ['cloudSkyIrradianceMultiplier', '0'], ['volumetricsColorMultiplier', '1'],
              ['EVEIntegration_preserveCloudColors', 'False'], ['adjustScaledTexture', 'False'], ['scaledLandBrightnessAdjust', '1'],
              ['scaledLandContrastAdjust', '1'], ['scaledLandSaturationAdjust', '1'], ['scaledOceanBrightnessAdjust', '1'],
              ['scaledOceanContrastAdjust', '1'], ['scaledOceanSaturationAdjust', '1']]
ATMO = {'enabled': False, 'atmosphereStartRadiusScale': 1.0, 'HR': 3.84, 'HM': 1.0,
        'm_betaR': [0.0153408, 0.0357075, 0.0875489], 'BETA_MSca': [0.0121406, 0.0121406, 0.0121406], 'm_mieG': 0.85,
        'useOzone': True, 'ozoneAbsorption': [0.000493594, 0.00142889, 0.0000645469], 'ozoneHeight': 20.0, 'ozoneFalloff': 12.0,
        'averageGroundReflectance': 0.1, 'multipleScattering': True, 'godrayStrength': 0.7,
        'configPoints': [dict(ATMO_POINT)], 'sun': 'Sun', 'sun_color': [255, 255, 255], 'cloud_integration': True,
        'flat_model': True, 'eclipse_casters': '', 'sun_angle': 55.0, 'view': 'planet', 'extra': None}
ATMO_PRESETS = {
    'Kerbin (stock)': {'ref': 600.0, 'atmosphereStartRadiusScale': 1.0, 'HR': 3.84, 'HM': 1.0,
                       'm_betaR': [0.0153408, 0.0357075, 0.0875489], 'BETA_MSca': [0.0121406, 0.0121406, 0.0121406],
                       'm_mieG': 0.85, 'useOzone': True, 'ozoneAbsorption': [0.000493594, 0.00142889, 0.0000645469],
                       'ozoneHeight': 20.0, 'ozoneFalloff': 12.0, 'configPoints': [dict(ATMO_POINT)]},
    'Duna (stock)': {'ref': 320.0, 'atmosphereStartRadiusScale': 1.0, 'HR': 5.0, 'HM': 3.0,
                     'm_betaR': [0.04485, 0.0225, 0.0078], 'BETA_MSca': [0.0045, 0.009, 0.009], 'm_mieG': 0.7,
                     'useOzone': False, 'configPoints': [dict(ATMO_POINT, extinctionTint=0.0)]},
    'Eve (stock)': {'ref': 700.0, 'atmosphereStartRadiusScale': 1.0, 'HR': 8.0, 'HM': 4.2,
                    'm_betaR': [0.078623, 0.029649, 0.078623], 'BETA_MSca': [0.016, 0.016, 0.016], 'm_mieG': 0.82,
                    'useOzone': False, 'configPoints': [dict(ATMO_POINT, extinctionTint=0.0)]},
    'Laythe (stock)': {'ref': 500.0, 'atmosphereStartRadiusScale': 1.0, 'HR': 3.75, 'HM': 1.0,
                       'm_betaR': [0.007734, 0.018, 0.057466], 'BETA_MSca': [0.1024, 0.1024, 0.1024], 'm_mieG': 0.55,
                       'useOzone': True, 'ozoneAbsorption': [0.0, 0.00635546, 0.00341546], 'ozoneHeight': 0.0,
                       'ozoneFalloff': 10.0, 'configPoints': [dict(ATMO_POINT, skyExposure=0.12, scatteringExposure=0.12)]},
    'Earth-like': {'ref': 6371.0, 'atmosphereStartRadiusScale': 1.0, 'HR': 8.0, 'HM': 1.2,
                   'm_betaR': [0.0058, 0.0135, 0.0331], 'BETA_MSca': [0.004, 0.004, 0.004], 'm_mieG': 0.8,
                   'useOzone': True, 'ozoneAbsorption': [0.0003426, 0.0008298, 0.000036], 'ozoneHeight': 25.0,
                   'ozoneFalloff': 15.0, 'configPoints': [dict(ATMO_POINT)]},
}


def vec3(v, d):
    try:
        if isinstance(v, str):
            v = [float(x) for x in v.replace(' ', '').split(',') if x != '']
        v = [float(x) for x in v]
        if len(v) == 1:
            v = v * 3
        return [v[0], v[1], v[2]]
    except (TypeError, ValueError, IndexError):
        return list(d)


def g6(x):
    return float('%.6g' % x)


def atmo_preset(name, radius_km, fit=True):
    p = copy.deepcopy(ATMO_PRESETS[name])
    ref = p.pop('ref')
    k = float(radius_km) / ref if fit else 1.0
    if abs(k - 1) > 1e-9:
        for key in ('HR', 'HM', 'ozoneHeight', 'ozoneFalloff'):
            if key in p:
                p[key] = g6(p[key] * k)
        for key in ('m_betaR', 'BETA_MSca', 'ozoneAbsorption'):
            if key in p:
                p[key] = [g6(x / k) for x in p[key]]
        for q in p['configPoints']:
            q['altitude'] = round(q['altitude'] * k)
    return p


def atmo_entry(a):
    e = copy.deepcopy(ATMO)
    a = a if isinstance(a, dict) else {}
    for k, v in a.items():
        if k in ATMO:
            e[k] = copy.deepcopy(v)
    for k in ('m_betaR', 'BETA_MSca', 'ozoneAbsorption'):
        e[k] = [max(0.0, x) for x in vec3(e[k], ATMO[k])]
    for k in ('atmosphereStartRadiusScale', 'HR', 'HM', 'm_mieG', 'ozoneHeight', 'ozoneFalloff',
              'averageGroundReflectance', 'godrayStrength', 'sun_angle'):
        try:
            e[k] = float(e[k])
        except (TypeError, ValueError):
            e[k] = ATMO[k]
    e['HR'] = max(0.01, e['HR']); e['HM'] = max(0.01, e['HM'])
    e['ozoneFalloff'] = max(0.01, e['ozoneFalloff'])
    e['m_mieG'] = min(max(e['m_mieG'], -0.99), 0.99)
    for k in ('useOzone', 'multipleScattering', 'enabled', 'cloud_integration', 'flat_model'):
        e[k] = bool(e[k])
    pts = []
    for p in e.get('configPoints') or []:
        q = dict(ATMO_POINT)
        if isinstance(p, dict):
            for k in ATMO_POINT_KEYS:
                try:
                    q[k] = float(p.get(k, q[k]))
                except (TypeError, ValueError):
                    pass
        pts.append(q)
    e['configPoints'] = sorted(pts, key=lambda q: q['altitude']) or [dict(ATMO_POINT)]
    e['sun_color'] = [int(min(255, max(0, round(float(c))))) for c in vec3(e['sun_color'], ATMO['sun_color'])]
    e['sun'] = str(e['sun']).strip() or 'Sun'
    e['eclipse_casters'] = str(e['eclipse_casters'] or '')
    if e['view'] not in ('planet', 'limb', 'sunset'):
        e['view'] = 'planet'
    if not isinstance(e['extra'], list):
        e['extra'] = copy.deepcopy(ATMO_EXTRA)
    e['extra'] = [[str(k), str(v)] for k, v in e['extra'] if str(k) not in ATMO_VALUES and str(k) not in ('name', 'configPoints')]
    return e


def has_atmo(P):
    return bool((P.get('atmosphere') or {}).get('enabled'))


def atmo_e(P):
    e = atmo_entry(P.get('atmosphere'))
    e['radius'] = max(1.0, float(P.get('radius', 600000.0)) / 1000.0)
    return e


def atmo_top(e):
    tr = 1000.0 * e['HR'] * np.log(max(np.linalg.norm(e['m_betaR']), 2e-7) / 1e-7)
    tm = 1000.0 * e['HM'] * np.log(max(np.linalg.norm(e['BETA_MSca']), 2e-7) / 1e-7)
    t = max(tr, tm)
    if e['useOzone']:
        t = max(t, 1000.0 * (e['ozoneHeight'] + e['ozoneFalloff']))
    return t / 1000.0


class AtmoModel:
    def __init__(self, e):
        R = e['radius']
        self.Rg = float(e['atmosphereStartRadiusScale'])
        self.Rt = self.Rg + atmo_top(e) / R
        self.HR = e['HR'] / R; self.HM = e['HM'] / R
        self.bR = np.array(e['m_betaR'], np.float32) * np.float32(R)
        self.bM = np.array(e['BETA_MSca'], np.float32) * np.float32(R)
        self.bMe = self.bM / np.float32(0.9)
        self.oz = bool(e['useOzone'])
        self.bO = np.array(e['ozoneAbsorption'], np.float32) * np.float32(R)
        self.oH = e['ozoneHeight'] / R; self.oF = e['ozoneFalloff'] / R
        self.g = float(e['m_mieG'])
        self.albedo = float(e['averageGroundReflectance'])
        self.H = np.sqrt(self.Rt ** 2 - self.Rg ** 2)
        self.trans_lut()
        self.ms = self.ms_lut() if e['multipleScattering'] else None

    def dens(self, r):
        h = np.maximum(r - np.float32(self.Rg), 0)
        dR = np.exp(-h / np.float32(self.HR))
        dM = np.exp(-h / np.float32(self.HM))
        dO = np.maximum(0, 1 - np.abs(h - np.float32(self.oH)) / np.float32(self.oF)) if self.oz else None
        return dR, dM, dO

    def ext(self, dR, dM, dO):
        s = dR[..., None] * self.bR + dM[..., None] * self.bMe
        if dO is not None:
            s = s + dO[..., None] * self.bO
        return s

    def trans_lut(self, nr=64, nm=256, steps=96):
        Rg, Rt, H = self.Rg, self.Rt, self.H
        xr = np.linspace(0, 1, nr, dtype=np.float64)
        xm = np.linspace(0, 1, nm, dtype=np.float64)
        rho = H * xr
        r = np.sqrt(rho ** 2 + Rg ** 2)[:, None]
        dmin = (Rt - r); dmax = rho[:, None] + H
        d = dmin + xm[None, :] * (dmax - dmin)
        mu = np.where(d > 0, (H * H - rho[:, None] ** 2 - d * d) / np.maximum(2 * r * d, 1e-12), 1.0)
        mu = np.clip(mu, -1, 1)
        tau = np.zeros((nr, nm, 3), np.float32)
        for i in range(steps):
            t = (i + 0.5) / steps * d
            ri = np.sqrt(np.maximum(t * t + 2 * r * mu * t + r * r, 0)).astype(np.float32)
            tau += self.ext(*self.dens(ri)) * (d / steps).astype(np.float32)[..., None]
        self.tau = tau
        self.nr, self.nm = nr, nm

    def sun_t(self, r, mu):
        Rg, Rt, H = self.Rg, self.Rt, self.H
        r = np.clip(r, Rg, Rt).astype(np.float32)
        rho = np.sqrt(np.maximum(r * r - np.float32(Rg * Rg), 0))
        disc = r * r * (mu * mu - 1) + np.float32(Rt * Rt)
        d = np.maximum(-r * mu + np.sqrt(np.maximum(disc, 0)), 0)
        dmin = np.float32(Rt) - r; dmax = rho + np.float32(H)
        xm = np.clip((d - dmin) / np.maximum(dmax - dmin, 1e-9), 0, 1) * (self.nm - 1)
        xr = np.clip(rho / np.float32(H), 0, 1) * (self.nr - 1)
        i0 = np.minimum(xr.astype(np.int32), self.nr - 2); fr = (xr - i0)[..., None]
        j0 = np.minimum(xm.astype(np.int32), self.nm - 2); fm = (xm - j0)[..., None]
        T = self.tau
        tau = (T[i0, j0] * (1 - fm) + T[i0, j0 + 1] * fm) * (1 - fr) + (T[i0 + 1, j0] * (1 - fm) + T[i0 + 1, j0 + 1] * fm) * fr
        hor = -np.sqrt(np.maximum(1 - (np.float32(Rg) / r) ** 2, 0))
        lit = np.clip((mu - hor) / np.float32(0.004) + 0.5, 0, 1)
        lit = lit * lit * (3 - 2 * lit)
        return np.exp(-tau) * lit[..., None]

    def ms_lut(self, nr=16, nm=24, nd=48, steps=16):
        Rg, Rt = self.Rg, self.Rt
        xr = np.linspace(0, 1, nr)
        rr = Rg + (Rt - Rg) * xr ** 2
        ms = np.linspace(-1, 1, nm)
        k = np.arange(nd) + 0.5
        cz = 1 - 2 * k / nd
        phi = np.pi * (1 + 5 ** 0.5) * k
        sz = np.sqrt(1 - cz * cz)
        D = np.stack([sz * np.cos(phi), sz * np.sin(phi), cz], -1)
        R_, M_, K_ = np.meshgrid(rr, ms, np.arange(nd), indexing='ij')
        d = D[K_]
        r0 = R_
        mu = d[..., 2]
        disc_g = r0 * r0 * (mu * mu - 1) + Rg * Rg
        tg = -r0 * mu - np.sqrt(np.maximum(disc_g, 0))
        hit = (disc_g >= 0) & (tg > 0)
        tt = -r0 * mu + np.sqrt(np.maximum(r0 * r0 * (mu * mu - 1) + Rt * Rt, 0))
        tmax = np.where(hit, tg, tt)
        sun = np.stack([np.sqrt(1 - M_ * M_), np.zeros_like(M_), M_], -1)
        L2 = np.zeros(R_.shape + (3,), np.float32)
        Lf = np.zeros(R_.shape + (3,), np.float32)
        Tv = np.ones(R_.shape + (3,), np.float32)
        pu = np.float32(1 / (4 * np.pi))
        for i in range(steps):
            t = (i + 0.5) / steps * tmax
            ds = (tmax / steps).astype(np.float32)[..., None]
            px = d[..., 0] * t; py = d[..., 1] * t; pz = r0 + d[..., 2] * t
            r = np.sqrt(px * px + py * py + pz * pz).astype(np.float32)
            mus = ((px * sun[..., 0] + pz * sun[..., 2]) / r).astype(np.float32)
            dR, dM, dO = self.dens(r)
            se = self.ext(dR, dM, dO)
            ss_ = dR[..., None] * self.bR + dM[..., None] * self.bM
            st = np.exp(-se * ds)
            w = np.where(se > 1e-9, (1 - st) / np.maximum(se, 1e-9), ds)
            Ts = self.sun_t(r, mus)
            L2 += Tv * ss_ * Ts * pu * w
            Lf += Tv * ss_ * w
            Tv *= st
        gx = d[..., 0] * tmax; gy = d[..., 1] * tmax; gz = r0 + d[..., 2] * tmax
        gr = np.sqrt(gx * gx + gy * gy + gz * gz)
        gmu = (gx * sun[..., 0] + gz * sun[..., 2]) / np.maximum(gr, 1e-9)
        Tg = self.sun_t(gr.astype(np.float32), gmu.astype(np.float32))
        L2 += np.where(hit[..., None], Tv * Tg * np.maximum(gmu, 0)[..., None] * np.float32(self.albedo / np.pi), 0)
        L2n = L2.mean(2); fms = np.clip(Lf.mean(2), 0, 0.98)
        self.ms_nr, self.ms_nm = nr, nm
        return (L2n / (1 - fms)).astype(np.float32)

    def ms_at(self, r, mus):
        xr = np.sqrt(np.clip((r - np.float32(self.Rg)) / np.float32(self.Rt - self.Rg), 0, 1)) * (self.ms_nr - 1)
        xm = np.clip((mus + 1) * 0.5, 0, 1) * (self.ms_nm - 1)
        i0 = np.minimum(xr.astype(np.int32), self.ms_nr - 2); fr = (xr - i0)[..., None]
        j0 = np.minimum(xm.astype(np.int32), self.ms_nm - 2); fm = (xm - j0)[..., None]
        T = self.ms
        return (T[i0, j0] * (1 - fm) + T[i0, j0 + 1] * fm) * (1 - fr) + (T[i0 + 1, j0] * (1 - fm) + T[i0 + 1, j0 + 1] * fm) * fr

    def phases(self, nu):
        pr = 3.0 / (16 * np.pi) * (1 + nu * nu)
        g = self.g
        pm = 1.5 / (4 * np.pi) * (1 - g * g) * (1 + g * g - 2 * g * nu) ** -1.5 * (1 + nu * nu) / (2 + g * g)
        return np.float32(pr), np.float32(pm)

    def jlut(self, nu, nr=192, nm=384):
        Rg, Rt = self.Rg, self.Rt
        xr = np.linspace(0, 1, nr, dtype=np.float32)
        r = (np.float32(Rg) + np.float32(Rt - Rg) * xr * xr)[:, None] * np.ones((1, nm), np.float32)
        mus = np.linspace(-1, 1, nm, dtype=np.float32)[None, :] * np.ones((nr, 1), np.float32)
        pr, pm = self.phases(nu)
        dR, dM, dO = self.dens(r)
        sR = dR[..., None] * self.bR; sM = dM[..., None] * self.bM
        J = self.sun_t(r, mus) * (sR * pr + sM * pm)
        if self.ms is not None:
            J = J + (sR + sM) * self.ms_at(r, mus)
        self.Jc = np.ascontiguousarray(J.reshape(-1, 3).T.astype(np.float32))
        self.j_nr, self.j_nm = nr, nm
        self.cR = self.bR[:, None]; self.cMe = self.bMe[:, None]; self.cO = self.bO[:, None]

    def j_at(self, r, mus):
        nr, nm = self.j_nr, self.j_nm
        xr = np.sqrt(np.maximum(r - np.float32(self.Rg), 0) * np.float32((nr - 1) ** 2 / (self.Rt - self.Rg)))
        xm = mus * np.float32(0.5 * (nm - 1)) + np.float32(0.5 * (nm - 1))
        i0 = np.minimum(xr.astype(np.int32), nr - 2)
        j0 = np.minimum(xm.astype(np.int32), nm - 2)
        fr = xr - i0; fm = xm - j0
        k = i0 * nm + j0
        J = self.Jc
        a = np.take(J, k, axis=1); b = np.take(J, k + 1, axis=1)
        c = np.take(J, k + nm, axis=1); d = np.take(J, k + nm + 1, axis=1)
        x0 = a + (c - a) * fr
        return x0 + (b + (d - b) * fr - x0) * fm

    def march(self, u, v, s0, s1, L, n, dense_end, cancel=None):
        b2 = (u * u + v * v).astype(np.float32)
        Lin = np.zeros((3,) + u.shape, np.float32)
        Tv = np.ones((3,) + u.shape, np.float32)
        ln = (s1 - s0).astype(np.float32)
        lx, ly, lz = np.float32(L[0]), np.float32(L[1]), np.float32(L[2])
        uv = u * lx + v * ly
        for i in range(n):
            if cancel and i % 4 == 0:
                cancel()
            a = (i + 0.5) / n; a1 = (i + 1.0) / n; a0 = i / float(n)
            if dense_end:
                f = 1 - (1 - a) ** 2; ds = ln * np.float32((1 - a0) ** 2 - (1 - a1) ** 2)
            else:
                f = a * a; ds = ln * np.float32(a1 * a1 - a0 * a0)
            s = s0 + ln * np.float32(f)
            r = np.sqrt(b2 + s * s)
            mus = (uv - s * lz) / r
            dR, dM, dO = self.dens(r)
            x = self.cR * (dR * ds) + self.cMe * (dM * ds)
            if dO is not None:
                x += self.cO * (dO * ds)
            np.maximum(x, np.float32(1e-20), out=x)
            em = np.expm1(-x)
            Lin += Tv * self.j_at(r, mus) * (-em / x * ds)
            Tv *= 1 + em
        return Lin.T, Tv.T


def scatterer_hdr(L, exposure):
    L = L * np.float32(exposure)
    return np.where(L < 1.413, np.power(np.maximum(L * 0.38317, 0), 1 / 2.2), 1 - np.exp(-L)).astype(np.float32)


ATMO_CACHE = {}


def atmo_model(e):
    key = json.dumps([e[k] for k in ATMO_VALUES] + [e['radius']], default=str)
    m = ATMO_CACHE.get(key)
    if m is None:
        m = AtmoModel(e)
        ATMO_CACHE[key] = m
        while len(ATMO_CACHE) > 4:
            ATMO_CACHE.pop(next(iter(ATMO_CACHE)))
    return m


def atmo_light(e, ang=None):
    ph = np.radians(float(e['sun_angle'] if ang is None else ang)); ps = np.radians(18.0)
    return np.array([np.sin(ph) * np.cos(ps), np.sin(ph) * np.sin(ps), np.cos(ph)], np.float32)


def atmo_frame(e, view, w, h, m):
    L = atmo_light(e)
    if view == 'planet':
        half = 1.0 + max(0.07, min(7 * max(m.HR, m.HM), m.Rt - 1.0 + 0.02))
        sc = min(w, h) / (2 * half)
        X = (np.arange(w, dtype=np.float32) + 0.5 - w / 2) / np.float32(sc)
        Y = (h / 2 - np.arange(h, dtype=np.float32) - 0.5) / np.float32(sc)
        u, v = np.meshgrid(X, Y)
        return u, v, 1.0 / sc
    if view == 'limb':
        n = np.array([L[0], L[1]], np.float64)
    else:
        n = np.array([-L[1], L[0]], np.float64)
    nn = np.linalg.norm(n)
    n = n / nn if nn > 1e-6 else np.array([1.0, 0.0])
    t = np.array([-n[1], n[0]])
    span = float(np.clip(30 * max(m.HR, m.HM), 0.05, 0.6))
    sc = w / span
    X = (np.arange(w, dtype=np.float32) + 0.5 - w / 2) / np.float32(sc)
    Y = (h * 0.62 - np.arange(h, dtype=np.float32) - 0.5) / np.float32(sc)
    Xg, Yg = np.meshgrid(X, Y)
    r0 = 1.0
    u = (n[0] * r0 + Xg * t[0] + Yg * n[0]).astype(np.float32)
    v = (n[1] * r0 + Xg * t[1] + Yg * n[1]).astype(np.float32)
    return u, v, 1.0 / sc


def sphere_ground(tex, gx, gy, k, x, y, z, tilt, vlat, vlon, L):
    H, W = tex.shape[:2]
    t = np.radians(tilt); cu, su = np.float32(np.cos(t)), np.float32(np.sin(t))
    u2 = x * cu - y * su; v2 = x * su + y * cu
    a = np.radians(vlat); cl, sl = np.float32(np.cos(a)), np.float32(np.sin(a))
    y3 = v2 * cl + z * sl; z3 = -v2 * sl + z * cl
    lat = np.arcsin(np.clip(y3, -1, 1)); dlon = np.arctan2(u2, z3)
    fx = ((dlon + np.float32(np.radians(vlon))) / np.float32(2 * np.pi)) % 1 * W - 0.5
    fy = np.clip((0.5 - lat / np.pi) * H - 0.5, 0, H - 1.001)
    x0 = np.floor(fx).astype(np.int32); y0 = fy.astype(np.int32)
    ax = (fx - x0).astype(np.float32)[:, None]; ay = (fy - y0).astype(np.float32)[:, None]
    x0 %= W; x1 = (x0 + 1) % W; y1 = np.minimum(y0 + 1, H - 1)
    c = (tex[y0, x0] * (1 - ax) + tex[y0, x1] * ax) * (1 - ay) + (tex[y1, x0] * (1 - ax) + tex[y1, x1] * ax) * ay
    nd0 = np.clip(x * L[0] + y * L[1] + z * L[2], 0, 1)
    if gx is None or gy is None or k <= 0:
        return c * nd0[:, None]
    sla, cla = np.sin(lat), np.cos(lat)
    sd, cd = np.sin(dlon), np.cos(dlon)

    def back(wx, wy, wz):
        vv2 = wy * cl - wz * sl
        zz = wy * sl + wz * cl
        return wx * cu + vv2 * su, -wx * su + vv2 * cu, zz
    ex, ey, ez = back(cd, np.zeros_like(cd), -sd)
    nx, ny, nz = back(-sla * sd, cla, -sla * cd)
    gh, gw = gx.shape
    yy = np.minimum((fy + 0.5) * (gh / float(H)), gh - 1).astype(np.int32)
    xx = (((fx + 0.5) * (gw / float(W))).astype(np.int32)) % gw
    sx = gx[yy, xx]; sy = gy[yy, xx]
    kk = np.float32(k)
    qx = x - kk * (sx * ex + sy * nx)
    qy = y - kk * (sx * ey + sy * ny)
    qz = z - kk * (sx * ez + sy * nz)
    qn = np.sqrt(qx * qx + qy * qy + qz * qz) + np.float32(1e-6)
    nd = np.clip((qx * L[0] + qy * L[1] + qz * L[2]) / qn, 0, 1)
    nd = np.minimum(nd, nd0 * np.float32(4))
    return c * nd[:, None]


def render_atmo(P, tex, gx=None, gy=None, view=None, w=560, h=360, rot=(0.0, 0.0), steps=16, chunk=60000, cancel=None, bg=None):
    e = atmo_e(P)
    m = atmo_model(e)
    view = view or e['view']
    pt = e['configPoints'][-1]
    L = atmo_light(e)
    sun = np.array(e['sun_color'], np.float32) / 255 * np.float32(100.0)
    u, v, px = atmo_frame(e, view, w, h, m)
    m.jlut(-float(L[2]))
    b = np.sqrt(u * u + v * v)
    out = np.zeros((h, w, 3), np.float32)
    cov = np.clip((1 - b) / np.float32(px) + 0.5, 0, 1)
    pv = P.get('preview', {'tilt': 0, 'view_lat': 0, 'view_lon': 0})
    tilt = float(pv.get('tilt', 0)); vlat = max(-90.0, min(90.0, float(pv.get('view_lat', 0)) + rot[1])); vlon = float(pv.get('view_lon', 0)) + rot[0]
    k = float(P.get('normal_strength', 0.0))
    gi = np.nonzero((cov > 0).ravel())[0]
    si = np.nonzero(((cov < 1) & (b < m.Rt)).ravel())[0]
    uf, vf, bf = u.ravel(), v.ravel(), b.ravel()
    flat = out.reshape(-1, 3)
    covf = cov.ravel()
    for c0 in range(0, len(gi), chunk):
        idx = gi[c0:c0 + chunk]
        bb = np.minimum(bf[idx], np.float32(1 - 1e-5))
        sc_ = bb / np.maximum(bf[idx], 1e-9)
        uu = uf[idx] * sc_; vv = vf[idx] * sc_
        zg = np.sqrt(np.maximum(1 - bb * bb, 0)).astype(np.float32)
        s0 = -np.sqrt(np.maximum(np.float32(m.Rt ** 2) - bb * bb, 0)).astype(np.float32)
        s1 = -zg
        Lin, Tv = m.march(uu, vv, s0, s1, L, steps, True, cancel)
        C = np.clip(sphere_ground(tex, gx, gy, k, uu, vv, zg, tilt, vlat, vlon, L), 0, 1)
        E = Tv
        avg = E.mean(1, keepdims=True)
        E = np.float32(pt['extinctionTint']) * E + np.float32(1 - pt['extinctionTint']) * avg
        E = np.maximum(0, np.float32(1 - pt['extinctionThickness']) + np.float32(pt['extinctionThickness']) * E)
        S = scatterer_hdr(Lin * sun, pt['scatteringExposure'])
        CE = C * E
        flat[idx] += (CE + S * (1 - CE)) * covf[idx][:, None]
    for c0 in range(0, len(si), chunk):
        idx = si[c0:c0 + chunk]
        bb = np.maximum(bf[idx], np.float32(max(1.0, m.Rg) + 1e-6))
        sc_ = bb / np.maximum(bf[idx], 1e-9)
        uu = uf[idx] * sc_; vv = vf[idx] * sc_
        sm = np.sqrt(np.maximum(np.float32(m.Rt ** 2) - bb * bb, 0)).astype(np.float32)
        z0 = np.zeros_like(sm)
        La, Ta = m.march(uu, vv, -sm, z0, L, steps, True, cancel)
        Lb, Tb = m.march(uu, vv, z0, sm, L, steps, False, cancel)
        Lin = La + Ta * Lb
        S = scatterer_hdr(Lin * sun, pt['skyExposure']) * np.float32(pt['skyAlpha'])
        flat[idx] += S * (1 - covf[idx])[:, None]
    if bg is not None:
        out += np.array(bg, np.float32)[None, None, :] / np.float32(255) * (1 - cov)[..., None]
    img = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def cfg_num(v):
    v = float('%.7g' % float(v))
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return np.format_float_positional(np.float64(v), trim='-')


def cfg_vec(v):
    return ','.join(cfg_num(x) for x in v)


def cfg_val(v):
    if isinstance(v, bool):
        return 'True' if v else 'False'
    if isinstance(v, (list, tuple)):
        return cfg_vec(v)
    return cfg_num(v)


def atmo_cfg(P, name=None):
    e = atmo_entry(P.get('atmosphere'))
    name = name or P['name']
    out = ['Scatterer_atmosphere', '{', '\tAtmo', '\t{', '\t\tname = %s' % name]
    for k in ATMO_VALUES:
        out.append('\t\t%s = %s' % (k, cfg_val(e[k])))
    for k, v in e['extra']:
        out.append('\t\t%s = %s' % (k, v))
    out += ['\t\tconfigPoints', '\t\t{']
    for p in e['configPoints']:
        out += ['\t\t\tItem', '\t\t\t{'] + ['\t\t\t\t%s = %s' % (k, cfg_num(p[k])) for k in ATMO_POINT_KEYS] + ['\t\t\t}']
    out += ['\t\t}', '\t}', '}']
    return '\n'.join(out) + '\n'


def atmo_casters(e):
    return [c.strip() for c in str(e.get('eclipse_casters') or '').replace(';', ',').split(',') if c.strip()]


def atmo_planets(P, name=None):
    e = atmo_entry(P.get('atmosphere'))
    name = name or P['name']
    t = '\t\t\t'
    out = ['@Scatterer_planetsList:AFTER[Kopernicus]', '{', '\t@scattererCelestialBodies', '\t{', '\t\tItem', '\t\t{',
           t + 'celestialBodyName = ' + name, t + 'transformName = ' + name,
           t + 'loadDistance = 300000000', t + 'unloadDistance = 500000000', t + 'hasOcean = False',
           t + 'flatScaledSpaceModel = ' + cfg_val(bool(e['flat_model'])),
           t + 'usesCloudIntegration = ' + cfg_val(bool(e['cloud_integration'])),
           t + 'mainSunCelestialBody = ' + (str(e['sun']).strip() or 'Sun')]
    if list(e['sun_color']) != [255, 255, 255]:
        out.append(t + 'sunColor = %s,1' % cfg_vec([round(c / 255.0, 3) for c in e['sun_color']]))
    out.append(t + 'sunsUseIntensityCurves = False')
    cs = atmo_casters(e)
    if cs:
        out += [t + 'eclipseCasters', t + '{'] + [t + '\tItem = ' + c for c in cs] + [t + '}']
    out += ['\t\t}', '\t}', '}']
    return '\n'.join(out) + '\n'


def parse_cfg(text):
    root = {'name': '', 'values': [], 'nodes': []}
    stack = [root]
    pending = ''
    for raw in text.replace('﻿', '').splitlines():
        line = raw.split('//', 1)[0].strip()
        while line:
            if line[0] == '{':
                node = {'name': pending, 'values': [], 'nodes': []}
                stack[-1]['nodes'].append(node)
                stack.append(node)
                pending = ''
                line = line[1:].strip()
                continue
            if line[0] == '}':
                if len(stack) > 1:
                    stack.pop()
                pending = ''
                line = line[1:].strip()
                continue
            cut = [i for i in (line.find('{'), line.find('}')) if i >= 0]
            seg, line = (line[:min(cut)], line[min(cut):]) if cut else (line, '')
            seg = seg.strip()
            if '=' in seg:
                k, v = seg.split('=', 1)
                stack[-1]['values'].append((k.strip(), v.strip()))
                pending = ''
            elif seg:
                pending = seg
    return root


def cfg_base(name):
    n = name.lstrip('@!%+-').split(':')[0]
    return n.split('[')[0].strip()


def cfg_get(node, key, default=None):
    for k, v in node['values']:
        if k == key:
            return v
    return default


def cfg_walk(node, name):
    for n in node['nodes']:
        if cfg_base(n['name']) == name:
            yield n
        for x in cfg_walk(n, name):
            yield x


def cfg_bool(v, default):
    if v is None:
        return default
    return str(v).strip().lower() in ('true', '1', 'yes')


def atmo_from_cfg(text, body=None):
    root = parse_cfg(text)
    atmos = list(cfg_walk(root, 'Atmo'))
    if not atmos:
        return None, None
    pick = next((a for a in atmos if body and cfg_get(a, 'name') == body), atmos[0])
    e = copy.deepcopy(ATMO)
    extra = []
    for k, v in pick['values']:
        if k == 'name':
            continue
        if k in ('m_betaR', 'BETA_MSca', 'ozoneAbsorption'):
            e[k] = vec3(v, ATMO[k])
        elif k in ('useOzone', 'multipleScattering'):
            e[k] = cfg_bool(v, ATMO[k])
        elif k in ATMO_VALUES:
            try:
                e[k] = float(v)
            except ValueError:
                pass
        else:
            extra.append([k, v])
    e['extra'] = extra
    pts = []
    for cp in cfg_walk(pick, 'configPoints'):
        for it in cfg_walk(cp, 'Item'):
            q = dict(ATMO_POINT)
            for k, v in it['values']:
                if k in q:
                    try:
                        q[k] = float(v)
                    except ValueError:
                        pass
            pts.append(q)
        break
    if pts:
        e['configPoints'] = pts
    return e, cfg_get(pick, 'name')


def planets_item(text, body):
    root = parse_cfg(text)
    for it in cfg_walk(root, 'Item'):
        if cfg_get(it, 'celestialBodyName') == body:
            d = {'sun': cfg_get(it, 'mainSunCelestialBody', 'Sun'),
                 'cloud_integration': cfg_bool(cfg_get(it, 'usesCloudIntegration'), True),
                 'flat_model': cfg_bool(cfg_get(it, 'flatScaledSpaceModel'), True)}
            sc = cfg_get(it, 'sunColor')
            if sc:
                c = vec3(sc, [1, 1, 1])
                d['sun_color'] = [int(round(min(1.0, max(0.0, x)) * 255)) for x in c]
            ec = [v for n in cfg_walk(it, 'eclipseCasters') for k, v in n['values'] if k == 'Item']
            d['eclipse_casters'] = ', '.join(ec)
            return d
    return None


def cfg_files(folder, needle=None, limit=4000):
    out = []
    for dp, dn, fn in os.walk(folder):
        dn[:] = [d for d in dn if d.lower() not in ('plugindata', 'cache', 'textures', 'models')]
        for f in fn:
            if f.lower().endswith('.cfg'):
                p = os.path.join(dp, f)
                try:
                    with open(p, encoding='utf-8', errors='replace') as fh:
                        t = fh.read()
                except OSError:
                    continue
                if needle is None or needle in t:
                    out.append((p, t))
                if len(out) >= limit:
                    return out
    return out


def scatterer_dir(mod):
    if not mod:
        return ''
    for n in os.listdir(mod) if os.path.isdir(mod) else []:
        if n.lower() == 'scatterer' and os.path.isdir(os.path.join(mod, n)):
            return os.path.join(mod, n)
    return ''


def find_atmo_cfg(body, mod=None):
    mod = mod if mod is not None else game_mod_dir()
    sd = scatterer_dir(mod)
    if not sd:
        return ''
    p = os.path.join(sd, 'Planets', body, 'atmo.cfg')
    if os.path.isfile(p):
        return p
    for path, t in cfg_files(sd, body):
        if 'Scatterer_atmosphere' in t:
            e, nm = atmo_from_cfg(t, body)
            if e is not None and nm == body:
                return path
    return ''


def find_planets_item(body, folder):
    for path, t in cfg_files(folder, body):
        if 'scattererCelestialBodies' in t:
            d = planets_item(t, body)
            if d:
                return d, path
    return None, ''


def colour_from_beta(b):
    b = np.maximum(np.array(b, np.float64), 0)
    if b.max() <= 0:
        return [255, 255, 255]
    c = (b / b.max()) ** (1 / 2.2)
    return [int(round(x * 255)) for x in c]


def beta_from_colour(rgb, old):
    c = np.maximum(np.array(rgb, np.float64) / 255.0, 0.004) ** 2.2
    mag = max(float(np.linalg.norm(old)), 1e-5)
    b = c / np.linalg.norm(c) * mag
    return [float('%.6g' % x) for x in b]


def planet_tint(P, col=None):
    if col is not None:
        a = np.asarray(col)[::4, ::4].astype(np.float64)
        w = np.cos(row_lat(a.shape[0], 0, a.shape[0]))
        m = (a * w[:, None, None]).sum((0, 1)) / max(w.sum() * a.shape[1], 1e-9)
    else:
        m = np.mean([s[1] for s in P['colors']['stops']], axis=0)
    grey = m.mean()
    m = grey + (m - grey) * 1.6
    return [int(round(min(255, max(0, x)))) for x in m]


def atmo_texture(col, hm, P, size=2048):
    H, W = hm.shape
    f = max(1, W // size)
    if f > 1:
        hm = hm[:H - H % f, :W - W % f].reshape(H // f, f, W // f, f).mean((1, 3))
        col = np.asarray(Image.fromarray(col).resize((W // f, H // f), Image.LANCZOS))
    gx, gy = slopes(hm, float(P['radius']), 0.5)
    if P['shape']['ocean']:
        wet = hm < 0
        gx = np.where(wet, 0, gx); gy = np.where(wet, 0, gy)
    return col.astype(np.float32) / 255, gx.astype(np.float32), gy.astype(np.float32)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def height_grey(hm, lo=None, hi=None):
    lo = float(hm.min()) if lo is None else lo
    hi = float(hm.max()) if hi is None else hi
    g = (hm - lo) / max(hi - lo, 1e-6)
    return Image.fromarray(np.clip(g * 255 + 0.5, 0, 255).astype(np.uint8))


def write_preview(P, col, hm, path):
    H, W = hm.shape
    if W > 4096:
        f = W // 4096
        hm = hm.reshape(H // f, f, W // f, f).mean((1, 3))
        col = np.asarray(Image.fromarray(col).resize((4096, 2048), Image.LANCZOS))
        H, W = hm.shape
    gx, gy = slopes(hm, float(P['radius']), 0.5)
    ocean = (hm < 0).astype(np.float32) if P['shape']['ocean'] else None
    if ocean is not None:
        gx = gx * (1 - ocean); gy = gy * (1 - ocean)
    k = float(P['normal_strength'])
    pv = P['preview']
    sheet = Image.new('RGB', (2400, 1200), (13, 15, 20))
    if has_atmo(P):
        t2, gx2, gy2 = atmo_texture(col, hm, P)
        sheet.paste(render_atmo(P, t2, gx2, gy2, view='planet', w=800, h=800, steps=24, bg=(13, 15, 20)), (0, 0))
    else:
        sheet.paste(render_globe(col, gx, gy, 800, pv['tilt'], pv['view_lat'], pv['view_lon'], k, ocean=ocean), (0, 0))
    sh = np.clip(col.astype(np.float32) * shade_map(gx, gy, k)[..., None], 0, 255).astype(np.uint8)
    sheet.paste(Image.fromarray(sh).resize((1600, 800), Image.LANCZOS), (800, 0))
    sheet.paste(render_globe(col, gx, gy, 400, 0, 72, pv['view_lon'], k, ocean=ocean), (0, 800))
    sheet.paste(render_globe(col, gx, gy, 400, 0, -72, pv['view_lon'], k, ocean=ocean), (400, 800))
    sheet.paste(height_grey(hm).resize((800, 400), Image.LANCZOS), (800, 800))
    s = W / 4096.0
    crop = Image.fromarray(sh).crop((int(1650 * s), int(800 * s), int(2450 * s), int(1200 * s))).resize((800, 400), Image.LANCZOS)
    sheet.paste(crop, (1600, 800))
    d = ImageDraw.Draw(sheet)
    f = font(15)
    d.text((808, 806), 'height %.0f m to %.0f m' % (float(hm.min()), float(hm.max())), fill=(230, 235, 245), font=f)
    sheet.save(path)


def out_dir(P, res):
    d = os.path.join(OUTROOT, P['name'] if res == 4096 else '%s_%d' % (P['name'], res))
    os.makedirs(d, exist_ok=True)
    return d


def save_height16(hm, path):
    lo, hi = float(hm.min()), float(hm.max())
    g = np.clip(np.rint((hm - lo) / max(hi - lo, 1e-6) * 65535), 0, 65535).astype(np.uint16)
    Image.fromarray(g).save(path)
    return lo, hi


def load_height(src_dir, name):
    with open(os.path.join(src_dir, name + '_info.json')) as f:
        info = json.load(f)
    g = np.asarray(Image.open(os.path.join(src_dir, name + '_height.png'))).astype(np.float32)
    lo, hi = float(info['min_m']), float(info['max_m'])
    return lo + g / 65535.0 * (hi - lo), info


def dxt_bytes(im, fmt):
    b = io.BytesIO(); im.save(b, 'DDS', pixel_format=fmt); return b.getvalue()


def save_mips(im, path, fmt):
    lv = []; cur = im
    while True:
        lv.append(dxt_bytes(cur, fmt))
        if cur.size == (1, 1): break
        cur = cur.resize((max(1, cur.size[0] // 2), max(1, cur.size[1] // 2)), Image.BOX)
    hd = bytearray(lv[0][:128])
    fl = struct.unpack_from('<I', hd, 8)[0] | 0x20000 | 0x80000
    struct.pack_into('<I', hd, 8, fl); struct.pack_into('<I', hd, 20, len(lv[0]) - 128); struct.pack_into('<I', hd, 28, len(lv))
    struct.pack_into('<I', hd, 108, 0x401008)
    with open(path, 'wb') as f:
        f.write(bytes(hd) + b''.join(x[128:] for x in lv))


def bc_blocks(a):
    if a.ndim == 2:
        a = a[..., None]
    H, W, C = a.shape
    ph, pw = (-H) % 4, (-W) % 4
    if ph or pw:
        a = np.pad(a, ((0, ph), (0, pw), (0, 0)), mode='edge')
        H, W = a.shape[:2]
    return a.reshape(H // 4, 4, W // 4, 4, C).transpose(0, 2, 1, 3, 4).reshape(-1, 16, C)


def bc4_encode(ch):
    v = bc_blocks(ch)[..., 0].astype(np.int32)
    hi = v.max(1); lo = v.min(1)
    rng = np.maximum(hi - lo, 1)
    k = np.clip(np.rint((hi[:, None] - v) * 7.0 / rng[:, None]), 0, 7).astype(np.uint64)
    code = np.where(k == 0, 0, np.where(k == 7, 1, k + 1)).astype(np.uint64)
    code[hi == lo] = 0
    bits = np.zeros(len(v), np.uint64)
    for i in range(16):
        bits |= code[:, i] << np.uint64(3 * i)
    out = np.zeros((len(v), 8), np.uint8)
    out[:, 0] = hi; out[:, 1] = lo
    for j in range(6):
        out[:, 2 + j] = ((bits >> np.uint64(8 * j)) & np.uint64(255)).astype(np.uint8)
    return out


def bc5_encode(r, g):
    return np.concatenate([bc4_encode(r), bc4_encode(g)], 1).tobytes()


BC7_W = np.array([0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64], np.float32)


def bc7_chunk(px):
    n = len(px)
    mean = px.mean(1)
    d = px - mean[:, None]
    ax = d.max(1) - d.min(1) + 1e-3
    for _ in range(4):
        ax = np.einsum('nki,nk->ni', d, np.einsum('nkj,nj->nk', d, ax))
        ax /= np.maximum(np.linalg.norm(ax, axis=1, keepdims=True), 1e-6)
    t = np.einsum('nki,ni->nk', d, ax)
    e0 = np.clip(mean + t.min(1)[:, None] * ax, 0, 255)
    e1 = np.clip(mean + t.max(1)[:, None] * ax, 0, 255)

    def quant(e):
        res = None
        for p in (0, 1):
            q = np.clip(np.rint((e - p) / 2.0), 0, 127)
            err = ((q * 2 + p - e) ** 2).sum(1)
            if res is None:
                res = [q, np.full(len(e), p), err]
            else:
                m = err < res[2]
                res = [np.where(m[:, None], q, res[0]), np.where(m, p, res[1]), np.where(m, err, res[2])]
        return res[0].astype(np.int64), res[1].astype(np.int64)
    q0, p0 = quant(e0)
    q1, p1 = quant(e1)
    E0 = (q0 * 2 + p0[:, None]).astype(np.float32)
    E1 = (q1 * 2 + p1[:, None]).astype(np.float32)
    best = None; idx = None
    for k in range(16):
        col = np.floor(((64 - BC7_W[k]) * E0 + BC7_W[k] * E1 + 32) / 64)
        err = ((px - col[:, None, :]) ** 2).sum(2)
        if best is None:
            best, idx = err, np.zeros(err.shape, np.int64)
        else:
            m = err < best
            best = np.where(m, err, best); idx = np.where(m, k, idx)
    sw = idx[:, 0] >= 8
    q0s = np.where(sw[:, None], q1, q0); q1s = np.where(sw[:, None], q0, q1)
    p0s = np.where(sw, p1, p0); p1s = np.where(sw, p0, p1)
    idx = np.where(sw[:, None], 15 - idx, idx)
    Uu = np.uint64
    lo = np.full(n, 0x40, np.uint64)
    sh = 7
    for c in range(4):
        lo |= q0s[:, c].astype(Uu) << Uu(sh); sh += 7
        lo |= q1s[:, c].astype(Uu) << Uu(sh); sh += 7
    lo |= p0s.astype(Uu) << Uu(63)
    hi = p1s.astype(Uu) | (idx[:, 0].astype(Uu) << Uu(1))
    for i in range(1, 16):
        hi |= idx[:, i].astype(Uu) << Uu(4 + 4 * (i - 1))
    return np.stack([lo, hi], 1).astype('<u8').tobytes()


def bc7_encode(rgba, chunk=131072):
    px = bc_blocks(rgba)
    return b''.join(bc7_chunk(px[i:i + chunk].astype(np.float32)) for i in range(0, len(px), chunk))


def dds_header(w, h, mips, top_size, fourcc=b'DX10', dxgi=None):
    hd = bytearray(128)
    hd[0:4] = b'DDS '
    struct.pack_into('<7I', hd, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000, h, w, top_size, 0, mips)
    struct.pack_into('<2I', hd, 76, 32, 0x4)
    hd[84:88] = fourcc
    struct.pack_into('<I', hd, 108, 0x401008)
    if fourcc == b'DX10':
        hd += struct.pack('<5I', dxgi, 3, 0, 1, 0)
    return bytes(hd)


def save_bc(arr, path, kind):
    levels = []
    cur = Image.fromarray(arr)
    while True:
        a = np.asarray(cur)
        if kind == 'BC7':
            if a.shape[-1] == 3:
                a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, np.uint8)], 2)
            levels.append(bc7_encode(a))
        else:
            levels.append(bc5_encode(a[..., 0], a[..., 1]))
        if cur.size == (1, 1):
            break
        cur = cur.resize((max(1, cur.size[0] // 2), max(1, cur.size[1] // 2)), Image.BOX)
    w, h = arr.shape[1], arr.shape[0]
    with open(path, 'wb') as f:
        f.write(dds_header(w, h, len(levels), len(levels[0]), b'DX10', 98 if kind == 'BC7' else 83) + b''.join(levels))


def save_colour_dds(c, path, fmt, flip=True):
    a = np.ascontiguousarray(c[::-1] if flip else c)
    if fmt == 'BC7':
        save_bc(a, path, 'BC7')
    elif fmt == 'DXT5':
        rgba = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, np.uint8)], 2)
        save_mips(Image.fromarray(rgba, 'RGBA'), path, 'DXT5')
    else:
        save_mips(Image.fromarray(a, 'RGB'), path, 'DXT1')


def save_l8_dds(g, path, flip=True):
    a = np.ascontiguousarray(g[::-1] if flip else g).astype(np.uint8)
    h, w = a.shape
    hd = bytearray(128)
    hd[0:4] = b'DDS '
    struct.pack_into('<7I', hd, 4, 124, 0x100F, h, w, w, 0, 0)
    struct.pack_into('<8I', hd, 76, 32, 0x20000, 0, 8, 255, 0, 0, 0)
    struct.pack_into('<I', hd, 108, 0x1000)
    with open(path, 'wb') as f:
        f.write(bytes(hd) + a.tobytes())


def split_height(hm):
    lo, hi = float(hm.min()), float(hm.max())
    t = (hm.astype(np.float64) - lo) / max(hi - lo, 1e-9) * 255.0
    coarse = np.clip(np.floor(t), 0, 255)
    fine = np.clip(np.rint((t - coarse) * 255.0), 0, 255)
    return coarse.astype(np.uint8), fine.astype(np.uint8), lo, hi


DDS_BC1 = 'DDS BC1 / DXT1 (KSP default)'
DDS_BC3 = 'DDS BC3 / DXT5 (with alpha)'
DDS_BC7 = 'DDS BC7 (best quality)'
DDS_NM = 'DDS DXT5nm (KSP default)'
DDS_BC5 = 'DDS BC5 (two-channel)'
DDS_L8 = 'DDS L8 (KSP default)'
PNG16 = 'PNG 16-bit'
PNG8 = 'PNG 8-bit'
CFG = 'Kopernicus .cfg'
ATMO_CFG = 'Scatterer cfg'
DDS_CODEC = {DDS_BC1: 'DXT1', DDS_BC3: 'DXT5', DDS_BC7: 'BC7'}
EXPORT_FORMATS = {
    'height': [DDS_L8, PNG16, PNG8],
    'heightfine': [DDS_L8, PNG8],
    'color': [DDS_BC1, DDS_BC3, DDS_BC7, 'PNG', 'JPG', 'TGA', 'BMP'],
    'normal': [DDS_NM, DDS_BC5, 'PNG'],
    'preview': ['PNG', 'JPG'],
    'config': [CFG],
    'atmo': [ATMO_CFG],
}
FMT_EXT = {DDS_BC1: '.dds', DDS_BC3: '.dds', DDS_BC7: '.dds', DDS_NM: '.dds', DDS_BC5: '.dds', DDS_L8: '.dds',
           PNG16: '.png', PNG8: '.png', 'PNG': '.png', 'JPG': '.jpg', 'TGA': '.tga', 'BMP': '.bmp', CFG: '.cfg', ATMO_CFG: '.cfg'}
PIL_FMT = {'PNG': 'PNG', 'JPG': 'JPEG', 'TGA': 'TGA', 'BMP': 'BMP'}


def export_target(folder, base, fmt):
    return os.path.join(folder, base + FMT_EXT[fmt])


def planets_file(folder, name):
    return os.path.join(folder, 'planetsList_%s.cfg' % name)


def resize_height(hm, size):
    H, W = hm.shape
    if not size or size == W:
        return hm
    return np.asarray(Image.fromarray(hm.astype(np.float32), 'F').resize((size, size // 2), Image.LANCZOS if size < W else Image.BICUBIC))


def default_cfg_path(folder):
    rel = gamedata_rel(folder)
    if not rel:
        td = texture_dir()
        rel = gamedata_rel(td) if td else ''
    return rel or 'MyMod/Textures'


def tex_path(folder, fname, base=None):
    rel = default_cfg_path(folder) if base is None else base.strip().replace('\\', '/').strip('/')
    return (rel + '/' if rel else '') + fname


def kopernicus_snippet(P, info, files, folder, base=None):
    def col(c):
        return '%.3f,%.3f,%.3f,1' % tuple(v / 255.0 for v in c)
    t = '\t'
    L = []
    mods = []
    if files.get('height'):
        mods += [t * 2 + 'VertexHeightMap', t * 2 + '{',
                 t * 3 + 'map = ' + tex_path(folder, files['height'], base),
                 t * 3 + 'offset = %.1f' % info['min_m'],
                 t * 3 + 'deformity = %.1f' % (info['max_m'] - info['min_m']),
                 t * 3 + 'scaleDeformityByRadius = false',
                 t * 3 + 'order = 20',
                 t * 3 + 'enabled = true',
                 t * 2 + '}']
    if files.get('heightfine'):
        mods += [t * 2 + 'VertexHeightMap', t * 2 + '{',
                 t * 3 + 'map = ' + tex_path(folder, files['heightfine'], base),
                 t * 3 + 'offset = 0',
                 t * 3 + 'deformity = %.2f' % ((info['max_m'] - info['min_m']) / 255.0),
                 t * 3 + 'scaleDeformityByRadius = false',
                 t * 3 + 'order = 21',
                 t * 3 + 'enabled = true',
                 t * 2 + '}']
    if files.get('color'):
        mods += [t * 2 + 'VertexColorMap', t * 2 + '{',
                 t * 3 + 'map = ' + tex_path(folder, files['color'], base),
                 t * 3 + 'order = 9999993',
                 t * 3 + 'enabled = true',
                 t * 2 + '}']
    if mods:
        L += ['PQS', '{', t + 'Mods', t + '{'] + mods + [t + '}', '}']
    if files.get('color') or files.get('normal'):
        L += ['ScaledVersion', '{', t + 'Material', t + '{']
        if files.get('color'):
            L.append(t * 2 + 'texture = ' + tex_path(folder, files['color'], base))
        if files.get('normal'):
            L.append(t * 2 + 'normals = ' + tex_path(folder, files['normal'], base))
        L += [t + '}', '}']
    if P['shape']['ocean']:
        C = P['colors']
        L += ['Ocean', '{', t + 'ocean = true', t + 'density = 1', t + 'oceanColor = ' + col(C['deep']), '',
              t + 'Material', t + '{', t * 2 + 'color = ' + col(C['shallow']), t * 2 + 'colorFromSpace = ' + col(C['deep']), t + '}', '',
              t + 'Fog', t + '{', t * 2 + 'fogColorStart = ' + col(C['shallow']), t * 2 + 'fogColorEnd = ' + col(C['deep']), t + '}', '}']
    return '\n'.join(L) + '\n'


def export_maps(src_dir, name, P, jobs, folder, size=None, flip=True, log=print, cfg_path=None):
    os.makedirs(folder, exist_ok=True)
    hm, info = load_height(src_dir, name)
    hm = resize_height(hm, size)
    c = None
    written = []
    names = {}
    for kind, base, fmt in jobs:
        names[kind] = base + FMT_EXT[fmt]
    fine = None
    for kind, base, fmt in jobs:
        path = export_target(folder, base, fmt)
        if kind in ('height', 'heightfine'):
            if fine is None:
                co, fi, lo, hi = split_height(hm)
                fine = (co, fi)
                info = dict(info, min_m=lo, max_m=hi)
            g = fine[0] if kind == 'height' else fine[1]
            if fmt == DDS_L8:
                save_l8_dds(g, path, flip)
            elif fmt == PNG16 and kind == 'height':
                lo, hi = info['min_m'], info['max_m']
                g16 = np.clip(np.rint((hm - lo) / max(hi - lo, 1e-6) * 65535), 0, 65535).astype(np.uint16)
                Image.fromarray(g16).save(path)
            else:
                Image.fromarray(g).save(path, 'PNG')
        elif kind == 'color':
            if c is None:
                c = np.asarray(Image.open(os.path.join(src_dir, name + '_color.png')).convert('RGB'))
                if size and size != c.shape[1]:
                    c = np.asarray(Image.fromarray(c).resize((size, size // 2), Image.LANCZOS))
            if fmt.startswith('DDS'):
                save_colour_dds(c, path, DDS_CODEC.get(fmt, 'DXT1'), flip)
            elif fmt == 'JPG':
                Image.fromarray(c).save(path, 'JPEG', quality=95)
            else:
                Image.fromarray(c).save(path, PIL_FMT[fmt])
        elif kind == 'normal':
            G, A = normal_rgba(hm, float(info.get('radius', P['radius'])), float(P['normal_strength']), bool(info.get('ocean', P['shape']['ocean'])), flip=True)
            if fmt == DDS_BC5:
                rg = np.stack([A, G, np.zeros_like(G)], -1)
                if not flip:
                    rg = np.ascontiguousarray(rg[::-1])
                save_bc(rg, path, 'BC5')
            elif fmt.startswith('DDS'):
                rgba = np.stack([G, G, G, A], -1)
                if not flip:
                    rgba = np.ascontiguousarray(rgba[::-1])
                save_mips(Image.fromarray(rgba, 'RGBA'), path, 'DXT5')
            else:
                g8 = G[::-1].astype(np.float32); a8 = A[::-1].astype(np.float32)
                x = (a8 - 128) / 127.0; y = (g8 - 128) / 127.0
                zz = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
                rgb = np.stack([a8, g8, 128 + 127 * zz], -1).clip(0, 255).astype(np.uint8)
                Image.fromarray(rgb).save(path, 'PNG')
        elif kind == 'preview':
            pp = os.path.join(src_dir, name + '_preview.png')
            if not os.path.isfile(pp):
                log('no preview in this build - skipped')
                continue
            im = Image.open(pp).convert('RGB')
            if fmt == 'JPG':
                im.save(path, 'JPEG', quality=92)
            else:
                im.save(path, 'PNG')
        elif kind == 'atmo':
            if not has_atmo(P):
                log('no atmosphere on this planet - skipped')
                continue
            with open(path, 'w', newline='\n') as f:
                f.write(atmo_cfg(P, name))
            pl = planets_file(folder, name)
            with open(pl, 'w', newline='\n') as f:
                f.write(atmo_planets(P, name))
            written.append(pl)
            log('exported ' + pl)
        elif kind == 'config':
            if fine is None:
                lo, hi = float(hm.min()), float(hm.max())
                info = dict(info, min_m=lo, max_m=hi)
            files = {k: names[k] for k in ('height', 'heightfine', 'color', 'normal') if k in names and names[k].lower().endswith('.dds')}
            with open(path, 'w', newline='\n') as f:
                f.write(kopernicus_snippet(P, info, files, folder, cfg_path))
        written.append(path)
        log('exported ' + path)
    return written


def preset_path(p):
    if os.path.isfile(p):
        return p
    q = os.path.join(PRESETS, p if p.endswith('.json') else p + '.json')
    if os.path.isfile(q):
        return q
    sys.exit('preset not found: ' + p)


def load_preset(p):
    with open(preset_path(p)) as f:
        raw = json.load(f)
    if 'name' not in raw:
        raw['name'] = os.path.splitext(os.path.basename(p))[0]
    return normalize(raw)


def live_maps(P, W, cache, cancel=None, workers=2):
    hk = height_key(P)
    tk = ('T', hk)
    T = cache.get(tk)
    if T is None:
        if len([k for k in cache if k[0] == 'T']) > 4:
            for k in [k for k in cache if k[0] in ('T', 'H')]:
                del cache[k]
        T = Terrain(P)
        cache[tk] = T
    if cancel:
        cancel()
    key = ('H', hk, W)
    got = cache.get(key)
    if got is None:
        hm, mk = make_height(P, W, T, crater_list(P), cancel, workers=workers)
        cache[key] = got = (hm, mk)
    hm, mk = got
    nc = cache.setdefault(('N', W), {})
    if len(nc) > 64:
        nc.clear()
    col, gx, gy = make_colour(P, hm, mk, W, cancel, workers=workers, noise_cache=nc)
    return col, hm, gx, gy


def cmd_make(a):
    t0 = time.time()
    P = load_preset(a.preset)
    W = int(a.res)
    H = W // 2
    od = out_dir(P, W)
    print('%s %s - %s at %d x %d' % (APP_NAME, APP_VERSION, P['name'], W, H), flush=True)
    T = Terrain(P)
    CR = crater_list(P)
    if CR is not None:
        print('craters: %d' % len(CR['D']), flush=True)
    last = [-1]

    def prog(label):
        def f(i, n):
            p = int(100 * i / n)
            if p != last[0]:
                last[0] = p
                print('%s %d%%' % (label, p), flush=True)
        return f
    hm, mk = make_height(P, W, T, CR, progress=prog('height'))
    last[0] = -1
    col, gx, gy = make_colour(P, hm, mk, W, progress=prog('color'))
    print('color done', flush=True)
    lo, hi = save_height16(hm, os.path.join(od, P['name'] + '_height.png'))
    Image.fromarray(col).save(os.path.join(od, P['name'] + '_color.png'))
    info = {'min_m': lo, 'max_m': hi, 'radius': P['radius'], 'ocean': P['shape']['ocean'], 'res': W, 'version': APP_VERSION}
    with open(os.path.join(od, P['name'] + '_info.json'), 'w') as f:
        json.dump(info, f, indent=1)
    with open(os.path.join(od, P['name'] + '_preset.json'), 'w') as f:
        json.dump(P, f, indent=1)
    print('height range: %.0f m to %.0f m' % (lo, hi), flush=True)
    print('files done', flush=True)
    write_preview(P, col, hm, os.path.join(od, P['name'] + '_preview.png'))
    print('preview done', flush=True)
    print('DONE in %.0f s -> %s' % (time.time() - t0, od), flush=True)


def cmd_export(a):
    P = load_preset(a.preset)
    W = int(a.res)
    src = os.path.join(OUTROOT, P['name'] if W == 4096 else '%s_%d' % (P['name'], W))
    if not os.path.isfile(os.path.join(src, P['name'] + '_height.png')):
        sys.exit('no build at %d - run make first' % W)
    jobs = []
    stem = lambda k: os.path.splitext(os.path.basename(P['files'].get(k) or '%s_%s' % (P['name'], k)))[0]
    if a.height != 'none':
        jobs.append(('height', stem('height'), {'dds': DDS_L8, 'png': PNG16, 'png8': PNG8}[a.height]))
    if a.fine != 'none':
        jobs.append(('heightfine', stem('height') + 'fine', {'dds': DDS_L8, 'png': PNG8}[a.fine]))
    if a.color != 'none':
        jobs.append(('color', stem('color'), {'dds': DDS_BC1, 'bc1': DDS_BC1, 'bc3': DDS_BC3, 'bc7': DDS_BC7, 'png': 'PNG', 'jpg': 'JPG', 'tga': 'TGA', 'bmp': 'BMP'}[a.color]))
    if a.normal != 'none':
        jobs.append(('normal', stem('normal'), {'dds': DDS_NM, 'bc5': DDS_BC5, 'png': 'PNG'}[a.normal]))
    if a.preview != 'none':
        jobs.append(('preview', P['name'] + '_preview', {'png': 'PNG', 'jpg': 'JPG'}[a.preview]))
    if a.atmo != 'none' and has_atmo(P):
        jobs.append(('atmo', P['name'] + '_atmo', ATMO_CFG))
    if a.config:
        jobs.append(('config', P['name'] + '_kopernicus', CFG))
    export_maps(src, P['name'], P, jobs, a.to, a.size, not a.no_flip, cfg_path=a.config_path)


def cmd_new(a):
    src = load_preset(a.template) if a.template else normalize({'name': a.name})
    P = copy.deepcopy(src)
    P['name'] = a.name
    P['seed'] = int(np.random.default_rng().integers(1, 99999))
    P['files'] = {'height': a.name + '_height.dds', 'color': a.name + '_color.dds', 'normal': a.name + '_normal.dds'}
    os.makedirs(PRESETS, exist_ok=True)
    path = os.path.join(PRESETS, a.name + '.json')
    if os.path.exists(path):
        sys.exit('%s already exists' % path)
    with open(path, 'w') as f:
        json.dump(normalize(P), f, indent=1)
    print('wrote ' + path)


def main():
    ap = argparse.ArgumentParser(prog='terrain')
    sp = ap.add_subparsers(dest='cmd', required=True)
    m = sp.add_parser('make')
    m.add_argument('preset')
    m.add_argument('--res', type=int, default=4096)
    e = sp.add_parser('export')
    e.add_argument('preset')
    e.add_argument('--to', required=True)
    e.add_argument('--res', type=int, default=4096)
    e.add_argument('--height', default='dds', choices=['dds', 'png', 'png8', 'none'])
    e.add_argument('--fine', default='dds', choices=['dds', 'png', 'none'])
    e.add_argument('--color', default='dds', choices=['dds', 'bc1', 'bc3', 'bc7', 'png', 'jpg', 'tga', 'bmp', 'none'])
    e.add_argument('--normal', default='dds', choices=['dds', 'bc5', 'png', 'none'])
    e.add_argument('--preview', default='none', choices=['png', 'jpg', 'none'])
    e.add_argument('--config', action='store_true')
    e.add_argument('--config-path', default=None, help='texture path under GameData written into the config')
    e.add_argument('--atmo', default='cfg', choices=['cfg', 'none'])
    e.add_argument('--size', type=int, default=None)
    e.add_argument('--no-flip', action='store_true')
    n = sp.add_parser('new')
    n.add_argument('name')
    n.add_argument('--template', default=None)
    a = ap.parse_args()
    {'make': cmd_make, 'export': cmd_export, 'new': cmd_new}[a.cmd](a)


if __name__ == '__main__':
    main()
