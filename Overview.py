import streamlit as st
import pandas as pd
from streamlit_js_eval import streamlit_js_eval

import syslog, asyncio, json, platform, argparse, subprocess
from pathlib import Path
from os.path import exists
from os import W_OK, R_OK, access, makedirs, _exit
from shutil import copy2, copyfileobj, unpack_archive

#from . import settings

# parser = argparse.ArgumentParser(description='DataDiodeConfigurationService')
# 
# parser.add_argument('--port', help="HTTP access port")
# # parser.add_argument('--mode', help='Operation mode (possible values are: RX, TX')
# try:
# 	args = parser.parse_args()
# except SystemExit as e:
# 	# This exception will be raised if --help or invalid command line arguments
# 	# are used. Currently streamlit prevents the program from exiting normally
# 	# so we have to do a hard exit.
# 	_exit(e.code)

def render():
	st.title(body='Сервис конфигурации Диода Данных')
	st.empty()
	st.write("Добро пожаловать в сервис конфигурации Диода Данных.\nДля начала настройки выберите интересующий вас пункт\nиз левой боковой панели.")



render()
