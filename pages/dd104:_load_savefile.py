import syslog, subprocess, time, tarfile
from shutil import move, copy2, unpack_archive, make_archive
from pathlib import Path
from os.path import exists, sep
from os import W_OK, R_OK, access, makedirs

import streamlit as st
import pandas as pd



confile = ""

def init():
	global confile
	
	st.set_page_config(layout="wide")
	
	
	confile = '/opt/dd/dd104client.ini'
	
	if 'dd104' not in st.session_state.keys():
		st.session_state['dd104L'] = {}
	if "render_run_n" not in st.session_state.keys():
		st.session_state['dd104L']['render_run_n'] = False


def _load_savefile(archive='/opt/dd/dd104/Archive.tar.gz', name=None):
	if not name:
		raise RuntimeError('dd104: no filename provided')
	try:
		_archive(confile)
	except Exception as e:
		st.empty()
		msg = f"dd104: Не удалось сохранить данные в архив при загрузке старой версии,\nПодробности:\n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		st.header("Ошибка!")
		st.text(msg)
	try:
		#stat = subprocess.run(f'rm -rf {confile}'.split())
		confiledir = "/".join(confile.split('/')[0:-1:])
		with tarfile.open(archive, 'r:gz') as tar:
			tar.extractall(confiledir, name)
			tar.close()
		if Path('/'.join([confiledir, name])).exists():
			move('/'.join([confiledir, name]), confile)
		else:
			raise RuntimeError(f"Error: {confiledir}/{name} file does not exist!\n")
		# st.rerun()
	except Exception as e:
		msg = f"dd104: Ошибка при загрузке архивированного файла;\nПодробности:\n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise RuntimeError(e)

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

def _getnames(archive='/opt/dd/dd104/Archive.tar.gz') -> list: # [('savename', 'filename'),(),()]
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

# def _loader(expander: st.expander, col3) -> None:
# 	
# 	filelist = _getnames('/opt/dd/dd104/Archive.tar.gz') #[('savename', 'filename'),(),()]
# 	with expander:
# 		for k, v in filelist:
# 			st.button(k, on_click=_load_savefile(col3, '/opt/dd/dd104/Archive.tar.gz', v))


def render():
	st.title('Сервис Конфигурации Диода Данных')
	st.header('Страница конфигурации протокола DD104')
	
	if not st.session_state['dd104L']['render_run_n']:
		
		st.session_state['dd104L']['render_run_n'] = False
		
		col1, col2, col3= st.columns([0.3, 0.23, 0.47], gap='large')
		
		options = _getnames()
		
		with col1:
			choice = st.selectbox("Выберите файл конфигурации:", options=options, index=None)
		
		with col2:
			
			loader = st.button("Загрузить Конфигурацию")
		
		
		if col2.loader:
			col3.empty()
			#col3.write(type(choice[0]))
			col3.write(choice[0])
			_load_savefile(name=f'./{choice[0]}')
	else:
		st.session_state['dd104L']['render_run_n'] = True
	
	

init()
render()
