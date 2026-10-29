import os, re, copy, time, shutil, struct
import numpy as np
from PIL import Image

G_NEWTON = 6.67430e-11
G0 = 9.80665
R_GAS = 8.314462618
ATMO_DEPTH = float(np.log(1e4))
STOCK_MASS = {'Sun': 1.7565459e28, 'Kerbol': 1.7565459e28, 'Moho': 2.5263314e21, 'Eve': 1.2243980e23, 'Kerbin': 5.2915158e22,
              'Mun': 9.7599066e20, 'Minmus': 2.6457580e19, 'Duna': 4.5154270e21, 'Ike': 2.7821615e20, 'Dres': 3.2190937e20,
              'Jool': 4.2332127e24, 'Laythe': 2.9397311e22, 'Vall': 3.1087655e21, 'Tylo': 4.2332127e22, 'Eeloo': 1.1149224e21}
TEMP_SHAPE = ((0.0, 1.0), (0.364, 0.766), (0.727, 0.872), (1.0, 1.17))
BIOME_COLOURS = ((200, 200, 60), (50, 50, 200), (200, 60, 60), (60, 200, 200), (60, 200, 60), (200, 60, 200),
                 (230, 140, 40), (140, 40, 230), (40, 140, 230), (230, 230, 230))
GROUND = {
    'Moho rock': [('factor', '10'), ('albedoBrightness', '1'), ('steepPower', '1'), ('steepTex', 'BUILTIN/MohoSteep'),
                  ('steepBumpMap', 'BUILTIN/MohoSteep_nrm'), ('steepNearTiling', '2000'), ('steepTiling', '20'),
                  ('lowTex', 'BUILTIN/MohoLow'), ('lowTiling', '100000'), ('midTex', 'BUILTIN/MohoMid'),
                  ('midBumpMap', 'BUILTIN/MohoMid_nrm'), ('midTiling', '100000'), ('midBumpTiling', '100000'),
                  ('highTex', 'BUILTIN/MohoMid'), ('highTiling', '100000'), ('lowStart', '0'), ('lowEnd', '0.3'),
                  ('highStart', '1'), ('highEnd', '1'), ('globalDensity', '0'), ('fogColorRamp', 'BUILTIN/AerialRampKerbin2')],
    'Dres ice and rock': [('factor', '9'), ('albedoBrightness', '1'), ('steepPower', '2'), ('steepTex', 'BUILTIN/dresSteepDiffuse'),
                          ('steepBumpMap', 'BUILTIN/DresSteepNRM'), ('steepNearTiling', '200'), ('steepTiling', '40'),
                          ('lowTex', 'BUILTIN/dresMid'), ('lowTiling', '30000'), ('midTex', 'BUILTIN/dresMid'),
                          ('midBumpMap', 'BUILTIN/dresMidNRM'), ('midTiling', '30000'), ('midBumpTiling', '30000'),
                          ('highTex', 'BUILTIN/dresHigh'), ('highTiling', '3000'), ('lowStart', '0'), ('lowEnd', '0.2'),
                          ('highStart', '0.7'), ('highEnd', '1'), ('globalDensity', '0'), ('fogColorRamp', 'BUILTIN/AerialRampKerbin2')],
}

PLANET = {'display_name': '', 'description': '', 'parent': 'Sun', 'gravity': 0.8, 'rotation': 6.0,
          'tidally_locked': False, 'initial_rotation': 0.0, 'albedo': 0.3,
          'sma': 13599840.0, 'ecc': 0.0, 'inc': 0.0, 'lan': 0.0, 'argpe': 0.0, 'mean_anomaly': 0.0, 'epoch': 0.0,
          'atmo': False, 'pressure': 101.325, 'temperature': 288.0, 'atmo_height': 70.0, 'molar_mass': 0.029, 'adiabatic': 1.4,
          'ground': 'Moho rock', 'biomes': True, 'mod': '', 'opts': {}}
LIMITS = {'gravity': (0.0, None), 'rotation': (0.01, None), 'ecc': (0.0, 0.99), 'pressure': (0.001, None), 'temperature': (1.0, None),
          'atmo_height': (1.0, None), 'molar_mass': (1e-4, None), 'adiabatic': (1.0, None), 'radius': (1.0, None)}


def planet_base(S):
    b = copy.deepcopy(PLANET)
    b.update(copy.deepcopy(getattr(S, 'KOP_DEFAULTS', {})))
    return b


def planet_entry(p, base=None):
    e = copy.deepcopy(base or PLANET)
    for k, v in (p if isinstance(p, dict) else {}).items():
        if k not in e:
            continue
        d = e[k]
        if isinstance(d, dict):
            e[k] = {str(q): [bool(s[0]), str(s[1] if len(s) > 1 else '')] for q, s in (v.items() if isinstance(v, dict) else [])
                    if isinstance(s, (list, tuple)) and s}
        elif isinstance(d, bool):
            e[k] = bool(v)
        elif isinstance(d, str):
            e[k] = str(v or '')
        else:
            try:
                e[k] = float(v)
            except (TypeError, ValueError):
                pass
    for k, (lo, hi) in LIMITS.items():
        if k in e:
            e[k] = max(lo, e[k]) if hi is None else min(max(e[k], lo), hi)
    e['parent'] = e['parent'].strip() or 'Sun'
    if e['ground'] not in GROUND:
        e['ground'] = 'Moho rock'
    return e


def entry(S, P):
    e = planet_entry(P.get('planet'), planet_base(S))
    e.update(S.kop_prepare(P))
    if e['gravity'] <= 0:
        e['gravity'] = float(P.get('radius', 600000)) / 600000.0
    if not getattr(S, 'KOP_ATMO', True):
        e['atmo'] = False
    return e


