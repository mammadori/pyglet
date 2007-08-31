import sys
import string

from pyglet.gl import *
from pyglet.window import key, mouse

from wydget import event, anim, util, element
from wydget.widgets.frame import Frame
from wydget.widgets.label import Label
from wydget import clipboard

# for detecting words later
letters = set(string.letters)

class Cursor(element.Element):
    name = '-text-cursor'
    def __init__(self, color, *args, **kw):
        self.color = color
        self.alpha = 1
        self.animation = None
        super(Cursor, self).__init__(*args, **kw)
    def draw(self, *args):
        pass
    def _render(self, rect):
        glPushAttrib(GL_ENABLE_BIT|GL_CURRENT_BIT)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)
        color = self.color[:3] + (self.alpha,)
        glColor4f(*color)
        glRectf(rect.x, rect.y, rect.x + rect.width, rect.y + rect.height)
        glPopAttrib()

    def enable(self):
        self.setVisible(True)
        self.animation = CursorAnimation(self)

    def disable(self):
        self.setVisible(False)
        if self.animation is not None:
            self.animation.cancel()
            self.animation = None

class CursorAnimation(anim.Animation):
    def __init__(self, element):
        self.element = element
        super(CursorAnimation, self).__init__()
        self.paused = 0

    def pause(self):
        self.element.alpha = 1
        self.paused = .5

    def animate(self, dt):
        if self.paused > 0:
            self.paused -= dt
            if self.paused < 0:
                self.paused = 0
            return
        self.anim_time += dt
        if self.anim_time % 1 < .5:
            self.element.alpha = 1
        else:
            self.element.alpha = 0.2

class TextInputLine(Label):
    name = '-text-input-line'
    is_focusable = True
    def __init__(self, parent, text, *args, **kw):
        self.cursor_index = len(text)
        if 'is_password' in kw:
            self.is_password = kw.pop('is_password')
        else:
            self.is_password = False
        kw['border'] = None
        super(TextInputLine, self).__init__(parent, text, *args, **kw)

        self.cursor = Cursor(self.color, self, 1, 0, 0, 1, self.font_size,
            is_visible=False)
        self.highlight = None

    def selectWord(self, pos):
        if self.is_password:
            return self.selectAll()

        # clicks outside the bounds should select the last item in the text
        if pos >= len(self.text):
            pos = len(self.text) - 1

        # determine whether we should select a word, some whitespace or
        # just a single char of punctuation
        current = self.text[pos]
        if current == ' ':
            allowed = set(' ')
        elif current in letters:
            allowed = letters
        else:
            self.highlight = (pos, pos+1)
            return

        # scan back to the start of the thing
        for start in range(pos, -1, -1):
            if self.text[start] not in allowed:
                start += 1
                break

        # scan up to the end of the thing
        for end in range(pos, len(self.text)):
            if self.text[end] not in allowed:
                break
        else:
            end += 1
        self.highlight = (start, end)

    def selectAll(self):
        self.highlight = (0, len(self.text))

    def clearSelection(self):
        self.highlight = None

    def setText(self, text):
        self._text = text

        if self.is_password:
            text = u'\u2022' * len(text)

        if text:
            style = self.getStyle()
            self.glyphs = style.getGlyphString(text, size=self.font_size)
            self.image = style.text(text, font_size=self.font_size,
                color=self.color, valign='top')
            self.width = self.image.width
            self.height = self.image.height
        else:
            self.glyphs = None
            self.image = None
            self.width = 0
            self.height = self.font_size

        # move cursor
        self.setCursorPosition(self.cursor_index)

    text = property(lambda self: self._text, setText)

    def editText(self, text, move=0):
        '''Either insert at the current cursor position or replace the
        current highlight.
        '''
        i = self.cursor_index
        if self.highlight:
            s, e = self.highlight
            text = self.text[0:s] + text + self.text[e:]
            self.highlight = None
        else:
            text = self.text[0:i] + text + self.text[i:]
        self.setText(text)
        self.setCursorPosition(i+move)
        self.getGUI().dispatch_event(self, 'on_change', text)

    def render(self, rect):
        super(TextInputLine, self).render(rect)
        if self.cursor.is_visible:
            self.cursor._render(self.cursor.rect)

        if self.highlight is not None:
            start, end = self.highlight
            if start:
                start = self.glyphs.get_subwidth(0, start)
            end = self.glyphs.get_subwidth(0, end)

            glPushAttrib(GL_ENABLE_BIT|GL_CURRENT_BIT)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_BLEND)
            glColor4f(.8, .8, 1, .5)
            glRectf(start, 0, end, rect.height)
            glPopAttrib()
               
    def determineIndex(self, x):
        diff = abs(x)
        if self.glyphs is None:
            return 0
        index = 0
        for advance in self.glyphs.cumulative_advance:
            new_diff = abs(x - advance)
            if new_diff > diff: break
            index += 1
            diff = new_diff
        return min(len(self.text), index)

    def setCursorPosition(self, index):
        if index >= len(self.text):
            index = len(self.text)
        direction = index - self.cursor_index

        self.cursor_index = index

        # determine position in self.glyphs
        if not self.text or index == 0:
            cursor_text_width = 0
        else:
            cursor_text_width = self.glyphs.get_subwidth(0, index)

        parent_width = self.parent.inner_rect.width
        cursor_x = cursor_text_width + self.x

        # offset for current self.image offset
        if direction > 0:
            if cursor_x > parent_width:
                self.x = - (cursor_text_width - parent_width)
        else:
            if cursor_x < 0:
                self.x = -(cursor_text_width)

        if hasattr(self, 'cursor'):
            self.cursor.x = max(0, cursor_text_width)

