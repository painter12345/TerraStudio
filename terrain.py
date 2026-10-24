import sys, os, io, json, copy, time, math, struct, argparse, heapq
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None

APP_NAME = 'Terra Studio'
APP_VERSION = '0.1.17'
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
    'ridge': {'height': 0.0, 'width': 40.0, 'coverage': 360.0, 'lon': 180.0, 'lat': 0.0, 'tilt': 0.0,
              'segments': 0.0, 'ragged': 0.5, 'wander': 0.3, 'seed': 1},
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
    'rings': {'enabled': False},
    'normal_strength': 2.0,
    'files': {'height': '', 'color': '', 'normal': ''},
    'preview': {'tilt': 0, 'view_lat': 15, 'view_lon': 0},
}

HEIGHT_KEYS = ('seed', 'radius', 'shape', 'relief', 'craters', 'volcanoes', 'features', 'plateaus', 'water', 'cracks', 'ridge')
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
    rg = P['ridge']
    for k in ('height', 'width', 'coverage', 'lon', 'lat', 'tilt', 'segments', 'ragged', 'wander'):
        try:
            rg[k] = float(rg[k])
        except (TypeError, ValueError):
            rg[k] = float(DEFAULTS['ridge'][k])
    rg['height'] = max(0.0, rg['height'])
    rg['width'] = max(0.5, rg['width'])
    rg['coverage'] = max(5.0, min(360.0, rg['coverage']))
    rg['lon'] = rg['lon'] % 360.0
    rg['lat'] = max(-60.0, min(60.0, rg['lat']))
    rg['tilt'] = max(-60.0, min(60.0, rg['tilt']))
    for k in ('segments', 'ragged', 'wander'):
        rg[k] = max(0.0, min(1.0, rg[k]))
    try:
        rg['seed'] = int(rg.get('seed', 1))
    except (TypeError, ValueError):
        rg['seed'] = 1
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
    P['aurora'] = aurora_entry(P.get('aurora'))
    P['lava'] = lava_entry(P.get('lava'))
    P['clouds'] = cloud_entry(P.get('clouds'))
    P['lava_ocean'] = lava_ocean_entry(P.get('lava_ocean'))
    P['emission'] = emission_entry(P.get('emission'))
    P['rings'] = ring_entry(P.get('rings'))
    return P


def height_key(P):
    d = {k: P[k] for k in HEIGHT_KEYS}
    if has_lava(P):
        d['lava'] = lava_shape(P)
    if volcano_glow(P):
        d['vglow'] = round(float(P['emission']['flows']), 4)
    return json.dumps(d, sort_keys=True)


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


VOLCANO_FLOWS = [0.5]


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
        if mk.shape[0] > 9:
            gw = (1 - ss(rc * 0.45, rc * 1.0, r)) * np.float32(0.6 + 0.4 * caldera)
            fl = VOLCANO_FLOWS[0]
            if fl > 0:
                ax = np.array([0, 0, 1], np.float32) if abs(float(c[2])) < 0.9 else np.array([1, 0, 0], np.float32)
                e1 = np.cross(c, ax); e1 = e1 / np.linalg.norm(e1); e2 = np.cross(c, e1)
                th = np.arctan2(sx * e2[0] + sy * e2[1] + sz * e2[2], sx * e1[0] + sy * e1[1] + sz * e1[2])
                q3 = np.float32(4.0 / Ra)
                wig = perlin(sx * q3 + o[0] + 3.1, sy * q3 + o[1], sz * q3 + o[2], 5301 + nid) * np.float32(2.6)
                wig = wig + perlin(sx * q3 * 2.3 + o[1], sy * q3 * 2.3 + o[2], sz * q3 * 2.3 + o[0], 5302 + nid) * np.float32(0.9)
                k = 4 + nid % 4
                st = np.cos(th * np.float32(k) + np.float32(nid * 1.7) + wig)
                wd = np.float32(0.72) + np.float32(0.22) * np.clip(r / np.float32(0.7), 0, 1)
                ln = np.clip(np.float32(0.55) + np.float32(0.45) * perlin(np.cos(th * k) * 2 + o[1], np.sin(th * k) * 2 + o[2], o[0] + nid, 5303 + nid), 0, 1)
                end = ln * np.float32(0.5) + np.float32(0.2)
                ch = ss(wd, np.float32(0.995), st) * (1 - ss(end * np.float32(0.6), end, r)) * ss(np.float32(0.05), np.float32(0.16), r)
                gw = np.maximum(gw, ch * np.float32(fl) * (1 - np.float32(0.8) * np.clip(r / end, 0, 1)))
            mk[9][idx] = np.maximum(mk[9][idx], gw.astype(np.float16))


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


def ridge_setup(P):
    G = P.get('ridge') or {}
    if float(G.get('height', 0)) <= 0:
        return None
    Rk = float(P['radius']) / 1000.0
    c0 = lonlat_vec(0.0, float(G['lon'])).astype(np.float64)
    z = np.array([0.0, 0.0, 1.0])
    t = math.radians(float(G['tilt']))
    a = z * math.cos(t) + np.cross(c0, z) * math.sin(t)
    a /= np.linalg.norm(a)
    e2 = np.cross(a, c0)
    e2 /= np.linalg.norm(e2)
    return {'a': a.astype(np.float32), 'e1': c0.astype(np.float32), 'e2': e2.astype(np.float32),
            'hw': max(float(G['width']), 0.5) * 0.5 / Rk, 'off': math.radians(float(G['lat'])),
            'half': math.radians(float(G['coverage'])) * 0.5, 'h': float(G['height']),
            'seg': float(G['segments']), 'rag': float(G['ragged']), 'wan': float(G['wander']),
            'sd': int(G.get('seed', 1)) * 1000 + 701}


def ring_noise(ct, st, k, seed, octs=1, gain=0.5):
    s = np.zeros(ct.shape, np.float32)
    amp, tot = 1.0, 0.0
    for i in range(octs):
        f = np.float32(k * 2 ** i)
        o = OFF[(seed + i) % 32]
        s += np.float32(amp) * perlin(ct * f + o[0], st * f + o[1], np.full(ct.shape, o[2] + 0.37 * i, np.float32), seed * 131 + i)
        tot += amp
        amp *= gain
    return s * np.float32(1.6 / tot)


def apply_ridge(G, hm, X, Y, Z, W, fmax):
    px = 2 * math.pi / W
    hw = max(G['hw'], 1.5 * px)
    a, e1, e2 = G['a'], G['e1'], G['e2']
    sd, rag, wan = G['sd'], G['rag'], G['wan']
    s = np.clip(X * a[0] + Y * a[1] + Z * a[2], -1, 1)
    d0 = np.arcsin(s) - np.float32(G['off'])
    reach = np.float32(hw * (2.6 * 1.4 + 0.6 * rag) + wan * (2.0 * hw + 0.035) * 1.7 + 1.5 * px)
    near = np.abs(d0) < reach
    if not near.any():
        return
    idx = np.flatnonzero(near)
    x, y, zz = X.reshape(-1)[idx], Y.reshape(-1)[idx], Z.reshape(-1)[idx]
    d = d0.reshape(-1)[idx]
    th = np.arctan2(x * e2[0] + y * e2[1] + zz * e2[2], x * e1[0] + y * e1[1] + zz * e1[2])
    ct, st = np.cos(th).astype(np.float32), np.sin(th).astype(np.float32)
    if wan > 0:
        d = d - np.float32(wan * (2.0 * hw + 0.035)) * ring_noise(ct, st, 1.3, sd + 1, 3, 0.45)
    m = np.ones(d.shape, np.float32)
    if G['half'] < math.pi - 1e-4:
        half = G['half']
        tp = min(half, max(0.2, half * 0.35))
        e = np.abs(th) + np.float32(tp * 0.25) * ring_noise(ct, st, 4.0, sd + 2, 2)
        m *= 1 - ss(np.float32(half - tp), np.float32(half), e)
    if G['seg'] > 0:
        t0 = np.float32(-1.1 + 1.9 * G['seg'])
        sn = ring_noise(ct, st, 1.8, sd + 3, 2, 0.35)
        m *= ss(t0 - np.float32(0.45), t0 + np.float32(0.45), sn)
    env = np.float32(1.0) + np.float32(0.45 * rag) * ring_noise(ct, st, 3.0, sd + 4, 4, 0.55)
    wv = np.float32(1.0) + np.float32(0.3 * rag) * ring_noise(ct, st, 5.0, sd + 5, 2)
    hwv = np.float32(hw) * wv * np.sqrt(np.maximum(m, np.float32(0.0004)))
    m = m * m
    if rag > 0:
        f0 = min(0.9 / hw, fmax)
        d = d + np.float32(0.3 * rag * hw) * fbm(x, y, zz, f0, fmax, sd + 6, 0.5, 5)
    r = np.abs(d) / hwv
    prof = np.float32(0.6) * (1 - ss(np.float32(0), np.float32(1), r)) + np.float32(0.4) * (1 - ss(np.float32(0), np.float32(2.4), r))
    h = np.float32(G['h']) * prof * m * np.maximum(env, np.float32(0.15))
    if rag > 0:
        f1 = min(1.6 / hw, fmax)
        h = h * (np.float32(1.0) + np.float32(0.35 * rag) * fbm(x, y, zz, f1, fmax, sd + 7, 0.55, 6))
    hm.reshape(-1)[idx] += np.maximum(h, np.float32(0))


RING = {'enabled': False, 'inner': 1.35, 'outer': 2.3, 'angle': 0.0, 'opacity': 0.85, 'zones': 4, 'ringlets': 0.6,
        'detail': 1.0, 'edge': 0.3, 'variation': 0.4, 'gaps': [[0.62, 0.035, 1.0], [0.88, 0.008, 0.9]],
        'inner_color': None, 'middle_color': None, 'outer_color': None, 'size': 2048, 'pattern': 0, 'view': 18.0}


def ring_entry(r):
    e = copy.deepcopy(RING)
    e.update({k: copy.deepcopy(v) for k, v in (r if isinstance(r, dict) else {}).items() if k in RING})
    gaps = []
    for g in e['gaps'] or []:
        try:
            gaps.append([min(max(float(g[0]), 0.0), 1.0), min(max(float(g[1]), 0.0005), 0.5), min(max(float(g[2]), 0.0), 1.0)])
        except (TypeError, ValueError, IndexError):
            pass
    e['gaps'] = gaps
    e['enabled'] = bool(e['enabled'])
    e['inner'] = max(1.0, float(e['inner']))
    e['outer'] = max(e['inner'] + 0.05, float(e['outer']))
    try:
        e['size'] = int(e['size']) if int(e['size']) in (1024, 2048, 4096) else 2048
    except (TypeError, ValueError):
        e['size'] = 2048
    for k in ('inner_color', 'middle_color', 'outer_color'):
        if e.get(k) is not None:
            try:
                e[k] = [int(max(0, min(255, round(float(v))))) for v in e[k]][:3]
            except (TypeError, ValueError):
                e[k] = None
    return e


def has_rings(P):
    return bool((P.get('rings') or {}).get('enabled'))


def ring_colours(P, e):
    cols = np.array([s_[1] for s_ in P['colors']['stops']], np.float32).reshape(-1, 3)
    m = cols.mean(0)
    grey = float(np.dot(m, [0.299, 0.587, 0.114]))
    d = m * 0.55 + grey * 0.45
    auto = (np.clip(d * 0.78, 0, 255), np.clip(d * 1.05 + 12, 0, 255), np.clip(d * 0.95 + 6, 0, 255))
    out = []
    for k, a in zip(('inner_color', 'middle_color', 'outer_color'), auto):
        out.append(np.array(e[k], np.float32) if e.get(k) else a)
    return out


def noise1d(x, freq, rng):
    n = int(np.ceil(freq)) + 2
    v = rng.random(n + 1).astype(np.float32)
    t = x * np.float32(freq)
    i = np.floor(t).astype(np.int32)
    f = t - i
    f = f * f * (3 - 2 * f)
    return v[i] * (1 - f) + v[i + 1] * f


def fbm1d(x, freq, rng, o=5):
    s = 0; a = 1.0; n = 0
    for k in range(o):
        s = s + a * noise1d(x, freq * 2 ** k, rng); n += a; a *= 0.5
    return s / n


def ring_profile(P, n=2048):
    e = ring_entry(P.get('rings'))
    rng = np.random.default_rng(int(P.get('seed', 1)) * 7 + 991 + int(e['pattern']) * 104729)
    x = ((np.arange(n) + 0.5) / n).astype(np.float32)
    k = max(1, int(e['zones']))
    bounds = np.sort(rng.uniform(0.08, 0.92, k - 1))
    levels = rng.uniform(0.25, 1.0, k)
    levels = levels / levels.max()
    dens = np.full(n, levels[0], np.float32)
    for b, l0, l1 in zip(bounds, levels[:-1], levels[1:]):
        w = rng.uniform(0.004, 0.03)
        dens += np.float32(l1 - l0) * ss(np.float32(b - w), np.float32(b + w), x)
    det = max(float(e['detail']), 0.1)
    rl = float(e['ringlets'])
    n1 = fbm1d(x, 60 * det, rng)
    dens *= np.clip(1 + rl * (2 * n1 - 1) * 1.4, 0, None)
    for pos, wid, dep in e['gaps']:
        g = np.exp(-(np.abs(x - pos) / (wid / 2)) ** 6)
        dens *= 1 - np.float32(dep) * g
    soft = np.float32(0.002 + float(e['edge']) * 0.04)
    dens *= ss(np.float32(0), soft, x) * (1 - ss(1 - soft, np.float32(1), x))
    alpha = np.clip(dens * np.float32(e['opacity']), 0, 1)
    ci, cm, co = ring_colours(P, e)
    t = x[:, None]
    col = np.where(t < 0.5, ci + (cm - ci) * (t / 0.5), cm + (co - cm) * ((t - 0.5) / 0.5))
    n2 = fbm1d(x, 25 * det, rng)
    col = col * (1 + float(e['variation']) * 0.35 * (2 * n2 - 1))[:, None]
    col = col * (0.85 + 0.15 * np.clip(dens, 0, 1))[:, None]
    return np.clip(col, 0, 255).astype(np.float32), alpha.astype(np.float32)


def ring_image(P, n=None, h=16):
    e = ring_entry(P.get('rings'))
    col, a = ring_profile(P, n or e['size'])
    rgba = np.concatenate([col, (a * 255)[:, None]], 1)[::-1]
    return np.repeat((rgba + 0.5).clip(0, 255).astype(np.uint8)[None], h, 0)


