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

# TODO: move status operations (start/stop/restart process) to status subtab?

# TODO: services are not getting created for whatever reason

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
	
	if 'newloaditor-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['newloaditor-flag'] = True
	
	if 'ld-editor-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['ld-editor-flag'] = False
	
	if 'ld-archive-use-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['ld-archive-use-flag'] = {}
	
	if 'ld-assign-validation-flag' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['ld-assign-validation-flag'] = False
	
	if 'NewFileStat' not in st.session_state.dd104m.keys():
		st.session_state.dd104m['NewFileStat'] = {'Flag':False, 'Error':''}
	
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
			syslog.syslog(syslog.LOG_CRIT, f'dd104m-loadouts: Ошибка при перечислении файлов директории {_dir}, подробности:   {str(e)}  ')
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
				files[int(i.split('dd104client')[1].split('.')[0] if 'dd104client' in i else i.split('dd104server')[1].split('.')[0])] = str((ldpath/i).resolve())
			
	
	print(files)
	return files

def get_active(LDIR:str) -> str: 
	try:
		LDIR=Path(LDIR)
		if not LDIR.is_dir():
			raise RuntimeError(f"Директория {LDIR} недоступна!")
	except Exception as e:
		msg = f"dd104m: Ошибка при получении текущей активной конфигурации, подробности:  {str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e
	else:
		if '.ACTIVE' in listdir(LDIR) and (LDIR/'.ACTIVE').is_symlink():
			try:
				return (LDIR/'.ACTIVE').resolve().name
			except Exception as e:
				msg = f"dd104m: Ошибка чтения указателя активной конфигурации, подробности:  {str(e)}"
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

def _save_to_file(string:str, old_confile:str, name='unnamed_file_version', return_timestamp=False) -> None:
	rtime = time.localtime(time.time())
	utime = f"{rtime.tm_year}-{rtime.tm_mon}-{rtime.tm_mday}@{rtime.tm_hour}:{rtime.tm_min}:{rtime.tm_sec}"
	# print(utime)
	if not (Path(old_confile).parent / f"{name}.ini").is_file():
		_new_file(extpath=Path(old_confile).parent/f"{name}.ini")
	with (Path(old_confile).parent / f"{name}.ini").open("w") as f:
		f.write(f"# Файл сгенерирован Сервисом Конфигурации Диода Данных;\n# savename: {name if name else 'unnamed_file_version'}\n# savetime: {utime}\n")
		f.write(string)
		f.close()
	
	if return_timestamp:
		return utime


def save_loadout():
	# out.empty()
	ld_sanitize()
	#WARNING: this line here is important to the rendering functionale, thank you streamlit
	st.session_state.dd104m['ld-editor-flag'] = False
	print(st.session_state)
	
	valid = True
	
	for i in range(1, len(st.session_state.dd104m['selected_ld']['selectors'])+1):
		if f'select_file_{i}' not in st.session_state.dd104m['selected_ld']['selectors'] or not st.session_state.dd104m['selected_ld']['selectors'][f'select_file_{i}']:
			valid = False
	
	if valid:
		ld = Path(st.session_state.dd104m['loaddir']) / st.session_state.dd104m['selected_ld']['name']
		if not ld.is_dir():
			try:
				makedirs(ld)
			except Exception as e:
				msg = f"dd104m: Критическая ошибка: директория {ld.parent} недоступна для записи, подробности:  {str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				raise e
			
		try:
			
			# this bitch doesn't work
			# stat = subprocess.run(f'rm -rf {ld}/*'.split(), text=True, capture_output=True)
			
			for f in listdir(ld):
				print(f"deleting {str(ld/f)}")
				(ld/f).unlink()
			
		except Exception as e:
			msg = f"dd104m: Критическая ошибка: не удалось очистить директорию {ld}, подробности:  {str(e)}"
			print(msg)
			syslog.syslog(syslog.LOG_CRIT, msg)
			raise e
			
		files = list_sources(st.session_state.dd104m['arcdir']) + list_sources(st.session_state.dd104m['inidir'])
		for i in range(1, len(st.session_state.dd104m['selected_ld']['selectors'])+1):
			# filepath = Path(st.session_state.dd104m['arcdir']) / st.session_state.dd104m['selected_ld']['selectors'][f'select_file_{i}'].split('(')[-1][:-1:]
			
			filepath = Path([x['filename'] for x in files if st.session_state.dd104m['selected_ld']['selectors'][f'select_file_{i}'] == f"{x['savename']} ({x['savetime']})"][0])
			
			if filepath.is_file():
				try:
					(ld/f"dd104client{i}.ini").symlink_to(filepath)
					print(f'  file {(ld/(f"dd104client{i}.ini" if i>1 else "dd104client.ini"))} was created!')
				except Exception as e:
					msg = f"dd104m: Критическая ошибка: не удалось создать ссылку на файл {filepath} в директории {ld}, подробности:  {str(e)}"
					syslog.syslog(syslog.LOG_CRIT, msg)
					raise e
			else:
				msg = f"dd104m: Критическая ошибка: файл {filepath} не найден!"
				syslog.syslog(syslog.LOG_CRIT, msg)
				raise FileNotFoundError(msg)


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
	
		

