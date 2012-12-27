#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Virtualkeyboard
# Copyright (C) 2010 Plan Ceibal
#
# Author: Esteban Arias <earias@plan.ceibal.edu.uy>
# Contact information: comunidad@plan.ceibal.edu.uy
# Plan Ceibal http://www.ceibal.edu.uy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, os
import time

from gi.repository import GConf
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Pango

import logging
import threading

import jarabe.model.virtualkeyboard
from sugar3.graphics.icon import Icon, get_icon_file_name

GObject.threads_init()
Gdk.threads_init()

velocidades = {'lenta': 4500, 'media': 3000, 'rapida':1500}
hablar = {'lenta': "170", 'media': "180", 'rapida':"275"}

class Teclado:

    def __init__(self):
        self.BOTONESxBARRIDO = False;
        self.BOTONESxBARRIDOxFILA = False;
        self.MAYUSCULA = True;
        self.fila_1 = [];
        self.fila_2 = [];
        self.fila_3 = [];
        self.fila_4 = [];
        self.fila_5 = [];
        self.losBotones = [];
        self.fila_actual = None;
        self.btn_actual = None;
        self.fila_actual_nro = -1;

        self.seg = velocidades['media'];
        self.hablar_al = "NUNCA";
        self.size = "CHICO"
        self.teclado_tipo = "COMPLETO";
        self.inicilizar_config()

