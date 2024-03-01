import syslog, subprocess, time, tarfile
from shutil import move, copy2, unpack_archive, make_archive
from pathlib import Path
from os.path import exists, sep, isfile, join, isdir
from os import W_OK, R_OK, access, makedirs, listdir

import streamlit as st
import pandas as pd



confile = ""
archive = "/opt/dd/dd104/Archive.tar.gz"

def init():
	global confile
	
	st.set_page_config(layout="wide")
	
	
	confile = '/opt/dd/dd104client.ini'
	
	if 'dd104L' not in st.session_state.keys():
		st.session_state['dd104L'] = {}
	if "render_run_n" not in st.session_state.keys():
		st.session_state['dd104L']['render_run_n'] = False

# def _unarch_load_savefile(savename=None):
# 	if not savename is None and not savename == 'None':
# 		try:
# 			_archive(confile)
# 		except Exception as e:
# 			msg = f"dd104: Не удалось сохранить данные в архив при загрузке старой версии,\nПодробности:\n{type(e)}: {str(e)}\n"
# 			syslog.syslog(syslog.LOG_CRIT, msg)
# 			return msg
# 		else:
# 			try:
# 				confiledir = "/".join(confile.split('/')[0:-1:])
# 				with tarfile.open(archive, 'r:gz') as tar:
# 					tar.extractall(confiledir, savename)
# 					tar.close()
# 				if Path('/'.join([confiledir, savename])).exists():
# 					move('/'.join([confiledir, savename]), confile)
# 				else:
# 					raise RuntimeError(f"Error: {confiledir}/{savename} file does not exist!\n")
# 			except Exception as e:
# 				msg = f"dd104: Ошибка при загрузке архивированного файла;\nПодробности:\n{type(e)}: {str(e)}\n"
# 				syslog.syslog(syslog.LOG_CRIT, msg)
# 				return msg
# 			

def _load_savefile(savename:str):
	try:
		savedir = Path(archive).parent / "archive.d"
		if not savedir.is_dir():
			raise RuntimeError(f"Не удалось найти директорию архивации файлов конфигурации ({savedir}), операция не может быть продолжена.")
	except Exception as e:
		msg = f"dd104L: Ошибка при загрузке архивированного файла;\nПодробности:\n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		return msg
	if not savename is None and not savename == 'None':
		try:
			_archive_d(confile)
		except Exception as e:
			msg = f"dd104L: Не удалось сохранить данные в архив при загрузке старой версии,\nПодробности:\n{type(e)}: {str(e)}\n"
			syslog.syslog(syslog.LOG_CRIT, msg)
			return msg
		else:
			try:
				if (savedir/savename).exists():
					#used to be move()
					copy2((savedir/savename), confile)
				else:
					raise RuntimeError(f"Ошибка: файл {savedir}/{savename} не существует или недоступен!\n")
			except Exception as e:
				msg = f"dd104L: Ошибка при загрузке архивированного файла;\nПодробности:\n{type(e)}: {str(e)}\n"
				syslog.syslog(syslog.LOG_CRIT, msg)
				return msg
			else:
				return f"Успех: файл {savename} был загружен успешно, для редактирования конфигурации и управления сервисом выберите пункт dd104 из панели меню в левой части экрана."


def _archive_d(filepath:str, location=f'/opt/dd/dd104/archive.d'):
	if exists(filepath):
		if not isdir(location):
			makedirs(location)
		
		try:
			filename = filepath.split('/')[-1].split('.')
			rtime = time.localtime(time.time())
			utime = f"{rtime.tm_mday}-{rtime.tm_mon}-{rtime.tm_year}-{rtime.tm_hour}-{rtime.tm_min}-{rtime.tm_sec}"
			copy2(filepath, f"{location}/{filename[0]}-{utime}.{filename[1]}")
		except Exception as e:
			syslog.syslog(syslog.LOG_CRIT, f"dd104: провал при создании архивного файла конфигурации, операция не может быть продолжена.")
			raise e
		
	else:
		msg = f"dd104: провал при архивации файла конфигурации ({filepath}), файл конфигурации отсутствует или недоступен, операция не может быть продолжена."
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise RuntimeError(msg)
	


