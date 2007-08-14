#!/usr/bin/env python

# Copyright (c) 2006-2007 Alex Holkner
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright 
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

'''A sprite-based game loosely based on the classic "Asteroids".

Shoot the asteroids, get high score.

Left/right: Turn ship
Up: Thrusters
Ctrl: Shoot
'''

import math
import os
import random
import sys

from pyglet.gl import *
from pyglet import clock
from pyglet import font
from pyglet import image
from pyglet import media
from pyglet import window
from pyglet.window import key

PLAYER_SPIN_SPEED = 360.
PLAYER_ACCEL = 200.
PLAYER_FIRE_DELAY = 0.1

BULLET_SPEED = 1000.

MAX_ASTEROID_SPIN_SPEED = 180.
MAX_ASTEROID_SPEED = 100.

INITIAL_ASTEROIDS = [2, 3, 4, 5]
ASTEROID_DEBRIS_COUNT = 3
MAX_DIFFICULTY = len(INITIAL_ASTEROIDS) - 1

ARENA_WIDTH = 480
ARENA_HEIGHT = 480

KEY_FIRE = key.LCTRL
KEY_PAUSE = key.ESCAPE

COLLISION_RESOLUTION = 8

SMOKE_ANIMATION_PERIOD = 0.05
EXPLOSION_ANIMATION_PERIOD = 0.07
PLAYER_FLASH_PERIOD = 0.15

GET_READY_DELAY = 1.
BEGIN_PLAY_DELAY = 2.
LIFE_LOST_DELAY = 2.

INSTRUCTIONS = \
'''Your ship is lost in a peculiar unchartered area of space-time infested with asteroids!  You have no chance for survival except to rack up the highest score possible.

Left/Right: Turn ship
Up: Thrusters
Ctrl: Shoot

Be careful, there's not much friction in space.'''

class Animation(object):
    def __init__(self, x, y, dx, dy, images, period):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.images = images
        self.period = period
        self.time = 0
        self.frame = 0
        self.finished = False

    def update(self, dt):
        self.x += self.dx * dt
        self.y += self.dy * dt

        self.time += dt
        while self.time >= self.period:
            self.time -= self.period
            self.frame += 1
            if self.frame == len(self.images):
                self.frame = 0 
                self.finished = True

    def draw(self):
        img = self.images[self.frame]
        img.blit(self.x - img.width / 2, self.y - img.height / 2, 0)

# --------------------------------------------------------------------------
# Game objects
# --------------------------------------------------------------------------

def wrap(value, width):
    if value > width:
        value -= width
    if value < 0:
        value += width
    return value

def to_radians(degrees):
    return math.pi * degrees / 180.0

class WrappingObject(object):
    dx = 0
    dy = 0
    heading = 0
    heading_speed = 0

    def __init__(self, x, y, img):
        self.x = x
        self.y = y
        self.img = img
        self.collision_radius = self.img.width / COLLISION_RESOLUTION / 2 

    def update(self, dt):
        self.x += self.dx * dt
        self.y += self.dy * dt
        self.heading += self.heading_speed * dt
        
        self.x = wrap(self.x, ARENA_WIDTH)
        self.y = wrap(self.y, ARENA_HEIGHT)
        self.heading = wrap(self.heading, 360.)

    def collision_cells(self):
        '''Generate a sequence of (x, y) cells this object covers,
        approximately.''' 
        radius = self.collision_radius
        cellx = int(self.x / COLLISION_RESOLUTION)
        celly = int(self.y / COLLISION_RESOLUTION)
        for y in range(celly - radius, celly + radius + 1):
            for x in range(cellx - radius, cellx + radius + 1):
                yield x, y

    def draw_at(self, x, y):
        glLoadIdentity()
        glTranslatef(x, y, 0)
        glRotatef(self.heading, 0, 0, 1)
        self.img.blit(-self.img.width/2, -self.img.height/2, 0)

    def draw(self):
        x_positions = [self.x]
        y_positions = [self.y]

        if self.x < self.img.width:
            x_positions.append(self.x + ARENA_WIDTH)
        if self.x > ARENA_WIDTH - self.img.width:
            x_positions.append(self.x - ARENA_WIDTH)
        if self.y < self.img.height:
            y_positions.append(self.y + ARENA_HEIGHT)
        if self.y > ARENA_HEIGHT - self.img.height:
            y_positions.append(self.y - ARENA_HEIGHT)

        for x in x_positions:
            for y in y_positions:
                self.draw_at(x, y)