#WARNING: do not merge w/ sanitize() or we die
def ld_sanitize():
	try:
		st.session_state.dd104m['selected_ld']['selectors'] = {k:v for k,v in st.session_state.items() if 'select_file_' in k}
		for k in st.session_state.dd104m['selected_ld']['selectors'].keys():
			del(st.session_state[k])
	except Exception as e:
		msg = f"dd104m: Критическая ошибка: невозможно обработать данные сессии, подробности:  {str(e)}  "
		syslog.syslog(syslog.LOG_CRIT, msg)


def _apply_process_ops(out: st.empty):
	# out.empty()
	# out.write(st.session_state)
	if st.session_state.oplist_select == 'Перезапустить':
		operation = 'restart'
	elif st.session_state.oplist_select == 'Остановить':
		operation = 'stop'
	else:
		operation = 'start'
	
	tgts = [x.split(':')[0] for x in st.session_state.proclist_select if ':' in x]
	
	#print(f"tgts: {tgts}")
	
	errs = {}
	
	for tgt in tgts:
		try:
			a = subprocess.run(f'systemctl {operation} dd104client{tgt}.service'.split(), text=True, capture_output=True)
			if a.stderr:
				msg = f"{a.stderr}"
				errs[f"dd104client{tgt}.service"] = f'{a.stderr}'
				raise RuntimeError(msg)
		except Exception as e:
			msg = f"dd104m: Ошибка выполнения операции над процессом dd104client{tgt}.service:  {str(e)}"
			print(msg)
			syslog.syslog(syslog.LOG_CRIT, msg)
			#raise RuntimeError(msg)
		
	
	with out:#.container():
		st.session_state.proclist_select = []
		st.session_state.oplist_select = None
		out.empty()



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
		syslog.syslog(syslog.LOG_CRIT, f'dd104m: Ошибка при парсинге блока статуса сервиса, подробности:   {str(e)}  ')
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
				syslog.syslog(syslog.LOG_CRIT, f"dd104: Ошибка при создании файла сервиса dd104client{i if i > 1 else ''}, подробности:   {str(e)}  ")
				raise e
		return "Успех"


def _delete_services(target='all'): #deletes all services dd104client*.service, for now
	if target == 'all':
		try:
			stat = subprocess.run('rm -f /etc/systemd/system/dd104client*.service'.split(), capture_output=True, text=True)
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при уничтожении файлов сервисов dd104client, подробности:   {str(e)}  ')
			raise e
	else:
		try:
			stat = subprocess.run(f'rm -f /etc/systemd/system/{target}'.split(), capture_output=True, text=True)
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f'dd104: Ошибка при уничтожении файлов сервисов dd104client, подробности:   {str(e)}  ')
			raise e


def _new_loadout():
	if 'new_loadout_name' in st.session_state:
		loadname = Path(st.session_state.dd104m['loaddir'])/st.session_state['new_loadout_name']
	else:
		raise RuntimeError('_new_loadout: session state key "new_loadout_name" not found!')
	
	if isdir(loadname):
		msg = f"dd104m: Директория {loadname} уже существует!"
		syslog.syslog(syslog.LOG_WARNING, msg)
		raise FileExistsError(msg)
	try:
		loadname.mkdir(parents=True, exist_ok=False)
		print(f"directory {loadname} was created!")
	except Exception as e:
		msg = f"dd104m: Ошибка при создании директории {loadname}, подробности:  {str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e



