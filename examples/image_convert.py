#!/usr/bin/env python

'''Convert an image to another file format supported by pyglet.

Usage::
    python image_convert.py <src-file> <dest-file>

'''

__docformat__ = 'restructuredtext'
__version__ = '$Id: $'

import sys

from pyglet.window import *
from pyglet.image import *

window = None
def convert(src, dest):
    if '.dds' in src.lower() or '.dds' in dest.lower():
        global window
        # A window is necessary to create a GL context so we can do
        # compressed texture conversions.
        window = window or Window(visible=False)
        texture = Texture.load(src)
        texture.save(dest)
    else:
        # Can do straight conversion without a window or context.
        image = load_image(src)
        image.save(dest)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print __doc__
        sys.exit(1)

    src = sys.argv[1]
    dest = sys.argv[2]
    convert(src, dest)
