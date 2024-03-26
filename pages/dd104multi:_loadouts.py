import streamlit as st

import syslog, subprocess, time, tarfile
from shutil import move, copy2, unpack_archive, make_archive
from pathlib import Path
from os.path import exists, sep, isdir, isfile, join
from os import W_OK, R_OK, access, makedirs, listdir

# ---------Notes:---------
#  
# the server assumes that the first dd104<>.service process  
# is called dd104<>1.service! 
#  
# ---------/Notes---------

# Globals
_mode = 'tx'
INIDIR = '/etc/dd/dd104/configs/'
ARCDIR = '/etc/dd/dd104/archive.d/'
LOADOUTDIR = '/etc/dd/dd104/loadouts.d/'
INIT_KEYS = ['servicename', 'inidir', 'selected_file']
# /Globals

#Logic

# this line was in init(), but streamlit started fussing up about it being called more than once all of a sudden
st.set_page_config(layout="wide")

def init():
	
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
	
	if 'newlbox-flag' not in st.session_state.dd104L.keys():
		st.session_state.dd104L['newfbox-flag'] = False
	
	if 'editor-flag' not in st.session_state.dd104L.keys():
		st.session_state.dd104L['editor-flag'] = False




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
			# else:
			# 	output['CGroup'] = f"{output['CGroup']}\n{line}"  
			i+=1
	except Exception as e:
		syslog.syslog(syslog.LOG_CRIT, f'dd104L: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e)}\n')
		raise e
	return output


def _status(num = 1) -> str:
	if num>=1:
		service = f"dd104client{num}.service" if _mode == 'tx' else f"dd104server{num}.service"
	else:
		raise RuntimeError("dd104L: номер процесса за границей области допустимых значений!")
	
	try:
		stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
	except Exception as e:
		msg = f"dd104L: невозможно получить статус {service}; \nПодробности: {type(e)} - {str(e)}\n"
		syslog.syslog(syslog.LOG_ERR, msg)
		return f"🔴"
	else:
		if stat.stderr:
			msg = f"dd104L: {stat.stderr}\n"
			syslog.syslog(syslog.LOG_ERR, msg)
			return f"🔴"
		else:
			try:
				data = _statparse(stat.stdout)
				if data:
					if ("stopped" in data['Active'].lower() or 'dead' in data['Active'].lower()) and not 'failed' in data['Active'].lower():
						return "⚫"
					elif 'failed' in data['Active'].lower():
						return f"🔴"
					elif "running" in data['Active'].lower():
						return f"🟢"
					else:
						raise RuntimeError(data)
				else:
					msg = f"dd104L: Ошибка: Парсинг статуса {service} передал пустой результат; Если эта ошибка повторяется, напишите в сервис поддержки ООО InControl.\n"
					syslog.syslog(syslog.LOG_ERR, msg)
					return f"🔴"
			except Exception as e:
				syslog.syslog(syslog.LOG_CRIT, f'dd104L: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e)}\n')
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

def sanitize():
	try:
		st.session_state.dd104L['selected_ld']['selectors'] = {k:v for k,v in st.session_state.items() if 'select_file_' in k}
		for k in st.session_state.dd104L['selected_ld']['selectors'].keys():
			del(st.session_state[k])
	except Exception as e:
		msg = f"dd104L: Критическая ошибка: невозможно обработать данные сессии, подробности:\n{str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		return msg
	return st.session_state

#TODO symlink problems
def save_loadout(out:st.empty):
	out.empty()
	out.write(sanitize())
	print(st.session_state)
	ld = Path(st.session_state.dd104L['loaddir']) / st.session_state.dd104L['selected_ld']['name']
	if not ld.is_dir():
		try:
			makedirs(ld)
		except Exception as e:
			msg = f"dd104L: Критическая ошибка: директория {ld.parent} недоступна для записи, подробности:\n{str(e)}"
			syslog.syslog(syslog.LOG_CRIT, msg)
			raise e
		
	try:
		
		# this bitch doesn't work
		# stat = subprocess.run(f'rm -rf {ld}/*'.split(), text=True, capture_output=True)
		
		for f in listdir(ld):
			print(f"deleting {str(ld/f)}")
			(ld/f).unlink()
		
	except Exception as e:
		msg = f"dd104L: Критическая ошибка: не удалось очистить директорию {ld}, подробности:\n{str(e)}"
		print(msg)
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e
		
	for i in range(1, len(st.session_state.dd104L['selected_ld']['selectors'])+1):
		filepath = Path(st.session_state.dd104L['arcdir']) / st.session_state.dd104L['selected_ld']['selectors'][f'select_file_{i}'].split('(')[-1][:-1:]
		
		if filepath.is_file():
			try:
				(ld/f"dd104client{i}.ini").symlink_to(filepath)
				print(f'\nfile {(ld/(f"dd104client{i}.ini" if i>1 else "dd104client.ini"))} was created!')
			except Exception as e:
				msg = f"dd104L: Критическая ошибка: не удалось создать ссылку на файл {filepath} в директории {ld}, подробности:\n{str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				raise e
		else:
			msg = f"dd104L: Критическая ошибка: файл {filepath} не найден!"
			syslog.syslog(syslog.LOG_CRIT, msg)
			raise FileNotFoundError(msg)
		
	

