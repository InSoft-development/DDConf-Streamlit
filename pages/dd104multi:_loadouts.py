 
import streamlit as st



import syslog, subprocess, time, tarfile
from shutil import move, copy2, unpack_archive, make_archive
from pathlib import Path
from os.path import exists, sep, isdir, isfile, join
from os import W_OK, R_OK, access, makedirs, listdir

# Globals
_mode = 'tx'
INIDIR = '/etc/dd/dd104/configs/'
ARCDIR = '/etc/dd/dd104/archive.d/'
LOADOUTDIR = '/etc/dd/dd104/loadouts.d/'
INIT_KEYS = ['servicename', 'inidir', 'selected_file']
# /Globals

#Logic

def init():
	
	st.set_page_config(layout="wide")
	
	
	if 'dd104L' not in st.session_state.keys():
		st.session_state['dd104L'] = {}
	
	if 'servicename' not in st.session_state.dd104L.keys():
		if _mode == 'tx':
			st.session_state.dd104L['servicename'] = 'dd104client'
		elif _mode == 'rx':
			st.session_state.dd104L['servicename'] = 'dd104server'
	
	if 'inidir' not in st.session_state.dd104L.keys():
		st.session_state.dd104L['inidir'] = INIDIR
	
	if 'loaddir' not in st.session_state.dd104L.keys():
		st.session_state.dd104L['loaddir'] = LOADOUTDIR
	
	if 'arcdir' not in st.session_state.dd104L.keys():
		st.session_state.dd104L['arcdir'] = ARCDIR
	
	if 'contents' not in st.session_state.dd104L.keys():
		st.session_state.dd104L['contents'] = {}
	
	# if 'selected_ld' not in st.session_state.dd104L.keys():
	# 	st.session_state.dd104L['selected_ld'] = ''


# class Loadout:
# 	
# 	_name = ''
# 	contents = {}
# 	_valid = False
# 	
# 	
# 	def __init__(self, name:str, confs=[]):
# 		self.validate(count, confs)
# 		for i in range(1, count+1):
# 			self.contents[f'process_{i}'] = {'confile': confs}
# 	
# 	def validate(self, count: int, confs: list):
# 		if not len(confs):
# 			self._valid = False
# 		else:
# 			self._valid = True
# 	
# 	def isvalid(self):
# 		return self._valid
# 	
# 	def __str__(self):
# 		return f"{{ {self._name}:  {self.contents} }} "
	



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




#TODO 
def _create_services(num:int) -> str: 
	path_to_sysd = '/etc/systemd/system/'
	default_service = Path('/opt/dd/ddconfserver/dd104client.service.default')
	if not default_service.parent.is_dir() or not default_service.is_file():
		msg = f"dd104: Файл сервиса {default_service} недоступен!"
		syslog.syslog(syslog.LOG_ERR, msg)
		raise FileNotFoundError(msg)
	else:
		
		for i in range(1, num+1):
			try:
				#
				#Copy the default to the system dir
				#
				copy2(default_service, Path(path_to_sysd/f"dd104client{i if i > 1 else ''}.service"))
				#copy2('/opt/dd/dd104client.ini', f'/opt/dd/dd104client{i if i > 1 else ""}.ini')
				#
				#Edit the resulting file
				#
				# read & edit
				with Path(path_to_sysd/f"dd104client{i if i > 1 else ''}.service").open("rw") as f:
					conf = f.read.split('\n')[:-1:]
					for n in range(len(conf)):
						if 'ExecStart=' in conf[n]:
							conf[n] = f"ExecStart=/opt/dd/dd104client/dd104client -c /etc/dd/dd104client{i if i > 1 else ''}.ini"
							break
					f.close()
				# write
				with Path(path_to_sysd/f"dd104client{i if i > 1 else ''}.service").open("w") as f:
					conf = '\n'.join(conf)
					f.write(conf)
					f.close()
			except Exception as e:
				syslog.syslog(syslog.LOG_CRIT, f"dd104: Ошибка при создании файла сервиса dd104client{i if i > 1 else ''}, подробности:\n {str(e)}\n")
				raise e
		return "Успех"


def _delete_services(target='all'): #deletes all services dd104client*.service, for now
	if target == 'all':
		try:
			stat = subprocess.run('rm -f /etc/systemd/system/dd104client*.service'.split(), capture_output=True, text=True)
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при уничтожении файлов сервисов dd104client, подробности:\n {str(e)}\n')
			raise e
	else:
		try:
			stat = subprocess.run(f'rm -f /etc/systemd/system/{target}'.split(), capture_output=True, text=True)
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при уничтожении файлов сервисов dd104client, подробности:\n {str(e)}\n')
			raise e


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


	

def list_sources(_dir=INIDIR) -> list: #returns a list of dicts like {'savename':'', 'savetime':'', 'filename':''}
	_dir = Path(_dir)
	if not _dir.is_dir():
		msg = f"dd104L: Директория сервиса {_dir} недоступна!"
		syslog.syslog(syslog.LOG_ERR, msg)
		raise FileNotFoundError(msg)
	L = [x for x in listdir(_dir) if (_dir/x).is_file() and ''.join(x[-3::]) == 'ini']
	out = []
	for f in L:
		try:
			with (_dir/f).open('r') as F:
				savetime = ''
				savename = ''
				for line in F.read().split('\n'):
					if 'savetime: ' in line and line.strip()[0] == '#':
						savetime = line.strip().split(': ')[1]
					if 'savename: ' in line and line.strip()[0] == '#':
						savename = line.strip().split(': ')[1]
						# break
				out.append({'savename':savename, 'savetime':savetime, 'filename':str(_dir/f)})
				
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104Loadouts: Ошибка: Файл конфигурации {_dir/f} недоступен, подробности:\n {str(e)}\n')
			raise e
	return out
	

