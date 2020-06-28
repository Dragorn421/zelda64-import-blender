bl_info = {
    "name":        "Zelda64 Importer",
    "version":     (2, 0),
    "author":      "SoulofDeity",
    "blender":     (2, 6, 0),
    "location":    "File > Import-Export",
    "description": "Import Zelda64 - updated in 2020",
    "warning":     "",
    "wiki_url":    "https://github.com/Dragorn421/zelda64-import-blender",
    "tracker_url": "https://github.com/Dragorn421/zelda64-import-blender",
    "support":     'COMMUNITY',
    "category":    "Import-Export"}

"""Anim stuff: RodLima http://www.facebook.com/rod.lima.96?ref=tn_tnmn"""

import bpy, os, struct, time
import mathutils

from bpy import ops
from bpy.props import *
from bpy_extras.image_utils import load_image
from bpy_extras.io_utils import ExportHelper, ImportHelper
from math import *
from mathutils import *
from struct import pack, unpack_from

from mathutils import Vector, Euler, Matrix

# logging stuff, code mostly uses getLogger()
import logging

# https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility
logging_trace_level = 5
logging.addLevelName(logging_trace_level, 'TRACE')

def getLogger(name):
    global root_logger
    log = root_logger.getChild(name)
    def trace(message, *args, **kws):
        if log.isEnabledFor(logging_trace_level):
            log._log(logging_trace_level, message, args, **kws)
    log.trace = trace
    return log

def registerLogging(level=logging.INFO):
    global root_logger, root_logger_formatter, root_logger_stream_handler, root_logger_file_handler
    root_logger = logging.getLogger('z64import')
    root_logger_stream_handler = logging.StreamHandler()
    root_logger_file_handler = None
    root_logger_formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')
    root_logger_stream_handler.setFormatter(root_logger_formatter)
    root_logger.addHandler(root_logger_stream_handler)
    #root_logger.setLevel(1) # may be needed
    root_logger_stream_handler.setLevel(level)
    getLogger('setupLogging').debug('Logging OK')

def setLoggingLevel(level):
    global root_logger_stream_handler
    root_logger_stream_handler.setLevel(level)

def setLogFile(path):
    global root_logger, root_logger_formatter, root_logger_file_handler
    if root_logger_file_handler:
        root_logger.removeHandler(root_logger_file_handler)
        root_logger_file_handler = None
    if path:
        root_logger_file_handler = logging.FileHandler(path, mode='w')
        root_logger_file_handler.setFormatter(root_logger_formatter)
        root_logger.addHandler(root_logger_file_handler)
        # fixme logfile isn't logging TRACE
        root_logger_file_handler.setLevel(1)

def unregisterLogging():
    global root_logger, root_logger_stream_handler
    setLogFile(None)
    root_logger.removeHandler(root_logger_stream_handler)
#

def splitOffset(offset):
    return offset >> 24, offset & 0x00FFFFFF

def translateRotation(rot):
    """ axis, angle """
    return Matrix.Rotation(rot[3], 4, Vector(rot[:3]))

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

def checkUseVertexAlpha():
    global useVertexAlpha
    return useVertexAlpha

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
        # todo texture files are written several times, at each usage
        log = getLogger('Tile.create')
        if exportTextures:
            try:
                os.mkdir(fpath + "/textures")
            except FileExistsError:
                pass
            except:
                log.error('Could not create textures directory %s' % (fpath + "/textures"))
                pass
            #Noka here
            extrastring = ""
            w = self.rWidth
            if int(self.clip.x) & 1 != 0:
                if replicateTexMirrorBlender:
                    w <<= 1
                if enableTexMirrorSharpOcarinaTags:
                    extrastring += "#MirrorX"
            h = self.rHeight
            if int(self.clip.y) & 1 != 0:
                if replicateTexMirrorBlender:
                    h <<= 1
                if enableTexMirrorSharpOcarinaTags:
                    extrastring += "#MirrorY"
            if int(self.clip.x) & 2 != 0 and enableTexClampSharpOcarinaTags:
                extrastring += "#ClampX"
            if int(self.clip.y) & 2 != 0 and enableTexClampSharpOcarinaTags:
                extrastring += "#ClampY"
            self.current_texture_file_path = fpath + ("/textures/%08X" % self.data) + str(extrastring) + ".tga"
            log.debug('Writing texture %s (format 0x%02X)' % (self.current_texture_file_path, self.texFmt))
            file = open(self.current_texture_file_path, 'wb')
            if self.texFmt in (0x40, 0x48, 0x50):
                file.write(pack("<BBBHHBHHHHBB", 0, 1, 1, 0, 256, 24, 0, 0, w, h, 8, 0))
                self.writePalette(file, segment)
            else:
                file.write(pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 8))
            if int(self.clip.y) & 1 != 0 and replicateTexMirrorBlender:
                self.writeImageData(file, segment, True)
            else:
                self.writeImageData(file, segment)
            file.close()
        try:
            tex = bpy.data.textures.new(name="tex_%08X" % self.data, type='IMAGE')
            img = load_image(fpath + ("/textures/%08X" % self.data) + str(extrastring) + ".tga")
            if img:
                tex.image = img
                if int(self.clip.x) & 2 != 0 and enableTexClampBlender:
                    img.use_clamp_x = True
                if int(self.clip.y) & 2 != 0 and enableTexClampBlender:
                    img.use_clamp_y = True
            mtl = bpy.data.materials.new(name="mtl_%08X" % self.data)
            if enableShadelessMaterials:
                mtl.use_shadeless = True
            mt = mtl.texture_slots.add()
            mt.texture = tex
            mt.texture_coords = 'UV'
            mt.use_map_color_diffuse = True
            if self.texFmt in (0x40,0x60,0x48,0x50,0x00,0x08,0x10,0x68,0x70,0x18):
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
        if int(self.clip.x) & 1 != 0 and replicateTexMirrorBlender:
            self.ratio.x /= 2
        self.offset.x = self.rect.x
        self.ratio.y = (self.scale.y * self.shift.y) / self.rHeight
        if not enableToon:
            self.ratio.y /= 32;
        if int(self.clip.y) & 1 != 0 and replicateTexMirrorBlender:
            self.ratio.y /= 2
        self.offset.y = 1.0 + self.rect.y

    def writePalette(self, file, segment):
        log = getLogger('Tile.writePalette')
        if self.texFmt == 0x40:
            palSize = 16
        else:
            palSize = 256
        if not validOffset(segment, self.palette + int(palSize * 2) - 1):
            log.error('Segment offsets 0x%X-0x%X are invalid, writing black palette to %s (has the segment data been loaded?)' % (self.palette, self.palette + int(palSize * 2) - 1, self.current_texture_file_path))
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
        log = getLogger('Tile.writeImageData')
        if fy == True:
            dir = (0, self.rHeight, 1)
        else:
            dir = (self.rHeight - 1, -1, -1)
        if self.texFmt in (0x40, 0x60, 0x80, 0x90):
            bpp = 0.5
        elif self.texFmt in (0x00, 0x08, 0x10, 0x70):
            bpp = 2
        elif self.texFmt in (0x48, 0x50, 0x68, 0x88):
            bpp = 1
        elif self.texFmt in (0x18,):
            bpp = 4
        else:
            log.warning('Unknown texture format 0x%02X for texture %s' % (self.texFmt, self.current_texture_file_path))
            bpp = 4
        lineSize = self.rWidth * bpp
        if not validOffset(segment, self.data + int(self.rHeight * lineSize) - 1):
            log.error('Segment offsets 0x%X-0x%X are invalid, writing default fallback colors to %s (has the segment data been loaded?)' % (self.data, self.data + int(self.rHeight * lineSize) - 1, self.current_texture_file_path))
            size = self.rWidth * self.rHeight
            if int(self.clip.x) & 1 != 0 and replicateTexMirrorBlender:
                size *= 2
            if int(self.clip.y) & 1 != 0 and replicateTexMirrorBlender:
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
                # IA4
                elif self.texFmt == 0x60:
                    if floor(j) == j:
                        color = color >> 4
                    r = int(((color >> 1) & 0b111) * 255 / 7)
                    g = r
                    b = r
                    a = 255 if color & 1 else 0
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
                    line.append(a)
                else:
                    line.append((b << 24) | (g << 16) | (r << 8) | a)
                j += bpp
            if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
                file.write(pack("B" * len(line), *line))
            else:
                file.write(pack(">" + "L" * len(line), *line))
            if int(self.clip.x) & 1 != 0 and replicateTexMirrorBlender:
                line.reverse()
                if self.texFmt == 0x40 or self.texFmt == 0x48 or self.texFmt == 0x50:
                    file.write(pack("B" * len(line), *line))
                else:
                    file.write(pack(">" + "L" * len(line), *line))
        if int(self.clip.y) & 1 != 0 and df == False and replicateTexMirrorBlender:
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
        log = getLogger('Vertex.read')
        if not validOffset(segment, offset + 16):
            log.warning('Invalid segmented offset 0x%X for vertex' % (offset + 16))
            return
        seg, offset = splitOffset(offset)
        self.pos.x = unpack_from(">h", segment[seg], offset)[0]
        self.pos.z = unpack_from(">h", segment[seg], offset + 2)[0]
        self.pos.y = -unpack_from(">h", segment[seg], offset + 4)[0]
        global scaleFactor
        self.pos *= scaleFactor
        self.uv.x = float(unpack_from(">h", segment[seg], offset + 8)[0])
        self.uv.y = float(unpack_from(">h", segment[seg], offset + 10)[0])
        self.normal.x = 0.00781250 * unpack_from("b", segment[seg], offset + 12)[0]
        self.normal.z = 0.00781250 * unpack_from("b", segment[seg], offset + 13)[0]
        self.normal.y = 0.00781250 * unpack_from("b", segment[seg], offset + 14)[0]
        self.color[0] = min(0.00392157 * segment[seg][offset + 12], 1.0)
        self.color[1] = min(0.00392157 * segment[seg][offset + 13], 1.0)
        self.color[2] = min(0.00392157 * segment[seg][offset + 14], 1.0)
        if checkUseVertexAlpha():
            self.color[3] = min(0.00392157 * segment[seg][offset + 15], 1.0)


