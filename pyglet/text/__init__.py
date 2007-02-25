#!/usr/bin/env python

'''

TODO in near future:
 - Kerning
 - Character spacing
 - Word spacing

TODO much later:
 - BIDI
 - Vertical text
 - Path following?
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

import sys
import os

from pyglet.gl import *
from pyglet.window import *
from pyglet.image import *

class Glyph(TextureRegion):
    advance = 0
    vertices = (0, 0, 0, 0)

    def set_bearings(self, baseline, left_side_bearing, advance):
        self.advance = advance
        self.vertices = (
            left_side_bearing,
            -baseline,
            left_side_bearing + self.width,
            -baseline + self.height)

    def draw(self):
        '''Debug method: use the higher level APIs for performance and
        kerning.'''
        glBindTexture(GL_TEXTURE_2D, self.owner.id)
        glBegin(GL_QUADS)
        self.draw_quad_vertices()
        glEnd()

    def draw_quad_vertices(self):
        '''Debug method: use the higher level APIs for performance and
        kerning.'''
        glTexCoord2f(self.tex_coords[0][0], self.tex_coords[0][1])
        glVertex2f(self.vertices[0], self.vertices[1])
        glTexCoord2f(self.tex_coords[1][0], self.tex_coords[1][1])
        glVertex2f(self.vertices[2], self.vertices[1])
        glTexCoord2f(self.tex_coords[2][0], self.tex_coords[2][1])
        glVertex2f(self.vertices[2], self.vertices[3])
        glTexCoord2f(self.tex_coords[3][0], self.tex_coords[3][1])
        glVertex2f(self.vertices[0], self.vertices[3])

    def get_kerning_pair(self, right_glyph):
        return 0

class GlyphTextureAtlas(Texture):
    region_class = Glyph
    x = 0
    y = 0
    line_height = 0

    def apply_blend_state(self):
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)

    def fit(self, image):
        '''Places `image` within the texture, returns a TextureRegion for
        that image.
        Returns None if image doesn't fit.
        '''
        if self.x + image.width > self.texture.width:
            self.x = 0
            self.y += self.line_height
            self.line_height = 0
        if self.y + image.height > self.texture.height:
            return None

        self.line_height = max(self.line_height, image.height)
        region = self.get_region(
            self.x, self.y, image.width, image.height)
        region.blit_into(image, 0, 0, 0)
        self.x += image.width
        return region

class GlyphRenderer(object):
    def __init__(self, font):
        pass

    def render(self, text):
        raise NotImplementedError('Subclass must override')

class GlyphString(object):
    '''An immutable string of glyphs that can be rendererd quickly.
    '''

    def __init__(self, text, glyphs, x=0, y=0):
        '''Initialise the string with the given sequence of glyphs, and
        optional offset in x and y.  Note that no attributes of this
        class are mutable.
        '''
        # Create an interleaved array in GL_T2F_V3F format and determine
        # state changes required.
        
        lst = []
        texture = None
        self.text = text
        self.states = []
        self.cumulative_advance = [] # for fast post-string breaking
        state_from = 0
        state_length = 0
        for i, glyph in enumerate(glyphs):
            if glyph.owner != texture:
                if state_length:
                    self.states.append((state_from, state_length, texture))
                texture = glyph.owner
                state_from = i
                state_length = 0
            state_length += 1
            lst += [glyph.tex_coords[0][0], glyph.tex_coords[0][1],
                    x + glyph.vertices[0], y + glyph.vertices[1], 0.,
                    glyph.tex_coords[1][0], glyph.tex_coords[1][1],
                    x + glyph.vertices[2], y + glyph.vertices[1], 0.,
                    glyph.tex_coords[2][0], glyph.tex_coords[2][1],
                    x + glyph.vertices[2], y + glyph.vertices[3], 0.,
                    glyph.tex_coords[3][0], glyph.tex_coords[3][1],
                    x + glyph.vertices[0], y + glyph.vertices[3], 0.]
            x += glyph.advance
            self.cumulative_advance.append(x)
        self.states.append((state_from, state_length, texture))

        self.array = (c_float * len(lst))(*lst)
        self.width = x

    def get_break_index(self, from_index, width):
        '''Return valid breakpoint after from_index so that text
        between from_index and breakpoint fits within width.  Uses
        precomputed cumulative glyph widths to give quick answer.

        Returns from_index if there is no valid breakpoint in range.
        '''
        to_index = from_index
        if from_index:
            width += self.cumulative_advance[from_index-1]
        for i, (c, w) in enumerate(
                zip(self.text[from_index:], 
                    self.cumulative_advance[from_index:])):
            if w > width:
                return to_index 
            if c == '\n':
                return i + from_index + 1
            elif c in u'\u0020\u200b':
                to_index = i + from_index + 1
        return to_index

    def get_subwidth(self, from_index, to_index):
        width = self.cumulative_advance[to_index-1] 
        if from_index:
            width -= self.cumulative_advance[from_index-1]
        return width

    def draw(self, from_index=0, to_index=None):
        '''Draw the glyph string.  Assumes texture state is enabled.
        '''
        if from_index == to_index or not self.text:
            return

        # XXX Safe to assume all required textures will use same blend state I
        # think.  (otherwise move this into loop)
        self.states[0][2].apply_blend_state()

        if from_index:
            glTranslatef(-self.cumulative_advance[from_index-1], 0, 0)
        if to_index is None:
            to_index = len(self.text)

        glInterleavedArrays(GL_T2F_V3F, 0, self.array)
        for state_from, state_length, texture in self.states:
            if state_from + state_length < from_index:
                continue
            state_from = max(state_from, from_index)
            state_length = min(state_length, to_index - state_from)
            if state_length <= 0:
                break
            glBindTexture(GL_TEXTURE_2D, texture.id)
            glDrawArrays(GL_QUADS, state_from * 4, state_length * 4)

class FontException(Exception):
    pass

class BaseFont(object):
    texture_width = 256
    texture_height = 256
    texture_internalformat = GL_ALPHA

    # These should also be set by subclass when known
    ascent = 0
    descent = 0

    glyph_renderer_class = GlyphRenderer
    texture_class = GlyphTextureAtlas

    def __init__(self):
        self.textures = []
        self.glyphs = {}

    @classmethod
    def add_font_data(cls, data):
        # Ignored unless overridden
        pass

    @classmethod
    def have_font(cls, name):
        # Subclasses override
        return True

    def create_glyph(self, image):
        glyph = None
        for texture in self.textures:
            glyph = texture.fit(image)
            if glyph:
                break
        if not glyph:
            if image.width > self.texture_width or \
               image.height > self.texture_height:
                texture = self.texture_class.create_for_size(GL_TEXTURE_2D,
                    image.width * 2, image.height * 2,
                    self.texture_internalformat)
                self.texture_width = texture.width
                self.texture_height = texture.height
            else:
                texture = self.texture_class.create_for_size(GL_TEXTURE_2D,
                    self.texture_width, self.texture_height,
                    self.texture_internalformat)
            self.textures.insert(0, texture)
            glyph = texture.fit(image)
        return glyph

    def get_glyphs(self, text):
        '''Create and return a list of Glyphs for 'text'.
        '''
        glyph_renderer = None
        glyphs = []         # glyphs that are committed.
        for c in text:
            # Get the glyph for 'c'
            if c not in self.glyphs:
                if not glyph_renderer:
                    glyph_renderer = self.glyph_renderer_class(self)
                self.glyphs[c] = glyph_renderer.render(c)
            glyphs.append(self.glyphs[c])
        return glyphs


    def get_glyphs_for_width(self, text, width):
        '''Create and return a list of Glyphs that fit within 'width',
        beginning with the text 'text'.  If the entire text is larger than
        'width', as much as possible will be used while breaking after
        a space or zero-width space character.  If a newline is enountered
        in text, only text up to that newline will be used.  If no break
        opportunities (newlines or spaces) occur within 'width', the text
        up to the first break opportunity will be used (this will exceed
        'width').  If there are no break opportunities, the entire text
        will be used.
        '''
        glyph_renderer = None
        glyph_buffer = []   # next glyphs to be added, as soon as a BP is found
        glyphs = []         # glyphs that are committed.
        for c in text:
            if c == '\n':
                glyphs += glyph_buffer
                break

            # Get the glyph for 'c'
            if c not in self.glyphs:
                if not glyph_renderer:
                    glyph_renderer = self.glyph_renderer_class(self)
                self.glyphs[c] = glyph_renderer.render(c)
            glyph = self.glyphs[c]
            
            # Add to holding buffer and measure
            glyph_buffer.append(glyph)
            width -= glyph.advance
            
            # If over width and have some committed glyphs, finish.
            if width <= 0 and len(glyphs) > 0:
                break

            # If a valid breakpoint, commit holding buffer
            if c in u'\u0020\u200b':
                glyphs += glyph_buffer
                glyph_buffer = []

        # If nothing was committed, commit everything (no breakpoints found).
        if len(glyphs) == 0:
            glyphs = glyph_buffer

        return glyphs

# Load platform dependent module
if sys.platform == 'darwin':
    from pyglet.text.carbon import CarbonFont
    _font_class = CarbonFont
elif sys.platform == 'win32':
    from pyglet.text.win32 import Win32Font
    _font_class = Win32Font
else:
    from pyglet.text.freetype import FreeTypeFont
    _font_class = FreeTypeFont

def load_font(name, size, bold=False, italic=False):
    '''Load a font for rendering.

    :Parameters:
        `name` : str, or list of str
            Font family, for example, "Times New Roman".  If a list of names
            is provided, the first one matching a known font is used.  If no
            font can be matched to the name(s), a default font is used.
        `size` : float
            Size of the font, in points.  The returned font may be an exact
            match or the closest available.
        `bold` : bool
            If True, a bold variant is returned, if one exists for the given
            family and size.
        `italic` : bool
            If True, an italic variant is returned, if one exists for the given
            family and size.

    :rtype: `BaseFont`
    '''
    # Find first matching name
    if type(name) in (tuple, list):
        for n in name:
            if _font_class.have_font(n):
                name = n
                break
        else:
            name = None

    # Locate or create font cache   
    shared_object_space = get_current_context().get_shared_object_space()
    if not hasattr(shared_object_space, 'pyglet_text_font_cache'):
        shared_object_space.pyglet_text_font_cache = {}
    font_cache = shared_object_space.pyglet_text_font_cache

    # Look for font name in font cache
    descriptor = (name, size, bold, italic)
    if descriptor in font_cache:
        return font_cache[descriptor]

    # Not in cache, create from scratch
    font = _font_class(name, size, bold=bold, italic=italic)
    font_cache[descriptor] = font
    return font

def add_font(font):
    if type(font) in (str, unicode):
        font = open(font, 'r')
    if hasattr(font, 'read'):
        font = font.read()
    _font_class.add_font_data(font)


def add_font_dir(dir):
    import os
    for file in os.listdir(dir):
        if file[:-4].lower() == '.ttf':
            add_font(file)

# Deprectated API:
def Font(*args, **kwargs):
    import warnings
    warnings.warn('Font is deprecated, use load_font.')
    load_font(*args, **kwargs)

