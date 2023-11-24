import streamlit as st
import pandas as pd
from streamlit_modal import Modal

import syslog, subprocess, time, tarfile
from shutil import move, copy2, unpack_archive, make_archive
from pathlib import Path
from os.path import exists, sep
from os import W_OK, R_OK, access, makedirs

# Globals
confile = ""
_mode = 'tx'

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

#Logic

def init():
	global confile
	
	st.set_page_config(layout="wide")
	
	
	confile = '/opt/dd/dd104client.ini'
	
	if 'dd104' not in st.session_state.keys():
		st.session_state['dd104'] = {}
	
	if 'servicename' not in st.session_state.dd104:
		if _mode == 'tx':
			st.session_state.dd104['servicename'] = 'dd104client'
		elif _mode == 'rx':
			st.session_state.dd104['servicename'] = 'dd104server'
	

def _archive(filepath:str, location=f'/opt/dd/dd104/') -> None:
	if exists(filepath):
		try:
			filename = filepath.split('/')[-1].split('.')
			rtime = time.localtime(time.time())
			utime = f"{rtime.tm_mday}-{rtime.tm_mon}-{rtime.tm_year}-{rtime.tm_hour}-{rtime.tm_min}-{rtime.tm_sec}"
			copy2(filepath, f"/tmp/{filename[0]}-{utime}.{filename[1]}")
			filepath = f"/tmp/{filename[0]}-{utime}.{filename[1]}"
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f"dd104: провал при создании временного файла конфигурации, операция не может быть продолжена.")
			raise e
		try:
			if not exists(location+'Archive.tar.gz'):
				stat = make_archive(base_name=location+'Archive', format='gztar', root_dir=filename)
			else:
				#unarchive to /tmp/Arc104, add file, repackage
				# stat = subprocess.run(f"rm -rf /tmp/Arc104-{utime}".split())
				if not (Path(f'/tmp/Arc104-{utime}').exists() and Path(f'/tmp/Arc104-{utime}').is_dir()):
					makedirs(f'/tmp/Arc104-{utime}')
				unpack_archive(location+'Archive.tar.gz', f'/tmp/Arc104-{utime}/', 'gztar')
				move(filepath, f'/tmp/Arc104-{utime}/')
				stat = make_archive(base_name=location+'Archive', format='gztar', root_dir=f'/tmp/Arc104-{utime}/')
				stat = subprocess.run(f"rm -rf /tmp/Arc104-{utime}".split())
				stat = subprocess.run(f"rm -rf {filepath}".split())
				del(stat)
				syslog.syslog(syslog.LOG_INFO, f"dd104: {location}/Archive.tar.gz был успешно упакован!")
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f"dd104: Ошибка при обработке архива конфигураций, операция не может быть продолжена.")
			raise e

def load_from_file(_path=confile) -> dict:
	mode = _mode.lower()
	try:
		lines = [ x.strip() for x in Path(_path).read_text().split('\n') if not x == '']
	except FileNotFoundError:
		return {'count':-1}
	
	data = {} # {'count':N, 'mode':mode, 'old_..._...1':..., ...}
	block = 0
	for line in lines:
		if line[0]=='#' and 'savename' in line:
			data['old_savename'] = line.strip().split(': ')[1]
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

def _save_to_file(string:str, name='unnamed_file_version') -> None:
	with Path(confile).open("w") as f:
		f.write(f"# Файл сгенерирован Сервисом Конфигурации Диода Данных;\n# savename: {name if name else 'unnamed_file_version'}\n")
		f.write(string)
	

def sanitize():
	#move stuff from st.session_state to st.<...>.dd104
	for k,v in st.session_state.items():
		if ('server_addr' in k or 'server_port' in k or 'recv_addr' in k or 'servicename' in k or 'savename' in k):
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
			syslog.syslog(syslog.LOG_ERR, f"dd104: Ошибка при остановке {service}: \n{stat.stderr}\n")
		
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
			syslog.syslog(syslog.LOG_ERR, f"dd104: Ошибка при перезапуске {service}: \n{stat.stderr}\n")
		
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
			syslog.syslog(syslog.LOG_ERR, f"dd104: Ошибка при запуске {service}: \n{stat.stderr}\n")
		
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
		syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e)}\n')
		raise e
	return output



def _status(service = 'dd104client.service') -> str:
	try:
		stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
	except Exception as e:
		msg = f"dd104: невозможно получить статус {service}; \nПодробности: {type(e)} - {str(e)}\n"
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
					msg = f"dd104: Ошибка: Парсинг статуса {service} передал пустой результат; Если эта ошибка повторяется, напишите в сервис поддержки ООО InControl.\n"
					syslog.syslog(syslog.LOG_ERR, msg)
					return None
			except Exception as e:
				syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e.output)}\n')
				raise e

def current_op() -> str:
	try:
		stat = _status(st.session_state.dd104['servicename'])
		if not stat:
			raise RuntimeError(f"Провал при получении статуса сервиса {st.session_state.dd104['servicename']}.\n")
	except Exception as e:
		msg = f"dd104: не удалось получить статус {st.session_state.dd104['servicename']}; \nПодробности: \n{type(e)}: {str(e)}\n"
		return msg
	else:
		if 'running' in stat['Active'] or 'failed' in stat['Active']:
			return 'перезапуск'
		elif 'stopped' in stat['Active'] :
			return 'запуск'
	