def ring_scene(tex, col, alpha, e, w=560, h=300, light=(0.75, -0.45, 0.5), ss_=2, bg=(13, 15, 20)):
    W, Hh = w * ss_, h * ss_
    el = np.radians(max(2.0, min(89.0, float(e.get('view', 18.0)))))
    ang = np.radians(float(e.get('angle', 0.0)))
    ro = float(e['outer']); ri = float(e['inner'])
    half_w = ro * 1.06
    half_h = max(1.06, ro * np.sin(el) * 1.06 + 0.1)
    sc = min(W / (2 * half_w), Hh / (2 * half_h))
    xs = (np.arange(W) + 0.5 - W / 2) / sc
    ys = (Hh / 2 - np.arange(Hh) - 0.5) / sc
    X, Yv = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
    c = np.array([0, -np.cos(el), np.sin(el)], np.float32)
    up = np.array([0, np.sin(el), np.cos(el)], np.float32)
    O = X[..., None] * np.array([1, 0, 0], np.float32) + Yv[..., None] * up + 10 * c
    d = -c
    L = np.array(light, np.float32); L /= np.linalg.norm(L)
    nr = np.array([0, -np.sin(ang), np.cos(ang)], np.float32)
    b = O @ d
    cc = (O * O).sum(-1) - 1
    disc = b * b - cc
    hit_s = disc >= 0
    ts = -b - np.sqrt(np.maximum(disc, 0))
    tr_ = -(O @ nr) / float(d @ nr)
    Q = O + tr_[..., None] * d
    rq = np.sqrt((Q * Q).sum(-1))
    n = len(alpha)

    def ring_at(r):
        u = (r - ri) / (ro - ri)
        inside = (u >= 0) & (u <= 1)
        i = np.clip((u * n).astype(np.int32), 0, n - 1)
        return inside, i
    in_r, ir = ring_at(rq)
    a_r = np.where(in_r, alpha[ir], 0)
    out = np.broadcast_to(np.array(bg, np.float32), X.shape + (3,)).copy()
    S = O + ts[..., None] * d
    Hs, Ws = tex.shape[:2]
    lat = np.arcsin(np.clip(S[..., 2], -1, 1))
    lon = np.arctan2(S[..., 1], S[..., 0])
    py = np.clip(((0.5 - lat / np.pi) * Hs).astype(np.int32), 0, Hs - 1)
    px = ((lon / (2 * np.pi)) % 1 * Ws).astype(np.int32) % Ws
    shade = np.clip(S @ L, 0, 1) * 0.95 + 0.04
    tl = -(S @ nr) / max(abs(float(L @ nr)), 1e-4) * np.sign(float(L @ nr))
    Qs = S + tl[..., None] * L
    in_s, isd = ring_at(np.sqrt((Qs * Qs).sum(-1)))
    shade = shade * np.where((tl > 0) & in_s, 1 - 0.85 * alpha[isd], 1)
    planet = tex[py, px].astype(np.float32) * shade[..., None]
    out[hit_s] = planet[hit_s]
    bq = Q @ L
    cq = (Q * Q).sum(-1) - 1
    dq = bq * bq - cq
    shadowed = (dq > 0) & (-bq - np.sqrt(np.maximum(dq, 0)) > 0)
    rl = (0.25 + 0.75 * abs(float(L @ nr))) * np.where(shadowed, 0.12, 1.0)
    rc = col[ir] * rl[..., None]
    front = in_r & (~hit_s | (tr_ < ts))
    out = np.where(front[..., None], rc * a_r[..., None] + out * (1 - a_r[..., None]), out)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    return img.resize((w, h), Image.LANCZOS) if ss_ > 1 else img


def ring_snippet(P, path):
    e = ring_entry(P.get('rings'))
    return ('Rings\n{\n\tRing\n\t{\n\t\tinnerRadius = %d\n\t\touterRadius = %d\n\t\tangle = %s\n'
            '\t\ttexture = %s\n\t\tcolor = 1,1,1,1\n\t\tlockRotation = false\n\t\tuseNewShader = true\n\t}\n}\n') % (
        round(e['inner'] * 1000), round(e['outer'] * 1000), ('%g' % float(e['angle'])), path)


LAVA = {'amount': 0.0, 'mode': 'star', 'lat': 0.0, 'lon': 180.0, 'spread': 105.0, 'seed': 1,
        'plate_km': 90.0, 'shrink': 0.65, 'crack_km': 7.0, 'widen': 2.5, 'jagged': 0.5,
        'tilt': 1500.0, 'depth': 900.0, 'core': 16.0, 'core_depth': 1200.0, 'rafts': 0.6,
        'pools': 0, 'pool_km': 90.0,
        'color': [255, 92, 20], 'hot_color': [255, 196, 92], 'crust_color': [36, 30, 28], 'crust_amount': 0.85,
        'edge_glow': 0.5, 'glow': 0.85}
LAVA_MODES = ('star', 'all')
LAVA_LOOK = ('color', 'hot_color', 'crust_color', 'crust_amount', 'edge_glow', 'glow')


def lava_entry(a):
    e = copy.deepcopy(LAVA)
    a = a if isinstance(a, dict) else {}
    for k, v in a.items():
        if k in LAVA:
            e[k] = copy.deepcopy(v)
    for k in ('amount', 'lat', 'lon', 'spread', 'plate_km', 'shrink', 'crack_km', 'widen', 'jagged', 'tilt', 'depth',
              'core', 'core_depth', 'rafts', 'pool_km', 'crust_amount', 'edge_glow', 'glow'):
        try:
            e[k] = float(e[k])
        except (TypeError, ValueError):
            e[k] = float(LAVA[k])
    for k in ('seed', 'pools'):
        try:
            e[k] = int(round(float(e[k])))
        except (TypeError, ValueError):
            e[k] = int(LAVA[k])
    for k in ('color', 'hot_color', 'crust_color'):
        try:
            e[k] = [int(max(0, min(255, round(float(c))))) for c in e[k]][:3]
            if len(e[k]) != 3:
                raise ValueError
        except (TypeError, ValueError):
            e[k] = list(LAVA[k])
    e['mode'] = e['mode'] if e['mode'] in LAVA_MODES else 'star'
    e['amount'] = max(0.0, min(1.0, e['amount']))
    e['lat'] = max(-90.0, min(90.0, e['lat']))
    e['lon'] = e['lon'] % 360.0
    e['spread'] = max(5.0, min(180.0, e['spread']))
    e['plate_km'] = max(2.0, e['plate_km'])
    e['crack_km'] = max(0.1, e['crack_km'])
    for k in ('shrink', 'jagged', 'rafts', 'crust_amount', 'edge_glow'):
        e[k] = max(0.0, min(1.0, e[k]))
    e['widen'] = max(0.0, e['widen'])
    e['core'] = max(0.0, min(90.0, e['core']))
    e['pools'] = max(0, min(40, e['pools']))
    e['pool_km'] = max(1.0, e['pool_km'])
    e['glow'] = max(0.0, min(2.0, e['glow']))
    e['seed'] = max(1, e['seed'])
    return e


def has_lava(P):
    return float((P.get('lava') or {}).get('amount', 0)) > 0


def lava_shape(P):
    return {k: v for k, v in lava_entry(P.get('lava')).items() if k not in LAVA_LOOK}


def lava_setup(P):
    if not has_lava(P):
        return None
    L = lava_entry(P.get('lava'))
    c = lonlat_vec(L['lat'], L['lon'])
    rng = np.random.default_rng([L['seed'], 77])
    pools = []
    for i in range(L['pools']):
        v = None
        for _ in range(60):
            q = rng.normal(size=3)
            q /= np.linalg.norm(q)
            if L['mode'] == 'all' or math.degrees(math.acos(max(-1.0, min(1.0, float(q @ c))))) < L['spread'] * 0.8:
                v = q
                break
        if v is None:
            v = c.copy()
        pools.append((v.astype(np.float32), float(rng.uniform(0.6, 1.4)), int(rng.integers(1, 1 << 30))))
    return {'L': L, 'c': c, 'pools': pools}


def worley_cells(X, Y, Z, f, seed):
    x = X * np.float32(f); y = Y * np.float32(f); z = Z * np.float32(f)
    xf = np.floor(x); yf = np.floor(y); zf = np.floor(z)
    fx = x - xf; fy = y - yf; fz = z - zf
    xi = xf.astype(np.int32).view(U); yi = yf.astype(np.int32).view(U); zi = zf.astype(np.int32).view(U)
    sd = U((seed * 0x27D4EB2F + 0x7F4A7C15) & 0xFFFFFFFF)
    F1 = np.full(X.shape, np.float32(9)); F2 = np.full(X.shape, np.float32(9))
    H1 = np.zeros(X.shape, U)
    VX = np.zeros(X.shape, np.float32); VY = np.zeros(X.shape, np.float32); VZ = np.zeros(X.shape, np.float32)
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
                near = d2 < F1
                F2 = np.where(near, F1, np.minimum(F2, d2))
                F1 = np.where(near, d2, F1)
                H1 = np.where(near, h, H1)
                VX = np.where(near, ex, VX); VY = np.where(near, ey, VY); VZ = np.where(near, ez, VZ)
    return np.sqrt(F1), np.sqrt(F2), H1, VX, VY, VZ


def cell_rand(h, k):
    g = (h ^ U((0x5BD1E995 * (k + 1)) & 0xFFFFFFFF)) * U(0x27D4EB2F)
    g ^= g >> U(15)
    return (g & U(65535)).astype(np.float32) * np.float32(2 / 65535.0) - 1


def apply_lava(P, LV, hm, mk, X, Y, Z, W, H, r0, fmax):
    L = LV['L']
    Rk = float(P['radius']) / 1000.0
    c = LV['c']
    ang = np.degrees(np.arccos(np.clip(X * c[0] + Y * c[1] + Z * c[2], -1, 1))).astype(np.float32)
    mask = ang < L['spread'] * 1.3 if L['mode'] == 'star' else np.ones(X.shape, bool)
    for v, sf, ps in LV['pools']:
        R = L['pool_km'] * sf / Rk
        mask |= np.arccos(np.clip(X * v[0] + Y * v[1] + Z * v[2], -1, 1)) < R * 1.6
    idx = np.flatnonzero(mask)
    if not idx.size:
        return
    g = lambda a: a.reshape(-1)[idx]
    hn, lv, halo, heat, hot = lava_points(P, LV, g(X), g(Y), g(Z), g(ang), g(hm).copy(), W, fmax)
    hm.reshape(-1)[idx] = hn
    if mk is not None and mk.shape[0] > 5:
        for ch, v in ((5, lv), (6, halo), (7, heat), (8, hot)):
            m = mk[ch].reshape(-1)
            m[idx] = np.maximum(m[idx], v.astype(np.float16))


def lava_points(P, LV, X, Y, Z, ang, hm, W, fmax):
    L = LV['L']
    Rk = float(P['radius']) / 1000.0
    px = 2 * math.pi / W
    sd = int(L['seed']) * 1000 + 503
    amt = float(L['amount'])
    if L['mode'] == 'star':
        jit = fbm(X, Y, Z, 1.5, min(8.0, fmax), sd + 3, 0.5, 3) * np.float32(L['spread'] * 0.2)
        heat = (1 - ss(np.float32(0), np.float32(L['spread']), ang + jit)) ** np.float32(0.8)
    else:
        heat = np.clip(np.float32(0.6) + np.float32(0.4) * fbm(X, Y, Z, 1.2, min(6.0, fmax), sd + 3, 0.5, 3), 0, 1)
    heat = (heat * np.float32(amt)).astype(np.float32)
    plate = max(float(L['plate_km']), 1.0) / Rk
    jg = np.float32(float(L['jagged']) * plate * 0.45)
    if jg > 0:
        wf = min(1.2 / plate, fmax)
        Xw = X + jg * fbm(X, Y, Z, wf, fmax, sd + 11, 0.55, 4)
        Yw = Y + jg * fbm(X, Y, Z, wf, fmax, sd + 13, 0.55, 4)
        Zw = Z + jg * fbm(X, Y, Z, wf, fmax, sd + 17, 0.55, 4)
    else:
        Xw, Yw, Zw = X, Y, Z
    sh = float(L['shrink'])
    lv = np.zeros(X.shape, np.float32)
    halo = np.zeros(X.shape, np.float32)
    rel = np.zeros(X.shape, np.float32)
    raft = None
    levels = [(1.0, None), (1 / 2.3, 0.85 - 0.5 * sh), (1 / 5.0, 0.97 - 0.4 * sh)]
    cw0 = float(L['crack_km']) * 0.5 / Rk
    for k, (scale, thr) in enumerate(levels):
        if thr is None:
            gate = ss(np.float32(0.0), np.float32(0.06), heat)
        else:
            if sh <= 0:
                break
            gate = ss(np.float32(thr), np.float32(thr + 0.15), heat)
            if not (gate > 0.002).any():
                continue
        f = 1.0 / (plate * scale)
        F1, F2, hh, vx, vy, vz = worley_cells(Xw, Yw, Zw, f, sd + 31 * k)
        e = (F2 - F1) * np.float32(0.5 / f)
        hw0 = cw0 * (0.75 if k else 1.0)
        hwb = max(hw0, 0.7 * px)
        hw = np.float32(hwb) * (1 + np.float32(L['widen'] * (1.0 if k == 0 else 0.6)) * heat)
        vis = np.float32(min(1.0, hw0 / (0.7 * px)))
        wob = fbm(X, Y, Z, min(0.4 / hwb, fmax), fmax, sd + 41 + k, 0.5, 3) * hw * np.float32(0.35)
        ed = e + wob
        np.maximum(lv, (1 - ss(hw * np.float32(0.35), hw, ed)) * gate * vis, out=lv)
        np.maximum(halo, np.exp(-(ed / (hw * np.float32(3.0))) ** 2) * gate, out=halo)
        a = cell_rand(hh, 0); bx = cell_rand(hh, 1); by = cell_rand(hh, 2); bz = cell_rand(hh, 3)
        slab = np.float32(0.35) * a - np.float32(0.9) * (bx * vx + by * vy + bz * vz)
        rel += np.float32(L['tilt'] * (1.0 if k == 0 else 0.45 * scale ** 0.5)) * slab * gate * (np.float32(0.4) + np.float32(0.6) * heat)
        raft = ss(np.float32(0.18), np.float32(0.42), (F2 - F1)) * ss(np.float32(0.0), np.float32(0.25), np.float32(0.5) + np.float32(0.5) * cell_rand(hh, 4))
    core = np.zeros(X.shape, np.float32)
    if L['mode'] == 'star' and L['core'] > 0:
        cj = fbm(X, Y, Z, 4.0, fmax, sd + 61, 0.55, 5) * np.float32(L['core'] * 0.35)
        core = (1 - ss(np.float32(L['core'] * 0.5), np.float32(L['core']), ang + cj)) * np.float32(min(1.0, amt * 1.5))
    rafts = np.float32(L['rafts'])
    pool = np.zeros(X.shape, np.float32)
    for v, sf, ps in LV['pools']:
        R = L['pool_km'] * sf / Rk
        r = np.arccos(np.clip(X * v[0] + Y * v[1] + Z * v[2], -1, 1)).astype(np.float32)
        pj = fbm(X, Y, Z, min(2.5 / R, fmax), fmax, sd + (ps % 997), 0.55, 5) * np.float32(0.35)
        np.maximum(pool, 1 - ss(np.float32(0.7 * R), np.float32(R), r * (1 + pj)), out=pool)
    melt = np.maximum(core, pool)
    if raft is None:
        raft = np.zeros(X.shape, np.float32)
    np.maximum(lv, melt * (1 - raft * rafts), out=lv)
    hot = np.clip(core * (1 - raft * rafts * np.float32(0.6)) + pool * np.float32(0.55) + heat ** 4 * np.float32(0.35) * lv, 0, 1)
    level = hm - np.float32(L['depth']) * (np.float32(0.6) + np.float32(0.4) * heat)
    out = (hm + rel * (1 - melt)) * (1 - lv) + level * lv
    out -= np.float32(L['core_depth']) * core * (1 - np.float32(0.15) * raft * rafts)
    out -= np.float32(L['depth'] * 0.5) * pool * (1 - raft * rafts)
    return out.astype(np.float32), lv, halo * (1 - lv), heat, hot


def lava_colours(L, mk, n2=None):
    lv = mk[5].astype(np.float32); halo = mk[6].astype(np.float32)
    heat = mk[7].astype(np.float32); hot = mk[8].astype(np.float32)
    t = np.clip(hot + heat * heat * np.float32(0.35), 0, 1)[..., None]
    lc = np.array(L['color'], np.float32) * (1 - t) + np.array(L['hot_color'], np.float32) * t
    if n2 is not None:
        lc = lc * (1 + np.float32(0.12) * n2)[..., None]
    return lv, halo, heat, hot, lc