def biome_set(rows, masks=None):
    bl = [(n, d, v, BIOME_COLOURS[i % len(BIOME_COLOURS)]) for i, (n, d, v) in enumerate(rows)]
    if masks is None:
        return bl, None
    img = np.zeros(masks[0].shape + (3,), np.uint8)
    for b, m in zip(bl, masks):
        img[m] = b[3]
    return bl, img


def lat_grid(W):
    H = W // 2
    return np.repeat((90.0 - (np.arange(H) + 0.5) / H * 180.0)[:, None], W, 1)


def nice_up(v):
    if v <= 0:
        return 0
    s = 10 ** max(0, int(np.floor(np.log10(v))) - 1)
    return int(np.ceil(v / s) * s)


def warp_limits(top):
    t = nice_up(max(top, 0.0) * 1.05 + 100)
    return [0, t, t, t * 2, t * 4, t * 8, t * 16, t * 32]


def pqs_distances(R, relief):
    fs = int(round(max(0.1 * R, 7.0 * relief, 2000.0), -2))
    fe = 2 * fs
    return {'sv_start': int(round(0.75 * fs, -2)), 'sv_end': fs, 'pqs_start': fs, 'pqs_end': fe,
            'deactivate': int(round(1.3 * fe)), 'max_level': 9 if R >= 300000 else 8}


def numbers(e, R, g, top_terrain, relief, parent_mass=None, ref='Kerbin'):
    M = g * G0 * R * R / G_NEWTON
    top = e['atmo_height'] * 1000.0 if e['atmo'] else 0.0
    d = {'mass': M, 'density': M / (4.0 / 3.0 * np.pi * R ** 3), 'top': top, 'R': R,
         'mass_ref': M / STOCK_MASS.get(ref, STOCK_MASS['Kerbin']), 'ref': ref,
         'scale_height': top / ATMO_DEPTH if top else 0.0,
         'real_scale_height': R_GAS * e['temperature'] / (e['molar_mass'] * g * G0),
         'warp': warp_limits(max(top, top_terrain)), 'fly': int(round(top / 2.0, -3)) if top else nice_up(max(top_terrain, 1000.0)),
         'space': int(float('%.2g' % (R * 0.5))), 'pqs': pqs_distances(R, relief),
         'hot': '600', 'lapse': '%.5g' % (e['temperature'] * (1 - TEMP_SHAPE[1][1]) / max((top or 1.0) * TEMP_SHAPE[1][0], 1.0)),
         'period': None, 'soi': None, 'parent_mass': parent_mass}
    if parent_mass:
        a = e['sma'] * 1000.0
        d['period'] = 2 * np.pi * np.sqrt(a ** 3 / (G_NEWTON * (parent_mass + M)))
        d['soi'] = a * (M / parent_mass) ** 0.4
    return d


def cfg_num(v):
    v = float('%.7g' % float(v))
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return np.format_float_positional(np.float64(v), trim='-')


def cfg_text(v):
    s = ' '.join(str(v).split())
    return s.replace('{', '(').replace('}', ')').replace('//', '/ /')


def k5(v):
    return '%.5E' % v


def curve_keys(pts):
    out = []
    for i, (h, v) in enumerate(pts):
        t = 0.0 if i in (0, len(pts) - 1) else (pts[i + 1][1] - pts[i - 1][1]) / float(pts[i + 1][0] - pts[i - 1][0])
        out.append(('key', '%d\t%s\t%s\t%s' % (h, cfg_num(v), k5(t), k5(t))))
    return out


def pressure_keys(p0, top, n=None, depth=ATMO_DEPTH):
    H = top / depth
    n = n or max(5, int(round(top / 10000.0)))
    out = []
    for i in range(n):
        h = int(round(top * i / n))
        p = p0 * np.exp(-h / H)
        out.append(('key', '%d\t%s\t%s\t%s' % (h, k5(p), k5(-p / H), k5(-p / H))))
    out.append(('key', '%d\t%s\t%s\t%s' % (int(round(top)), k5(0), k5(0), k5(0))))
    return out


def sun_mult_keys(top):
    return [('key', '0\t1\t0\t0'), ('key', '%d\t0.5\t%s\t%s' % (int(round(top / 2)), k5(-1 / top), k5(-1 / top))),
            ('key', '%d\t0\t0\t0' % int(round(top)))]


def v4(x, a=1):
    return ','.join(cfg_num(round(float(q), 2)) for q in list(x)[:3]) + ',' + cfg_num(a)


def display_name(e, name):
    dn = cfg_text(e['display_name'] or name)
    return dn if '^' in dn else dn + '^N'


def atmo_node(e, top, light):
    t0 = e['temperature']
    temp = [(int(round(top * f / 1000.0)) * 1000, round(t0 * r)) for f, r in TEMP_SHAPE]
    return ['Atmosphere', [
        ('enabled', 'True'), ('oxygen', 'False'), ('altitude', '%d' % int(round(top))), ('adiabaticIndex', cfg_num(e['adiabatic'])),
        ('atmosphereMolarMass', cfg_num(e['molar_mass'])), ('temperatureSeaLevel', cfg_num(t0)),
        ('staticPressureASL', cfg_num(e['pressure'])), ('ambientColor', v4([c * 0.3 for c in light])), ('lightColor', v4(light, 0.5)),
        ['AtmosphereFromGround', [('waveLength', v4(light, 0.5))]],
        ['temperatureCurve', curve_keys(temp)],
        ['temperatureSunMultCurve', sun_mult_keys(top)],
        ['temperatureLatitudeBiasCurve', [('key', '0\t3\t0\t0'), ('key', '40\t0\t-0.4\t-0.4'), ('key', '90\t-8\t-0.7\t0')]],
        ['temperatureLatitudeSunMultCurve', [('key', '0\t14\t0\t0'), ('key', '45\t11\t-0.1\t-0.1'), ('key', '90\t4\t-0.2\t0')]],
        ['temperatureAxialSunBiasCurve', [('key', '0\t0\t0\t0')]], ['temperatureAxialSunMultCurve', [('key', '0\t0\t0\t0')]],
        ['temperatureEccentricityBiasCurve', [('key', '0\t0\t0\t0')]],
        ['pressureCurve', pressure_keys(e['pressure'], top)]]]