def _add_process(box:st.empty, out:st.empty):
	out.empty()
	box.empty()
	out.write(st.session_state)
	if 'fcount' in st.session_state.dd104L['selected_ld']:
		st.session_state.dd104L['selected_ld']['fcount'] += 1
	
	

def list_ld(name: str): #returns the dict of files from the archive that are symlinked to from the loadout dir 
	if not '/' in name:
		ldpath = Path(st.session_state.dd104L['loaddir'])/name
	else:
		ldpath = Path(name)
	
	files = {}
	
	for i in listdir(ldpath):
		if (ldpath/i).is_symlink():
			if i == 'dd104client.ini' or i == 'dd104server.ini':
				files[1] = str((ldpath/i).resolve())
			elif 'dd104client' in i or 'dd104server' in i:
				files[int(i[-5])] = str((ldpath/i).resolve())
			
	
	return files

def _new_loadout():
	if 'new_loadout_name' in st.session_state:
		loadname = Path(st.session_state.dd104L['loaddir'])/st.session_state['new_loadout_name']
	else:
		raise RuntimeError('_new_loadout: session state key "new_loadout_name" not found!')
	
	if isdir(loadname):
		msg = f"dd104L: Директория {loadname} уже существует!"
		syslog.syslog(syslog.LOG_WARNING, msg)
		raise FileExistsError(msg)
	try:
		loadname.mkdir(parents=True, exist_ok=False)
		print(f"directory {loadname} was created!")
	except Exception as e:
		msg = f"dd104L: Ошибка при создании директории {loadname}, подробности:\n{str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e

def _apply_process_ops(out: st.empty):
	out.empty()
	out.write(st.session_state)
	if st.session_state.oplist_select == 'Перезапустить':
		operation = 'restart'
	elif st.session_state.oplist_select == 'Остановить':
		operation = 'stop'
	else:
		operation = 'start'
	
	tgts = [x.split(':')[0] for x in st.session_state.proclist_select if ':' in x]
	
	#print(f"tgts: {tgts}")
	
	errs = []
	
	for tgt in tgts:
		try:
			a = subprocess.run(f'systemctl {operation} dd104client{tgt}.service'.split(), text=True, capture_output=True)
			if a.stderr:
				msg = f"{a.stderr}"
				errs.append(f"dd104client{tgt}.service")
				raise RuntimeError(msg)
		except Exception as e:
			msg = f"dd104L: Ошибка выполнения операции над процессом dd104client{tgt}.service:\n{str(e)}"
			print(msg)
			syslog.syslog(syslog.LOG_CRIT, msg)
			#raise RuntimeError(msg)
		
	
	with out.container():
		st.write("Успех!" if not errs else f"Во время выполнения операции {st.session_state.oplist_select} над процессом(-ами) {errs} произошли ошибки. Операции не были применены к этим процессам либо были произведены безуспешно.")
		if st.button("OK"):
			out.empty()



def get_active(LDIR:str) -> str: 
	try:
		LDIR=Path(LDIR)
		if not LDIR.is_dir():
			raise RuntimeError(f"Директория {LDIR} недоступна!")
	except Exception as e:
		msg = f"dd104L: Ошибка при получении текущей активной конфигурации, подробности:\n{str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e
	else:
		if '.ACTIVE' in listdir(LDIR) and (LDIR/'.ACTIVE').is_symlink():
			try:
				return (LDIR/'.ACTIVE').resolve().name
			except Exception as e:
				msg = f"dd104L: Ошибка чтения указателя активной конфигурации, подробности:\n{str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				raise e
		else:
			return None 



