import os, copy, json, math
import numpy as np
from PIL import Image

SOURCES = (('auto', 'Lava if there is any, else the sea'), ('lava', 'Lava (fields, flows, rivers, lava sea)'),
           ('liquid', 'The sea (any deadly liquid)'), ('both', 'Lava and the sea'), ('rivers', 'Only the rivers'))
SIZES = (1024, 2048, 4096)
DEFAULTS = {'enabled': False, 'source': 'auto', 'temp': 1500.0, 'spread_km': 5.0, 'reach': 3000.0, 'sum': False, 'rivers': True, 'size': 2048}
RANGES = {'temp': (1.0, 100000.0), 'spread_km': (0.0, 2000.0), 'reach': (10.0, 1000000.0)}
WORK_W = 1024


def entry(a):
    e = copy.deepcopy(DEFAULTS)
    a = a if isinstance(a, dict) else {}
    for k, v in a.items():
        if k in e:
            e[k] = copy.deepcopy(v)
    e['enabled'] = bool(e['enabled'])
    e['sum'] = bool(e['sum'])
    e['rivers'] = bool(e['rivers'])
    for k, (lo, hi) in RANGES.items():
        try:
            e[k] = max(lo, min(hi, float(e[k])))
        except (TypeError, ValueError):
            e[k] = DEFAULTS[k]
    try:
        e['size'] = int(e['size'])
    except (TypeError, ValueError):
        e['size'] = DEFAULTS['size']
    if e['size'] not in SIZES:
        e['size'] = min(SIZES, key=lambda s: abs(s - e['size']))
    e['source'] = e['source'] if e['source'] in dict(SOURCES) else 'auto'
    return e


def has(P):
    return bool((P.get('hazard') or {}).get('enabled'))


def source(T, P):
    e = entry(P.get('hazard'))
    if e['source'] != 'auto':
        return e['source']
    return 'lava' if (T.has_lava(P) or T.is_lava_sea(P) or T.has_emission(P)) else 'liquid'


def resize_f(a, W, H):
    if a.shape[:2] == (H, W):
        return a.astype(np.float32)
    return np.asarray(Image.fromarray(a.astype(np.float32), 'F').resize((W, H), Image.BOX if a.shape[1] > W else Image.BILINEAR))


def rivers_used(T, P, Pr=None):
    Pr = P if Pr is None else Pr
    if float((Pr.get('water') or {}).get('rivers', 0)) <= 0:
        return False
    src = source(T, P)
    if src == 'rivers':
        return True
    if not entry(P.get('hazard'))['rivers']:
        return False
    return src in ('liquid', 'both') or T.lava_rivers(Pr)


def river_mask(T, Pr, W):
    NET = T.river_network(Pr)
    if NET is None:
        return None
    H = W // 2
    ch = np.zeros((H, W), np.float16)
    X, Y, Z = T.rows_xyz(W, H, 0, H)
    T.apply_rivers(Pr, NET, np.zeros((H, W), np.float32), [None, None, None, ch], X, Y, Z, W, H, 0)
    return np.clip(ch.astype(np.float32) / np.float32(0.15), 0, 1)


def raw_mask(T, P, h, em, riv=None):
    src = source(T, P)
    H, W = h.shape
    m = np.zeros((H, W), np.float32)
    if riv is not None:
        m = np.maximum(m, riv)
    sea = T.sea_mask(P, h)
    if src in ('lava', 'both'):
        if em is not None:
            g = resize_f(np.asarray(em, np.float32).max(2), W, H)
            m = np.maximum(m, np.clip((g - 30.0) / 90.0, 0, 1))
        if sea is not None and T.is_lava_sea(P):
            m = np.maximum(m, sea.astype(np.float32))
    if src in ('liquid', 'both') and sea is not None and T.has_liquid(P):
        m = np.maximum(m, sea.astype(np.float32))
    return m