#        self.desplegar()
        if os.environ.has_key('virtualkeyboard'):
            self.visible = os.environ['virtualkeyboard']
            if self.visible == 'True':
                return
            else:
                if self.visible == 'False':
                    self.desplegar()
        else:
            self.desplegar()


    def delete_event(self, widget, event=None):
        self.close()

    def close(self):
        self.BOTONESxBARRIDOxFILA = False
        self.BOTONESxBARRIDO = False
        os.environ['virtualkeyboard'] = 'False'
        logging.debug('close virtual keyboard')
        self.dialog.destroy()
        try:
            self.hilo_bloquear._Thread__stop()
            self.hilo_hablar._Thread__stop()
        except:
            pass
        return False


    def desplegar(self):
        self._mTeclado=jarabe.model.virtualkeyboard.Teclado()

        self.dialog = Gtk.Dialog()
        self.dialog.set_title("TECLADO VIRTUAL")
        self.dialog.set_keep_above(True)
        self.dialog.grab_focus()
        try:
            self.dialog.set_icon_from_file(get_icon_file_name('virtualkeyboard'))
        except:
            logging.debug('dont show virtual keyboard icon')

        self.dialog.set_accept_focus(False)
        self.dialog.connect("delete_event", self.delete_event)

        #tipo de teclado:
        try:
            self.teclado_tipo = self.get_tipo_teclado()
        except:
            logging.error("init - error al leer teclado_tipo")
            self.teclado_tipo  = "COMPLETO"

        self.vbox_teclado = self.mostrar_teclado()

        #sizes:
        try:
            self.size = self.get_size_botones()
        except:
            logging.error("init - error al leer size_botones")
            self.size = "CHICO"

        x, y = self.get_size_dialog(self.size, self.teclado_tipo)
        font_desc = self.get_font_desc(self.size, self.teclado_tipo)
        self.dialog.set_size_request(x, y)
        self.sizeBotones(font_desc)

        self.event_box = Gtk.EventBox()
        self.event_box.add(self.vbox_teclado)
        self.event_box.set_events(Gdk.EventType.BUTTON_PRESS)
        self.event_box.show()
        self.ebc = self.event_box.connect("button_press_event", self.mouse_boton)
        self.dialog.vbox.pack_start(self.event_box, False, False, 5)

        self.vbox_teclado.show_all()

        self.posicionar_dialog(self.dialog)

        self.dialog.show()

        try:
            self.hablar_al = self.get_opciones_hablar()
        except:
            logging.debug('init - Error  al cargar opciones.')
            self.hablar_al = "NUNCA"

        barriendo=""
        try:
            barriendo = self.leer_barrido()
        except:
            logging.error("init - Error al leer barrido.")
            barriendo = "NO"

        if barriendo == "SI":
            try:
                seg =self.get_time_barrido_botones()
            except:
                logging.error("init - error al leer time_barrido_botones")
                seg = velocidades['media']

            self.seg = seg
            self.BOTONESxBARRIDOxFILA = True
            self.botonesXbarridoXfila()

        os.environ['virtualkeyboard'] = 'True'


    def mostrar_teclado(self):
        if (self.teclado_tipo == "COMPLETO"):
            return self.mostrar_teclado_completo()
        elif (self.teclado_tipo == "NUMERICO"):
            return self.mostrar_teclado_numerico()
        elif (self.teclado_tipo == "LETRAS"):
            return self.mostrar_teclado_letras()

    def mostrar_teclado_completo(self):
        child = Gtk.VBox(False, 2)

        # defino botones
        self.btn_BACK_SPACE = self.new_button_borrar()
        self.losBotones.append(self.btn_BACK_SPACE)

        self.btn_SPACE = self.new_button_espacio()
        self.losBotones.append(self.btn_SPACE)

        self.btn_CAPS_LOCK = self.new_button_mayuscula()
        self.fila_3.append(self.btn_CAPS_LOCK)
        self.losBotones.append(self.btn_CAPS_LOCK)

        self.btn_ENTER = self.new_button_enter()	
        self.losBotones.append(self.btn_ENTER)
        self.fila_2.append(self.btn_ENTER)

        self.btn_TAB = self.new_button_tab()
        self.losBotones.append(self.btn_TAB)
        self.fila_2.append(self.btn_TAB)

        self.btn_do = self.new_button_escribir("º")
        self.btn_do.set_text_desc("o superíndice")
        self.losBotones.append(self.btn_do)
        self.fila_1.append(self.btn_do)

        self.btn_1 = self.new_button_escribir("1")
        self.losBotones.append(self.btn_1)
        self.fila_1.append(self.btn_1)

        self.btn_2 = self.new_button_escribir("2")
        self.losBotones.append(self.btn_2)
        self.fila_1.append(self.btn_2)

        self.btn_3 = self.new_button_escribir("3")
        self.losBotones.append(self.btn_3)
        self.fila_1.append(self.btn_3)

        self.btn_4 = self.new_button_escribir("4")
        self.losBotones.append(self.btn_4)
        self.fila_1.append(self.btn_4)

        self.btn_5 = self.new_button_escribir("5")
        self.losBotones.append(self.btn_5)
        self.fila_1.append(self.btn_5)

        self.btn_6 = self.new_button_escribir("6")
        self.losBotones.append(self.btn_6)
        self.fila_1.append(self.btn_6)

        self.btn_7 = self.new_button_escribir("7")
        self.losBotones.append(self.btn_7)
        self.fila_1.append(self.btn_7)

        self.btn_8 = self.new_button_escribir("8")
        self.losBotones.append(self.btn_8)
        self.fila_1.append(self.btn_8)

        self.btn_9 = self.new_button_escribir("9")
        self.losBotones.append(self.btn_9)
        self.fila_1.append(self.btn_9)

        self.btn_0 = self.new_button_escribir("0")
        self.losBotones.append(self.btn_0)
        self.fila_1.append(self.btn_0)

        self.btn_finPreg = self.new_button_escribir("'")
        self.btn_finPreg.set_text_desc("comilla simple")
        self.losBotones.append(self.btn_finPreg)
        self.fila_1.append(self.btn_finPreg)

        self.btn_inicioPreg = self.new_button_escribir("¡")
        self.btn_inicioPreg.set_text_desc("abro exclamación")
        self.losBotones.append(self.btn_inicioPreg)
        self.fila_1.append(self.btn_inicioPreg)

        self.btn_Q = self.new_button_escribir("Q")
        self.losBotones.append(self.btn_Q)
        self.fila_2.append(self.btn_Q)

        self.btn_W = self.new_button_escribir("W")
        self.losBotones.append(self.btn_W)
        self.fila_2.append(self.btn_W)

        self.btn_E = self.new_button_escribir("E")
        self.losBotones.append(self.btn_E)
        self.fila_2.append(self.btn_E)

        self.btn_R = self.new_button_escribir("R")
        self.losBotones.append(self.btn_R)
        self.fila_2.append(self.btn_R)

        self.btn_T = self.new_button_escribir("T")
        self.losBotones.append(self.btn_T)
        self.fila_2.append(self.btn_T)

        self.btn_Y = self.new_button_escribir("Y")
        self.losBotones.append(self.btn_Y)
        self.fila_2.append(self.btn_Y)

        self.btn_U = self.new_button_escribir("U")
        self.losBotones.append(self.btn_U)
        self.fila_2.append(self.btn_U)

        self.btn_I = self.new_button_escribir("I")
        self.losBotones.append(self.btn_I)
        self.fila_2.append(self.btn_I)

        self.btn_O = self.new_button_escribir("O")
        self.losBotones.append(self.btn_O)
        self.fila_2.append(self.btn_O)

        self.btn_P = self.new_button_escribir("P")
        self.losBotones.append(self.btn_P)
        self.fila_2.append(self.btn_P)

        self.btn_asterisco = self.new_button_escribir("*")
        self.losBotones.append(self.btn_asterisco)
        self.fila_2.append(self.btn_asterisco)

        self.btn_cierra_llave = self.new_button_escribir("]")
        self.btn_cierra_llave.set_text_desc("cierro paréntesis recto")
        self.losBotones.append(self.btn_cierra_llave)

        self.btn_A = self.new_button_escribir("A")
        self.losBotones.append(self.btn_A)
        self.fila_3.append(self.btn_A)

        self.btn_S = self.new_button_escribir("S")
        self.losBotones.append(self.btn_S)
        self.fila_3.append(self.btn_S)

        self.btn_D = self.new_button_escribir("D")
        self.losBotones.append(self.btn_D)
        self.fila_3.append(self.btn_D)

        self.btn_F = self.new_button_escribir("F")
        self.losBotones.append(self.btn_F)
        self.fila_3.append(self.btn_F)

        self.btn_G = self.new_button_escribir("G")
        self.losBotones.append(self.btn_G)
        self.fila_3.append(self.btn_G)

        self.btn_H = self.new_button_escribir("H")
        self.losBotones.append(self.btn_H)
        self.fila_3.append(self.btn_H)

        self.btn_J = self.new_button_escribir("J")
        self.losBotones.append(self.btn_J)
        self.fila_3.append(self.btn_J)

        self.btn_K = self.new_button_escribir("K")
        self.losBotones.append(self.btn_K)
        self.fila_3.append(self.btn_K)

        self.btn_L = self.new_button_escribir("L")
        self.losBotones.append(self.btn_L)
        self.fila_3.append(self.btn_L)

        self.btn_enie = self.new_button_escribir("Ñ")
        self.losBotones.append(self.btn_enie)
        self.fila_3.append(self.btn_enie)

        self.btn_mas = self.new_button_escribir("+")
        self.btn_mas.set_text_desc("más")
        self.losBotones.append(self.btn_mas)
        self.fila_3.append(self.btn_mas)

        self.fila_3.append(self.btn_cierra_llave)

        self.btn_abre_llave = self.new_button_escribir("[")
        self.btn_abre_llave.set_text_desc("abro paréntesis recto")
        self.losBotones.append(self.btn_abre_llave)
        self.fila_2.append(self.btn_abre_llave)

        self.btn_Z = self.new_button_escribir("Z")
        self.losBotones.append(self.btn_Z)
        self.fila_4.append(self.btn_Z)

        self.btn_X = self.new_button_escribir("X")
        self.losBotones.append(self.btn_X)
        self.fila_4.append(self.btn_X)

        self.btn_C = self.new_button_escribir("C")
        self.losBotones.append(self.btn_C)
        self.fila_4.append(self.btn_C)

        self.btn_V = self.new_button_escribir("V")
        self.losBotones.append(self.btn_V)
        self.fila_4.append(self.btn_V)

        self.btn_B = self.new_button_escribir("B")
        self.losBotones.append(self.btn_B)
        self.fila_4.append(self.btn_B)

        self.btn_N = self.new_button_escribir("N")
        self.losBotones.append(self.btn_N)
        self.fila_4.append(self.btn_N)

        self.btn_M = self.new_button_escribir("M")
        self.losBotones.append(self.btn_M)
        self.fila_4.append(self.btn_M)

        self.btn_coma = self.new_button_escribir(",")
        self.btn_coma.set_text_desc("coma")
        self.losBotones.append(self.btn_coma)
        self.fila_4.append(self.btn_coma)

        self.btn_punto = self.new_button_escribir(".")
        self.btn_punto.set_text_desc("punto")
        self.losBotones.append(self.btn_punto)
        self.fila_4.append(self.btn_punto)

        self.btn_guion = self.new_button_escribir("-")
        self.btn_guion.set_text_desc("guión")
        self.losBotones.append(self.btn_guion)
        self.fila_4.append(self.btn_guion)

        self.btn_A_tilde = self.new_button_escribir("Á")
        self.btn_A_tilde.set_text_desc("Á tilde")
        self.losBotones.append(self.btn_A_tilde)
        self.fila_5.append(self.btn_A_tilde)

        self.btn_E_tilde = self.new_button_escribir("É")
        self.btn_E_tilde.set_text_desc("É tilde")
        self.losBotones.append(self.btn_E_tilde)
        self.fila_5.append(self.btn_E_tilde)

        self.btn_I_tilde = self.new_button_escribir("Í")
        self.btn_I_tilde.set_text_desc("Í tilde")
        self.losBotones.append(self.btn_I_tilde)
        self.fila_5.append(self.btn_I_tilde)

        self.btn_O_tilde = self.new_button_escribir("Ó")
        self.btn_O_tilde.set_text_desc("Ó tilde")
        self.losBotones.append(self.btn_O_tilde)
        self.fila_5.append(self.btn_O_tilde)

        self.btn_U_tilde = self.new_button_escribir("Ú")
        self.btn_U_tilde.set_text_desc("Ú tilde")
        self.losBotones.append(self.btn_U_tilde)
        self.fila_5.append(self.btn_U_tilde)

        self.btn_U_puntos = self.new_button_escribir("Ü")
        self.btn_U_puntos.set_text_desc("u diéresis")
        self.losBotones.append(self.btn_U_puntos)
        self.fila_5.append(self.btn_U_puntos)

        self.btn_pite = self.new_button_escribir("|")
        self.btn_pite.set_text_desc("pait")
        self.losBotones.append(self.btn_pite)
        self.fila_5.append(self.btn_pite)

        self.btn_arroba = self.new_button_escribir("@")
        self.losBotones.append(self.btn_arroba)
        self.fila_5.append(self.btn_arroba)

        self.btn_menor = self.new_button_escribir("<")
        self.btn_menor.set_text_desc("menor")
        self.losBotones.append(self.btn_menor)
        self.fila_5.append(self.btn_menor)

        self.btn_opciones = self.new_button(Gtk.STOCK_PREFERENCES, " ", self.desplegar_opciones)

        #dibujo tabla
        table = Gtk.Table(7, 19, True)

        table.set_row_spacing(0, 15)
        table.set_row_spacing(1, 3)
        table.set_row_spacing(2, 3)
        table.set_row_spacing(3, 15)
        table.set_row_spacing(4, 10)
        table.set_row_spacing(5, 3)
        table.set_row_spacing(6, 3)

        table.set_col_spacing(0, 3)
        table.set_col_spacing(1, 3)
        table.set_col_spacing(2, 3)
        table.set_col_spacing(3, 3)
        table.set_col_spacing(4, 3)
        table.set_col_spacing(5, 3)
        table.set_col_spacing(6, 3)
        table.set_col_spacing(7, 3)
        table.set_col_spacing(8, 3)
        table.set_col_spacing(9, 3)
        table.set_col_spacing(10, 3)
        table.set_col_spacing(11, 3)
        table.set_col_spacing(12, 3)
        table.set_col_spacing(13, 15)


        table.attach(self.btn_do, 1, 2, 0, 1)
        table.attach(self.btn_1, 2, 3, 0, 1)
        table.attach(self.btn_2, 3, 4, 0, 1)
        table.attach(self.btn_3, 4, 5, 0, 1)
        table.attach(self.btn_4, 5, 6, 0, 1)
        table.attach(self.btn_5, 6, 7, 0, 1)
        table.attach(self.btn_6, 7, 8, 0, 1)
        table.attach(self.btn_7, 8, 9, 0, 1)
        table.attach(self.btn_8, 9, 10, 0, 1)
        table.attach(self.btn_9, 10, 11, 0, 1)
        table.attach(self.btn_0, 11, 12, 0, 1)
        table.attach(self.btn_finPreg, 12 ,13, 0, 1)
        table.attach(self.btn_inicioPreg, 13, 14, 0, 1)
        table.attach(self.btn_TAB, 0, 2, 1, 2)
        table.attach(self.btn_Q, 2, 3, 1, 2)
        table.attach(self.btn_W, 3, 4, 1, 2)
        table.attach(self.btn_E, 4, 5, 1, 2)
        table.attach(self.btn_R, 5, 6, 1, 2)
        table.attach(self.btn_T, 6, 7, 1, 2)
        table.attach(self.btn_Y, 7, 8, 1, 2)
        table.attach(self.btn_U, 8, 9, 1, 2)
        table.attach(self.btn_I, 9, 10, 1, 2)
        table.attach(self.btn_O, 10, 11, 1, 2)
        table.attach(self.btn_P, 11, 12, 1, 2)
        table.attach(self.btn_asterisco, 12, 13, 1, 2)
        table.attach(self.btn_abre_llave, 13, 14, 1, 2)
        table.attach(self.btn_A, 2, 3, 2, 3)
        table.attach(self.btn_S, 3, 4, 2, 3)
        table.attach(self.btn_D, 4, 5, 2, 3)
        table.attach(self.btn_F, 5, 6, 2, 3)
        table.attach(self.btn_G, 6, 7, 2, 3)
        table.attach(self.btn_H, 7, 8, 2, 3)
        table.attach(self.btn_J, 8, 9, 2, 3)
        table.attach(self.btn_K, 9, 10, 2, 3)
        table.attach(self.btn_L, 10, 11, 2, 3)
        table.attach(self.btn_enie, 11, 12, 2, 3)
        table.attach(self.btn_mas, 12, 13, 2, 3)
        table.attach(self.btn_cierra_llave, 13, 14, 2, 3)
        table.attach(self.btn_Z, 2, 3, 3, 4)
        table.attach(self.btn_X, 3, 4, 3, 4)
        table.attach(self.btn_C, 4, 5, 3, 4)
        table.attach(self.btn_V, 5, 6, 3, 4)
        table.attach(self.btn_B, 6, 7, 3, 4)
        table.attach(self.btn_N, 7, 8, 3, 4)
        table.attach(self.btn_M, 8, 9, 3, 4)
        table.attach(self.btn_coma, 9, 10, 3, 4)
        table.attach(self.btn_punto, 10, 11, 3, 4)
        table.attach(self.btn_guion, 11, 12, 3, 4)

        table.attach(self.btn_BACK_SPACE, 14, 19, 0, 1)
        table.attach(self.btn_ENTER, 14, 19, 1, 2)
        table.attach(self.btn_CAPS_LOCK, 14, 19, 2, 3)
        table.attach(self.btn_SPACE, 2, 14, 5, 6)
        table.attach(self.btn_opciones, 18, 19, 5, 6)

        table.attach(self.btn_A_tilde, 2, 3, 4, 5)
        table.attach(self.btn_E_tilde, 3, 4, 4, 5)
        table.attach(self.btn_I_tilde, 4, 5, 4, 5)
        table.attach(self.btn_O_tilde, 5, 6, 4, 5)
        table.attach(self.btn_U_tilde, 6, 7, 4, 5)
        table.attach(self.btn_U_puntos, 9, 10, 4, 5)
        table.attach(self.btn_pite, 10, 11, 4, 5)
        table.attach(self.btn_arroba, 11, 12, 4, 5)
        table.attach(self.btn_menor, 12, 13, 4, 5)

        child.pack_end(table, True, True, 0)

        return child

