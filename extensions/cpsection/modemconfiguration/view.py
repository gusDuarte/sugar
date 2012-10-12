# Copyright (C) 2009 Paraguay Educa, Martin Abente
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  US

from gettext import gettext as _
import logging

from gi.repository import Gtk
from gi.repository import GObject

from sugar3.graphics import style

from jarabe.controlpanel.sectionview import SectionView

from cpsection.modemconfiguration.config import GSM_COUNTRY_PATH, \
                                                GSM_PROVIDERS_PATH, \
                                                GSM_PLAN_PATH


APPLY_TIMEOUT = 1000


class EntryWithLabel(Gtk.HBox):
    __gtype_name__ = 'SugarEntryWithLabel'

    def __init__(self, label_text):
        Gtk.HBox.__init__(self, spacing=style.DEFAULT_SPACING)

        self.label = Gtk.Label(label=label_text)
        self.label.modify_fg(Gtk.StateType.NORMAL,
                        style.COLOR_SELECTION_GREY.get_gdk_color())
        self.label.set_alignment(1, 0.5)
        self.pack_start(self.label, False, True, 0)
        self.label.show()

        self._entry = Gtk.Entry()
        self._entry.set_max_length(25)
        self._entry.set_width_chars(25)
        self.pack_start(self._entry, False, True, 0)
        self._entry.show()

    def get_entry(self):
        return self._entry

    entry = GObject.property(type=object, getter=get_entry)