class Mesh:
    def __init__(self):
        self.verts, self.uvs, self.colors, self.faces = [], [], [], []
        self.vgroups = {}
        # import normals
        self.normals = []

    def create(self, hierarchy, offset):
        log = getLogger('Mesh.create')
        if len(self.faces) == 0:
            log.trace('Skipping empty mesh %08X', offset)
            return
        log.trace('Creating mesh %08X', offset)
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
        # todo import normals (saving them in blender is the weird part)
        """
        # doesn't work, blender eventually automatically recalculates normals
        for i in range(len(self.verts)):
            print(i)
            print(self.normals[i])
            me.vertices[i].normal = self.normals[i]
            print(me.vertices[i].normal)
        """
        """
        # https://blender.stackexchange.com/questions/104650/there-is-a-way-to-add-custom-split-normal-use-python-api/104664#104664
         # this does set normals in a way that would carry through to oot
        # however it seems like removing double vertices ruins most of it
        me.normals_split_custom_set([(0, 0, 0) for l in me.loops])
        me.normals_split_custom_set_from_vertices(self.normals)
        """
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
            mod.show_in_editmode = True
            mod.show_on_cage = True


class Limb:
    def __init__(self):
        self.parent, self.child, self.sibling = -1, -1, -1
        self.pos = Vector([0, 0, 0])
        self.near, self.far = 0x00000000, 0x00000000
        self.poseBone = None
        self.poseLocPath, self.poseRotPath = None, None
        self.poseLoc, self.poseRot = Vector([0, 0, 0]), None

    def read(self, segment, offset, actuallimb, BoneCount):
        seg, offset = splitOffset(offset)

        rot_offset = offset & 0xFFFFFF
        rot_offset += (0 * (BoneCount * 6 + 8));

        self.pos.x = unpack_from(">h", segment[seg], offset)[0]
        self.pos.z = unpack_from(">h", segment[seg], offset + 2)[0]
        self.pos.y = -unpack_from(">h", segment[seg], offset + 4)[0]
        global scaleFactor
        self.pos *= scaleFactor
        self.child = unpack_from("b", segment[seg], offset + 6)[0]
        self.sibling = unpack_from("b", segment[seg], offset + 7)[0]
        self.near = unpack_from(">L", segment[seg], offset + 8)[0]
        self.far = unpack_from(">L", segment[seg], offset + 12)[0]

        self.poseLoc.x = unpack_from(">h", segment[seg], rot_offset)[0]
        self.poseLoc.z = unpack_from(">h", segment[seg], rot_offset + 2)[0]
        self.poseLoc.y = unpack_from(">h", segment[seg], rot_offset + 4)[0]
        getLogger('Limb.read').trace("      Limb %r: %f,%f,%f", (actuallimb, self.poseLoc.x, self.poseLoc.z, self.poseLoc.y))