####################################################################################
    def escribir(self, widget, *arg):
        txt = widget.get_text()

        self._mTeclado.escribir_txt(txt)
        if (self.hablar_al == "ESCRIBIR"):
            self.btn_actual=widget
            self.hablar()

    def espacio(self, *arg):
        self._mTeclado.escribir_txt(" ")
        if (self.hablar_al == "ESCRIBIR"):
            self.btn_actual = self.btn_SPACE
            self.hablar()

    def tab(self, *arg):
        self._mTeclado.escribir_txt("\t")
        if (self.hablar_al == "ESCRIBIR"):
            self.btn_actual = self.btn_TAB
            self.hablar()

    def enter(self, *arg):
        self._mTeclado.escribir_txt("\n")
        if (self.hablar_al == "ESCRIBIR"):
            self.btn_actual = self.btn_ENTER
            self.hablar()

    def borrar(self, *arg):
        self._mTeclado.escribir_txt("\r")
        if (self.hablar_al == "ESCRIBIR"):
            self.btn_actual = self.btn_BACK_SPACE
            self.hablar()

    def new_button_escribir(self, plabel):
        btn = Boton(plabel)
        btn.connect("pressed", self.escribir, plabel)
        btn.connect("activate", self.escribir, plabel)
        return btn


    def new_button_enter(self):
        btn = Boton("ENTER")
        btn.set_text_desc("énter")
        btn.set_font_desc("sans bold 11")
        btn.connect("pressed", self.enter)
        btn.connect("activate", self.enter)
        return btn

    def new_button_espacio(self):
        btn = Boton("ESPACIO")
        btn.set_font_desc("sans bold 11")
        btn.connect("pressed", self.espacio)
        btn.connect("activate", self.espacio)
        return btn

    def new_button_borrar(self):
        btn = Boton("BORRAR")
        btn.set_font_desc("sans bold 11")
        btn.connect("pressed", self.borrar)
        btn.connect("activate", self.borrar)
        return btn

    def new_button_tab(self):
        btn = Boton("TAB")
        btn.set_font_desc("sans bold 11")
        btn.connect("pressed", self.tab)
        btn.connect("activate", self.tab)
        return btn

    def new_button_mayuscula(self):
        btn = Boton("MINÚSCULA")
        btn.set_font_desc("sans bold 11")
        btn.connect("pressed", self.set_mayuscula)
        btn.connect("activate", self.set_mayuscula)
        return btn

    def new_button_cambiar_tipo(self, titulo):
        btn = Boton(titulo)
        btn.set_font_desc("sans 9")
        btn.connect("pressed", self.cambiar_tipo)
        btn.connect("activate", self.cambiar_tipo)
        return btn


    def set_mayuscula(self, *arg):
        if (self.MAYUSCULA):
            self.btn_do.set_text("ª")
            self.btn_do.set_text_desc("a superíndice")
            self.btn_1.set_text("!")
            self.btn_1.set_text_desc("cierro exclamación")
            self.btn_2.set_text("\"")
            self.btn_2.set_text_desc("comilla doble")
            self.btn_3.set_text("#")
            self.btn_3.set_text_desc("numeral")
            self.btn_4.set_text("$")
            self.btn_4.set_text_desc("peso")
            self.btn_5.set_text("%")
            self.btn_5.set_text_desc("porcentaje")
            self.btn_6.set_text("&")
            self.btn_6.set_text_desc("ámpersand")
            self.btn_7.set_text("/")
            self.btn_7.set_text_desc("barra")
            self.btn_8.set_text("(")
            self.btn_8.set_text_desc("abro paréntesis")
            self.btn_9.set_text(")")
            self.btn_9.set_text_desc("cierro paréntesis")
            self.btn_0.set_text("=")
            self.btn_0.set_text_desc("igual")
            self.btn_finPreg.set_text("?")
            self.btn_finPreg.set_text_desc("cierro pregunta")
            self.btn_inicioPreg.set_text("¿")
            self.btn_inicioPreg.set_text_desc("abro pregunta")
            self.btn_Q.set_text("q")
            self.btn_W.set_text("w")
            self.btn_E.set_text("e")
            self.btn_R.set_text("r")
            self.btn_T.set_text("t")
            self.btn_Y.set_text("y")
            self.btn_U.set_text("u")
            self.btn_I.set_text("i")
            self.btn_O.set_text("o")
            self.btn_P.set_text("p")
            self.btn_A.set_text("a")
            self.btn_S.set_text("s")
            self.btn_D.set_text("d")
            self.btn_F.set_text("f")
            self.btn_G.set_text("g")
            self.btn_H.set_text("h")
            self.btn_J.set_text("j")
            self.btn_K.set_text("k")
            self.btn_L.set_text("l")
            self.btn_enie.set_text("ñ")
            self.btn_menor.set_text(">")
            self.btn_menor.set_text_desc("mayor")
            self.btn_Z.set_text("z")
            self.btn_X.set_text("x")
            self.btn_C.set_text("c")
            self.btn_V.set_text("v")
            self.btn_B.set_text("b")
            self.btn_N.set_text("n")
            self.btn_M.set_text("m")
            self.btn_coma.set_text(";")
            self.btn_coma.set_text_desc("punto y coma")
            self.btn_punto.set_text(":")
            self.btn_punto.set_text_desc("dos puntos")
            self.btn_guion.set_text("_")
            self.btn_guion.set_text_desc("guión bajo")
            self.btn_A_tilde.set_text("á")
            self.btn_A_tilde.set_text_desc("á tilde")
            self.btn_E_tilde.set_text("é")
            self.btn_E_tilde.set_text_desc("é tilde")
            self.btn_I_tilde.set_text("í")
            self.btn_I_tilde.set_text_desc("í tilde")
            self.btn_O_tilde.set_text("ó")
            self.btn_O_tilde.set_text_desc("ó tilde")
            self.btn_U_tilde.set_text("ú")
            self.btn_U_tilde.set_text_desc("ú tilde")
            self.btn_U_puntos.set_text("ü")
            self.btn_U_puntos.set_text_desc("u diéresis")
            self.btn_abre_llave.set_text("{")
            self.btn_abre_llave.set_text_desc("abro llave")
            self.btn_cierra_llave.set_text("}")
            self.btn_cierra_llave.set_text_desc("cierro llave")

            self.MAYUSCULA = False
            self.btn_CAPS_LOCK.set_text("MAYÚSCULA")
            self.btn_CAPS_LOCK.set_text_desc("MAYÚSCULA")
        else:
            self.btn_do.set_text("º")
            self.btn_do.set_text_desc("o superíndice")
            self.btn_1.set_text("1")
            self.btn_1.set_text_desc("1")
            self.btn_2.set_text("2")
            self.btn_2.set_text_desc("2")
            self.btn_3.set_text("3")
            self.btn_3.set_text_desc("3")
            self.btn_4.set_text("4")
            self.btn_4.set_text_desc("4")
            self.btn_5.set_text("5")
            self.btn_5.set_text_desc("5")
            self.btn_6.set_text("6")
            self.btn_6.set_text_desc("6")
            self.btn_7.set_text("7")
            self.btn_7.set_text_desc("7")
            self.btn_8.set_text("8")
            self.btn_8.set_text_desc("8")
            self.btn_9.set_text("9")
            self.btn_9.set_text_desc("9")
            self.btn_0.set_text("0")
            self.btn_0.set_text_desc("0")
            self.btn_finPreg.set_text("'")
            self.btn_finPreg.set_text_desc("comilla simple")
            self.btn_inicioPreg.set_text("¡")
            self.btn_inicioPreg.set_text_desc("abro exclamación")
            self.btn_Q.set_text("Q")
            self.btn_W.set_text("W")
            self.btn_E.set_text("E")
            self.btn_R.set_text("R")
            self.btn_T.set_text("T")
            self.btn_Y.set_text("Y")
            self.btn_U.set_text("U")
            self.btn_I.set_text("I")
            self.btn_O.set_text("O")
            self.btn_P.set_text("P")
            self.btn_A.set_text("A")
            self.btn_S.set_text("S")
            self.btn_D.set_text("D")
            self.btn_F.set_text("F")
            self.btn_G.set_text("G")
            self.btn_H.set_text("H")
            self.btn_J.set_text("J")
            self.btn_K.set_text("K")
            self.btn_L.set_text("L")
            self.btn_enie.set_text("Ñ")
            self.btn_menor.set_text("<")
            self.btn_menor.set_text_desc("menor")
            self.btn_Z.set_text("Z")
            self.btn_X.set_text("X")
            self.btn_C.set_text("C")
            self.btn_V.set_text("V")
            self.btn_B.set_text("B")
            self.btn_N.set_text("N")
            self.btn_M.set_text("M")
            self.btn_coma.set_text(",")
            self.btn_coma.set_text_desc("coma")
            self.btn_punto.set_text(".")
            self.btn_punto.set_text_desc("punto")
            self.btn_guion.set_text("-")
            self.btn_guion.set_text_desc("guión")
            self.btn_A_tilde.set_text("Á")
            self.btn_A_tilde.set_text_desc("Á tilde")
            self.btn_E_tilde.set_text("É")
            self.btn_E_tilde.set_text_desc("É tilde")
            self.btn_I_tilde.set_text("Í")
            self.btn_I_tilde.set_text_desc("Í tilde")
            self.btn_O_tilde.set_text("Ó")
            self.btn_O_tilde.set_text_desc("Ó tilde")
            self.btn_U_tilde.set_text("Ú")
            self.btn_U_tilde.set_text_desc("Ú tilde")
            self.btn_U_puntos.set_text("Ü")
            self.btn_U_puntos.set_text_desc("u diéresis")
            self.btn_abre_llave.set_text("[")
            self.btn_abre_llave.set_text_desc("abro paréntesis recto")
            self.btn_cierra_llave.set_text("]")
            self.btn_cierra_llave.set_text_desc("abro paréntesis recto")


            self.MAYUSCULA = True
            self.btn_CAPS_LOCK.set_text("MINÚSCULA")
            self.btn_CAPS_LOCK.set_text_desc("MINÚSCULA")
        if (self.hablar_al == "ESCRIBIR"):
            self.btn_actual = self.btn_CAPS_LOCK
            self.hablar()

