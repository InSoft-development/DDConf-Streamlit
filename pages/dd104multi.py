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

# TODO: MASTERMODE functionality for authorised personnel to change important parameters

st.set_page_config(layout="wide")

def init():
	
	# st.set_page_config(layout="wide")
	
	
	if 'dd104m' not in st.session_state.keys():
		st.session_state['dd104m'] = {}
	
	if 'servicename' not in st.session_state.dd104m.keys():
		if _mode == 'tx':
			st.session_state.dd104m['servicename'] = 'dd104client'
		elif _mode == 'rx':
			st.session_state.dd104m['servicename'] = 'dd104server'
	
	if 'inidir' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['inidir'] = INIDIR
	
	if 'loaddir' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['loaddir'] = LOADOUTDIR
	
	if 'arcdir' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['arcdir'] = ARCDIR
	
	if 'contents' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['contents'] = {}
	
	if 'newfbox-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['newfbox-flag'] = True
	
	if 'editor-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['editor-flag'] = False
	
	# dict_cleanup(st.session_state, ['dd104m'])

#WARNING deprecated
def _archive(filepath:str, location=f'/etc/dd/dd104/') -> None:
	if exists(filepath):
		try:
			filename = Path(filepath).name[:-4:] if Path(filepath).name.count('.') == 1 else Path(filepath).name.replace('.','_')[:-4:]#filepath.split('/')[-1].split('.')
			rtime = time.localtime(time.time())
			utime = f"{rtime.tm_mday}-{rtime.tm_mon}-{rtime.tm_year}-{rtime.tm_hour}-{rtime.tm_min}-{rtime.tm_sec}"
			copy2(filepath, f"/tmp/{filename}-{utime}.{filename[1]}")
			filepath = f"/tmp/{filename}-{utime}.ini"
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
			filename = Path(filepath).name if Path(filepath).name.count('.') == 1 else Path(filepath).name.replace('.','_') #filepath.split('/')[-1].split('.')
			rtime = time.localtime(time.time())
			utime = f"{rtime.tm_year}-{rtime.tm_mon}-{rtime.tm_mday}-{rtime.tm_hour}-{rtime.tm_min}-{rtime.tm_sec}"
			copy2(filepath, f"{location}/{filename[:-4:]}-{utime}.{filename[-3::]}")
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

def list_loadouts(_dir=INIDIR) -> list: #returns a list of dicts like {'name':'', 'fcount':len([]), 'files':['','']}
	_dir = Path(_dir)
	if not _dir.is_dir():
		msg = f"dd104m: Директория сервиса {_dir} недоступна!"
		syslog.syslog(syslog.LOG_ERR, msg)
		raise FileNotFoundError(msg)
	L = [x for x in listdir(_dir) if (_dir/x).is_dir()]
	out = []
	for f in L:
		try:
			files = [x for x in listdir(_dir/f) if isfile(join(_dir/f, x))]
			
			out.append({'name':f, 'fcount':len(files), 'files':files})
		
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104m-loadouts: Ошибка при перечислении файлов директории {_dir}, подробности:\n {str(e)}\n')
			raise e
	return out

def list_ld(name: str): #returns the dict of files from the archive that are symlinked to from the loadout dir 
	if not '/' in name:
		ldpath = Path(st.session_state.dd104m['loaddir'])/name
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

def get_active(LDIR:str) -> str: 
	try:
		LDIR=Path(LDIR)
		if not LDIR.is_dir():
			raise RuntimeError(f"Директория {LDIR} недоступна!")
	except Exception as e:
		msg = f"dd104m: Ошибка при получении текущей активной конфигурации, подробности:\n{str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e
	else:
		if '.ACTIVE' in listdir(LDIR) and (LDIR/'.ACTIVE').is_symlink():
			try:
				return (LDIR/'.ACTIVE').resolve().name
			except Exception as e:
				msg = f"dd104m: Ошибка чтения указателя активной конфигурации, подробности:\n{str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				raise e
		else:
			return None 

