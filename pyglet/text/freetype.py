#!/usr/bin/env python

'''
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

from pyglet.gl import *

from ctypes import *
from ctypes import util
from warnings import warn

from pyglet.text import *
from pyglet.text.freetype_lib import *

# fontconfig library definitions

path = util.find_library('fontconfig')
if not path:
    raise ImportError('Cannot locate fontconfig library')
fontconfig = cdll.LoadLibrary(path)

FcResult = c_int

fontconfig.FcPatternBuild.restype = c_void_p
fontconfig.FcFontMatch.restype = c_void_p
fontconfig.FcFreeTypeCharIndex.restype = c_uint

FC_FAMILY = 'family'
FC_SIZE = 'size'
FC_SLANT = 'slant'
FC_WEIGHT = 'weight'
FC_FT_FACE = 'ftface'
FC_FILE = 'file'

FC_WEIGHT_REGULAR = 80
FC_WEIGHT_BOLD = 200

FC_SLANT_ROMAN = 0
FC_SLANT_ITALIC = 100

(FcTypeVoid,
 FcTypeInteger,
 FcTypeDouble, 
 FcTypeString, 
 FcTypeBool,
 FcTypeMatrix,
 FcTypeCharSet,
 FcTypeFTFace,
 FcTypeLangSet) = range(9)
FcType = c_int

(FcMatchPattern,
 FcMatchFont) = range(2)
FcMatchKind = c_int

class _FcValueUnion(Union):
    _fields_ = [
        ('s', c_char_p),
        ('i', c_int),
        ('b', c_int),
        ('d', c_double),
        ('m', c_void_p),
        ('c', c_void_p),
        ('f', c_void_p),
        ('p', c_void_p),
        ('l', c_void_p),
    ]

class FcValue(Structure):
    _fields_ = [
        ('type', FcType),
        ('u', _FcValueUnion)
    ]

# End of library definitions


# Hehe, battlestar galactica... (sorry.  was meant to be short for "fraction")
def frac(value):
    return int(value * 64)

def unfrac(value):
    return value >> 6

class FreeTypeGlyphRenderer(GlyphRenderer):
    def __init__(self, font):
        super(FreeTypeGlyphRenderer, self).__init__(font)
        self.font = font

    def render(self, text):
        face = self.font.face
        glyph_index = fontconfig.FcFreeTypeCharIndex(byref(face), ord(text[0]))
        error = FT_Load_Glyph(face, glyph_index, FT_LOAD_RENDER)
        if error != 0:
            raise FontException('Could not load glyph for "c"' % text[0], error) 
        glyph_slot = face.glyph.contents
        width = glyph_slot.bitmap.width
        height = glyph_slot.bitmap.rows
        baseline = height - glyph_slot.bitmap_top
        lsb = glyph_slot.bitmap_left
        advance = unfrac(glyph_slot.advance.x)
        pitch = glyph_slot.bitmap.pitch  # 1 component, so no alignment prob.

        # pitch should be negative, but much faster to just swap tex_coords
        image = ImageData(width, height, 'A', glyph_slot.bitmap.buffer, pitch)
        glyph = self.font.create_glyph(image) 
        glyph.set_bearings(baseline, lsb, advance)
        glyph.tex_coords = (glyph.tex_coords[3],
                            glyph.tex_coords[2],
                            glyph.tex_coords[1],
                            glyph.tex_coords[0])

        return glyph

class FreeTypeFont(BaseFont):
    glyph_renderer_class = FreeTypeGlyphRenderer

    def __init__(self, name, size, bold=False, italic=False):
        super(FreeTypeFont, self).__init__()
        ft_library = ft_get_library()

        match = self.get_fontconfig_match(name, size, bold, italic)
        if not match:
            raise FontException('Could not match font "%s"' % name)

        f = FT_Face()
        if fontconfig.FcPatternGetFTFace(match, FC_FT_FACE, 0, byref(f)) != 0:
            value = FcValue()
            result = fontconfig.FcPatternGet(match, FC_FILE, 0, byref(value))
            if result != 0:
                raise FontException('No filename or FT face for "%s"' % name)
            result = FT_New_Face(ft_library, value.u.s, 0, byref(f))
            if result:
                raise FontException('Could not load "%s": %d' % (name, result))

        fontconfig.FcPatternDestroy(match)

        self.face = f.contents

        FT_Set_Char_Size(self.face, 0, frac(size), 0, 0)
        self.ascent = self.face.ascender * size / self.face.units_per_EM
        self.descent = self.face.descender * size / self.face.units_per_EM

    @staticmethod
    def get_fontconfig_match(name, size, bold, italic):
        if bold:
            bold = FC_WEIGHT_BOLD
        else:
            bold = FC_WEIGHT_REGULAR

        if italic:
            italic = FC_SLANT_ITALIC
        else:
            italic = FC_SLANT_ROMAN

        fontconfig.FcInit()

        pattern = fontconfig.FcPatternCreate()
        fontconfig.FcPatternAddDouble(pattern, FC_SIZE, c_double(size))
        fontconfig.FcPatternAddInteger(pattern, FC_WEIGHT, bold)
        fontconfig.FcPatternAddInteger(pattern, FC_SLANT, italic)
        fontconfig.FcPatternAddString(pattern, FC_FAMILY, name)
        fontconfig.FcConfigSubstitute(0, pattern, FcMatchPattern)
        fontconfig.FcDefaultSubstitute(pattern)

        # Look for a font that matches pattern
        result = FcResult()
        match = fontconfig.FcFontMatch(0, pattern, byref(result))
        fontconfig.FcPatternDestroy(pattern)
        
        return match

    @classmethod
    def have_font(cls, name):
        value = FcValue()
        match = cls.get_fontconfig_match(name, 12, False, False)
        result = fontconfig.FcPatternGet(match, FC_FAMILY, 0, byref(value))
        return value.u.s == name