########################################################################

    def set_botonesXbarridoXfila(self, widget):
        state = widget.get_active()
        if state:
            self.BOTONESxBARRIDOxFILA = True
            self.grabar_barrido("SI")
            self.BOTONESxBARRIDO = False #nuevo
            self.botonesXbarridoXfila()
        else:
            if (self.BOTONESxBARRIDOxFILA):
                self.BOTONESxBARRIDOxFILA = False
                self.iluminarFila(self.fila_actual_nro, "white")
            self.iluminarBoton(self.btn_actual, "white")
            self.BOTONESxBARRIDO = False
            self.grabar_barrido("NO")

    def botonesXbarridoXfila(self):
        GObject.timeout_add(self.seg, self.barrerFocusXfila1)

    def barrerFocusXfila1(self, *arg):
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.fila_actual_nro = 1
        self.fila_actual = self.fila_1
        self.iluminarBoton(self.btn_actual, "white") #nuevo, sacarlo
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarFila(1, "Yellow")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        if self.BOTONESxBARRIDOxFILA:
            if (not self.fila_2 == []):
                GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE,1, 2)
            else:
                GObject.timeout_add(self.seg, self.barrerFocusXfila1)

    def barrer_el_boton(self, btn , fila_anterior, fila_a_seguir):
        if not self.BOTONESxBARRIDOxFILA:
            return False

        self.fila_actual_nro = -1
        self.fila_actual = None
        self.btn_actual = btn
        self.iluminarFila(fila_anterior, "white")

        if (self.hablar_al == "BARRER"):
            self.hablar()

        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarBoton(self.btn_actual, "Yellow")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        if self.BOTONESxBARRIDOxFILA:
            if fila_a_seguir==1:
                GObject.timeout_add(self.seg, self.barrerFocusXfila1)
            if fila_a_seguir==2:
                GObject.timeout_add(self.seg, self.barrerFocusXfila2)
            if fila_a_seguir==3:
                GObject.timeout_add(self.seg, self.barrerFocusXfila3)
            if fila_a_seguir==4:
                GObject.timeout_add(self.seg, self.barrerFocusXfila4)
            if fila_a_seguir==5:
                GObject.timeout_add(self.seg, self.barrerFocusXfila5)



    def barrerFocusXfila2(self, *arg):
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarBoton(self.btn_actual, "white")
        self.fila_actual_nro = 2
        self.fila_actual = self.fila_2
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarFila(2, "Yellow")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        if self.BOTONESxBARRIDOxFILA:
            if (not self.fila_3 == []):
                GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE,2, 3)
            else:
                GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE,2, 1)


    def barrerFocusXfila3(self, *arg):
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.fila_actual_nro = 3
        self.fila_actual = self.fila_3
        self.iluminarBoton(self.btn_actual, "white")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarFila(3, "Yellow")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        if self.BOTONESxBARRIDOxFILA:
            if (not self.fila_4 == []):
                GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE, 3, 4)
            else:
                GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE, 3, 1)


    def barrerFocusXfila4(self, *arg):
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.fila_actual_nro = 4
        self.fila_actual = self.fila_4
        self.iluminarBoton(self.btn_actual, "white")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarFila(4, "Yellow")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        if self.BOTONESxBARRIDOxFILA:
            if (not self.fila_5 == []):
                GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE, 4, 5)
            else:
                if (self.teclado_tipo=="LETRAS" or self.teclado_tipo=="COMPLETO"):
                    GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_SPACE, 4, 1)
                else:
                    GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_BACK_SPACE, 4, 1)


    def barrerFocusXfila5(self, *arg):
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.fila_actual_nro = 5
        self.fila_actual = self.fila_5
        self.iluminarBoton(self.btn_actual, "white")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        self.iluminarFila(5, "Yellow")
        if not self.BOTONESxBARRIDOxFILA:
            return False
        if self.BOTONESxBARRIDOxFILA:
            GObject.timeout_add(self.seg, self.barrer_el_boton, self.btn_SPACE, 5, 1)


    def iluminarFila(self, fila, color):
        if fila == 1:
            for f in range(0,len(self.fila_1)):
                GObject.idle_add(self.pintarControl,self.fila_1[f], color)
        if fila == 2:
            for f in range(0,len(self.fila_2)):
                GObject.idle_add(self.pintarControl,self.fila_2[f], color)
        if fila == 3:
            for f in range(0,len(self.fila_3)):
                GObject.idle_add(self.pintarControl,self.fila_3[f], color)
        if fila == 4:
            for f in range(0,len(self.fila_4)):
                GObject.idle_add(self.pintarControl,self.fila_4[f], color)
        if fila == 5:
            for f in range(0,len(self.fila_5)):
                GObject.idle_add(self.pintarControl,self.fila_5[f], color)

    def pintarControl(self, w, color):
        if not w == None:
            w.modify_bg( Gtk.StateType.NORMAL, Gdk.color_parse(color))

    def mouse_boton(self, widget, event):
        #evita repetición
        self.bloquearHandler()

        if self.BOTONESxBARRIDO:
            self.BOTONESxBARRIDO=False
            self.btn_actual.emit("pressed")
            #voler a empezar...
            self.iluminarBoton(self.btn_actual, "white")
            self.BOTONESxBARRIDOxFILA = True
            self.botonesXbarridoXfila()
            return
        if self.BOTONESxBARRIDOxFILA:
            if self.fila_actual_nro==-1: #es un boton
                self.btn_actual.emit("pressed")
                self.iluminarBoton(self.btn_actual, "white") #nuevo
            else:
                self.BOTONESxBARRIDOxFILA = False;
                self.iluminarFila(self.fila_actual_nro, "white")
                self.BOTONESxBARRIDO = True;
                self.botonesXbarridoEnFila()



    def iluminarBoton(self, btn, color):
        GObject.idle_add(self.pintarControl,btn, color)

    def bloquearHandler(self):
        self.hilo_bloquear = threading.Thread(target = self.bloquearHandler_aux_obj)
        self.hilo_bloquear.start()
        self.hilo_bloquear.quit = True

    def bloquearHandler_aux_obj(self):
        self.event_box.handler_block(self.ebc)
        try:
            seg=self.get_time_barrido_botones()
        except:
            seg = velocidades['media']

        s = seg/1000
        if self.BOTONESxBARRIDOxFILA:
            if self.fila_actual_nro==-1: #es un boton
                if seg == velocidades['rapida']:
                    s = s - 0.5
                else:
                    s = s - 1
        time.sleep(s)
        self.event_box.handler_unblock(self.ebc)


    def botonesXbarridoEnFila(self):
        GObject.idle_add(self.barrerEnFila)

    def barrerEnFila(self):
        if self.BOTONESxBARRIDO:
            i=0
            GObject.timeout_add(self.seg, self.barrerEnFila_aux, i)

    def barrerEnFila_aux(self, i):
        if not self.BOTONESxBARRIDO:
            return False
        try:
            self.btn_ant = self.fila_actual[i-1]
        except:
            return False
        try:
            self.btn_actual = self.fila_actual[i]
        except:
            self.BOTONESxBARRIDO = False
            self.BOTONESxBARRIDOxFILA = True
            self.botonesXbarridoXfila()
            return False
        if not self.BOTONESxBARRIDO:
            return False
        self.iluminarBoton(self.btn_ant, "white")
        if not self.BOTONESxBARRIDO:
            return False
        self.iluminarBoton(self.btn_actual, "Yellow")

        if (self.hablar_al == "BARRER"):
            self.hablar()

        if not self.BOTONESxBARRIDO:
            return False
        else:
            GObject.timeout_add(self.seg, self.barrerEnFila_aux, i+1)


    def combo_tiempos_botones(self):
        cb = Gtk.ComboBoxText()
        cb.append_text("RÁPIDO")
        cb.append_text("MEDIO")
        cb.append_text("LENTO")
        seg = velocidades['media']
        try:
            seg = self.get_time_barrido_botones()
            logging.debug('seg : ' + seg)
        except:
            logging.debug("ERROR al leer velocidad de barrido de botones")

        if seg==velocidades['rapida']:
            cb.set_active(0)
        if seg==velocidades['media']:
            cb.set_active(1)
        if seg==velocidades['lenta']:
            cb.set_active(2)

        cb.connect("changed", self.on_changed_cbo_time_btn)
        return cb


    def combo_size_botones(self):
        cb = Gtk.ComboBoxText()
        cb.append_text("CHICO")
        cb.append_text("MEDIANO")
        cb.append_text("GRANDE")
        size="CHICO"
        try:
            size = self.get_size_botones()
        except:
            logging.debug("ERROR, al leer size de botones")

        if size=="CHICO":
            cb.set_active(0)
        if size=="MEDIANO":
            cb.set_active(1)
        if size=="GRANDE":
            cb.set_active(2)

        cb.connect("changed", self.on_changed_cbo_size_btn)
        return cb

    def combo_tipo_teclados(self):
        cb = Gtk.ComboBoxText()
        cb.append_text("COMPLETO")
        cb.append_text("NUMÉRICO")
        cb.append_text("LETRAS")
        tipo="COMPLETO"
        try:
            tipo = self.get_tipo_teclado()
        except:
            logging.debug("ERROR, al leer tipo de teclado")

        if tipo=="COMPLETO":
            cb.set_active(0)
        if tipo=="NUMERICO":
            cb.set_active(1)
        if tipo=="LETRAS":
            cb.set_active(2)

        cb.connect("changed", self.on_changed_cbo_tipo_teclados)
        return cb

    def on_changed_cbo_tipo_teclados(self, widget):
        s = widget.get_active()

        if s==0:
            tipo = "COMPLETO"
        if s==1:
            tipo = "NUMERICO"
        if s==2:
            tipo = "LETRAS"

        self.set_tipo_teclado(tipo)

        self.dialog_opciones.hide()
        self.reset()


    def on_changed_cbo_size_btn(self, widget):
        s = widget.get_active()

        if s==0:
            size = "CHICO"
        if s==1:
            size = "MEDIANO"
        if s==2:
            size = "GRANDE"

        self.set_size_botones(size)

        self.dialog_opciones.hide()
        self.reset()


    def on_changed_cbo_time_btn(self, widget):
        s = widget.get_active()

        if s==0:
            seg = velocidades['rapida']
        if s==1:
            seg = velocidades['media']
        if s==2:
            seg = velocidades['lenta']

        self.set_time_barrido_botones(seg)
        self.seg=seg



    def get_time_barrido_botones(self):
        client = GConf.Client.get_default()
        return client.get_int("/desktop/sugar/virtualkeyboard/time")

    def set_time_barrido_botones(self, seg):
        client = GConf.Client.get_default()
        client.set_int("/desktop/sugar/virtualkeyboard/time", seg)

    def get_size_botones(self):
        client = GConf.Client.get_default()
        return client.get_string("/desktop/sugar/virtualkeyboard/size")

    def set_size_botones(self, size):
        client = GConf.Client.get_default()
        client.set_string("/desktop/sugar/virtualkeyboard/size", size)

    def set_hablar(self, hablar):
        client = GConf.Client.get_default()
        client.set_string("/desktop/sugar/virtualkeyboard/hablar", hablar)
        self.hablar_al = hablar

    def get_tipo_teclado(self):
        client = GConf.Client.get_default()
        return client.get_string("/desktop/sugar/virtualkeyboard/tipo")

    def set_tipo_teclado(self, tipo):
        client = GConf.Client.get_default()
        client.set_string("/desktop/sugar/virtualkeyboard/tipo", tipo)

    def leer_barrido(self):
        client = GConf.Client.get_default()
        return client.get_string("/desktop/sugar/virtualkeyboard/barrido")


    def grabar_barrido(self, barrido):
        client = GConf.Client.get_default()
        client.set_string("/desktop/sugar/virtualkeyboard/barrido", barrido)

    def get_opciones_hablar(self):
        client = GConf.Client.get_default()
        return client.get_string("/desktop/sugar/virtualkeyboard/hablar")

    def set_opciones_hablar(self, widget, data=None):
        if (widget.get_active()):
            self.set_hablar(data)

    def inicilizar_config(self):
        client = GConf.Client.get_default()
        if not client.dir_exists("/desktop/sugar/virtualkeyboard"):
            self.set_time_barrido_botones(self.seg)
            self.set_size_botones(self.size)
            self.set_hablar(self.hablar_al)
            self.set_tipo_teclado(self.teclado_tipo)
            if self.BOTONESxBARRIDOxFILA:
                self.grabar_barrido("SI")
            else:
                self.grabar_barrido("NO")

    def new_button(self, icon, label, callbackstr):
        btn = Boton(label)
        btn.set_font_desc("sans 9")
        btn.connect("pressed", callbackstr)
        if (not icon == None):
            btn.set_icon(icon)
        return btn


    def sizeBotones(self, desc):
        for btn in self.losBotones:
            btn.set_font_desc(desc)

    def reset(self):
        self.close()
        Teclado()

    def hablar(self):
        self.hilo_hablar = threading.Thread(target=self.hablar_aux)
        self.hilo_hablar.start()
        self.hilo_hablar.quit=True

    def hablar_aux(self):
        texto = ""
        v = ""
        try:
            texto = self.btn_actual.get_text_desc()
        except:
            return
        if (not texto == ""):
            try:
                seg=self.get_time_barrido_botones()
            except:
                seg = velocidades['media']
            if seg == velocidades['rapida']:
                v = hablar['rapida']
            if seg == velocidades['media']:
                v = hablar['media']
            if seg == velocidades['lenta']:
                v = hablar['lenta']
            self._mTeclado.hablar(texto, v)

    def desplegar_opciones(self, *arg):
        try:
            if (self.dialog_opciones.get_property('visible')):
                return
        except:
            pass

        self.dialog_opciones = Gtk.Dialog()
        self.dialog_opciones.set_title("OPCIONES")
        self.dialog_opciones.set_keep_above(True)

        #opciones hablar
        box_hablar = Gtk.VBox(False, 10)
        box_hablar.set_border_width(20)

        button = Gtk.RadioButton.new_with_label(None, "HABLAR AL BARRER BOTONES.")
        button.connect("toggled", self.set_opciones_hablar, "BARRER")
        if (self.get_opciones_hablar()=="BARRER"):
            button.set_active(True)
        box_hablar.pack_start(button, True, True, 0)
        button = Gtk.RadioButton.new_with_label_from_widget(button, "HABLAR AL ESCRIBIR.")
        button.connect("toggled", self.set_opciones_hablar, "ESCRIBIR")
        if (self.get_opciones_hablar()=="ESCRIBIR"):
            button.set_active(True)
        box_hablar.pack_start(button, True, True, 0)
        button = Gtk.RadioButton.new_with_label_from_widget(button, "NO HABLAR.")
        button.connect("toggled", self.set_opciones_hablar, "NUNCA")
        if (self.get_opciones_hablar()=="NUNCA"):
            button.set_active(True)
        box_hablar.pack_start(button, True, True, 0)
        self.dialog_opciones.vbox.pack_start(box_hablar, True, True, 0)

        separator_hablar = Gtk.HSeparator()
        self.dialog_opciones.vbox.pack_start(separator_hablar, False, False, 0)
        separator_hablar.show()

        #opciones de barrido
        box_barrido = Gtk.VBox(False, 10)
        box_barrido.set_border_width(20)

        lbl_op_botones = Gtk.Label("Barrer:")
        lbl_op_botones.show()
        box_barrido.pack_start(lbl_op_botones, True, True, 0)

        self.chk_activarBarrido_botones = Gtk.CheckButton("_BOTONES")

        barriendo= ""
        try:
            barriendo = self.leer_barrido()
        except:
            barriendo == "NO"
        if barriendo == "SI":
            self.BOTONESxBARRIDOxFILA = True
        elif barriendo == "NO":
            self.BOTONESxBARRIDOxFILA = False
        else:
            logging.error("Error al leer barrido." + str(barriendo))


        self.chk_activarBarrido_botones.set_active(self.BOTONESxBARRIDOxFILA or self.BOTONESxBARRIDO)
        self.chk_activarBarrido_botones.connect("toggled", self.set_botonesXbarridoXfila)
        box_barrido.pack_start(self.chk_activarBarrido_botones, True, True, 0)

        lbl_op_velocidad = Gtk.Label("Velocidad:")
        lbl_op_velocidad.show()
        box_barrido.pack_start(lbl_op_velocidad, True, True, 0)

        self.cbo_time_btn = self.combo_tiempos_botones()
        box_barrido.pack_start(self.cbo_time_btn, True, True, 0)
        self.dialog_opciones.vbox.pack_start(box_barrido, True, True, 0)

        separator_barrido = Gtk.HSeparator()
        self.dialog_opciones.vbox.pack_start(separator_barrido, False, False, 0)
        separator_barrido.show()

        #opciones de tamaño
        box_size = Gtk.VBox(False, 10)
        box_size.set_border_width(20)

        lbl_op_size = Gtk.Label("Tamaño:")
        lbl_op_size.show()
        box_size.pack_start(lbl_op_size, True, True, 0)

        self.cbo_size_btn = self.combo_size_botones()
        box_size.pack_start(self.cbo_size_btn, True, True, 0)
        self.dialog_opciones.vbox.pack_start(box_size, True, True, 0)

        separator_size = Gtk.HSeparator()
        self.dialog_opciones.vbox.pack_start(separator_size, False, False, 0)
        separator_size.show()

        #tipo
        box_teclado = Gtk.VBox(False, 10)
        box_teclado.set_border_width(20)

        lbl_op_tipo = Gtk.Label("Tipo:")
        lbl_op_tipo.show()
        box_teclado.pack_start(lbl_op_tipo, True, True, 0)

        self.cbo_tipo_teclado = self.combo_tipo_teclados()
        box_teclado.pack_start(self.cbo_tipo_teclado, True, True, 0)
        self.dialog_opciones.vbox.pack_start(box_teclado, True, True, 0)

        separator_tipo = Gtk.HSeparator()
        self.dialog_opciones.vbox.pack_start(separator_tipo, False, False, 0)
        separator_tipo.show()

        self.dialog_opciones.show_all()



    def set_opciones_hablar(self, widget, data=None):
        if (widget.get_active()):
            self.set_hablar(data)