def orbit_node(e, orbit_col):
    return ['Orbit', [('referenceBody', e['parent']), ('semiMajorAxis', '%d' % int(round(e['sma'] * 1000))),
                      ('eccentricity', cfg_num(e['ecc'])), ('inclination', cfg_num(e['inc'])),
                      ('longitudeOfAscendingNode', cfg_num(e['lan'])), ('argumentOfPeriapsis', cfg_num(e['argpe'])),
                      ('meanAnomalyAtEpoch', cfg_num(e['mean_anomaly'])), ('epoch', cfg_num(e['epoch'])), ('color', v4(orbit_col))]]


def biomes_node(biomes):
    return ['Biomes', [['Biome', [('name', bn), ('displayName', bdn), ('value', cfg_num(bv)),
                                  ('color', ','.join('%.4f' % (c / 255.0) for c in col) + ',1')]]
                       for bn, bdn, bv, col in biomes]]


def body_tree(name, mod_name, e, nums, g, tex, mods, light, orbit_col, biomes=None, ocean=None, scaled_extra=(), rings=None):
    R = nums['R']
    q = nums['pqs']
    tpl = [('name', 'Kerbin'), ('removeAllPQSMods', 'true'), ('removeBiomes', 'true')]
    if not e['atmo']:
        tpl.append(('removeAtmosphere', 'true'))
    if ocean is None:
        tpl.append(('removeOcean', 'true'))
    props = [('displayName', display_name(e, name)), ('description', cfg_text(e['description'] or 'A world.')),
             ('radius', '%d' % int(round(R))), ('geeASL', cfg_num(float('%.4g' % g))),
             ('rotationPeriod', cfg_num(round(e['rotation'] * 3600.0, 1))), ('rotates', 'true'),
             ('tidallyLocked', 'true' if e['tidally_locked'] else 'false'), ('initialRotation', cfg_num(e['initial_rotation'])),
             ('isHomeWorld', 'false'), ('albedo', cfg_num(e['albedo'])),
             ('timewarpAltitudeLimits', ' '.join(str(x) for x in nums['warp']))]
    if biomes and tex.get('biomes'):
        props.append(('biomeMap', tex['biomes']))
    props.append(['ScienceValues', [('landedDataValue', '15'), ('splashedDataValue', '15'), ('flyingLowDataValue', '13'),
                                    ('flyingHighDataValue', '13'), ('inSpaceLowDataValue', '12'), ('inSpaceHighDataValue', '10'),
                                    ('recoveryValue', '13'), ('flyingAltitudeThreshold', '%d' % nums['fly']),
                                    ('spaceAltitudeThreshold', '%d' % nums['space'])]])
    if biomes and tex.get('biomes'):
        props.append(biomes_node(biomes))
    body = [('name', name), ('identifier', '%s/%s' % (mod_name, name)), ('cacheFile', '%s/Cache/%s.bin' % (mod_name, name)),
            ['Template', tpl], ['Properties', props]]
    if e['atmo']:
        body.append(atmo_node(e, nums['top'], light))
    body.append(orbit_node(e, orbit_col))
    mat = [('color', '1,1,1,1'), ('specColor', '0.1,0.1,0.1,1'), ('shininess', '0.1'), ('texture', tex['color']),
           ('mainTexScale', '1,1'), ('mainTexOffset', '0,0'), ('normals', tex['normal']), ('bumpMapScale', '1,1'), ('bumpMapOffset', '0,0')]
    if e['atmo']:
        mat += [('opacity', '1'), ('rimPower', '5'), ('rimBlend', '1'), ('rimColorRamp', 'BUILTIN/AerialRampKerbin2'),
                ('rimColorRampScale', '1,1'), ('rimColorRampOffset', '0,0')]
    mat += [('resourceMapScale', '1,1'), ('resourceMapOffset', '0,0')]
    body.append(['ScaledVersion', [('type', 'Atmospheric' if e['atmo'] else 'Vacuum'), ('fadeStart', '%d' % q['sv_start']),
                                   ('fadeEnd', '%d' % q['sv_end']), ['Material', mat]] + list(scaled_extra)])
    body.append(['PQS', [('fadeStart', '%d' % q['pqs_start']), ('fadeEnd', '%d' % q['pqs_end']), ('deactivateAltitude', '%d' % q['deactivate']),
                         ('minLevel', '2'), ('maxLevel', '%d' % q['max_level']), ('materialType', 'AtmosphericTriplanarZoomRotation'),
                         ['Material', list(GROUND[e['ground']])], ['Mods', mods]]])
    if ocean is not None:
        body.append(ocean)
    if rings is not None:
        body.append(rings)
    return ['Body', body]


KOP_REQUIRED = {'name', 'Template/name', 'Properties/radius', 'Orbit/referenceBody', 'Orbit/semiMajorAxis', 'ScaledVersion/type',
                'ScaledVersion/OnDemand', 'ScaledVersion/Material/texture', 'PQS/Mods', 'Atmosphere/enabled', 'Atmosphere/altitude'}
