import operator

from wydget import util
from wydget.widgets.label import Label

TOP = 'top'
BOTTOM = 'bottom'
LEFT = 'left'
RIGHT = 'right'
CENTER = 'center'
FILL = 'fill'

class Layout(object):
    def __init__(self, parent):
        self.parent = parent

    def __repr__(self):
        return '<%s %dx%d>'%(self.__class__.__name__, self.width, self.height)

    def layout(self):
        # XXX use signal?
        self.parent.layoutDimensionsChanged(self)

    def add(self, child):
        '''Generally this is a NOOP for simple layouts.

        We generally only care about "child" when it's a child layout.

        See Grid for where this is actually used.
        '''
        pass

    def get_height(self):
        return max(c.y + c.height for c in self.parent.children)
    height = property(get_height)

    def get_width(self):
        return max(c.x + c.width for c in self.parent.children)
    width = property(get_width)

    @classmethod
    def fromXML(cls, element, parent):
        '''Create the a layout from the XML element and handle children.
        Don't add the layout to the parent element.
        '''
        kw = loadxml.parseAttributes(parent, element)
        parent.layout = layout = cls(parent, **kw)

        for child in element.getchildren():
            child = loadxml.getConstructor(child.tag)(child, layout.parent)
            layout.add(child)
        layout.layout()

        return layout


class Grid(Layout):
    name = 'grid'

    def __init__(self, parent):
        super(Grid, self).__init__(parent)
        self.rows = []

    def add(self, row):
        self.rows.append(row)
    
    def layout(self):
        # XXX allow varying heights
        ys = self.parent.height // len(self.rows)

        for j, row in enumerate(self.rows):
            # XXX allow varying widths
            # XXX allow column spanning
            # XXX allow row spanning
            xs = self.parent.width // len(row.cells)
            for i, cell in enumerate(row.cells):
                if cell.child is None: continue

                x = i * xs
                if cell.halign == CENTER:
                    x += xs // 2 - cell.child.width // 2
                elif cell.halign == RIGHT:
                    x += xs - cell.child.width

                y = j * ys
                if cell.valign == CENTER:
                    y += ys // 2 - cell.child.height // 2
                elif cell.valign == TOP:
                    y += ys - cell.child.height

                cell.child.x, cell.child.y, cell.child.z = x, y, 0

        super(Grid, self).layout()


class Row(Layout):
    name = 'row'
    def __init__(self, parent):
        super(Row, self).__init__(parent)
        self.cells = []

    def add(self, cell):
        self.cells.append(cell)

    def layout(self):
        pass

class Cell(object):
    name = 'cell'

    def __init__(self, parent, child=None, valign=CENTER, halign=CENTER):
        super(Cell, self).__init__(parent)
        self.child = child
        self.valign = valign
        self.halign = halign

    def layout(self):
        pass

    @classmethod
    def fromXML(cls, element, parent):
        kw = loadxml.parseAttributes(parent, element)
        layout = cls(parent, **kw)

        l = element.getchildren()
        if not l: return

        assert len(l) == 1, '<cell> may only have one (or no) child'

        layout.child = loadxml.getConstructor(l[0].tag)(l[0], parent)

        return layout


class Vertical(Layout):
    name = 'vertical'

    def __init__(self, parent, valign=CENTER, halign=None, padding=0):
        self.valign = valign
        self.halign = halign
        self.padding = util.parse_value(padding, parent.inner_rect.height)
        super(Vertical, self).__init__(parent)

    # XXX make these two properties static
    def get_height(self):
        h = reduce(operator.add, [c.height for c in self.parent.children])
        return h + self.padding * (len(self.parent.children)-1)
    height = property(get_height)

    def get_width(self):
        return max([c.width for c in self.parent.children])
    width = property(get_width)

    def layout(self):
        # give the parent a chance to resize before we layout
        self.parent.layoutDimensionsChanged(self)

        # now get the area available for our layout
        rect = self.parent.inner_rect

        h = self.height

        if self.valign == TOP:
            y = rect.height
        elif self.valign == CENTER:
            y = rect.height//2 + h//2
        elif self.valign == BOTTOM:
            y = h

        for c in self.parent.children:
            if self.halign == LEFT:
                c.x = 0
            elif self.halign == CENTER:
                c.x = rect.width//2 - c.width//2
            elif self.halign == RIGHT:
                c.x = rect.width - c.width
            y -= c.height
            c.y = y
            y -= self.padding

        super(Vertical, self).layout()

