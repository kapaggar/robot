import re
import os, sys	
import unicodedata
import time
import signal
import tarfile
import HTML
import __main__ as main
from urlgrabber import urlopen,grabber
from Email import Email
from colorama import Fore, Back, Style

__all__ =  ['clean_results','collect_results','clear_collector_logs','collector_results','display_testresults','get_nightly',
			'get_rc_severity','get_rc_skipped','get_rc_ok','get_rc_nok','get_rc_error','get_skipped','get_success','get_failure','get_error','check_iso_exists','get_system_date','get_startProcess',
			'message','record_status','premailer','notify_email','terminate_self','br_text_to_html','monospace_text']

logfile_name	= ''
tracefile_name	= ''
result_file		= ''
mail_body		= ''
smtp_server		= 'smtp-relay.guavus.com'
test_status = {'SUCCESS':0,'FAIL':0,'ERROR':0,'SKIPPED':0}
test_table = {}
test_count = 0
mail_report_buffer = {}

def _get_exit_status():
	return {'SKIPPED':'0','SUCCESS':'1','FAIL':'2','ERROR':'3'}

def get_rc_severity(status):
	return_code_severity = _get_exit_status()
	return return_code_severity.get(status) and return_code_severity[status]

def add_skipped():
	test_status['SKIPPED'] +=1

def add_success():
	test_status['SUCCESS'] +=1

def add_failure():
	test_status['FAIL'] +=1

def add_error():
	test_status['ERROR'] +=1

def get_skipped():
	return int(test_status['SKIPPED'])

def get_success():
	return int(test_status['SUCCESS'])

def get_failure():
	return int(test_status['FAIL'])

def get_error():
	return int(test_status['ERROR'])

def get_max_rc_status(status1,status2):
	"""
	get_max_rc_status(status1,status2) : eg (get_rc_nok(),get_rc_ok()) will return exit status of get_rc_nok()
	"""
	if status1 == None or status2 == None:
		return
	else:
		sev1 = get_rc_severity(status1)
		sev2 = get_rc_severity(status2)
		if sev1 > sev2 :
			return status1
		else:
			return status2

def get_rc_skipped():
	return 'SKIPPED'

def get_rc_ok():
	return 'SUCCESS'

def get_rc_nok():
	return 'FAIL'

def get_rc_error():
	return 'ERROR'

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
			logfile.flush()
			logfile.close()
	except IOError:
		with open(logfile_name, "w+") as logfile:
			logfile.write(string_to_append)
	except Exception, err:
		print ("Unable to write to file %s"%(logfile_name,str(err)))
		terminate_self()

def append_to_mail(header,string_to_append):
	if not header :
		header = 'footnote'
	try:
		mail_report_buffer[header] = string_to_append
	except Exception, err:
		print ("Unable to add to mail buffer %s"%str(err))

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
	except Exception, err:
		message("Unable to make tar for writing %s"%str(err),{'style':'FATAL'})
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