def _status(num = 1, way='emoji') -> str:
	if num>=1:
		service = f"dd104client{num}.service" if _mode == 'tx' else f"dd104server{num}.service"
	else:
		raise RuntimeError(f"dd104m: номер процесса за границей области допустимых значений!")
	
	if way == 'emoji':
		try:
			stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
		except Exception as e:
			msg = f"dd104m: невозможно получить статус {service};   Подробности: {type(e)} - {str(e)}  "
			syslog.syslog(syslog.LOG_ERR, msg)
			return f"🔴"
		else:
			if stat.stderr:
				msg = f"dd104m: {stat.stderr}  "
				syslog.syslog(syslog.LOG_ERR, msg)
				return f"🔴"
			else:
				try:
					data = _statparse(stat.stdout)
					if data:
						if ("stopped" in data['Active'].lower() or 'dead' in data['Active'].lower()) and not 'failed' in data['Active'].lower():
							return "⚫"
						elif "activating" in data['Active'].lower():
							return f"🔁"
						elif 'failed' in data['Active'].lower():
							return f"🔴"
						elif "running" in data['Active'].lower():
							return f"🟢"
						else:
							raise RuntimeError(data)
					else:
						msg = f"dd104m: Ошибка: Парсинг статуса {service} передал пустой результат; Если эта ошибка повторяется, напишите в сервис поддержки ООО InControl.  "
						syslog.syslog(syslog.LOG_ERR, msg)
						return f"🔴"
				except Exception as e:
					syslog.syslog(syslog.LOG_CRIT, f'dd104m: Ошибка при парсинге блока статуса сервиса, подробности:   {str(e)}  ')
					raise e
	elif way == 'text':
		try:
			stat = subprocess.run(f"systemctl status {service}".split(), text=True, capture_output=True)
		except Exception as e:
			msg = f"dd104m: невозможно получить статус {service};   Подробности: {type(e)} - {str(e)}  "
			syslog.syslog(syslog.LOG_ERR, msg)
			return f"Ошибка! Подробности: {msg}"
		else:
			if stat.stderr:
				msg = f"dd104m: {stat.stderr}  "
				syslog.syslog(syslog.LOG_ERR, msg)
				return f"Ошибка! Подробности: {msg}"
			else:
				try:
					data = _statparse(stat.stdout)
					if data:
						if ("stopped" in data['Active'].lower() or 'dead' in data['Active'].lower()) and not 'failed' in data['Active'].lower():
							# return ''':gray[Остановлен]'''
							return '''Остановлен'''
						elif "activating" in data['Active'].lower():
							# return f":yellow[Запускается]"
							return "Запускается"
						elif 'failed' in data['Active'].lower():
							# return f":red[Отказ]"
							return "Отказ"
						elif "running" in data['Active'].lower():
							# return f":green[Запущен]"
							return '''Запущен'''
						else:
							raise RuntimeError(data)
					else:
						msg = f"dd104m: Ошибка: Парсинг статуса {service} передал пустой результат; Если эта ошибка повторяется, напишите в сервис поддержки ООО InControl.  "
						syslog.syslog(syslog.LOG_ERR, msg)
						return f":red[Ошибка! Подробности: {msg}]"
				except Exception as e:
					syslog.syslog(syslog.LOG_CRIT, f'dd104m: Ошибка при парсинге блока статуса сервиса, подробности:   {str(e)}  ')
					raise e

def current_op() -> str:
	try:
		stat = _status(st.session_state.dd104m['servicename'])
		if not stat:
			raise RuntimeError(f"Провал при получении статуса сервиса {st.session_state.dd104m['servicename']}.  ")
	except Exception as e:
		msg = f"dd104m: не удалось получить статус {st.session_state.dd104m['servicename']};   Подробности:   {type(e)}: {str(e)}  "
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
	L = [x for x in listdir(_dir) if (_dir/x).is_file() and (_dir/x).name.split('.')[-1] == 'ini']
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
			syslog.syslog(syslog.LOG_CRIT, f'dd104multi: Ошибка: Файл конфигурации {_dir/f} недоступен, подробности:   {str(e)}  ')
			raise e
	return out
	


def parse_form(confile: str, box: st.container):
	print(st.session_state)
	
	
	try:
		
		sanitize()
		
		
	except Exception as e:
		msg = f"dd104: Провал обработки данных формы,  Подробности:   {type(e)}: {str(e)}  "
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise e
	else:
		try:
			
			_save_to_file(parse_from_user(st.session_state.dd104m['contents']), confile, st.session_state.dd104m['contents']['savename'])
			#_archive(confile)
			_archive_d(confile)
			close_box(box, 'editor')
		except Exception as e:
			msg = f"dd104: Не удалось сохранить данные формы в файл конфигурации,  Подробности:  {type(e)}: {str(e)}  "
			syslog.syslog(syslog.LOG_CRIT, msg)
			raise e

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
			errors = errors + f"{str(e)}    "
	if len(errors) > 0:
		syslog.syslog(syslog.LOG_CRIT, f"DD104m: Во время проведения операций удаления произошли ошибки, подробности:     {errors}")
		st.write(f"DD104m: Во время проведения операций удаления произошли ошибки, подробности:     {errors}")
	



