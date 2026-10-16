# Changelog

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