def parse_from_user(data) -> str:
	mode = _mode.lower()
	if mode == 'tx':
		message=f"receiver\naddress={data['recv_addr'] if 'recv_addr' in data.keys() else '192.168.100.10'}\n\nserver"
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
			msg = f"dd104m: Ошибка выполнения операции над процессом dd104client{tgt}.service:\n{str(e)}"
			print(msg)
			syslog.syslog(syslog.LOG_CRIT, msg)
			#raise RuntimeError(msg)
		
	
	with out.container():
		def _cleaner():
			st.session_state.proclist_select = []
			st.session_state.oplist_select = None
			out.empty()
			
		st.write("Успех!" if not errs else f"Во время выполнения операции {st.session_state.oplist_select} над процессом(-ами) {errs} произошли ошибки. Операции не были применены к этим процессам либо были произведены безуспешно.")
		st.button("OK", on_click=_cleaner)


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
		syslog.syslog(syslog.LOG_CRIT, f'dd104m: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e)}\n')
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

# WARNING: LEGACY
# def _status(service = 'dd104client.service') -> str:
# 	try:
# 		stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
# 	except Exception as e:
# 		msg = f"dd104: невозможно получить статус {service}; \nПодробности: {type(e)} - {str(e)}\n"
# 		syslog.syslog(syslog.LOG_ERR, msg)
# 		return None
# 	else:
# 		if stat.stderr:
# 			msg = f"dd104: {stat.stderr}\n"
# 			syslog.syslog(syslog.LOG_ERR, msg)
# 			return None
# 		else:
# 			try:
# 				data = _statparse(stat)
# 				if data:
# 					return data
# 				else:
# 					msg = f"dd104: Ошибка: Парсинг статуса {service} передал пустой результат; Если эта ошибка повторяется, напишите в сервис поддержки ООО InControl.\n"
# 					syslog.syslog(syslog.LOG_ERR, msg)
# 					return None
# 			except Exception as e:
# 				syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e)}\n')
# 				raise e

def _status(num = 1) -> str:
	if num>=1:
		service = f"dd104client{num}.service" if _mode == 'tx' else f"dd104server{num}.service"
	else:
		raise RuntimeError(f"dd104m: номер процесса за границей области допустимых значений!")
	
	try:
		stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
	except Exception as e:
		msg = f"dd104m: невозможно получить статус {service}; \nПодробности: {type(e)} - {str(e)}\n"
		syslog.syslog(syslog.LOG_ERR, msg)
		return f"🔴"
	else:
		if stat.stderr:
			msg = f"dd104m: {stat.stderr}\n"
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
					msg = f"dd104m: Ошибка: Парсинг статуса {service} передал пустой результат; Если эта ошибка повторяется, напишите в сервис поддержки ООО InControl.\n"
					syslog.syslog(syslog.LOG_ERR, msg)
					return f"🔴"
			except Exception as e:
				syslog.syslog(syslog.LOG_CRIT, f'dd104m: Ошибка при парсинге блока статуса сервиса, подробности:\n {str(e)}\n')
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
	

def parse_form(confile: str, box: st.container):
	print(st.session_state)
	
	# output.empty()
	
	try:
		
		sanitize()
		
		
	except Exception as e:
		msg = f"dd104: Провал обработки данных формы,\nПодробности: \n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		# output.text = msg
		raise e
	else:
		try:
			# with output:
				
			_save_to_file(parse_from_user(st.session_state.dd104m['contents']), confile, st.session_state.dd104m['contents']['savename'])
			#_archive(confile)
			_archive_d(confile)
			close_box(box, 'editor')
		except Exception as e:
			# output.empty()
			msg = f"dd104: Не удалось сохранить данные формы в файл конфигурации,\nПодробности:\n{type(e)}: {str(e)}\n"
			syslog.syslog(syslog.LOG_CRIT, msg)
			# output.subheader("Ошибка!")
			# output.text(msg)
			raise e
		# else:
		# 	output.subheader("Статус Операции:")
		# 	output.text("Успех")
		# 	if output.button("OK"):
		# 		output.empty()

def dict_cleanup(array: dict, to_be_saved=[]):
	dead_keys=[]
	for k in array.keys():
		if k not in to_be_saved:
			dead_keys.append(k)
	for k in dead_keys:
		del(array[k])