#/Logic

#Render

def render_tx(servicename): #TODO: expand on merge with rx
	
	#st.markdown(col_css, unsafe_allow_html=True)
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Страница конфигурации протокола DD104')
	exp = st.expander("Доступные конфигурации", False)
	
	data = load_from_file(confile)
	
	col1, col2, col3= st.columns([0.3, 0.23, 0.47], gap='large')
	
	col3.empty()
	with col3:
		col3.subheader(f"Статус {servicename}:")
		st.text(f"{_status()}")
	
	
	with col1:
		f = st.form("dd104form")
		
		if "count" not in st.session_state.dd104:
			st.session_state.dd104['count'] = data['count']
		if st.session_state.dd104['count'] > 0:
			with f:
				st.text_input(label = "Имя версии конфигурации", value=data['old_savename'] if 'old_savename' in data.keys() else "", key='savename')
				st.text_input(label = "Адрес получателя (НЕ ИЗМЕНЯТЬ БЕЗ ИЗМЕНЕНИЙ АДРЕСАЦИИ ДИОДНОГО СОЕДИНЕНИЯ)", value = data['old_recv_addr'], key='recv_addr')
				
				for i in range(1, st.session_state.dd104['count']+1):
					st.text(f"Сервер {i}")
					if f'old_server_addr{i}' in data.keys():
						st.text_input(label=f'Адрес Сервера {i}', value=data[f'old_server_addr{i}'], key=f'server_addr{i}') 
						st.text_input(label=f'Порт Сервера {i}', value=data[f'old_server_port{i}'], key=f'server_port{i}') 
					else:
						st.text_input(label=f'Адрес Сервера {i}', key=f'server_addr{i}') 
						st.text_input(label=f'Порт Сервера {i}', key=f'server_port{i}') 
					
				submit = st.form_submit_button(label='Сохранить')
		
		with col2:
			adder = st.button("Добавить Сервер", use_container_width=True)
			stop = st.button(f"Остановить {servicename}", use_container_width=True)
			start = st.button(f"Запустить {servicename}", use_container_width=True)
			restart = st.button(f"Перезапустить {servicename}", use_container_width=True)
		
		if adder:
			
			st.session_state.dd104['count'] += 1
			
			with f:
				st.text_input(label=f"Адрес Сервера {st.session_state.dd104['count']}", key=f"server_addr{st.session_state.dd104['count']}")
				st.text_input(label=f"Порт Сервера {st.session_state.dd104['count']}", key=f"server_port{st.session_state.dd104['count']}")
		
		
		
		if submit:
			col3.empty()
			
			try:
				sanitize()
			except Exception as e:
				msg = f"dd104: Провал обработки данных формы,\nПодробности: \n{type(e)}: {str(e)}\n"
				syslog.syslog(syslog.LOG_CRIT, msg)
				col3.text(msg)
			else:
				try:
					with col3:
						col3.write(st.session_state)
						#st.text(st.session_state)
						_save_to_file(parse_from_user(st.session_state.dd104), st.session_state.dd104['savename'])
						_archive(confile)
						
				except Exception as e:
					col3.empty()
					msg = f"dd104: Не удалось сохранить данные формы в файл конфигурации,\nПодробности:\n{type(e)}: {str(e)}\n"
					syslog.syslog(syslog.LOG_CRIT, msg)
					col3.header("Ошибка!")
					col3.text(msg)
				else:
					operation = current_op()
					col3.empty()
					with col3:
						if operation and len(operation) > 10: #if error, basically
							st.text(operation)
						else:
							st.text(f"Для корректной работы сервиса необходим {operation}.")
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
				st.header("Ошибка!")
				st.subheader('Подробности:')
				st.text(f"status: {status['status']}, \ndescription: \n{status['errors']}")
		else:
			col3.text(f"{servicename} был успешно остановлен!")
	
	if restart:
		if not '.service' in servicename:
			servicename = servicename + '.service'
		status = _restart(servicename)
		if status['status']:
			with col3:
				st.header("Ошибка!")
				st.subheader('Подробности:')
				st.text(f"status: {status['status']}, \ndescription: \n{status['errors']}")
		else:
			col3.text(f"{servicename} был успешно перезапущен!")
	
	if start:
		if not '.service' in servicename:
			servicename = servicename + '.service'
		status = _start(servicename)
		if status['status']:
			with col3:
				st.header("Ошибка!")
				st.subheader('Подробности:')
				st.text(f"status: {status['status']}, \ndescription: \n{status['errors']}")
		else:
			col3.text(f"{servicename} был успешно запущен!")
	
	

	

def render_rx(servicename):
	pass

def render():
	servicename = st.session_state.dd104['servicename']
	mode = _mode.lower()
	if mode == 'tx':
		render_tx(servicename)
	elif mode == 'rx':
		render_rx(servicename)

#/Render

init()
render()