#TODO: DEFINITELY A BUG HERE, parsing is not working with the choicebox
# def _archive(filepath:str, location=f'/opt/dd/dd104/') -> None:
# 	if exists(filepath):
# 		try:
# 			filename = filepath.split('/')[-1].split('.')
# 			rtime = time.localtime(time.time())
# 			utime = f"{rtime.tm_mday}-{rtime.tm_mon}-{rtime.tm_year}-{rtime.tm_hour}-{rtime.tm_min}-{rtime.tm_sec}"
# 			copy2(filepath, f"/tmp/{filename[0]}-{utime}.{filename[1]}")
# 			filepath = f"/tmp/{filename[0]}-{utime}.{filename[1]}"
# 		except Exception as e:
# 			syslog.syslog(syslog.LOG_CRIT, f"dd104: провал при создании временного файла конфигурации, операция не может быть продолжена.")
# 			raise e
# 		try:
# 			if not exists(location+'Archive.tar.gz'):
# 				stat = make_archive(base_name=location+'Archive', format='gztar', root_dir=filename)
# 			else:
# 				#unarchive to /tmp/Arc104, add file, repackage
# 				# stat = subprocess.run(f"rm -rf /tmp/Arc104-{utime}".split())
# 				if not (Path(f'/tmp/Arc104-{utime}').exists() and Path(f'/tmp/Arc104-{utime}').is_dir()):
# 					makedirs(f'/tmp/Arc104-{utime}')
# 				unpack_archive(location+'Archive.tar.gz', f'/tmp/Arc104-{utime}/', 'gztar')
# 				move(filepath, f'/tmp/Arc104-{utime}/')
# 				stat = make_archive(base_name=location+'Archive', format='gztar', root_dir=f'/tmp/Arc104-{utime}/')
# 				stat = subprocess.run(f"rm -rf /tmp/Arc104-{utime}".split())
# 				stat = subprocess.run(f"rm -rf {filepath}".split())
# 				del(stat)
# 				syslog.syslog(syslog.LOG_INFO, f"dd104: {location}/Archive.tar.gz был успешно упакован!")
# 		except Exception as e:
# 			syslog.syslog(syslog.LOG_CRIT, f"dd104: Ошибка при обработке архива конфигураций, операция не может быть продолжена.")
# 			raise e
# 
def _arch_getnames(archive='/opt/dd/dd104/Archive.tar.gz') -> list: # [('savename', 'filename'),(),()]
	try:
		with tarfile.open(archive, "r:gz") as tar:
			files = tar.getnames()
			tar.close()
	except Exception as e:
		msg = f"dd104: Ошибка при обработке архивного файла;\nПодробности:\n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise RuntimeError(e)
	else:
		return [(x.strip('./'), x.strip('./')) for x in files if x and x != '.']
		

def _getnames(location='/opt/dd/dd104/archive.d'):
	if len([f for f in listdir(location) if isfile(join(location, f))]) > 0:
		try:
			saves = {}
			for i in listdir(location):
				with Path(f"{location}/{i}").open('r') as f:
					for line in f.read().split('\n'):
						if "savename" in line and line.strip()[0] == '#':
							v = line.split(':')[1].strip() if len(line.split(':'))>1 else ""
							saves[f"{i}"]=v
							break
					f.close()
		except Exception as e:
			msg = f"dd104L: Ошибка доступа к архивной директории;\nПодробности:\n{type(e)}: {str(e)}\n"
			syslog.syslog(syslog.LOG_CRIT, msg)
			raise RuntimeError(msg)
		else:
			return saves
	else:
		msg = f"dd104L: Ошибка доступа к архивной директории;\nПодробности:\nДиректория пуста или недоступна для чтения.\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise RuntimeError(msg)

def render():
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Страница конфигурации протокола DD104')
	
	if not st.session_state['dd104L']['render_run_n']:
		
		st.session_state['dd104L']['render_run_n'] = True
		
		col1, col2, col3= st.columns([0.3, 0.23, 0.47], gap='large')
		
		options = _getnames()
		
		with col1:
			choice = st.selectbox("Выберите файл конфигурации:", options=[f"{v}; {k}" for k,v in options.items()], index=None)
		# st.text = f'{choice}, {type(choice)}'
		
		with col2:
			
			loader = st.button("Загрузить Конфигурацию")
		
		
		if loader:
			op = choice.split('; ')[1]
			col3.write(_load_savefile(op))
	else:
		st.session_state['dd104L']['render_run_n'] = False
	
	

init()
render()