@event.default('-text-input-line')
def on_click(widget, x, y, buttons, modifiers, click_count):
    x, y = widget.calculateRelativeCoords(x, y)
    if not buttons & mouse.LEFT:
        return event.EVENT_UNHANDLED
    if click_count == 1:
        new = widget.determineIndex(x)
        if modifiers & key.MOD_SHIFT:
            old = widget.cursor_index
            if old < new: widget.highlight = (old, new)
            else: widget.highlight = (new, old)
            widget.getGUI().setSelection(widget)
        else:
            widget.getGUI().clearSelection(widget)
            widget.highlight = None
            widget.cursor.enable()
            widget.setCursorPosition(new)
    elif click_count == 2:
        widget.cursor.disable()
        pos = widget.determineIndex(x)
        widget.selectWord(pos)
        widget.getGUI().setSelection(widget)
    elif click_count == 3:
        widget.cursor.disable()
        widget.selectAll()
        widget.getGUI().setSelection(widget)

    return event.EVENT_HANDLED

@event.default('-text-input-line')
def on_mouse_drag(widget, x, y, dx, dy, buttons, modifiers):
    if not buttons & mouse.LEFT: return event.EVENT_UNHANDLED
    x, y = widget.calculateRelativeCoords(x, y)
    if widget.highlight is None:
        start = widget.determineIndex(x)
        widget.highlight = (start, start)
        widget.getGUI().setSelection(widget)
        widget.cursor.disable()
    else:
        start, end = widget.highlight
        now = widget.determineIndex(x)
        if now <= start:
            widget.highlight = (now, end)
        else:
            widget.highlight = (start, now)
    return event.EVENT_HANDLED

@event.default('-text-input-line')
def on_gain_focus(widget):
    if widget.text:
        widget.selectAll()
    else:
        widget.cursor.enable()
        widget.setCursorPosition(0)
    return event.EVENT_HANDLED

@event.default('-text-input-line')
def on_lose_focus(widget):
    widget.cursor.disable()
    widget.highlight = None
    return event.EVENT_HANDLED

@event.default('-text-input-line')
def on_key_press(widget, symbol, modifiers):
    if sys.platform == 'darwin':
        active_mod = key.MOD_COMMAND
    else:
        active_mod = key.MOD_CTRL
    if modifiers & active_mod:
        if symbol == key.A:
            widget.selectAll()
            return event.EVENT_HANDLED
        elif symbol == key.X:
            # cut highlighted section
            if widget.highlight is None:
                return event.EVENT_UNHANDLED
            start, end = widget.highlight
            clipboard.put_text(widget.text[start:end])
            widget.editText('')
            return event.EVENT_HANDLED
        elif symbol == key.C:
            # copy highlighted section
            if widget.highlight is None:
                return event.EVENT_UNHANDLED
            start, end = widget.highlight
            clipboard.put_text(widget.text[start:end])
            return event.EVENT_HANDLED
        elif symbol == key.V:
            widget.editText(clipboard.get_text())
            return event.EVENT_HANDLED
    return event.EVENT_UNHANDLED

@event.default('-text-input-line')
def on_text(widget, text):
    # special-case newlines - we don't want them
    if text == '\r': return event.EVENT_UNHANDLED
    widget.editText(text, move=1)
    if widget.cursor.animation is not None:
        widget.cursor.animation.pause()
    return event.EVENT_HANDLED