def list_loadouts(_dir=INIDIR) -> list: #returns a list of dicts like {'name':'', 'fcount':len([]), 'files':['','']}
	_dir = Path(_dir)
	if not _dir.is_dir():
		msg = f"dd104L: Директория сервиса {_dir} недоступна!"
		syslog.syslog(syslog.LOG_ERR, msg)
		raise FileNotFoundError(msg)
	L = [x for x in listdir(_dir) if (_dir/x).is_dir()]
	out = []
	for f in L:
		try:
			files = [x for x in listdir(_dir/f) if isfile(join(_dir/f, x))]
			
			out.append({'name':f, 'fcount':len(files), 'files':files})
		
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104Loadouts: Ошибка при перечислении файлов директории {_dir}, подробности:\n {str(e)}\n')
			raise e
	return out

def dict_cleanup(array: dict, to_be_saved=[]):
	dead_keys=[]
	for k in array.keys():
		if k not in to_be_saved:
			dead_keys.append(k)
	for k in dead_keys:
		del(array[k])

#TODO
def save_loadout(out:st.empty):
	out.empty()
	

def _add_process(box:st.empty, out:st.empty):
	out.empty()
	box.empty()
	out.write(st.session_state)
	if 'fcount' in st.session_state.dd104L['selected_ld']:
		st.session_state.dd104L['selected_ld']['fcount'] += 1
	
	

#/Logic

#Render


def _create_form(loadout:dict, box:st.empty, out:st.empty):
	box.empty()
	out.empty()
	out.write(st.session_state)
	
	with box:
		archived = list_sources(st.session_state.dd104L['arcdir'])
		
		_form = st.form('dd104L-form')
		for i in range(0, loadout['fcount']+1):
			with _form:
				with st.container():
					col1, col2 = st.columns([0.6, 0.4])
					col1.caption(f'Процесс {i+1}')
					col2.caption(f'Тут будет статус процесса {i+1}')
					st.selectbox(label='Файл настроек', options=[f"{x['savename']}@{x['savetime']} ({x['filename']})" for x in archived], index=None, key=f"select_file_{i}")
					
			# with st.columns(3, gap='small') as c1, c2, c3:
			# 	c1.button('Остановить процесс', on_click=_stop, kwargs={'out':out, 'service':f"dd104client{i+1}" if _mode.lower() == 'tx' else f"dd104server{i+1}"}, key=f'stopper{i+1}')
			# 	c2.button('Перезапустить процесс', on_click=_restart, kwargs={'out':out, 'service':f"dd104client{i+1}" if _mode.lower() == 'tx' else f"dd104server{i+1}"}, key=f'restarter{i+1}')
			# 	c3.button('Запустить процесс', on_click=_start, kwargs={'out':out, 'service':f"dd104client{i+1}" if _mode.lower() == 'tx' else f"dd104server{i+1}"}, key=f'starter{i+1}')
		
		_form.form_submit_button('Сохранить Конфигурацию', on_click=save_loadout, kwargs={'out':out})
		
		
					
			
			


def render_tx(servicename): #TODO: expand on merge with rx
	
	#st.markdown(col_css, unsafe_allow_html=True)
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Редактор файла конфигурации протокола DD104')
	
	ld, bt, cf, outs = st.columns([0.25, 0.15, 0.3, 0.3], gap='small')
	
	#archived = list_sources(st.session_state.dd104L['arcdir'])
	loadouts = list_loadouts(st.session_state.dd104L['loaddir']) # [{'name':'', 'fcount':''}, {}]
	st.session_state.dd104L['names'] = [x['name'] for x in loadouts if x and 'name' in x]
	
	#containers
	ld.subheader('Конфигурации')
	bt.subheader('Операции')
	cf.subheader('Настройка Конфигурации')
	outs.subheader('Вывод')
	
	out = outs.empty()
	out.write(st.session_state)
	
	formbox = cf.empty()
	
	if st.session_state.dd104L['names']:
		loadouter = ld.container(height=600)
	
	buttons = bt.container(height=600)
	
	#filling
	for i in loadouts:
		if loadouter.button(f"{i['name']}"):
			st.session_state.dd104L['selected_ld'] = i
			
	
	if 'selected_ld' in st.session_state.dd104L and st.session_state.dd104L['selected_ld']:
		_create_form(st.session_state.dd104L['selected_ld'], formbox, out)
	
	with buttons:
		stop = st.button('Остановить все процессы', use_container_width=True, on_click=_stop, kwargs={'out':out, 'service':'all'})
		start = st.button('Запустить все процессы', use_container_width=True, on_click=_start, kwargs={'out':out, 'service':'all'})
		restart = st.button('Перезапустить все процессы', use_container_width=True, on_click=_restart, kwargs={'out':out, 'service':'all'})
		add = st.button('Добавить процесс', disabled=True if not 'selected_ld' in st.session_state.dd104L else False, use_container_width=True, on_click=_add_process, kwargs={'out':out, 'box':formbox})
	
	if loadouter.button(f"Новая Конфигурация"):
		newlbox = loadouter.empty()
		with newlbox.container():
			_form = st.form('newloadoutform')
			with _form:
				st.text_input(label='Имя конфигурации', key='new_loadout_name')
				submit = st.form_submit_button('Создать', on_click=_new_loadout)

def render_rx(servicename):
	pass

def render():
	servicename = st.session_state.dd104L['servicename']
	mode = _mode.lower()
	if mode == 'tx':
		render_tx(servicename)
	elif mode == 'rx':
		render_rx(servicename)

#/Render

init()
render()
 
