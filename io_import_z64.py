bl_info = {
   "name":		"Zelda64 Importer",
   "author":		"SoulofDeity",
   "blender":		(2, 6, 0),
   "location":		"File > Import-Export",
   "description":	"Import Zelda64",
   "warning":		"",
   "wiki_url":		"https://code.google.com/p/sods-blender-plugins/",
   "tracker_url":	"https://code.google.com/p/sods-blender-plugins/",
   "support":		'COMMUNITY',
   "category":		"Import-Export" }

import bpy, os, struct, time

from bpy import ops
from bpy.props import *
from bpy_extras.image_utils import load_image
from bpy_extras.io_utils import ExportHelper, ImportHelper
from math import *
from mathutils import *
from struct import pack, unpack_from


def splitOffset(offset):
   return offset >> 24, offset & 0x00FFFFFF

def validOffset(segment, offset):
   seg, offset = splitOffset(offset)
   if seg > 15:
      return False
   if offset >= len(segment[seg]):
      return False
   return True

def pow2(val):
   i = 1
   while i < val:
      i <<= 1
   return int(i)

def powof(val):
   num, i = 1, 0
   while num < val:
      num <<= 1
      i += 1
   return int(i)

def mulVec(v1, v2):
   return Vector([v1.x * v2.x, v1.y * v2.y, v1.z * v2.z])