KOP_DESCEND = ('Template', 'Properties', 'Atmosphere', 'Orbit', 'ScaledVersion', 'Material', 'AtmosphereFromGround', 'Debug', 'PQS')
KOP_EXTRA = (
    ('barycenter', 'false', 'true: an invisible point other bodies orbit, with no planet'),
    ('finalizeOrbit', 'true', 'lets Kopernicus finalize the orbit when the game loads'),
    ('randomMainMenuBody', 'true', 'may be shown on the main menu'),
    ('contractWeight', '30', 'how often contracts are made for this body'),
    ('implements', '', 'another identifier (System/Body) this body stands in for'),
    ('Template/removePQS', 'true', 'drops the template\'s surface'),
    ('Template/removeBiomes', 'true', 'drops the template\'s own biomes'),
    ('Template/removeOcean', 'true', 'drops the template\'s ocean'),
    ('Template/removeAtmosphere', 'true', 'drops the template\'s air'),
    ('Template/removeProgressTree', 'false', 'true drops the template\'s contracts and milestones'),
    ('Template/removeCoronas', 'true', 'drops coronas (only the Sun has them)'),
    ('Properties/useTheInName', 'false', 'true: the game says "the <name>" in some places'),
    ('Properties/mass', '=mass', 'mass in kg, instead of geeASL'),
    ('Properties/gravParameter', '=mu', 'G x mass in m³/s², instead of geeASL'),
    ('Properties/inverseRotThresholdAltitude', '=inv', 'altitude in m where the frame switches from surface to orbit'),
    ('Properties/emissivity', '0.4', 'how strongly the body radiates heat, 0 to 1'),
    ('Properties/coreTemperatureOffset', '0', 'extra core temperature in K'),
    ('Properties/sphereOfInfluence', '=soi', 'a fixed sphere of influence in m (otherwise worked out)'),
    ('Properties/hillSphere', '=hill', 'a fixed Hill sphere in m'),
    ('Properties/solarRotationPeriod', 'false', 'true: rotationPeriod counts the solar day, not the sidereal one'),
    ('Properties/navballSwitchRadiusMult', '0.06', 'the navball switches to orbit going up, times the radius'),
    ('Properties/navballSwitchRadiusMultLow', '0.055', 'the navball switches back going down, times the radius'),
    ('Properties/selectable', 'true', 'false: cannot be selected in map view'),
    ('Properties/RnDVisibility', 'Visible', 'in the R&D archives: Visible, Noicon, Hidden or Skip'),
    ('Properties/RnDRotation', 'false', 'turns in the R&D archives'),
    ('Properties/maxZoom', '=zoom', 'closest map view zoom, in m that fit the screen height'),
    ('Orbit/period', '=period', 'a fixed orbital period in s (instead of the one from the orbit)'),
    ('Orbit/meanAnomalyAtEpochD', '=madeg', 'mean anomaly in degrees, instead of meanAnomalyAtEpoch'),
    ('Orbit/iconColor', '=orbitcol', 'colour of the map icon'),
    ('Orbit/iconTexture', '', 'your own map icon texture (GameData path)'),
    ('Orbit/mode', 'REDRAW_AND_RECALCULATE', 'OFF, REDRAW_ONLY, REDRAW_AND_FOLLOW or REDRAW_AND_RECALCULATE'),
    ('Orbit/icon', 'ALL', 'NONE, OBJ, OBJ_PE_AP or ALL'),
    ('Orbit/cameraSmaRatioBounds', '0.3 25', 'lower and upper map camera bounds'),
    ('ScaledVersion/invisible', 'false', 'true hides the scaled model'),
    ('ScaledVersion/sphericalModel', 'false', 'true: the scaled model is a sphere instead of the real shape'),
    ('ScaledVersion/deferMesh', 'false', 'true: does not make a new scaled mesh every time'),
    ('ScaledVersion/Material/rimColorRamp', '', 'a rim colour texture instead of the Gradient'),
    ('Atmosphere/staticDensityASL', '=rho', 'air density at the bottom of the air in kg/m³'),
    ('Atmosphere/temperatureLapseRate', '=lapse', 'temperature fall per m, used when there are no curves'),
    ('Atmosphere/AtmosphereFromGround/innerRadiusMult', '0.975', 'the glow starts at this times the radius'),
    ('Atmosphere/AtmosphereFromGround/outerRadiusMult', '1.025', 'the glow ends at this times the radius'),
    ('Atmosphere/AtmosphereFromGround/samples', '4', 'quality of the atmosphere glow'),
    ('HazardousBody', '=hot', 'heats craft in the atmosphere: base temperature in K, fading out with height'),
    ('Debug/exportMesh', 'true', 'saves the scaled mesh to the cache file'),
    ('Debug/update', 'false', 'true rebuilds the scaled mesh every time the game loads'),
    ('Debug/showSOI', 'false', 'shows the sphere of influence as a wireframe'),
)
KOP_HELP = {
    'identifier': 'a unique ID other mods can use for the body', 'cacheFile': 'where Kopernicus keeps the scaled mesh',
    'Template/removeAllPQSMods': 'drops the template\'s terrain', 'Template/removeBiomes': 'drops the template\'s biomes',
    'Template/removeAtmosphere': 'drops the template\'s air', 'Template/removeOcean': 'drops the template\'s ocean',
    'Properties/displayName': 'name shown in game (^N: proper name)', 'Properties/geeASL': 'surface gravity in g',
    'Properties/rotationPeriod': 'day length in s', 'Properties/initialRotation': 'starting rotation in degrees',
    'Properties/albedo': 'reflectivity, 0 to 1', 'Properties/timewarpAltitudeLimits': 'lowest altitude for each warp speed',
    'Properties/ScienceValues': 'science multipliers and the flying and space altitudes', 'Properties/Biomes': 'the biomes in the biome map',
    'Atmosphere/oxygen': 'true lets jet engines work', 'Atmosphere/ambientColor': 'tints craft in the atmosphere',
    'Atmosphere/lightColor': 'old way to set the glow colour', 'Atmosphere/AtmosphereFromGround': 'the atmosphere glow seen from space',
    'Atmosphere/pressureCurve': 'pressure by height', 'Atmosphere/temperatureCurve': 'temperature by height',
    'Orbit/color': 'colour of the orbit line', 'ScaledVersion/fadeStart': 'altitude where the scaled model starts to fade in',
    'ScaledVersion/fadeEnd': 'where it is fully there', 'ScaledVersion/Material/normals': 'normal map of the scaled model',
    'ScaledVersion/Material/rimColorRamp': 'rim colour of the air from space',
    'ScaledVersion/Material/Gradient': 'rim colour from the lit side (0) to the dark side (1)',
    'ScaledVersion/Material/rimPower': 'lower covers more of the planet with the rim',
    'ScaledVersion/Material/rimBlend': 'blend between atmosphere and rim',
    'PQS/fadeStart': 'altitude where the close-up terrain starts to fade out', 'PQS/fadeEnd': 'where it is gone',
    'PQS/deactivateAltitude': 'altitude where the terrain is switched off', 'PQS/maxLevel': 'finest terrain detail (8 or 9)',
    'PQS/materialType': 'the close-up terrain shader', 'PQS/Material': 'close-up ground textures (the Ground setting)',
    'PQS/Mods': 'the vertex maps: height, colour and the rest', 'Ocean': 'the ocean in the water colours', 'Rings': 'the rings from the Rings tab',
    'HazardousBody': 'heat that hurts craft, from the hazard map',
}


