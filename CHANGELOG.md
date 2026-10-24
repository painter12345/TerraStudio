# Changelog

## 0.1.17

- Rings tab (from Gas Giant Studio): rings with wide zones, ringlets, gaps, soft edges,
  opacity, tilt and three colours (auto from the planet's colour stops). The tab shows the
  planet with its rings and the ring shadow, plus the Kopernicus Rings node to copy.
- Build writes `<name>_ring.png`; Export has a Ring texture row (DDS BC3, BC7 or PNG) and
  the Kopernicus config gets the Rings node. Command line: `export --ring dds|bc3|bc7|png|none`.
- The preview sheet shows the rings when the planet has rings and no Scatterer atmosphere.

## 0.1.16

- Landforms: Equatorial ridge, one long mountain wall around the planet like the ridge on
  Iapetus (or Pan and Atlas). Settings: height, width, length (all the way around or an arc
  that fades out at both ends), centre longitude, latitude shift, tilt, gaps, ragged and
  wander, plus a New ridge shape button. The ridge is part of the height map, so craters cut
  into it and rivers run around it. Randomize landforms sometimes adds one on worlds without
  an ocean. Old presets load without a ridge and look the same as before.

## 0.1.15

- Scatterer: the planet list entry no longer writes autoMainSun, which only a modified Scatterer
  knows. Everything the studio writes is now for the regular Scatterer release. For a planet
  around another star, set Sun (mainSunCelestialBody) on the Atmosphere tab to that star.

## 0.1.14

- In game view: now also shows the clouds (fair weather, one weather system and cirrus, lit by the
  sun under the atmosphere), the aurora and the lava glow on the night side. Each can be switched
  off on the Atmosphere tab ("In game view also shows").
- In game view: works without a Scatterer atmosphere too, as soon as the planet has clouds, an
  aurora or glowing lava.

## 0.1.13

- Clouds: the cloud cover now really goes from 0 to 100 %. Before, the fair weather could not go
  below about 20 % or above about 70 %, the cirrus stopped at about 50 % and the weather systems
  never went below about 12 %.
- Clouds: every layer is set in percent of the planet now (fair weather, each weather system,
  cirrus); 0 % leaves the layer out. The old Coverage sliders are gone. Presets without a
  percentage start at 35 % fair weather, 30 % per weather system and 15 % cirrus.
- Clouds view: shows one weather system (as at one moment in game) instead of all of them on top
  of each other, which made the planet look overcast whatever the cover was. The tab also shows
  how much of the planet has clouds with everything together.

## 0.1.12

- Clouds: "Cover (% of the planet)" for the fair weather and for the weather systems. The clouds
  then cover exactly that much of the planet, whatever the other settings are (0 = use the
  Coverage slider as before). The tab shows how much the fair weather, each weather system and
  the cirrus cover now.
- Clouds: a Randomize clouds button for new wind, swirls, layers and cloud cover. Surprise me
  randomizes the clouds too.

## 0.1.11

- The Clouds view shows its progress: working out the wind, then drawing the clouds, in percent
  under the picture and in the status line. A quick, smaller picture comes first.
- Clouds are about four times faster: the wind is worked out in parallel and only once for the
  seed and the wind settings, so changing coverage, systems, cirrus or colours redraws in about
  a second. The export logs its progress too.
- The view buttons fit again (Preview sheet is now called Sheet).

## 0.1.10

- Clouds: a new Clouds tab makes volumetric clouds for EVE and True Volumetric Clouds, made the
  same way as Edmunds' clouds: the wind carries them around eddies and along east-west bands, so
  they come out in curls, long streaks and thin fibres. A fair-weather layer with fields of small
  cumulus, up to four weather systems that build up and fade away again on a cycle (EVE
  timeSettings), and a high cirrus layer. Swirls, swirl size, wind, wind bands, streaks, gaps,
  coverage, cycle times, heights, drift speed, brightness and colour can be set, and a seed gives
  a new pattern.
- Clouds view: a new view shows the clouds over the planet, with or without the weather systems.
- Export: "Clouds (EVE + TVC)" writes a coverage map (BC4) and a cloud type map for each layer,
  the maps for scaled space (DXT5) and `<name>_clouds.cfg` with Edmunds' cloud types. Map sizes
  2048 to 16384. From the command line: `--clouds tvc|none`.
- Changing the clouds does not mark the build as out of date.

## 0.1.9

- Lava ocean: on the Lava tab, everything below sea level can be lava instead of water, with
  floating crust plates, glowing shores and its own glow. The Kopernicus config writes the
  ocean in the lava colours and puts the emissive map on the ocean surface too.
- More glow: glowing cracks, glowing volcano calderas with lava flows down their slopes, and
  lava rivers (the rivers from the Landforms tab carry lava instead of water). All of it goes
  into the colour map and the one emissive map.
- New preset MoltenWorld: an ordinary rocky planet with continents, lava rivers, glowing
  volcanoes and a lava ocean.

## 0.1.8

- Lava plates: a new Lava tab tears the crust into plates with glowing lava between them, like
  the worlds close to their star. On the star-facing side (or all over, for tidally heated
  moons) the plates are tipped and pushed up, they get smaller and the lava channels wider
  towards the hottest point, and the hottest point melts into an open lava sea with floating
  rafts. Plate size, ragged edges, tilt, channel width and depth, the lava sea, lava pools, the
  lava, hottest lava and crust colours, heated plate edges and glow can be set.
- Emissive map: a planet with lava gets `<name>_emissive.png` in its build. The live preview and
  the preview sheet show the glow. Export writes it as DDS or PNG (`--emissive` on the command
  line), and the Kopernicus config adds it as VertexColorMapEmissive (Additive) in the PQS mods
  and the ScaledVersion.
- Two new presets: TornLava and LavaMoon.

## 0.1.7

- Aurora: a new Aurora tab makes polar lights around each magnetic pole: glowing curtains
  with rays, a lower fringe, bright cores and a red and purple top part. Magnetic tilt per
  pole, oval size and wobble, a dark centre, the number, spacing and width of the curtains,
  gaps, rays, diffuse glow, brightness and six colours can be set, and a seed gives a new
  pattern.
- Aurora view: a new view next to In game shows both poles from above with all layers.
- Export: "Aurora (EVE)" writes <name>_aurora and <name>_aurora_top (DDS DXT5 or PNG, at
  the size set on the tab) and <name>_aurora.cfg, an EVE config that stacks them as thin
  layers from the lowest layer up, fading towards the top. From the command line:
  `--aurora dds|png|none`.
- Changing the aurora does not mark the build as out of date.

## 0.1.6

- Atmosphere: fixed the black layer Scatterer drew around the planet. atmo.cfg was written with
  specR, specG, specB and shininess at 0; it now uses specR/G/B 40 and shininess 50. Presets and
  atmo.cfg files that still have shininess 0 (or all three spec values at 0) are repaired when
  they are loaded, and any of the other Scatterer values that are missing are filled in.
- Planet list entry: now also writes cloudIntegrationUsesScattererSunColors = False and
  autoMainSun = True, so a planet around another star is lit by that star.

## 0.1.5

- Features: a new kind, Plateau. Place a single tableland where you want it: it rises by its height
  above the ground around it, with a flat top, steep ragged edges and a gentle slope of rubble at
  the foot. Height 0 = a height that fits its size.
- Presets look exactly the same.

## 0.1.4

- Atmosphere: a new Atmosphere tab makes a Scatterer atmosphere for the planet, ported from
  Gas Giant Studio, with Scatterer's own values: atmosphereStartRadiusScale, HR and m_betaR
  (Rayleigh, the colour of the sky), HM, BETA_MSca and m_mieG (Mie, the haze), the ozone
  layer, averageGroundReflectance, multipleScattering, godrayStrength and the config points.
  Other Scatterer values (rim, shine, cloud and scaled-texture settings) are kept and written
  back as they are.
- Start from the stock Kerbin, Duna, Eve or Laythe atmosphere (Scatterer's own values),
  Earth-like, or the planet's colours. "Fit to this planet's size" scales them to the radius.
- In game view: shows the planet with its atmosphere the way KSP's map view shows it, with the
  relief lit by the sun: the whole planet, the day-side edge or the sunset edge. Drag left or
  right to move the sun. It uses the build when that is up to date, otherwise the live preview.
- Sky colour and haze colour pickers, Match the planet, Grey haze.
- Load from Scatterer config, Copy, Save atmo.cfg (backs up a file it replaces) and the planet
  list entry. Turning the atmosphere on offers the planet's existing Scatterer config if your
  mod has one.
- Export: "Scatterer config" writes the atmo.cfg and planetsList_<planet>.cfg (also `--atmo` on
  the command line).
- The preview sheet shows the atmosphere on the big globe.
- The preview toolbar has two rows, so the Export button always fits.
- The example preset Riverlands has a Kerbin-like atmosphere.
- Presets without an atmosphere look exactly the same.

## 0.1.3

- New name: Terra Studio (was Terrain Studio).
- Windows version: `build_release.bat` builds `TerraStudio.exe` and zips it, no Python needed to run it.
- Export: "Path in config" sets the folder under GameData that the texture paths in the
  Kopernicus config start with (also `--config-path` on the command line).
- Example preset Riverlands looks at its continents in the preview.

## 0.1.2

- New Landforms tab.
- Rivers and valleys: real drainage, so rivers run downhill, join and widen, and end in the sea or a basin.
  They carve a channel and a valley. River colour: water or your own colour.
- Plateaus: flat-topped tablelands with steep, ragged edges.
- Cracks: long crossing lines (Europa-like) or polygon cells, with raised edges and their own colour.
- Canyons and volcanoes moved to the Landforms tab.
- New example presets Riverlands and CrackedIce.
- Presets from 0.1.1 look exactly the same.

## 0.1.1

- Colours from picture: take the colours by height from a line across a photo.
- The colour picker (the same as in Gas Giant Studio) is now mentioned where the colour boxes are.
- Climate colours: a dry belt on both sides of the equator and a cold tint towards the poles.
- Separate north and south polar caps, and how far sea ice reaches.
- Crater floor colour and ejecta colour.
- Volcanic rock colour.
- Brightness, contrast and saturation for the whole colour map.
- Twist goes up to 2 without creasing the land.
- Continent size variety, and land gathering near the equator or near the poles.
- Mountain sharpness.
- Canyons with a depth and width in km.
- Random shield volcanoes with a summit crater.
- Features tab: place your own craters, basins, volcanoes and mountains by clicking the map or the globe.
- New example preset RiftDesert.
- Old presets look the same as before; a single polar-cap latitude becomes the same north and south cap.

## 0.1.0

- First version: continents and oceans, mountains, hills, plains, craters, colours by height,
  rock on slopes, ice and snow, live preview, builds up to 8192, export of height (with a fine
  height map), colour and normal maps and a Kopernicus config.
