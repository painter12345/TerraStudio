# Changelog

## 1.0.0

- Hazard map: makes lava or a deadly sea (acid, molten metal, anything) hurt
  craft through Kopernicus' HazardousBody. Pick what is deadly (lava fields, flows, rivers and lava sea; the
  sea; or both), the temperature craft are heated towards, how far the heat spreads past the edge and how high
  it reaches. Export writes <name>_hazard.dds (greyscale L8, white = full heat, same layout as the height map)
  and the Kopernicus config gets a HazardousBody node with the map and an AltitudeCurve; Export to mod does
  both. The tab shows the heat on a map. Export row "Hazard map", command line `export --hazard dds|png|none`.
- Hazard map: rivers. The rivers from the Landforms tab can carry the deadly stuff too: water rivers when
  the sea is deadly, lava rivers (Lava tab, More glow) when the lava is. Tick "The rivers carry it too"
  (on by default), or pick "Only the rivers" under What is deadly. The river channels are traced from the
  same river network as the build, so they line up with the rivers in the colour map.
- New Biome Map Maker (Biome maps... at the top): make your own biomes with a name, a science value and a
  colour, and rules for where each one goes: in the ocean, on the shores, on land, on ice and snow, on glowing lava, in big craters
  or in a placed feature, height, slope and latitude.
  The first biome whose rules fit a spot gets it, so the order counts. Paint biomes straight onto the
  map with a brush, or erase painting to get the rules back. It shows the biomes over the planet with
  their share of the surface, and suggests a first set from the build (ice and snow, oceans, shores, peaks, highlands,
  lowlands, lava fields, big craters and the features you placed). Export to mod on the Config
  tab writes these biomes and their map; Save biome map... and Copy Biomes node give you the PNG and the
  config node on their own.
- Biome maps: In big craters now only takes the craters you can still see in the build, measured from
  its heights, so craters buried under lava flows or worn flat are left out, and your placed craters and
  basins count too. Under a lava or water sea a crater only counts when its rim shows as a ring around
  it, and a crater cut by glowing lava cracks only when most of its rim is clear of the lava. The craters
  come from the build itself, so changing the crater settings after building no longer moves them. The
  suggested Big Craters size no longer falls to the smallest crater when craters cover little of the
  surface.
- Biome maps: In big craters now uses the crater generator's own maths. Each crater biome has the exact
  outline of the crater's bowl as it was drawn (its wobbly edge included) at its exact spot, instead of
  a circle. Where two craters of similar size overlap, each spot goes to the one whose bowl is deeper
  there; a crater much smaller than the one it sits in counts as part of the bigger one. A crater that
  keeps less than half of its bowl this way is left out, and the heights still decide whether a crater
  can be seen at all (worn flat, buried under lava, under the sea). The suggested Big Craters size now
  takes in the biggest craters covering about 15 % of the surface (was 5 %).
- Biome maps: painting shows the stroke straight away, and Paint and Erase show the brush size as a
  circle on the map.
- Biome maps: a new Relief switch shades the map with the build's heights, so craters and other
  landforms show even where flowed lava paints over them.
- Biome maps are written as a DDS with an 8-bit palette (Kopernicus' palette format, which keeps the
  exact biome colours, and one GIMP can open) instead of a PNG, by Export to
  mod, Save biome map... and the Export window. The Export window has a new Biome map row (DDS or PNG),
  and with it ticked its Kopernicus config gets biomeMap and the Biomes node.
- New Config tab, the same as in Gas Giant Studio: fill in the display name, description, what the
  planet orbits, gravity, day length, the orbit and the atmosphere you can fly in, and it writes the
  whole Kopernicus config. It works out the mass and density, orbital period and sphere of influence
  (from the parent in your mod), the pressure and temperature curves, time warp limits, science
  altitudes, the close-up terrain (PQS) distances the way the rocky bodies in your mod have them, and
  a biome map from the build's heights (oceans, shores, lowlands, highlands, peaks, polar caps).
  Gravity 0 means "like Kerbin for its size". "Close-up ground textures" picks the PQS textures.
- Kopernicus options: every line of the config can be left out or given your own value, and the other
  options from the Kopernicus wiki can be ticked on.
- Export to mod: pick your mod's folder in GameData and it writes everything where the mod keeps it:
  height, fine height, colour, normal, glow, ring, cloud and aurora textures in Textures/PluginData, the
  config in Configs/<star> (or next to the body it orbits), the EVE clouds and aurora in
  Configs/volumetricclouds/Clouds (and adds the planet to pqs.cfg), the Scatterer atmosphere in
  Scatterer/Planets and its entry in planetsList_<star>.cfg. Exporting again replaces the planet's own
  files instead of adding a second copy, and every file that is already there is backed up first.
- Code boxes scroll up again: the mouse wheel scrolls the box until its top or bottom and only then the
  page.
- Number fields no longer round their value when you only click into them and out again.
- Placed craters have a Central peak setting on the Features tab: 1 = the full knob in the middle of
  craters wider than 20 km (as before), 0 = no knob, anything between makes it lower.

## 0.2.0

- Lava: a second style next to the torn plates, "Flowed and cooled", made to look like Anneheg in the
  Kcalbeloh System. The lava fills the low ground (below the lava level, or the whole sea on a planet with
  an ocean) and its surface is worked out as if it had really flowed: divergence-free currents, eddies and
  streams along the shores carry it along, stretching it into streaks and folding it into swirls. The
  molten lava glows red at the shore and hotter further out, with crisp floes of crust, crumbs around them
  and thin glowing cracks, and lights up the foot of the rock around it. Everywhere else it has cooled into
  rock that keeps the flow lines, as streaks of colour and low frozen ridges. Lava level, flow, eddy size,
  flow along the shores, how far from the shore it gets hot, crust floes, glowing cracks, shore glow reach,
  flow lines and ridges on the rock and their colour; amount, seed, the lava colours, heated edges and glow
  are shared with the plates. It goes into the colour map and the emissive map, and with an ocean the
  Kopernicus config writes the ocean in the lava colours.
- New preset FlowedMoon.
- Presets with torn plates, lava oceans and everything else look exactly the same.
- Normal map: now made the way GIMP's Filters → Generic → Normal Map makes it from the height map (the same
  numbers as GEGL's normal-map operation), with wrap-around at the left and right edges and flat oceans.
  New "Normal map scale" on the Relief tab (GIMP's Scale, default 10); Relief strength now only sets the
  preview. The green channel points the other way than in earlier versions, so re-export normal maps.

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