class Hierarchy:
    def __init__(self):
        self.name, self.offset = "", 0x00000000
        self.limbCount, self.dlistCount = 0x00, 0x00
        self.limb = []
        self.armature = None

    def read(self, segment, offset):
        log = getLogger('Hierarchy.read')
        self.dlistCount = None
        if not validOffset(segment, offset + 5):
            log.error('Invalid segmented offset 0x%X for hierarchy' % (offset + 5))
            return False
        if not validOffset(segment, offset + 9):
            log.warning('Invalid segmented offset 0x%X for hierarchy (incomplete header), still trying to import ignoring dlistCount' % (offset + 9))
            self.dlistCount = 1
        self.name = "sk_%08X" % offset
        self.offset = offset
        seg, offset = splitOffset(offset)
        limbIndex_offset = unpack_from(">L", segment[seg], offset)[0]
        if not validOffset(segment, limbIndex_offset):
            log.error("        ERROR:  Limb index table 0x%08X out of range" % limbIndex_offset)
            return False
        limbIndex_seg, limbIndex_offset = splitOffset(limbIndex_offset)
        self.limbCount = segment[seg][offset + 4]
        if not self.dlistCount:
            self.dlistCount = segment[seg][offset + 8]
        for i in range(self.limbCount):
            limb_offset = unpack_from(">L", segment[limbIndex_seg], limbIndex_offset + 4 * i)[0]
            limb = Limb()
            limb.index = i
            self.limb.append(limb)
            if validOffset(segment, limb_offset + 12):
                limb.read(segment, limb_offset, i, self.limbCount)
            else:
                log.error("        ERROR:  Limb 0x%02X offset 0x%08X out of range" % (i, limb_offset))[0]
        self.limb[0].pos = Vector([0, 0, 0])
        self.initLimbs(0x00)
        return True

    def create(self):
        rx, ry, rz = 90,0,0
        if (bpy.context.active_object):
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        for i in bpy.context.selected_objects:
            i.select = False
        self.armature = bpy.data.objects.new(self.name, bpy.data.armatures.new("%s_armature" % self.name))
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

        self.animTotal = 0
        self.TimeLine = 0
        self.TimeLinePosition = 0
        self.displaylists = []

        for i in range(16):
            self.segment.append([])
            self.vbuf.append(Vertex())
        for i in range(2):
            self.tile.append(Tile())
            self.vbuf.append(Vertex())
        for i in range(14 + 32):
            self.vbuf.append(Vertex())
        self.curTile = 0
        self.material = []
        self.hierarchy = []
        self.resetCombiner()

    def loaddisplaylists(self, path):
        log = getLogger('F3DZEX.loaddisplaylists')
        try:
             file = open(path, 'rb')
             self.displaylists = file.readlines()
             file.close()
             log.info("Loaded the display list list successfully!")
        except:
             log.info("Did not find displaylists.txt!")
             pass

    def loadSegment(self, seg, path):
        try:
            file = open(path, 'rb')
            self.segment[seg] = file.read()
            file.close()
        except:
            getLogger('F3DZEX.loadSegment').error('Could not load segment 0x%02X data from %s' % (seg, path))
            pass

    def locateHierarchies(self):
        log = getLogger('F3DZEX.locateHierarchies')
        data = self.segment[0x06]
        for i in range(0, len(data), 4):
            # test for header "bboooooo pp000000 xx000000": if segment bb=0x06 and offset oooooo 4-aligned and not zero parts (pp!=0)
            if data[i] == 0x06 and (data[i+3] & 3) == 0 and data[i+4] != 0:
                offset = unpack_from(">L", data, i)[0] & 0x00FFFFFF
                if offset < len(data):
                    # each Limb index entry is 4 bytes starting at offset
                    offset_end = offset + (data[i+4] << 2)
                    if offset_end <= len(data):
                        j = offset
                        while j < offset_end:
                            # test for limb entry "bboooooo": valid limb entry table as long as segment bb=0x06 and offset oooooo 4-aligned and offset is valid
                            if data[j] != 0x06 or (data[j+3] & 3) != 0 or (unpack_from(">L", data, j)[0] & 0x00FFFFFF) > len(data):
                                break
                            j += 4
                        if (j == i):
                            j |= 0x06000000
                            log.info("    hierarchy found at 0x%08X", j)
                            h = Hierarchy()
                            if h.read(self.segment, j):
                                self.hierarchy.append(h)
                            else:
                                log.warning('Skipping hierarchy at 0x%08X', j)

    def locateAnimations(self):
        log = getLogger('F3DZEX.locateAnimations')
        data = self.segment[0x06]
        self.animation = []
        self.offsetAnims = []
        self.durationAnims = []
        for i in range(0, len(data), 4):
            if ((data[i] == 0) and (data[i+1] > 1) and
                 (data[i+2] == 0) and (data[i+3] == 0) and
                 (data[i+4] == 0x06) and
                 (((data[i+5] << 16)|(data[i+6] << 8)|data[i+7]) < len(data)) and
                 (data[i+8] == 0x06) and
                 (((data[i+9] << 16)|(data[i+10] << 8)|data[i+11]) < len(data)) and
                 (data[i+14] == 0) and (data[i+15] == 0)):
                log.info("          Anims found at %08X Frames: %d", i, data[i+1] & 0x00FFFFFF)
                self.animation.append(i)
                self.offsetAnims.append(i)
                self.offsetAnims[self.animTotal] = (0x06 << 24) | i
                self.durationAnims.append(data[i+1] & 0x00FFFFFF)
                self.animTotal += 1
        if(self.animTotal > 0):
                log.info("          Total Anims                         : %d", self.animTotal)

    def locateExternAnimations(self):
        log = getLogger('F3DZEX.locateExternAnimations')
        data = self.segment[0x0F]
        self.animation = []
        self.offsetAnims = []
        for i in range(0, len(data), 4):
            if ((data[i] == 0) and (data[i+1] > 1) and
                 (data[i+2] == 0) and (data[i+3] == 0) and
                 (data[i+4] == 0x06) and
                 (((data[i+5] << 16)|(data[i+6] << 8)|data[i+7]) < len(data)) and
                 (data[i+8] == 0x06) and
                 (((data[i+9] << 16)|(data[i+10] << 8)|data[i+11]) < len(data)) and
                 (data[i+14] == 0) and (data[i+15] == 0)):
                log.info("          Ext Anims found at %08X" % i, "Frames:", data[i+1] & 0x00FFFFFF)
                self.animation.append(i)
                self.offsetAnims.append(i)
                self.offsetAnims[self.animTotal] = (0x0F << 24) | i
                self.animTotal += 1
        if(self.animTotal > 0):
            log.info("        Total Anims                   :", self.animTotal)

    def locateLinkAnimations(self):
        log = getLogger('F3DZEX.locateLinkAnimations')
        data = self.segment[0x04]
        self.animation = []
        self.offsetAnims = []
        self.animFrames = []
        self.animTotal = -1
        if (len( self.segment[0x04] ) > 0):
            if (MajorasAnims):
                for i in range(0xD000, 0xE4F8, 8):
                    self.animTotal += 1
                    self.animation.append(self.animTotal)
                    self.animFrames.append(self.animTotal)
                    self.offsetAnims.append(self.animTotal)
                    self.offsetAnims[self.animTotal]     = unpack_from(">L", data, i + 4)[0]
                    self.animFrames[self.animTotal] = unpack_from(">h", data, i)[0]
                    log.debug('- Animation #%d offset: %07X frames: %d', self.animTotal+1, self.offsetAnims[self.animTotal], self.animFrames[self.animTotal])
            else:
                for i in range(0x2310, 0x34F8, 8):
                    self.animTotal += 1
                    self.animation.append(self.animTotal)
                    self.animFrames.append(self.animTotal)
                    self.offsetAnims.append(self.animTotal)
                    self.offsetAnims[self.animTotal]     = unpack_from(">L", data, i + 4)[0]
                    self.animFrames[self.animTotal] = unpack_from(">h", data, i)[0]
                    log.debug('- Animation #%d offset: %07X frames: %d', self.animTotal+1, self.offsetAnims[self.animTotal], self.animFrames[self.animTotal])
        log.info("         Link has come to town!!!!")
        if ( (len( self.segment[0x07] ) > 0) and (self.animTotal > 0)):
            self.buildLinkAnimations(self.hierarchy[0], 0)

    def importMap(self):
        log = getLogger('F3DZEX.importMap')
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
                    log.info("            Mesh Type: %02X" % type)
                    if (data[mho+4] == 0x03 and start < end and end < len(data)):
                        log.info("            start %08X" % start)
                        log.info("            end %08X" % end)
                        if (type == 0):
                            for j in range(start, end, 4):
                                self.buildDisplayList(None, [None], unpack_from(">L", data, j)[0], False)
                        elif (type == 1 and count == 1):
                            #Noka here
                            end = start + 8
                            for j in range(start, end, 4):
                                self.buildDisplayList(None, [None], unpack_from(">L", data, j)[0], False)
                        elif (type == 2):
                            for j in range(start, end, 16):
                                near = (data[j+8] << 24)|(data[j+9] << 16)|(data[j+10] << 8)|data[j+11]
                                far = (data[j+12] << 24)|(data[j+13] << 16)|(data[j+14] << 8)|data[j+15]
                                if (near != 0):
                                    self.buildDisplayList(None, [None], near, False)
                                elif (far != 0):
                                    self.buildDisplayList(None, [None], far, False)
                return
            elif (data[i] == 0x14):
                break
        log.error("ERROR:  Map header not found")

    def importObj(self):
        log = getLogger('F3DZEX.importObj')
        log.info("Locating hierarchies...")
        self.locateHierarchies()

        if len(self.hierarchy) == 0:
            log.info("Found zilch. Using display lists, then...")
            if len(self.displaylists) == 0:
                log.info("...but none were found...")
            for dll in self.displaylists:
                s = dll.decode("utf-8")
                self.buildDisplayList(None, 0, int(s, 0), True)
            return

        for hierarchy in self.hierarchy:
            log.info("Building hierarchy '%s'..." % hierarchy.name)
            hierarchy.create()
            for i in range(hierarchy.limbCount):
                limb = hierarchy.limb[i]
                if limb.near != 0:
                    if validOffset(self.segment, limb.near):
                        log.info("    0x%02X : building display lists..." % i)
                        self.resetCombiner()
                        self.buildDisplayList(hierarchy, limb, limb.near, False)
                    else:
                        log.info("    0x%02X : out of range" % i)
                else:
                    log.info("    0x%02X : n/a" % i)
        if len(self.hierarchy) > 0:
            bpy.context.scene.objects.active = self.hierarchy[0].armature
            self.hierarchy[0].armature.select = True
            bpy.ops.object.mode_set(mode='POSE', toggle=False)
            global AnimtoPlay
            if (AnimtoPlay > 0):
                bpy.context.scene.frame_end = 1
                if(ExternalAnimes and len(self.segment[0x0F]) > 0):
                    self.locateExternAnimations()
                else:
                    self.locateAnimations()
                if len(self.animation) > 0:
                    for h in self.hierarchy:
                        if h.armature.animation_data is None:
                            h.armature.animation_data_create()
                    # use the hierarchy with most bones
                    # this works for building any animation regardless of its target skeleton (bone positions) because all limbs are named limb_XX, so the hierarchy with most bones has bones with same names as every other armature
                    # and the rotation and root location animated values don't rely on the actual armature used
                    # and in blender each action can be used for any armature, vertex groups/bone names just have to match
                    # this is useful for iron knuckles and anything with several hierarchies, although an unedited iron kunckles zobj won't work
                    hierarchy = max(self.hierarchy, key=lambda h:h.limbCount)
                    armature = hierarchy.armature
                    log.info('Building animations using armature %s in %s', armature.data.name, armature.name)
                    for i in range(len(self.animation)):
                        AnimtoPlay = i + 1
                        log.info("   Loading animation %d/%d", AnimtoPlay, len(self.animation))
                        action = bpy.data.actions.new('anim%d_%d' % (AnimtoPlay, self.durationAnims[i]))
                        # not sure what users an action is supposed to have, or what it should be linked to
                        action.use_fake_user = True
                        armature.animation_data.action = action
                        self.buildAnimations(hierarchy, 0)
                    for h in self.hierarchy:
                        h.armature.animation_data.action = action
                    bpy.context.scene.frame_end = max(self.durationAnims)
                else:
                    self.locateLinkAnimations()
            else:
                log.info("    Load anims OFF.")

    def resetCombiner(self):
        self.primColor = Vector([1.0, 1.0, 1.0, 1.0])
        self.envColor = Vector([1.0, 1.0, 1.0, 1.0])
        if checkUseVertexAlpha():
            self.vertexColor = Vector([1.0, 1.0, 1.0, 1.0])
        else:
            self.vertexColor = Vector([1.0, 1.0, 1.0])
        self.shadeColor = Vector([1.0, 1.0, 1.0])

    def getCombinerColor(self):
        def mult4d(v1, v2):
            return Vector([v1[i] * v2[i] for i in range(4)])
        cc = Vector([1.0, 1.0, 1.0, 1.0])
        if enablePrimColor:
            cc = mult4d(cc, self.primColor)
        if enableEnvColor:
            cc = mult4d(cc, self.envColor)
        if vertexMode == 'COLORS':
            cc = mult4d(cc, self.vertexColor.to_4d())
        elif vertexMode == 'NORMALS':
            cc = mult4d(cc, self.shadeColor.to_4d())
        if checkUseVertexAlpha():
            return cc
        else:
            return cc.xyz

    def buildDisplayList(self, hierarchy, limb, offset, static):
        log = getLogger('F3DZEX.buildDisplayList')
        if static:
            data = self.segment[0x6]
        else:
            data = self.segment[offset >> 24]

        mesh = Mesh()
        has_tex = False
        material = None
        if hierarchy:
            matrix = [limb]
        else:
            matrix = [None]
        log.debug('Reading dlists from %08X' % offset)
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
                            self.material.append(material)
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
                                mesh.verts.append((v3.pos.x, v3.pos.y, v3.pos.z))
                                # import normals
                                mesh.normals.append((v3.normal.x, v3.normal.y, v3.normal.z))
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
                                if checkUseVertexAlpha():
                                    self.vertexColor = Vector([v3.color[0], v3.color[1], v3.color[2], v3.color[3]])
                                else:
                                    self.vertexColor = Vector([v3.color[0], v3.color[1], v3.color[2]])
                                self.shadeColor = Vector([sc, sc, sc])
                                mesh.colors.append(self.getCombinerColor())
                                sc = (((v2.normal.x + v2.normal.y + v2.normal.z) / 3) + 1.0) / 2
                                if checkUseVertexAlpha():
                                    self.vertexColor = Vector([v2.color[0], v2.color[1], v2.color[2], v2.color[3]])
                                else:
                                    self.vertexColor = Vector([v2.color[0], v2.color[1], v2.color[2]])
                                self.shadeColor = Vector([sc, sc, sc])
                                mesh.colors.append(self.getCombinerColor())
                                sc = (((v1.normal.x + v1.normal.y + v1.normal.z) / 3) + 1.0) / 2
                                if checkUseVertexAlpha():
                                    self.vertexColor = Vector([v1.color[0], v1.color[1], v1.color[2], v1.color[3]])
                                else:
                                    self.vertexColor = Vector([v1.color[0], v1.color[1], v1.color[2]])
                                self.shadeColor = Vector([sc, sc, sc])
                                mesh.colors.append(self.getCombinerColor())
                                mesh.uvs.extend([
                                    (self.tile[0].offset.x + v3.uv.x * self.tile[0].ratio.x, self.tile[0].offset.y - v3.uv.y * self.tile[0].ratio.y),
                                    (self.tile[0].offset.x + v2.uv.x * self.tile[0].ratio.x, self.tile[0].offset.y - v2.uv.y * self.tile[0].ratio.y),
                                    (self.tile[0].offset.x + v1.uv.x * self.tile[0].ratio.x, self.tile[0].offset.y - v1.uv.y * self.tile[0].ratio.y),
                                    material
                                ])
                                if hierarchy:
                                    if v3.limb:
                                        if not (("limb_%02i" % v3.limb.index) in mesh.vgroups):
                                            mesh.vgroups["limb_%02i" % v3.limb.index] = []
                                        mesh.vgroups["limb_%02i" % v3.limb.index].append(vi3)
                                    if v2.limb:
                                        if not (("limb_%02i" % v2.limb.index) in mesh.vgroups):
                                            mesh.vgroups["limb_%02i" % v2.limb.index] = []
                                        mesh.vgroups["limb_%02i" % v2.limb.index].append(vi2)
                                    if v1.limb:
                                        if not (("limb_%02i" % v1.limb.index) in mesh.vgroups):
                                            mesh.vgroups["limb_%02i" % v1.limb.index] = []
                                        mesh.vgroups["limb_%02i" % v1.limb.index].append(vi1)
                                mesh.faces.append((vi1, vi2, vi3))
                                if vi1==vi2 or vi1==vi3 or vi2==vi3:
                                     log.warning('Found empty tri! %d %d %d' % (vi1, vi2, vi3))
                except:
                    for i in range(count):
                        mesh.verts.pop()
            elif data[i] == 0xD7:
