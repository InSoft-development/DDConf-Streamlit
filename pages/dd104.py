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

def parse_from_user(data) -> str:
	mode = _mode.lower()
	if mode == 'tx':
		message=f'''
receiver
address={data['recv_addr']}
server
		'''
	

#tx
def render():
	st.title('Data Diode Configuration Service')
	st.header('Protocol 104 configuration page')
	#TODO: expand on merge with rx
	data = load_from_file(confile)
	#st.write(data)
	f = st.form("dd104form")
	if "count" not in st.session_state:
		st.session_state.count = data['count']
	if st.session_state.count > 0:
		with f:
			st.text_input(label = "Receiver Address (DON'T CHANGE UNLESS YOU KNOW WHAT YOU'RE DOING)", value = data['old_recv_addr'], key='recv_addr')
			
			for i in range(1, st.session_state.count+1):
				st.write(f"Server {i}")
				if f'old_server_addr{i}' in data.keys():
					st.text_input(label=f'Server Address {i}', value=data[f'old_server_addr{i}'], key=f'server_addr{i}') 
					st.text_input(label=f'Server Port {i}', value=data[f'old_server_port{i}'], key=f'server_port{i}') 
				else:
					st.text_input(label=f'Server Address {i}', key=f'server_addr{i}') 
					st.text_input(label=f'Server Port {i}', key=f'server_port{i}') 
				
			submit = st.form_submit_button(label='Submit')
	
	adder = st.button("Add Server")
	if adder:
		
		st.session_state.count += 1
		
		with f:
			st.text_input(label=f"Server Address {st.session_state.count}", key=f"server_addr{st.session_state.count}")
			st.text_input(label=f"Server Port {st.session_state.count}", key=f"server_port{st.session_state.count}")
	
	if submit:
		try:
			st.write(st.session_state)
			#save_to_struct()
		except Exception as e:
			st.write(f"{type(e)}: {str(e)}")
	
	
	
init()
render()