def _delete_files(filelist:list):
	errors = ''
	for item in filelist:
		try:
			Path(item).unlink()
		except Exception as e:
			errors = errors + f"{str(e)}\n\n"
	if len(errors) > 0:
		syslog.syslog(syslog.LOG_CRIT, f"DD104m: Во время проведения операций удаления произошли ошибки, подробности: \n\n{errors}")
		st.write(f"DD104m: Во время проведения операций удаления произошли ошибки, подробности: \n\n{errors}")
	

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
	# else:
		# st.session_state.dd104m['selected_file'] = f"{st.session_state.dd104m['inidir']}/{filename}"
		# close_box(box, 'newfbox')


def _edit_svc(path:str): #possible problems: num is anything that comes between dd104<> and .
	
	path = Path(path)
	num = path.name().split('.')[0].split(st.session_state.dd104m['servicename'])[1]
	text = path.read_text().split('\n')
	for i in range(0, len(text)):
		if 'ExecStart=' in text[i] and text[i].strip()[0] != '#':
			text[i] = f"ExecStart=/opt/dd/{st.session_state.dd104m['servicename']}/{st.session_state.dd104m['servicename']} -c {st.session_state.dd104m['loaddir']}{st.session_state.dd104m['servicename']}{num}.service"
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
		msg = f"dd104m: Ошибка при остановке процессов, подробности:\n{str(e)}"
		raise RuntimeError(msg)
	else:
		#delete
		services = [x for x in listdir('/etc/systemd/system/') if st.session_state.dd104m['servicename'] in x]
		for s in services:
			try:
				(Path('/etc/systemd/system/')/s).unlink()
			except Exception as e:
				failed.append(s)
				errors.append(str(e))
		#copy
		for i in range(1, st.session_state.dd104m['activator_selected_ld']['fcount']+1):
			try:
				copy2(f"/etc/dd/dd104/{st.session_state.dd104m['servicename']}.service.default", f"/etc/systemd/system/{st.session_state.dd104m['servicename']}{i}.service")
			except Exception as e:
				msg = f"dd104m: Ошибка при создании файлов сервиса, подробности:\n{str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				errors.append(str(e))
				failed.append(f"dd104client{i}.service")
			else:
				try:
					_edit_svc(f"/etc/systemd/system/{st.session_state.dd104m['servicename']}{i}.service")
				except Exception as e:
					msg = f"dd104m: Ошибка при редактировании файлов сервиса, подробности:\n{str(e)}"
					syslog.syslog(syslog.LOG_CRIT, msg)
					errors.append(str(e))
					failed.append(f"{st.session_state.dd104m['servicename']}{i}.service")
				else:
					try:
						stat = subprocess.run(f"systemctl daemon-reload".split(), capture_output=True, text=True)
						if stat.stderr:
							raise RuntimeError(stat.stderr)
					except Exception as e:
						msg = f"dd104m: Ошибка при перезагрузке демонов systemctl, подробности:\n{str(e)}"
						syslog.syslog(syslog.LOG_CRIT, msg)
						errors.append(str(e))
						failed.append(f"systemctl daemon-reload")
	
	
	return {'errors':errors, 'failed':failed}


def activate_ld(name:str, out:st.empty()): 
	out.empty()
	try:
		loadout = Path(st.session_state.dd104m['loaddir'])/name
		if '.ACTIVE' in listdir(loadout.parent):
			(loadout.parent/'.ACTIVE').unlink()
		(loadout.parent/'.ACTIVE').symlink_to(loadout, target_is_directory=True)
		
		results = processify()
		if not results['errors']:
			msg = f"dd104m: Конфигурация {name} успешно активирована!"
			syslog.syslog(syslog.LOG_INFO, msg)
			out.write(msg)
		else:
			msg = f"dd104m: При обработке процессов {results['failed']} произошла(-и) ошибка(-и): \n{results['errors']}"
			syslog.syslog(syslog.LOG_ERR, msg)
			out.write(msg)
		
	except Exception as e:
		msg = f"dd104m: Ошибка при активации конфигурации, подробности:\n{str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		out.write(msg)
		raise e

