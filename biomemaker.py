import re, copy
import numpy as np

W_MAP = 1024
OWN_SHARE = 0.5
WHERE = (('any', 'Anywhere'), ('land', 'On land'), ('ocean', 'In the ocean'), ('shore', 'On the shores'),
         ('ice', 'On ice and snow'), ('lava', 'On glowing lava'), ('craters', 'In big craters'), ('features', 'In placed features'))
PALETTE = ((200, 200, 60), (50, 50, 200), (200, 60, 60), (60, 200, 200), (60, 200, 60), (200, 60, 200), (230, 140, 40),
           (140, 40, 230), (40, 140, 230), (230, 230, 230), (120, 120, 40), (40, 120, 120), (120, 40, 120), (240, 100, 140),
           (100, 240, 140), (140, 100, 240), (170, 110, 60), (60, 110, 170), (110, 170, 60), (20, 20, 20), (250, 200, 160),
           (160, 250, 200), (200, 160, 250), (90, 90, 90))
BIOME = {'id': 0, 'name': 'Biome', 'value': 1.0, 'color': None, 'where': 'any', 'feature': -1, 'crater_km': 0.0,
         'hmin': None, 'hmax': None, 'latmin': None, 'latmax': None, 'both': True, 'slopemin': None, 'slopemax': None}
RANGES = ('hmin', 'hmax', 'latmin', 'latmax', 'slopemin', 'slopemax')


