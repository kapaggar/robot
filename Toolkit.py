import re
import os, sys
import unicodedata
import time
import signal
import tarfile
import __main__ as main
from urlgrabber import urlopen,grabber
from Email import Email
from colorama import Fore, Back, Style

logfile_name	= ''
tracefile_name	= ''
result_file		= ''

def append_to_trace(string_to_append):
	"""
	Append_to_trace(string_to_append)
	"""
	global tracefile_name
	if not string_to_append:
		return 1
	if not tracefile_name:
		try:
			if os.environ["TRACEFILE_NAME"]:
				tracefile_name = os.environ["TRACEFILE_NAME"]
		except KeyError:
			my_script		=	os.path.basename(main.__file__)
			my_prefix		=	my_script.split('.')[0]
			my_timestamp	=	time.strftime("%Y%m%d-%H%M%S")
			my_suffix		=	"tra"
			tracefile_name	=	my_prefix + "." + my_timestamp  + "." + my_suffix
	append_to_file(tracefile_name,string_to_append)

def append_to_log(string_to_append):
	"""
	Append_to_log(string_to_append)
	"""
	global logfile_name
	if not string_to_append:
		return 1
	if not logfile_name:
		try:
			if os.environ["LOGFILE_NAME"]:
				logfile_name = os.environ["LOGFILE_NAME"]
		except KeyError:
			my_script		=	os.path.basename(main.__file__)
			my_prefix		=	my_script.split('.')[0]
			my_timestamp	=	time.strftime("%Y%m%d-%H%M%S")
			my_suffix		=	"log"
			logfile_name	=	my_prefix + "." + my_timestamp  + "." + my_suffix
		initialise_log_trace_and_truncate(logfile_name)
	append_to_file(logfile_name,string_to_append)

def append_to_file(logfile_name,string_to_append):
    try:
        with open(logfile_name, "a") as logfile:
            logfile.write(string_to_append)
            logfile.close()
    except IOError:
        with open(logfile_name, "w+") as logfile:
            logfile.write(string_to_append)

def check_iso_exists(config):
	_iso_path	= config['HOSTS']['iso_path']
	if _iso_path == "nightly" :
		nightly_base_dir = config['HOSTS']['nightly_dir']
		try:
			full_iso_path = get_nightly (nightly_base_dir)
			return full_iso_path
		except Exception:
			message("Unable to get nightly from %s" % nightly_base_dir ,{'style':'FATAL'})
			return False
	elif _iso_path is not None:
		if not _iso_path.endswith(".iso"):
			message("IMG provided instead of ISO file %s" % _iso_path ,{'style':'FATAL'})
		base_dir = os.path.dirname(_iso_path)
		iso_name = os.path.basename(_iso_path)
		try:
			page = urlopen(base_dir)
		except grabber.URLGrabError as e:
			message("Unable to get iso from %s" % base_dir ,{'style':'FATAL'})
			return False
		page_read = page.read()
		re_mfgiso = re.compile( r"(?P<mfgiso>"+ iso_name + ")",re.M)
		match = re_mfgiso.search(page_read)
		if match:
			iso_filename = match.group("mfgiso")
			return iso_filename
		else :
			message("Unable to get iso from %s" % base_dir ,{'style':'FATAL'})
			return False
	else:
		message("Please correct nightly field in input ini file %s" ,{'style':'FATAL'})
		return False

def clean_results(file_name):
	if not file_name:
		return
	if not os.path.exists(file_name):
		print "File '%s' does not exist. Already cleaned ?" % file_name
		return 
	if not os.path.isfile(file_name):
		print "Attachment '%s' is not a file.  Not deleting" % file_name
		return
	try:
		os.remove(file_name)
	except Exception:
		message("Unable to remove file %s" % file_name ,{'style':'FATAL'})
	
def collect_results():
	global tracefile_name
	global logfile_name
	global result_file
	result_file_ext = ".tgz"
	result_file = os.path.splitext(logfile_name)[0] + result_file_ext
	try:
		tar = tarfile.open(result_file, "w:gz")
		for name in [tracefile_name, logfile_name]:
			tar.add(name)
		tar.close()
		return result_file
	except Exception:
		message("Unable to make tar for writing",{'style':'FATAL'})
		return False

