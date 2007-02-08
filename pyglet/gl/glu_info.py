#!/usr/bin/env python

'''Information about version and extensions of current GLU implementation.

Usage::

    from pyglet.gl.glu_info import glu_info

    if glu_info.have_extension('GLU_EXT_nurbs_tessellator'):
        # ...

If multiple contexts are in use you can use a separate GLUInfo object for each
context.  Call `set_active_context` after switching to the desired context for
each GLUInfo::

    from pyglet.gl.glu_info import GLUInfo

    info = GLUInfo()
    info.set_active_context()
    if info.have_version(1, 3):
        # ...

Note that GLUInfo only returns meaningful information if a context has been
created.
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

__all__ = ['GLUInfo', 'glu_info']

from ctypes import *
import warnings

from pyglet.gl.glu import *

class GLUInfo(object):
    have_context = False
    version = '0.0.0'
    extensions = []

    def set_active_context(self):
        self.have_context = True
        self.extensions = \
            cast(gluGetString(GLU_EXTENSIONS), c_char_p).value.split()
        self.version = cast(gluGetString(GLU_VERSION), c_char_p).value

    def have_version(self, major, minor=0, release=0):
        if not self.have_context:
            warnings.warn('No GL context created yet.')
        ver = '%s.0.0' % self.version.split(' ', 1)[0]
        imajor, iminor, irelease = [int(v) for v in ver.split('.', 3)[:3]]
        return imajor > major or \
           (imajor == major and iminor > minor) or \
           (imajor == major and iminor == minor and irelease >= release)

    def get_version(self):
        if not self.have_context:
            warnings.warn('No GL context created yet.')
        return self.version

    def have_extension(self, extension):
        if not self.have_context:
            warnings.warn('No GL context created yet.')
        return extension in self.extensions

    def get_extensions(self):
        if not self.have_context:
            warnings.warn('No GL context created yet.')
        return self.extensions

# Single instance useful for apps with only a single context (or all contexts
# have same GLU driver, common case). 
glu_info = GLUInfo()
