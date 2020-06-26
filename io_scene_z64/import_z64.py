# <pep8-80 compliant>

import bmesh, bpy, math, mathutils, os, struct, time
from bpy import ops
from bpy_extras.image_utils import load_image
from bpy.props import *
from math import *
from mathutils import *
from struct import pack, unpack_from


class Limb:
   def __init__(self, i=0, p=Vector([0, 0, 0]), c=-1, s=-1, d=0):
      self.index = i
      self.pos = p
      self.parent = None
      self.child = c
      self.sibling = s
      self.dlist = d


class Vertex:
   def __init__(self):
      self.bone = 0
      self.pos = Vector([0, 0, 0])
      self.uv = Vector([0, 0])
      self.normal = Vector([0, 0, 0])
      self.color = Vector([0, 0, 0, 0])

class Tile:
   def __init__(self):
      self.offset = 0
      self.format = 0
      self.size = 0
      self.line = 0
      self.tmem = 0
      self.palette = 0
      self.width = 0
      self.height = 0
      self.rect = Vector([0, 0, 0, 0])
      self.clip = Vector([0, 0])
      self.mask = Vector([0, 0])
      self.shift = Vector([0, 0])
      self.scale = Vector([0, 0])

class Img:
   def __init__(self):
      self.offset = 0
      self.format = 0
      self.size = 0
      self.width = 0