def lava_colourize(P, col, mk, n2):
    L = lava_entry(P.get('lava'))
    lv, halo, heat, hot, lc = lava_colours(L, mk, n2)
    torn = ss(np.float32(0.0), np.float32(0.08), heat) * np.float32(L['crust_amount'])
    crust = np.array(L['crust_color'], np.float32) * (1 + np.float32(0.18) * n2)[..., None]
    col = col + (crust - col) * torn[..., None]
    eg = (halo * np.float32(L['edge_glow']) * np.float32(0.4))[..., None]
    col = col + (lc * np.float32(0.75) - col) * eg
    col = col + (lc - col) * lv[..., None]
    return col


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


LAVA_OCEAN = {'enabled': False, 'crust': 0.55, 'crust_km': 60.0, 'shore': 0.5, 'glow': 0.9}
EMISSION = {'cracks': 0.0, 'volcanoes': 0.0, 'flows': 0.5, 'rivers': 0.0}


def lava_ocean_entry(a):
    e = copy.deepcopy(LAVA_OCEAN)
    a = a if isinstance(a, dict) else {}
    e.update({k: copy.deepcopy(v) for k, v in a.items() if k in LAVA_OCEAN})
    e['enabled'] = bool(e['enabled'])
    for k in ('crust', 'crust_km', 'shore', 'glow'):
        try:
            e[k] = float(e[k])
        except (TypeError, ValueError):
            e[k] = float(LAVA_OCEAN[k])
    e['crust'] = max(0.0, min(1.0, e['crust']))
    e['shore'] = max(0.0, min(1.0, e['shore']))
    e['crust_km'] = max(1.0, e['crust_km'])
    e['glow'] = max(0.0, min(2.0, e['glow']))
    return e


def emission_entry(a):
    e = copy.deepcopy(EMISSION)
    a = a if isinstance(a, dict) else {}
    e.update({k: copy.deepcopy(v) for k, v in a.items() if k in EMISSION})
    for k in EMISSION:
        try:
            e[k] = max(0.0, min(2.0 if k != 'flows' else 1.0, float(e[k])))
        except (TypeError, ValueError):
            e[k] = float(EMISSION[k])
    return e


def has_lava_ocean(P):
    return bool(P['shape']['ocean']) and bool((P.get('lava_ocean') or {}).get('enabled'))


def lava_rivers(P):
    return float((P.get('emission') or {}).get('rivers', 0)) > 0 and float((P.get('water') or {}).get('rivers', 0)) > 0


def volcano_glow(P):
    return float((P.get('emission') or {}).get('volcanoes', 0)) > 0


def has_emission(P):
    em = P.get('emission') or {}
    return (has_lava(P) or has_lava_ocean(P) or float(em.get('cracks', 0)) > 0 or float(em.get('volcanoes', 0)) > 0
            or lava_rivers(P))


def mk_channels(P):
    return 10 if (has_lava(P) or volcano_glow(P)) else 5


def lava_ocean_noise(P, X, Y, Z, fmax):
    O = lava_ocean_entry(P.get('lava_ocean'))
    Rk = float(P['radius']) / 1000.0
    sd = int(P['seed']) * 1000 + 911
    f = Rk / O['crust_km']
    jg = np.float32(0.4 / f)
    wf = min(1.3 * f, fmax)
    Xw = X + jg * fbm(X, Y, Z, wf, fmax, sd + 1, 0.55, 4)
    Yw = Y + jg * fbm(X, Y, Z, wf, fmax, sd + 2, 0.55, 4)
    Zw = Z + jg * fbm(X, Y, Z, wf, fmax, sd + 3, 0.55, 4)
    F1, F2 = worley(Xw, Yw, Zw, f, sd + 5)
    cov = fbm(X, Y, Z, 1.4, min(8.0, fmax), sd + 7, 0.5, 3)
    return (F2 - F1).astype(np.float32), cov.astype(np.float32)


def lava_ocean_parts(P, hm, lo):
    O = lava_ocean_entry(P.get('lava_ocean'))
    e, cov = lo
    t = np.float32(0.62 - 0.55 * O['crust'])
    crust = ss(np.float32(0.05), np.float32(0.16), e) * ss(t - np.float32(0.12), t + np.float32(0.12), cov * np.float32(0.5) + np.float32(0.5))
    crust = crust * np.float32(min(1.0, O['crust'] * 2.5))
    sea = ss(np.float32(-8), np.float32(8), -hm)
    sh = np.float32(40 + 460 * O['shore'])
    shore = (1 - ss(np.float32(0), sh, hm)) * (hm >= 0) * np.float32(O['shore'] > 0)
    return sea, crust, shore


def lava_paint(P):
    L = lava_entry(P.get('lava'))
    return np.array(L['color'], np.float32), np.array(L['hot_color'], np.float32), np.array(L['crust_color'], np.float32)


def glow_colourize(P, col, hm, mk, n2, lo, nj=None):
    lc, hc, cc = lava_paint(P)
    E = emission_entry(P.get('emission'))
    if mk is not None:
        if E['cracks'] > 0:
            w = np.clip(mk[4].astype(np.float32) * np.float32(min(1.0, E['cracks'])), 0, 1)
            col = col + (lc * (1 + np.float32(0.1) * n2)[..., None] - col) * w[..., None]
        if E['volcanoes'] > 0 and mk.shape[0] > 9:
            w = np.clip(mk[9].astype(np.float32) * np.float32(min(1.0, E['volcanoes'])), 0, 1)
            t = (w * np.float32(0.6))[..., None]
            col = col + (lc * (1 - t) + hc * t - col) * w[..., None]
        if E['rivers'] > 0:
            w = np.clip(mk[3].astype(np.float32) * np.float32(min(1.0, E['rivers'] * 1.2)), 0, 1)
            t = (w * w * np.float32(0.45))[..., None]
            rc = (lc * (1 - t) + hc * t) * (1 + np.float32(0.1) * n2)[..., None]
            col = col + (rc - col) * w[..., None]
    if has_lava_ocean(P) and lo is not None:
        sea, crust, shore = lava_ocean_parts(P, hm, lo)
        hot = np.clip(np.float32(0.2) + np.float32(0.25) * n2 + (np.float32(0.25) * nj if nj is not None else 0), 0, 1)[..., None]
        lava = lc * (1 - hot) + hc * hot
        surf = lava * (1 - crust[..., None]) + cc * (1 + np.float32(0.15) * n2)[..., None] * crust[..., None]
        col = col + (surf - col) * sea[..., None]
        col = col + (lc * np.float32(0.7) - col) * (shore * np.float32(0.45))[..., None]
    return col


def emissive_strip(P, hm, mk, lo):
    H, W = hm.shape
    em = np.zeros((H, W, 3), np.float32)
    lc, hc, cc = lava_paint(P)
    E = emission_entry(P.get('emission'))
    gl = lava_entry(P.get('lava'))['glow']
    if mk is not None and mk.shape[0] > 5 and has_lava(P):
        L = lava_entry(P.get('lava'))
        lv, halo, heat, hot, lcol = lava_colours(L, mk)
        w = lv * (np.float32(0.4) + np.float32(0.45) * np.clip(heat + hot, 0, 1)) + halo * np.float32(L['edge_glow'] * 0.3)
        em += lcol * (w * np.float32(gl))[..., None]
    if mk is not None and E['cracks'] > 0:
        em += lc * (mk[4].astype(np.float32) * np.float32(0.8 * E['cracks']))[..., None]
    if mk is not None and E['volcanoes'] > 0 and mk.shape[0] > 9:
        w = mk[9].astype(np.float32)
        t = (w * np.float32(0.6))[..., None]
        em += (lc * (1 - t) + hc * t) * (w * np.float32(0.85 * E['volcanoes']))[..., None]
    if mk is not None and E['rivers'] > 0:
        w = np.clip(mk[3].astype(np.float32), 0, 1)
        t = (w * w * np.float32(0.45))[..., None]
        em += (lc * (1 - t) + hc * t) * (w * np.float32(0.75 * E['rivers']))[..., None]
    if has_lava_ocean(P) and lo is not None:
        O = lava_ocean_entry(P.get('lava_ocean'))
        sea, crust, shore = lava_ocean_parts(P, hm, lo)
        w = sea * (1 - np.float32(0.88) * crust) * np.float32(0.5) + shore * np.float32(0.2)
        em += (lc * np.float32(0.7) + hc * np.float32(0.3)) * (w * np.float32(O['glow']))[..., None]
    return np.clip(em + 0.5, 0, 255).astype(np.uint8)


def colour_noise(P, X, Y, Z, fmax):
    sd = int(P['seed'])
    ps = max(float(P['colors']['patch_size']), 0.1)
    n1 = fbm(X, Y, Z, 3.0 / ps, fmax, sd + 101, 0.55, 5)
    n2 = fbm(X, Y, Z, 7.0 / ps, fmax, sd + 103, 0.5, 4)
    n3 = fbm(X, Y, Z, 1.6, fmax, sd + 107, 0.55, 5)
    nj = fbm(X, Y, Z, 9.0, fmax, sd + 109, 0.5, 3)
    lo = lava_ocean_noise(P, X, Y, Z, fmax) if has_lava_ocean(P) else None
    return n1, n2, n3, nj, lo


def colourize(P, hm, gx, gy, mk, lat, noise):
    C = P['colors']
    n1, n2, n3, nj = noise[:4]
    lo = noise[4] if len(noise) > 4 else None
    lava_sea = has_lava_ocean(P)
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
    if ocean and not lava_sea:
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
    if lava_sea:
        ice = ice * ss(np.float32(0), np.float32(150), hm)
    icec = np.array(C['ice'], np.float32)[None, None] * (1 + np.float32(0.06) * n2 + np.float32(0.04) * nj)[..., None]
    col += (icec - col) * ice[..., None]
    if mk is not None and mk.shape[0] > 5 and has_lava(P):
        col = lava_colourize(P, col, mk, n2)
    if has_emission(P):
        col = glow_colourize(P, col, hm, mk, n2, lo, nj)
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
    LV = lava_setup(P)
    RG = ridge_setup(P)
    VOLCANO_FLOWS[0] = float(emission_entry(P.get('emission'))['flows'])
    hm = np.zeros((H, W), np.float32)
    need = CR is not None or VL is not None or feats or NET is not None or CK is not None or LV is not None
    mk = np.zeros((mk_channels(P), H, W), np.float16) if need else None
    fm = fmax_for(W)

    def job(r0, r1):
        if cancel:
            cancel()
        X, Y, Z = rows_xyz(W, H, r0, r1)
        hm[r0:r1] = T.metres(X, Y, Z, fm, T.low_rows(W, H, r0, r1))
        if RG is not None:
            apply_ridge(RG, hm[r0:r1], X, Y, Z, W, fm)
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
        if LV is not None:
            apply_lava(P, LV, hm[r0:r1], sub, X, Y, Z, W, H, r0, fm)
    run_strips(job, strips(H, W), workers, progress)
    return hm, mk


def make_colour(P, hm, mk, W, cancel=None, progress=None, workers=None, noise_cache=None):
    H = W // 2
    gx, gy = slopes(hm, float(P['radius']), 0.6 * W / 2048.0 if W > 2048 else 0.0)
    if P['shape']['ocean']:
        wet = hm < 0
        gx = np.where(wet, 0, gx); gy = np.where(wet, 0, gy)
    col = np.zeros((H, W, 3), np.uint8)
    em = np.zeros((H, W, 3), np.uint8) if has_emission(P) else None
    fm = fmax_for(W)
    lat = row_lat(H, 0, H)
    lok = json.dumps(lava_ocean_entry(P.get('lava_ocean')) if has_lava_ocean(P) else None, sort_keys=True)

    def job(r0, r1):
        if cancel:
            cancel()
        key = (W, r0, r1, int(P['seed']), float(P['colors']['patch_size']), lok, float(P['radius']))
        nz = noise_cache.get(key) if noise_cache is not None else None
        if nz is None:
            X, Y, Z = rows_xyz(W, H, r0, r1)
            nz = colour_noise(P, X, Y, Z, fm)
            if noise_cache is not None:
                noise_cache[key] = nz
        sub = None if mk is None else mk[:, r0:r1]
        col[r0:r1] = colourize(P, hm[r0:r1], gx[r0:r1], gy[r0:r1], sub, lat[r0:r1], nz)
        if em is not None:
            em[r0:r1] = emissive_strip(P, hm[r0:r1], sub, nz[4] if len(nz) > 4 else None)
    run_strips(job, strips(H, W), workers, progress)
    return col, gx, gy, em


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


def render_globe(col, gx, gy, S, tilt, vlat, vlon, strength, light=None, ocean=None, emis=None):
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
    if emis is not None:
        e = emis.astype(np.float32)
        ee = (e[y0, x0] * (1 - tx) + e[y0, x1] * tx) * (1 - ty) + (e[y1, x0] * (1 - tx) + e[y1, x1] * tx) * ty
        out = out + ee / np.float32(255) * np.float32(0.7)
    o = np.zeros((S, S, 3), np.float32)
    o[m] = out[m]
    return Image.fromarray((np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8))


ATMO_POINT = {'altitude': 0.0, 'skyExposure': 0.2, 'skyAlpha': 1.0, 'skyExtinctionTint': 1.0, 'scatteringExposure': 0.2,
              'extinctionThickness': 1.0, 'postProcessAlpha': 1.0, 'postProcessDepth': 0.0, 'extinctionTint': 1.0}
ATMO_POINT_KEYS = ('altitude', 'skyExposure', 'skyAlpha', 'skyExtinctionTint', 'scatteringExposure', 'extinctionThickness',
                   'postProcessAlpha', 'postProcessDepth', 'extinctionTint')
ATMO_VALUES = ('atmosphereStartRadiusScale', 'HR', 'HM', 'm_betaR', 'BETA_MSca', 'm_mieG', 'ozoneAbsorption', 'ozoneHeight',
               'ozoneFalloff', 'useOzone', 'averageGroundReflectance', 'multipleScattering', 'godrayStrength')