def _new_file(extpath=None):
	if not extpath:
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
	else:
		if Path(extpath).is_file():
			syslog.syslog(syslog.LOG_WARNING, f"dd104m: Файл {extpath} уже существует!")
			raise FileExistsError
		try:
			f = open(str(extpath), 'w')
			f.write('#')
			f.close()
			utime = _save_to_file("", str(extpath), f"{Path(extpath).name[:Path(extpath).name.rindex('.'):]}", return_timestamp=True)
			
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f"dd104m: Невозможно создать файл {str(extpath)}!")
			raise e


def _edit_svc(path:str): #possible problems: num is anything that comes between dd104<> and .
	
	path = Path(path)
	num = path.name.split('.')[0].split(st.session_state.dd104m['servicename'])[1]
	text = path.read_text().split('\n')
	for i in range(0, len(text)):
		if 'ExecStart=' in text[i] and text[i].strip()[0] != '#':
			text[i] = f"ExecStart=/opt/dd/{st.session_state.dd104m['servicename']}/{st.session_state.dd104m['servicename']} -c {st.session_state.dd104m['loaddir']}.ACTIVE/{st.session_state.dd104m['servicename']}{num}.service"
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
		msg = f"dd104m: Ошибка при остановке процессов, подробности:  {str(e)}"
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
				msg = f"dd104m: Ошибка при создании файлов сервиса, подробности:  {str(e)}"
				syslog.syslog(syslog.LOG_CRIT, msg)
				errors.append(str(e))
				failed.append(f"dd104client{i}.service")
			else:
				try:
					_edit_svc(f"/etc/systemd/system/{st.session_state.dd104m['servicename']}{i}.service")
				except Exception as e:
					msg = f"dd104m: Ошибка при редактировании файлов сервиса, подробности:  {str(e)}"
					syslog.syslog(syslog.LOG_CRIT, msg)
					errors.append(str(e))
					failed.append(f"{st.session_state.dd104m['servicename']}{i}.service")
				else:
					try:
						stat = subprocess.run(f"systemctl daemon-reload".split(), capture_output=True, text=True)
						if stat.stderr:
							raise RuntimeError(stat.stderr)
					except Exception as e:
						msg = f"dd104m: Ошибка при перезагрузке демонов systemctl, подробности:  {str(e)}"
						syslog.syslog(syslog.LOG_CRIT, msg)
						errors.append(str(e))
						failed.append(f"systemctl daemon-reload")
	
	
	return {'errors':errors, 'failed':failed}


def activate_ld(name:str):#, out:st.empty()): 
	# out.empty()
	st.session_state.dd104m['ld-editor-flag'] = False
	try:
		loadout = Path(st.session_state.dd104m['loaddir'])/name
		if '.ACTIVE' in listdir(loadout.parent):
			(loadout.parent/'.ACTIVE').unlink()
		(loadout.parent/'.ACTIVE').symlink_to(loadout, target_is_directory=True)
		
		results = processify()
		if not results['errors']:
			msg = f"dd104m: Конфигурация {name} успешно активирована!"
			syslog.syslog(syslog.LOG_INFO, msg)
			# out.write(msg)
		else:
			msg = f"dd104m: При обработке процессов {results['failed']} произошла(-и) ошибка(-и):   {results['errors']}"
			syslog.syslog(syslog.LOG_ERR, msg)
			# out.write(msg)
		
	except Exception as e:
		msg = f"dd104m: Ошибка при активации конфигурации, подробности:  {str(e)}"
		syslog.syslog(syslog.LOG_CRIT, msg)
		# out.write(msg)
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
		syslog.syslog(syslog.LOG_CRIT, f'dd104multi: Ошибка заполнения формы: подробности:   {str(e)}  ')
		raise e
	else:
		if st.session_state.dd104m['editor-flag']:
			with _form:
				if '/' in filepath:
					st.caption(f"Редактируемый файл: {data['old_savename'] if 'old_savename' in data.keys() else filepath.split('/')[-1]}")
				else:
					st.caption(f"Редактируемый файл: {data['old_savename'] if 'old_savename' in data.keys() else filepath}")
				
				
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
			

def _add_process(box:st.empty):
	# out.empty()
	box.empty()
	# out.write(st.session_state)
	if 'fcount' in st.session_state.dd104m['activator_selected_ld']:
		st.session_state.dd104m['activator_selected_ld']['fcount'] += 1