#                for i in range(2):
#                    if ((w1 >> 16) & 0xFFFF) < 0xFFFF:
#                        self.tile[i].scale.x = ((w1 >> 16) & 0xFFFF) * 0.0000152587891
#                    else:
#                        self.tile[i].scale.x = 1.0
#                    if (w1 & 0xFFFF) < 0xFFFF:
#                        self.tile[i].scale.y = (w1 & 0xFFFF) * 0.0000152587891
#                    else:
#                        self.tile[i].scale.y = 1.0
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
                            matrix.append(matrixLimb)
                        else:
                            matrix[len(matrix) - 1] = matrixLimb
                    else:
                        matrix.append(matrix[len(matrix) - 1])
                elif hierarchy:
                    log.error("unknown limb %08X %08X" % (w0, w1))
            elif data[i] == 0xDE:
                mesh.create(hierarchy, offset)
                mesh.__init__()
                offset = (offset >> 24) | i + 8
                if validOffset(self.segment, w1):
                    self.buildDisplayList(hierarchy, limb, w1, False)
                if data[i + 1] != 0x00:
                    return
            elif data[i] == 0xDF:
                mesh.create(hierarchy, offset)
                return
            # handle "LOD dlists"
            elif data[i] == 0xE1:
                # 4 bytes starting at data[i+8+4] is a distance to check for displaying this dlist
                mesh.create(hierarchy, offset)
                mesh.__init__()
                offset = (offset >> 24) | i + 8
                if validOffset(self.segment, w1):
                    self.buildDisplayList(hierarchy, limb, w1, False)
                else:
                    log.warning('Invalid 0xE1 offset 0x%04X, skipping', w1)
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
                log.info("%08X : %08X", w0, w1)
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
                self.primColor = Vector([((w1 >> (8*(3-i))) & 0xFF) / 255 for i in range(4)])
                log.debug('new primColor -> %r', self.primColor)
                if enablePrimColor and self.primColor.w != 1 and not checkUseVertexAlpha():
                    log.warning('primColor %r has non-opaque alpha, merging it into vertex colors may produce unexpected results' % self.primColor)
                #self.primColor = Vector([min(((w1 >> 24) & 0xFF) / 255, 1.0), min(0.003922 * ((w1 >> 16) & 0xFF), 1.0), min(0.003922 * ((w1 >> 8) & 0xFF), 1.0), min(0.003922 * ((w1) & 0xFF), 1.0)])
            elif data[i] == 0xFB:
                self.envColor = Vector([((w1 >> (8*(3-i))) & 0xFF) / 255 for i in range(4)])
                log.debug('new envColor -> %r', self.envColor)
                if enableEnvColor and self.envColor.w != 1 and not checkUseVertexAlpha():
                    log.warning('envColor %r has non-opaque alpha, merging it into vertex colors may produce unexpected results' % self.envColor)
                #self.envColor = Vector([min(0.003922 * ((w1 >> 24) & 0xFF), 1.0), min(0.003922 * ((w1 >> 16) & 0xFF), 1.0), min(0.003922 * ((w1 >> 8) & 0xFF), 1.0)])
                if invertEnvColor:
                    self.envColor = Vector([1 - c for c in self.envColor])
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

    def LinkTpose(self, hierarchy):
        log = getLogger('F3DZEX.LinkTpose')
        segment = []
        data = self.segment[0x06]
        segment = self.segment
        RX, RY, RZ = 0,0,0
        BoneCount  = hierarchy.limbCount
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = True
        bonesIndx = [0,-90,0,0,0,0,0,0,0,90,0,0,0,180,0,0,-180,0,0,0,0]
        bonesIndy = [0,90,0,0,0,90,0,0,90,-90,-90,-90,0,0,0,90,0,0,90,0,0]
        bonesIndz = [0,0,0,0,0,0,0,0,0,0,0,0,0,-90,0,0,90,0,0,0,0]

        log.info("Link T Pose...")
        for i in range(BoneCount):
            bIndx = ((BoneCount-1) - i)
            if (i > -1):
                bone = hierarchy.armature.bones["limb_%02i" % (bIndx)]
                bone.select = True
                bpy.ops.transform.rotate(value = radians(bonesIndx[bIndx]), axis=(0, 0, 0), constraint_axis=(True, False, False))
                bpy.ops.transform.rotate(value = radians(bonesIndz[bIndx]), axis=(0, 0, 0), constraint_axis=(False, False, True))
                bpy.ops.transform.rotate(value = radians(bonesIndy[bIndx]), axis=(0, 0, 0), constraint_axis=(False, True, False))
                bpy.ops.pose.select_all(action="DESELECT")

        hierarchy.armature.bones["limb_00"].select = True ## Translations
        bpy.ops.transform.translate(value =(0, 0, 0), constraint_axis=(True, False, False))
        bpy.ops.transform.translate(value = (0, 0, 50), constraint_axis=(False, False, True))
        bpy.ops.transform.translate(value = (0, 0, 0), constraint_axis=(False, True, False))
        bpy.ops.pose.select_all(action="DESELECT")
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = False

        for i in range(BoneCount):
            bIndx = i
            if (i > -1):
                bone = hierarchy.armature.bones["limb_%02i" % (bIndx)]
                bone.select = True
                bpy.ops.transform.rotate(value = radians(-bonesIndy[bIndx]), axis=(0, 0, 0), constraint_axis=(False, True, False))
                bpy.ops.transform.rotate(value = radians(-bonesIndz[bIndx]), axis=(0, 0, 0), constraint_axis=(False, False, True))
                bpy.ops.transform.rotate(value = radians(-bonesIndx[bIndx]), axis=(0, 0, 0), constraint_axis=(True, False, False))
                bpy.ops.pose.select_all(action="DESELECT")

        hierarchy.armature.bones["limb_00"].select = True ## Translations
        bpy.ops.transform.translate(value =(0, 0, 0), constraint_axis=(True, False, False))
        bpy.ops.transform.translate(value = (0, 0, -50), constraint_axis=(False, False, True))
        bpy.ops.transform.translate(value = (0, 0, 0), constraint_axis=(False, True, False))
        bpy.ops.pose.select_all(action="DESELECT")

    def buildLinkAnimations(self, hierarchy, newframe):
        global AnimtoPlay
        global Animscount
        log = getLogger('F3DZEX.buildLinkAnimations')
        # todo buildLinkAnimations hasn't been rewritten/improved like buildAnimations has
        log.warning('The code to build link animations has not been improved/tested for a while, not sure what features it lacks compared to regular animations, pretty sure it will not import all animations')
        segment = []
        rot_indx = 0
        rot_indy = 0
        rot_indz = 0
        data = self.segment[0x06]
        segment = self.segment
        n_anims = self.animTotal
        seg, offset = splitOffset(hierarchy.offset)
        BoneCount  = hierarchy.limbCount
        RX, RY, RZ = 0,0,0
        frameCurrent = newframe

        if (AnimtoPlay > 0 and AnimtoPlay <= n_anims):
          currentanim = AnimtoPlay - 1
        else:
          currentanim = 0

        log.info("currentanim: %d frameCurrent: %d", currentanim+1, frameCurrent+1)
        AnimationOffset = self.offsetAnims[currentanim]
        TAnimationOffset = self.offsetAnims[currentanim]
        AniSeg = AnimationOffset >> 24
        AnimationOffset &= 0xFFFFFF
        rot_offset = AnimationOffset
        rot_offset += (frameCurrent * (BoneCount * 6 + 8))
        frameTotal = self.animFrames[currentanim]
        rot_offset += BoneCount * 6

        Trot_offset = TAnimationOffset & 0xFFFFFF
        Trot_offset += (frameCurrent * (BoneCount * 6 + 8))
        TRX = unpack_from(">h", segment[AniSeg], Trot_offset)[0]
        Trot_offset += 2
        TRZ = unpack_from(">h", segment[AniSeg], Trot_offset)[0]
        Trot_offset += 2
        TRY = -unpack_from(">h", segment[AniSeg], Trot_offset)[0]
        Trot_offset += 2
        BoneListListOffset = unpack_from(">L", segment[seg], offset)[0]
        BoneListListOffset &= 0xFFFFFF

        BoneOffset = unpack_from(">L", segment[seg], BoneListListOffset + (0 << 2))[0]
        S_Seg = (BoneOffset >> 24) & 0xFF
        BoneOffset &= 0xFFFFFF
        TRX += unpack_from(">h", segment[S_Seg], BoneOffset)[0]
        TRZ += unpack_from(">h", segment[S_Seg], BoneOffset + 2)[0]
        TRY += -unpack_from(">h", segment[S_Seg], BoneOffset + 4)[0]
        newLocx = TRX / 79
        newLocz = -25.5
        newLocz += TRZ / 79
        newLocy = TRY / 79

        bpy.context.scene.tool_settings.use_keyframe_insert_auto = True

        for i in range(BoneCount):
            bIndx = ((BoneCount-1) - i) # Had to reverse here, cuz didn't find a way to rotate bones on LOCAL space, start rotating from last to first bone on hierarchy GLOBAL.
            RX = unpack_from(">h", segment[AniSeg], rot_offset)[0]
            rot_offset -= 2
            RY = unpack_from(">h", segment[AniSeg], rot_offset + 4)[0]
            rot_offset -= 2
            RZ = unpack_from(">h", segment[AniSeg], rot_offset + 8)[0]
            rot_offset -= 2

            RX /= (182.04444444444444444444)
            RY /= (182.04444444444444444444)
            RZ /= (182.04444444444444444444)

            RXX = (RX)
            RYY = (-RZ)
            RZZ = (RY)

            log.trace('limb: %d RX %d RZ %d RY %d anim: %d frame: %d', bIndx, int(RXX), int(RZZ), int(RYY), currentanim+1, frameCurrent+1)
            if (i > -1):
                bone = hierarchy.armature.bones["limb_%02i" % (bIndx)]
                bone.select = True
                bpy.ops.transform.rotate(value = radians(RXX), axis=(0, 0, 0), constraint_axis=(True, False, False))
                bpy.ops.transform.rotate(value = radians(RZZ), axis=(0, 0, 0), constraint_axis=(False, False, True))
                bpy.ops.transform.rotate(value = radians(RYY), axis=(0, 0, 0), constraint_axis=(False, True, False))
                bpy.ops.pose.select_all(action="DESELECT")

        hierarchy.armature.bones["limb_00"].select = True ## Translations
        bpy.ops.transform.translate(value =(newLocx, 0, 0), constraint_axis=(True, False, False))
        bpy.ops.transform.translate(value = (0, 0, newLocz), constraint_axis=(False, False, True))
        bpy.ops.transform.translate(value = (0, newLocy, 0), constraint_axis=(False, True, False))
        bpy.ops.pose.select_all(action="DESELECT")

        if (frameCurrent < (frameTotal - 1)):## Next Frame ### Could have done some math here but... just reverse previus frame, so it just repose.
            bpy.context.scene.tool_settings.use_keyframe_insert_auto = False

            hierarchy.armature.bones["limb_00"].select = True ## Translations
            bpy.ops.transform.translate(value = (-newLocx, 0, 0), constraint_axis=(True, False, False))
            bpy.ops.transform.translate(value = (0, 0, -newLocz), constraint_axis=(False, False, True))
            bpy.ops.transform.translate(value = (0, -newLocy, 0), constraint_axis=(False, True, False))
            bpy.ops.pose.select_all(action="DESELECT")

            rot_offset = AnimationOffset
            rot_offset += (frameCurrent * (BoneCount * 6 + 8))
            rot_offset += 6
            for i in range(BoneCount):
                RX = unpack_from(">h", segment[AniSeg], rot_offset)[0]
                rot_offset += 2
                RY = unpack_from(">h", segment[AniSeg], rot_offset)[0]
                rot_offset += 2
                RZ = unpack_from(">h", segment[AniSeg], rot_offset)[0]
                rot_offset += 2

                RX /= (182.04444444444444444444)
                RY /= (182.04444444444444444444)
                RZ /= (182.04444444444444444444)

                RXX = (-RX)
                RYY = (RZ)
                RZZ = (-RY)

                log.trace("limb: %d RX %d RZ %d RY %d anim: %d frame: %d", i, int(RXX), int(RZZ), int(RYY), currentanim+1, frameCurrent+1)
                if (i > -1):
                    bone = hierarchy.armature.bones["limb_%02i" % (i)]
                    bone.select = True
                    bpy.ops.transform.rotate(value = radians(RYY), axis=(0, 0, 0), constraint_axis=(False, True, False))
                    bpy.ops.transform.rotate(value = radians(RZZ), axis=(0, 0, 0), constraint_axis=(False, False, True))
                    bpy.ops.transform.rotate(value = radians(RXX), axis=(0, 0, 0), constraint_axis=(True, False, False))
                    bpy.ops.pose.select_all(action="DESELECT")

            bpy.context.scene.frame_end += 1
            bpy.context.scene.frame_current += 1
            frameCurrent += 1
            self.buildLinkAnimations(hierarchy, frameCurrent)
        else:
            bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
            bpy.context.scene.frame_current = 1

    def buildAnimations(self, hierarchyMostBones, newframe):
        log = getLogger('F3DZEX.buildAnimations')
        rot_indx = 0
        rot_indy = 0
        rot_indz = 0
        Trot_indx = 0
        Trot_indy = 0
        Trot_indz = 0
        segment = self.segment
        RX, RY, RZ = 0,0,0
        n_anims = self.animTotal
        if (AnimtoPlay > 0 and AnimtoPlay <= n_anims):
            currentanim = AnimtoPlay - 1
        else:
            currentanim = 0

        AnimationOffset = self.offsetAnims[currentanim]
        #seg, offset = splitOffset(hierarchy.offset) # not used, MUST be not relevant because we use hierarchyMostBones (its armature) as placeholder
        BoneCountMax = hierarchyMostBones.limbCount
        armature = hierarchyMostBones.armature
        frameCurrent = newframe

        if not validOffset(segment, AnimationOffset):
            log.warning('Skipping invalid animation offset 0x%X', AnimationOffset)
            return

        AniSeg = AnimationOffset >> 24
        AnimationOffset &= 0xFFFFFF

        frameTotal = unpack_from(">h", segment[AniSeg], (AnimationOffset))[0]
        rot_vals_addr = unpack_from(">L", segment[AniSeg], (AnimationOffset + 4))[0]
        RotIndexoffset = unpack_from(">L", segment[AniSeg], (AnimationOffset + 8))[0]
        Limit = unpack_from(">h", segment[AniSeg], (AnimationOffset + 12))[0] # todo no idea what this is

        rot_vals_addr  &= 0xFFFFFF
        RotIndexoffset &= 0xFFFFFF

        rot_vals_max_length = int ((RotIndexoffset - rot_vals_addr) / 2)
        if rot_vals_max_length < 0:
            log.info('rotation indices (animation data) is located before indexed rotation values, this is weird but fine')
            rot_vals_max_length = (len(segment[AniSeg]) - rot_vals_addr) // 2
        rot_vals_cache = []
        def rot_vals(index, errorDefault=0):
            if index < 0 or (rot_vals_max_length and index >= rot_vals_max_length):
                log.trace('index in rotations table %d is out of bounds (rotations table is <= %d long)', index, rot_vals_max_length)
                return errorDefault
            if index >= len(rot_vals_cache):
                rot_vals_cache.extend(unpack_from(">h", segment[AniSeg], (rot_vals_addr) + (j * 2))[0] for j in range(len(rot_vals_cache),index+1))
                log.trace('Computed rot_vals_cache up to %d %r', index, rot_vals_cache)
            return rot_vals_cache[index]

        bpy.context.scene.tool_settings.use_keyframe_insert_auto = True
        bpy.context.scene.frame_end = frameTotal
        bpy.context.scene.frame_current = frameCurrent + 1

        log.log(
            logging.INFO if (frameCurrent + 1) % min(20, max(min(10, frameTotal), frameTotal // 3)) == 0 else logging.DEBUG,
            "anim: %d/%d frame: %d/%d", currentanim+1, self.animTotal, frameCurrent+1, frameTotal)

        ## Translations
        Trot_indx = unpack_from(">h", segment[AniSeg], RotIndexoffset)[0]
        Trot_indy = unpack_from(">h", segment[AniSeg], RotIndexoffset + 2)[0]
        Trot_indz = unpack_from(">h", segment[AniSeg], RotIndexoffset + 4)[0]

        if (Trot_indx >= Limit):
            Trot_indx += frameCurrent
        if (Trot_indz >= Limit):
            Trot_indz += frameCurrent
        if (Trot_indy >= Limit):
            Trot_indy += frameCurrent

        TRX = rot_vals(Trot_indx)
        TRZ = rot_vals(Trot_indy)
        TRY = rot_vals(Trot_indz)

        global scaleFactor
        newLocx =  TRX * scaleFactor
        newLocz =  TRZ * scaleFactor
        newLocy = -TRY * scaleFactor
        log.trace("X %d Y %d Z %d", int(TRX), int(TRY), int(TRZ))

        log.trace("       %d Frames %d still values %f tracks",frameTotal, Limit, ((rot_vals_max_length - Limit) / frameTotal)) # what is this debug message?
        for i in range(BoneCountMax):
            bIndx = ((BoneCountMax-1) - i) # Had to reverse here, cuz didn't find a way to rotate bones on LOCAL space, start rotating from last to first bone on hierarchy GLOBAL.

            if RotIndexoffset + (bIndx * 6) + 10 + 2 > len(segment[AniSeg]):
                log.trace('Ignoring bone %d in animation %d, rotation table does not have that many entries', bIndx, AnimtoPlay)
                continue

            rot_indexx = unpack_from(">h", segment[AniSeg], RotIndexoffset + (bIndx * 6) + 6)[0]
            rot_indexy = unpack_from(">h", segment[AniSeg], RotIndexoffset + (bIndx * 6) + 8)[0]
            rot_indexz = unpack_from(">h", segment[AniSeg], RotIndexoffset + (bIndx * 6) + 10)[0]

            rot_indx = rot_indexx
            rot_indy = rot_indexy
            rot_indz = rot_indexz

            if (rot_indx >= Limit):
                rot_indx += frameCurrent
            if (rot_indy >= Limit):
                rot_indy += frameCurrent
            if (rot_indz >= Limit):
                rot_indz += frameCurrent

            RX = rot_vals(rot_indx, False)
            RY = rot_vals(rot_indz, False)
            RZ = rot_vals(rot_indy, False)

            if RX is False or RY is False or RZ is False:
                log.trace('Ignoring bone %d in animation %d, rotation table did not have the entry', bIndx, AnimtoPlay)
                continue

            RX /= 182.04444444444444444444
            RY /= -182.04444444444444444444
            RZ /= 182.04444444444444444444

            RXX = radians(RX)
            RYY = radians(RY)
            RZZ = radians(RZ)

            log.trace("limb: %d XIdx: %d YIdx: %d ZIdx: %d frameTotal: %d", bIndx, rot_indexx, rot_indexy, rot_indexz, frameTotal)
            log.trace("limb: %d RX %d RZ %d RY %d anim: %d frame: %d frameTotal: %d", bIndx, int(RX), int(RZ), int(RY), currentanim+1, frameCurrent+1, frameTotal)
            if (bIndx > -1):
                bone = armature.data.bones["limb_%02i" % (bIndx)]
                bone.select = True
                bpy.ops.transform.rotate(value = RXX, axis=(0, 0, 0), constraint_axis=(True, False, False))
                bpy.ops.transform.rotate(value = RZZ, axis=(0, 0, 0), constraint_axis=(False, False, True))
                bpy.ops.transform.rotate(value = RYY, axis=(0, 0, 0), constraint_axis=(False, True, False))
                bpy.ops.pose.select_all(action="DESELECT")

        bone = armature.pose.bones["limb_00"]
        bone.location += mathutils.Vector((newLocx,newLocz,-newLocy))
        bone.keyframe_insert(data_path='location')

        ### Could have done some math here but... just reverse previus frame, so it just repose.
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = False

        bone = armature.pose.bones["limb_00"]
        bone.location -= mathutils.Vector((newLocx,newLocz,-newLocy))

        for i in range(BoneCountMax):
            bIndx = i

            if RotIndexoffset + (bIndx * 6) + 10 + 2 > len(segment[AniSeg]):
                log.trace('Ignoring bone %d in animation %d, rotation table does not have that many entries', bIndx, AnimtoPlay)
                continue

            rot_indexx = unpack_from(">h", segment[AniSeg], RotIndexoffset + (bIndx * 6) + 6)[0]
            rot_indexy = unpack_from(">h", segment[AniSeg], RotIndexoffset + (bIndx * 6) + 8)[0]
            rot_indexz = unpack_from(">h", segment[AniSeg], RotIndexoffset + (bIndx * 6) + 10)[0]

            rot_indx = rot_indexx
            rot_indy = rot_indexy
            rot_indz = rot_indexz

            if (rot_indx > Limit):
                rot_indx += frameCurrent
            if (rot_indy > Limit):
                rot_indy += frameCurrent
            if (rot_indz > Limit):
                rot_indz += frameCurrent

            RX = rot_vals(rot_indx, False)
            RY = rot_vals(rot_indz, False)
            RZ = rot_vals(rot_indy, False)

            if RX is False or RY is False or RZ is False:
                log.trace('Ignoring bone %d in animation %d, rotation table did not have the entry', bIndx, AnimtoPlay)
                continue

            RX /= -182.04444444444444444444
            RY /= 182.04444444444444444444
            RZ /= -182.04444444444444444444

            RXX = radians(RX)
            RYY = radians(RY)
            RZZ = radians(RZ)

            log.trace("limb: %d XIdx: %d YIdx: %d ZIdx: %d frameTotal: %d", i, rot_indexx, rot_indexy, rot_indexz, frameTotal)
            log.trace("limb: %d RX %d RZ %d RY %d anim: %d frame: %d frameTotal: %d", bIndx, int(RX), int(RZ), int(RY), currentanim+1, frameCurrent+1, frameTotal)
            if (bIndx > -1):
                bone = armature.data.bones["limb_%02i" % (bIndx)]
                bone.select = True
                bpy.ops.transform.rotate(value = RYY, axis=(0, 0, 0), constraint_axis=(False, True, False))
                bpy.ops.transform.rotate(value = RZZ, axis=(0, 0, 0), constraint_axis=(False, False, True))
                bpy.ops.transform.rotate(value = RXX, axis=(0, 0, 0), constraint_axis=(True, False, False))
                bpy.ops.pose.select_all(action="DESELECT")

        if (frameCurrent < (frameTotal - 1)):## Next Frame
            frameCurrent += 1
            self.buildAnimations(hierarchyMostBones, frameCurrent)
        else:
            bpy.context.scene.frame_current = 1

global Animscount
Animscount = 1

class ImportZ64(bpy.types.Operator, ImportHelper):
    """Load a Zelda64 File"""
    bl_idname    = "file.zobj2020"
    bl_label     = "Import Zelda64"
    bl_options   = {'PRESET', 'UNDO'}
    filename_ext = ".zobj"
    filter_glob  = StringProperty(default="*.zobj;*.zmap", options={'HIDDEN'})
    loadOtherSegments = BoolProperty(name="Load Data From Other Segments",
                                    description="Load data from other segments",
                                    default=True,)
    vertexMode = EnumProperty(name="Vtx Mode",
                             items=(('COLORS', "COLORS", "Use vertex colors"),
                                    ('NORMALS', "NORMALS", "Use vertex normals as shading"),
                                    ('NONE', "NONE", "Don't use vertex colors or normals"),),
                             default='NORMALS',)
    useVertexAlpha = BoolProperty(name="Use vertex alpha",
                                 description="Only enable if your version of blender has native support",
                                 default=(bpy.app.version == (2,79,7) and bpy.app.build_hash == b'10f724cec5e3'),)
    enableMatrices = BoolProperty(name="Matrices",
                                 description="Use 0xDA G_MTX and 0xD8 G_POPMTX commands",
                                 default=True,)
    enablePrimColor = BoolProperty(name="Prim Color",
                                  description="Enable blending with primitive color",
                                  default=False,) # this may be nice for strictly importing but exporting again will then not be exact
    enableEnvColor = BoolProperty(name="Env Color",
                                 description="Enable blending with environment color",
                                 default=False,) # same as primColor above
    invertEnvColor = BoolProperty(name="Invert Env Color",
                                 description="Invert environment color (temporary fix)",
                                 default=False,) # todo what is this?
    exportTextures = BoolProperty(name="Export Textures",
                                 description="Export textures for the model",
                                 default=True,)
    importTextures = BoolProperty(name="Import Textures",
                                 description="Import textures for the model",
                                 default=True,)
    enableTexClampBlender = BoolProperty(name="Texture Clamp",
                                 description="Enable texture clamping in Blender, used by Blender in the 3d viewport and by zzconvert",
                                 default=False,)
    replicateTexMirrorBlender = BoolProperty(name="Texture Mirror",
                                  description="Replicate texture mirroring by writing the textures with the mirrored parts (with double width/height) instead of the initial texture",
                                  default=False,)
    enableTexClampSharpOcarinaTags = BoolProperty(name="Texture Clamp SO Tags",
                                 description="Add #ClampX and #ClampY tags where necessary in the texture filename, used by SharpOcarina",
                                 default=False,)
    enableTexMirrorSharpOcarinaTags = BoolProperty(name="Texture Mirror SO Tags",
                                  description="Add #MirrorX and #MirrorY tags where necessary in the texture filename, used by SharpOcarina",
                                  default=False,)
    enableShadelessMaterials = BoolProperty(name="Shadeless Materials",
                                  description="Set materials to be shadeless, prevents using environment colors in-game",
                                  default=False,)
    enableToon = BoolProperty(name="Toony UVs",
                             description="Obtain a toony effect by not scaling down the uv coords",
                             default=False,)
    originalObjectScale = IntProperty(name="File Scale",
                             description="Scale of imported object, blender model will be scaled 1/(file scale) (use 1 for maps, actors are usually 100, 10 or 1) (0 defaults to 1 for maps and 100 for actors)",
                             default=0, min=0, soft_max=1000)
    loadAnimations = BoolProperty(name="Load animations",
                             description="For animated actors, load all animations or none",
                             default=True,)
    MajorasAnims = BoolProperty(name="MajorasAnims",
                             description="Majora's Mask Link's Anims.",
                             default=False,)
    ExternalAnimes = BoolProperty(name="ExternalAnimes",
                             description="Load External Animes.",
                             default=False,)
    setView3dParameters = BoolProperty(name="Set 3D View parameters",
                             description="For maps, use a more appropriate grid size and clip distance",
                             default=True,)
    logging_level = IntProperty(name="Log level",
                             description="(logs in the system console) The lower, the more logs. trace=%d debug=%d info=%d" % (logging_trace_level,logging.DEBUG,logging.INFO),
                             default=logging.INFO, min=1, max=51)
    logging_logfile = BoolProperty(name="Log to file",
                             description="Log everything to a file",
                             default=False,)

    def execute(self, context):
        global fpath
        fpath, fext = os.path.splitext(self.filepath)
        fpath, fname = os.path.split(fpath)
        global vertexMode, enableMatrices
        global useVertexAlpha
        global enablePrimColor, enableEnvColor, invertEnvColor
        global importTextures, exportTextures
        global enableTexClampBlender, replicateTexMirrorBlender
        global enableTexClampSharpOcarinaTags, enableTexMirrorSharpOcarinaTags
        global enableMatrices, enableToon
        global AnimtoPlay, MajorasAnims, ExternalAnimes
        vertexMode = self.vertexMode
        useVertexAlpha = self.useVertexAlpha
        enableMatrices = self.enableMatrices
        enablePrimColor = self.enablePrimColor
        enableEnvColor = self.enableEnvColor
        invertEnvColor = self.invertEnvColor
        importTextures = self.importTextures
        exportTextures = self.exportTextures
        enableTexClampBlender = self.enableTexClampBlender
        replicateTexMirrorBlender = self.replicateTexMirrorBlender
        enableTexClampSharpOcarinaTags = self.enableTexClampSharpOcarinaTags
        enableTexMirrorSharpOcarinaTags = self.enableTexMirrorSharpOcarinaTags
        enableToon = self.enableToon
        AnimtoPlay = 1 if self.loadAnimations else 0
        MajorasAnims = self.MajorasAnims
        ExternalAnimes = self.ExternalAnimes
        global enableShadelessMaterials
        enableShadelessMaterials = self.enableShadelessMaterials
        global scaleFactor
        if self.originalObjectScale == 0:
            if fext.lower() == '.zmap':
                scaleFactor = 1 # maps are actually stored 1:1
            else:
                scaleFactor = 1 / 100
        else:
            scaleFactor = 1 / self.originalObjectScale
        setLoggingLevel(self.logging_level)
        #setLoggingLevel(logging.DEBUG)
        log = getLogger('ImportZ64.execute')
        if self.logging_logfile:
            logfile_path = os.path.abspath('log_io_import_z64.txt')
            log.info('Writing logs to %s' % logfile_path)
            setLogFile(logfile_path)
        log.info("Importing '%s'..." % fname)
        time_start = time.time()
        f3dzex = F3DZEX()
        f3dzex.loaddisplaylists(os.path.join(fpath, "displaylists.txt"))
        if self.loadOtherSegments:
            log.debug('Loading other segments')
            # for segment 2, use [zmap prefix]_scene.zscene then segment_02.zdata then fallback to any .zscene
            scene_file = None
            if "_room" in fname:
                scene_file = fpath + "/" + fname[:fname.index("_room")] + "_scene.zscene"
            if not scene_file or not os.path.isfile(scene_file):
                scene_file = fpath + "/segment_02.zdata"
            if not scene_file or not os.path.isfile(scene_file):
                scene_file = None
                for f in os.listdir(fpath):
                    if f.endswith('.zscene'):
                        if segment_data_file:
                            log.warning('Found another .zscene file %s, keeping %s' % (f, segment_data_file))
                        else:
                            segment_data_file = fpath + '/' + f
            if scene_file and os.path.isfile(scene_file):
                log.info('Loading scene segment 0x02 from %s' % scene_file)
                f3dzex.loadSegment(2, scene_file)
            for i in range(16):
                if i == 2:
                    continue
                # I was told this is "ZRE" naming?
                segment_data_file = fpath + "/segment_%02X.zdata" % i
                if os.path.isfile(segment_data_file):
                    log.info('Loading segment 0x%02X from %s' % (i, segment_data_file))
                    f3dzex.loadSegment(i, segment_data_file)
                else:
                    log.debug('No file found to load segment 0x%02X from')
        if fext.lower() == '.zmap':
            log.debug('Importing map')
            f3dzex.loadSegment(0x03, self.filepath)
            f3dzex.importMap()
        else:
            log.debug('Importing object')
            f3dzex.loadSegment(0x06, self.filepath)
            f3dzex.importObj()

        #Noka here
        if fext.lower() == '.zmap' and self.setView3dParameters:
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        area.spaces.active.grid_lines = 500
                        area.spaces.active.grid_scale = 10
                        area.spaces.active.grid_subdivisions = 10
                        area.spaces.active.clip_end = 900000
        #

        log.info("SUCCESS:  Elapsed time %.4f sec" % (time.time() - time_start))
        bpy.context.scene.update()
        return {'FINISHED'}

    def draw(self, context):
        l = self.layout
        l.prop(self, "vertexMode")
        l.prop(self, "loadOtherSegments")
        l.prop(self, "originalObjectScale")
        box = l.box()
        box.prop(self, "enableTexClampBlender")
        box.prop(self, "replicateTexMirrorBlender")
        if self.replicateTexMirrorBlender:
            wBox = box.box()
            wBox.label(text='Enabling texture mirroring', icon='ERROR')
            wBox.label(text='will break exporting with', icon='ERROR')
            wBox.label(text='SharpOcarina, and may break', icon='ERROR')
            wBox.label(text='exporting in general with', icon='ERROR')
            wBox.label(text='other tools.', icon='ERROR')
        box.prop(self, "enableTexClampSharpOcarinaTags")
        box.prop(self, "enableTexMirrorSharpOcarinaTags")
        l.prop(self, "enableMatrices")
        l.prop(self, "enablePrimColor")
        l.prop(self, "enableEnvColor")
        l.prop(self, "invertEnvColor")
        l.prop(self, "exportTextures")
        l.prop(self, "importTextures")
        l.prop(self, "enableShadelessMaterials")
        l.prop(self, "enableToon")
        l.separator()
        l.prop(self, "loadAnimations")
        l.prop(self, "MajorasAnims")
        l.prop(self, "ExternalAnimes")
        l.prop(self, "setView3dParameters")
        l.separator()
        l.prop(self, "logging_level")
        l.prop(self, "logging_logfile")

def menu_func_import(self, context):
    self.layout.operator(ImportZ64.bl_idname, text="Zelda64 (.zobj;.zmap)")


def register():
    registerLogging()
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_func_import)
    unregisterLogging()


if __name__ == "__main__":
    register()