def _edit_svc(path:str): #possible problems: num is anything that comes between dd104<> and .
	
	path = Path(path)
	num = path.name().split('.')[0].split(st.session_state.dd104L['servicename'])[1]
	text = path.read_text().split('\n')
	for i in range(0, len(text)):
		if 'ExecStart=' in text[i] and text[i].strip()[0] != '#':
			text[i] = f"ExecStart=/opt/dd/{st.session_state.dd104L['servicename']}/{st.session_state.dd104L['servicename']} -c {st.session_state.dd104L['loaddir']}{st.session_state.dd104L['servicename']}{num}.service"
			break
	a = path.write_text('\n'.join(text))
	


def processify() -> dict: 
	#TODO returns {'errors':[], 'failed':[]}
	# stops all related processes, deletes their files, copies the default files over them, 
	# edits them to fit in the config file, returns the status of the whole ordeal
	#
	errors = []
	failed = []
	
	#stop all dd104 services
	try:
		stat = subprocess.run("systemctl stop dd104*.service".split(), capture_output=True, text=True)
		if stat.stderr:
			# failed.append("systemctl stop dd104*.service")
			# errors.append(stat.stderr)
			raise RuntimeError(stat.stderr)
	except Exception as e:
		msg = f"dd104L: Ошибка при остановке процессов, подробности:\n{str(e)}"
		raise RuntimeError(msg)
	else:
		#delete
		services = [x for x in listdir('/etc/systemd/system/') if st.session_state.dd104L['servicename'] in x]
		for s in services:
			try:
				(Path('/etc/systemd/system/')/s).unlink()
			except Exception as e:
				failed.append(s)
				errors.append(str(e))
		#copy
		for i in range(1, st.session_state.dd104L['activator_selected_ld']['fcount']+1):
			try:
				copy2(f"/etc/dd/dd104/{st.session_state.dd104L['servicename']}.service.default", f"/etc/systemd/system/{st.session_state.dd104L['servicename']}{i}.service")
			except Exception as e:
				msg = f"dd104L: Ошибка при создании файлов сервиса, подробности:\n{str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				errors.append(str(e))
				failed.append(f"dd104client{i}.service")
			else:
				try:
					_edit_svc(f"/etc/systemd/system/{st.session_state.dd104L['servicename']}{i}.service")
				except Exception as e:
					msg = f"dd104L: Ошибка при редактировании файлов сервиса, подробности:\n{str(e)}"
					syslog.syslog(syslog.LOG_CRIT, msg)
					errors.append(str(e))
					failed.append(f"{st.session_state.dd104L['servicename']}{i}.service")
				else:
					try:
						stat = subprocess.run(f"systemctl daemon-reload".split(), capture_output=True, text=True)
						if stat.stderr:
							raise RuntimeError(stat.stderr)
					except Exception as e:
						msg = f"dd104L: Ошибка при перезагрузке демонов systemctl, подробности:\n{str(e)}"
						syslog.syslog(syslog.LOG_CRIT, msg)
						errors.append(str(e))
						failed.append(f"systemctl daemon-reload")
	
	
	return {'errors':errors, 'failed':failed}

def activate_ld(name:str, out:st.empty()): #TODO
	out.empty()
	try:
		loadout = Path(st.session_state.dd104L['loaddir'])/name
		if '.ACTIVE' in listdir(loadout.parent):
			(loadout.parent/'.ACTIVE').unlink()
		(loadout.parent/'.ACTIVE').symlink_to(loadout, target_is_directory=True)
		
		results = processify()
		if not results['errors']:
			msg = f"dd104L: Конфигурация {name} успешно активирована!"
			syslog.syslog(syslog.LOG_INFO, msg)
			out.write(msg)
		else:
			msg = f"dd104L: При обработке процессов {results['failed']} произошла(-и) ошибка(-и): \n{results['errors']}"
			syslog.syslog(syslog.LOG_ERR, msg)
			out.write(msg)
		
	except Exception as e:
		msg = f"dd104L: Ошибка при активации конфигурации, подробности:\n{str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		out.write(msg)
		raise e

#/Logic

#Render

def close_box(box:st.empty, bname='editor'):
	box.empty()
	st.session_state.dd104L[f'{bname}-flag'] = False

