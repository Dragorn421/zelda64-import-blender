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