################################################################################################################
    def mostrar_teclado_numerico(self):
        child = Gtk.VBox(False, 2)

        self.fila_1 = []
        self.fila_2 = []
        self.fila_3 = []
        self.fila_4 = []
        self.fila_5 = []
        self.losBotones = []

        # defino botones
        self.btn_BACK_SPACE = self.new_button_borrar()
        self.losBotones.append(self.btn_BACK_SPACE)

        self.btn_1 = self.new_button_escribir("1")
        self.losBotones.append(self.btn_1)
        self.fila_3.append(self.btn_1)

        self.btn_2 = self.new_button_escribir("2")
        self.losBotones.append(self.btn_2)
        self.fila_3.append(self.btn_2)

        self.btn_3 = self.new_button_escribir("3")
        self.losBotones.append(self.btn_3)
        self.fila_3.append(self.btn_3)

        self.btn_4 = self.new_button_escribir("4")
        self.losBotones.append(self.btn_4)
        self.fila_2.append(self.btn_4)

        self.btn_5 = self.new_button_escribir("5")
        self.losBotones.append(self.btn_5)
        self.fila_2.append(self.btn_5)

        self.btn_6 = self.new_button_escribir("6")
        self.losBotones.append(self.btn_6)
        self.fila_2.append(self.btn_6)

        self.btn_7 = self.new_button_escribir("7")
        self.losBotones.append(self.btn_7)
        self.fila_1.append(self.btn_7)

        self.btn_8 = self.new_button_escribir("8")
        self.losBotones.append(self.btn_8)
        self.fila_1.append(self.btn_8)

        self.btn_9 = self.new_button_escribir("9")
        self.losBotones.append(self.btn_9)
        self.fila_1.append(self.btn_9)

        self.btn_0 = self.new_button_escribir("0")
        self.losBotones.append(self.btn_0)
        self.fila_4.append(self.btn_0)

        self.btn_asterisco = self.new_button_escribir("*")
        self.btn_asterisco.set_text_desc("por")
        self.losBotones.append(self.btn_asterisco)
        self.fila_3.append(self.btn_asterisco)

        self.btn_barra = self.new_button_escribir("/")
        self.btn_barra.set_text_desc("dividido")
        self.losBotones.append(self.btn_barra)
        self.fila_3.append(self.btn_barra)

        self.btn_mas = self.new_button_escribir("+")
        self.btn_mas.set_text_desc("más")
        self.losBotones.append(self.btn_mas)
        self.fila_2.append(self.btn_mas)

        self.btn_punto = self.new_button_escribir(".")
        self.btn_punto.set_text_desc("punto")
        self.losBotones.append(self.btn_punto)
        self.fila_4.append(self.btn_punto)

        self.btn_guion = self.new_button_escribir("-")
        self.btn_guion.set_text_desc("menos")
        self.losBotones.append(self.btn_guion)
        self.fila_2.append(self.btn_guion)

        self.btn_ENTER = self.new_button_enter()
        self.losBotones.append(self.btn_ENTER)
        self.fila_4.append(self.btn_ENTER)

        self.btn_opciones = self.new_button(Gtk.STOCK_PREFERENCES, None ,self.desplegar_opciones)
        self.btn_cambiar_tipo = self.new_button_cambiar_tipo("ABC")
        self.fila_4.append(self.btn_cambiar_tipo)

        table = Gtk.Table(6, 11, True)

        table.set_row_spacing(0, 3)
        table.set_row_spacing(1, 3)
        table.set_row_spacing(2, 3)
        table.set_row_spacing(3, 3)
        table.set_row_spacing(4, 3)
        table.set_row_spacing(5, 3)

        table.set_col_spacing(0, 3)
        table.set_col_spacing(1, 3)
        table.set_col_spacing(2, 3)
        table.set_col_spacing(3, 3)
        table.set_col_spacing(4, 3)
        table.set_col_spacing(5, 15)
        table.set_col_spacing(6, 3)
        table.set_col_spacing(7, 3)
        table.set_col_spacing(8, 3)
        table.set_col_spacing(9, 3)
        table.set_col_spacing(10, 15)

        table.attach(self.btn_7, 0, 2, 0, 2)
        table.attach(self.btn_8, 2, 4, 0, 2)
        table.attach(self.btn_9, 4, 6, 0, 2)
        table.attach(self.btn_BACK_SPACE, 6, 10, 0, 2)

        table.attach(self.btn_4, 0, 2, 2, 4)
        table.attach(self.btn_5, 2, 4, 2, 4)
        table.attach(self.btn_6, 4, 6, 2, 4)
        table.attach(self.btn_mas, 6, 8, 2, 4)
        table.attach(self.btn_guion, 8, 10, 2, 4)

        table.attach(self.btn_1, 0, 2, 4, 6)
        table.attach(self.btn_2, 2, 4, 4, 6)
        table.attach(self.btn_3, 4, 6, 4, 6)
        table.attach(self.btn_asterisco, 6, 8, 4, 6)
        table.attach(self.btn_barra, 8, 10, 4, 6)

        table.attach(self.btn_0, 0, 2, 6, 8)
        table.attach(self.btn_punto, 2, 4, 6, 8)
        table.attach(self.btn_ENTER, 6, 10, 6, 8)

        table.attach(self.btn_opciones, 10, 11, 6, 7)
        table.attach(self.btn_cambiar_tipo, 10, 11, 7, 8)


        child.pack_end(table, True, True, 0)

        return child

    def posicionar_dialog(self, dialog):
        dialog.set_gravity(Gdk.Gravity.SOUTH_EAST)
        width, height = dialog.get_size()
        dialog.move(Gdk.Screen.width() - width, Gdk.Screen.height() - height)

    def mostrar_teclado_letras(self):
        self.fila_1 = []
        self.fila_2 = []
        self.fila_3 = []
        self.fila_4 = []
        self.fila_5 = []
        self.losBotones = []

        child = Gtk.VBox(False, 2)

        # defino botones
        self.btn_BACK_SPACE = self.new_button_borrar()
        self.losBotones.append(self.btn_BACK_SPACE)

        self.btn_SPACE = self.new_button_espacio()
        self.losBotones.append(self.btn_SPACE)

        self.btn_ENTER = self.new_button_enter()
        self.losBotones.append(self.btn_ENTER)
        self.fila_2.append(self.btn_ENTER)

        self.btn_Q = self.new_button_escribir("Q")
        self.losBotones.append(self.btn_Q)
        self.fila_1.append(self.btn_Q)

        self.btn_W = self.new_button_escribir("W")
        self.losBotones.append(self.btn_W)
        self.fila_1.append(self.btn_W)

        self.btn_E = self.new_button_escribir("E")
        self.losBotones.append(self.btn_E)
        self.fila_1.append(self.btn_E)

        self.btn_R = self.new_button_escribir("R")
        self.losBotones.append(self.btn_R)
        self.fila_1.append(self.btn_R)

        self.btn_T = self.new_button_escribir("T")
        self.losBotones.append(self.btn_T)
        self.fila_1.append(self.btn_T)

        self.btn_Y = self.new_button_escribir("Y")
        self.losBotones.append(self.btn_Y)
        self.fila_1.append(self.btn_Y)

        self.btn_U = self.new_button_escribir("U")
        self.losBotones.append(self.btn_U)
        self.fila_1.append(self.btn_U)

        self.btn_I = self.new_button_escribir("I")
        self.losBotones.append(self.btn_I)
        self.fila_1.append(self.btn_I)

        self.btn_O = self.new_button_escribir("O")
        self.losBotones.append(self.btn_O)
        self.fila_1.append(self.btn_O)

        self.btn_P = self.new_button_escribir("P")
        self.losBotones.append(self.btn_P)
        self.fila_1.append(self.btn_P)

        self.btn_A = self.new_button_escribir("A")
        self.losBotones.append(self.btn_A)
        self.fila_2.append(self.btn_A)

        self.btn_S = self.new_button_escribir("S")
        self.losBotones.append(self.btn_S)
        self.fila_2.append(self.btn_S)

        self.btn_D = self.new_button_escribir("D")
        self.losBotones.append(self.btn_D)
        self.fila_2.append(self.btn_D)

        self.btn_F = self.new_button_escribir("F")
        self.losBotones.append(self.btn_F)
        self.fila_2.append(self.btn_F)

        self.btn_G = self.new_button_escribir("G")
        self.losBotones.append(self.btn_G)
        self.fila_2.append(self.btn_G)

        self.btn_H = self.new_button_escribir("H")
        self.losBotones.append(self.btn_H)
        self.fila_2.append(self.btn_H)

        self.btn_J = self.new_button_escribir("J")
        self.losBotones.append(self.btn_J)
        self.fila_2.append(self.btn_J)

        self.btn_K = self.new_button_escribir("K")
        self.losBotones.append(self.btn_K)
        self.fila_2.append(self.btn_K)

        self.btn_L = self.new_button_escribir("L")
        self.losBotones.append(self.btn_L)
        self.fila_2.append(self.btn_L)

        self.btn_enie = self.new_button_escribir("Ñ")
        self.losBotones.append(self.btn_enie)
        self.fila_2.append(self.btn_enie)

        self.btn_Z = self.new_button_escribir("Z")
        self.losBotones.append(self.btn_Z)
        self.fila_3.append(self.btn_Z)

        self.btn_X = self.new_button_escribir("X")
        self.losBotones.append(self.btn_X)
        self.fila_3.append(self.btn_X)

        self.btn_C = self.new_button_escribir("C")
        self.losBotones.append(self.btn_C)
        self.fila_3.append(self.btn_C)

        self.btn_V = self.new_button_escribir("V")
        self.losBotones.append(self.btn_V)
        self.fila_3.append(self.btn_V)

        self.btn_B = self.new_button_escribir("B")
        self.losBotones.append(self.btn_B)
        self.fila_3.append(self.btn_B)

        self.btn_N = self.new_button_escribir("N")
        self.losBotones.append(self.btn_N)
        self.fila_3.append(self.btn_N)

        self.btn_M = self.new_button_escribir("M")
        self.losBotones.append(self.btn_M)
        self.fila_3.append(self.btn_M)

        self.btn_A_tilde = self.new_button_escribir("Á")
        self.btn_A_tilde.set_text_desc("Á tilde")
        self.losBotones.append(self.btn_A_tilde)
        self.fila_4.append(self.btn_A_tilde)

        self.btn_E_tilde = self.new_button_escribir("É")
        self.btn_E_tilde.set_text_desc("É tilde")
        self.losBotones.append(self.btn_E_tilde)
        self.fila_4.append(self.btn_E_tilde)

        self.btn_I_tilde = self.new_button_escribir("Í")
        self.btn_I_tilde.set_text_desc("Í tilde")
        self.losBotones.append(self.btn_I_tilde)
        self.fila_4.append(self.btn_I_tilde)

        self.btn_O_tilde = self.new_button_escribir("Ó")
        self.btn_O_tilde.set_text_desc("Ó tilde")
        self.losBotones.append(self.btn_O_tilde)
        self.fila_4.append(self.btn_O_tilde)

        self.btn_U_tilde = self.new_button_escribir("Ú")
        self.btn_U_tilde.set_text_desc("Ú tilde")
        self.losBotones.append(self.btn_U_tilde)
        self.fila_4.append(self.btn_U_tilde)

        self.btn_opciones = self.new_button(Gtk.STOCK_PREFERENCES, " ", self.desplegar_opciones)
        self.btn_cambiar_tipo = self.new_button_cambiar_tipo("123")
        self.fila_4.append(self.btn_cambiar_tipo)

        #dibujo tabla
        table = Gtk.Table(7, 13, True)

        table.set_row_spacing(0, 3)
        table.set_row_spacing(1, 3)
        table.set_row_spacing(2, 13)
        table.set_row_spacing(3, 10)
        table.set_row_spacing(4, 3)
        table.set_row_spacing(5, 3)
        table.set_row_spacing(6, 3)

        table.set_col_spacing(0, 3)
        table.set_col_spacing(1, 3)
        table.set_col_spacing(2, 3)
        table.set_col_spacing(3, 3)
        table.set_col_spacing(4, 3)
        table.set_col_spacing(5, 3)
        table.set_col_spacing(6, 3)
        table.set_col_spacing(7, 3)
        table.set_col_spacing(8, 3)
        table.set_col_spacing(9, 3)
        table.set_col_spacing(10, 3)
        table.set_col_spacing(11, 13)
        table.set_col_spacing(12, 3)


        table.attach(self.btn_Q, 0, 1, 0, 1)
        table.attach(self.btn_W, 1, 2, 0, 1)
        table.attach(self.btn_E, 2, 3, 0, 1)
        table.attach(self.btn_R, 3, 4, 0, 1)
        table.attach(self.btn_T, 4, 5, 0, 1)
        table.attach(self.btn_Y, 5, 6, 0, 1)
        table.attach(self.btn_U, 6, 7, 0, 1)
        table.attach(self.btn_I, 7, 8, 0, 1)
        table.attach(self.btn_O, 8, 9, 0, 1)
        table.attach(self.btn_P, 9, 10, 0, 1)
        table.attach(self.btn_A, 0, 1, 1, 2)
        table.attach(self.btn_S, 1, 2, 1, 2)
        table.attach(self.btn_D, 2, 3, 1, 2)
        table.attach(self.btn_F, 3, 4, 1, 2)
        table.attach(self.btn_G, 4, 5, 1, 2)
        table.attach(self.btn_H, 5, 6, 1, 2)
        table.attach(self.btn_J, 6, 7, 1, 2)
        table.attach(self.btn_K, 7, 8, 1, 2)
        table.attach(self.btn_L, 8, 9, 1, 2)
        table.attach(self.btn_Z, 0, 1, 2, 3)
        table.attach(self.btn_X, 1, 2, 2, 3)
        table.attach(self.btn_C, 2, 3, 2, 3)
        table.attach(self.btn_V, 3, 4, 2, 3)
        table.attach(self.btn_B, 4, 5, 2, 3)
        table.attach(self.btn_N, 5, 6, 2, 3)
        table.attach(self.btn_M, 6, 7, 2, 3)

        table.attach(self.btn_BACK_SPACE, 10, 13, 0, 1)
        table.attach(self.btn_ENTER, 10, 13, 1, 2)
        table.attach(self.btn_SPACE, 1, 9, 4, 5)
        table.attach(self.btn_opciones, 12, 13, 4, 5)
        table.attach(self.btn_cambiar_tipo, 12, 13, 3, 4)


        table.attach(self.btn_A_tilde, 1, 2, 3, 4)
        table.attach(self.btn_E_tilde, 2, 3, 3, 4)
        table.attach(self.btn_I_tilde, 3, 4, 3, 4)
        table.attach(self.btn_O_tilde, 4, 5, 3, 4)
        table.attach(self.btn_U_tilde, 5, 6, 3, 4)

        child.pack_end(table, True, True, 0)

        return child

    def get_size_dialog(self, size, teclado_tipo):
        if teclado_tipo == "COMPLETO":
            if size == "CHICO":
                return 700, 335
            if size == "MEDIANO":
                return 1000, 400
            if size == "GRANDE":
                return 1200, 475

        if teclado_tipo == "NUMERICO":
            if size == "CHICO":
                return 700, 400
            if size == "MEDIANO":
                return 900, 400
            if size == "GRANDE":
                return 1200, 500

        if teclado_tipo == "LETRAS":
            if size == "CHICO":
                return 830, 290
            if size == "MEDIANO":
                return 1000, 330
            if size == "GRANDE":
                return 1200, 550

    def get_font_desc(self, size, teclado_tipo):
        if teclado_tipo == "COMPLETO":
            if size == "CHICO":
                return "sans 7"
            if size == "MEDIANO":
                return "sans bold 13"
            if size == "GRANDE":
                return "sans bold 15"

        if teclado_tipo == "NUMERICO":
            if size == "CHICO":
                return "sans bold 7"
            if size == "MEDIANO":
                return "sans bold 13"
            if size == "GRANDE":
                return "sans bold 28"

        if teclado_tipo == "LETRAS":
            if size == "CHICO":
                return "sans 7"
            if size == "MEDIANO":
                return "sans bold 13"
            if size == "GRANDE":
                return "sans bold 17"

    def cambiar_tipo(self, w):

        if (self.teclado_tipo=="NUMERICO"):
            tipo = "LETRAS"
        else:
            tipo = "NUMERICO"

        self.set_tipo_teclado(tipo)

        self.reset()