def _create_form(loadout:dict, box:st.empty, out:st.empty):
	box.empty()
	out.empty()
	out.write(st.session_state)
	
	if st.session_state.dd104L['editor-flag']:
		with box:
			archived = list_sources(st.session_state.dd104L['arcdir'])
			
			_form = st.form('dd104L-form')
			files = [f"{x['savename']} ({x['savetime']}) ({x['filename']})" for x in archived]
			loadouted = [f"{x['savename']} ({x['savetime']}) ({x['filename']})" for x in archived if x['filename'] in list_ld(loadout['name']).values()]
			
			out.write(loadouted)
			
			if loadout['fcount'] <= 0:
				with _form:
						with st.container():
							
							col1, col2 = st.columns([0.8, 0.2])
							col1.caption(f'Процесс 1')
							# col2.caption(f"Статус:  {_status(1)}", help="⚫ - процесс остановлен,\n🟢 - процесс запущен,\n🔴 - ошибка/процесс остановлен с ошибкой.")
							st.selectbox(label='Файл настроек', options=files, index=None, key=f"select_file_1")
			else:
				for i in range(1, loadout['fcount']+1):
					with _form:
						with st.container():
							
							col1, col2 = st.columns([0.8, 0.2])
							col1.caption(f'Процесс {i}')
							# col2.caption(f"Статус:  {_status(i)}", help="⚫ - процесс остановлен,\n🟢 - процесс запущен,\n🔴 - ошибка/процесс остановлен с ошибкой.")
							st.selectbox(label='Файл настроек', options=files, index=files.index(loadouted[i-1]) if i<=len(loadouted) else None, key=f"select_file_{i}")
						
				
			
			_form.form_submit_button('Сохранить Конфигурацию', on_click=save_loadout, kwargs={'out':out})
		



def render_tx(servicename): #TODO: expand on merge with rx
	
	#archived = list_sources(st.session_state.dd104L['arcdir'])
	loadouts = list_loadouts(st.session_state.dd104L['loaddir']) # [{'name':'', 'fcount':'', 'files':[]}, {}]
	st.session_state.dd104L['names'] = [x['name'] for x in loadouts if x and 'name' in x]
	
	_index = get_active(st.session_state.dd104L['loaddir'])
	
	if _index:
		for l in loadouts:
			if l['name'] == _index:
				st.session_state.dd104L['active_ld'] = l
	else:
		st.session_state.dd104L['active_ld'] = None
	
	#st.session_state.dd104L['active_ld'] = (i for i in loadouts if i['name']==_index) if _index else None
	
	#st.markdown(col_css, unsafe_allow_html=True)
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Управление конфигурациями протокола DD104')
	
	st.subheader('Выбрать конфигурацию для загрузки...')
	