#/Logic

#Render

def close_box(box:st.empty, bname='editor'):
	box.empty()
	st.session_state.dd104m[f'{bname}-flag'] = False


def _create_form(formbox: st.container, filepath: str):
	# output.empty()
	
	try:
		data = load_from_file(filepath)
		with formbox.container():
			c1, c2 = st.columns([0.8, 0.2])
			ff = st.empty()
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
				
				# TODO:  MASTERMODE functionality 
				# st.text_input(label = "Адрес получателя (НЕ ИЗМЕНЯТЬ БЕЗ ИЗМЕНЕНИЙ АДРЕСАЦИИ ДИОДНОГО СОЕДИНЕНИЯ)", value = data['old_recv_addr'] if 'old_recv_addr' in data.keys() else "", key='recv_addr', disabled=MASTERMODE)
				
				
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
				
				
				submit = st.form_submit_button(label='Сохранить', on_click=parse_form, kwargs={'confile':filepath, 'box':formbox})
			
# 
# def render_tx(servicename): #TODO: expand on merge with rx
# 	
# 	#st.markdown(col_css, unsafe_allow_html=True)
# 	st.title('Сервис Конфигурации Диода Данных')
# 	st.header('Редактор файлов настроек протокола DD104')
# 	
# 	filelist = list_sources(st.session_state.dd104m['inidir']) #[{'savename':'', 'savetime':'', 'filename':''}, {}] 
# 	
# 	col1, col2, col3= st.columns([0.25, 0.375, 0.375], gap='large')
# 	with col1:
# 		col1.subheader("Выберите файл конфигурации")
# 		filebox = col1.container(height=600)
# 	
# 	c2c1, c2c2 = col2.columns([0.9, 0.1])
# 	c2c1.subheader("Редактор Файла Конфигурации")
# 	
# 	formbox = col2.container()
# 	# f = formbox.form("dd104multi-form")
# 	
# 	col3.subheader(f"Статус Операции:")
# 	output = col3.empty()
# 	
# 	c1c1, c1c2 = filebox.columns([0.8, 0.2])
# 	if c1c1.button(f"Новый Файл"):
# 		if not st.session_state.dd104m['newfbox-flag']:
# 			st.session_state.dd104m['newfbox-flag'] = True
# 		tempbox = filebox.container()
# 		with tempbox:
# 			# c1, c2 = st.columns([0.8, 0.2])
# 			newfbox = st.empty()
# 			c1c2.button("❌", on_click=close_box, kwargs={'box':newfbox, 'bname':'newfbox'}, key='newfbox-close')
# 			if st.session_state.dd104m['newfbox-flag']:
# 				with newfbox.container():
# 					_form = st.form('newfileform')
# 					with _form:
# 						st.text_input(label='Имя файла', key='new_filename')
# 						submit = st.form_submit_button('Создать', on_click=_new_file)
# 	
# 	for source in filelist:
# 		if filebox.button(f"{source['savename']}; {source['savetime']}", key=f"src-{source['filename']}"):
# 			st.session_state.dd104m['selected_file'] = source['filename']
# 			if not st.session_state.dd104m['editor-flag']:
# 				st.session_state.dd104m['editor-flag'] = True
# 			
# 	
# 	
# 	
# 	if 'selected_file' in st.session_state.dd104m and st.session_state.dd104m['selected_file'] and st.session_state.dd104m['editor-flag']:
# 		#dict_cleanup(st.session_state, ['dd104m', 'dd104'])
# 		#WARNING: might cause unknown side-effects
# 		c2c2.button("❌", on_click=close_box, kwargs={'box':formbox, 'bname':'editor'}, key='editor-close')
# 		_create_form(formbox, st.session_state.dd104m['selected_file'])

