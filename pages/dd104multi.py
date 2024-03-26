import streamlit as st


import syslog, subprocess, time, tarfile
from shutil import move, copy2, unpack_archive, make_archive
from pathlib import Path
from os.path import exists, sep, isdir, isfile, join
from os import W_OK, R_OK, access, makedirs, listdir

# Globals
_mode = 'tx'
INIDIR = '/etc/dd/dd104/configs/'
INIT_KEYS = ['servicename', 'inidir', 'selected_file']
# /Globals

#Logic

def init():
	
	st.set_page_config(layout="wide")
	
	
	if 'dd104m' not in st.session_state.keys():
		st.session_state['dd104m'] = {}
	
	if 'servicename' not in st.session_state.dd104m.keys():
		if _mode == 'tx':
			st.session_state.dd104m['servicename'] = 'dd104client'
		elif _mode == 'rx':
			st.session_state.dd104m['servicename'] = 'dd104server'
	
	if 'inidir' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['inidir'] = INIDIR
	
	if 'contents' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['contents'] = {}
	
	if 'newfbox-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['newfbox-flag'] = True
	
	if 'editor-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['editor-flag'] = True
	
	# dict_cleanup(st.session_state, ['dd104m'])

def _archive(filepath:str, location=f'/etc/dd/dd104/') -> None:
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

def _archive_d(filepath:str, location=f'/etc/dd/dd104/archive.d'):
	if exists(filepath):
		if not isdir(location):
			makedirs(location)
		
		try:
			filename = filepath.split('/')[-1].split('.')
			rtime = time.localtime(time.time())
			utime = f"{rtime.tm_year}-{rtime.tm_mon}-{rtime.tm_mday}-{rtime.tm_hour}-{rtime.tm_min}-{rtime.tm_sec}"
			copy2(filepath, f"{location}/{filename[0]}-{utime}.{filename[1]}")
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f"dd104m: провал при создании архивного файла конфигурации, операция не может быть продолжена.")
			raise e
		
	else:
		msg = f"dd104: провал при архивации файла конфигурации ({filepath}), файл конфигурации отсутствует или недоступен, операция не может быть продолжена."
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise RuntimeError(msg)

def load_from_file(_path:str) -> dict:
	mode = _mode.lower()
	try:
		lines = [ x.strip() for x in Path(_path).read_text().split('\n') if not x == '']
	except FileNotFoundError:
		return {'count':-1}
	
	if len(lines)>1:
		data = {} # {'count':N, 'mode':mode, 'old_..._...1':..., ...}
		block = 0
		for line in lines:
			if line[0]=='#' and 'savename' in line:
				data['old_savename'] = line.strip().split(': ')[1]
			if line[0]=='#' and 'savetime' in line:
				data['old_savetime'] = line.strip().split(': ')[1]
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
			#the 3 is for savename, savetime and recv
			data['count'] = (len(data.keys()) - 3) //2
		else:
			data['count'] = 1
		
		return data
	else:
		return {'count':1, 'old_savename':'', 'old_savetime':'', 'old_recv_addr':''}

def parse_from_user(data) -> str:
	mode = _mode.lower()
	if mode == 'tx':
		message=f"receiver\naddress={data['recv_addr']}\n\nserver"
		for i in range(1, data['count']+1):
			message = message + f"\naddress{i}={data[f'server_addr{i}']}\nport{i}={data[f'server_port{i}']}" 
		#st.write(message)
		return message

def _save_to_file(string:str, confile:str, name='unnamed_file_version', return_timestamp=False) -> None:
	rtime = time.localtime(time.time())
	utime = f"{rtime.tm_year}-{rtime.tm_mon}-{rtime.tm_mday}@{rtime.tm_hour}:{rtime.tm_min}:{rtime.tm_sec}"
	# print(utime)
	with Path(confile).open("w") as f:
		f.write(f"# Файл сгенерирован Сервисом Конфигурации Диода Данных;\n# savename: {name if name else 'unnamed_file_version'}\n# savetime: {utime}\n")
		f.write(string)
	
	if return_timestamp:
		return utime

