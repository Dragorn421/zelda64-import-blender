# zelda64-import-blender

This is an addon allowing to import models and animations from files extracted from N64 Zelda roms.

# History

## SoulofDeity

Originally written by SoulofDeity, they did most of the work. Their code can be found in this repository's history or 
[on google code](https://code.google.com/archive/p/sods-blender-plugins/)
([http url](http://code.google.com/archive/p/sods-blender-plugins/)).

## Nokaubure

Then, Nokaubure distributed a version with following added features:
- Textures tags `#MirrorX/Y` and `#ClampX/Y` for exporting again using SharpOcarina
- Importing vertex alpha
- A `displaylists.txt` file alongside the imported file is read for display lists to import (made by Skawo)
- If the imported file is named like `XXX_room.*`, data for segment 2 will first tried to be read from `XXX_scene.zscene`
- Scale map models by 48 (it turned out this was just cancelling out the 1/48 scale SoulofDeity implemented)
- Set Blender's 3D view grid size parameters for maps
- Made pre-rendered scenes able to import

## Dragorn421

Then, Dragorn421 made changes to import all animations at once instead of only one every import, and other smaller changes, changelog for these versions was:

**Import Options**
- Added option to use shadeless materials (don't use environment colors in-game) (default False)
- Added original object scale option, blender objects will be at inverted scale (default 100, use 48 for maps?)
- Made Texture Clamp and Texture Mirror options True by default
- Removed option for animation to import

**Features**
- Made all animations import at once, each action named animXX_FF where XX is some number and FF the number of frames
- Removed the (useless) actions every mesh part had
- Made armature modifier show in edit mode by default
- Made end frame (in Timeline) be the maximum duration of animations
- Improved console log a tiny bit (open console before importing to see progress)

**Remarks**
- Importing normals only lacks ability to apply them reliably (Blender limitations), currently data is lost when merging doubles, so in this version normals are not used at all