class AsteroidSize(object):
    def __init__(self, filename, points):
        self.img = image.load(res(filename))
        self.next_size = None
        self.points = points

class Asteroid(WrappingObject):
    def __init__(self, x, y, size):
        super(Asteroid, self).__init__(x, y, size.img)
        self.dx = (random.random() - 0.5) * MAX_ASTEROID_SPEED
        self.dy = (random.random() - 0.5) * MAX_ASTEROID_SPEED
        self.size = size
        self.heading = random.random() * 360.
        self.heading_speed = (random.random() - 0.5) * MAX_ASTEROID_SPIN_SPEED
        self.hit = False

    def destroy(self):
        global score
        score += self.size.points

        # Modifies the asteroids list.
        next_size = self.size.next_size
        if next_size:
            # Spawn debris
            for i in range(ASTEROID_DEBRIS_COUNT):
                asteroids.append(Asteroid(self.x, self.y, next_size))

        asteroids.remove(self)

class Player(WrappingObject, key.KeyStateHandler):
    def __init__(self, img):
        super(Player, self).__init__(ARENA_WIDTH / 2, ARENA_HEIGHT / 2, img)
        self.reset()

    def reset(self):
        self.x = ARENA_WIDTH / 2
        self.y = ARENA_HEIGHT / 2
        self.dx = 0
        self.dy = 0
        self.heading = 0
        self.fire_timeout = 0
        self.hit = False
        self.invincible = True
        self.visible = True

        self.flash_timeout = 0
        self.flash_visible = False

    def update(self, dt):
        # Update heading
        if self[key.LEFT]:
            self.heading += PLAYER_SPIN_SPEED * dt
        if self[key.RIGHT]:
            self.heading -= PLAYER_SPIN_SPEED * dt

        # Get x/y components of orientation
        heading_x = math.cos(to_radians(self.heading))
        heading_y = math.sin(to_radians(self.heading))

        # Update velocity
        if self[key.UP]:
            self.dx += PLAYER_ACCEL * heading_x * dt
            self.dy += PLAYER_ACCEL * heading_y * dt

        # Update position
        super(Player, self).update(dt)

        # Fire bullet?
        self.fire_timeout -= dt
        if self[KEY_FIRE] and self.fire_timeout <= 0 and not self.invincible:
            self.fire_timeout = PLAYER_FIRE_DELAY

            # For simplicity, start the bullet at the player position.  If the
            # ship were bigger, or if bullets moved slower we'd adjust this
            # based on the orientation of the ship.
            bullets.append(Bullet(self.x, self.y, 
                                  heading_x * BULLET_SPEED,
                                  heading_y * BULLET_SPEED))

            if enable_sound:
                bullet_sound.play()

        # Update flash (invincible) animation
        if self.invincible:
            self.flash_timeout -= dt
            if self.flash_timeout <= 0:
                self.flash_timeout = PLAYER_FLASH_PERIOD
                self.flash_visible = not self.flash_visible
        else:
            self.flash_visible = True

    def draw(self):
        if self.visible and self.flash_visible:
            super(Player, self).draw()

class Bullet(object):
    __slots__ = ['x', 'y', 'dx', 'dy', 'hit']

    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy

    def update(self, dt):
        # Bullets have a much simpler update method than the other objects as
        # they are destroyed when the reach the edge of the arena rather than
        # wrapping.
        self.x += self.dx * dt
        self.y += self.dy * dt

    def in_bounds(self):
        return (self.x >= 0 and self.x < ARENA_WIDTH and
                self.y >= 0 and self.y < ARENA_HEIGHT)

    def draw(self):
        bullet_image.blit(self.x - bullet_image.width / 2, 
                          self.y - bullet_image.height / 2, 0)

