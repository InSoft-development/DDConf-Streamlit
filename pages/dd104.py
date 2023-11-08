import streamlit as st
import pandas as pd

import syslog, json, platform, subprocess
from pathlib import Path
from os.path import exists
from os import W_OK, R_OK, access, makedirs

confile = ""
_mode = 'tx'

def init():
	global confile
	confile = '/opt/dd/dd104client.ini'

def load_from_file(_path=confile) -> dict:
	mode = _mode.lower()
	try:
		lines = [ x.strip() for x in Path(_path).read_text().split('\n') if not x == '']
	except FileNotFoundError:
		return {'count':-1}
	
	data = {} # {'count':N, 'mode':mode, 'old_..._...1':..., ...}
	block = 0
	for line in lines:
		if 'receiver' in line:
			block = 1
		elif 'server' in line:
			block = 2
		else:
			if block == 1:
				if 'address' in line and not line[0] == '#':
					data['old_recv_addr'] = line.split('=')[1]
			elif block == 2:
				if mode == 'tx':
					if 'address' in line and not line[0] == '#':
						data[f'old_server_addr{line.split("=")[0].strip()[-1]}'] = line.split('=')[1].strip()
					elif 'port' in line and not line[0] == '#':
						data[f'old_server_port{line.split("=")[0].strip()[-1]}'] = line.split('=')[1].strip() 
				elif mode == 'rx':
					if 'address' in line and not line[0] == '#':
						data['old_addr'] = line.split('=')[1].strip()
					elif 'port' in line and not line[0] == '#':
						data['old_port'] = line.split('=')[1].strip()
					elif 'queuesize' in line and not line[0] == '#':
						data['old_queuesize'] = line.split('=')[1].strip()
					elif 'mode' in line and not line[0] == '#':
						data['old_mode'] = line.split('=')[1].strip()
	
	if mode == 'tx':
		data['count'] = len(data.keys())//2
	else:
		data['count'] = 1
	
	return data


#tx
def render():
	st.title('Data Diode Configuration Service')
	st.header('Protocol 104 configuration page')
	#TODO: expand on merge with rx
	data = load_from_file(confile)
	st.write(data)
	if data['count'] > 0:
		with st.container():
			st.text_input(label = "Receiver Address (DON'T CHANGE UNLESS YOU KNOW WHAT YOU'RE DOING)", value = data['old_recv_addr'] )
			del(data['count'])
			for i in data.keys():
				st.text_input(label=i, value=data[i])
			st.button(label='Submit',on_click=None)

init()
render()