def kop_paths(tree, prefix=''):
    out = []
    for it in tree[1]:
        p = prefix + it[0]
        if isinstance(it, tuple):
            if p not in KOP_REQUIRED:
                out.append((p, it[0], it[1]))
        elif it[0] in KOP_DESCEND:
            out += kop_paths(it, p + '/')
        elif p not in KOP_REQUIRED:
            out.append((p, it[0], None))
    return out


def kop_defaults(e, nums, orbit_col, tree):
    R = nums['R']; M = nums['mass']
    d = {'mass': '%.6g' % M, 'mu': '%.6g' % (M * G_NEWTON), 'inv': '%d' % int(nums['top'] or R * 0.05),
         'zoom': '%d' % int(R), 'madeg': cfg_num(round(np.degrees(e['mean_anomaly']), 4)), 'orbitcol': v4(orbit_col), 'hot': nums['hot'],
         'rho': '%.5g' % (e['pressure'] * 1000.0 * e['molar_mass'] / (R_GAS * e['temperature'])), 'lapse': nums['lapse'],
         'soi': '', 'hill': '', 'period': ''}
    if nums.get('parent_mass'):
        a = e['sma'] * 1000.0
        d['soi'] = '%d' % int(nums['soi'])
        d['hill'] = '%d' % int(a * (1 - e['ecc']) * (M / (3 * nums['parent_mass'])) ** (1 / 3.0))
        d['period'] = '%.1f' % nums['period']
    auto = {p for p, k, v in kop_paths(tree)} | KOP_REQUIRED
    return {p: (d.get(v[1:], '') if v.startswith('=') else v) for p, v, h in KOP_EXTRA if p not in auto}


def kop_node(tree, parts, create=False):
    node = tree
    for name in parts:
        nxt = next((it for it in node[1] if isinstance(it, list) and it[0] == name), None)
        if nxt is None:
            if not create:
                return None
            nxt = [name, []]
            node[1].append(nxt)
        node = nxt
    return node


def kop_apply(tree, opts, defaults, top=None):
    tree = copy.deepcopy(tree)
    for path, (on, val) in opts.items():
        parts = path.split('/')
        parent = kop_node(tree, parts[:-1])
        if parent is None or path in KOP_REQUIRED or path in defaults:
            continue
        for i, it in enumerate(parent[1]):
            if it[0] == parts[-1]:
                if not on:
                    del parent[1][i]
                elif val.strip() and isinstance(it, tuple):
                    parent[1][i] = (it[0], cfg_text(val))
                break
    for path, default, help in KOP_EXTRA:
        st = opts.get(path)
        if path not in defaults or not st or not st[0]:
            continue
        val = cfg_text(st[1] if st[1].strip() else defaults.get(path, ''))
        if not val:
            continue
        if path == 'HazardousBody':
            h = int(round(top or 10000))
            tree[1].append(['HazardousBody', [['Instance', [('ambientTemp', val), ('sumTemp', 'true'),
                                                            ['AltitudeCurve', [('key', '0 1'), ('key', '%d 0' % h)]]]]]])
            continue
        parts = path.split('/')
        parent = kop_node(tree, parts[:-1], create=parts[0] == 'Debug')
        if parent is not None:
            parent[1].append((parts[-1], val))
    return tree


KOP_BLANK = ('Template', 'Properties', 'Orbit', 'ScaledVersion', 'Rings', 'ScienceValues', 'Biomes', 'AtmosphereFromGround',
             'temperatureCurve', 'HazardousBody', 'Debug', 'Material', 'Fog')