class Starfield(object):
    def __init__(self, img):
        self.x = 0
        self.y = 0
        self.dx = 0.05
        self.dy = -0.06
        self.img = img

    def update(self, dt):
        self.x += self.dx * dt
        self.y += self.dy * dt

    def draw(self):
        # Fiddle with the texture matrix to make the starfield slide slowly
        # over the window.
        glMatrixMode(GL_TEXTURE)
        glPushMatrix()
        glTranslatef(self.x, self.y, 0)
        
        self.img.blit(0, 0, 0)
        
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

# --------------------------------------------------------------------------
# Overlays, such as menus and "Game Over" banners
# --------------------------------------------------------------------------

class Overlay(object):
    def update(self, dt):
        pass

    def draw(self):
        pass

class Banner(Overlay):
    def __init__(self, label, dismiss_func=None, timeout=None):
        self.text = font.Text(create_font(48),
                              label,
                              x = ARENA_WIDTH / 2, y = ARENA_HEIGHT / 2,
                              halign=font.Text.CENTER,
                              valign=font.Text.CENTER)

        self.dismiss_func = dismiss_func
        self.timeout = timeout
        if timeout and dismiss_func:
            clock.schedule_once(dismiss_func, timeout)

    def draw(self):
        self.text.draw()

    def on_key_press(self, symbol, modifiers):
        if self.dismiss_func and not self.timeout:
            self.dismiss_func()
        return True

class Menu(Overlay):
    def __init__(self, title):
        self.items = []
        self.title_text = font.Text(create_font(48),
                                    title, 
                                    x=ARENA_WIDTH / 2, y=350,
                                    halign=font.Text.CENTER,
                                    valign=font.Text.CENTER)

    def reset(self):
        self.selected_index = 0
        self.items[self.selected_index].selected = True

    def on_key_press(self, symbol, modifiers):
        if symbol == key.DOWN:
            self.selected_index += 1
        elif symbol == key.UP:
            self.selected_index -= 1
        else:
            self.items[self.selected_index].on_key_press(symbol, modifiers)
        self.selected_index = min(max(self.selected_index, 0), 
                                  len(self.items) - 1)

        if symbol in (key.DOWN, key.UP) and enable_sound:
            bullet_sound.play()

    def draw(self):
        self.title_text.draw()
        for i, item in enumerate(self.items):
            item.draw(i == self.selected_index)

class MenuItem(object):
    pointer_color = (.46, 0, 1.)
    inverted_pointers = False

    def __init__(self, label, y, activate_func):
        self.y = y
        self.text = font.Text(create_font(18),
                              label,
                              x=ARENA_WIDTH / 2, y=y,
                              halign=font.Text.CENTER,
                              valign=font.Text.CENTER)
        self.activate_func = activate_func

    def draw_pointer(self, x, y, color, flip=False):
        if flip:
            # Use the texture matrix to flip the image horizontally
            glMatrixMode(GL_TEXTURE)
            glPushMatrix()
            glScalef(-1, 1, 1)

        # Tint the pointer image to a color
        glPushAttrib(GL_CURRENT_BIT)
        glColor3f(*color)
        pointer_image.blit(x, y)
        glPopAttrib()

        if flip:
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)

    def draw(self, selected):
        self.text.draw()

        if selected:
            self.draw_pointer(
                self.text.x - self.text.width / 2 - pointer_image.width,
                self.y - pointer_image.height / 2, 
                self.pointer_color,
                self.inverted_pointers)
            self.draw_pointer(
                self.text.x + self.text.width / 2,
                self.y - pointer_image.height / 2,
                self.pointer_color,
                not self.inverted_pointers)

    def on_key_press(self, symbol, modifiers):
        if symbol == key.ENTER and self.activate_func:
            self.activate_func()
            if enable_sound:
                bullet_sound.play()