def num_or_none(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        return None


def biome_entry(b):
    e = copy.deepcopy(BIOME)
    e.update({k: copy.deepcopy(v) for k, v in (b if isinstance(b, dict) else {}).items() if k in BIOME})
    e['id'] = int(e['id'] or 0)
    e['name'] = ' '.join(str(e['name'] or 'Biome').split()) or 'Biome'
    e['value'] = num_or_none(e['value']) if num_or_none(e['value']) is not None else 1.0
    e['where'] = e['where'] if e['where'] in dict(WHERE) else 'any'
    e['feature'] = int(num_or_none(e['feature']) if num_or_none(e['feature']) is not None else -1)
    e['crater_km'] = max(0.0, num_or_none(e['crater_km']) or 0.0)
    e['both'] = bool(e['both'])
    for k in RANGES:
        e[k] = num_or_none(e[k])
    if e['color'] is not None:
        try:
            e['color'] = [int(max(0, min(255, round(float(c))))) for c in e['color']][:3]
        except (TypeError, ValueError):
            e['color'] = None
    return e


def bm_entry(d):
    d = d if isinstance(d, dict) else {}
    out = {'biomes': [biome_entry(b) for b in d.get('biomes') or []], 'strokes': []}
    used = set()
    for b in out['biomes']:
        if b['id'] <= 0 or b['id'] in used:
            b['id'] = max(used | {0}) + 1
        used.add(b['id'])
    for s in d.get('strokes') or []:
        try:
            i, la, lo, r = int(s[0]), float(s[1]), float(s[2]) % 360.0, max(0.01, float(s[3]))
        except (TypeError, ValueError, IndexError):
            continue
        if i == 0 or i in used:
            out['strokes'].append([i, max(-90.0, min(90.0, la)), lo, r])
    return out


def has(P):
    return bool(bm_entry(P.get('biome_map'))['biomes'])


def new_id(bm):
    return max([b['id'] for b in bm['biomes']] + [0]) + 1


def cfg_name(display, taken):
    n = ''.join(w[:1].upper() + w[1:] for w in re.split(r'[^A-Za-z0-9]+', display) if w) or 'Biome'
    if n[0].isdigit():
        n = 'B' + n
    base, k = n, 2
    while n in taken:
        n = '%s%d' % (base, k)
        k += 1
    taken.add(n)
    return n


def colours(biomes):
    used, out = set(), []
    for b in biomes:
        c = tuple(b['color']) if b['color'] else None
        if c is None or c in used:
            c = next((p for p in PALETTE if p not in used), None)
            k = 0
            while c is None or c in used:
                c = ((37 * k + 80) % 256, (91 * k + 30) % 256, (151 * k + 200) % 256)
                k += 1
        used.add(c)
        out.append(c)
    return out


def kop_list(P):
    bl = bm_entry(P.get('biome_map'))['biomes']
    taken = set()
    return [(cfg_name(b['name'], taken), b['name'], b['value'], c) for b, c in zip(bl, colours(bl))]


def grid(W):
    H = W // 2
    lat = 90.0 - (np.arange(H) + 0.5) / H * 180.0
    lon = (np.arange(W) + 0.5) / W * 360.0
    LA = np.repeat(lat[:, None], W, 1).astype(np.float32)
    LO = np.repeat(lon[None, :], H, 0).astype(np.float32)
    rl, ro = np.radians(LA), np.radians(LO)
    return LA, LO, np.cos(rl) * np.cos(ro), np.cos(rl) * np.sin(ro), np.sin(rl)


def caps(G, centres, angles, out=None):
    LA, LO, X, Y, Z = G
    H = LA.shape[0]
    m = np.zeros(LA.shape, bool) if out is None else out
    for (la, lo), a in zip(centres, angles):
        a = float(min(a, np.pi))
        r0 = int(max(0, np.floor((90.0 - la - np.degrees(a)) / 180.0 * H) - 1))
        r1 = int(min(H, np.ceil((90.0 - la + np.degrees(a)) / 180.0 * H) + 1))
        if r1 <= r0:
            continue
        cl = np.cos(np.radians(la))
        v = (cl * np.cos(np.radians(lo)), cl * np.sin(np.radians(lo)), np.sin(np.radians(la)))
        d = X[r0:r1] * v[0] + Y[r0:r1] * v[1] + Z[r0:r1] * v[2]
        m[r0:r1] |= d >= np.cos(a)
    return m


def rule_mask(L, G, b):
    LA = G[0]
    m = np.ones(LA.shape, bool)
    w = b['where']
    if w in ('land', 'ocean', 'shore', 'ice', 'lava'):
        layer = L['masks'].get('ocean' if w == 'land' else w)
        if layer is None:
            m[:] = w == 'land'
        else:
            m &= ~layer if w == 'land' else layer
    elif w == 'craters':
        cr = L.get('craters')
        if cr is None or not len(cr['D']):
            m[:] = False
        else:
            keep = (cr['D'] >= b['crater_km']) & cr['seen']
            n = cr.get('n', 0) if cr.get('owner') is not None and cr['owner'].shape == LA.shape else 0
            got = np.concatenate([[False], keep[:n]])[cr['owner'] + 1] if n else np.zeros(LA.shape, bool)
            keep[:n] = False
            v = cr['v'][keep]
            ang = cr['D'][keep] * 500.0 / cr['R'][keep]
            cen = zip(np.degrees(np.arcsin(np.clip(v[:, 2], -1, 1))), np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 360.0)
            m &= caps(G, list(cen), ang, out=got) if len(v) else got
    elif w == 'features':
        fs = L.get('features') or []
        if 0 <= b['feature'] < len(fs):
            fs = [fs[b['feature']]]
        m &= caps(G, [(f[1], f[2]) for f in fs], [f[3] * 500.0 / L['R'] for f in fs]) if fs else False
    h, s = L['h'], L['slope']
    if b['hmin'] is not None:
        m &= h >= b['hmin']
    if b['hmax'] is not None:
        m &= h < b['hmax']
    if b['slopemin'] is not None:
        m &= s >= b['slopemin']
    if b['slopemax'] is not None:
        m &= s < b['slopemax']
    la = np.abs(LA) if b['both'] else LA
    if b['latmin'] is not None:
        m &= la >= b['latmin']
    if b['latmax'] is not None:
        m &= la <= b['latmax']
    return m


def assign(L, bm):
    W = L['h'].shape[1]
    G = grid(W)
    bl = bm['biomes']
    idx = np.full(L['h'].shape, -1, np.int16)
    for i, b in enumerate(bl):
        sel = (idx < 0) & rule_mask(L, G, b)
        idx[sel] = i
    base = idx.copy()
    pos = {b['id']: i for i, b in enumerate(bl)}
    for bid, la, lo, r in bm['strokes']:
        m = caps(G, [(la, lo)], [r * 1000.0 / L['R']])
        idx[m] = base[m] if bid == 0 else pos.get(bid, -1)
    return idx, G


def areas(idx, n, G):
    w = np.cos(np.radians(G[0]))
    tot = float(w.sum())
    out = [float(w[idx == i].sum()) / tot for i in range(n)]
    return out, float(w[idx < 0].sum()) / tot


def image(idx, bl, fill_last=True):
    cols = np.array(colours(bl) + [(0, 0, 0)], np.uint8)
    k = idx.astype(np.int32)
    if fill_last and bl:
        k = np.where(k < 0, len(bl) - 1, k)
    else:
        k = np.where(k < 0, len(bl), k)
    return cols[k]


def crater_rim_seen(h, v, a, size_m, cover=None, steep=0.018, only=None):
    H, W = h.shape
    lat = np.arcsin(np.clip(v[:, 2], -1, 1))
    lon = np.arctan2(v[:, 1], v[:, 0]) % (2 * np.pi)
    la = np.radians(90.0 - (np.arange(H) + 0.5) / H * 180.0)
    lo = (np.arange(W) + 0.5) / W * 2 * np.pi
    seen = np.ones(len(v), bool)
    for k in (range(len(v)) if only is None else np.where(only)[0]):
        if a[k] * W / (2 * np.pi) < 2:
            if cover is not None:
                seen[k] = not cover[min(H - 1, int((np.pi / 2 - lat[k]) / np.pi * H)), int(lon[k] / (2 * np.pi) * W) % W]
            continue
        e = min(a[k] * 2.05, np.pi / 2)
        r0 = max(0, int((np.pi / 2 - lat[k] - e) / np.pi * H) - 1)
        r1 = min(H, int(np.ceil((np.pi / 2 - lat[k] + e) / np.pi * H)) + 1)
        if abs(lat[k]) + e >= np.pi / 2 - 0.01:
            cols = np.arange(W)
        else:
            dl = e / np.cos(abs(lat[k]) + e)
            cols = np.arange(int(np.floor((lon[k] - dl) / (2 * np.pi) * W)) - 1, int(np.ceil((lon[k] + dl) / (2 * np.pi) * W)) + 2) % W
        cl = np.cos(la[r0:r1])[:, None]
        px, py, pz = cl * np.cos(lo[cols])[None], cl * np.sin(lo[cols])[None], np.sin(la[r0:r1])[:, None]
        r = np.arccos(np.clip(px * v[k, 0] + py * v[k, 1] + pz * v[k, 2], -1, 1)) / a[k]
        hh = h[r0:r1][:, cols].astype(np.float64)
        ring, out, fl = (r > 0.85) & (r < 1.2), (r > 1.25) & (r < 2.0), r < 0.5
        if fl.sum() < 2 or ring.sum() < 8 or out.sum() < 12:
            continue
        e1 = np.cross([0.0, 0.0, 1.0] if abs(v[k, 2]) < 0.9 else [1.0, 0.0, 0.0], v[k])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(v[k], e1)
        x = (px * e1[0] + py * e1[1] + pz * e1[2]) / a[k]
        y = np.broadcast_to((px * e2[0] + py * e2[1] + pz * e2[2]) / a[k], x.shape)
        A = np.stack([np.ones(x.shape), x, y, x * x, x * y, y * y], -1)
        if cover is not None:
            cv = cover[r0:r1][:, cols]
            crest = (r > 0.95) & (r < 1.3)
            sc = ((np.arctan2(y[crest], x[crest]) + np.pi) / (2 * np.pi) * 8).astype(int) % 8
            cc = cv[crest]
            rim_dry = sum(1 for i in range(8) if (sc == i).any() and cc[sc == i].mean() < 0.5) >= 6
            if cv[fl].mean() > 0.5 or not rim_dry:
                seen[k] = rim_dry
                continue
            ring, out, fl = ring & ~cv, out & ~cv, fl & ~cv
            if out.sum() < 12:
                continue
        sec = ((np.arctan2(y[ring], x[ring]) + np.pi) / (2 * np.pi) * 8).astype(int) % 8
        rough = float((hh[out] - A[out] @ np.linalg.lstsq(A[out], hh[out], rcond=None)[0]).std())
        hr = hh[ring]
        rims = [float(hr[sec == i].mean()) for i in range(8) if (sec == i).any()]
        if len(rims) >= 6:
            seen[k] = float(np.median(rims)) - float(hh[fl].mean()) >= max(steep * float(size_m[k]), rough)
    return seen


def crater_layer(h, v, D, Rl, feats, R, cover=None, owner=None, share=None):
    v = np.asarray(v, np.float64).reshape(-1, 3)
    D = np.asarray(D, np.float64).ravel()
    Rl = np.broadcast_to(np.asarray(Rl, np.float64), D.shape).copy()
    n = len(D)
    if n and owner is not None:
        seen = np.asarray(share, np.float64) >= OWN_SHARE
        test = np.zeros(n, bool)
        if cover is not None:
            o = owner.ravel()
            on = o >= 0
            w = np.repeat(np.cos(np.radians(90.0 - (np.arange(owner.shape[0]) + 0.5) / owner.shape[0] * 180.0)), owner.shape[1])[on]
            tot = np.bincount(o[on], w, n)
            wet = np.bincount(o[on], w * cover.ravel()[on], n)
            test |= seen & (wet > 0.5 * np.maximum(tot, 1e-12))
        test |= seen
        if test.any():
            rim = crater_rim_seen(np.asarray(h, np.float32), v, D * 500.0 / Rl, D * 1000.0, cover, only=test)
            seen[test] &= rim[test]
    elif n:
        seen = crater_rim_seen(np.asarray(h, np.float32), v, D * 500.0 / Rl, D * 1000.0, cover)
    else:
        seen = np.ones(0, bool)
    if feats:
        la, lo = np.radians([f[1] for f in feats]), np.radians([f[2] for f in feats])
        v = np.concatenate([v, np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], 1)])
        D = np.concatenate([D, [float(f[3]) for f in feats]])
        Rl = np.concatenate([Rl, np.full(len(feats), float(R))])
        seen = np.concatenate([seen, np.ones(len(feats), bool)])
    if not len(D):
        return None
    return {'v': v, 'D': D, 'R': Rl, 'seen': seen, 'n': n, 'owner': owner}