def kop_render(node, depth):
    T = '\t'
    L = [T * depth + node[0], T * depth + '{']
    prev = None
    for it in node[1]:
        if isinstance(it, tuple):
            L.append(T * (depth + 1) + '%s = %s' % it)
        else:
            tight = it[0] == 'Material' and (node[0] == 'PQS' or isinstance(prev, list))
            if it[0] in KOP_BLANK and L[-1] not in ('', T * depth + '{') and not tight:
                L.append('')
            L += kop_render(it, depth + 1)
            if it[0] == 'AtmosphereFromGround':
                L.append('')
        prev = it
    if L[-1] == '':
        L.pop()
    L.append(T * depth + '}')
    return L


def body_cfg(tree, opts, defaults, top=None):
    tree = kop_apply(tree, opts or {}, defaults, top)
    return '\n'.join(['@Kopernicus:AFTER[Kopernicus]', '{'] + kop_render(tree, 1) + ['}']) + '\n'


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
    return name.lstrip('@!%+-').split(':')[0].split('[')[0].strip()


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


def cfg_blocks(text):
    root = ['', 0, -1, len(text), []]
    stack = [root]
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '/' and text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        if ch == '{':
            j = i - 1
            while j >= 0 and text[j] in ' \t\r\n':
                j -= 1
            k = j
            while k >= 0 and text[k] not in '{}\n':
                k -= 1
            name = text[k + 1:j + 1].strip() if j >= 0 and text[j] not in '{}' else ''
            node = [name, k + 1 if name else i, i, len(text), []]
            stack[-1][4].append(node)
            stack.append(node)
        elif ch == '}' and len(stack) > 1:
            stack[-1][3] = i
            stack.pop()
        i += 1
    return root


def cfg_find(node, base):
    for c in node[4]:
        if cfg_base(c[0]) == base:
            yield c
        for x in cfg_find(c, base):
            yield x


def cfg_has(text, node, key, val):
    return re.search(r'^[ \t]*%s[ \t]*=[ \t]*%s[ \t]*$' % (re.escape(key), re.escape(val)), text[node[2] + 1:node[3]], re.M) is not None


def cfg_insert_child(text, node, block):
    ls = text.rfind('\n', 0, node[3]) + 1
    return text[:ls] + block + '\n' + text[ls:]


def merge_planets_list(text, full, name):
    item = '\n'.join(full.split('\n')[4:-3])
    for lst in cfg_find(cfg_blocks(text), 'scattererCelestialBodies'):
        for it in lst[4]:
            if cfg_base(it[0]) == 'Item' and cfg_has(text, it, 'celestialBodyName', name):
                return text[:it[1]] + item + text[it[3] + 1:]
        return cfg_insert_child(text, lst, item)
    return None


def merge_pqs(text, name):
    obj = '\tOBJECT\n\t{\n\t\tbody = %s\n\t\tdeactivateDistance = 175000\n\t}' % name
    for m in cfg_find(cfg_blocks(text), 'PQS_MANAGER'):
        if any(cfg_base(o[0]) == 'OBJECT' and cfg_has(text, o, 'body', name) for o in m[4]):
            return text
        return cfg_insert_child(text, m, obj)
    t = text.rstrip()
    return (t + '\n\n' if t else '') + 'PQS_MANAGER\n{\n' + obj + '\n}\n'


def gamedata_rel(d):
    parts = os.path.abspath(d).split(os.sep)
    low = [p.lower() for p in parts]
    if 'gamedata' in low:
        i = len(low) - 1 - low[::-1].index('gamedata')
        rest = parts[i + 1:]
        if rest:
            return '/'.join(rest)
    return ''


def sub_dir(parent, name):
    if os.path.isdir(parent):
        for n in os.listdir(parent):
            if n.lower() == name.lower() and os.path.isdir(os.path.join(parent, n)):
                return os.path.join(parent, n)
    return os.path.join(parent, name)


def find_gamedata(start):
    d = start
    for _ in range(6):
        g = sub_dir(d, 'GameData')
        if os.path.isdir(g):
            return g
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return ''


def mod_name_of(mod):
    rel = gamedata_rel(mod)
    return rel.split('/')[0] if rel else os.path.basename(os.path.normpath(mod))


def mod_rel(mod, path):
    rel = gamedata_rel(path)
    return rel or (mod_name_of(mod) + '/' + os.path.relpath(path, mod).replace('\\', '/'))


def mod_tex_dir(mod):
    tex = sub_dir(mod, 'Textures')
    if os.path.isdir(sub_dir(tex, 'PluginData')) or not os.path.isdir(tex):
        tex = sub_dir(tex, 'PluginData')
    return tex


def mod_bodies(mod):
    out = {}
    if not mod or not os.path.isdir(mod):
        return out
    for path, t in cfg_files(mod, 'Body'):
        for b in cfg_walk(parse_cfg(t), 'Body'):
            if b['name'].strip() != 'Body':
                continue
            nm = cfg_get(b, 'name')
            if nm and nm not in out:
                out[nm] = (path, b)
    return out


def body_mass(name, bodies):
    hit = bodies.get(name)
    if hit:
        for pr in cfg_walk(hit[1], 'Properties'):
            try:
                if cfg_get(pr, 'mass'):
                    return float(cfg_get(pr, 'mass'))
                if cfg_get(pr, 'gravParameter'):
                    return float(cfg_get(pr, 'gravParameter')) / G_NEWTON
                if cfg_get(pr, 'geeASL') and cfg_get(pr, 'radius'):
                    return float(cfg_get(pr, 'geeASL')) * G0 * float(cfg_get(pr, 'radius')) ** 2 / G_NEWTON
            except ValueError:
                pass
        for tp in cfg_walk(hit[1], 'Template'):
            if cfg_get(tp, 'name') in STOCK_MASS:
                return STOCK_MASS[cfg_get(tp, 'name')]
    return STOCK_MASS.get(name)