class ToggleMenuItem(MenuItem):
    pointer_color = (.27, .82, .25)
    inverted_pointers = True

    def __init__(self, label, value, y, toggle_func):
        self.value = value
        self.label = label
        self.toggle_func = toggle_func
        super(ToggleMenuItem, self).__init__(self.get_label(), y, None)

    def get_label(self):
        return self.label + (self.value and ': ON' or ': OFF')

    def on_key_press(self, symbol, modifiers):
        if symbol == key.LEFT or symbol == key.RIGHT:
            self.value = not self.value
            self.text.text = self.get_label()
            self.toggle_func(self.value)
            if enable_sound:
                bullet_sound.play()

class DifficultyMenuItem(MenuItem):
    pointer_color = (.27, .82, .25)
    inverted_pointers = True

    def __init__(self, y):
        super(DifficultyMenuItem, self).__init__(self.get_label(), y, None)

    def get_label(self):
        if difficulty == 0:
            return 'DIFFICULTY: PEBBLES'
        elif difficulty == 1:
            return 'DIFFICULTY: STONES'
        elif difficulty == 2:
            return 'DIFFICULTY: ASTEROIDS'
        elif difficulty == 3:
            return 'DIFFICULTY: METEORS'
        else:
            return 'DIFFICULTY: %d' % difficulty

    def on_key_press(self, symbol, modifiers):
        global difficulty
        if symbol == key.LEFT:
            difficulty -= 1
        elif symbol == key.RIGHT:
            difficulty += 1
        difficulty = min(max(difficulty, 0), MAX_DIFFICULTY)
        self.text.text = self.get_label()

        if symbol in (key.LEFT, key.RIGHT) and enable_sound:
            bullet_sound.play()

class MainMenu(Menu):
    def __init__(self):
        super(MainMenu, self).__init__('Astraea')

        self.items.append(MenuItem('New Game', 240, begin_game))
        self.items.append(MenuItem('Instructions', 200, 
                                   begin_instructions_menu))
        self.items.append(MenuItem('Options', 160, begin_options_menu))
        self.items.append(MenuItem('Quit', 120, sys.exit))
        self.reset()

class OptionsMenu(Menu):
    def __init__(self):
        super(OptionsMenu, self).__init__('Options')

        self.items.append(DifficultyMenuItem(280))
        def set_enable_sound(value):
            global enable_sound
            enable_sound = value
        self.items.append(ToggleMenuItem('Sound', enable_sound, 240,
                                         set_enable_sound))
                                
        self.items.append(ToggleMenuItem('Vsync', win.vsync, 200, 
                                         win.set_vsync))

        def set_show_fps(value):
            global show_fps
            show_fps = value
        self.items.append(ToggleMenuItem('FPS', show_fps, 160, set_show_fps))
        self.items.append(MenuItem('Ok', 100, begin_main_menu))
        self.reset()

class InstructionsMenu(Menu):
    def __init__(self):
        super(InstructionsMenu, self).__init__('Instructions')

        self.items.append(MenuItem('Ok', 50, begin_main_menu))
        self.reset()

        self.instruction_text = font.Text(create_font(18),
                                          INSTRUCTIONS,
                                          x=20, y=300,
                                          width=ARENA_WIDTH - 40,
                                          valign=font.Text.TOP)

    def draw(self):
        super(InstructionsMenu, self).draw()
        self.instruction_text.draw()

class PauseMenu(Menu):
    def __init__(self):
        super(PauseMenu, self).__init__('Paused')

        self.items.append(MenuItem('Continue Game', 240, resume_game))
        self.items.append(MenuItem('Main Menu', 200, end_game))
        self.reset()

# --------------------------------------------------------------------------
# Game state functions
# --------------------------------------------------------------------------