class Tile:
   def __init__(self):
      self.texFmt, self.texBytes = 0x00, 0
      self.width, self.height = 0, 0
      self.rWidth, self.rHeight = 0, 0
      self.txlSize = 0
      self.lineSize = 0
      self.rect = Vector([0, 0, 0, 0])
      self.scale = Vector([1, 1])
      self.ratio = Vector([1, 1])
      self.clip = Vector([0, 0])
      self.mask = Vector([0, 0])
      self.shift = Vector([0, 0])
      self.tshift = Vector([0, 0])
      self.offset = Vector([0, 0])
      self.data = 0x00000000
      self.palette = 0x00000000

   def create(self, segment):
      if exportTextures:
         try:
            os.mkdir(fpath + "/textures")
         except:
            pass
         w = self.rWidth
         if int(self.clip.x) & 1 != 0 and enableTexMirror:
            w <<= 1
         h = self.rHeight
         if int(self.clip.y) & 1 != 0 and enableTexMirror:
            h <<= 1
         file = open(fpath + "/textures/%08X.tga" % self.data, 'wb')
         if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
            file.write(pack("<BBBHHBHHHHBB", 0, 1, 1, 0, 256, 24, 0, 0, w, h, 8, 0))
            self.writePalette(file, segment)
         else:
            file.write(pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 8))
         if int(self.clip.y) & 1 != 0 and enableTexMirror:
            self.writeImageData(file, segment, True)
         else:
            self.writeImageData(file, segment)
         file.close()
      try:
         tex = bpy.data.textures.new(name="tex_%08X" % self.data, type='IMAGE')
         img = load_image(fpath + "/textures/%08X.tga" % self.data)
         if img:
            tex.image = img
            if int(self.clip.x) & 2 != 0 and enableTexClamp:
               img.use_clamp_x = True
            if int(self.clip.y) & 2 != 0 and enableTexClamp:
               img.use_clamp_y = True
         mtl = bpy.data.materials.new(name="mtl_%08X" % self.data)
         mtl.use_shadeless = True
         mt = mtl.texture_slots.add()
         mt.texture = tex
         mt.texture_coords = 'UV'
         mt.use_map_color_diffuse = True
         if (img.depth == 32):
            mt.use_map_alpha = True
            tex.use_mipmap = True
            tex.use_interpolation = True
            tex.use_alpha = True
            mtl.use_transparency = True
            mtl.alpha = 0.0
            mtl.game_settings.alpha_blend = 'ALPHA'
         return mtl
      except:
         return None

   def calculateSize(self):
      maxTxl, lineShift = 0, 0
      if self.texFmt == 0x00 or self.texFmt == 0x40:
         maxTxl = 4096
         lineShift = 4
      elif self.texFmt == 0x60 or self.texFmt == 0x80:
         maxTxl = 8192
         lineShift = 4
      elif self.texFmt == 0x08 or self.texFmt == 0x48:
         maxTxl = 2048
         lineShift = 3
      elif self.texFmt == 0x68 or self.texFmt == 0x88:
         maxTxl = 4096
         lineShift = 3
      elif self.texFmt == 0x10 or self.texFmt == 0x70:
         maxTxl = 2048
         lineShift = 2
      elif self.texFmt == 0x50 or self.texFmt == 0x90:
         maxTxl = 2048
         lineShift = 0
      elif self.texFmt == 0x18:
         maxTxl = 1024
         lineShift = 2
      lineWidth = self.lineSize << lineShift
      self.lineSize = lineWidth
      tileWidth = self.rect.z - self.rect.x + 1
      tileHeight = self.rect.w - self.rect.y + 1
      maskWidth = 1 << int(self.mask.x)
      maskHeight = 1 << int(self.mask.y)
      lineHeight = 0
      if lineWidth > 0:
         lineHeight = min(int(maxTxl / lineWidth), tileHeight)
      if self.mask.x > 0 and (maskWidth * maskHeight) <= maxTxl:
         self.width = maskWidth
      elif (tileWidth * tileHeight) <= maxTxl:
         self.width = tileWidth
      else:
         self.width = lineWidth
      if self.mask.y > 0 and (maskWidth * maskHeight) <= maxTxl:
         self.height = maskHeight
      elif (tileWidth * tileHeight) <= maxTxl:
         self.height = tileHeight
      else:
         self.height = lineHeight
      clampWidth, clampHeight = 0, 0
      if self.clip.x == 1:
         clampWidth = tileWidth
      else:
         clampWidth = self.width
      if self.clip.y == 1:
         clampHeight = tileHeight
      else:
         clampHeight = self.height
      if maskWidth > self.width:
         self.mask.x = powof(self.width)
         maskWidth = 1 << int(self.mask.x)
      if maskHeight > self.height:
         self.mask.y = powof(self.height)
         maskHeight = 1 << int(self.mask.y)
      if int(self.clip.x) & 2 != 0:
         self.rWidth = pow2(clampWidth)
      elif int(self.clip.x) & 1 != 0:
         self.rWidth = pow2(maskWidth)
      else:
         self.rWidth = pow2(self.width)
      if int(self.clip.y) & 2 != 0:
         self.rHeight = pow2(clampHeight)
      elif int(self.clip.y) & 1 != 0:
         self.rHeight = pow2(maskHeight)
      else:
         self.rHeight = pow2(self.height)
      self.shift.x, self.shift.y = 1.0, 1.0
      if self.tshift.x > 10:
         self.shift.x = 1 << int(16 - self.tshift.x)
      elif self.tshift.x > 0:
         self.shift.x /= 1 << int(self.tshift.x)
      if self.tshift.y > 10:
         self.shift.y = 1 << int(16 - self.tshift.y)
      elif self.tshift.y > 0:
         self.shift.y /= 1 << int(self.tshift.y)
      self.ratio.x = (self.scale.x * self.shift.x) / self.rWidth
      if not enableToon:
         self.ratio.x /= 32;
      if int(self.clip.x) & 1 != 0 and enableTexMirror:
         self.ratio.x /= 2
      self.offset.x = self.rect.x
      self.ratio.y = (self.scale.y * self.shift.y) / self.rHeight
      if not enableToon:
         self.ratio.y /= 32;
      if int(self.clip.y) & 1 != 0 and enableTexMirror:
         self.ratio.y /= 2
      self.offset.y = 1.0 + self.rect.y

   def writePalette(self, file, segment):
      if self.texFmt == 0x40:
         palSize = 16
      else:
         palSize = 256
      if not validOffset(segment, self.palette + int(palSize * 2) - 1):
         for i in range(256):
            file.write(pack("L", 0))
         return
      seg, offset = splitOffset(self.palette)
      for i in range(256):
         if i < palSize:
            color = unpack_from(">H", segment[seg], offset + (i << 1))[0]
            r = int(8 * ((color >> 11) & 0x1F))
            g = int(8 * ((color >> 6) & 0x1F))
            b = int(8 * ((color >> 1) & 0x1F))
            file.write(pack("BBB", b, g, r))
         else:
            file.write(pack("BBB", 0, 0, 0))

   def writeImageData(self, file, segment, fy=False, df=False):
      if fy == True:
         dir = (0, self.rHeight, 1)
      else:
         dir = (self.rHeight - 1, -1, -1)
      if self.texFmt == 0x40 or self.texFmt == 0x60 or self.texFmt == 0x80 or self.texFmt == 0x90:
         bpp = 0.5
      elif self.texFmt == 0x00 or self.texFmt == 0x08 or self.texFmt == 0x10 or self.texFmt == 0x70:
         bpp = 2
      elif self.texFmt == 0x48 or self.texFmt == 0x50 or self.texFmt == 0x68 or self.texFmt == 0x88:
         bpp = 1
      else:
         bpp = 4
      lineSize = self.rWidth * bpp
      if not validOffset(segment, self.data + int(self.rHeight * lineSize) - 1):
         size = self.rWidth * self.rHeight
         if int(self.clip.x) & 1 != 0 and enableTexMirror:
            size *= 2
         if int(self.clip.y) & 1 != 0 and enableTexMirror:
            size *= 2
         for i in range(size):
            if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
               file.write(pack("B", 0))
            else:
               file.write(pack(">L", 0x000000FF))
         return
      seg, offset = splitOffset(self.data)
      for i in range(dir[0], dir[1], dir[2]):
         off = offset + int(i * lineSize)
         line = []
         j = 0
         while j < int(self.rWidth * bpp):
            if bpp < 2:
               color = unpack_from("B", segment[seg], off + int(floor(j)))[0]
            elif bpp == 2:
               color = unpack_from(">H", segment[seg], off + j)[0]
            else:
               color = unpack_from(">L", segment[seg], off + j)[0]
            if self.texFmt == 0x40:
               if floor(j) == j:
                  a = color >> 4
               else:
                  a = color & 0x0F
            elif self.texFmt == 0x48 or self.texFmt == 0x50:
               a = color
            elif self.texFmt == 0x00 or self.texFmt == 0x08 or self.texFmt == 0x10:
               r = int(8 * ((color >> 11) & 0x1F))
               g = int(8 * ((color >> 6) & 0x1F))
               b = int(8 * ((color >> 1) & 0x1F))
               a = int(255 * (color & 0x01))
            elif self.texFmt == 0x80:
               if floor(j) == j:
                  r = int(16 * (color >> 4))
               else:
                  r = int(16 * (color & 0x0F))
               g = r
               b = g
               a = 0xFF
            elif self.texFmt == 0x88:
               r = color
               g = r
               b = g
               a = 0xFF
            elif self.texFmt == 0x68:
               r = int(16 * (color >> 4))
               g = r
               b = g
               a = int(16 * (color & 0x0F))
            elif self.texFmt == 0x70:
               r = color >> 8
               g = r
               b = g
               a = color & 0xFF
            elif self.texFmt == 0x18:
               r = color >> 24
               g = (color >> 16) & 0xFF
               b = (color >> 8) & 0xFF
               a = color & 0xFF
            else:
               r = 0
               g = 0
               b = 0
               a = 0xFF
            if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
               line.extend([a])
            else:
               line.extend([(b << 24) | (g << 16) | (r << 8) | a])
            j += bpp
         if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
            file.write(pack("B" * len(line), *line))
         else:
            file.write(pack(">" + "L" * len(line), *line))
         if int(self.clip.x) & 1 != 0 and enableTexMirror:
            line.reverse()
            if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
               file.write(pack("B" * len(line), *line))
            else:
               file.write(pack(">" + "L" * len(line), *line))
      if int(self.clip.y) & 1 != 0 and df == False and enableTexMirror:
         if fy == True:
            self.writeImageData(file, segment, False, True)
         else:
            self.writeImageData(file, segment, True, True)


