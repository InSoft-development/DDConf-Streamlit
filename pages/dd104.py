import streamlit as st
import pandas as pd
from streamlit_modal import Modal

import syslog, platform, subprocess
from pathlib import Path
from os.path import exists
from os import W_OK, R_OK, access, makedirs

# Globals
confile = ""
_mode = 'tx'
#servicename = ""

col_css='''
<style>
    section.main>div {
        padding-bottom: 1rem;
    }
    [data-testid="column"]>div>div>div>div>div {
        overflow: auto;
        height: 70vh;
    }
</style>
'''

# /Globals

def init():
	global confile, servicename
	confile = '/opt/dd/dd104client.ini'
	if 'servicename' not in st.session_state:
		if _mode == 'tx':
			st.session_state['servicename'] = 'dd104client'
		elif _mode == 'rx':
			st.session_state['servicename'] = 'dd104server'
	
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
		#st.text(message)
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
	

def _stop(service: str) -> dict:
	'''
	statuses are:
	0 - success, 1 - subprocess/pipe error, 2 - stderr
	
	'''
	status = {'status':'', 'errors':[]} 
	try:
		stat = subprocess.run(f'systemctl stop {service}'.split(), text=True, capture_output=True)
	except subprocess.CalledProcessError as e:
		status['status'] = 1
		status['errors'].append(e.output)
		syslog.syslog(syslog.LOG_CRIT, str(e.output))
		return status
	else:
		if not stat.stderr:
			status['status'] = 0
		else:
			status['status'] = 2
			status['errors'].append(stat.stderr)
			syslog.syslog(syslog.LOG_ERR, f"DD104: Error while stopping {service}: \n{stat.stderr}\n")
		
	return status

def _restart(service: str) -> dict:
	'''
	statuses are:
	0 - success, 1 - subprocess/pipe error, 2 - stderr
	
	'''
	status = {'status':'', 'errors':[]} 
	try:
		stat = subprocess.run(f'systemctl restart {service}'.split(), text=True, capture_output=True)
	except subprocess.CalledProcessError as e:
		status['status'] = 1
		status['errors'].append(e.output)
		syslog.syslog(syslog.LOG_CRIT, str(e.output))
		return status
	else:
		if not stat.stderr:
			status['status'] = 0
		else:
			status['status'] = 2
			status['errors'].append(stat.stderr)
			syslog.syslog(syslog.LOG_ERR, f"DD104: Error while restarting {service}: \n{stat.stderr}\n")
		
	return status

def _start(service: str) -> dict:
	'''
	statuses are:
	0 - success, 1 - subprocess/pipe error, 2 - stderr
	
	'''
	status = {'status':'', 'errors':[]} 
	try:
		stat = subprocess.run(f'systemctl start {service}'.split(), text=True, capture_output=True)
	except subprocess.CalledProcessError as e:
		status['status'] = 1
		status['errors'].append(e.output)
		syslog.syslog(syslog.LOG_CRIT, str(e.output))
		return status
	else:
		if not stat.stderr:
			status['status'] = 0
		else:
			status['status'] = 2
			status['errors'].append(stat.stderr)
			syslog.syslog(syslog.LOG_ERR, f"DD104: Error while starting {service}: \n{stat.stderr}\n")
		
	return status

def _statparse(data:str) -> dict:
	try:
		data = data.split('\n')
		output = {}
		line = data[1]
		i = 1
		while not line == '':
			line = data[i]
			if ': ' in line:
				output[line.split(': ')[0].strip(' ')] = ': '.join(line.split(': ')[1::])
			else:
				output['CGroup'] = f"{output['CGroup']}\n{line}"  
			i+=1
	except Exception as e:
		syslog.syslog(syslog.LOG_CRIT, f'DDConfServer: Error while parsing status block; more data below:\n {str(e)}\n')
		raise e
	return output



def _status(service = 'dd104client.service') -> str:
	try:
		stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
	except Exception as e:
		msg = f"dd104: can't fetch {service} status; \nDetails: {type(e)} - {str(e)}\n"
		syslog.syslog(syslog.LOG_ERR, msg)
		return None
	else:
		if stat.stderr:
			msg = f"dd104: {stat.stderr}\n"
			syslog.syslog(syslog.LOG_ERR, msg)
			return None
		else:
			try:
				data = _statparse(stat)
				if data:
					return data
				else:
					msg = f"dd104: Error: parsing {service} status yielded no result; please try collecting status again or report the bug with system logs to InControl support service.\n"
					syslog.syslog(syslog.LOG_ERR, msg)
					return None
			except Exception as e:
				syslog.syslog(syslog.LOG_CRIT, f'DDConfServer: Error while parsing status block; more data below:\n {str(e.output)}\n')
				raise e