def check_collisions():
    # Check for collisions using an approximate uniform grid.
    #
    #   1. Mark all grid cells that the bullets are in
    #   2. Mark all grid cells that the player is in
    #   3. For each asteroid, check grid cells that are covered for
    #      a collision.
    #
    # This is by no means perfect collision detection (in particular,
    # there are rounding errors, and it doesn't take into account the
    # arena wrapping).  Improving it is left as an exercise for the
    # reader.

    # The collision grid.  It is recreated each iteration, as bullets move
    # quickly.
    hit_squares = {}

    # 1. Mark all grid cells that the bullets are in.  Assume bullets
    #    occupy a single cell.
    for bullet in bullets:
        hit_squares[int(bullet.x / COLLISION_RESOLUTION), 
                    int(bullet.y / COLLISION_RESOLUTION)] = bullet

    # 2. Mark all grid cells that the player is in.
    for x, y in player.collision_cells():
        hit_squares[x, y] = player

    # 3. Check grid cells of each asteroid for a collision.
    for asteroid in asteroids:
        for x, y in asteroid.collision_cells():
           if (x, y) in hit_squares:
                asteroid.hit = True
                hit_squares[x, y].hit = True
                del hit_squares[x, y]

def begin_main_menu():
    set_overlay(MainMenu())
    
def begin_options_menu():
    set_overlay(OptionsMenu())

def begin_instructions_menu():
    set_overlay(InstructionsMenu())

def begin_game():
    global player_lives
    global score
    player_lives = 3
    score = 0

    begin_clear_background()
    set_overlay(Banner('Get Ready', begin_first_round, GET_READY_DELAY))

def begin_first_round(*args):
    player.reset()
    player.visible = True
    begin_round()

def next_round(*args):
    global in_game
    player.invincible = True
    in_game = False
    set_overlay(Banner('Get Ready', begin_round, GET_READY_DELAY))

def begin_round(*args):
    global asteroids
    global bullets
    global animations
    global in_game
    asteroids = []
    for i in range(INITIAL_ASTEROIDS[difficulty]):
        x = random.random() * ARENA_WIDTH
        y = random.random() * ARENA_HEIGHT
        asteroids.append(Asteroid(x, y, asteroid_sizes[-1]))

    bullets = []
    animations = []
    in_game = True
    set_overlay(None)
    clock.schedule_once(begin_play, BEGIN_PLAY_DELAY)

def begin_play(*args):
    player.invincible = False

def begin_life(*args):
    player.reset()
    clock.schedule_once(begin_play, BEGIN_PLAY_DELAY)
    
def life_lost(*args):
    global player_lives
    player_lives -= 1

    if player_lives > 0:
        begin_life()
    else:
        game_over()

def game_over():
    set_overlay(Banner('Game Over', end_game))

def pause_game():
    global paused
    paused = True
    set_overlay(PauseMenu())

def resume_game():
    global paused
    paused = False
    set_overlay(None)

def end_game():
    global in_game
    global paused
    paused = False
    in_game = False
    player.invincible = True
    clock.unschedule(life_lost)
    clock.unschedule(begin_play)
    begin_menu_background()
    set_overlay(MainMenu())

def set_overlay(new_overlay):
    global overlay
    if overlay:
        win.pop_handlers()
    overlay = new_overlay
    if overlay:
        win.push_handlers(overlay)