def _ld_create_form(loadout:dict, box:st.empty):
	
	def validate():
		
		existing = set()
		length = 0
		for k,v in st.session_state.items():
			if 'select_file_' in k and v:
				length += 1
				if v not in existing:
					existing.add(v)
				else:
					# out.write(":red[Внимание: обнаружены дублирующиеся значения]")
					st.session_state.dd104m['ld-assign-validation-flag'] = True
					break
		if length == len(existing):
			st.session_state.dd104m['ld-assign-validation-flag'] = False
	
	archived = list_sources(st.session_state.dd104m['arcdir'])
	current = list_sources(st.session_state.dd104m['inidir'])
	arch_files = [f"{x['savename']} ({x['savetime']})" for x in archived]
	files = [f"{x['savename']} ({x['savetime']})" for x in current]
	loadouted = [f"{x['savename']} ({x['savetime']})" for x in archived if x['filename'] in list_ld(loadout['name']).values()] + [f"{x['savename']} ({x['savetime']})" for x in current if x['filename'] in list_ld(loadout['name']).values()]
	
	print(loadouted)
	
	# box.empty()
	_form = box.container(border=True)
	
	with _form:
		if st.session_state.dd104m['ld-editor-flag']:
			
			cont = st.container()
			# sbtn, smsg = st.columns([0.3,0.7])
			# Statusbox = smsg.empty()
			
			if loadout['fcount'] <= 0:
				with cont:
					
					def checker(i:int):
						if f'ld-archive-use-cbox-0' in st.session_state.keys():
							st.session_state.dd104m['ld-archive-use-flag'][0] = st.session_state[f'ld-archive-use-cbox-0']
						elif i in st.session_state.dd104m['ld-archive-use-flag'].keys():
							del(st.session_state.dd104m['ld-archive-use-flag'][0])
						if f'select_file_0' in st.session_state:
							st.session_state[f'select_file_0'] = None
					
					col1, col2 = st.columns([0.8, 0.2])
					
					col2.checkbox(label="Использовать файлы из архива", value=st.session_state.dd104m['ld-archive-use-flag'][0] if 0 in st.session_state.dd104m['ld-archive-use-flag'].keys() else False, on_change=checker, kwargs={'i':0}, label_visibility="collapsed", key=f'ld-archive-use-cbox-0')
					
					col1.selectbox(label=f'Файл настроек процесса 1', options=(files if (0 in st.session_state.dd104m[f'ld-archive-use-flag'].keys() and not st.session_state.dd104m[f'ld-archive-use-flag'][0] or not 0 in st.session_state.dd104m[f'ld-archive-use-flag'].keys()) else files+arch_files), index=None, on_change=validate, key=f"select_file_0")
						
			else:
				
				for i in range(1, loadout['fcount']+1):
					with cont:
						
						def checker(i:int):
							if f'ld-archive-use-cbox-{i}' in st.session_state.keys():
								st.session_state.dd104m['ld-archive-use-flag'][i] = st.session_state[f'ld-archive-use-cbox-{i}']
							elif i in st.session_state.dd104m['ld-archive-use-flag'].keys():
								del(st.session_state.dd104m['ld-archive-use-flag'][i])
							if f'select_file_{i}' in st.session_state:
								st.session_state[f'select_file_{i}'] = None
						
						col1, col2 = st.columns([0.8, 0.2])
						
						col2.checkbox(label="Использовать файлы из архива", value=(st.session_state.dd104m['ld-archive-use-flag'][i] if i in st.session_state.dd104m['ld-archive-use-flag'].keys() else False), on_change=checker, kwargs={'i':i}, label_visibility="collapsed", key=f'ld-archive-use-cbox-{i}')
						
						options = files if (i in st.session_state.dd104m[f'ld-archive-use-flag'].keys() and not st.session_state.dd104m[f'ld-archive-use-flag'][i] or not i in st.session_state.dd104m[f'ld-archive-use-flag'].keys()) else files+arch_files
						
						col1.selectbox(label=f'Файл настроек процесса {i}', options=options, index=options.index(loadouted[i-1]) if (i<=len(loadouted) and loadouted[i-1] in options) else None, on_change=validate, key=f"select_file_{i}")
						





def draw_status():
	filelist = list_sources(st.session_state.dd104m['arcdir'])
	statbox = st.container()
	with statbox:
		if 'active_ld' in st.session_state.dd104m.keys() and st.session_state.dd104m['active_ld']:
			ldlist = list_ld(st.session_state.dd104m['active_ld']['name'])
			options = [f"{i}: {[f['savename']+' ('+f['savetime']+')' for f in filelist if f['filename'] == ldlist[i]][0]}" for i in range(1, st.session_state.dd104m['active_ld']['fcount']+1)] 
			if options:
				for proc in options:
					col1, col2 = st.columns([0.85, 0.15])
					col1.caption(f"Процесс {proc.split(': ')[0]}")
					col2.caption(f"Статус: {_status(int(proc.split(': ')[0]))}", help="⚫ - процесс остановлен,\n🔁 - выполняется процедура запуска,\n🟢 - процесс запущен,\n🔴 - ошибка/процесс остановлен с ошибкой.")
					col1, col2 = st.columns([0.4, 0.6])
					col1.caption('Файл настроек:')
					col2.text(proc.split(': ')[1])
			else:
				with st.empty():
					st.write("Нет процессов!")
		else:
			with st.empty():
				st.write("Нет загруженной конфигурации!")