def is_star(node):
    if any(cfg_get(t, 'name') == 'Sun' for t in cfg_walk(node, 'Template')):
        return True
    if any(str(cfg_get(s, 'type', '')).lower() == 'star' for s in cfg_walk(node, 'ScaledVersion')):
        return True
    return any(True for _ in cfg_walk(node, 'Light'))


def star_of(name, bodies):
    for _ in range(12):
        hit = bodies.get(name)
        if not hit or is_star(hit[1]):
            return name
        ref = None
        for o in cfg_walk(hit[1], 'Orbit'):
            ref = cfg_get(o, 'referenceBody')
            break
        if not ref or ref == name:
            return name
        name = ref
    return name


def find_scatterer(name, mod):
    sd = sub_dir(mod, 'Scatterer')
    atmo = os.path.join(sd, 'Planets', name, 'atmo.cfg')
    plist = ''
    if os.path.isdir(sd):
        pat_a = re.compile(r'^\s*name\s*=\s*%s\s*$' % re.escape(name), re.M)
        pat_p = re.compile(r'^\s*celestialBodyName\s*=\s*%s\s*$' % re.escape(name), re.M)
        for path, t in cfg_files(sd, name):
            if not os.path.isfile(atmo) and 'Scatterer_atmosphere' in t and pat_a.search(t):
                atmo = path
            if not plist and 'scattererCelestialBodies' in t and pat_p.search(t):
                plist = path
    return atmo, plist


def mod_plan(name, parent, mod, bodies):
    star = star_of(parent, bodies)
    tex = mod_tex_dir(mod)
    cfgs = sub_dir(mod, 'Configs')
    hit = bodies.get(name)
    if hit and os.path.abspath(hit[0]).startswith(os.path.abspath(mod)):
        body = hit[0]
    else:
        if os.path.isdir(sub_dir(cfgs, parent)):
            folder = sub_dir(cfgs, parent)
        elif parent in bodies and os.path.abspath(bodies[parent][0]).startswith(os.path.abspath(cfgs) + os.sep):
            folder = os.path.dirname(bodies[parent][0])
        else:
            folder = sub_dir(cfgs, star)
        body = os.path.join(folder, name + '.cfg')
    vc = sub_dir(cfgs, 'volumetricclouds')
    cdir = sub_dir(vc, 'Clouds')
    clouds = None
    if os.path.isdir(mod):
        pat = re.compile(r'^\s*body\s*=\s*%s\s*$' % re.escape(name), re.M)
        for path, t in cfg_files(mod, name):
            if 'EVE_CLOUDS' in t and pat.search(t) and '-aurora-' not in t:
                clouds = path
                break
    pqs = next((os.path.join(vc, n) for n in (os.listdir(vc) if os.path.isdir(vc) else [])
                if n.lower() == 'pqs.cfg' and os.path.isfile(os.path.join(vc, n))), os.path.join(vc, 'pqs.cfg'))
    atmo, plist = find_scatterer(name, mod)
    plist = plist or os.path.join(sub_dir(mod, 'Scatterer'), 'planetsList_%s.cfg' % star)
    return {'star': star, 'tex': tex, 'body': body, 'cloud_dir': cdir, 'clouds': clouds or os.path.join(cdir, name + '_clouds.cfg'),
            'pqs': pqs, 'atmo': atmo, 'plist': plist}


def fix_sun(P, star, bodies, log=None):
    a = P.get('atmosphere')
    if not isinstance(a, dict):
        return
    sun = str(a.get('sun') or '').strip()
    if star and (sun in ('', 'Sun') or (bodies and sun not in bodies and sun not in STOCK_MASS)):
        if log and sun and sun != star:
            log('Scatterer sun %s is not in the mod - using %s' % (sun, star))
        a['sun'] = star


def backup(paths, mod, bdir):
    done = False
    for p in paths:
        if os.path.isfile(p):
            dst = os.path.join(bdir, os.path.relpath(p, mod))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)
            done = True
    return done


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def merged(path, text_fn, fresh):
    if os.path.isfile(path):
        with open(path, encoding='utf-8', errors='replace') as f:
            t = text_fn(f.read())
        if t is not None:
            return t
    if not fresh:
        return text_fn('') or ''
    return fresh


def save_palette_dds(img, path, flip=True):
    a = np.ascontiguousarray(img[::-1] if flip else img)[..., :3]
    H, W = a.shape[:2]
    cols, idx = np.unique(a.reshape(-1, 3), axis=0, return_inverse=True)
    if len(cols) > 256:
        raise ValueError('a biome map can have at most 256 colours, this one has %d' % len(cols))
    pal = np.zeros((256, 4), np.uint8)
    pal[:len(cols), :3] = cols
    pal[:, 3] = 255
    data = idx.reshape(H, W).astype(np.uint8)
    hd = bytearray(128)
    hd[0:4] = b'DDS '
    struct.pack_into('<7I', hd, 4, 124, 0x100F, H, W, W, 0, 0)
    struct.pack_into('<8I', hd, 76, 32, 0x20, 0, 8, 0, 0, 0, 0)
    struct.pack_into('<I', hd, 108, 0x1000)
    with open(path, 'wb') as f:
        f.write(bytes(hd) + pal.tobytes() + np.ascontiguousarray(data).tobytes())
    return len(cols)


def biome_file(tdir, name):
    return os.path.join(tdir, name + '_biomes.dds')


