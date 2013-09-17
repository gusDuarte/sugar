# Copyright (C) 2010 Plan Ceibal <comunidad@plan.ceibal.edu.uy>

import os

import ConfigParser
import logging
from gi.repository import GObject

from jarabe.view.viewsource import setup_view_source
from sugar import env

if os.path.exists('/etc/debian_version'):
    KEY='F8'
else:
    KEY='F13'

PATH_VMG_CONFIG = os.environ['HOME'] + '/.magnifier.ini'
BOUND_KEYS = ['<shift>'+KEY, KEY, '<control>'+KEY]

def handle_key_press(key):
    logger = logging.getLogger('magnifier')
    logger.setLevel(logging.DEBUG)
    logger.debug("Ejecutando magnifier......" + key)
    if (key=='<shift>'+KEY):
        set_ruta_archivo()
        set_GraphicsTools()
    if (key=='<control>'+KEY):
        set_ruta_archivo()
        set_InvertColors()
    _run_cmd_async('launchVmg')

def get_GraphicsTools():
    return leer_config('General', 'GraphicsTools')

def set_GraphicsTools():
    grabar_config_GraphicsTools('General', 'GraphicsTools')

def grabar_config_GraphicsTools(encabezado, etiqueta):
    parser = ConfigParser.ConfigParser()
    parser.read(PATH_VMG_CONFIG)
    val_old = get_GraphicsTools()  
    if val_old == '1':
        parser.set(encabezado, etiqueta, '0')
        arch = open(PATH_VMG_CONFIG, 'w')
        parser.write(arch)
        arch.close()
    else:
        parser.set(encabezado, etiqueta, '1')
        arch = open(PATH_VMG_CONFIG, 'w')
        parser.write(arch)
        arch.close()    

def get_InvertColors():
    return leer_config('General', 'InvertColors')

def set_InvertColors():
    grabar_config_InvertColors('General', 'InvertColors')

def grabar_config_InvertColors(encabezado, etiqueta):
    parser = ConfigParser.ConfigParser()
    parser.read(PATH_VMG_CONFIG)
    val_old = get_InvertColors()  
    if val_old == '1':
        parser.set(encabezado, etiqueta, '0')
        arch = open(PATH_VMG_CONFIG, 'w')
        parser.write(arch)
        arch.close()
    else:
        parser.set(encabezado, etiqueta, '1')
        arch = open(PATH_VMG_CONFIG, 'w')
        parser.write(arch)
        arch.close() 

def leer_config(encabezado, etiqueta):
    parser = ConfigParser.ConfigParser()
    parser.read(PATH_VMG_CONFIG)
    return parser.get(encabezado, etiqueta)

def set_ruta_archivo():
    try:
        f = file(PATH_VMG_CONFIG)
    except:
        PATH_VMG_CONFIG = "/root/.magnifier.ini"

def _run_cmd_async(cmd):
    logger = logging.getLogger('magnifier')
    logger.setLevel(logging.DEBUG)
    try:
        GObject.spawn_async([find_and_absolutize('launchVmg')])
        logger.debug("Ejecuto magnifier")
    except Exception, e:
        logger.debug("Error ejecutando magnifier" + str(e))

def find_and_absolutize(script_name):
    paths = env.os.environ['PATH'].split(':')
    for path in paths:
        looking_path =  path + '/' + script_name
        if env.os.path.isfile(looking_path):
            return looking_path
    return None