def begin_menu_background():
    global asteroids
    global bullets
    global animations
    global in_game
    global player_lives

    asteroids = []
    for i in range(11):
        x = random.random() * ARENA_WIDTH
        y = random.random() * ARENA_HEIGHT
        asteroids.append(Asteroid(x, y, asteroid_sizes[i // 4]))

    bullets = []
    animations = []
    in_game = False
    player_lives = 0
    player.visible = False

def begin_clear_background():
    global asteroids
    global bullets
    global animations

    asteroids = []
    bullets = []
    animations = []
    player.visible = False

# --------------------------------------------------------------------------
# Load resources
# --------------------------------------------------------------------------

def res(filename):
    frozen = getattr(sys, 'frozen', None)
    if frozen in ('windows_exe', 'console_exe'):
        res_dir = os.path.join(os.path.dirname(sys.executable), 'res')
    elif frozen == 'macosx_app':
        res_dir = os.path.join(os.environ['RESOURCEPATH'], 'res')
    else:
        res_dir = os.path.join(os.path.dirname(__file__), 'res')
    return os.path.join(res_dir, filename)

def create_font(size):
    return font.load('Saved By Zero', size, dpi=72)

asteroid_sizes = [AsteroidSize('asteroid1.png', 100),
                  AsteroidSize('asteroid2.png', 50),
                  AsteroidSize('asteroid3.png', 10)]
for small, big in map(None, asteroid_sizes[:-1], asteroid_sizes[1:]):
    big.next_size = small

bullet_image = image.load(res('bullet.png'))

smoke_images_image = image.load(res('smoke.png'))
smoke_images = image.ImageGrid(smoke_images_image, 1, 8)

explosion_images_image = image.load(res('explosion.png'))
explosion_images = image.ImageGrid(explosion_images_image, 2, 8)

pointer_image = image.load(res('pointer.png'))

crunch_sound = media.load(res('27504.wav'), streaming=False)
bullet_sound = media.load(res('2096.wav'), streaming=False)

# --------------------------------------------------------------------------
# Global game state vars
# --------------------------------------------------------------------------

starfield = Starfield(image.load(res('starfield.jpg')))
player = Player(image.load(res('ship.png')))

overlay = None
in_game = False
paused = False
score = 0

difficulty = 2
show_fps = False
enable_sound = True

if __name__ == '__main__':
    win = window.Window(ARENA_WIDTH, ARENA_HEIGHT, caption='Astraea')

    # Override default Escape key behaviour
    def on_key_press(symbol, modifiers):
        if symbol == KEY_PAUSE and in_game:
            if not paused:
                pause_game()
            else:
                resume_game()
            return True
        elif symbol == key.ESCAPE:
            sys.exit()
    win.on_key_press = on_key_press

    win.push_handlers(player)

    # Now that we have a GL context, construct textures.
    smoke_images = smoke_images.texture_sequence
    explosion_images = explosion_images.texture_sequence

    font.add_file(res('saved_by_zero.ttf'))

    score_text = font.Text(create_font(24),
                           '',
                           x = ARENA_WIDTH - 10, y = ARENA_HEIGHT - 10,
                           halign=font.Text.RIGHT, valign=font.Text.TOP)

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    begin_menu_background()
    begin_main_menu()

    fps_display = clock.ClockDisplay(font=create_font(36))

    while not win.has_exit:
        win.dispatch_events()
        media.dispatch_events()

        # Update
        dt = clock.tick()
        if overlay:
            overlay.update(dt)

        if not paused:
            starfield.update(dt)
            player.update(dt)
            for asteroid in asteroids:
                asteroid.update(dt)
            for bullet in bullets:
                bullet.update(dt)
            for animation in animations:
                animation.update(dt)

        # Destroy bullets that have left the arena
        bullets = [bullet for bullet in bullets if bullet.in_bounds()]

        # Cancel animations that are finished
        animations = [ani for ani in animations if not ani.finished]

        if not player.invincible:
            # Collide bullets and player with asteroids
            check_collisions()

            # Destroy asteroids that were hit
            for asteroid in [a for a in asteroids if a.hit]:
                animations.append(Animation(asteroid.x, asteroid.y, 
                                            asteroid.dx, asteroid.dy,
                                            smoke_images, 
                                            SMOKE_ANIMATION_PERIOD))
                asteroid.destroy()
                if enable_sound:
                    crunch_sound.play()

            # Check if the player was hit 
            if player.hit:
                animations.append(Animation(player.x, player.y,
                                            player.dx, player.dy,
                                            explosion_images,
                                            EXPLOSION_ANIMATION_PERIOD))
                player.invincible = True
                player.visible = False
                clock.schedule_once(life_lost, LIFE_LOST_DELAY)

            # Check if the area is clear
            if not asteroids:
                next_round()

        # Render
        starfield.draw()

        for asteroid in asteroids:
            asteroid.draw()
        glLoadIdentity()
        for bullet in bullets:
            bullet.draw()
        player.draw()
        glLoadIdentity()
        for animation in animations:
            animation.draw()

        if in_game:
            # HUD ship lives
            x = 10
            for i in range(player_lives - 1):
                player.img.blit(x, win.height - player.img.height - 10, 0)
                x += player.img.width + 10
            
            # HUD score
            score_text.text = str(score)
            score_text.draw()

        if overlay:
            overlay.draw()

        if show_fps:
            fps_display.draw()

        win.flip()