def draw_table_status():
	if 'active_ld' in st.session_state.dd104m.keys() and st.session_state.dd104m['active_ld']:
		ldlist = list_ld(st.session_state.dd104m['active_ld']['name'])
		filelist = list_sources(st.session_state.dd104m['arcdir']) + list_sources(st.session_state.dd104m['inidir'])
		options = [f"{i}: {[f['savename']+' ('+f['savetime']+')' for f in filelist if f['filename'] == ldlist[i]][0]}" for i in range(1, st.session_state.dd104m['active_ld']['fcount']+1)] 
		
		if options:
			Data = {'Процесс':[],"Статус":[],'Файл настроек':[]}
			
			for i in options:
				Data['Процесс'].append(i.split(': ')[0])
				Data["Статус"].append(_status(int(i.split(': ')[0]), 'text'))
				Data['Файл настроек'].append(i.split(': ')[1])
		
			with st.container():
				st.caption(f"Профиль Запуска: {st.session_state.dd104m['active_ld']['name']}")
				st.table(data = Data)
		
		else:
			with st.empty():
				st.write("Нет процессов!")
	else:
		with st.empty():
			st.write("Нет загруженной конфигурации!")






def new_render_tx(servicename):
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Настройка протокола DD104')
	
	filelist = list_sources(st.session_state.dd104m['inidir']) #[{'savename':'', 'savetime':'', 'filename':''}, {}] 
	savenames = [x['savename'] for x in filelist]
	
	
	Filetab, Presettab = st.tabs(['Файлы конфигураций', "Профили Запуска"])
	
	Edit, Create, Delete = Filetab.tabs(["Редактор", "Создание Файлов", "Удаление Файлов"])
	
	Status, Loadouts = Presettab.tabs(['Процессы', 'Редактор'])
	
	statbox = Status.container()
	LSelectBox = Status.container()
	
	with Edit:
		
		def _close_wrap(box:st.container, bname:str):
			st.session_state['edit_file_select'] = None
			close_box(box, bname)
		lcol, rcol = st.columns([0.8, 0.2])
		
		archive_cb = rcol.checkbox("Добавить архивные файлы")
		
		arclist = list_sources(st.session_state.dd104m['arcdir'])
		
		edit_select = lcol.selectbox("Выберите файл для редактирования:", options=[f"{source['savename']}; {source['savetime']}" for source in (filelist if not archive_cb else filelist + arclist)], index=None, key="edit_file_select", placeholder="Не выбрано")
		
		if st.button("Редактировать выбранный файл", disabled=(edit_select == None), key="editfbtn"):
			st.session_state.dd104m['selected_file'] = [source['filename'] for source in filelist + arclist if f"{source['savename']}; {source['savetime']}" == edit_select][0]
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
		
		def _validate():
			if st.session_state.new_filename:
				if st.session_state.new_filename in savenames:
					st.session_state.dd104m['NewFileStat']['Flag'] = True
					st.session_state.dd104m['NewFileStat']['Error'] = f"Файл с такой меткой уже существует"
				else:
					st.session_state.dd104m['NewFileStat']['Flag'] = False
					st.session_state.dd104m['NewFileStat']['Error'] = ''
			else:
				st.session_state.dd104m['NewFileStat']['Flag'] = True
				st.session_state.dd104m['NewFileStat']['Error'] = f"Метка файла не может быть пустой"
		
		def _submit():
			try:
				_new_file()
			except FileExistsError:
				st.session_state.dd104m['NewFileStat']['Flag'] = True
				st.session_state.dd104m['NewFileStat']['Error'] = f"Файл с такой меткой уже существует"
			except Exception as e:
				st.session_state.dd104m['NewFileStat']['Flag'] = True
				st.session_state.dd104m['NewFileStat']['Error'] = f"При выполнении операции произошла ошибка: {str(e)}"
				# out.markdown(f":red[при выполнении операции произошла ошибка: {str(e)}]")
			
			st.session_state.new_filename = None
		
		
		tempbox = st.container()
		
		with tempbox:
			newfbox = st.empty()
			# if st.session_state.dd104m['NewFileStat']['Flag']:
			# 	outs.markdown(f":red[{st.session_state.dd104m['NewFileStat']['Error']}; файл не был создан.]")
			with newfbox:
				_form = st.container()
				with _form:
					outs = st.container()
					st.text_input(label='Метка файла', value=None, on_change=_validate, key='new_filename')
					submit = st.button('Создать', disabled=(st.session_state.dd104m['NewFileStat']['Flag'] or not st.session_state.new_filename), on_click=_submit, key='new-file-submit-btn')
					_validate()
					if st.session_state.dd104m['NewFileStat']['Flag']:
						outs.markdown(f":red[{st.session_state.dd104m['NewFileStat']['Error']}!]")
		
	
	
	with Delete:
		
		def _deletes():
			_delete_files([source['filename'] for source in filelist if f"{source['savename']}; {source['savetime']}" in st.session_state.delete_file_select])
			st.session_state.delete_file_select = []
		
		delete_select = st.multiselect("Выберите файл(ы) для удаления:", options=[f"{source['savename']}; {source['savetime']}" for source in filelist], default=None, key="delete_file_select", placeholder="Не выбрано")
		
		st.button("Удалить выбранные файлы", disabled=(not len(delete_select)>0), on_click=_deletes, key="delfbtn")
		
		
	
	
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
		col1, edt = st.columns([0.3, 0.7], gap='medium')
			
		col1.subheader("Выбор профиля")
		edt.subheader("Редактор выбранного профиля")
		
		edits = edt.container(height=600)
		loads = col1.container(height=200)
		# newbox = col1.container(height=440)
		
		
		with loads:
			
			def _load():
				if st.session_state.ld_selector:
					st.session_state.dd104m['selected_ld'] = [x for x in loadouts if x['name'] == st.session_state.ld_selector][0]
					st.session_state.dd104m['ld-editor-flag'] = True
					# st.session_state.ld_selector = None
				
			
			
			selector = st.selectbox(label="Выберите профиль", options=[x['name'] for x in loadouts if x['name'] != '.ACTIVE'], index=None, placeholder='Не выбрано', on_change=_load, key='ld_selector')
			
			c1c1, c1c2 = st.columns(2)
			
			# c1c1.button("Выбрать", key='act_selector', disabled=(not selector), on_click=_load)
			if c1c1.button('Новый профиль запуска'):
				newbox = col1.empty()
				block_nl = newbox.container()
				nlc1, nlc2 = block_nl.columns([0.8, 0.2])
				nlc1.subheader("Новый профиль запуска")
				nlc2.button("❌", on_click=close_box, kwargs={'box':newbox, 'bname':'newbox'}, key='newbox-close')
				Nlb = block_nl.container(height=240)
				with Nlb:
					# n1, n2 = st.columns([0.8, 0.2])
					st.session_state.dd104m['newlbox-flag'] = True
					newlbox = st.empty()
					# nlc2.button("❌", on_click=close_box, kwargs={'box':newlbox, 'bname':'newlbox'}, key='newlbox-close')
					if st.session_state.dd104m['newlbox-flag']:
						with newlbox.container():
							_form_nld = st.form('newloadoutform')
							with _form_nld:
								st.text_input(label='Имя профиля', key='new_loadout_name')
								submit = st.form_submit_button('Создать', on_click=_new_loadout)
			
		
		
		with edits:
			
			def closer_wrap(box:st.empty, bname:str):
				close_box(box, bname)
				st.session_state.ld_selector = None
				del(st.session_state.dd104m['selected_ld'])
			
			def _add_process(box:st.empty):
				box.empty()
				if 'fcount' in st.session_state.dd104m['selected_ld']:
					st.session_state.dd104m['selected_ld']['fcount'] += 1
			
			def _rm_process(box:st.empty):
				box.empty()
				if 'fcount' in st.session_state.dd104m['selected_ld'] and st.session_state.dd104m['selected_ld']['fcount'] > 0:
					st.session_state.dd104m['selected_ld']['fcount'] -= 1
			
			def save_wrap():
				save_loadout()
				st.session_state.ld_selector = None
			# add = st.button('Добавить процесс', disabled=(not 'selected_ld' in st.session_state.dd104m), on_click=_add_process, kwargs={'box':ld_formbox})
			
			ec1, ec2 = st.columns([0.9, 0.1])
			ld_formbox = st.empty()
			
			if 'selected_ld' in st.session_state.dd104m and st.session_state.dd104m['selected_ld'] and st.session_state.dd104m['ld-editor-flag']:
				
				ec2.button("❌", on_click=closer_wrap, kwargs={'box':ld_formbox, 'bname':'ld-editor'}, key='ld-editor-close')
				
				btn_l, btn_m, btn_r = st.columns(3)
				
				
				save = btn_l.button('Сохранить Профиль Запуска', on_click=save_wrap, disabled=st.session_state.dd104m['ld-assign-validation-flag'], use_container_width=True, key='save-ld-btn')
				
				add = btn_m.button('Добавить процесс', disabled=(not 'selected_ld' in st.session_state.dd104m), on_click=_add_process, kwargs={'box':ld_formbox}, use_container_width=True, key='add-process-btn')
				
				rm = btn_r.button('Удалить последний процесс из списка', disabled=(not 'selected_ld' in st.session_state.dd104m), on_click=_rm_process, kwargs={'box':ld_formbox}, use_container_width=True, key='rm-process-btn')
				
				_ld_create_form(st.session_state.dd104m['selected_ld'], ld_formbox)
				
				if st.session_state.dd104m['ld-assign-validation-flag']:
					ec1.empty().write(':red[Внимание: обнаружены дублирующиеся значения]')
			
			
		
	
	with LSelectBox.columns(2)[1]:
		def _load():
			if st.session_state.stat_ld_selector:
				st.session_state.dd104m['activator_selected_ld'] = [x for x in loadouts if x['name'] == st.session_state.stat_ld_selector][0]
		
		st.subheader('Выбор профиля для активации')
		
		selector = st.selectbox(label="Выберите профиль запуска", options=[x['name'] for x in loadouts if x['name'] != '.ACTIVE'], index=None, placeholder='Не выбрано', on_change=_load, key='stat_ld_selector')
		
		if 'activator_selected_ld' in st.session_state.dd104m:
			
			def activator_wrap(name:str):
				activate_ld(name)
				st.session_state.stat_ld_selector = None
				del(st.session_state.dd104m['activator_selected_ld'])
			
			st.button(f"Загрузить профиль {st.session_state.dd104m['activator_selected_ld']['name']}", on_click=activator_wrap, kwargs={'name':st.session_state.dd104m['activator_selected_ld']['name']}, key='stat_ld_activator_btn')
	
	with statbox:
		if _index:
			ldlist = list_ld(st.session_state.dd104m['active_ld']['name'])
			
			arclist = list_sources(st.session_state.dd104m['arcdir'])
			current = list_sources(st.session_state.dd104m['inidir'])
			# print("arclist:",arclist)
			
		print("activeLD: ",st.session_state.dd104m['active_ld'])
		
		options = [f"{i}: Процесс {i} - {[f['savename']+' (' + f['savetime']+')' for f in arclist+current if f['filename'] == ldlist[i]][0]}" for i in range(1, st.session_state.dd104m['active_ld']['fcount']+1)] if 'active_ld' in st.session_state.dd104m.keys() and st.session_state.dd104m['active_ld'] else []
		
		
		
		col1, col2 = st.columns([0.5, 0.5], gap='medium') # main, proc_ops
		
		c1c1, c1c2 = col1.columns([0.9, 0.1])
		c1c1.subheader("Статус Активной Конфигурации:")
		tempbox = col1.container(border=True).empty()
		with tempbox:
			draw_table_status()
		
		if c1c2.button("🔄"):
			with tempbox:
				draw_table_status()
		
		col2.subheader("Управление Процессами")
		procs = col2.container(border=True)
		
		
		outbox = col2.empty()
		
		with procs:
			
			def _allwrap(out: st.empty, options:list, op='Остановить'):
				
				st.session_state.proclist_select = options
				st.session_state.oplist_select = op
				_apply_process_ops(outbox)
				st.session_state.proclist_select = []
				st.session_state.oplist_select = None
				
			
			procselect = st.multiselect(label="Выберите процессы:", options=options, default=None, disabled=(not 'active_ld' in st.session_state.dd104m), key=f"proclist_select", placeholder="Не выбрано")
			
			opselect = st.selectbox(label="Выберите операцию:", options=["Остановить","Перезапустить","Запустить"], index=None, disabled=(len(procselect) == 0), key="oplist_select", placeholder="Не выбрано", on_change=_apply_process_ops, kwargs={'out':outbox})
			
			btn_l, btn_m, btn_r = st.columns([0.3, 0.3, 0.3])
			btn_l.button("Остановить все процессы", disabled=not options, on_click=_allwrap, kwargs={'op':'Остановить', 'options':options, 'out':outbox}, key="stat-stop-all-btn")
			btn_m.button("Запустить все процессы", disabled=not options, on_click=_allwrap, kwargs={'op':'Запустить', 'options':options, 'out':outbox}, key="stat-start-all-btn")
			btn_r.button("Перезапустить все процессы", disabled=not options, on_click=_allwrap, kwargs={'op':'Перезапустить', 'options':options, 'out':outbox}, key="stat-restart-all-btn")
		
		
	
	
	# with Outputs.empty():
	# 	st.write(st.session_state)
	# with Outputs.empty():
	# 	draw_table_status()


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
 
