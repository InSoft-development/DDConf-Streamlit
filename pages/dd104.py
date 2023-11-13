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
	if 'dd104' not in st.session_state.keys():
		st.session_state['dd104'] = {}

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
		message=f"receiver\naddress={data['recv_addr']}\n\nserver"
		for i in range(1, data['count']+1):
			message = message + f"\naddress{i}={data[f'server_addr{i}']}\nport{i}={data[f'server_port{i}']}" 
		st.write(message)
		return message

def save_to_file(string:str) -> None:
	with Path(confile).open("w") as f:
		f.write(string)
	

def sanitize():
	#move stuff from st.session_state to st.<...>.dd104
	for k,v in st.session_state.items():
		if ('server_addr' in k or 'server_port' in k or 'recv_addr' in k):
			st.session_state.dd104[k] = v
			del(st.session_state[k])
	
	#sanitize
	for i in range(1, st.session_state.dd104['count']+1):
		if (st.session_state.dd104[f"server_addr{i}"] == '' or st.session_state.dd104[f"server_port{i}"] == ''):
			for j in range(i+1, st.session_state.dd104['count']+1):
				if (st.session_state.dd104[f"server_addr{j}"] and st.session_state.dd104[f"server_port{j}"]):
					st.session_state.dd104[f"server_addr{i}"] = st.session_state.dd104[f"server_addr{j}"]
					st.session_state.dd104[f"server_port{i}"] = st.session_state.dd104[f"server_port{j}"]
					st.session_state.dd104[f"server_addr{j}"] = ''
					st.session_state.dd104[f"server_port{j}"] = ''
					break
	
	c = st.session_state.dd104['count']
	for i in range(1, c+1):
		if i <= st.session_state.dd104['count']+1:
			if (st.session_state.dd104[f"server_addr{i}"] == '' or st.session_state.dd104[f"server_port{i}"] == ''):
				st.session_state.dd104['count'] -= 1
				del(st.session_state.dd104[f"server_addr{i}"])
				del(st.session_state.dd104[f"server_port{i}"])
	

#tx
def render():
	st.set_page_config(layout="wide")
	st.title('Data Diode Configuration Service')
	st.header('Protocol 104 configuration page')
	#TODO: expand on merge with rx
	data = load_from_file(confile)
	#st.write(data)
	col1, col2 = st.columns([0.3, 0.7], gap='large')
	with col1:
		f = st.form("dd104form")
		if "count" not in st.session_state.dd104:
			st.session_state.dd104['count'] = data['count']
		if st.session_state.dd104['count'] > 0:
			with f:
				st.text_input(label = "Receiver Address (DON'T CHANGE UNLESS YOU KNOW WHAT YOU'RE DOING)", value = data['old_recv_addr'], key='recv_addr')
				
				for i in range(1, st.session_state.dd104['count']+1):
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
			
			st.session_state.dd104['count'] += 1
			
			with f:
				st.text_input(label=f"Server Address {st.session_state.dd104['count']}", key=f"server_addr{st.session_state.dd104['count']}")
				st.text_input(label=f"Server Port {st.session_state.dd104['count']}", key=f"server_port{st.session_state.dd104['count']}")
		
		if submit:
			
			try:
				sanitize()
				with col2:
					st.write(st.session_state)
					save_to_file(parse_from_user(st.session_state.dd104))
			except Exception as e:
				with col2:
					st.write(f"{type(e)}: {str(e)}")
	
	
	
init()
render()
