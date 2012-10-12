#Copyright (C) 2010 Software for Education, Entertainment and Training
#Activities
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

from gi.repository import Gdk

from sugar3.graphics.window import Window

_journal_window = None


class JournalWindow(Window):

    def __init__(self):

        global _journal_window
        Window.__init__(self)
        _journal_window = self


def get_journal_window():
    return _journal_window


def set_widgets_active_state(active_state):
    from jarabe.journal.journalactivity import get_journal
    journal = get_journal()

    journal.get_toolbar_box().set_sensitive(active_state)
    journal.get_list_view().set_sensitive(active_state)
    journal.get_volumes_toolbar().set_sensitive(active_state)


def show_waiting_cursor():
    # Only show waiting-cursor, if this is the batch-mode.

    from jarabe.journal.journalactivity import get_journal
    if not get_journal().is_editing_mode_present():
        return

    _journal_window.get_root_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))


def freeze_ui():
    # Only freeze, if this is the batch-mode.

    from jarabe.journal.journalactivity import get_journal
    if not get_journal().is_editing_mode_present():
        return

    show_waiting_cursor()

    set_widgets_active_state(False)


def show_normal_cursor():
    _journal_window.get_root_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR))


def unfreeze_ui():
    # Unfreeze, irrespective of whether this is the batch mode.

    set_widgets_active_state(True)

    show_normal_cursor()