def clear_collector_logs():
	CommonLogs_path = os.environ["INSTALL_PATH"]  + "/" + "hubrix/GData/Logs/CommonLogs"
	oldpwd = os.getcwd() 
	os.chdir(CommonLogs_path)
	filelist = [ f for f in os.listdir(CommonLogs_path) if f.endswith(".log") ]
	for f in filelist:
		os.remove(f)
	os.chdir(oldpwd)
		
def collector_results():
	result_file_ext = ".tgz"
	result_file = "collector_sanity_logs" + result_file_ext
	Logs_path = os.environ["INSTALL_PATH"]  + "/" + "hubrix/GData/Logs/"
	message ("Collector sanity logs are placed in %s" % Logs_path ,{'style' : 'info'})
	try:
		old_pwd = os.getcwd()
		os.chdir(Logs_path)
		tar = tarfile.open(result_file, "w:gz")
		tar.add("CommonLogs")
		tar.close()
		os.chdir(old_pwd)
		return Logs_path + result_file
	except Exception:
		message("Unable to make tar for writing",{'style':'FATAL'})
		return False

def get_nightly(base_path):
	re_mfgiso = re.compile( r"(?P<mfgiso>mfgcd-\S+?.iso)",re.M)
	try:
		page = urlopen(base_path)
	except grabber.URLGrabError as e:
		raise IOError
		return False
	page_read = page.read()
	match = re_mfgiso.search(page_read)
	if match:
		iso_filename = match.group("mfgiso")
		return base_path + "/" + iso_filename
	return False

def get_system_date():
    now = time.strftime("%c")
    return now