@event.default('-text-input-line')
def on_text_motion(widget, motion):
    # hide mouse highlight, show caret
    widget.highlight = None
    widget.cursor.enable()
    widget.cursor.animation.pause()

    pos = widget.cursor_index
    if motion == key.MOTION_LEFT:
        if pos != 0: widget.setCursorPosition(pos-1)
    elif motion == key.MOTION_RIGHT:
        if pos != len(widget.text): widget.setCursorPosition(pos+1)
    elif motion in (key.MOTION_UP, key.MOTION_BEGINNING_OF_LINE,
            key.MOTION_BEGINNING_OF_FILE):
        widget.setCursorPosition(0)
    elif motion in (key.MOTION_DOWN, key.MOTION_END_OF_LINE,
            key.MOTION_END_OF_FILE):
        widget.setCursorPosition(len(widget.text))
    elif motion == key.MOTION_BACKSPACE:
        text = widget.text
        if widget.highlight is not None:
            start, end = widget.highlight
            text = text[:start] + text[end:]
            widget.highlight = None
            widget.cursor_index = start
        if pos != 0:
            n = pos
            widget.cursor_index -= 1
            text = text[0:n-1] + text[n:]
        if text != widget.text:
            widget.setText(text)
            widget.getGUI().dispatch_event(widget.parent, 'on_change', text)
    elif motion == key.MOTION_DELETE:
        text = widget.text
        if widget.highlight is not None:
            start, end = widget.highlight
            text = text[:start] + text[end:]
            widget.highlight = None
            widget.cursor_index = start
        elif pos != len(text):
            n = pos
            text = text[0:n] + text[n+1:]
        if text != widget.text:
            widget.setText(text)
            widget.getGUI().dispatch_event(widget.parent, 'on_change', text)
    else:
        print 'Unhandled MOTION', key.motion_string(motion)

    return event.EVENT_HANDLED

@event.default('-text-input-line')
def on_text_motion_select(widget, motion):
    pos = widget.cursor_index
    if widget.highlight is None:
        start = end = pos
        widget.getGUI().setSelection(widget)
    else:
        start, end = widget.highlight

    # regular motion
    if motion == key.MOTION_LEFT:
        if pos != 0: widget.setCursorPosition(pos-1)
    elif motion == key.MOTION_RIGHT:
        if pos != len(widget.text): widget.setCursorPosition(pos+1)
    elif motion in (key.MOTION_UP, key.MOTION_BEGINNING_OF_LINE,
            key.MOTION_BEGINNING_OF_FILE):
        widget.setCursorPosition(0)
    elif motion in (key.MOTION_DOWN, key.MOTION_END_OF_LINE,
            key.MOTION_END_OF_FILE):
        widget.setCursorPosition(len(widget.text))
    else:
        print 'Unhandled MOTION SELECT', key.motion_string(motion)

    if widget.cursor_index < start:
        start = widget.cursor_index
    elif widget.cursor_index > end:
        end = widget.cursor_index
    if start < end: widget.highlight = (start, end)
    else: widget.highlight = (end, start)

    return event.EVENT_HANDLED


class TextInput(Frame):
    '''Cursor position indicates which indexed element the cursor is to the
    left of.

    Note the default padding of 2 (rather than 1) pixels to give some space
    from the border.
    '''
    name='textinput'
    def __init__(self, parent, text='', font_size=None, size=None,
            x=0, y=0, z=0, width=None, height=None, border='black',
            padding=2, bgcolor='white', color='black', classes=(), **kw):
        style = parent.getStyle()
        if font_size is None:
            font_size = style.font_size
        else:
            font_size = util.parse_value(font_size, None)
        self.font_size = font_size
        if size is not None:
            size = util.parse_value(size, None)
            width = size * style.getGlyphString('M', size=font_size).width
            width += padding*2
        super(TextInput, self).__init__(parent, x, y, z, width, height,
            padding=padding, border=border, classes=classes, bgcolor=bgcolor,
            **kw)

        self.ti = TextInputLine(self, text, font_size=font_size,
            bgcolor=bgcolor, color=color)

        if width is None:
            self.width = self.ti.width + self.padding * 2
        if height is None:
            self.height = self.ti.height + self.padding * 2

    def get_text(self):
        return self.ti.text
    def set_text(self, text):
        self.ti.setText(text)
    text = property(get_text, set_text)
    value = property(get_text, set_text)

    def get_cursor_postion(self):
        return self.ti.cursor_index
    def set_cursor_postion(self, pos):
        self.ti.setCursorPosition(pos)
    cursor_postion = property(get_cursor_postion, set_cursor_postion)

    def get_width(self): return self._width
    def set_width(self, value):
        super(TextInput, self).set_width(value)
        # set up clipping
        ir = self.inner_rect
        self.setViewClip((0, 0, ir.width, ir.height))
    width = property(get_width, set_width)

    def get_height(self): return self._height
    def set_height(self, value):
        super(TextInput, self).set_height(value)
        # set up clipping
        ir = self.inner_rect
        self.setViewClip((0, 0, ir.width, ir.height))
    height = property(get_height, set_height)
 
class PasswordInput(TextInput):
    name='password'
    def __init__(self, *args, **kw):
        super(PasswordInput, self).__init__(*args, **kw)
        self.ti.is_password = True
        self.ti.setText(self.ti.text)

@event.default('textinput, password')
def on_element_enter(widget, x, y):
    w = widget.getGUI().window
    cursor = w.get_system_mouse_cursor(w.CURSOR_TEXT)
    w.set_mouse_cursor(cursor)
    return event.EVENT_HANDLED

@event.default('textinput, password')
def on_element_leave(widget, x, y):
    w = widget.getGUI().window
    cursor = w.get_system_mouse_cursor(w.CURSOR_DEFAULT)
    w.set_mouse_cursor(cursor)
    return event.EVENT_HANDLED

