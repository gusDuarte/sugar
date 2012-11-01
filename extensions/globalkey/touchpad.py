# Copyright (C) 2010, Martin Abente
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging

BOUND_KEYS = ['<alt>m']
touchpad = None

def handle_key_press(key):
    global touchpad
    if touchpad is None:
        try:
            touchpad = __import__('deviceicon.touchpad', globals(),
                                   locals(), ['touchpad'])
        except Exception:
            logging.error('Could not import touchpad module.')
            return

    if touchpad._view is not None:
        touchpad._view._palette.toggle_mode()
