import streamlit as st
import syslog

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
			raise RuntimeError(f"Error: {'/'.join([confiledir, name])} file does not exist!\n")
		# st.rerun()
	except Exception as e:
		msg = f"dd104: Ошибка при загрузке архивированного файла;\nПодробности:\n{type(e)}: {str(e)}\n"
		syslog.syslog(syslog.LOG_CRIT, msg)
		raise RuntimeError(e)

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
		return [(x,x) for x in files if x and x != '.']

def _loader(expander: st.expander, col3) -> None:
	
	filelist = _getnames('/opt/dd/dd104/Archive.tar.gz') #[('savename', 'filename'),(),()]
	with expander:
		for k, v in filelist:
			st.button(k, on_click=_load_savefile(col3, '/opt/dd/dd104/Archive.tar.gz', v))