class Horizontal(Layout):
    name = 'horizontal'

    def __init__(self, parent, halign=CENTER, valign=None, padding=0):
        self.halign = halign
        self.valign = valign
        self.padding = util.parse_value(padding, parent.inner_rect.width)
        super(Horizontal, self).__init__(parent)

    # XXX make these two properties static
    def get_width(self):
        if self.halign == FILL:
            c = self.parent.children[-1]
            return c.x + c.width
        else:
            w = reduce(operator.add, [c.width for c in self.parent.children])
            return w + self.padding * (len(self.parent.children)-1)
    width = property(get_width)

    def get_height(self):
        return max([c.height for c in self.parent.children])
    height = property(get_height)

    def layout(self):
        # give the parent a chance to resize before we layout
        self.parent.layoutDimensionsChanged(self)

        # now get the area available for our layout
        rect = self.parent.inner_rect

        w = self.width

        if self.halign == RIGHT:
            x = rect.width - w
        elif self.halign == CENTER:
            x = rect.width//2 - w//2
        elif self.halign == LEFT:
            x = 0
        elif self.halign == FILL:
            x = 0
            sizes = {}
            w = reduce(operator.add, [c.width for c in self.parent.children])
            w += self.padding * (len(self.parent.children)-1)
            for child in self.parent.children:
                sizes[child.id] = float(child.width) / w

        for child in self.parent.children:
            if self.valign == BOTTOM:
                child.y = 0
            elif self.valign == CENTER:
                child.y = rect.height//2 - child.height//2
            elif self.valign == TOP:
                child.y = rect.height - child.height
            if self.halign == FILL:
                w = int(sizes[child.id] * self.parent.width)
                child.x = x
                x += w
            else:
                child.x = x
                x += child.width + self.padding

        super(Horizontal, self).layout()


class Form(Layout):
    name = 'form'

    def __init__(self, parent, valign=TOP, label_width=None, padding=4):
        self.valign = valign
        if label_width is None:
            label_width = parent.width * .25
        self.label_width = label_width
        self.padding = padding
        pw = parent.inner_rect.width
        self.element_width = pw - (self.label_width + self.padding)
        self.elements = []
        super(Form, self).__init__(parent)

    def get_width(self):
        return self.parent.width
    width = property(get_width)

    def get_height(self):
        h = reduce(operator.add, [c.height for c in self.elements])
        return h + self.padding * (len(self.elements)-1)
    height = property(get_height)

    def addElement(self, label, element, expand_element=True):
        self.elements.append(element)
        if expand_element:
            element.width = self.element_width
        # XXX alignment
        if label:
            element._label = Label(self.parent, label, width=self.label_width,
                halign='right')
        else:
            element._label = None

    def layout(self):
        # give the parent a chance to resize before we layout
        self.parent.layoutDimensionsChanged(self)

        # now get the area available for our layout
        rect = self.parent.inner_rect

        h = self.height

        if self.valign == TOP:
            y = rect.height
        elif self.valign == CENTER:
            y = rect.height//2 + h//2
        elif self.valign == BOTTOM:
            y = h

        for element in self.elements:
            element.x = self.label_width + self.padding
            y -= element.height
            element.y = y
            if element._label: element._label.y = y
            y -= self.padding

        super(Form, self).layout()


import loadxml
for klass in [Grid, Row, Cell, Vertical, Horizontal]:
    loadxml.xml_registry[klass.name] = klass