class Vertex:
   def __init__(self):
      self.pos = Vector([0, 0, 0])
      self.uv = Vector([0, 0])
      self.normal = Vector([0, 0, 0])
      self.color = [0, 0, 0, 0]
      self.limb = None

   def read(self, segment, offset):
      if not validOffset(segment, offset + 16):
         return
      seg, offset = splitOffset(offset)
      self.pos.x = unpack_from(">h", segment[seg], offset)[0]
      self.pos.z = unpack_from(">h", segment[seg], offset + 2)[0]
      self.pos.y = -unpack_from(">h", segment[seg], offset + 4)[0]
      self.pos /= 1024
      self.uv.x = float(unpack_from(">h", segment[seg], offset + 8)[0])
      self.uv.y = float(unpack_from(">h", segment[seg], offset + 10)[0])
      self.normal.x = 0.00781250 * unpack_from("b", segment[seg], offset + 12)[0]
      self.normal.z = 0.00781250 * unpack_from("b", segment[seg], offset + 13)[0]
      self.normal.y = 0.00781250 * unpack_from("b", segment[seg], offset + 14)[0]
      self.color[0] = min(0.00392157 * segment[seg][offset + 12], 1.0)
      self.color[1] = min(0.00392157 * segment[seg][offset + 13], 1.0)
      self.color[2] = min(0.00392157 * segment[seg][offset + 14], 1.0)


class Mesh:
   def __init__(self):
      self.verts, self.uvs, self.colors, self.faces = [], [], [], []
      self.vgroups = {}

   def create(self, hierarchy, offset):
      if len(self.faces) == 0:
         return
      me = bpy.data.meshes.new("me_%08X" % offset)
      ob = bpy.data.objects.new("ob_%08X" % offset, me)
      bpy.context.scene.objects.link(ob)
      bpy.context.scene.objects.active = ob
      me.vertices.add(len(self.verts))
      for i in range(len(self.verts)):
         me.vertices[i].co = self.verts[i]
      me.tessfaces.add(len(self.faces))
      vcd = me.tessface_vertex_colors.new().data
      for i in range(len(self.faces)):
         me.tessfaces[i].vertices = self.faces[i]
         vcd[i].color1 = self.colors[i * 3 + 2]
         vcd[i].color2 = self.colors[i * 3 + 1]
         vcd[i].color3 = self.colors[i * 3]
      uvd = me.tessface_uv_textures.new().data
      for i in range(len(self.faces)):
         if self.uvs[i * 4 + 3]:
            if not self.uvs[i * 4 + 3].name in me.materials:
               me.materials.append(self.uvs[i * 4 + 3])
            uvd[i].image = self.uvs[i * 4 + 3].texture_slots[0].texture.image
         uvd[i].uv[0] = self.uvs[i * 4 + 2]
         uvd[i].uv[1] = self.uvs[i * 4 + 1]
         uvd[i].uv[2] = self.uvs[i * 4]
      me.calc_normals()
      me.validate()
      me.update()
      if hierarchy:
         for name, vgroup in self.vgroups.items():
            grp = ob.vertex_groups.new(name)
            for v in vgroup:
               grp.add([v], 1.0, 'REPLACE')
         ob.parent = hierarchy.armature
         mod = ob.modifiers.new(hierarchy.name, 'ARMATURE')
         mod.object = hierarchy.armature
         mod.use_bone_envelopes = False
         mod.use_vertex_groups = True