ATMO_EXTRA = [['flattenScaledSpaceMesh', '0'], ['rimBlend', '20'], ['rimpower', '600'], ['specR', '40'], ['specG', '40'],
              ['specB', '40'], ['shininess', '50'], ['noonSunlightExtinctionStrength', '1'], ['cloudColorMultiplier', '1'],
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
    e['extra'] = atmo_fix_extra([[str(k), str(v)] for k, v in e['extra'] if str(k) not in ATMO_VALUES and str(k) not in ('name', 'configPoints')])
    return e


def atmo_fix_extra(extra):
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    d = dict(ATMO_EXTRA)
    have = {k for k, v in extra}
    out = [list(x) for x in extra] + [list(x) for x in ATMO_EXTRA if x[0] not in have]
    cur = dict(out)
    bad = set()
    if num(cur.get('shininess')) <= 0:
        bad.add('shininess')
    if all(num(cur.get(k)) <= 0 for k in ('specR', 'specG', 'specB')):
        bad.update(('specR', 'specG', 'specB'))
    return [[k, d[k] if k in bad else v] for k, v in out]


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


def sphere_lookup(img, x, y, z, tilt, vlat, vlon):
    H, W = img.shape[:2]
    t = np.radians(tilt); cu, su = np.float32(np.cos(t)), np.float32(np.sin(t))
    u2 = x * cu - y * su; v2 = x * su + y * cu
    a = np.radians(vlat); cl, sl = np.float32(np.cos(a)), np.float32(np.sin(a))
    y3 = v2 * cl + z * sl; z3 = -v2 * sl + z * cl
    lat = np.arcsin(np.clip(y3, -1, 1)); dlon = np.arctan2(u2, z3)
    fx = ((dlon + np.float32(np.radians(vlon))) / np.float32(2 * np.pi)) % 1 * W - 0.5
    fy = np.clip((0.5 - lat / np.pi) * H - 0.5, 0, H - 1.001)
    x0 = np.floor(fx).astype(np.int32); y0 = fy.astype(np.int32)
    ax = (fx - x0).astype(np.float32); ay = (fy - y0).astype(np.float32)
    x0 %= W; x1 = (x0 + 1) % W; y1 = np.minimum(y0 + 1, H - 1)
    if img.ndim == 3:
        ax = ax[:, None]; ay = ay[:, None]
    return (img[y0, x0] * (1 - ax) + img[y0, x1] * ax) * (1 - ay) + (img[y1, x0] * (1 - ax) + img[y1, x1] * ax) * ay


def ingame_clouds(P, W=1024, cancel=None, workers=None):
    if not has_clouds(P):
        return None
    cov, typ = cloud_maps(P, W, cancel=cancel, workers=workers)
    if not cov:
        return None
    A = np.zeros((W // 2, W), np.float32)
    for n, u in cov.items():
        if n.startswith('sys') and n != 'sys0':
            continue
        a = u.astype(np.float32) / 255
        if n == 'cirrus':
            a = a * np.float32(0.5)
        elif n != 'fair':
            a = a * np.float32(0.85)
        else:
            a = np.clip(a ** np.float32(1.1) * np.float32(0.92), 0, 1)
        A = 1 - (1 - A) * (1 - a)
    return A


def ingame_glow(P, em=None, W=1024, cancel=None):
    g = None
    if em is not None:
        e8 = np.asarray(em, np.uint8)
        if e8.shape[1] != W:
            e8 = np.asarray(Image.fromarray(e8).resize((W, W // 2), Image.BILINEAR))
        g = e8.astype(np.float32) / 255 * np.float32(0.7)
    if has_aurora(P):
        e = aurora_entry(P.get('aurora'))
        low, top = aurora_maps(P, W, cancel=cancel)
        nl = max(1, e['layers'] - e['top_layers']); nt = e['top_layers']
        ol = 1 - (1 - min(1.0, e['opacity'] / 255.0)) ** min(nl, 3)
        ot = (1 - (1 - min(1.0, e['opacity'] * (0.5 + 0.5 * e['fade']) / 255.0)) ** min(nt, 3)) * 0.6 if nt else 0.0
        a = low[..., :3] * low[..., 3:4] * np.float32(ol) + top[..., :3] * top[..., 3:4] * np.float32(ot)
        g = a if g is None else g + a
    return g


def render_ingame(P, tex, gx=None, gy=None, view=None, w=560, h=360, rot=(0.0, 0.0), steps=16, cancel=None, bg=None, clouds=None, glow=None):
    if has_atmo(P):
        return render_atmo(P, tex, gx, gy, view, w, h, rot, steps, cancel=cancel, bg=bg, clouds=clouds, glow=glow)
    e = atmo_e(P)
    pv = P.get('preview', {'tilt': 0, 'view_lat': 0, 'view_lon': 0})
    vlat = max(-90.0, min(90.0, float(pv.get('view_lat', 0)) + rot[1])); vlon = float(pv.get('view_lon', 0)) + rot[0]
    col = tex.astype(np.float32) * (255 if tex.dtype != np.uint8 and tex.max() <= 1.0 else 1)
    if clouds is not None:
        A = clouds
        if A.shape != col.shape[:2]:
            A = np.asarray(Image.fromarray(A.astype(np.float32), 'F').resize((col.shape[1], col.shape[0]), Image.BILINEAR), np.float32)
        col = col * (1 - A[..., None]) + np.float32(242) * A[..., None]
        if gx is not None:
            gx = gx * (1 - A); gy = gy * (1 - A)
    em = None
    if glow is not None:
        G = glow
        if G.shape[:2] != col.shape[:2]:
            G = np.asarray(Image.fromarray((np.clip(G, 0, 1) * 255).astype(np.uint8)).resize((col.shape[1], col.shape[0]), Image.BILINEAR), np.float32) / 255
        em = np.clip(G * 255 / 0.7, 0, 255)
    S = max(40, min(w, h) - 8)
    if gx is None:
        gx = np.zeros(col.shape[:2], np.float32); gy = gx
    g = render_globe(col, gx, gy, S, float(pv.get('tilt', 0)), vlat, vlon, float(P.get('normal_strength', 0.0)),
                     light=[float(v) for v in atmo_light(e)], emis=em)
    out = Image.new('RGB', (w, h), tuple(bg) if bg is not None else (0, 0, 0))
    yy, xx = np.mgrid[0:S, 0:S]
    rr = np.sqrt(((xx + 0.5) / S * 2 - 1) ** 2 + ((yy + 0.5) / S * 2 - 1) ** 2)
    mask = Image.fromarray((np.clip((1 - rr) * S / 2 + 0.5, 0, 1) * 255).astype(np.uint8), 'L')
    out.paste(g, ((w - S) // 2, (h - S) // 2), mask)
    return out


def render_atmo(P, tex, gx=None, gy=None, view=None, w=560, h=360, rot=(0.0, 0.0), steps=16, chunk=60000, cancel=None, bg=None, clouds=None, glow=None):
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
        nd0 = np.clip(uu * L[0] + vv * L[1] + zg * L[2], 0, 1)
        if clouds is not None:
            A = sphere_lookup(clouds, uu, vv, zg, tilt, vlat, vlon)[:, None]
            C = C * (1 - A) + A * (np.float32(0.95) * nd0 ** np.float32(0.8))[:, None]
        E = Tv
        avg = E.mean(1, keepdims=True)
        E = np.float32(pt['extinctionTint']) * E + np.float32(1 - pt['extinctionTint']) * avg
        E = np.maximum(0, np.float32(1 - pt['extinctionThickness']) + np.float32(pt['extinctionThickness']) * E)
        S = scatterer_hdr(Lin * sun, pt['scatteringExposure'])
        CE = C * E
        px_ = CE + S * (1 - CE)
        if glow is not None:
            px_ = px_ + sphere_lookup(glow, uu, vv, zg, tilt, vlat, vlon) * (1 - np.float32(0.75) * nd0)[:, None]
        flat[idx] += px_ * covf[idx][:, None]
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
           t + 'cloudIntegrationUsesScattererSunColors = False',
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


AURORA = {'enabled': False, 'seed': 1, 'north': True, 'south': True,
          'north_tilt': 8.0, 'north_lon': 40.0, 'south_tilt': 10.0, 'south_lon': 215.0,
          'oval': 17.0, 'wobble': 7.0, 'polar_gap': 0.0,
          'curtains': 4, 'spread': 1.0, 'width': 1.5, 'patchy': 0.5, 'rays': 0.65, 'glow': 0.16, 'brightness': 0.9,
          'color': [41, 255, 107], 'edge_color': [242, 97, 217], 'core_color': [140, 255, 204],
          'top_color': [230, 56, 128], 'top_edge_color': [128, 71, 255], 'top_core_color': [255, 128, 191],
          'layers': 7, 'top_layers': 3, 'altitude': 17000.0, 'spacing': 2500.0, 'opacity': 130, 'fade': 0.42,
          'speed': 12.0, 'size': 4096}
AURORA_COLOURS = ('color', 'edge_color', 'core_color', 'top_color', 'top_edge_color', 'top_core_color')
AURORA_SIZES = (1024, 2048, 4096, 8192)
AURORA_CURTAINS = ((0.0, 0.37, 0.68, 1.0), (4.8, 0.42, 0.76, 0.8), (-3.4, 0.46, 0.8, 0.6), (8.5, 0.5, 0.84, 0.5),
                   (-6.8, 0.52, 0.86, 0.42), (12.0, 0.55, 0.88, 0.36))
AURORA_COVERAGE = 'StockVolumetricClouds/Clouds/Textures/PluginData/Kerbin/base/coverage'
AURORA_UVNOISE = 'StockVolumetricClouds/Clouds/Textures/PluginData/uvnoise1'


def aurora_entry(a):
    e = copy.deepcopy(AURORA)
    a = a if isinstance(a, dict) else {}
    for k, v in a.items():
        if k in AURORA:
            e[k] = copy.deepcopy(v)
    for k in ('enabled', 'north', 'south'):
        e[k] = bool(e[k])
    for k in ('north_tilt', 'north_lon', 'south_tilt', 'south_lon', 'oval', 'wobble', 'polar_gap', 'spread', 'width',
              'patchy', 'rays', 'glow', 'brightness', 'altitude', 'spacing', 'fade', 'speed'):
        try:
            e[k] = float(e[k])
        except (TypeError, ValueError):
            e[k] = float(AURORA[k])
    for k in ('seed', 'curtains', 'layers', 'top_layers', 'opacity', 'size'):
        try:
            e[k] = int(round(float(e[k])))
        except (TypeError, ValueError):
            e[k] = int(AURORA[k])
    for k in AURORA_COLOURS:
        try:
            e[k] = [int(max(0, min(255, round(float(c))))) for c in e[k]][:3]
            if len(e[k]) != 3:
                raise ValueError
        except (TypeError, ValueError):
            e[k] = list(AURORA[k])
    e['curtains'] = max(1, min(len(AURORA_CURTAINS), e['curtains']))
    e['layers'] = max(1, min(16, e['layers']))
    e['top_layers'] = max(0, min(e['layers'], e['top_layers']))
    e['opacity'] = max(0, min(255, e['opacity']))
    e['fade'] = max(0.0, min(1.0, e['fade']))
    e['oval'] = max(1.0, min(60.0, e['oval']))
    e['wobble'] = max(0.0, e['wobble'])
    e['polar_gap'] = max(0.0, e['polar_gap'])
    e['spread'] = max(0.1, e['spread'])
    e['width'] = max(0.1, e['width'])
    for k in ('patchy', 'rays'):
        e[k] = max(0.0, min(1.0, e[k]))
    e['glow'] = max(0.0, e['glow'])
    e['brightness'] = max(0.0, min(1.0, e['brightness']))
    e['spacing'] = max(0.0, e['spacing'])
    e['seed'] = max(1, e['seed'])
    if e['size'] not in AURORA_SIZES:
        e['size'] = min(AURORA_SIZES, key=lambda s: abs(s - e['size']))
    return e


def has_aurora(P):
    e = (P.get('aurora') or {})
    return bool(e.get('enabled')) and bool(e.get('north', True) or e.get('south', True))


class AuroraNoise:
    N = 64

    def __init__(self, seed):
        rng = np.random.default_rng(4116 + int(seed))
        self.tabs = [rng.random((self.N, self.N, self.N), dtype=np.float32) for _ in range(8)]

    def vn(self, x, y, z, t):
        T = self.tabs[t]; N = self.N
        xi = np.floor(x).astype(np.int32); yi = np.floor(y).astype(np.int32); zi = np.floor(z).astype(np.int32)
        fx = (x - xi).astype(np.float32); fy = (y - yi).astype(np.float32); fz = (z - zi).astype(np.float32)
        fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz)
        x0 = xi % N; y0 = yi % N; z0 = zi % N; x1 = (x0 + 1) % N; y1 = (y0 + 1) % N; z1 = (z0 + 1) % N
        c00 = T[x0, y0, z0] * (1 - fx) + T[x1, y0, z0] * fx
        c10 = T[x0, y1, z0] * (1 - fx) + T[x1, y1, z0] * fx
        c01 = T[x0, y0, z1] * (1 - fx) + T[x1, y0, z1] * fx
        c11 = T[x0, y1, z1] * (1 - fx) + T[x1, y1, z1] * fx
        return (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz

    def fbm(self, x, y, z, t, o=4):
        s = 0; a = 1.0; n = 0.0
        for i in range(o):
            s = s + a * self.vn(x * 2 ** i + 17.3 * i, y * 2 ** i + 5.1 * i, z * 2 ** i + 9.7 * i, (t + i) % 8)
            n += a; a *= 0.5
        return (s / n) * 2 - 1


def aurora_ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def aurora_axis(e, sgn):
    key = 'north' if sgn > 0 else 'south'
    t = np.radians(e[key + '_tilt']); l = np.radians(e[key + '_lon'])
    return np.array([np.sin(t) * np.cos(l), np.sin(t) * np.sin(l), np.cos(t)]) * sgn


def aurora_reach(e):
    offs = [c[0] for c in AURORA_CURTAINS[:e['curtains']]]
    th = e['oval'] + e['wobble'] + 3.0 + 3.6 + 1.1 + max(offs) * e['spread'] + 4 * e['width'] * 1.6 + 8.0
    return th + max(e['north_tilt'], e['south_tilt'])


def aurora_hemi(e, nz, px, py, pz, sgn):
    m = aurora_axis(e, sgn)
    e1 = np.cross(m, [0.3, 0.9, 0.1]); e1 /= np.linalg.norm(e1); e2 = np.cross(m, e1)
    cm = px * m[0] + py * m[1] + pz * m[2]
    th = np.degrees(np.arccos(np.clip(cm, -1, 1))).astype(np.float32)
    cx = px * e1[0] + py * e1[1] + pz * e1[2]; cy = px * e2[0] + py * e2[1] + pz * e2[2]
    r = np.sqrt(cx * cx + cy * cy) + 1e-6; cx = (cx / r).astype(np.float32); cy = (cy / r).astype(np.float32)
    s = float((3 if sgn > 0 else 71) + 13 * (e['seed'] - 1))
    fb = nz.fbm
    th0 = e['oval'] + e['wobble'] * fb(cx * 1.3 + s, cy * 1.3, s * 0.7, 0, 3) + 3.0 * cx
    thw = th + 3.6 * fb(px * 5 + s, py * 5, pz * 5, 1, 4) + 1.1 * fb(px * 13, py * 13 + s, pz * 13, 2, 3)
    rays = 0.5 + 0.5 * fb(cx * 16 + s, cy * 16, th * 0.05, 3, 2)
    rays = (1 - e['rays']) + e['rays'] * aurora_ss(0.25, 0.8, rays)
    rays = rays * (0.75 + 0.25 * (0.5 + 0.5 * fb(cx * 38, cy * 38 + s, th * 0.08, 4, 2)))
    I = np.zeros_like(th); Cv = np.zeros_like(th)
    gd = (e['patchy'] - 0.5) * 0.5
    for k, (off, g0, g1, amp) in enumerate(AURORA_CURTAINS[:e['curtains']]):
        thk = th0 + off * e['spread'] + 2.4 * fb(cx * 2.6 + k * 7.1 + s, cy * 2.6, k * 3.3, 5, 3)
        w = e['width'] * (1 + 0.6 * fb(cx * 3.1 + s, cy * 3.1 + k * 2.2, 1.7, 6, 2))
        gate = aurora_ss(g0 + gd, g1 + gd, 0.5 + 0.5 * fb(cx * 1.9 + k * 11.3, cy * 1.9 + s, k * 1.9, 7, 3))
        d = thw - thk
        prof = np.where(d > 0, np.exp(-(d / w) ** 2), np.exp(-(np.abs(d) / (1.7 * w)) ** 1.6))
        a = amp * gate * prof
        I += a; Cv += a * np.clip(-d / (2.6 * w), 0, 1)
    patch = 0.5 + 0.5 * fb(px * 3 + s, py * 3, pz * 3, 2, 3)
    I = I * rays + e['glow'] * np.exp(-((thw - th0 - 1) / 8) ** 2) * aurora_ss(0.3, 0.7, patch)
    if e['polar_gap'] > 0:
        I = I * aurora_ss(e['polar_gap'] / 3.0, e['polar_gap'], th)
    v = Cv / np.maximum(I, 1e-4)
    return I.astype(np.float32), np.clip(v, 0, 1).astype(np.float32)


def aurora_maps(P, W=None, cancel=None):
    e = aurora_entry(P.get('aurora'))
    W = int(W or e['size']); H = W // 2
    nz = AuroraNoise(e['seed'])
    low = np.zeros((H, W, 4), np.float32); top = np.zeros((H, W, 4), np.float32)
    cl = [np.array(e[k], np.float32) / 255 for k in AURORA_COLOURS]
    low[..., :3] = cl[0]; top[..., :3] = cl[3]
    reach = min(90.0, aurora_reach(e))
    lon = ((np.arange(W) + 0.5) / W * 2 * np.pi).astype(np.float32)
    CH = max(8, min(256, (1 << 21) // W))
    for sgn, on in ((1, e['north']), (-1, e['south'])):
        if not on:
            continue
        rows = np.arange(0, H // 2) if sgn > 0 else np.arange(H // 2, H)
        lat_all = (np.pi / 2 - (rows + 0.5) / H * np.pi).astype(np.float32)
        keep = rows[np.abs(np.degrees(lat_all)) >= 90.0 - reach]
        for c0 in range(0, len(keep), CH):
            if cancel:
                cancel()
            rr = keep[c0:c0 + CH]
            lat = (np.pi / 2 - (rr + 0.5) / H * np.pi).astype(np.float32)
            la, lo = np.meshgrid(lat, lon, indexing='ij')
            px = np.cos(la) * np.cos(lo); py = np.cos(la) * np.sin(lo); pz = np.sin(la)
            I, v = aurora_hemi(e, nz, px, py, pz, sgn)
            a0 = (np.clip(I, 0, 1.25) / 1.25) ** 0.85 * (1 - 0.2 * aurora_ss(0.2, 1.0, v))
            core = aurora_ss(0.55, 1.0, 0.9 * a0)[..., None] * 0.45
            vv = aurora_ss(0.05, 1.0, v)[..., None] * 0.85
            a = np.clip(e['brightness'] * a0, 0, 1)
            for out, (g, pu, cy) in ((low, cl[0:3]), (top, cl[3:6])):
                col = g * (1 - vv) + pu * vv
                out[rr, :, :3] = col * (1 - core) + cy * core
                out[rr, :, 3] = a
    return low, top


def aurora_u8(m):
    return (np.clip(m, 0, 1) * 255 + 0.5).astype(np.uint8)


def aurora_layers(e):
    n = e['layers']
    out = []
    for i in range(n):
        f = i / float(n - 1) if n > 1 else 0.0
        alt = e['altitude'] + e['spacing'] * i
        a = int(round(e['opacity'] * (1 - (1 - e['fade']) * f)))
        out.append((i, alt, a, i >= n - e['top_layers']))
    return out


def aurora_cfg(P, name, tex_low, tex_top):
    e = aurora_entry(P.get('aurora'))
    t = '\t'
    def g(v):
        return ('%.6g' % v)
    L = ['EVE_CLOUDS', '{']
    for i, alt, a, is_top in aurora_layers(e):
        lo = alt - 500; hi = alt + 500
        L += [t + 'OBJECT', t + '{',
              t * 2 + 'name = %s-aurora-%d' % (name, i),
              t * 2 + 'body = ' + name,
              t * 2 + 'altitude = ' + g(alt),
              t * 2 + 'detailSpeed = 0,25,0',
              t * 2 + 'speed = 0,%s,0' % g(e['speed']),
              t * 2 + 'speedMode = LinearSurface',
              t * 2 + 'settings', t * 2 + '{',
              t * 3 + '_UVNoiseTex = ' + AURORA_UVNOISE,
              t * 3 + '_UVNoiseStrength = 0.0012',
              t * 3 + '_Color = 255,255,255,%d' % a,
              t * 3 + '_MainTex', t * 3 + '{',
              t * 4 + 'value = ' + (tex_top if is_top else tex_low),
              t * 4 + 'isClamped = True',
              t * 3 + '}', t * 2 + '}',
              t * 2 + 'layer2D', t * 2 + '{',
              t * 3 + 'macroCloudMaterial', t * 3 + '{',
              t * 4 + '_DetailDist = 2E-06',
              t * 4 + '_MinLight = 1',
              t * 3 + '}', t * 2 + '}',
              t * 2 + 'layerRaymarchedVolumeV5', t * 2 + '{',
              t * 3 + 'scaledFadeStartAltitude = -2000',
              t * 3 + 'scaledFadeEndAltitude = -1000',
              t * 3 + 'coverageMap', t * 3 + '{',
              t * 4 + 'value = ' + AURORA_COVERAGE,
              t * 4 + 'type = AlphaMap',
              t * 4 + 'alphaMask = ALPHAMAP_R',
              t * 3 + '}',
              t * 3 + 'raymarchingSettings', t * 3 + '{',
              t * 4 + 'adaptiveStepSizeFactor = 0',
              t * 4 + 'baseStepSize = 90000000',
              t * 4 + 'maxStepSize = 90000000',
              t * 4 + 'lightMarchDistance = 0',
              t * 4 + 'lightMarchSteps = 0',
              t * 4 + 'fxOnlyLayer = True',
              t * 3 + '}',
              t * 3 + 'cloudTypes', t * 3 + '{',
              t * 4 + 'Item', t * 4 + '{',
              t * 5 + 'typeName = AuroraEmpty',
              t * 5 + 'minAltitude = ' + g(lo),
              t * 5 + 'maxAltitude = ' + g(hi),
              t * 5 + 'interpolateCloudHeights = false',
              t * 5 + 'baseNoiseTiling = 0',
              t * 5 + 'density = 0.0',
              t * 5 + 'lightningFrequency = 0.0',
              t * 5 + 'coverageCurve', t * 5 + '{', t * 6 + 'key = 0 0', t * 5 + '}',
              t * 5 + 'densityCurve', t * 5 + '{', t * 5 + '}',
              t * 4 + '}', t * 3 + '}',
              t * 3 + 'noise', t * 3 + '{', t * 3 + '}',
              t * 3 + 'lightVolumeSettings', t * 3 + '{', t * 4 + 'useLightVolume = False', t * 3 + '}',
              t * 3 + 'phaseFunctions', t * 3 + '{', t * 3 + '}',
              t * 2 + '}', t + '}']
    L.append('}')
    return '\n'.join(L) + '\n'


def aurora_composite(e, low, top, bg):
    o = bg.astype(np.float32)
    al = low[..., 3:4]; at = top[..., 3:4]
    nl = max(1, e['layers'] - e['top_layers']); nt = e['top_layers']
    ol = 1 - (1 - min(1.0, e['opacity'] / 255.0)) ** min(nl, 3)
    ot = (1 - (1 - min(1.0, e['opacity'] * (0.5 + 0.5 * e['fade']) / 255.0)) ** min(nt, 3)) * 0.6 if nt else 0.0
    o = o * (1 - al * ol) + low[..., :3] * al * ol
    o = o * (1 - at * ot) + top[..., :3] * at * ot
    return o


def aurora_preview(P, low, top, bg=None, S=420):
    e = aurora_entry(P.get('aurora'))
    H, W = low.shape[:2]
    offs = [c[0] for c in AURORA_CURTAINS[:e['curtains']]]
    reach = min(89.0, e['oval'] + e['wobble'] + max(offs) * e['spread'] + 3 * e['width'] + max(e['north_tilt'], e['south_tilt']) + 6)
    yy, xx = np.mgrid[0:S, 0:S]
    X = (xx - S / 2 + 0.5) / (S / 2); Y = (yy - S / 2 + 0.5) / (S / 2); R = np.sqrt(X * X + Y * Y)
    if bg is not None:
        bgf = np.asarray(Image.fromarray(np.asarray(bg, np.uint8)).resize((W, H), Image.BILINEAR), np.float32) / 255 * 0.08
    else:
        bgf = np.zeros((H, W, 3), np.float32) + np.array([0.02, 0.03, 0.06], np.float32)
    panels = []
    for sgn in (1, -1):
        col = np.radians(R * reach)
        lo = (np.arctan2(Y, X) * sgn) % (2 * np.pi)
        fy = (col / np.pi if sgn > 0 else 1 - col / np.pi) * H
        py_ = np.clip(fy, 0, H - 1).astype(int); px_ = np.clip(lo / (2 * np.pi) * W, 0, W - 1).astype(int)
        o = aurora_composite(e, low[py_, px_], top[py_, px_], bgf[py_, px_])
        edge = np.clip((1 - R) * S / 2, 0, 1)[..., None]
        o = o * edge + np.array([13, 15, 20], np.float32) / 255 * (1 - edge)
        panels.append(o)
    gap = np.zeros((S, 24, 3), np.float32) + np.array([13, 15, 20], np.float32) / 255
    pv = np.concatenate([panels[0], gap, panels[1]], 1)
    return Image.fromarray(aurora_u8(pv))


def save_aurora(m, path, fmt, flip=True):
    u = aurora_u8(m)
    if path.lower().endswith('.dds'):
        if flip:
            u = np.ascontiguousarray(u[::-1])
        save_mips(Image.fromarray(u, 'RGBA'), path, 'DXT5')
    else:
        Image.fromarray(u, 'RGBA').save(path, 'PNG')


CLOUDS = {'enabled': False, 'seed': 1, 'size': 4096,
          'swirl': 1.0, 'swirl_size': 1.0, 'wind': 1.0, 'bands': 3, 'streaks': 0.7, 'breakup': 0.5,
          'fair': 0.45, 'speckle': 0.5, 'systems': 3, 'system_cover': 0.5, 'fair_pct': 35.0, 'system_pct': 30.0, 'cirrus_pct': 15.0,
          'duration': 16.0, 'repeat': 30.0, 'fade': 5.0,
          'cirrus': 0.5, 'base': 6500.0, 'height': 1.0, 'cirrus_altitude': 14300.0,
          'speed': 29.89, 'brightness': 512, 'color': [120, 120, 120]}
CLOUD_SIZES = (2048, 4096, 8192, 16384)
CLOUD_TOPS = (1700, 2700, 3700, 4700, 5700, 5700)
CLOUD_MW = 1024
CLOUD_STEPS = 24
CLOUD_NB = 6
_CFLOW = {}


def cloud_entry(a):
    e = copy.deepcopy(CLOUDS)
    a = a if isinstance(a, dict) else {}
    for k, v in a.items():
        if k in CLOUDS:
            e[k] = copy.deepcopy(v)
    e['enabled'] = bool(e['enabled'])
    for k in ('swirl', 'swirl_size', 'wind', 'streaks', 'breakup', 'fair', 'speckle', 'system_cover', 'fair_pct', 'system_pct', 'cirrus_pct', 'duration', 'repeat',
              'fade', 'cirrus', 'base', 'height', 'cirrus_altitude', 'speed'):
        try:
            e[k] = float(e[k])
        except (TypeError, ValueError):
            e[k] = float(CLOUDS[k])
    for k in ('seed', 'size', 'bands', 'systems', 'brightness'):
        try:
            e[k] = int(round(float(e[k])))
        except (TypeError, ValueError):
            e[k] = int(CLOUDS[k])
    try:
        e['color'] = [int(max(0, min(255, round(float(c))))) for c in e['color']][:3]
        if len(e['color']) != 3:
            raise ValueError
    except (TypeError, ValueError):
        e['color'] = list(CLOUDS['color'])
    e['seed'] = max(1, e['seed'])
    if e['size'] not in CLOUD_SIZES:
        e['size'] = min(CLOUD_SIZES, key=lambda s: abs(s - e['size']))
    e['swirl'] = max(0.0, min(3.0, e['swirl']))
    e['swirl_size'] = max(0.25, min(4.0, e['swirl_size']))
    e['wind'] = max(0.0, min(3.0, e['wind']))
    e['bands'] = max(1, min(8, e['bands']))
    for k in ('streaks', 'breakup', 'fair', 'speckle', 'system_cover', 'cirrus'):
        e[k] = max(0.0, min(1.0, e[k]))
    e['systems'] = max(0, min(4, e['systems']))
    for k in ('fair_pct', 'system_pct', 'cirrus_pct'):
        e[k] = max(0.0, min(100.0, e[k]))
    e['repeat'] = max(1.0, e['repeat'])
    e['duration'] = max(0.5, min(e['repeat'], e['duration']))
    e['fade'] = max(0.0, min(e['duration'] / 2.0, e['fade']))
    e['base'] = max(0.0, e['base'])
    e['height'] = max(0.2, min(4.0, e['height']))
    e['cirrus_altitude'] = max(e['base'] + 500.0, e['cirrus_altitude'])
    e['brightness'] = max(1, min(2000, e['brightness']))
    return e


def has_clouds(P):
    return bool((P.get('clouds') or {}).get('enabled'))


def cloud_layers(e):
    out = [('fair', 'fair', None)] if e['fair_pct'] > 0 else []
    if e['system_pct'] > 0:
        for k in range(e['systems']):
            off = e['repeat'] * k / max(1, e['systems'])
            out.append(('sys%d' % k, 'system-%d' % k, round(off, 2)))
    if e['cirrus_pct'] > 0:
        out.append(('cirrus', 'cirrus', None))
    return out


def sphere_rows(W, H, r0, r1):
    lat = (math.pi / 2 - (np.arange(r0, r1, dtype=np.float64) + 0.5) / H * math.pi)
    lon = (np.arange(W, dtype=np.float64) + 0.5) / W * 2 * math.pi
    la, lo = np.meshgrid(lat, lon, indexing='ij')
    return (np.cos(la) * np.cos(lo)).astype(np.float32), (np.cos(la) * np.sin(lo)).astype(np.float32), np.sin(la).astype(np.float32)


def grid_sample(G, x, y, z):
    C, H, W = G.shape
    lon = np.arctan2(y, x)
    lon = np.where(lon < 0, lon + np.float32(2 * math.pi), lon)
    fx = lon * np.float32(W / (2 * math.pi)) - np.float32(0.5)
    fy = (np.float32(math.pi / 2) - np.arcsin(np.clip(z, -1, 1))) * np.float32(H / math.pi) - np.float32(0.5)
    fy = np.clip(fy, 0, H - 1.001)
    x0 = np.floor(fx).astype(np.int32); y0 = fy.astype(np.int32)
    tx = (fx - x0).astype(np.float32); ty = (fy - y0).astype(np.float32)
    x0 %= W; x1 = (x0 + 1) % W; y1 = np.minimum(y0 + 1, H - 1)
    out = []
    for g in G:
        a = g[y0, x0] * (1 - tx) + g[y0, x1] * tx
        b = g[y1, x0] * (1 - tx) + g[y1, x1] * tx
        out.append(a * (1 - ty) + b * ty)
    return out


def cloud_velocity(e, X, Y, Z):
    sd = e['seed'] * 1000 + 701
    f0 = 1.3 / e['swirl_size']

    def psi(x, y, z):
        return fbm(x, y, z, f0, f0 * 5, sd, 0.5, 3) + np.float32(0.2) * fbm(x, y, z, f0 * 2.5, f0 * 8, sd + 1, 0.5, 1)
    h = np.float32(0.004)
    gx = (psi(X + h, Y, Z) - psi(X - h, Y, Z)) / (2 * h)
    gy = (psi(X, Y + h, Z) - psi(X, Y - h, Z)) / (2 * h)
    gz = (psi(X, Y, Z + h) - psi(X, Y, Z - h)) / (2 * h)
    k = np.float32(e['swirl'] * 0.35 / f0)
    vx = (Y * gz - Z * gy) * k; vy = (Z * gx - X * gz) * k; vz = (X * gy - Y * gx) * k
    lat = np.arcsin(np.clip(Z, -1, 1))
    zon = np.float32(e['wind'] * 0.35) * np.cos(lat * np.float32(e['bands'])) * (1 + np.float32(0.25) * fbm(X, Y, Z, 1.1, 3, sd + 5, 0.5, 2))
    vx = vx - Y * zon; vy = vy + X * zon
    return np.stack([vx, vy, vz]).astype(np.float32)


def cloud_flow(e, cancel=None, progress=None, workers=None):
    key = json.dumps([e[k] for k in ('seed', 'swirl', 'swirl_size', 'wind', 'bands')])
    got = _CFLOW.get(key)
    if got is not None:
        return got
    VW = 512
    vX, vY, vZ = sphere_rows(VW, VW // 2, 0, VW // 2)
    V = cloud_velocity(e, vX, vY, vZ)
    MW = CLOUD_MW; MH = MW // 2
    sd = e['seed'] * 1000 + 733
    nb = CLOUD_NB
    P6 = np.zeros((6, MH, MW), np.float32)
    BL = np.zeros((nb, MH // 2, MW // 2), np.float32)
    MID = np.zeros((MH, MW), np.float32)
    dt = np.float32(0.016)
    samples = [s for s in range(CLOUD_STEPS) if s % 4 == 3]
    wts = [0.5 + 0.5 * math.sin(math.pi * (s + 1) / (CLOUD_STEPS + 1)) for s in samples]
    wsum = np.float32(sum(wts))

    def job(r0, r1):
        x, y, z = sphere_rows(MW, MH, r0, r1)
        bacc = [np.zeros(((r1 - r0) // 2, MW // 2), np.float32) for _ in range(nb)]
        macc = np.zeros(x.shape, np.float32)
        for s in range(CLOUD_STEPS):
            if cancel:
                cancel()
            vx, vy, vz = grid_sample(V, x, y, z)
            mx = x - dt * 0.5 * vx; my = y - dt * 0.5 * vy; mz = z - dt * 0.5 * vz
            vx, vy, vz = grid_sample(V, mx, my, mz)
            x = x - dt * vx; y = y - dt * vy; z = z - dt * vz
            n = np.sqrt(x * x + y * y + z * z); x /= n; y /= n; z /= n
            if s in samples:
                w = np.float32(wts[samples.index(s)])
                xs, ys, zs = x[::2, ::2], y[::2, ::2], z[::2, ::2]
                for i in range(nb):
                    bacc[i] += w * fbm(xs, ys, zs, 2.3, 7.0, sd + 11 * i, 0.5, 3)
                macc += w * fbm(x, y, z, 11.0, 24.0, sd + 97, 0.5, 2)
        vx, vy, vz = grid_sample(V, x, y, z)
        P6[:, r0:r1] = np.stack([x, y, z, vx, vy, vz])
        for i in range(nb):
            BL[i, r0 // 2:r1 // 2] = bacc[i] / wsum
        MID[r0:r1] = macc / wsum
    rows = [(r, min(MH, r + 32)) for r in range(0, MH, 32)]
    run_strips(job, rows, workers, progress)
    fields = []
    for i in range(nb):
        b = BL[i]
        b = (b - b.mean()) / max(float(b.std()), 1e-6)
        bp = np.concatenate([b[:, -1:], b, b[:, :1]], 1)
        up = np.asarray(Image.fromarray(bp.astype(np.float32), 'F').resize(((MW // 2 + 2) * 2, MH), Image.BILINEAR), np.float32)
        fields.append(up[:, 2:2 + MW])
    fields.append(((MID - MID.mean()) / max(float(MID.std()), 1e-6)).astype(np.float32))
    G = np.concatenate([P6, np.stack(fields)]).astype(np.float32)
    if len(_CFLOW) > 3:
        _CFLOW.clear()
    _CFLOW[key] = G
    return G


def cloud_fib_stats(e, W, G):
    rng = np.random.default_rng(e['seed'] + 4)
    q = rng.normal(size=(3, 6000)).astype(np.float32)
    q /= np.linalg.norm(q, axis=0)
    f = cloud_fib(e, W, G, q[0], q[1], q[2])
    return float(f.mean()), max(float(f.std()), 1e-6)


def cloud_fib(e, W, G, X, Y, Z):
    S = grid_sample(G, X, Y, Z)
    ax, ay, az, vx, vy, vz = S[:6]
    n = np.sqrt(ax * ax + ay * ay + az * az) + np.float32(1e-9)
    ax /= n; ay /= n; az /= n
    vm = np.sqrt(vx * vx + vy * vy + vz * vz) + np.float32(1e-6)
    px = np.float32(2 * math.pi / W)
    hstep = np.float32(1.6) * px / vm * np.float32(0.5 + e['streaks'])
    ff = W / 36.0
    sd = e['seed'] * 1000 + 761
    acc = np.zeros(X.shape, np.float32)
    K = 4
    for k in range(-K, K + 1):
        t = np.float32(k) * hstep
        acc += fbm(ax + t * vx, ay + t * vy, az + t * vz, ff, ff * 2.2, sd, 0.5, 2)
    return acc / np.float32(2 * K + 1)


def cloud_strip(e, W, G, fst, r0, r1, only=None):
    want = set(only) if only is not None else set(n for n, _, _ in cloud_layers(e))
    H = W // 2
    X, Y, Z = sphere_rows(W, H, r0, r1)
    S = grid_sample(G, X, Y, Z)
    ax, ay, az = S[0], S[1], S[2]
    n = np.sqrt(ax * ax + ay * ay + az * az) + np.float32(1e-9)
    ax = ax / n; ay = ay / n; az = az / n
    nb = CLOUD_NB
    bands = S[6:6 + nb]
    mid = S[6 + nb]
    fib = (cloud_fib(e, W, G, X, Y, Z) - np.float32(fst[0])) / np.float32(fst[1])
    sd = e['seed'] * 1000 + 787
    fs = W / 4096.0
    fine = 0.5 + 0.5 * fbm(ax, ay, az, 60 * fs, 140 * fs, sd + 1, 0.55, 3)
    iso = 0.5 + 0.5 * fbm(ax, ay, az, 5.0, 14.0, sd + 2, 0.5, 3)
    m = np.clip(0.5 + 0.28 * mid, 0, 1)
    f = np.clip(0.5 + 0.26 * fib, 0, 1)
    out = {}
    st = np.float32(e['streaks'])
    c = np.float32((0.45 - e['fair']) * 1.4)
    band = bands[0]
    if 'fair' not in want:
        band = None
    mask = ss(-0.24 + c, 0.48 + c, band) if band is not None else None
    if band is not None:
        halo = ss(-0.70 + c, 0.12 + c, band)
        brk = ss(0.28, 0.60, iso) * np.float32(e['breakup']) + np.float32(1 - e['breakup'])
        body = mask * (0.32 + 0.68 * ss(0.26, 0.64, m)) * (0.45 + 0.55 * brk)
        veil = (halo - halo * mask) * ss(0.48, 0.80, m) * 0.75
        cov = (body + veil) * ((1 - st) * np.float32(0.7) + st * (0.14 + 1.12 * f))
        cov = cov * (0.66 + 0.68 * fine)
        g = np.float32(max(0.0, float(e['fair']) - 1.0))
        cov = ss(np.float32(0.12) - np.float32(0.12) * g, np.float32(0.90) - np.float32(0.45) * g, cov + np.float32(0.3) * g * mask)
        if e['speckle'] > 0:
            dots = fbm(ax, ay, az, W / 10.0, W / 5.0, sd + 3, 0.5, 2)
            zone = halo * (1 - mask * np.float32(0.7)) * ss(0.35, 0.65, iso)
            sp = ss(0.32, 0.5, dots) * zone * np.float32(e['speckle'])
            cov = np.maximum(cov, sp)
        core = ss(0.8 - c, 1.6 - c, band) * ss(0.45, 0.8, m)
        typ = np.clip(0.18 * ss(0.30, 0.92, cov) + 0.3 * core * ss(0.55, 0.95, cov), 0, 1)
        out['fair'] = (cov, typ)
    for k in range(e['systems']):
        if 'sys%d' % k not in want:
            continue
        b = bands[2 + k]
        t = np.float32((0.5 - e['system_cover']) * 1.6 + 0.35)
        mk_ = ss(t - 0.45, t + 0.25, b)
        body = mk_ * (0.55 + 0.45 * ss(0.26, 0.7, m))
        cv = body * ((1 - st) * np.float32(0.8) + st * (0.3 + 1.0 * f)) * (0.75 + 0.5 * fine)
        cv = ss(0.10, 0.80, cv)
        core = ss(t + 0.3, t + 1.2, b) * ss(0.4, 0.8, m)
        ty = np.clip(0.25 * ss(0.3, 0.9, cv) + 0.75 * core * ss(0.5, 0.95, cv), 0, 1)
        out['sys%d' % k] = (cv, ty)
    if 'cirrus' in want:
        b = bands[1]
        cc = np.float32((0.5 - e['cirrus']) * 1.4)
        mask = ss(0.02 + cc, 0.92 + cc, b)
        fc = np.clip(0.5 + 0.22 * fib, 0, 1)
        g = np.float32(max(0.0, float(e['cirrus']) - 1.0))
        hair = ss(np.float32(0.30) - np.float32(0.3) * g, np.float32(1.00) - np.float32(0.5) * g, fc) ** 1.25
        cv = mask * hair * (0.35 + 0.65 * ss(0.25, 0.75, m)) * (0.50 + 0.50 * ss(0.22, 0.62, iso)) * (0.85 + 0.3 * fine)
        out['cirrus'] = (np.clip(cv * 1.45, 0, 1), None)
    return out


CLOUD_PCT_W = 192
_CPCT = {}


def cloud_cover_frac(u, thr=0.1):
    H = u.shape[0]
    w = np.cos(np.pi / 2 - (np.arange(H) + 0.5) / H * np.pi)
    return float(((u > thr).mean(1) * w).sum() / w.sum())


def cloud_measure(e, G, keys):
    W = CLOUD_PCT_W
    st = cloud_fib_stats(e, W, G)
    res = cloud_strip(e, W, G, st, 0, W // 2, keys)
    return {k: cloud_cover_frac(res[k][0]) for k in keys if k in res}


CLOUD_SHAPE = ('seed', 'swirl', 'swirl_size', 'wind', 'bands', 'streaks', 'breakup', 'speckle', 'systems')


def cloud_solve(e, G, param, keys, target, lo, hi):
    key = json.dumps([[e[k] for k in CLOUD_SHAPE], param, target])
    got = _CPCT.get(key)
    if got is not None:
        return got
    q = dict(e)
    for _ in range(10):
        mid = 0.5 * (lo + hi)
        q[param] = mid
        m = cloud_measure(q, G, keys)
        f = sum(m.values()) / max(1, len(m))
        if f < target:
            lo = mid
        else:
            hi = mid
    v = round(0.5 * (lo + hi), 4)
    if len(_CPCT) > 64:
        _CPCT.clear()
    _CPCT[key] = v
    return v


def cloud_resolve(e, G):
    e = dict(e)
    if e['fair_pct'] > 0:
        e['fair'] = cloud_solve(e, G, 'fair', ['fair'], e['fair_pct'] / 100.0, -1.6, 2.4)
    if e['system_pct'] > 0 and e['systems'] > 0:
        e['system_cover'] = cloud_solve(e, G, 'system_cover', ['sys%d' % k for k in range(e['systems'])], e['system_pct'] / 100.0, -1.6, 2.2)
    if e['cirrus_pct'] > 0:
        e['cirrus'] = cloud_solve(e, G, 'cirrus', ['cirrus'], e['cirrus_pct'] / 100.0, -1.6, 2.4)
    return e


def cloud_report(P, cancel=None):
    e = cloud_entry(P.get('clouds'))
    G = cloud_flow(e, cancel)
    e = cloud_resolve(e, G)
    names = [n for n, _, _ in cloud_layers(e)]
    m = cloud_measure(e, G, names)
    return e, m


def cloud_total(cov):
    keys = [k for k in ('fair', 'sys0', 'cirrus') if k in cov]
    if not keys:
        return 0.0
    u = np.maximum.reduce([cov[k] for k in keys]).astype(np.float32) / 255
    return cloud_cover_frac(u)


def cloud_maps(P, W=None, cancel=None, progress=None, workers=None):
    e = cloud_entry(P.get('clouds'))
    W = int(W or e['size']); H = W // 2
    fkey = json.dumps([e[k] for k in ('seed', 'swirl', 'swirl_size', 'wind', 'bands')])
    fresh = fkey not in _CFLOW
    fw = 0.6 if fresh else 0.0
    G = cloud_flow(e, cancel, (lambda i, n: progress('wind', fw * i / n)) if progress else None, workers)
    mp = (lambda i, n: progress('clouds', fw + (1 - fw) * i / n)) if progress else None
    e = cloud_resolve(e, G)
    fst = cloud_fib_stats(e, W, G)
    names = [n for n, _, _ in cloud_layers(e)]
    cov = {n: np.zeros((H, W), np.uint8) for n in names}
    typ = {n: np.zeros((H, W), np.uint8) for n in names if n != 'cirrus'}

    def job(r0, r1):
        if cancel:
            cancel()
        res = cloud_strip(e, W, G, fst, r0, r1)
        for n in names:
            c, t = res[n]
            cov[n][r0:r1] = (np.clip(c, 0, 1) * 255 + 0.5).astype(np.uint8)
            if t is not None:
                typ[n][r0:r1] = (np.clip(t, 0, 1) * 255 + 0.5).astype(np.uint8)
    run_strips(job, strips(H, W, 1 << 18), workers, mp)
    return cov, typ


def half_u8(u):
    return ((u[0::2, 0::2].astype(np.uint16) + u[0::2, 1::2] + u[1::2, 0::2] + u[1::2, 1::2] + 2) // 4).astype(np.uint8)


def save_bc4_dds(u, path, flip=True):
    a = np.ascontiguousarray(u[::-1] if flip else u)
    H, W = a.shape
    blocks = bc4_encode(a).tobytes()
    hd = bytearray(128)
    hd[0:4] = b'DDS '
    struct.pack_into('<7I', hd, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000, H, W, len(blocks), 1, 1)
    struct.pack_into('<2I', hd, 76, 32, 0x4)
    hd[84:88] = b'BC4U'
    struct.pack_into('<I', hd, 108, 0x1000)
    with open(path, 'wb') as f:
        f.write(bytes(hd) + blocks)


def save_cloud_scaled(u, path, flip=True, gamma=1.15, gain=0.88):
    a = (np.clip((u.astype(np.float32) / 255) ** np.float32(gamma) * np.float32(gain), 0, 1) * 255 + 0.5).astype(np.uint8)
    if flip:
        a = a[::-1]
    rgba = np.full(a.shape + (4,), 255, np.uint8)
    rgba[..., 3] = a
    save_mips(Image.fromarray(rgba, 'RGBA'), path, 'DXT5')


def cloud_files(folder, base, e):
    out = {}
    for n, _, _ in cloud_layers(e):
        out[n] = {'coverage': os.path.join(folder, '%s_%s_coverage.dds' % (base, n)),
                  'scaled': os.path.join(folder, '%s_%s_scaled.dds' % (base, n))}
        if n != 'cirrus':
            out[n]['type'] = os.path.join(folder, '%s_%s_type.dds' % (base, n))
    out['cfg'] = os.path.join(folder, base + '_clouds.cfg')
    return out


def cloud_cfg(P, name, texbase):
    from string import Template
    e = cloud_entry(P.get('clouds'))
    r, g, b = e['color']
    tops = [int(round(e['base'] + t * e['height'])) for t in CLOUD_TOPS]
    out = ['EVE_CLOUDS', '{']
    for n, label, off in cloud_layers(e):
        tex = lambda k: '%s_%s_%s' % (texbase, n, k)
        common = dict(name='%s-%s' % (name, label), body=name, speed=('%.6g' % e['speed']), r=r, g=g, b=b,
                      scaled=tex('scaled'), coverage=tex('coverage'))
        if n == 'cirrus':
            txt = Template(CLOUD_TPL_CIRRUS).substitute(common, altitude='%d' % round(e['cirrus_altitude']),
                                                        bright=int(round(e['brightness'] * 400 / 512.0)), alpha=300,
                                                        cmin='%d' % round(e['base']),
                                                        cmax='%d' % round(e['cirrus_altitude'] + 1500))
        else:
            d = dict(common, altitude='%d' % round(e['base'] + 400), bright=e['brightness'], typemap=tex('type'),
                     order=3 if n == 'fair' else 0, base='%d' % round(e['base']))
            d.update({'top%d' % i: '%d' % t for i, t in enumerate(tops)})
            txt = Template(CLOUD_TPL_LAYER).substitute(d)
            if off is not None:
                ts = ['\t\ttimeSettings', '\t\t{', '\t\t\tunit = Hours', '\t\t\tfadeTime = %.6g' % e['fade'],
                      '\t\t\tduration = %.6g' % e['duration'], '\t\t\toffset = %.6g' % off,
                      '\t\t\trepeatInterval = %.6g' % e['repeat'], '\t\t\tfadeMode = Coverage', '\t\t}']
                lines = txt.rstrip('\n').split('\n')
                assert lines[-1] == '\t}'
                txt = '\n'.join(lines[:-1] + ts + ['\t}']) + '\n'
        out.append(txt.rstrip('\n'))
    out.append('}')
    return '\n'.join(out) + '\n'


def export_clouds(P, name, base, folder, flip=True, log=print, cfg_path=None, cancel=None):
    e = cloud_entry(P.get('clouds'))
    files = cloud_files(folder, base, e)
    log('making the clouds at %d x %d' % (e['size'], e['size'] // 2))
    last = [-1]

    def prog(stage, f):
        p = int(f * 100) // 10 * 10
        if p != last[0]:
            last[0] = p
            log('clouds %d%% (%s)' % (p, 'working out the wind' if stage == 'wind' else 'cloud maps'))
    cov, typ = cloud_maps(P, cancel=cancel, progress=prog)
    written = []
    for n, _, _ in cloud_layers(e):
        F = files[n]
        c = cov[n] if n != 'cirrus' else half_u8(cov[n])
        save_bc4_dds(c, F['coverage'], flip); written.append(F['coverage'])
        if n != 'cirrus':
            save_bc4_dds(half_u8(typ[n]), F['type'], flip); written.append(F['type'])
            save_cloud_scaled(half_u8(cov[n]), F['scaled'], flip)
        else:
            save_cloud_scaled(c, F['scaled'], flip, 1.0, 0.5)
        written.append(F['scaled'])
        log('cloud layer %s done' % n)
    del cov, typ
    with open(files['cfg'], 'w', newline='\n') as f:
        f.write(cloud_cfg(P, name, tex_path(folder, base, cfg_path)))
    written.append(files['cfg'])
    return written


def cloud_composite(P, cov, base_rgb):
    e = cloud_entry(P.get('clouds'))
    o = base_rgb.astype(np.float32) / 255
    names = [n for n, _, _ in cloud_layers(e) if n in cov]
    for n in names:
        a = cov[n].astype(np.float32) / 255
        if a.shape != o.shape[:2]:
            a = np.asarray(Image.fromarray(cov[n]).resize((o.shape[1], o.shape[0]), Image.BILINEAR), np.float32) / 255
        if n == 'cirrus':
            a = a * np.float32(0.5)
        elif n != 'fair':
            a = a * np.float32(0.85)
        else:
            a = np.clip(a ** np.float32(1.1) * np.float32(0.92), 0, 1)
        o = o * (1 - a[..., None]) + a[..., None]
    return (np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8)
CLOUD_TPL_LAYER = '\tOBJECT\n\t{\n\t\tname = ${name}\n\t\tbody = ${body}\n\t\taltitude = ${altitude}\n\t\tdetailSpeed = 0,6,0\n\t\tspeed = 0,${speed},0\n\t\tspeedMode = LinearSurface\n\t\tsettings\n\t\t{\n\t\t\t_DetailTex = StockVolumetricClouds/Clouds/Textures/PluginData/detail1\n\t\t\t_DetailScale = 30\n\t\t\t_UVNoiseTex = StockVolumetricClouds/Clouds/Textures/PluginData/uvnoise1\n\t\t\t_UVNoiseStrength = 0.00020000001\n\t\t\t_BumpScale = 0.5\n\t\t\t_Lambertian = 0.75\n\t\t\t_Color = ${bright},${bright},${bright},255\n\t\t\t_MainTex\n\t\t\t{\n\t\t\t\tvalue = ${scaled}\n\t\t\t\tisClamped = True\n\t\t\t}\n\t\t\t_FlowMap\n\t\t\t{\n\t\t\t}\n\t\t}\n\t\tlayer2D\n\t\t{\n\t\t\tshadowMaterial\n\t\t\t{\n\t\t\t\t_ShadowFactor = 1\n\t\t\t\t_VolumetricShadowDensity\n\t\t\t\t{\n\t\t\t\t}\n\t\t\t}\n\t\t\tmacroCloudMaterial\n\t\t\t{\n\t\t\t\t_DetailDist = 2E-06\n\t\t\t}\n\t\t}\n\t\tlayerRaymarchedVolumeV5\n\t\t{\n\t\t\tcolor = ${r}, ${g}, ${b}, 255\n\t\t\tupwardsCloudSpeed = 5\n\t\t\tscaledFadeStartAltitude = 200000\n\t\t\tscaledFadeEndAltitude = 260000\n\t\t\tskylightMultiplier = 1.0\n\t\t\tskylightTintMultiplier = 0.7\n\t\t\traymarchingSettings\n\t\t\t{\n\t\t\t\tlightMarchSteps = 4\n\t\t\t\tlightMarchDistance = 1200\n\t\t\t\tbaseStepSize = 75\n\t\t\t\tadaptiveStepSizeFactor = 0.006\n\t\t\t\toverlapRenderOrder = ${order}\n\t\t\t\tmaxStepSize = 1500\n\t\t\t}\n\t\t\tnoise\n\t\t\t{\n\t\t\t\terosionDepth = 0.65\n\t\t\t\tworley\n\t\t\t\t{\n\t\t\t\t\tspherical = 1\n\t\t\t\t\tpersistence = 0.57\n\t\t\t\t}\n\t\t\t}\n\t\t\tcoverageMap\n\t\t\t{\n\t\t\t\tvalue = ${coverage}\n\t\t\t\ttype = AlphaMap\n\t\t\t\talphaMask = ALPHAMAP_R\n\t\t\t}\n\t\t\tcloudTypeMap\n\t\t\t{\n\t\t\t\tvalue = ${typemap}\n\t\t\t\ttype = AlphaMap\n\t\t\t\talphaMask = ALPHAMAP_R\n\t\t\t}\n\t\t\tambientSound\n\t\t\t{\n\t\t\t\tsoundName = StockVolumetricClouds/Clouds/Sounds/WhistlingWindLooped\n\t\t\t}\n\t\t\tdroplets\n\t\t\t{\n\t\t\t\tdropletsConfig = droplets-cloud-Kerbin\n\t\t\t}\n\t\t\tlightVolumeSettings\n\t\t\t{\n\t\t\t}\n\t\t\tphaseFunctions\n\t\t\t{\n\t\t\t\tsingleScattering1 = 0.95, 0.1\n\t\t\t\tsingleScattering2 = 0.8, 0.2\n\t\t\t\tmultipleScattering1 = 0.2, 3.0\n\t\t\t\tmultipleScattering2 = -0.4, 0.3\n\t\t\t}\n\t\t\tcloudTypes\n\t\t\t{\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = Stratus\n\t\t\t\t\tminAltitude = ${base}\n\t\t\t\t\tmaxAltitude = ${top0}\n\t\t\t\t\tinterpolateCloudHeights = true\n\t\t\t\t\tdensity = 0.0015\n\t\t\t\t\tbaseNoiseTiling = 2300\n\t\t\t\t\tambientVolume = 2\n\t\t\t\t\tdropletsDensity = 0.2\n\t\t\t\t\tnoiseEdgeHardness = 0.9\n\t\t\t\t\tmultipleScatteringBrightness = 0.8\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 1.633945\n\t\t\t\t\t\tkey = 0.1140957 0.8506892 0.06669102 0.261398\n\t\t\t\t\t\tkey = 0.3686106 0.9575245 0 0\n\t\t\t\t\t\tkey = 0.9732781 -0.006797761 -0.369256 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = Cumulus\n\t\t\t\t\tminAltitude = ${base}\n\t\t\t\t\tmaxAltitude = ${top1}\n\t\t\t\t\tinterpolateCloudHeights = true\n\t\t\t\t\tdensity = 0.012\n\t\t\t\t\tbaseNoiseTiling = 2300\n\t\t\t\t\tambientVolume = 2\n\t\t\t\t\tdropletsDensity = 0.2\n\t\t\t\t\tnoiseEdgeHardness = 0.97\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 1.633945\n\t\t\t\t\t\tkey = 0.08695792 0.976166 0.06669102 0.04846065\n\t\t\t\t\t\tkey = 0.9732781 -0.006797761 -0.7966601 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = Congestus0\n\t\t\t\t\tminAltitude = ${base}\n\t\t\t\t\tmaxAltitude = ${top2}\n\t\t\t\t\tinterpolateCloudHeights = true\n\t\t\t\t\tdensity = 0.012\n\t\t\t\t\tbaseNoiseTiling = 2300\n\t\t\t\t\tambientVolume = 2\n\t\t\t\t\tdropletsDensity = 0.2\n\t\t\t\t\tnoiseEdgeHardness = 0.97\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 1.633945\n\t\t\t\t\t\tkey = 0.08695792 0.976166 0.06669102 0.04846065\n\t\t\t\t\t\tkey = 0.9732781 -0.006797761 -0.7966601 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = Congestus 1\n\t\t\t\t\tminAltitude = ${base}\n\t\t\t\t\tmaxAltitude = ${top3}\n\t\t\t\t\tinterpolateCloudHeights = true\n\t\t\t\t\tdensity = 0.012\n\t\t\t\t\tbaseNoiseTiling = 2300\n\t\t\t\t\tambientVolume = 2\n\t\t\t\t\tdropletsDensity = 0.3\n\t\t\t\t\tnoiseEdgeHardness = 0.97\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 1.633945\n\t\t\t\t\t\tkey = 0.08695792 0.976166 0.06669102 0.04846065\n\t\t\t\t\t\tkey = 0.4343985 0.6765829 -1.224023 -1.224023\n\t\t\t\t\t\tkey = 0.8816288 0.3897246 -1.164106 -1.164106\n\t\t\t\t\t\tkey = 0.9732781 -0.006797761 -0.7966601 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = Congestus 2\n\t\t\t\t\tminAltitude = ${base}\n\t\t\t\t\tmaxAltitude = ${top4}\n\t\t\t\t\tinterpolateCloudHeights = false\n\t\t\t\t\tdensity = 0.006\n\t\t\t\t\tbaseNoiseTiling = 2300\n\t\t\t\t\tdropletsDensity = 0.3\n\t\t\t\t\tnoiseEdgeHardness = 0.97\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 1.633945\n\t\t\t\t\t\tkey = 0.09431168 0.9640306 0.06669102 -0.8954304\n\t\t\t\t\t\tkey = 0.2904161 0.8003764 0.2357683 0.2357683\n\t\t\t\t\t\tkey = 0.59456 0.7429472 -0.001872113 -0.001872113\n\t\t\t\t\t\tkey = 0.734686 0.7428927 -3.4198 -1.176937\n\t\t\t\t\t\tkey = 0.9732781 -0.006797761 -0.8304251 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = Congestus 3\n\t\t\t\t\tminAltitude = ${base}\n\t\t\t\t\tmaxAltitude = ${top5}\n\t\t\t\t\tinterpolateCloudHeights = false\n\t\t\t\t\tdensity = 0.006\n\t\t\t\t\tbaseNoiseTiling = 2300\n\t\t\t\t\tambientVolume = 2\n\t\t\t\t\tdropletsDensity = 0.5\n\t\t\t\t\tnoiseEdgeHardness = 0.97\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 1.633945\n\t\t\t\t\t\tkey = 0.09431168 0.9640306 0.06669102 -0.8954304\n\t\t\t\t\t\tkey = 0.2904161 0.8003764 0.2357683 0.2357683\n\t\t\t\t\t\tkey = 0.734686 0.7428927 -3.4198 -1.176937\n\t\t\t\t\t\tkey = 0.9732781 -0.006797761 -0.8304251 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n'
CLOUD_TPL_CIRRUS = '\tOBJECT\n\t{\n\t\tname = ${name}\n\t\tbody = ${body}\n\t\taltitude = ${altitude}\n\t\tdetailSpeed = 0,6,0\n\t\tspeed = 0,${speed},0\n\t\tspeedMode = LinearSurface\n\t\tsettings\n\t\t{\n\t\t\t_DetailTex = StockVolumetricClouds/Clouds/Textures/PluginData/detail1\n\t\t\t_DetailScale = 30\n\t\t\t_UVNoiseTex = StockVolumetricClouds/Clouds/Textures/PluginData/uvnoise1\n\t\t\t_UVNoiseStrength = 0.00020000001\n\t\t\t_Color = ${bright},${bright},${bright},${alpha}\n\t\t\t_BumpScale = 0.5\n\t\t\t_Lambertian = 0.75\n\t\t\t_MainTex\n\t\t\t{\n\t\t\t\tvalue = ${scaled}\n\t\t\t\tisClamped = True\n\t\t\t}\n\t\t\t_FlowMap\n\t\t\t{\n\t\t\t}\n\t\t}\n\t\tlayer2D\n\t\t{\n\t\t\tshadowMaterial\n\t\t\t{\n\t\t\t\t_ShadowFactor = 1\n\t\t\t\t_VolumetricShadowDensity\n\t\t\t\t{\n\t\t\t\t}\n\t\t\t}\n\t\t\tmacroCloudMaterial\n\t\t\t{\n\t\t\t\t_DetailDist = 2E-06\n\t\t\t}\n\t\t}\n\t\tlayerRaymarchedVolumeV5\n\t\t{\n\t\t\tcolor = ${r}, ${g}, ${b}, 255\n\t\t\tupwardsCloudSpeed = 5\n\t\t\tscaledFadeStartAltitude = 200000\n\t\t\tscaledFadeEndAltitude = 260000\n\t\t\tskylightMultiplier = 1.0\n\t\t\tskylightTintMultiplier = 0.7\n\t\t\traymarchingSettings\n\t\t\t{\n\t\t\t\tlightMarchSteps = 0\n\t\t\t\tlightMarchDistance = 0\n\t\t\t\tbaseStepSize = 300\n\t\t\t\tadaptiveStepSizeFactor = 0.006\n\t\t\t\toverlapRenderOrder = 7\n\t\t\t\tmaxStepSize = 1500\n\t\t\t}\n\t\t\tnoise\n\t\t\t{\n\t\t\t\terosionDepth = 0.65\n\t\t\t\tworley\n\t\t\t\t{\n\t\t\t\t\tspherical = 1\n\t\t\t\t\tpersistence = 0.57\n\t\t\t\t}\n\t\t\t}\n\t\t\tcoverageMap\n\t\t\t{\n\t\t\t\tvalue = ${coverage}\n\t\t\t\ttype = AlphaMap\n\t\t\t\talphaMask = ALPHAMAP_R\n\t\t\t}\n\t\t\tcloudTypeMap\n\t\t\t{\n\t\t\t\tvalue = ${coverage}\n\t\t\t\ttype = AlphaMap\n\t\t\t\talphaMask = ALPHAMAP_R\n\t\t\t}\n\t\t\tcloudTypes\n\t\t\t{\n\t\t\t\tItem\n\t\t\t\t{\n\t\t\t\t\ttypeName = trail\n\t\t\t\t\tminAltitude = ${cmin}\n\t\t\t\t\tmaxAltitude = ${cmax}\n\t\t\t\t\tinterpolateCloudHeights = true\n\t\t\t\t\tdensity = 0.001\n\t\t\t\t\tbaseNoiseTiling = 50000\n\t\t\t\t\tambientVolume = 2\n\t\t\t\t\tdropletsDensity = 0.2\n\t\t\t\t\tnoiseEdgeHardness = 0.5\n\t\t\t\t\tcoverageCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0.01728953 -0.004032524 1.633945 -0.2416199\n\t\t\t\t\t\tkey = 0.4307672 -0.2456568 0.2357683 0.2357683\n\t\t\t\t\t\tkey = 0.6933722 0.9572497 0.3691055 0.3691055\n\t\t\t\t\t\tkey = 0.8104363 -0.01274869 -0.8304251 -0.5550035\n\t\t\t\t\t}\n\t\t\t\t\tdensityCurve\n\t\t\t\t\t{\n\t\t\t\t\t\tkey = 0 0 1 1\n\t\t\t\t\t\tkey = 1 1 1 1\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t\tambientSound\n\t\t\t{\n\t\t\t\tsoundName = StockVolumetricClouds/Clouds/Sounds/WhistlingWindLooped\n\t\t\t}\n\t\t\tdroplets\n\t\t\t{\n\t\t\t\tdropletsConfig = droplets-cloud-Kerbin\n\t\t\t}\n\t\t\tlightVolumeSettings\n\t\t\t{\n\t\t\t}\n\t\t\tphaseFunctions\n\t\t\t{\n\t\t\t\tsingleScattering1 = 0.95, 0.05\n\t\t\t\tsingleScattering2 = 0.8, 0.15\n\t\t\t\tmultipleScattering1 = 0.2, 2.0\n\t\t\t\tmultipleScattering2 = -0.4, 0.2\n\t\t\t}\n\t\t\tcurlNoise\n\t\t\t{\n\t\t\t\ttiling = 20000\n\t\t\t\tstrength = 10000\n\t\t\t\tcontrast = 0.25\n\t\t\t}\n\t\t}\n\t}\n'


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


def write_preview(P, col, hm, path, em=None):
    H, W = hm.shape
    if W > 4096:
        f = W // 4096
        hm = hm.reshape(H // f, f, W // f, f).mean((1, 3))
        col = np.asarray(Image.fromarray(col).resize((4096, 2048), Image.LANCZOS))
        if em is not None:
            em = np.asarray(Image.fromarray(em).resize((4096, 2048), Image.LANCZOS))
        H, W = hm.shape
    gx, gy = slopes(hm, float(P['radius']), 0.5)
    ocean = (hm < 0).astype(np.float32) if P['shape']['ocean'] else None
    if ocean is not None:
        gx = gx * (1 - ocean); gy = gy * (1 - ocean)
    k = float(P['normal_strength'])
    pv = P['preview']
    sheet = Image.new('RGB', (2400, 1200), (13, 15, 20))
    shf = col.astype(np.float32) * shade_map(gx, gy, k)[..., None]
    if em is not None:
        shf = shf + em.astype(np.float32) * np.float32(0.7)
    sh = np.clip(shf, 0, 255).astype(np.uint8)
    if has_atmo(P):
        t2, gx2, gy2 = atmo_texture(col, hm, P)
        sheet.paste(render_atmo(P, t2, gx2, gy2, view='planet', w=800, h=800, steps=24, bg=(13, 15, 20)), (0, 0))
    elif has_rings(P):
        rc, ra = ring_profile(P, 2048)
        sheet.paste(ring_scene(sh, rc, ra, ring_entry(P['rings']), w=800, h=800), (0, 0))
    else:
        sheet.paste(render_globe(col, gx, gy, 800, pv['tilt'], pv['view_lat'], pv['view_lon'], k, ocean=ocean, emis=em), (0, 0))
    sheet.paste(Image.fromarray(sh).resize((1600, 800), Image.LANCZOS), (800, 0))
    sheet.paste(render_globe(col, gx, gy, 400, 0, 72, pv['view_lon'], k, ocean=ocean, emis=em), (0, 800))
    sheet.paste(render_globe(col, gx, gy, 400, 0, -72, pv['view_lon'], k, ocean=ocean, emis=em), (400, 800))
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
CLOUD_FMT = 'EVE + True Volumetric Clouds'
DDS_CODEC = {DDS_BC1: 'DXT1', DDS_BC3: 'DXT5', DDS_BC7: 'BC7'}
EXPORT_FORMATS = {
    'height': [DDS_L8, PNG16, PNG8],
    'heightfine': [DDS_L8, PNG8],
    'color': [DDS_BC1, DDS_BC3, DDS_BC7, 'PNG', 'JPG', 'TGA', 'BMP'],
    'normal': [DDS_NM, DDS_BC5, 'PNG'],
    'preview': ['PNG', 'JPG'],
    'config': [CFG],
    'atmo': [ATMO_CFG],
    'aurora': [DDS_BC3, 'PNG'],
    'emissive': [DDS_BC1, DDS_BC7, 'PNG'],
    'clouds': [CLOUD_FMT],
    'ring': [DDS_BC3, DDS_BC7, 'PNG'],
}
FMT_EXT = {DDS_BC1: '.dds', DDS_BC3: '.dds', DDS_BC7: '.dds', DDS_NM: '.dds', DDS_BC5: '.dds', DDS_L8: '.dds',
           PNG16: '.png', PNG8: '.png', 'PNG': '.png', 'JPG': '.jpg', 'TGA': '.tga', 'BMP': '.bmp', CFG: '.cfg', ATMO_CFG: '.cfg', CLOUD_FMT: '_clouds.cfg'}
PIL_FMT = {'PNG': 'PNG', 'JPG': 'JPEG', 'TGA': 'TGA', 'BMP': 'BMP'}


def export_target(folder, base, fmt):
    return os.path.join(folder, base + FMT_EXT[fmt])


def planets_file(folder, name):
    return os.path.join(folder, 'planetsList_%s.cfg' % name)


def aurora_files(folder, base, fmt):
    ext = FMT_EXT[fmt]
    return (os.path.join(folder, base + ext), os.path.join(folder, base + '_top' + ext), os.path.join(folder, base + '.cfg'))


def export_aurora(P, name, base, fmt, folder, flip=True, log=print, cfg_path=None, cancel=None):
    lp, tp, cp = aurora_files(folder, base, fmt)
    log('making the aurora at %d x %d' % (aurora_entry(P.get('aurora'))['size'], aurora_entry(P.get('aurora'))['size'] // 2))
    low, top = aurora_maps(P, cancel=cancel)
    save_aurora(low, lp, fmt, flip)
    save_aurora(top, tp, fmt, flip)
    del low, top
    with open(cp, 'w', newline='\n') as f:
        f.write(aurora_cfg(P, name, tex_path(folder, base, cfg_path), tex_path(folder, base + '_top', cfg_path)))
    return [lp, tp, cp]


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
    if files.get('emissive'):
        mods += [t * 2 + 'VertexColorMapEmissive', t * 2 + '{',
                 t * 3 + 'blendMode = Additive',
                 t * 3 + 'map = ' + tex_path(folder, files['emissive'], base),
                 t * 3 + 'brightness = 1',
                 t * 3 + 'order = 9999994',
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
        L += [t + '}']
        if files.get('emissive'):
            L += [t + 'VertexColorMapEmissive', t + '{', t * 2 + 'blendMode = Additive',
                  t * 2 + 'map = ' + tex_path(folder, files['emissive'], base), t * 2 + 'brightness = 1', t + '}']
        L += ['}']
    if has_lava_ocean(P):
        lc, hc, cc = [list(v) for v in lava_paint(P)]
        dk = [v * 0.55 for v in lc]
        L += ['Ocean', '{', t + 'ocean = true', t + 'density = 2.6', t + 'oceanColor = ' + col(lc), '',
              t + 'Material', t + '{', t * 2 + 'color = ' + col(lc), t * 2 + 'colorFromSpace = ' + col(dk), t + '}', '',
              t + 'Fog', t + '{', t * 2 + 'fogColorStart = ' + col(hc), t * 2 + 'fogColorEnd = ' + col(cc), t + '}']
        if files.get('emissive'):
            L += ['', t + 'Mods', t + '{', t * 2 + 'VertexColorMapEmissive', t * 2 + '{', t * 3 + 'blendMode = Additive',
                  t * 3 + 'map = ' + tex_path(folder, files['emissive'], base), t * 3 + 'brightness = 1',
                  t * 3 + 'order = 9999994', t * 3 + 'enabled = true', t * 2 + '}', t + '}']
        L += ['}']
    elif P['shape']['ocean']:
        C = P['colors']
        L += ['Ocean', '{', t + 'ocean = true', t + 'density = 1', t + 'oceanColor = ' + col(C['deep']), '',
              t + 'Material', t + '{', t * 2 + 'color = ' + col(C['shallow']), t * 2 + 'colorFromSpace = ' + col(C['deep']), t + '}', '',
              t + 'Fog', t + '{', t * 2 + 'fogColorStart = ' + col(C['shallow']), t * 2 + 'fogColorEnd = ' + col(C['deep']), t + '}', '}']
    out = '\n'.join(L) + '\n'
    if files.get('ring') and has_rings(P):
        out += ring_snippet(P, tex_path(folder, os.path.splitext(files['ring'])[0], base))
    return out


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
        elif kind == 'ring':
            rp = os.path.join(src_dir, name + '_ring.png')
            if not os.path.isfile(rp):
                log('no ring texture in this build - skipped')
                continue
            r = np.asarray(Image.open(rp).convert('RGBA'))
            if fmt == DDS_BC7:
                save_bc(np.ascontiguousarray(r), path, 'BC7')
            elif fmt.startswith('DDS'):
                save_mips(Image.fromarray(r, 'RGBA'), path, 'DXT5')
            else:
                Image.fromarray(r, 'RGBA').save(path, 'PNG')
        elif kind == 'emissive':
            ep = os.path.join(src_dir, name + '_emissive.png')
            if not os.path.isfile(ep):
                log('no lava glow in this build - skipped')
                continue
            em = np.asarray(Image.open(ep).convert('RGB'))
            if size and size != em.shape[1]:
                em = np.asarray(Image.fromarray(em).resize((size, size // 2), Image.LANCZOS))
            if fmt.startswith('DDS'):
                save_colour_dds(em, path, DDS_CODEC.get(fmt, 'DXT1'), flip)
            else:
                Image.fromarray(em).save(path, 'PNG')
        elif kind == 'clouds':
            if not has_clouds(P):
                log('no clouds on this planet - skipped')
                continue
            for w in export_clouds(P, name, base, folder, flip, log, cfg_path):
                written.append(w)
                log('exported ' + w)
            continue
        elif kind == 'aurora':
            if not has_aurora(P):
                log('no aurora on this planet - skipped')
                continue
            for w in export_aurora(P, name, base, fmt, folder, flip, log, cfg_path):
                written.append(w)
                log('exported ' + w)
            continue
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
            files = {k: names[k] for k in ('height', 'heightfine', 'color', 'normal', 'emissive') if k in names and names[k].lower().endswith('.dds')}
            if 'emissive' in files and not os.path.isfile(os.path.join(src_dir, name + '_emissive.png')):
                del files['emissive']
            if 'ring' in names and has_rings(P) and os.path.isfile(os.path.join(src_dir, name + '_ring.png')):
                files['ring'] = names['ring']
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
    col, gx, gy, em = make_colour(P, hm, mk, W, cancel, workers=workers, noise_cache=nc)
    return col, hm, gx, gy, em


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
    col, gx, gy, em = make_colour(P, hm, mk, W, progress=prog('color'))
    print('color done', flush=True)
    del mk
    lo, hi = save_height16(hm, os.path.join(od, P['name'] + '_height.png'))
    Image.fromarray(col).save(os.path.join(od, P['name'] + '_color.png'))
    ep = os.path.join(od, P['name'] + '_emissive.png')
    if em is not None:
        Image.fromarray(em).save(ep)
    elif os.path.isfile(ep):
        os.remove(ep)
    rp = os.path.join(od, P['name'] + '_ring.png')
    if has_rings(P):
        Image.fromarray(ring_image(P), 'RGBA').save(rp)
    elif os.path.isfile(rp):
        os.remove(rp)
    info = {'min_m': lo, 'max_m': hi, 'radius': P['radius'], 'ocean': P['shape']['ocean'], 'res': W, 'version': APP_VERSION}
    with open(os.path.join(od, P['name'] + '_info.json'), 'w') as f:
        json.dump(info, f, indent=1)
    with open(os.path.join(od, P['name'] + '_preset.json'), 'w') as f:
        json.dump(P, f, indent=1)
    print('height range: %.0f m to %.0f m' % (lo, hi), flush=True)
    print('files done', flush=True)
    write_preview(P, col, hm, os.path.join(od, P['name'] + '_preview.png'), em)
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
    if a.emissive != 'none' and os.path.isfile(os.path.join(src, P['name'] + '_emissive.png')):
        jobs.append(('emissive', P['name'] + '_emissive', {'dds': DDS_BC1, 'bc7': DDS_BC7, 'png': 'PNG'}[a.emissive]))
    if a.preview != 'none':
        jobs.append(('preview', P['name'] + '_preview', {'png': 'PNG', 'jpg': 'JPG'}[a.preview]))
    if a.atmo != 'none' and has_atmo(P):
        jobs.append(('atmo', P['name'] + '_atmo', ATMO_CFG))
    if a.clouds != 'none' and has_clouds(P):
        jobs.append(('clouds', P['name'], CLOUD_FMT))
    if a.aurora != 'none' and has_aurora(P):
        jobs.append(('aurora', P['name'] + '_aurora', {'dds': DDS_BC3, 'png': 'PNG'}[a.aurora]))
    if a.ring != 'none' and has_rings(P):
        jobs.append(('ring', P['name'] + '_ring', {'dds': DDS_BC3, 'bc3': DDS_BC3, 'bc7': DDS_BC7, 'png': 'PNG'}[a.ring]))
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
    e.add_argument('--aurora', default='dds', choices=['dds', 'png', 'none'])
    e.add_argument('--clouds', default='tvc', choices=['tvc', 'none'])
    e.add_argument('--emissive', default='dds', choices=['dds', 'bc7', 'png', 'none'])
    e.add_argument('--ring', default='dds', choices=['dds', 'bc3', 'bc7', 'png', 'none'])
    e.add_argument('--size', type=int, default=None)
    e.add_argument('--no-flip', action='store_true')
    n = sp.add_parser('new')
    n.add_argument('name')
    n.add_argument('--template', default=None)
    a = ap.parse_args()
    {'make': cmd_make, 'export': cmd_export, 'new': cmd_new}[a.cmd](a)


if __name__ == '__main__':
    main()