def sanitize():
	#move stuff from st.session_state to st.<...>.dd104m.contents
	if 'contents' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['contents'] = {}
	for k,v in st.session_state.items():
		if ('server_addr' in k or 'server_port' in k or 'recv_addr' in k or 'servicename' in k or 'savename' in k):
			st.session_state.dd104m['contents'][k] = v
			del(st.session_state[k])
	
	#sanitize
	for i in range(1, st.session_state.dd104m['contents']['count']+1): #moving the healthy pairs over the incorrect one 
		if (st.session_state.dd104m['contents'][f"server_addr{i}"] == '' or st.session_state.dd104m['contents'][f"server_port{i}"] == ''):
			for j in range(i+1, st.session_state.dd104m['contents']['count']+1):
				if (st.session_state.dd104m['contents'][f"server_addr{j}"] and st.session_state.dd104m['contents'][f"server_port{j}"]):
					st.session_state.dd104m['contents'][f"server_addr{i}"] = st.session_state.dd104m['contents'][f"server_addr{j}"]
					st.session_state.dd104m['contents'][f"server_port{i}"] = st.session_state.dd104m['contents'][f"server_port{j}"]
					st.session_state.dd104m['contents'][f"server_addr{j}"] = ''
					st.session_state.dd104m['contents'][f"server_port{j}"] = ''
					break
	
	c = st.session_state.dd104m['contents']['count']
	for i in range(1, c+1):
		if i <= st.session_state.dd104m['contents']['count']+1:
			if (st.session_state.dd104m['contents'][f"server_addr{i}"] == '' or st.session_state.dd104m['contents'][f"server_port{i}"] == ''):
				st.session_state.dd104m['contents']['count'] -= 1
				del(st.session_state.dd104m['contents'][f"server_addr{i}"])
				del(st.session_state.dd104m['contents'][f"server_port{i}"])
	

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


#TODO NOT create_services_and_inis, CREATE_SERVICES (the former goes into the caller of this func)
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

def current_op() -> str:
	try:
		stat = _status(st.session_state.dd104m['servicename'])
		if not stat:
			raise RuntimeError(f"Провал при получении статуса сервиса {st.session_state.dd104m['servicename']}.\n")
	except Exception as e:
		msg = f"dd104m: не удалось получить статус {st.session_state.dd104m['servicename']}; \nПодробности: \n{type(e)}: {str(e)}\n"
		return msg
	else:
		if 'running' in stat['Active'] or 'failed' in stat['Active']:
			return 'перезапуск'
		elif 'stopped' in stat['Active'] :
			return 'запуск'
	

def list_sources(_dir=INIDIR) -> list: #returns a list of dicts like {'savename':'', 'savetime':'', 'filename':''}
	_dir = Path(_dir)
	if not _dir.is_dir():
		msg = f"dd104: Директория сервиса {_dir} недоступна!"
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
			syslog.syslog(syslog.LOG_CRIT, f'dd104multi: Ошибка: Файл конфигурации {_dir/f} недоступен, подробности:\n {str(e)}\n')
			raise e
	return out
	

def parse_form(confile: str, output: st.empty):
	print(st.session_state)
	
	output.empty()
	
	try:
		
		sanitize()
		
		
	except Exception as e:
		msg = f"dd104: Провал обработки данных формы,\nПодробности: \n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		output.text = msg
		raise e
	else:
		try:
			with output:
				
				_save_to_file(parse_from_user(st.session_state.dd104m['contents']), confile, st.session_state.dd104m['contents']['savename'])
				#_archive(confile)
				_archive_d(confile)
				
		except Exception as e:
			output.empty()
			msg = f"dd104: Не удалось сохранить данные формы в файл конфигурации,\nПодробности:\n{type(e)}: {str(e)}\n"
			syslog.syslog(syslog.LOG_CRIT, msg)
			output.subheader("Ошибка!")
			output.text(msg)
			raise e
		else:
			output.subheader("Статус Операции:")
			output.text("Успех")
			if output.button("OK"):
				output.empty()

def dict_cleanup(array: dict, to_be_saved=[]):
	dead_keys=[]
	for k in array.keys():
		if k not in to_be_saved:
			dead_keys.append(k)
	for k in dead_keys:
		del(array[k])

def _new_file():
	filename = st.session_state['new_filename'] if '.ini' in st.session_state['new_filename'][-4::] else f"{st.session_state['new_filename']}.ini"
	if isfile(f"{st.session_state.dd104m['inidir']}/{filename}"):
		syslog.syslog(syslog.LOG_WARNING, f"dd104m: Файл {st.session_state.dd104m['inidir']}/{filename} уже существует!")
		raise FileExistsError
	try:
		f = open(f"{st.session_state.dd104m['inidir']}/{filename}", 'w')
		f.write('#')
		f.close()
		utime = _save_to_file("", f"{st.session_state.dd104m['inidir']}/{filename}", f"{filename[:-4:]}", return_timestamp=True)
		
	except Exception as e:
		syslog.syslog(syslog.LOG_CRIT, f"dd104m: Невозможно создать файл {st.session_state.dd104m['inidir']}/{filename}!")
		raise e
	else:
		st.session_state.dd104m['selected_file'] = f"{st.session_state.dd104m['inidir']}/{filename}"

#/Logic

#Render

def close_box(box:st.empty, bname='editor'):
	box.empty()
	st.session_state.dd104m[f'{bname}-flag'] = False