class Limb:
   def __init__(self):
      self.parent, self.child, self.sibling = -1, -1, -1
      self.pos = Vector([0, 0, 0])
      self.near, self.far = 0x00000000, 0x00000000
      self.poseBone = None
      self.poseLocPath, self.poseRotPath = None, None
      self.poseLoc, self.poseRot = None, None

   def read(self, segment, offset):
      seg, offset = splitOffset(offset)
      self.pos.x = unpack_from(">h", segment[seg], offset)[0]
      self.pos.z = unpack_from(">h", segment[seg], offset + 2)[0]
      self.pos.y = -unpack_from(">h", segment[seg], offset + 4)[0]
      self.pos /= 1024
      self.child = unpack_from("b", segment[seg], offset + 6)[0]
      self.sibling = unpack_from("b", segment[seg], offset + 7)[0]
      self.near = unpack_from(">L", segment[seg], offset + 8)[0]
      self.far = unpack_from(">L", segment[seg], offset + 12)[0]


class Hierarchy:
   def __init__(self):
      self.name, self.offset = "", 0x00000000
      self.limbCount, self.dlistCount = 0x00, 0x00
      self.limb = []
      self.armature = None

   def read(self, segment, offset):
      if not validOffset(segment, offset + 9):
         return
      self.name = "sk_%08X" % offset
      self.offset = offset
      seg, offset = splitOffset(offset)
      limbIndex_offset = unpack_from(">L", segment[seg], offset)[0]
      if not validOffset(segment, limbIndex_offset):
         print("      ERROR:  Limb index table 0x%08X out of range" % limbIndex_offset)
         return
      limbIndex_seg, limbIndex_offset = splitOffset(limbIndex_offset)
      self.limbCount = segment[seg][offset + 4]
      self.dlistCount = segment[seg][offset + 8]
      for i in range(self.limbCount):
         limb_offset = unpack_from(">L", segment[limbIndex_seg], limbIndex_offset + 4 * i)[0]
         limb = Limb()
         limb.index = i
         self.limb.extend([limb])
         if validOffset(segment, limb_offset + 12):
            limb.read(segment, limb_offset)
         else:
            print("      ERROR:  Limb 0x%02X offset 0x%08X out of range" % (i, limb_offset))[0]
      self.limb[0].pos = Vector([0, 0, 0])
      self.initLimbs(0x00)

   def create(self):
      if (bpy.context.active_object):
         bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
      for i in bpy.context.selected_objects:
         i.select = False
      self.armature = bpy.data.objects.new(self.name, bpy.data.armatures.new("armature"))
      self.armature.show_x_ray = True
      self.armature.data.draw_type = 'STICK'
      bpy.context.scene.objects.link(self.armature)
      bpy.context.scene.objects.active = self.armature
      bpy.ops.object.mode_set(mode='EDIT', toggle=False)
      for i in range(self.limbCount):
         bone = self.armature.data.edit_bones.new("limb_%02i" % i)
         bone.use_deform = True
         bone.head = self.limb[i].pos
      for i in range(self.limbCount):
         bone = self.armature.data.edit_bones["limb_%02i" % i]
         if (self.limb[i].parent != -1):
            bone.parent = self.armature.data.edit_bones["limb_%02i" % self.limb[i].parent]
            bone.use_connect = False
         bone.tail = bone.head + Vector([0, 0, 0.0001])
      bpy.ops.object.mode_set(mode='OBJECT')

   def initLimbs(self, i):
      if (self.limb[i].child > -1 and self.limb[i].child != i):
         self.limb[self.limb[i].child].parent = i
         self.limb[self.limb[i].child].pos += self.limb[i].pos
         self.initLimbs(self.limb[i].child)
      if (self.limb[i].sibling > -1 and self.limb[i].sibling != i):
         self.limb[self.limb[i].sibling].parent = self.limb[i].parent
         self.limb[self.limb[i].sibling].pos += self.limb[self.limb[i].parent].pos
         self.initLimbs(self.limb[i].sibling)

   def getMatrixLimb(self, offset):
      j = 0
      index = (offset & 0x00FFFFFF) / 0x40
      for i in range(self.limbCount):
         if self.limb[i].near != 0:
            if (j == index):
               return self.limb[i]
            j += 1
      return self.limb[0]