def draw_status():
	statbox = st.container()
	with statbox:
		if 'active_ld' in st.session_state.dd104m.keys() and st.session_state.dd104m['active_ld']:
			options = [f"{i}: Процесс {i} ({list_ld(st.session_state.dd104m['active_ld']['name'])[i]})" for i in range(1, st.session_state.dd104m['active_ld']['fcount']+1)] 
			if options:
				for proc in options:
					col1, col2 = st.columns([0.85, 0.15])
					col1.caption(f"Процесс {proc.split(':')[0]}")
					col2.caption(f"Статус: {_status(int(proc.split(':')[0]))}", help="⚫ - процесс остановлен,\n🟢 - процесс запущен,\n🔴 - ошибка/процесс остановлен с ошибкой.")
					st.caption('Файл настроек:')
					col1, col2 = st.columns([0.25, 0.75])
					col2.text(str((Path(st.session_state.dd104m['loaddir'])/f".ACTIVE/{st.session_state.dd104m['servicename']}{proc.split(':')[0]}.ini").resolve().name))
			else:
				with st.empty():
					st.write("Нет процессов!")
		else:
			with st.empty():
				st.write("Нет загруженной конфигурации!")

def new_render_tx(servicename):
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Редактор файлов настроек протокола DD104')
	
	filelist = list_sources(st.session_state.dd104m['inidir']) #[{'savename':'', 'savetime':'', 'filename':''}, {}] 
	
	Edit, Create, Delete, Loadouts, Outputs = st.tabs(["Редактор", "Создание Файлов", "Удаление Файлов", "Пресеты", "DEBUG"])
	
	statbox = st.container(height=400, border=True)
	
	try:
		with Edit:
			
			def _close_wrap(box:st.container, bname:str):
				st.session_state['edit_file_select'] = None
				close_box(box, bname)
			
			edit_select = st.selectbox("Выберите файл для редактирования:", options=[f"{source['savename']}; {source['savetime']}" for source in filelist], index=None, key="edit_file_select", placeholder="Не выбрано")
			
			if st.button("Редактировать выбранный файл", disabled=(edit_select == None), key="editfbtn"):
				st.session_state.dd104m['selected_file'] = [source['filename'] for source in filelist if f"{source['savename']}; {source['savetime']}" == edit_select][0]
				if not st.session_state.dd104m['editor-flag']:
					st.session_state.dd104m['editor-flag'] = True
			
			if 'selected_file' in st.session_state.dd104m and st.session_state.dd104m['selected_file'] and st.session_state.dd104m['editor-flag']:
			
				with st.container():
					
					c1, c2 = st.columns([0.8, 0.2])
					c1.caption("Редактор:")
					formbox = st.container()
					
					#WARNING: might cause unknown side-effects
					c2.button("❌", on_click=_close_wrap, kwargs={'box':formbox, 'bname':'editor'}, key='editor-close')
					
					_create_form(formbox, st.session_state.dd104m['selected_file'])
			
		
		with Create:
			def _submit():
				_new_file()
				st.session_state.new_filename = None
			
			tempbox = st.container()
			
			with tempbox:
				newfbox = st.empty()
				with newfbox.container():
					_form = st.form('newfileform')
					with _form:
						st.text_input(label='Имя файла', value=None, key='new_filename')
						submit = st.form_submit_button('Создать', on_click=_submit)
			
		
		
		with Delete:
			
			def _deletes():
				_delete_files([source['filename'] for source in filelist if f"{source['savename']}; {source['savetime']}" in st.session_state.delete_file_select])
				st.session_state.delete_file_select = []
			
			delete_select = st.multiselect("Выберите файл(ы) для удаления:", options=[f"{source['savename']}; {source['savetime']}" for source in filelist], default=None, key="delete_file_select", placeholder="Не выбрано")
			
			st.button("Удалить выбранные файлы", disabled=(not len(delete_select)>0), on_click=_deletes, key="delfbtn")
		
	except Exception as e:
		Outputs.empty().write(f'Error: {str(e)}\n\n\n\n{st.session_state}')
		
	
	
	loadouts = list_loadouts(st.session_state.dd104m['loaddir']) # [{'name':'', 'fcount':'', 'files':[]}, {}]
	st.session_state.dd104m['ld_names'] = [x['name'] for x in loadouts if x and 'name' in x]
	_index = get_active(st.session_state.dd104m['loaddir'])
	
	if _index:
		for l in loadouts:
			if l['name'] == _index:
				st.session_state.dd104m['active_ld'] = l
	else:
		st.session_state.dd104m['active_ld'] = None
		
	
	with Loadouts.container():
		ald, aop, edt, col4 = st.columns([0.2, 0.2, 0.3, 0.3], gap='medium')
			
		ald.subheader("Выбор конфигурации")
		aop.subheader("Операции")
		# col4.subheader("Вывод")
		edt.subheader("Редактор выбранной конфигурации")
		
		edits = edt.container(height=600)
		loads = ald.container(height=600)
		procs = aop.container(height=434)
		c_load = aop.container(height=150)
		col4.subheader("Вывод")
		_aout = col4.container(height=224)
		aout = _aout.empty()
		col4.subheader("PLACEHOLDER")
		_extras = col4.container(height=300)
		# _extras.subheader('PLACEHOLDER')
		
		aout.write(st.session_state)
		
		# _processwork(astat, aout)
		
		# for i in loadouts:
		# 	if not i['name'] == '.ACTIVE':
		# 		if loads.button(f"{i['name']}", type='primary' if i['name']==_index else "secondary", key=f"act_{i['name']}"):
		# 			st.session_state.dd104m['activator_selected_ld'] = i
		# 			aout.write(st.session_state)
		
		
		with loads:
			
			def _load():
				st.session_state.dd104m['activator_selected_ld'] = [x for x in loadouts if x['name'] == st.session_state.ld_selector][0]
				st.session_state.ld_selector = None
			
			selector = st.selectbox(label="Выберите конфигурацию", options=[x['name'] for x in loadouts if x['name'] != '.ACTIVE'], index=None, placeholder='Не выбрано', key='ld_selector')
			st.button("Выбрать", key='act_selector', disabled=(not selector), on_click=_load)
			
		
		if 'activator_selected_ld' in st.session_state.dd104m:
			with c_load:
				st.button(f"Загрузить конфигурацию {st.session_state.dd104m['activator_selected_ld']['name']}", on_click=activate_ld, kwargs={'name':st.session_state.dd104m['activator_selected_ld']['name'], 'out':aout})
		
		options = [f"{i}: Процесс {i} ({list_ld(st.session_state.dd104m['active_ld']['name'])[i]})" for i in range(1, st.session_state.dd104m['active_ld']['fcount']+1)] if 'active_ld' in st.session_state.dd104m.keys() and st.session_state.dd104m['active_ld'] else []
		
		
		
		with procs:
			
			def disabler():
					st.session_state.dd104m['proc_submit_disabled'] = not ('proclist_select' in st.session_state and st.session_state['proclist_select']) or not ('oplist_select' in st.session_state and st.session_state['oplist_select'])
				
			
			procselect = st.multiselect(label="Выберите процессы:", options=options, default=None, disabled=(not 'active_ld' in st.session_state.dd104m), key=f"proclist_select", placeholder="Не выбрано", on_change=disabler)
			
			opselect = st.selectbox(label="Выберите операцию:", options=["Остановить","Перезапустить","Запустить"], index=None, disabled=(not 'active_ld' in st.session_state.dd104m), key="oplist_select", placeholder="Не выбрано", on_change=disabler)
			
			
			if procs.button("Применить", disabled=st.session_state.dd104m['proc_submit_disabled'] if 'proc_submit_disabled' in st.session_state.dd104m else True):
				_apply_process_ops(aout)
	
	
	with statbox:
		
		col1, col2= st.columns([0.95, 0.05], gap='large') # main, status emoji, refresh button
		
		col1.subheader("Статус Активной Конфигурации:")
		tempbox = col1.empty()
		with tempbox:
			draw_status()
		
		if col2.button("🔄"):
			with tempbox:
				draw_status()
	
	with Outputs.empty():
		st.write(st.session_state)


def render_rx(servicename):
	pass

def render():
	servicename = st.session_state.dd104m['servicename']
	mode = _mode.lower()
	if mode == 'tx':
		new_render_tx(servicename)
	elif mode == 'rx':
		render_rx(servicename)

#/Render

init()
render()
 