class F3DZEX:
   def __init__(self):
      self.segment = []
      for i in range(16):
         self.segment.append([])
      self.vbuf = []
      for i in range(32):
         self.vbuf.append(Vertex())
      self.tile = []
      for i in range(8):
         self.tile.append(Tile())
      self.materials = {}
      self.tImg = Img()
      self.zImg = Img()
      self.cImg = Img()

   def dumpZMAP(self):
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
                        self.buildDisplayList(None, [None], 0, (data[j] << 24)|(data[j+1] << 16)|(data[j+2] << 8)|data[j+3])
                  elif (type == 2):
                     for j in range(start, end, 16):
                        near = (data[j+8] << 24)|(data[j+9] << 16)|(data[j+10] << 8)|data[j+11]
                        far = (data[j+12] << 24)|(data[j+13] << 16)|(data[j+14] << 8)|data[j+15]
                        if (near != 0):
                           self.buildDisplayList(None, [None], 0, near)
                        elif (far != 0):
                           self.buildDisplayList(None, [None], 0, far)
            return
         elif (data[i] == 0x14):
            break
      print("ERROR:  Map header not found")

   def dumpZOBJ(self):
      has_anim = False
      data = self.segment[0x06]
      for i in range(0, len(data), 4):
         if ((data[i] == 0x06) and ((data[i+3] & 3) == 0) and (data[i+4] != 0)):
            offset = unpack_from(">L", data, i)[0] & 0x00FFFFFF
            if (offset < len(data)):
               offset_end = offset + (data[i+4] << 2)
               if (offset_end < len(data)):
                  j = offset
                  while (j < offset_end):
                     if ((data[j] != 0x06) or ((data[j+3] & 3) != 0) or ((unpack_from(">L", data, j)[0] & 0x00FFFFFF) > len(data))):
                        break
                     j += 4
                  if (j == i):
                     print("   Found hierarchy at %08X" % i)
                     li = unpack_from(">L", data, i)[0] & 0x00FFFFFF
                     nLimbs = data[i+4]
                     limb = []
                     for j in range(nLimbs):
                        l = unpack_from(">L", data, li+j*4)[0] & 0x00FFFFFF
                        if (j > 0):
                           p = unpack_from(">hhh", data, l)
                        else:
                           p = [0, 0, 0]
                        c = unpack_from("b", data, l+6)[0]
                        s = unpack_from("b", data, l+7)[0]
                        d = unpack_from(">L", data, l+8)[0]
                        limb.append(Limb(j, Vector([p[0], p[2], p[1]]), c, s, d))
                     print("      Building Hierarchy...")
                     self.setupHierarchy(limb, 0)
                     a = self.buildSkinnedMesh(limb, 0x06000000 | i)
                     if not has_anim:
                        self.dumpAnimations(a, limb)
                        has_anim = True

   def setupHierarchy(self, limb, i):
      if (limb[i].child > -1 and limb[i].child != i):
         limb[limb[i].child].parent = i
         limb[limb[i].child].pos += limb[i].pos
         self.setupHierarchy(limb, limb[i].child)
      if (limb[i].sibling > -1 and limb[i].sibling != i):
         limb[limb[i].sibling].parent = limb[i].parent
         limb[limb[i].sibling].pos += limb[limb[i].parent].pos
         self.setupHierarchy(limb, limb[i].sibling)

   def buildSkinnedMesh(self, limb, offset):
      print("      Building Armature...")
      if (bpy.context.active_object):
         bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
      for i in bpy.context.selected_objects:
         i.select = False
      a = bpy.data.objects.new("sk_%08X" % offset, bpy.data.armatures.new("armature"))
      a.show_x_ray = True
      a.data.draw_type = 'STICK'
      bpy.context.scene.objects.link(a)
      bpy.context.scene.objects.active = a
      a.select = True
      bpy.ops.object.mode_set(mode='EDIT', toggle=False)
      for i in range(len(limb)):
         bone = a.data.edit_bones.new("limb_%02i" % i)
         bone.use_deform = True
         bone.head = limb[i].pos / 1024
      for i in range(len(limb)):
         bone = a.data.edit_bones["limb_%02i" % i]
         if (limb[i].parent != None):
            bone.parent = a.data.edit_bones["limb_%02i" % limb[i].parent]
            bone.use_connect = False
         bone.tail = bone.head + Vector([0, 0, 0.0001])
      bpy.ops.object.mode_set(mode='OBJECT')
      print("      Building Mesh...")
      for i in range(len(limb)):
         if (limb[i].dlist != 0):
            self.buildDisplayList(a, limb, limb[i].index, limb[i].dlist)
      bpy.context.scene.objects.active = a
      a.select = True
      bpy.ops.object.mode_set(mode='POSE')
      return a

   def getMatrixLimb(self, limb, mi):
      j = 0
      for i in range(len(limb)):
         if (limb[i].dlist != 0):
            if (j == mi):
               return limb[i]
            j += 1
      return limb[0]

   def setTexture(self):
      tex_seg = self.tile[0].offset >> 24
      tex_offset = self.tile[0].offset & 0x00FFFFFF
      tex_bpp = 8 * self.tile[0].size
      if (tex_bpp == 0):
         tex_bpp = 4
      elif (tex_bpp == 3):
         tex_bpp = 32
      tex_size = int(float(self.tile[0].width * self.tile[0].height * tex_bpp) / 8.0)
      if (self.tile[0].format == 2):
         has_pal = 1
         pal_seg = self.tile[7].offset >> 24
         pal_offset = self.tile[7].offset & 0x00FFFFFF
         pal_bpp = 8 * self.tile[7].size
         if (pal_bpp == 0):
            pal_bpp = 4
         elif (pal_bpp == 3):
            pal_bpp = 32
         pal_size = int(float(256 * pal_bpp) / 8.0)
      else:
         has_pal = 0
         pal_bpp = 0
      mtl_name = "mtl_%08X" % self.tile[0].offset
      if not(mtl_name in self.materials):
         try:
            os.mkdir(path+"/textures")
         except:
            pass
         try:
            desc = 0x20
            if (self.tile[0].format == 0):
               if (tex_bpp == 16):
                  desc |= 1
               elif (tex_bpp == 32):
                  desc |= 8
            elif (self.tile[0].format == 3):
               if (tex_bpp == 8):
                  desc |= 4
               elif (tex_bpp == 16):
                  desc |= 8
            file = open(path+"/textures/%08X.tga" % self.tile[0].offset, 'wb')
            file.write(pack("<BBBHHBHHHHBB", 0, has_pal, 2-has_pal, 0, 256*has_pal, 24*has_pal, 0, self.tile[0].height, self.tile[0].width, self.tile[0].height, 32-24*has_pal, desc))
            if (has_pal == 1):
               if (pal_seg < 16 and (pal_offset + pal_size - 1) < len(self.segment[pal_seg])):
                  for j in range(pal_offset, pal_offset + pal_size, 2):
                     color = (self.segment[pal_seg][j] << 8) | self.segment[pal_seg][j + 1]
                     r = (color & 0xF800) >> 11
                     g = (color & 0x07C0) >> 6
                     b = (color & 0x003E) >> 1
                     a = (color & 0x0001)
                     file.write(pack("BBB", 8*b, 8*g, 8*r))
               else:
                  for j in range(pal_size):
                     file.write(pack("BBB", 0, 0, 0))
               if (tex_bpp == 4):
                  for j in range(tex_offset, tex_offset + tex_size):
                     file.write(pack("BB", self.segment[tex_seg][j] >> 4, self.segment[tex_seg][j] & 0x0F))
               else:
                  for j in range(tex_offset, tex_offset + tex_size):
                     file.write(pack("B", self.segment[tex_seg][j]))
            elif (tex_seg < 16 and (tex_offset + tex_size - 1) < len(self.segment[tex_seg])):
               if (tex_bpp == 4):
                  for j in range(tex_offset, tex_offset + tex_size):
                     c1 = 16*(self.segment[tex_seg][j] >> 4)
                     c2 = 16*(self.segment[tex_seg][j] & 0x0F)
                     file.write(pack("BBBBBBBB", c1, c1, c1, 0xFF, c2, c2, c2, 0xFF))
               elif (tex_bpp == 8):
                  for j in range(tex_offset, tex_offset + tex_size):
                     if (self.tile[0].format == 3):
                        c1 = 16*(self.segment[tex_seg][j] >> 4)
                        c2 = 16*(self.segment[tex_seg][j] & 0x0F)
                        file.write(pack("BBBBBBBB", c1, c1, c1, c2, c2, c2, c2, c2))
                     else:
                        c = self.segment[tex_seg][j]
                        file.write(pack("BBBB", c, c, c, 0xFF))
               elif (tex_bpp == 16):
                  for j in range(tex_offset, tex_offset + tex_size, 2):
                     if (self.tile[0].format == 0):
                        color = (self.segment[tex_seg][j] << 8) | self.segment[tex_seg][j + 1]
                        r = (color & 0xF800) >> 11
                        g = (color & 0x07C0) >> 6
                        b = (color & 0x003E) >> 1
                        a = (color & 0x0001)
                        file.write(pack("BBBB", 8*b, 8*g, 8*r, 255*a))
                     else:
                        c1 = self.segment[tex_seg][j]
                        c2 = self.segment[tex_seg][j+1]
                        file.write(pack("BBBB", c1, c1, c1, c2))
               elif (tex_bpp == 32):
                  for j in range(0, tex_size, 4):
                     file.write(pack("B", self.segment[tex_seg][(tex_offset & 0x00FFFFFF) + j + 2]))
                     file.write(pack("B", self.segment[tex_seg][(tex_offset & 0x00FFFFFF) + j + 1]))
                     file.write(pack("B", self.segment[tex_seg][(tex_offset & 0x00FFFFFF) + j]))
                     file.write(pack("B", self.segment[tex_seg][(tex_offset & 0x00FFFFFF) + j + 3]))
            else:
               print("%02X%06X : %08X " % (tex_seg, tex_offset, tex_size), tex_bpp, self.tile[0].width, self.tile[0].height)
               for j in range(tex_size):
                  file.write(pack("B", 0))
            file.close()
            img = load_image(path + "/textures/%08X.tga" % self.tile[0].offset)
            if (self.tile[0].clip.x == 2):
               img.use_clamp_x = True
            if (self.tile[0].clip.y == 2):
               img.use_clamp_y = True
            tex = bpy.data.textures.new(name="tex_%08X" % self.tile[0].offset, type='IMAGE')
            tex.image = img
            mtl = bpy.data.materials.new(name=mtl_name)
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
            self.materials[mtl_name] = mtl
         except:
            print("         WARNING: Failed to dump texture %08X" % self.tImg.offset)
      return self.materials.get(mtl_name)

   def buildDisplayList(self, a, limb, li, dl):
      data = self.segment[dl >> 24]
      verts = []
      colors = []
      uvs = []
      faces = []
      vgroups = {}
      mtl = None
      has_tex = False
      if (a != None):
         mv = [limb[li]]
      for i in range(dl & 0x00FFFFFF, len(data), 8):
         if (data[i] == 0x01):
            count = (data[i+1] << 4) | (data[i+2] >> 4)
            index = (data[i+3] >> 1) - count
            offset = (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            if (data[i+4] < 16):
               if ((offset + count * 16) < len(self.segment[data[i+4]])):
                  for j in range(0, count):
                     self.vbuf[index + j].pos.x = unpack_from(">h", self.segment[data[i+4]], offset + j * 16)[0]
                     self.vbuf[index + j].pos.z = unpack_from(">h", self.segment[data[i+4]], offset + j * 16 + 2)[0]
                     self.vbuf[index + j].pos.y = unpack_from(">h", self.segment[data[i+4]], offset + j * 16 + 4)[0]
                     if (a != None):
                        self.vbuf[index + j].bone = mv[len(mv)-1].index
                        self.vbuf[index + j].pos += mv[len(mv)-1].pos
                     self.vbuf[index + j].pos /= 1024
                     self.vbuf[index + j].uv.x = float(unpack_from(">h", self.segment[data[i+4]], offset + j * 16 + 8)[0]) / 32
                     self.vbuf[index + j].uv.y = float(unpack_from(">h", self.segment[data[i+4]], offset + j * 16 + 10)[0]) / 32
                     self.vbuf[index + j].normal.x = 1.0/128.0*unpack_from("b", self.segment[data[i+4]], offset + j * 16 + 12)[0]
                     self.vbuf[index + j].normal.y = 1.0/128.0*unpack_from("b", self.segment[data[i+4]], offset + j * 16 + 13)[0]
                     self.vbuf[index + j].normal.z = 1.0/128.0*unpack_from("b", self.segment[data[i+4]], offset + j * 16 + 14)[0]
                     self.vbuf[index + j].color.x = 1.0/255.0*unpack_from("B", self.segment[data[i+4]], offset + j * 16 + 12)[0]
                     self.vbuf[index + j].color.y = 1.0/255.0*unpack_from("B", self.segment[data[i+4]], offset + j * 16 + 13)[0]
                     self.vbuf[index + j].color.z = 1.0/255.0*unpack_from("B", self.segment[data[i+4]], offset + j * 16 + 14)[0]
                     self.vbuf[index + j].color.w = 1.0/255.0*unpack_from("B", self.segment[data[i+4]], offset + j * 16 + 15)[0]
         elif (data[i] == 0x02):
            vtx = (data[i+2] << 7) | (data[i+3] >> 1)
            val = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
            if (data[i+1] == 0x00):
               self.vbuf[index + j].pos.z = (unpack_from(">h", self.segment[data[i+4]], offset + j * 16)[0] + mv[len(mv)-1].pos.x) / 1024
            elif (data[i+1] == 0x02):
               self.vbuf[index + j].pos.y = (unpack_from(">h", self.segment[data[i+4]], offset + j * 16 + 2)[0] + mv[len(mv)-1].pos.x) / 1024
            elif (data[i+1] == 0x04):
               self.vbuf[index + j].pos.x = (unpack_from(">h", self.segment[data[i+4]], offset + j * 16 + 4)[0] + mv[len(mv)-1].pos.x) / 1024
         elif (data[i] == 0x05 or data[i] == 0x06):
            if (has_tex):
               mtl = self.setTexture()
               has_tex = False
            v1, v2, v3 = None, None, None
            vi1, vi2, vi3 = 0, 0, 0
            for j in range(1, (data[i]-4)*4):
               if (j != 4):
                  v3 = self.vbuf[data[i + j] >> 1]
                  vi3 = -1
                  for k in range(len(verts)):
                     if (verts[k][0] == v3.pos.x and verts[k][1] == v3.pos.y and verts[k][2] == v3.pos.z):
                        vi3 = k
                  if (vi3 == -1):
                     vi3 = len(verts)
                     verts.extend([(v3.pos.x, v3.pos.y, v3.pos.z)])
                     if (a != None):
                        if not (("limb_%02i" % v3.bone) in vgroups):
                           vgroups["limb_%02i" % v3.bone] = []
                        vgroups["limb_%02i" % v3.bone].extend([vi3])
                  if (j == 1 or j == 5):
                     v1 = v3
                     vi1 = vi3
                  elif (j == 2 or j == 6):
                     v2 = v3
                     vi2 = vi3
                  elif (j == 3 or j == 7):
                     n1 = 0.5 * (((v1.normal.x + v1.normal.y + v1.normal.z) / 3) + 1)
                     n2 = 0.5 * (((v2.normal.x + v2.normal.y + v2.normal.z) / 3) + 1)
                     n3 = 0.5 * (((v3.normal.x + v3.normal.y + v3.normal.z) / 3) + 1)
                     colors.extend([((n1, n1, n1), (n2, n2, n2), (n3, n3, n3))])
                     uvs.extend([(mtl, Vector([(v1.uv.x+self.tile[0].rect.x)/self.tile[0].scale.x, (self.tile[0].height-(v1.uv.y+self.tile[0].rect.y))/self.tile[0].scale.y]),
                                       Vector([(v2.uv.x+self.tile[0].rect.x)/self.tile[0].scale.x, (self.tile[0].height-(v2.uv.y+self.tile[0].rect.y))/self.tile[0].scale.y]),
                                       Vector([(v3.uv.x+self.tile[0].rect.x)/self.tile[0].scale.x, (self.tile[0].height-(v3.uv.y+self.tile[0].rect.y))/self.tile[0].scale.y]))])
                     faces.extend([(vi1, vi2, vi3)])
         elif (data[i] == 0xDA and a != None):
            l = self.getMatrixLimb(limb, ((data[i+5] << 16) | (data[i+6] << 8) | data[i+7]) / 0x40)
            if ((data[i+3] & 0x04) == 0):
               if ((data[i+3] & 0x02) == 0):
                  l = Limb(l.index, l.pos + mv[len(mv)-1].pos, l.child, l.sibling, l.dlist)
               if ((data[i+3] & 0x01) == 0):
                  mv.append(l)
               else:
                  mv[len(mv)-1] = l
         elif (data[i] == 0xD8 and a != None):
            if (len(mv) > 0):
               mv.pop()
         elif (data[i] == 0xDE or data[i] == 0xDF or data[i] == 0xE7 or (i == len(data)-8 and data[i] != 0xDF)):
            if (len(faces) > 0):
               me = bpy.data.meshes.new("me_%08X" % dl)
               ob = bpy.data.objects.new("ob_%08X" % dl, me)
               bpy.context.scene.objects.link(ob)
               bpy.context.scene.objects.active = ob
               ob.select = True
               me.vertices.add(len(verts))
               for j in range(len(verts)):
                 me.vertices[j].co = verts[j]
               me.tessfaces.add(len(faces))
               vcd = me.tessface_vertex_colors.new().data
               for j in range(len(faces)):
                  me.tessfaces[j].vertices = faces[j]
                  vcd[j].color1.r, vcd[j].color1.g, vcd[j].color1.b = colors[j][0]
                  vcd[j].color2.r, vcd[j].color2.g, vcd[j].color2.b = colors[j][1]
                  vcd[j].color3.r, vcd[j].color3.g, vcd[j].color3.b = colors[j][2]
               uvd = me.tessface_uv_textures.new().data
               for j in range(len(faces)):
                  if (uvs[j][0] != None):
                     if not(uvs[j][0].name in me.materials):
                        me.materials.append(uvs[j][0])
                     uvd[j].image = uvs[j][0].texture_slots[0].texture.image
                  uvd[j].uv[0][0], uvd[j].uv[0][1] = uvs[j][1].x, uvs[j][1].y
                  uvd[j].uv[1][0], uvd[j].uv[1][1] = uvs[j][2].x, uvs[j][2].y
                  uvd[j].uv[2][0], uvd[j].uv[2][1] = uvs[j][3].x, uvs[j][3].y
               me.calc_normals()
               me.validate()
               me.update()
               if (a != None):
                  for name, vgroup in vgroups.items():
                     grp = ob.vertex_groups.new(name)
                     for v in vgroup:
                        grp.add([v], 1.0, 'REPLACE')
                  ob.parent = a
                  mod = ob.modifiers.new(a.name, 'ARMATURE')
                  mod.object = a
                  mod.use_bone_envelopes = False
                  mod.use_vertex_groups = True
               ob.select = False
               verts = []
               normals = []
               colors = []
               uvs = []
               faces = []
               vgroups = {}
               dl = (dl & 0xFF000000) | i
               if (data[i] == 0xDE):
                  self.buildDisplayList(a, limb, mv[len(mv)-1].index, ((data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]))
                  if (data[i+1] == 0x00):
                     dl += 8
                  else:
                     break
            if (data[i] == 0xDF):
               break
         elif (data[i] == 0xF0):
            has_tex = True
            self.tile[7].format = self.tImg.format
            self.tile[7].size = self.tImg.size
            self.tile[7].offset = self.tImg.offset
         elif (data[i] == 0xF2 and data[i+4] < 8):
            has_tex = True
            self.tile[data[i+4]].offset = self.tImg.offset
            self.tile[data[i+4]].rect.x = ((data[i+1] << 4) | (data[i+2] >> 4)) >> 2
            self.tile[data[i+4]].rect.y = (((data[i+2] & 0x0F) << 8) | data[i+3]) >> 2
            self.tile[data[i+4]].rect.z = ((data[i+5] << 4) | (data[i+6] >> 4)) >> 2
            self.tile[data[i+4]].rect.w = (((data[i+6] & 0x0F) << 8) | data[i+7]) >> 2
            self.tile[data[i+4]].scale.x = (self.tile[data[i+4]].rect.z - self.tile[data[i+4]].rect.x) + 1
            self.tile[data[i+4]].scale.y = (self.tile[data[i+4]].rect.w - self.tile[data[i+4]].rect.y) + 1
            self.tile[data[i+4]].width = int(self.tile[data[i+4]].scale.x)
            self.tile[data[i+4]].height = int(self.tile[data[i+4]].scale.y)
         elif (data[i] == 0xF5 and data[i+4] < 8):
            self.tile[data[i+4]].format = data[i+1] >> 5
            self.tile[data[i+4]].size = (data[i+1] & 0x18) >> 3
            self.tile[data[i+4]].line = ((data[i+1] & 0x03) << 7) | (data[i+2] >> 1)
            self.tile[data[i+4]].tmem = ((data[i+2] & 0x01) << 8) | data[i+3]
            self.tile[data[i+4]].palette = data[i+5] >> 4
            self.tile[data[i+4]].clip.y = (data[i+5] & 0x0C) >> 2
            self.tile[data[i+4]].mask.y = ((data[i+5] & 0x03) << 2) | (data[i+6] >> 6)
            self.tile[data[i+4]].shift.y = (data[i+6] & 0x3C) >> 2
            self.tile[data[i+4]].clip.x = data[i+6] & 0x03
            self.tile[data[i+4]].mask.x = data[i+7] >> 4
            self.tile[data[i+4]].shift.x = data[i+7] & 0x0F
         elif (data[i] == 0xFD):
            self.tImg.format = data[i+1] >> 5
            self.tImg.size = (data[i+1] & 0x18) >> 3
            self.tImg.width = ((data[i+2] & 0x0F) << 8) | data[i+3]
            self.tImg.offset = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
         elif (data[i] == 0xFE):
            self.zImg.format = data[i+1] >> 5
            self.zImg.size = (data[i+1] & 0x18) >> 3
            self.zImg.width = ((data[i+2] & 0x0F) << 8) | data[i+3]
            self.zImg.offset = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]
         elif (data[i] == 0xFF):
            self.cImg.format = data[i+1] >> 5
            self.cImg.size = (data[i+1] & 0x18) >> 3
            self.cImg.width = ((data[i+2] & 0x0F) << 8) | data[i+3]
            self.cImg.offset = (data[i+4] << 24) | (data[i+5] << 16) | (data[i+6] << 8) | data[i+7]

   def dumpAnimations(self, a, limb):
      data = self.segment[0x06]
      print("      Building animations...")
      a.animation_data_create()
      for i in range(len(limb)):
         limb[i].pose = a.pose.bones.get("limb_%02i" % i)
      limb[0].loc_path = limb[i].pose.path_from_id("location")
      for i in range(len(limb)):
         limb[i].pose.rotation_mode = 'XZY'
         limb[i].rot_path = limb[i].pose.path_from_id("rotation_euler")
      for i in range(0, len(data), 4):
         if ((data[i] == 0) and (data[i+1] > 1) and
             (data[i+2] == 0) and (data[i+3] == 0) and
             (data[i+4] == 0x06) and
             (((data[i+5] << 16)|(data[i+6] << 8)|data[i+7]) < len(data)) and
             (data[i+8] == 0x06) and
             (((data[i+9] << 16)|(data[i+10] << 8)|data[i+11]) < len(data)) and
             (data[i+14] == 0) and (data[i+15] == 0)):
            print("         found at %08X" % i)
            self.buildAnimation(a, limb, i)

   def buildAnimation(self, a, limb, anm):
      data = self.segment[0x06]
      frameCount = data[anm + 1]
      rv = (data[anm + 5] << 16)|(data[anm + 6] << 8)|data[anm + 7]
      ri = (data[anm + 9] << 16)|(data[anm + 10] << 8)|data[anm + 11]
      limit = (data[anm + 12] << 8)|data[anm + 13]
      bpy.context.scene.frame_start = 1
      bpy.context.scene.frame_end = 101
      bpy.context.scene.frame_current = 1
      action = bpy.context.blend_data.actions.new("anm_%08X" % anm)
      a.animation_data.action = action
      limb[0].loc = [action.fcurves.new(limb[0].loc_path, index = 0),
                     action.fcurves.new(limb[0].loc_path, index = 1),
                     action.fcurves.new(limb[0].loc_path, index = 2)]
      for i in range(len(limb)):
         limb[i].rot = [action.fcurves.new(limb[i].rot_path, index=0),
                        action.fcurves.new(limb[i].rot_path, index=1),
                        action.fcurves.new(limb[i].rot_path, index=2)]


def load(operator, context, filepath):
   print("Importing \"%s\"..." % filepath)
   global path
   path = os.path.dirname(filepath)
   fname, fext = os.path.splitext(filepath)
   time_start = time.time()
   f3dzex = F3DZEX()
   file = open(filepath, 'rb')
   if (fext.lower() == '.zmap'):
      f3dzex.segment[0x03] = file.read()
   else:
      f3dzex.segment[0x06] = file.read()
   file.close()
   for i in range(16):
      try:
         file = open(path+"/segment_%02X.zdata" % i, 'rb')
         f3dzex.segment[i] = file.read()
         file.close()
      except:
         pass
   if (fext.lower() == '.zmap'):
      f3dzex.dumpZMAP()
   else:
      f3dzex.dumpZOBJ()
   print("SUCCESS:  Elapsed time %.4f sec" % (time.time() - time_start))
   bpy.context.scene.update()
   return {'FINISHED'}