# 	if 'Flag_a' not in st.session_state.dd104L:
# 		st.session_state.dd104L['Flag_a'] = False
# 	
# 	if 'Flag_b' not in st.session_state.dd104L:
# 		st.session_state.dd104L['Flag_b'] = False
	
	alpha = st.expander(label="Выбор конфигурации:")#, expanded = st.session_state.dd104L['Flag_a'] if 'Flag_a' in st.session_state.dd104L else False)
	
	with alpha:
		with st.container():
			#TODO active ld => symlink?
			
			ald, aop, ast, aouts = st.columns([0.2, 0.2, 0.3, 0.3], gap='medium')
			
			ald.subheader("Конфигурации")
			aop.subheader("Операции")
			aouts.subheader("Вывод")
			ast.subheader("Статус")
			
			astat = ast.container(height=600)
			loads = ald.container(height=600)
			procs = aop.container(height=434)
			c_load = aop.container(height=150)
			_aout = aouts.container(height=600)
			aout = _aout.empty()
			
			aout.write(st.session_state)
			
			# _processwork(astat, aout)
			
			for i in loadouts:
				if not i['name'] == '.ACTIVE':
					if loads.button(f"{i['name']}", type='primary' if i['name']==_index else "secondary", key=f"act_{i['name']}"):
						st.session_state.dd104L['activator_selected_ld'] = i
						aout.write(st.session_state)
			
			if 'activator_selected_ld' in st.session_state.dd104L:
				with c_load:
					st.button(f"Загрузить конфигурацию {st.session_state.dd104L['activator_selected_ld']['name']}", on_click=activate_ld, kwargs={'name':st.session_state.dd104L['activator_selected_ld']['name'], 'out':aout})
			
			options = [f"{i}: Процесс {i} ({list_ld(st.session_state.dd104L['active_ld']['name'])[i]})" for i in range(1, st.session_state.dd104L['active_ld']['fcount']+1)] if st.session_state.dd104L['active_ld'] else []
			
			with astat:
				if st.session_state.dd104L['active_ld']:
					if options:
						for proc in options:
							col1, col2 = st.columns([0.75, 0.25])
							col1.caption(f"Процесс {proc.split(':')[0]}")
							col2.caption(f"Статус: {_status(int(proc.split(':')[0]))}", help="⚫ - процесс остановлен,\n🟢 - процесс запущен,\n🔴 - ошибка/процесс остановлен с ошибкой.")
							st.caption('Файл настроек:')
							col1, col2 = st.columns([0.35, 0.65])
							col2.text(str((Path(st.session_state.dd104L['loaddir'])/f".ACTIVE/{st.session_state.dd104L['servicename']}{proc.split(':')[0]}.ini").resolve().name))
					else:
						with st.empty():
							st.write("Нет процессов!")
				else:
					with st.empty():
						st.write("Нет загруженной конфигурации!")
			
			
			
			with procs:
				
				def disabler():
						st.session_state.dd104L['proc_submit_disabled'] = not ('proclist_select' in st.session_state and st.session_state['proclist_select']) or not ('oplist_select' in st.session_state and st.session_state['oplist_select'])
					
				
				procselect = st.multiselect(label="Выберите процессы:", options=options, default=None, disabled=(not 'active_ld' in st.session_state.dd104L), key=f"proclist_select", placeholder="Не выбрано", on_change=disabler)
				
				opselect = st.selectbox(label="Выберите операцию:", options=["Остановить","Перезапустить","Запустить"], index=None, disabled=(not 'active_ld' in st.session_state.dd104L), key="oplist_select", placeholder="Не выбрано", on_change=disabler)
				
				
				if procs.button("Применить", disabled=st.session_state.dd104L['proc_submit_disabled'] if 'proc_submit_disabled' in st.session_state.dd104L else True):
					_apply_process_ops(aout)
			
			
			
			
			
			
	
	st.subheader('...Или')
	st.subheader('Отредактировать существующую конфигурацию:')
	beta = st.expander(label="Конфигуратор:")#, expanded = st.session_state.dd104L['Flag_b'] if 'Flag_b' in st.session_state.dd104L else False)
	
	with beta:
		ld, bt, cf, outs = st.columns([0.20, 0.20, 0.3, 0.3], gap='small')
		
		
		
		#containers
		ld.subheader('Конфигурации')
		bt.subheader('Операции')
		c3c1, c3c2 = cf.columns([0.8, 0.2])
		c3c1.subheader('Настройка Конфигурации')
		outs.subheader('Вывод')
		
		out = outs.empty()
		out.write(st.session_state)
		
		with cf.container(height=600):
			formbox = st.empty()
		
		loadouter = ld.container(height=600)
		
		ldbuttons = bt.container(height=600)
		
		#filling
		with ldbuttons:
			
			add = st.button('Добавить процесс', disabled=True if not 'selected_ld' in st.session_state.dd104L else False, use_container_width=True, on_click=_add_process, kwargs={'out':out, 'box':formbox})
		
		c1c1, c1c2 = loadouter.columns([0.8, 0.2])
		if c1c1.button(f"Новая Конфигурация"):
			st.session_state.dd104L['newlbox-flag'] = True
			newlbox = loadouter.empty()
			c1c2.button("❌", on_click=close_box, kwargs={'box':newlbox, 'bname':'newlbox'}, key='newlbox-close')
			if st.session_state.dd104L['newlbox-flag']:
				with newlbox.container():
					_form_nld = st.form('newloadoutform')
					with _form_nld:
						st.text_input(label='Имя конфигурации', key='new_loadout_name')
						submit = st.form_submit_button('Создать', on_click=_new_loadout)
		
		for i in loadouts:
			if loadouter.button(f"{i['name']}"):
				st.session_state.dd104L['selected_ld'] = i
				st.session_state.dd104L['editor-flag'] = True
				
		
		if 'selected_ld' in st.session_state.dd104L and st.session_state.dd104L['selected_ld'] and st.session_state.dd104L['editor-flag']:
			c3c2.button("❌", on_click=close_box, kwargs={'box':formbox, 'bname':'editor'}, key='editor-close')
			_create_form(st.session_state.dd104L['selected_ld'], formbox, out)
		
		
		

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
 