class F3DZEX:
   def __init__(self):
      self.segment, self.vbuf, self.tile  = [], [], []
      for i in range(16):
         self.segment.extend([[]])
         self.vbuf.extend([Vertex()])
      for i in range(2):
         self.tile.extend([Tile()])
         self.vbuf.extend([Vertex()])
      for i in range(14 + 32):
         self.vbuf.extend([Vertex()])
      self.curTile = 0
      self.material = []
      self.hierarchy = []
      self.resetCombiner()

   def setSegment(self, seg, path):
      try:
         file = open(path, 'rb')
         self.segment[seg] = file.read()
         file.close()
      except:
         pass

   def locateHierarchies(self):
      data = self.segment[0x06]
      for i in range(0, len(data), 4):
         if data[i] == 0x06 and (data[i+3] & 3) == 0 and data[i+4] != 0:
            offset = unpack_from(">L", data, i)[0] & 0x00FFFFFF
            if offset < len(data):
               offset_end = offset + (data[i+4] << 2)
               if offset_end < len(data):
                  j = offset
                  while j < offset_end:
                     if data[j] != 0x06 or (data[j+3] & 3) != 0 or (unpack_from(">L", data, j)[0] & 0x00FFFFFF) > len(data):
                        break
                     j += 4
                  if (j == i):
                     j |= 0x06000000
                     print("   hierarchy found at 0x%08X" % j)
                     h = Hierarchy()
                     h.read(self.segment, j)
                     self.hierarchy.extend([h])

   def locateAnimations(self):
      data = self.segment[0x06]
      self.animation = []
      for i in range(0, len(data), 4):
         if ((data[i] == 0) and (data[i+1] > 1) and
             (data[i+2] == 0) and (data[i+3] == 0) and
             (data[i+4] == 0x06) and
             (((data[i+5] << 16)|(data[i+6] << 8)|data[i+7]) < len(data)) and
             (data[i+8] == 0x06) and
             (((data[i+9] << 16)|(data[i+10] << 8)|data[i+11]) < len(data)) and
             (data[i+14] == 0) and (data[i+15] == 0)):
            print("         found at %08X" % i)
            self.animation.extend([i])

   def importMap(self):
      data = self.segment[0x03]
      for i in range(0, len(data), 8):
         if (data[i] == 0x0A and data[i+4] == 0x03):
            mho = (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            if (mho < len(data)):
               type = data[mho]
               count = data[mho+1]
               seg = data[mho+4]
               start = (data[mho+5] << 16) | (data[mho+6] << 8) | data[mho+7]
               end = (data[mho+9] << 16) | (data[mho+10] << 8) | data[mho+11]
               if (data[mho+4] == 0x03 and start < end and end < len(data)):
                  if (type == 0):
                     for j in range(start, end, 4):
                        self.buildDisplayList(None, [None], unpack_from(">L", data, j)[0])
                  elif (type == 2):
                     for j in range(start, end, 16):
                        near = (data[j+8] << 24)|(data[j+9] << 16)|(data[j+10] << 8)|data[j+11]
                        far = (data[j+12] << 24)|(data[j+13] << 16)|(data[j+14] << 8)|data[j+15]
                        if (near != 0):
                           self.buildDisplayList(None, [None], near)
                        elif (far != 0):
                           self.buildDisplayList(None, [None], far)
            return
         elif (data[i] == 0x14):
            break
      print("ERROR:  Map header not found")

   def importObj(self):
      print("\nLocating hierarchies...")
      self.locateHierarchies()
      for hierarchy in self.hierarchy:
         print("\nBuilding hierarchy '%s'..." % hierarchy.name)
         hierarchy.create()
         for i in range(hierarchy.limbCount):
            limb = hierarchy.limb[i]
            if limb.near != 0:
               if validOffset(self.segment, limb.near):
                  print("   0x%02X : building display lists..." % i)
                  self.resetCombiner()
                  self.buildDisplayList(hierarchy, limb, limb.near)
               else:
                  print("   0x%02X : out of range" % i)
            else:
                  print("   0x%02X : n/a" % i)
      if len(self.hierarchy) > 0:
         bpy.context.scene.objects.active = self.hierarchy[0].armature
         self.hierarchy[0].armature.select = True
         bpy.ops.object.mode_set(mode='POSE', toggle=False)
         self.locateAnimations()
         if len(self.animation) > 0:
            self.buildAnimations(self.hierarchy[0])

   def resetCombiner(self):
      self.primColor = Vector([1.0, 1.0, 1.0])
      self.envColor = Vector([1.0, 1.0, 1.0])
      self.vertexColor = Vector([1.0, 1.0, 1.0])
      self.shadeColor = Vector([1.0, 1.0, 1.0])

   def getCombinerColor(self):
      cc = Vector([1.0, 1.0, 1.0])
      if enablePrimColor:
         cc = mulVec(cc, self.primColor)
      if enableEnvColor:
         cc = mulVec(cc, self.envColor)
      if vertexMode == 'COLORS':
         print(self.vertexColor)
         cc = mulVec(cc, self.vertexColor)
      elif vertexMode == 'NORMALS':
         cc = mulVec(cc, self.shadeColor)
      return cc

   def buildDisplayList(self, hierarchy, limb, offset):
      data = self.segment[offset >> 24]
      mesh = Mesh()
      has_tex = False
      material = None
      if hierarchy:
         matrix = [limb]
      else:
         matrix = [None]
      for i in range(offset & 0x00FFFFFF, len(data), 8):
         w0 = unpack_from(">L", data, i)[0]
         w1 = unpack_from(">L", data, i + 4)[0]
         if data[i] == 0x01:
            count = (data[i + 1] << 4) | (data[i + 2] >> 4)
            index = (data[i + 3] >> 1) - count
            offset = unpack_from(">L", data, i + 4)[0]
            if validOffset(self.segment, offset + int(16 * count) - 1):
               for j in range(count):
                  self.vbuf[index + j].read(self.segment, offset + 16 * j)
                  if hierarchy:
                     self.vbuf[index + j].limb = matrix[len(matrix) - 1]
                     if self.vbuf[index + j].limb:
                        self.vbuf[index + j].pos += self.vbuf[index + j].limb.pos
         elif data[i] == 0x02:
            index = ((data[i + 2] & 0x0F) << 3) | (data[i + 3] >> 1)
            if data[i + 1] == 0x10:
               self.vbuf[index].normal.x = 0.00781250 * unpack_from("b", data, i + 4)[0]
               self.vbuf[index].normal.z = 0.00781250 * unpack_from("b", data, i + 5)[0]
               self.vbuf[index].normal.y = 0.00781250 * unpack_from("b", data, i + 6)[0]
               self.vbuf[index].color = 0.00392157 * unpack_from("BBBB", data, i + 4)[0]
            elif data[i + 1] == 0x14:
               self.vbuf[index].uv.x = float(unpack_from(">h", data, i + 4)[0])
               self.vbuf[index].uv.y = float(unpack_from(">h", data, i + 6)[0])
         elif data[i] == 0x05 or data[i] == 0x06:
            if has_tex:
               material = None
               for j in range(len(self.material)):
                  if self.material[j].name == "mtl_%08X" % self.tile[0].data:
                     material = self.material[j]
                     break
               if material == None:
                  material = self.tile[0].create(self.segment)
                  if material:
                    self.material.extend([material])
               has_tex = False
            v1, v2 = None, None
            vi1, vi2 = -1, -1
            if not importTextures:
               material = None
            count = 0
            try:
               for j in range(1, (data[i] - 4) * 4):
                  if j != 4:
                     v3 = self.vbuf[data[i + j] >> 1]
                     vi3 = -1
                     for k in range(len(mesh.verts)):
                        if mesh.verts[k] == (v3.pos.x, v3.pos.y, v3.pos.z):
                           vi3 = k
                           break
                     if vi3 == -1:
                        mesh.verts.extend([(v3.pos.x, v3.pos.y, v3.pos.z)])
                        vi3 = len(mesh.verts) - 1
                        count += 1
                     if j == 1 or j == 5:
                        v1 = v3
                        vi1 = vi3
                     elif j == 2 or j == 6:
                        v2 = v3
                        vi2 = vi3
                     elif j == 3 or j == 7:
                        sc = (((v3.normal.x + v3.normal.y + v3.normal.z) / 3) + 1.0) / 2
                        self.vertexColor = Vector([v3.color[0], v3.color[1], v3.color[2]])
                        self.shadeColor = Vector([sc, sc, sc])
                        mesh.colors.extend([self.getCombinerColor()])
                        sc = (((v2.normal.x + v2.normal.y + v2.normal.z) / 3) + 1.0) / 2
                        self.vertexColor = Vector([v2.color[0], v2.color[1], v2.color[2]])
                        self.shadeColor = Vector([sc, sc, sc])
                        mesh.colors.extend([self.getCombinerColor()])
                        sc = (((v1.normal.x + v1.normal.y + v1.normal.z) / 3) + 1.0) / 2
                        self.vertexColor = Vector([v1.color[0], v1.color[1], v1.color[2]])
                        self.shadeColor = Vector([sc, sc, sc])
                        mesh.colors.extend([self.getCombinerColor()])
                        mesh.uvs.extend([(self.tile[0].offset.x + v3.uv.x * self.tile[0].ratio.x, self.tile[0].offset.y - v3.uv.y * self.tile[0].ratio.y),
                                         (self.tile[0].offset.x + v2.uv.x * self.tile[0].ratio.x, self.tile[0].offset.y - v2.uv.y * self.tile[0].ratio.y),
                                         (self.tile[0].offset.x + v1.uv.x * self.tile[0].ratio.x, self.tile[0].offset.y - v1.uv.y * self.tile[0].ratio.y),
                                         material])
                        if hierarchy:
                           if v3.limb:
                              if not (("limb_%02i" % v3.limb.index) in mesh.vgroups):
                                 mesh.vgroups["limb_%02i" % v3.limb.index] = []
                              mesh.vgroups["limb_%02i" % v3.limb.index].extend([vi3])
                           if v2.limb:
                              if not (("limb_%02i" % v2.limb.index) in mesh.vgroups):
                                 mesh.vgroups["limb_%02i" % v2.limb.index] = []
                              mesh.vgroups["limb_%02i" % v2.limb.index].extend([vi2])
                           if v1.limb:
                              if not (("limb_%02i" % v1.limb.index) in mesh.vgroups):
                                 mesh.vgroups["limb_%02i" % v1.limb.index] = []
                              mesh.vgroups["limb_%02i" % v1.limb.index].extend([vi1])
                        mesh.faces.extend([(vi1, vi2, vi3)])
            except:
               for i in range(count):
                  mesh.verts.pop()
         elif data[i] == 0xD7:
#            for i in range(2):
#               if ((w1 >> 16) & 0xFFFF) < 0xFFFF:
#                  self.tile[i].scale.x = ((w1 >> 16) & 0xFFFF) * 0.0000152587891
#               else:
#                  self.tile[i].scale.x = 1.0
#               if (w1 & 0xFFFF) < 0xFFFF:
#                  self.tile[i].scale.y = (w1 & 0xFFFF) * 0.0000152587891
#               else:
#                  self.tile[i].scale.y = 1.0
            pass
         elif data[i] == 0xD8 and enableMatrices:
            if hierarchy and len(matrix) > 1:
               matrix.pop()
         elif data[i] == 0xDA and enableMatrices:
            if hierarchy and data[i + 4] == 0x0D:
               if (data[i + 3] & 0x04) == 0:
                  matrixLimb = hierarchy.getMatrixLimb(unpack_from(">L", data, i + 4)[0])
                  if (data[i + 3] & 0x02) == 0:
                     newMatrixLimb = Limb()
                     newMatrixLimb.index = matrixLimb.index
                     newMatrixLimb.pos = (Vector([matrixLimb.pos.x, matrixLimb.pos.y, matrixLimb.pos.z]) + matrix[len(matrix) - 1].pos) / 2
                     matrixLimb = newMatrixLimb
                  if (data[i + 3] & 0x01) == 0:
                     matrix.extend([matrixLimb])
                  else:
                     matrix[len(matrix) - 1] = matrixLimb
               else:
                  matrix.extend([matrix[len(matrix) - 1]])
            elif hierarchy:
               print("unknown limb %08X %08X" % (w0, w1))
         elif data[i] == 0xDE:
            mesh.create(hierarchy, offset)
            mesh.__init__()
            offset = (offset >> 24) | i + 8
            if validOffset(self.segment, w1):
               self.buildDisplayList(hierarchy, limb, w1)
            if data[i + 1] != 0x00:
               return
         elif data[i] == 0xDF:
            mesh.create(hierarchy, offset)
            return
         elif data[i] == 0xE7:
            mesh.create(hierarchy, offset)
            mesh.__init__()
            offset = (offset >> 24) | i
         elif data[i] == 0xF0:
            self.palSize = ((w1 & 0x00FFF000) >> 13) + 1
         elif data[i] == 0xF2:
            self.tile[self.curTile].rect.x = (w0 & 0x00FFF000) >> 14
            self.tile[self.curTile].rect.y = (w0 & 0x00000FFF) >> 2
            self.tile[self.curTile].rect.z = (w1 & 0x00FFF000) >> 14
            self.tile[self.curTile].rect.w = (w1 & 0x00000FFF) >> 2
            self.tile[self.curTile].width = (self.tile[self.curTile].rect.z - self.tile[self.curTile].rect.x) + 1
            self.tile[self.curTile].height = (self.tile[self.curTile].rect.w - self.tile[self.curTile].rect.y) + 1
            self.tile[self.curTile].texBytes = int(self.tile[self.curTile].width * self.tile[self.curTile].height) << 1
            if (self.tile[self.curTile].texBytes >> 16) == 0xFFFF:
               self.tile[self.curTile].texBytes = self.tile[self.curTile].size << 16 >> 15
            self.tile[self.curTile].calculateSize()
         elif data[i] == 0xF4 or data[i] == 0xE4 or data[i] == 0xFE or data[i] == 0xFF:
            print("%08X : %08X" % (w0, w1))
         elif data[i] == 0xF5:
            self.tile[self.curTile].texFmt = (w0 >> 16) & 0xFF
            self.tile[self.curTile].txlSize = (w0 >> 19) & 0x03
            self.tile[self.curTile].lineSize = (w0 >> 9) & 0x1F
            self.tile[self.curTile].clip.x = (w1 >> 8) & 0x03
            self.tile[self.curTile].clip.y = (w1 >> 18) & 0x03
            self.tile[self.curTile].mask.x = (w1 >> 4) & 0x0F
            self.tile[self.curTile].mask.y = (w1 >> 14) & 0x0F
            self.tile[self.curTile].tshift.x = w1 & 0x0F
            self.tile[self.curTile].tshift.y = (w1 >> 10) & 0x0F
         elif data[i] == 0xFA:
            self.primColor = Vector([min(0.003922 * ((w1 >> 24) & 0xFF), 1.0), min(0.003922 * ((w1 >> 16) & 0xFF), 1.0), min(0.003922 * ((w1 >> 8) & 0xFF), 1.0)])
         elif data[i] == 0xFB:
            self.envColor = Vector([min(0.003922 * ((w1 >> 24) & 0xFF), 1.0), min(0.003922 * ((w1 >> 16) & 0xFF), 1.0), min(0.003922 * ((w1 >> 8) & 0xFF), 1.0)])
            if invertEnvColor:
               self.envColor = Vector([1.0, 1.0, 1.0]) - self.envColor
         elif data[i] == 0xFD:
            try:
               if data[i - 8] == 0xF2:
                  self.curTile = 1
               else:
                  self.curTile = 0
            except:
               pass
            try:
               if data[i + 8] == 0xE8:
                  self.tile[0].palette = w1
               else:
                  self.tile[self.curTile].data = w1
            except:
               pass
            has_tex = True

   def buildAnimations(self, hierarchy):
      pass


class ImportZ64(bpy.types.Operator, ImportHelper):
   """Load a Zelda64 File"""
   bl_idname	= "file.zobj"
   bl_label	= "Import Zelda64"
   bl_options	= {'PRESET', 'UNDO'}
   filename_ext	= ".zobj"
   filter_glob	= StringProperty(default="*.zobj;*.zmap", options={'HIDDEN'})
   loadOtherSegments = BoolProperty(name="Load Data From Other Segments",
                                    description="Load data from other segments",
                                    default=True,)
   vertexMode = EnumProperty(name="Vtx Mode",
                             items=(('COLORS', "COLORS", "Use vertex colors"),
                                    ('NORMALS', "NORMALS", "Use vertex normals as shading"),
                                    ('NONE', "NONE", "Don't use vertex colors or normals"),),
                             default='NORMALS',)
   enableMatrices = BoolProperty(name="Matrices",
                                 description="Enable texture mirroring",
                                 default=True,)
   enablePrimColor = BoolProperty(name="Prim Color",
                                  description="Enable blending with primitive color",
                                  default=True,)
   enableEnvColor = BoolProperty(name="Env Color",
                                 description="Enable blending with environment color",
                                 default=True,)
   invertEnvColor = BoolProperty(name="Invert Env Color",
                                 description="Invert environment color (temporary fix)",
                                 default=False,)
   exportTextures = BoolProperty(name="Export Textures",
                                 description="Export textures for the model",
                                 default=True,)
   importTextures = BoolProperty(name="Import Textures",
                                 description="Import textures for the model",
                                 default=True,)
   enableTexClamp = BoolProperty(name="Texture Clamp",
                                 description="Enable texture clamping",
                                 default=True,)
   enableTexMirror = BoolProperty(name="Texture Mirror",
                                  description="Enable texture mirroring",
                                  default=True,)
   enableToon = BoolProperty(name="Toony UVs",
                             description="Obtain a toony effect by not scaling down the uv coords",
                             default=False,)

   def execute(self, context):
      global fpath
      fpath, fext = os.path.splitext(self.filepath)
      fpath, fname = os.path.split(fpath)
      global vertexMode, enableMatrices
      global enablePrimColor, enableEnvColor, invertEnvColor
      global importTextures, exportTextures
      global enableTexClamp, enableTexMirror
      global enableMatrices, enableToon
      vertexMode = self.vertexMode
      enableMatrices = self.enableMatrices
      enablePrimColor = self.enablePrimColor
      enableEnvColor = self.enableEnvColor
      invertEnvColor = self.invertEnvColor
      importTextures = self.importTextures
      exportTextures = self.exportTextures
      enableTexClamp = self.enableTexClamp
      enableTexMirror = self.enableTexMirror
      enableToon = self.enableToon
      print("Importing '%s'..." % fname)
      time_start = time.time()
      f3dzex = F3DZEX()
      if self.loadOtherSegments:
         for i in range(16):
            f3dzex.setSegment(i, fpath + "/segment_%02X.zdata" % i)
      if fext.lower() == '.zmap':
         f3dzex.setSegment(0x03, self.filepath)
         f3dzex.importMap()
      else:
         f3dzex.setSegment(0x06, self.filepath)
         f3dzex.importObj()
      print("SUCCESS:  Elapsed time %.4f sec" % (time.time() - time_start))
      bpy.context.scene.update()
      return {'FINISHED'}

   def draw(self, context):
      layout = self.layout
      row = layout.row(align=True)
      row.prop(self, "vertexMode")
      row = layout.row(align=True)
      row.prop(self, "loadOtherSegments")
      box = layout.box()
      row = box.row(align=True)
      row.prop(self, "enableMatrices")
      row.prop(self, "enablePrimColor")
      row = box.row(align=True)
      row.prop(self, "enableEnvColor")
      row.prop(self, "invertEnvColor")
      row = box.row(align=True)
      row.prop(self, "exportTextures")
      row.prop(self, "importTextures")
      row = box.row(align=True)
      row.prop(self, "enableTexClamp")
      row.prop(self, "enableTexMirror")
      row = box.row(align=True)
      row.prop(self, "enableToon")

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