class Boton(Gtk.Button):
    font_desc = ''
    font_color = ''
    fondo_color = ''
    text = ''
    text_desc = ''

    def __init__(self, nom=None):
        Gtk.Button.__init__(self)

        self.hbox = Gtk.HBox(False, 0)
        self.add(self.hbox)

        self.label = Gtk.Label()
        self.set_text(nom)

        self.set_text(nom)
        self.set_text_desc(nom)
        self.set_font_desc('sans bold 13')
        self.set_font_color('black')
        self.set_fondo_color('white')

        self.label.set_use_underline(True)
        self.hbox.add(self.label)

    def set_font_desc(self, pfont_desc):
        self.font_desc = pfont_desc
        self.label.modify_font(Pango.FontDescription(pfont_desc))

    def set_font_color(self, pfont_color):
        self.font_color = pfont_color
        self.label.modify_fg(Gtk.StateType.NORMAL, Gdk.color_parse(pfont_color))

    def set_fondo_color(self, pfondo_color):
        self.fondo_color = pfondo_color
        self.modify_bg( Gtk.StateType.NORMAL, Gdk.color_parse(pfondo_color))

    def set_text(self, ptext):
        if (not ptext == None):
            self.text = ptext
        self.label.set_text(self.text)

    def get_font_desc(self):
        return self.font_desc

    def get_font_color(self):
        return self.font_color

    def get_fondo_color(self):
        return self.fondo_color

    def get_text(self):
        return self.text

    def is_visible(self):
        self.get_property('visible')

    def get_text_desc(self):
        return self.text_desc

    def set_text_desc(self, ptext_desc):
        self.text_desc = ptext_desc

    def set_icon(self, icon):
        #http://www.pyGtk.org/docs/pyGtk/Gtk-stock-items.html
        s = Gtk.Style()
        icon = s.lookup_icon_set(icon).render_icon(s, Gtk.TextDirection.LTR, Gtk.StateType.NORMAL, Gtk.IconSize.BUTTON, self.hbox, None)
        img = Gtk.Image()
        img.set_from_pixbuf(icon)
        self.hbox.add(img)