def _create_form(formbox: st.container, filepath: str, output: st.empty):
	output.empty()
	
	try:
		data = load_from_file(filepath)
		with formbox.container():
			c1, c2 = st.columns([0.8, 0.2])
			ff = st.empty()
			c2.button("❌", on_click=close_box, kwargs={'box':ff, 'bname':'editor'}, key='editor-close')
			st.session_state.dd104m['contents'] = {}
			if st.session_state.dd104m['editor-flag']:
				with ff.container():
					_form = st.form("dd104mform")
	except Exception as e:
		syslog.syslog(syslog.LOG_CRIT, f'dd104multi: Ошибка заполнения формы: подробности:\n {str(e)}\n')
		raise e
	else:
		if st.session_state.dd104m['editor-flag']:
			with _form:
				if '/' in filepath:
					st.caption(f"Редактируемый файл: {filepath.split('/')[-1]}")
				else:
					st.caption(f"Редактируемый файл: {filepath}")
				
				
				st.session_state.dd104m['contents']['count'] = 2 #data['count']
				
				st.text_input(label = "Имя версии конфигурации", value=data['old_savename'] if 'old_savename' in data.keys() else "", key='savename')
				st.text_input(label = "Адрес получателя (НЕ ИЗМЕНЯТЬ БЕЗ ИЗМЕНЕНИЙ АДРЕСАЦИИ ДИОДНОГО СОЕДИНЕНИЯ)", value = data['old_recv_addr'] if 'old_recv_addr' in data.keys() else "", key='recv_addr')
				
				# if st.session_state.dd104m['contents']['count'] > 0:
					
				st.write(f"Основной Сервер (поля обязательны к заполнению)")
				if f'old_server_addr1' in data.keys():
					st.text_input(label=f'Адрес Сервера 1', value=data[f'old_server_addr1'], key=f'server_addr1') 
					st.text_input(label=f'Порт Сервера 1', value=data[f'old_server_port1'], key=f'server_port1') 
				else:
					st.text_input(label=f'Адрес Сервера 1', key=f'server_addr1') 
					st.text_input(label=f'Порт Сервера 1', key=f'server_port1') 
				
				st.write(f"Запасной Сервер (оставьте поля пустыми если запасной сервер не требуется)")
				if f'old_server_addr2' in data.keys():
					st.text_input(label=f'Адрес Запасного Сервера', value=data[f'old_server_addr2'], key=f'server_addr2') 
					st.text_input(label=f'Порт Запасного Сервера', value=data[f'old_server_port2'], key=f'server_port2') 
				else:
					st.text_input(label=f'Адрес Запасного Сервера', key=f'server_addr2') 
					st.text_input(label=f'Порт Запасного Сервера', key=f'server_port2') 
				
				
				submit = st.form_submit_button(label='Сохранить', on_click=parse_form, kwargs={'confile':filepath, 'output':output})
			

def render_tx(servicename): #TODO: expand on merge with rx
	
	#st.markdown(col_css, unsafe_allow_html=True)
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Редактор файлов настроек протокола DD104')
	
	filelist = list_sources(st.session_state.dd104m['inidir']) #[{'savename':'', 'savetime':'', 'filename':''}, {}] 
	
	col1, col2, col3= st.columns([0.25, 0.375, 0.375], gap='large')
	with col1:
		col1.subheader("Выберите файл конфигурации")
		filebox = col1.container(height=600)
	
	c2c1, c2c2 = col2.columns([0.9, 0.1])
	if st.session_state.dd104m['editor-flag']:
		c2c1.subheader("Редактор Файла Конфигурации")
	
	formbox = col2.container()
	# f = formbox.form("dd104multi-form")
	
	col3.subheader(f"Статус Операции:")
	output = col3.empty()
	
	if filebox.button(f"Новый Файл"):
		if not st.session_state.dd104m['newfbox-flag']:
			st.session_state.dd104m['newfbox-flag'] = True
		tempbox = filebox.container()
		with tempbox:
			# c1, c2 = st.columns([0.8, 0.2])
			newfbox = st.empty()
			c2c2.button("❌", on_click=close_box, kwargs={'box':newfbox, 'bname':'newfbox'}, key='newfbox-close')
			if st.session_state.dd104m['newfbox-flag']:
				with newfbox.container():
					_form = st.form('newfileform')
					with _form:
						st.text_input(label='Имя файла', key='new_filename')
						submit = st.form_submit_button('Создать', on_click=_new_file)
	
	for source in filelist:
		if filebox.button(f"{source['savename']}; {source['savetime']}", key=f"src-{source['filename']}"):
			st.session_state.dd104m['selected_file'] = source['filename']
			if not st.session_state.dd104m['editor-flag']:
				st.session_state.dd104m['editor-flag'] = True
	
	
	
	if 'selected_file' in st.session_state.dd104m and st.session_state.dd104m['selected_file'] and st.session_state.dd104m['editor-flag']:
		#dict_cleanup(st.session_state, ['dd104m', 'dd104'])
		_create_form(formbox, st.session_state.dd104m['selected_file'], output)

def render_rx(servicename):
	pass

def render():
	servicename = st.session_state.dd104m['servicename']
	mode = _mode.lower()
	if mode == 'tx':
		render_tx(servicename)
	elif mode == 'rx':
		render_rx(servicename)

#/Render

init()
render()
 
