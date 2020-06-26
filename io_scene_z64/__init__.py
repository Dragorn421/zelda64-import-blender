# <pep8-80 compliant>

bl_info = {
   "name":		"Zelda64 Format",
   "author":		"SoulofDeity",
   "blender":		(2, 5, 8),
   "location":		"File > Import-Export",
   "description":	"Import-Export Zelda64, Import Zelda64",
   "warning":		"",
   "wiki_url":		"",
   "tracker_url":	"",
   "support":		'OFFICIAL',
   "category":		"Import-Export" }

if "bpy" in locals():
   import imp
   if "import_z64" in locals():
      imp.reload(import_z64)
   if "export_z64" in locals():
      imp.reload(export_z64)



import bpy
from bpy.props import(BoolProperty, FloatProperty, StringProperty, EnumProperty)
from bpy_extras.io_utils import(ExportHelper, ImportHelper)


class ImportZ64(bpy.types.Operator, ImportHelper):
   """Load a Zelda64 File"""
   bl_idname	= "file.zobj"
   bl_label	= "Import Zelda64"
   bl_options	= {'PRESET', 'UNDO'}
   filename_ext	= ".zobj"
   filter_glob	= StringProperty(default="*.zobj;*.zmap", options={'HIDDEN'})

   def execute(self, context):
      from . import import_z64
      keywords = self.as_keywords(ignore=("filter_glob",))
      return import_z64.load(self, context, **keywords)


def menu_func_import(self, context):
    self.layout.operator(ImportZ64.bl_idname, text="Zelda64 (.zobj;.zmap)")


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