def current_op() -> str:
	try:
		stat = _status(st.session_state['servicename'])
		if not stat:
			raise RuntimeError(f"Could not get status for {st.session_state['servicename']}.\n")
	except Exception as e:
		msg = f"dd104: can't fetch {st.session_state['servicename']} status; \nDetails: {type(e)} - {str(e)}\n"
		return msg
	else:
		if 'running' in stat['Active'] or 'failed' in stat['Active']:
			return 'restart'
		elif 'stopped' in stat['Active'] :
			return 'start'
	

#tx
def render_tx(servicename): #TODO: expand on merge with rx
	st.set_page_config(layout="wide")
	#st.markdown(col_css, unsafe_allow_html=True)
	st.title('Data Diode Configuration Service')
	st.header('Protocol 104 configuration page')
	
	data = load_from_file(confile)
	
	col1, col2, col3= st.columns([0.3, 0.18, 0.52], gap='large')
	
	col3.empty()
	with col3:
		col3.subheader(f"{servicename} status:")
		st.text(f"{_status()}")
	
	with col1:
		f = st.form("dd104form")
		if "count" not in st.session_state.dd104:
			st.session_state.dd104['count'] = data['count']
		if st.session_state.dd104['count'] > 0:
			with f:
				st.text_input(label = "Receiver Address (DON'T CHANGE UNLESS YOU KNOW WHAT YOU'RE DOING)", value = data['old_recv_addr'], key='recv_addr')
				
				for i in range(1, st.session_state.dd104['count']+1):
					st.text(f"Server {i}")
					if f'old_server_addr{i}' in data.keys():
						st.text_input(label=f'Server Address {i}', value=data[f'old_server_addr{i}'], key=f'server_addr{i}') 
						st.text_input(label=f'Server Port {i}', value=data[f'old_server_port{i}'], key=f'server_port{i}') 
					else:
						st.text_input(label=f'Server Address {i}', key=f'server_addr{i}') 
						st.text_input(label=f'Server Port {i}', key=f'server_port{i}') 
					
				submit = st.form_submit_button(label='Submit')
		
		with col2:
			adder = st.button("Add Server", use_container_width=True)
			stop = st.button(f"Stop {servicename}", use_container_width=True)
			start = st.button(f"Start {servicename}", use_container_width=True)
			restart = st.button(f"Restart {servicename}", use_container_width=True)
		
		if adder:
			
			st.session_state.dd104['count'] += 1
			
			with f:
				st.text_input(label=f"Server Address {st.session_state.dd104['count']}", key=f"server_addr{st.session_state.dd104['count']}")
				st.text_input(label=f"Server Port {st.session_state.dd104['count']}", key=f"server_port{st.session_state.dd104['count']}")
		
		
		
		if submit:
			col3.empty()
			try:
				sanitize()
			except Exception as e:
				msg = f"DD104: Failed to sanitize the form's contents; Error info: \n{type(e)}: {str(e)}\n"
				syslog.syslog(syslog.LOG_CRIT, msg)
				col3.text(msg)
			else:
				try:
					with col3:
						#st.text(st.session_state)
						save_to_file(parse_from_user(st.session_state.dd104))
				except Exception as e:
					col3.empty()
					msg = f"DD104: Failed to write the form's contents to the configuration file; Error info: \n{type(e)}: {str(e)}\n"
					syslog.syslog(syslog.LOG_CRIT, msg)
					col3.header("Error")
					col3.text(msg)
				else:
					operation = current_op()
					col3.empty()
					with col3:
						if operation and len(operation) > 10: #if error, basically
							st.text(operation)
						else:
							st.text(f"For the service to function properly, a manual {operation} is required.")
						collapse = st.button("OK")
						
					if collapse:
						col3.empty()
						with col3:
							st.text(_status())
	
	if stop:
		if not '.service' in servicename:
			servicename = servicename + '.service'
		status = _stop(servicename)
		if status['status']:
			with col3:
				st.header("Oops, an error has occurred")
				st.subheader('Details:')
				st.text(f"status: {status['status']}, \ndescription: \n{status['errors']}")
		else:
			col3.text(f"{servicename} was stopped succesfully!")
	
	if restart:
		if not '.service' in servicename:
			servicename = servicename + '.service'
		status = _restart(servicename)
		if status['status']:
			with col3:
				st.header("Oops, an error has occurred")
				st.subheader('Details:')
				st.text(f"status: {status['status']}, \ndescription: \n{status['errors']}")
		else:
			col3.text(f"{servicename} was restarted succesfully!")
	
	if start:
		if not '.service' in servicename:
			servicename = servicename + '.service'
		status = _start(servicename)
		if status['status']:
			with col3:
				st.header("Oops, an error has occurred")
				st.subheader('Details:')
				st.text(f"status: {status['status']}, \ndescription: \n{status['errors']}")
		else:
			col3.text(f"{servicename} was started succesfully!")
	

def render_rx(servicename):
	pass

def render():
	servicename = st.session_state['servicename']
	mode = _mode.lower()
	if mode == 'tx':
		render_tx(servicename)
	elif mode == 'rx':
		render_rx(servicename)


init()
render()