def big_crater_km(cr, R, cover=0.15):
    D = np.sort(np.asarray(cr['D'], np.float64)[cr['seen']])[::-1]
    if not len(D):
        return 0.0
    part = np.cumsum(np.pi * (D * 500.0) ** 2) / (4 * np.pi * R * R)
    cover = min(cover, float(part[-1]) * 0.5)
    d = float(D[min(int(np.searchsorted(part, cover)), len(D) - 1)])
    p = 10.0 ** (np.floor(np.log10(d)) - 1)
    return float('%.2g' % (np.floor(d / p + 1e-9) * p))


def relief(h):
    H = h.shape[0]
    cl = np.maximum(np.cos(np.radians(90.0 - (np.arange(H) + 0.5) / H * 180.0)), 0.1)[:, None]
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / cl
    gy = np.zeros_like(gx)
    gy[1:-1] = h[2:] - h[:-2]
    g = gx + gy
    return np.clip(0.5 + g / (2.5 * float(np.percentile(np.abs(g), 98)) + 1e-6), 0, 1).astype(np.float32)


def share(mask):
    w = np.cos(np.radians(90.0 - (np.arange(mask.shape[0]) + 0.5) / mask.shape[0] * 180.0))[:, None]
    return float((mask * w).sum() / (w.sum() * mask.shape[1]))


def kop_biomes(S, P, build, with_map):
    bl = kop_list(P)
    if not (with_map and build):
        return bl, None
    bm = bm_entry(P.get('biome_map'))
    idx, G = assign(S.bio_layers(P, build, W_MAP), bm)
    return bl, image(idx, bm['biomes'])


def biomes_cfg(P):
    return biomes_text(kop_list(P))


def biomes_text(bl):
    T = '\t'
    L = ['Biomes', '{']
    for n, d, v, c in bl:
        L += [T + 'Biome', T + '{', T * 2 + 'name = ' + n, T * 2 + 'displayName = ' + d,
              T * 2 + 'value = %g' % v, T * 2 + 'color = ' + ','.join('%.4f' % (x / 255.0) for x in c) + ',1', T + '}']
    return '\n'.join(L + ['}']) + '\n'


def suggest(S, P, build):
    L = S.bio_layers(P, build, W_MAP)
    out = []
    for i, b in enumerate(S.bio_suggest(P, L)):
        b = biome_entry(dict(b, id=i + 1))
        out.append(b)
    return {'biomes': out, 'strokes': []}