class ModemConfiguration(SectionView):
    def __init__(self, model, alerts=None):
        SectionView.__init__(self)

        self._model = model
        self.restart_alerts = alerts
        self._timeout_sid = 0

        self.set_border_width(style.DEFAULT_SPACING)
        self.set_spacing(style.DEFAULT_SPACING)
        self._group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        self._combo_group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        scrolled_win = Gtk.ScrolledWindow()
        scrolled_win.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_win.show()
        self.add(scrolled_win)

        main_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)
        main_box.set_border_width(style.DEFAULT_SPACING)
        main_box.show()
        scrolled_win.add_with_viewport(main_box)

        explanation = _('You will need to provide the following information'
                        ' to set up a mobile broadband connection to a'
                        ' cellular (3G) network.')
        self._text = Gtk.Label(label=explanation)
        self._text.set_line_wrap(True)
        self._text.set_alignment(0, 0)
        main_box.pack_start(self._text, False, False, 0)
        self._text.show()

        if model.has_providers_db():
            self._upper_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)
            self._upper_box.set_border_width(style.DEFAULT_SPACING)
            main_box.pack_start(self._upper_box, True, True, 0)
            self._upper_box.show()

            # Do not attach any 'change'-handlers for now.
            # They will be attached (once per combobox), once the
            # individual combobox is processed at startup.
            self._country_store = model.CountryListStore()
            self._country_combo = Gtk.ComboBox(model=self._country_store)
            self._attach_combobox_widget(_('Country:'),
                                         self._country_combo)

            self._providers_combo = Gtk.ComboBox()
            self._attach_combobox_widget(_('Provider:'),
                                         self._providers_combo)

            self._plan_combo = Gtk.ComboBox()
            self._attach_combobox_widget(_('Plan:'),
                                         self._plan_combo)

            separator = Gtk.HSeparator()
            main_box.pack_start(separator, True, True, 0)
            separator.show()

        self._lower_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)
        self._lower_box.set_border_width(style.DEFAULT_SPACING)
        main_box.pack_start(self._lower_box, True, True, 0)
        self._lower_box.show()

        self._username_entry = EntryWithLabel(_('Username:'))
        self._attach_entry_widget(self._username_entry)

        self._password_entry = EntryWithLabel(_('Password:'))
        self._attach_entry_widget(self._password_entry)

        self._number_entry = EntryWithLabel(_('Number:'))
        self._attach_entry_widget(self._number_entry)

        self._apn_entry = EntryWithLabel(_('Access Point Name (APN):'))
        self._attach_entry_widget(self._apn_entry)

        self._pin_entry = EntryWithLabel(_('Personal Identity Number (PIN):'))
        self._attach_entry_widget(self._pin_entry)

        self.setup()

    def _attach_combobox_widget(self, label_text, combobox_obj):
        box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        label = Gtk.Label(label_text)
        self._group.add_widget(label)
        label.set_alignment(1, 0.5)
        box.pack_start(label, False, False, 0)
        label.show()

        self._combo_group.add_widget(combobox_obj)
        cell = Gtk.CellRendererText()
        cell.props.xalign = 0.5

        cell.set_property('width-chars', 30)

        combobox_obj.pack_start(cell, True)
        combobox_obj.add_attribute(cell, 'text', 0)

        box.pack_start(combobox_obj, False, False, 0)
        combobox_obj.show()
        self._upper_box.pack_start(box, False, False, 0)
        box.show()

    def _attach_entry_widget(self, entry_with_label_obj):
        entry_with_label_obj.entry.connect('changed', self.__entry_changed_cb)
        self._group.add_widget(entry_with_label_obj.label)
        self._lower_box.pack_start(entry_with_label_obj, True, True, 0)
        entry_with_label_obj.show()

    def undo(self):
        self._model.undo()

    def _populate_entry(self, entrywithlabel, text):
        """Populate an entry with text, without triggering its 'changed'
        handler."""
        entry = entrywithlabel.entry

        # Do not block/unblock the callback functions.
        #
        # Thus, the savings will be persisted to the NM settings,
        # whenever any setting on the UI changes (by user-intervention,
        # or otherwise).
        #entry.handler_block_by_func(self.__entry_changed_cb)
        entry.set_text(text)
        #entry.handler_unblock_by_func(self.__entry_changed_cb)

    def setup(self):
        if self._model.has_providers_db():
            persisted_country = self._model.get_gconf_setting_string(GSM_COUNTRY_PATH)
            if (self._model.has_providers_db()) and (persisted_country != ''):
                self._country_combo.set_active(self._country_store.search_index_by_code(persisted_country))
            else:
                self._country_combo.set_active(self._country_store.guess_country_row())

            # Call the selected callback anyway, so as to chain-set the
            # default values for providers and the plans.
            self.__country_selected_cb(self._country_combo, setup=True)

        self._model.get_modem_settings(self.populate_entries)

    def populate_entries(self, settings):
        self._populate_entry(self._username_entry,
            settings.get('username', ''))
        self._populate_entry(self._number_entry, settings.get('number', ''))
        self._populate_entry(self._apn_entry, settings.get('apn', ''))
        self._populate_entry(self._password_entry,
            settings.get('password', ''))
        self._populate_entry(self._pin_entry, settings.get('pin', ''))

    def __entry_changed_cb(self, widget, data=None):
        if self._timeout_sid:
            GObject.source_remove(self._timeout_sid)
        self._timeout_sid = GObject.timeout_add(APPLY_TIMEOUT,
                                                self.__timeout_cb)

    def _get_selected_text(self, combo):
        active_iter = combo.get_active_iter()
        return combo.get_model().get(active_iter, 0)[0]

    def __country_selected_cb(self, combo, setup=False):
        country = self._get_selected_text(combo)
        self._model.set_gconf_setting_string(GSM_COUNTRY_PATH, country)

        model = combo.get_model()
        providers = model.get_row_providers(combo.get_active())
        self._providers_liststore = self._model.ProviderListStore(providers)
        self._providers_combo.set_model(self._providers_liststore)

        # Set the default provider as well.
        if setup:
            persisted_provider = self._model.get_gconf_setting_string(GSM_PROVIDERS_PATH)
            if persisted_provider == '':
                self._providers_combo.set_active(self._providers_liststore.guess_providers_row())
            else:
                self._providers_combo.set_active(self._providers_liststore.search_index_by_code(persisted_provider))
        else:
            self._providers_combo.set_active(self._providers_liststore.guess_providers_row())

        # Country-combobox processed once at startip; now, attach the
        # change-handler.
        self._country_combo.connect('changed', self.__country_selected_cb, False)

        # Call the callback, so that default provider may be set.
        self.__provider_selected_cb(self._providers_combo, setup)

    def __provider_selected_cb(self, combo, setup=False):
        provider = self._get_selected_text(combo)
        self._model.set_gconf_setting_string(GSM_PROVIDERS_PATH,  provider)

        model = combo.get_model()
        plans = model.get_row_plans(combo.get_active())
        self._plan_liststore = self._model.PlanListStore(plans)
        self._plan_combo.set_model(self._plan_liststore)

        # Set the default plan as well.
        if setup:
            persisted_plan = self._model.get_gconf_setting_string(GSM_PLAN_PATH)
            if persisted_plan == '':
                self._plan_combo.set_active(self._plan_liststore.guess_plan_row())
            else:
                self._plan_combo.set_active(self._plan_liststore.search_index_by_code(persisted_plan))
        else:
            self._plan_combo.set_active(self._plan_liststore.guess_plan_row())

        # Providers-combobox processed once at startip; now, attach the
        # change-handler.
        self._providers_combo.connect('changed', self.__provider_selected_cb, False)

        # Call the callback, so that the default plan is set.
        self.__plan_selected_cb(self._plan_combo, setup)

    def __plan_selected_cb(self, combo, setup=False):
        plan = self._get_selected_text(combo)
        self._model.set_gconf_setting_string(GSM_PLAN_PATH, plan)

        # Plan-combobox processed once at startip; now, attach the
        # change-handler.
        self._plan_combo.connect('changed', self.__plan_selected_cb, False)

        model = combo.get_model()
        plan = model.get_row_plan(combo.get_active())

        self._populate_entry(self._username_entry, plan['username'])
        self._populate_entry(self._password_entry, plan['password'])
        self._populate_entry(self._apn_entry, plan['apn'])
        self._populate_entry(self._number_entry, plan['number'])

    def __timeout_cb(self):
        self._timeout_sid = 0
        settings = {}
        settings['username'] = self._username_entry.entry.get_text()
        settings['password'] = self._password_entry.entry.get_text()
        settings['number'] = self._number_entry.entry.get_text()
        settings['apn'] = self._apn_entry.entry.get_text()
        settings['pin'] = self._pin_entry.entry.get_text()
        self._model.set_modem_settings(settings)