def tex_paths(S, P, mod, build, tdir):
    t = {kind: mod_rel(mod, path) for path, what, kind in S.kop_textures(P, build, tdir) if kind}
    if P['planet']['biomes']:
        t['biomes'] = mod_rel(mod, biome_file(tdir, P['name']))
    return t


def body_text(S, P, mod, bodies, build, tex):
    e = P['planet']
    shape = S.kop_shape(P, build)
    nums = numbers(e, shape['R'], shape['g'], shape['top'], shape['relief'], body_mass(e['parent'], bodies),
                   getattr(S, 'KOP_MASS_REF', 'Kerbin'))
    if hasattr(S, 'kop_numbers'):
        S.kop_numbers(e, nums)
    biomes = S.kop_biomes(P, build, False)[0] if e['biomes'] else None
    if hasattr(S, 'kop_body'):
        tree = S.kop_body(P, mod_name_of(mod), e, nums, tex, biomes)
    else:
        tree = body_tree(P['name'], mod_name_of(mod), e, nums, shape['g'], tex, S.kop_mods(P, tex, shape), S.kop_light(P),
                         S.kop_orbit_colour(P), biomes, S.kop_ocean(P, tex), S.kop_scaled_extra(P, tex), S.kop_rings(P, tex))
    tree[1].extend(getattr(S, 'kop_body_extra', lambda P, tex: [])(P, tex))
    defs = kop_defaults(e, nums, S.kop_orbit_colour(P), tree)
    return tree, defs, nums, body_cfg(tree, e.get('opts'), defs, nums['top'] or shape['top'])


def preview_texts(S, P, mod, bodies):
    P = copy.deepcopy(P)
    P['planet'] = entry(S, P)
    star = star_of(P['planet']['parent'], bodies)
    fix_sun(P, star, bodies)
    build = S.kop_build(P)
    tdir = mod_tex_dir(mod)
    rel = lambda p: mod_rel(mod, p)
    tree, defs, nums, text = body_text(S, P, mod, bodies, build, tex_paths(S, P, mod, build, tdir))
    out = {'Kopernicus config': text}
    cdir = sub_dir(sub_dir(sub_dir(mod, 'Configs'), 'volumetricclouds'), 'Clouds')
    plan = {'star': star, 'tex': tdir, 'cloud_dir': cdir, 'clouds': os.path.join(cdir, P['name'] + '_clouds.cfg'),
            'atmo': '', 'plist': '', 'pqs': None}
    for path, t, what, fresh in S.kop_extras(P, plan, rel, mod):
        if fresh:
            out[what[0].upper() + what[1:]] = fresh
    if hasattr(S, 'kop_preview_extra'):
        out.update(S.kop_preview_extra(P, rel, tdir))
    return out, tree, defs, nums, build


def export_files(S, P, mod, build, plan):
    out = []
    for path, what, kind in S.kop_textures(P, build, plan['tex']):
        out.append((path, what, 'replace' if os.path.isfile(path) else 'new'))
    if P['planet']['biomes']:
        bp = biome_file(plan['tex'], P['name'])
        out.append((bp, 'biome map', 'replace' if os.path.isfile(bp) else 'new'))
    for fname, what in getattr(S, 'kop_cloud_cfgs', lambda P: [])(P):
        p = os.path.join(plan['cloud_dir'], fname)
        out.append((p, what, 'replace' if os.path.isfile(p) else 'new'))
    out.append((plan['body'], 'Kopernicus config', 'replace' if os.path.isfile(plan['body']) else 'new'))
    for path, t, what, fresh in S.kop_extras(P, plan, lambda p: mod_rel(mod, p), mod):
        out.append((path, what, ('add to' if callable(t) else 'replace') if os.path.isfile(path) else 'new'))
    return out


def export_mod(S, P, mod, build, backup_root, log=print):
    P = copy.deepcopy(P)
    P['planet'] = entry(S, P)
    name = P['name']
    bodies = mod_bodies(mod)
    plan = mod_plan(name, P['planet']['parent'], mod, bodies)
    fix_sun(P, plan['star'], bodies, log)
    files = export_files(S, P, mod, build, plan)
    bdir = os.path.join(backup_root, name, time.strftime('%Y%m%d_%H%M%S'))
    had = backup([p for p, w, h in files if h != 'new'], mod, bdir)
    rel = lambda p: mod_rel(mod, p)
    tex = tex_paths(S, P, mod, build, plan['tex'])
    written, cloud_cfgs = S.kop_write_textures(P, build, plan['tex'], plan['cloud_dir'], rel, log)
    for w in cloud_cfgs:
        dst = os.path.join(plan['cloud_dir'], os.path.basename(w))
        if os.path.abspath(dst) != os.path.abspath(w):
            os.makedirs(plan['cloud_dir'], exist_ok=True)
            shutil.move(w, dst)
        written.append(dst); log('wrote ' + dst)
    if P['planet']['biomes']:
        bl, img = S.kop_biomes(P, build, True)
        if img is not None:
            bp = biome_file(plan['tex'], name)
            os.makedirs(plan['tex'], exist_ok=True)
            save_palette_dds(img, bp)
            written.append(bp); log('exported ' + bp)
    texts = [(plan['body'], body_text(S, P, mod, bodies, build, tex)[3])]
    for path, t, what, fresh in S.kop_extras(P, plan, rel, mod):
        texts.append((path, merged(path, t, fresh) if callable(t) else t))
    for path, t in texts:
        write_text(path, t)
        written.append(path); log('wrote ' + path)
    return written, (bdir if had or os.path.isdir(bdir) else None)