def display_testresults():
	from prettytable import from_html
	pretty_str = ''
	for pretty_table in from_html(premailer()):
		pretty_str += str(pretty_table)
		pretty_str +=  "\n"
		pretty_str +=  '='*40
		pretty_str +=  "\n"
	return pretty_str

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
	'to_email' : 1,
	'style': 'NOK',    ok / nok / info / warning / debug / fatal
	eg: message ( " log this in %s " % self._name, {'to_log': '1' ,'style': 'DEBUG'}  )
	"""
	if arg_ref.get('to_trace'): # If Tracing set .. only explicitly set options are treated
		pass
	elif arg_ref.get('to_mail'): # If Mail set .. only explicitly set options are treated. helps in formatting
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
	elif arg_ref.get('style') and re.match("^warn",arg_ref['style'], re.IGNORECASE):
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
	if arg_ref.get('to_mail') and arg_ref['to_mail']:
		append_to_mail(sprintf_nocolor(message_string))
	if arg_ref.get('to_log') and arg_ref['to_log']:
		append_to_log ( sprintf_nocolor ( sprintf_timestamped ( message_string ) ) )
	if arg_ref.get('to_trace') and arg_ref['to_trace']:
		append_to_trace ( sprintf_nocolor ( sprintf_timestamped ( message_string ) ) )

def notify_email(config,msg,attachment=None):
	notifyFrom		= config['HOSTS']['notifyFrom']
	notifyTo		= config['HOSTS']['notifyTo']
	notifySubject	= config['HOSTS']['notifySubject']
	email_msg		= premailer()
	email_msg 		+= "\n\tlogfile and trace file for the run attached\n"
	email_msg		+= str(msg)
	notify 			= Email(smtp_server)
	notify.setFrom(notifyFrom)
	for email_address in notifyTo:
		notify.addRecipient(email_address)
	notify.setSubject(notifySubject)
	notify.setHtmlBody(email_msg)
	#notify.setTextBody(email_msg)
	if attachment:
		notify.addAttachment(attachment)
	return notify.send()

def br_text_to_html(msg="\n"):
	return msg.replace('\n', '<br/>')

def monospace_text(msg="<br/>"):
	return '<pre style="font-family: consolas,monospace;font-size:8pt" >' + msg + '</pre>'
	
def premailer():
	result_colors = {
		'SUCCESS'	:	'lime',
		'FAIL'		:	'red',
		'ERROR'		:	'yellow',
		'SKIPPED'	:	'silver',
	}
	myTable = HTML.Table(header_row=['Test Executed', 'Results'])
	for test_id in test_table:
		color = result_colors[test_table[test_id]]
		colored_result = HTML.TableCell(test_table[test_id], bgcolor=color)
		myTable.rows.append([test_id, colored_result])

	mySummary = HTML.Table(header_row=['Total','Skipped','Success', 'Failed','Error'])
	mySummary.rows.append([stats_values(),get_skipped(),get_success(),get_failure(),get_error()])
	return str(myTable) + str (mySummary)

def record_status(test_string,mystatus):
	"""
	'header','status': status = success / fail / skipped / error 
	eg: record_status ( " Test Case %s ." % self._name,'success' )
	"""
	message ( "RECORDKEEPING : %s|%s " % (test_string,mystatus),{'to_trace': '1' ,'style': 'TRACE'}  ) 
	if not test_string:
		return
	if not mystatus:
		return get_rc_skipped()
	status = mystatus.upper()
	most_severe_status = test_table.get(test_string,None)
	if most_severe_status and status != most_severe_status:
		my_severity = get_rc_severity(status)
		older_severity = get_rc_severity(test_table[test_string])
		if (my_severity < older_severity):
			return status

	if re.match("^success$",status, re.IGNORECASE):
		add_success()
	elif re.match("^fail$",status, re.IGNORECASE):
		add_failure()
	elif re.match("^skipped$",status, re.IGNORECASE):
		add_skipped()
	elif re.match("^error$",status, re.IGNORECASE):
		add_error()
	else:
		add_success()
	test_table[test_string] = status.upper()
	return status.upper()

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
    return Fore.CYAN + Back.BLACK +		Style.BRIGHT +	"DEBUG" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_fatal():
    return Fore.RED +	Back.YELLOW +	Style.BRIGHT +	"FATAL" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_unknown():
    return Fore.WHITE +	Back.BLACK +	Style.NORMAL +	"UNKNOWN" + Fore.RESET + Back.RESET + Style.RESET_ALL	+ " : "

def sprintf_trace():
    return "TRACE" + " : "

def sprintf_nocolor(string):
    regex = re.compile(ur'\x1B\[([0-9]{0,2}(;[0-9]{0,2})?)?[m|K]', re.UNICODE)
    return re.sub(regex,"", string)

def stats_values():
	return sum(test_status.values())

def terminate_self(mesg=None):
	try:
		if mesg :
			message ("%s"%mesg, {'style':'nok'} )
		else:
			message ("Killing Self", {'style':'nok'} )
		os.kill(os.getpid(), signal.SIGTERM)
		time.sleep(1)
		os.kill(os.getpid(), signal.SIGKILL)
	except Exception:
		sys.exit()

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