def heat_map(T, P, h, em, W, Pr=None):
    e = entry(P.get('hazard'))
    H = W // 2
    hs = resize_f(h, W, H)
    riv = river_mask(T, P if Pr is None else Pr, W) if rivers_used(T, P, Pr) else None
    m = raw_mask(T, P, hs, em, riv)
    px_m = 2 * math.pi * float(P['radius']) / W
    sig = e['spread_km'] * 1000.0 / px_m
    out = m
    if sig > 0.3:
        b = T.gblur(m, sig)
        out = np.maximum(m, np.clip(b * 1.5, 0, 1))
    return np.clip(out, 0, 1).astype(np.float32), hs, m


def heights(T, P, hs, m):
    sea = T.sea_mask(P, hs)
    surf = hs if sea is None else np.where(sea, np.float32(0), hs)
    lo = float(hs.min())
    v = surf[m > 0.5]
    top = float(np.percentile(v, 99)) if v.size >= 8 else 0.0
    return lo, top


def curve(P, lo, top):
    e = entry(P.get('hazard'))
    R = float(P['radius'])
    a = round(R + min(lo, top) - 100.0)
    b = round(R + top)
    c = round(R + top + e['reach'])
    return [('key', '%d 1 0 0' % a), ('key', '%d 1 0 0' % max(b, a + 1)), ('key', '%d 0 0 0' % max(c, b + 2))]


def node(P, path, lo, top):
    e = entry(P.get('hazard'))
    return ['HazardousBody', [['HazardousArea', [('ambientTemp', '%g' % e['temp']), ('sumTemp', 'true' if e['sum'] else 'false'),
                                                 ('HeatMap', path), ['AltitudeCurve', curve(P, lo, top)]]]]]


def node_text(P, path, lo, top):
    t = '\t'
    L = ['HazardousBody', '{', t + 'HazardousArea', t + '{', t * 2 + 'ambientTemp = %g' % entry(P.get('hazard'))['temp'],
         t * 2 + 'sumTemp = ' + ('true' if entry(P.get('hazard'))['sum'] else 'false'), t * 2 + 'HeatMap = ' + path,
         t * 2 + 'AltitudeCurve', t * 2 + '{']
    L += [t * 3 + '%s = %s' % kv for kv in curve(P, lo, top)]
    L += [t * 2 + '}', t + '}', '}']
    return '\n'.join(L) + '\n'


def load_build(T, src_dir, name):
    hm, info = T.load_height(src_dir, name)
    ep = os.path.join(src_dir, name + '_emissive.png')
    em = np.asarray(Image.open(ep).convert('RGB')) if os.path.isfile(ep) else None
    return hm, em


def from_build(T, P, src_dir, name, W=None):
    hm, em = load_build(T, src_dir, name)
    hmap, hs, m = heat_map(T, P, hm, em, W or entry(P.get('hazard'))['size'], T.bio_built(P, src_dir))
    lo, top = heights(T, P, hs, m)
    return hmap, lo, top, float(m.mean())


_CACHE = {}


def build_info(T, P, build):
    name = P['name']
    hp = os.path.join(build, name + '_height.png')
    key = json.dumps([hp, os.path.getmtime(hp), entry(P.get('hazard')), P['shape'], P['radius'], P.get('lava_ocean'), P.get('water'), P.get('emission')], sort_keys=True, default=str)
    if _CACHE.get('key') != key:
        _CACHE.update(key=key, info=from_build(T, P, build, name, WORK_W)[1:])
    return _CACHE['info']


def share(m):
    H = m.shape[0]
    w = np.cos((0.5 - (np.arange(H) + 0.5) / H) * math.pi)
    return float((m.mean(1) * w).sum() / w.sum())


def overlay(col, hmap):
    H, W = hmap.shape
    c = np.asarray(Image.fromarray(np.asarray(col, np.uint8)).resize((W, H), Image.BILINEAR), np.float32) * np.float32(0.55)
    a = hmap[..., None]
    hot = np.array([255, 70, 20], np.float32) * (0.6 + 0.4 * a)
    return np.clip(c * (1 - a * 0.8) + hot * a * 0.8, 0, 255).astype(np.uint8)