def get_startProcess(process):
		if not process:
			return False
		try:
			m1 = re.search(ur'^\s*?(?P<start_time>\S+)\s+.*?$',process,re.MULTILINE)
			if m1:
				start_time = m1.group("start_time")
				pidInfo = start_time.partition("-")
				if pidInfo[1] == '-':
					# there is a day
					days = int(pidInfo[0])
					rest = pidInfo[2].split(":")
					hours = int(rest[0])
					minutes = int(rest[1])
					seconds = int(rest[2])
				else:
					days = 0
					rest = pidInfo[0].split(":")
					if len(rest) == 3:
						hours = int(rest[0])
						minutes = int(rest[1])
						seconds = int(rest[2])
					elif len(rest) == 2:
						hours = 0
						minutes = int(rest[0])
						seconds = int(rest[1])
					else:
						hours = 0
						minutes = 0
						seconds = int(rest[0])
				
				# get the start time
				secondsSinceStart = days*24*3600 + hours*3600 + minutes*60 + seconds
				return secondsSinceStart
			else:
				return False
		except Exception:
			message ( "Error matching start_time" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

def initialise_log_trace_and_truncate(logfile_name):
	'''
	Its job is to truncate the log and trace file if present.
	#Todo create a log dir if not present and then inside dir write log
	'''
	global tracefile_name
	tracefile_ext = ".tra"
	tracefile_name = os.path.splitext(logfile_name)[0] + tracefile_ext
	os.environ["LOGFILE_NAME"] 		= logfile_name
	os.environ["TRACEFILE_NAME"]	= tracefile_name

	# Truncate Logfile
	try:
		with open(logfile_name, "w") as logfile:
			logfile.truncate()
			logfile.close()
	except IOError:
		message("Unable to truncate logfile for writing",{'style':'FATAL'})
		terminate_self("Exiting")

	# Truncate Tracefile
	try:
		with open(tracefile_name, "w") as tracefile:
			tracefile.truncate()
			tracefile.close()
	except IOError:
		message("Unable to truncate tracefile for writing",{'style':'FATAL'})
		terminate_self("Exiting")

def message(message_string,arg_ref):
	"""
	'to_log' : 1,
	'to_stdout' : 1,
	'to_trace' : 1,
	'style': 'NOK',    ok / nok / info / warning / debug / fatal
	eg: message ( " log this in %s " % self._name, {'to_log': '1' ,'style': 'DEBUG'}  )
	"""
	if arg_ref.get('to_trace'): # If Tracing set .. only explicitly set options are treated
		pass 
	else: # If Tracing not set .. default logging to all targets
		if not arg_ref.get('to_stdout'):
			arg_ref['to_stdout'] = 1
		if not arg_ref.get('to_log'): 
			arg_ref['to_log'] = 1
		if not arg_ref.get('to_trace'):
			arg_ref['to_trace'] = 1

	if arg_ref.get('style') and re.match("^ok$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_ok() +			message_string
	elif arg_ref.get('style') and re.match("^nok$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_nok() +		message_string
	elif arg_ref.get('style') and re.match("^info$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_info() +		message_string
	elif arg_ref.get('style') and re.match("^warning$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_warning() +	message_string
	elif arg_ref.get('style') and re.match("^debug$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_debug() + 		message_string
	elif arg_ref.get('style') and re.match("^fatal$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_fatal()+		message_string
	elif arg_ref.get('style') and re.match("^trace$",arg_ref['style'], re.IGNORECASE):
		message_string = sprintf_trace()+		message_string
	else:
		message_string = sprintf_unknown() +	message_string
	if arg_ref.get('to_stdout') and arg_ref['to_stdout']:
		print message_string
	if arg_ref.get('to_log') and arg_ref['to_log']:
		append_to_log ( sprintf_nocolor ( sprintf_timestamped ( message_string ) ) )
	if arg_ref.get('to_trace') and arg_ref['to_trace']:
		append_to_trace ( sprintf_nocolor ( sprintf_timestamped ( message_string ) ) )

def notify_email(config,msg,attachment=None):
	notifyFrom		= config['HOSTS']['notifyFrom']
	notifyTo		= config['HOSTS']['notifyTo']
	email_msg 		= "\n\tlogfile and trace file for the run attached\n"
	email_msg 		+= "\t==================\n"
	email_msg		+= str(msg)
	notify 			= Email("mx1.guavus.com")
	notify.setFrom(notifyFrom)
	for email_address in notifyTo:
		notify.addRecipient(email_address)
	notify.setSubject("Hubrix notification")
	notify.setTextBody(email_msg)
	if attachment:
		notify.addAttachment(attachment)
	notify.send()

def sprintf_timestamped(message):
	timestamped_string = ''
	if isinstance(message, str):
		strings = map(str.strip, message.split('\n'))
	elif isinstance(message, unicode):
		strings = map(str.strip, unicodedata.normalize('NFKD', message).encode('ascii','ignore').split('\n'))
	else:
		strings = "<NON STRING - NON UNICODE - LOG"
	for line in strings:
		timestamped_string += time.strftime("%b %e %H:%M:%S ") + str(line) + " \n"
	return timestamped_string

def sprintf_ok():
    return Fore.WHITE +	Back.GREEN +	Style.BRIGHT +	"OK" + Fore.RESET + Back.RESET + Style.RESET_ALL 		+ " : "

def sprintf_nok():
    return Fore.WHITE +	Back.RED +		Style.BRIGHT +	"NOK" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_info():
    return Fore.WHITE +	Back.BLUE +		Style.DIM +		"INFO" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_warning():
    return Fore.CYAN +	Back.BLUE +		Style.BRIGHT +	"WARN" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_debug():
    return Fore.CYAN +Back.BLACK +		Style.BRIGHT +	"DEBUG" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_fatal():
    return Fore.RED +	Back.YELLOW +	Style.BRIGHT +	"FATAL" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_unknown():
    return Fore.WHITE +	Back.BLACK +	Style.NORMAL +	"UNKNOWN" + Fore.RESET + Back.RESET + Style.RESET_ALL	+ " : "

def sprintf_trace():
    return "TRACE" + " : "

def sprintf_nocolor(string):
    regex = re.compile(ur'\x1B\[([0-9]{0,2}(;[0-9]{0,2})?)?[m|K]', re.UNICODE)
    return re.sub(regex,"", string)

def terminate_self(mesg):
    if mesg :
        message ("%s"%mesg, {'style':'nok'} )
    else:
        message ("Killing Self", {'style':'nok'} )
    os.kill(os.getpid(), signal.SIGTERM)

def write_to_file(file_name,string_to_write):
    try:
        with open(file_name, "w") as file_handle:
            file_handle.write(string_to_write)
            file_handle.close()
    except IOError:
        with open(file_name, "w+") as file_handle:
            file_handle.write(string_to_write)

if __name__ == '__main__':
    pass