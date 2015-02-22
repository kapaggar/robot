import re
import os, sys
import time
import signal
import __main__ as main
from colorama import Fore, Back, Style

logfile_name = ''
tracefile_name = ''

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

def sprintf_timestamped(string):
    timestamped_string = ''
    strings = map(str.strip, string.split('\n'))
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
    return Fore.YELLOW +Back.BLUE +		Style.DIM +		"DEBUG" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_fatal():
    return Fore.RED +	Back.YELLOW +	Style.BRIGHT +	"FATAL" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_unknown():
    return Fore.WHITE +	Back.BLACK +	Style.NORMAL +	"UNKNOWN" + Fore.RESET + Back.RESET + Style.RESET_ALL	+ " : "

def sprintf_trace():
    return "TRACE" + " : "

def sprintf_nocolor(string):
    regex = re.compile(ur'\x1B\[([0-9]{0,2}(;[0-9]{0,2})?)?[m|K]', re.UNICODE)
    return re.sub(regex,"", string)

def get_system_date():
    now = time.strftime("%c")
    return now

def terminate_self(mesg):
    if mesg :
        message ("%s"%mesg, {'style':'nok'} )
    else:
        message ("Killing Self", {'style':'nok'} )
    os.kill(os.getpid(), signal.SIGTERM)

if __name__ == '__main__':
    pass