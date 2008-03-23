#!/usr/bin/env python

'''Load and display a GIF animation.

Usage::

    animation.py [<filename>]

If the filename is omitted, a sample animation is loaded
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

# The dinosaur.gif file packaged alongside this script is in the public
# domain, it was obtained from http://www.gifanimations.com/.

import sys

import pyglet

if len(sys.argv) > 1:
    # Load the animation from file path.
    animation = pyglet.image.load_animation(sys.argv[1])
    bin = pyglet.image.atlas.TextureBin()
    animation.add_to_texture_bin(bin)
else:
    # Load animation from resource (this script's directory).
    animation = pyglet.resource.animation('dinosaur.gif')
sprite = pyglet.sprite.Sprite(animation)

window = pyglet.window.Window(width=sprite.width, height=sprite.height)

# Set window background color to white.
pyglet.gl.glClearColor(1, 1, 1, 1)

@window.event
def on_draw():
    window.clear()
    sprite.draw()

pyglet.app.run()
