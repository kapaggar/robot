import re
import os, sys
import time
import __main__ as main
from colorama import Fore, Back, Style

def message(message_string,arg_ref):
	"""
		'to_log' : 1,
		'to_stdout' : 1,
		'to_trace' : 1,
		'style': 'NOK',    ok / nok / info / warning / debug / fatal
	"""
	if not arg_ref.get('to_stdout'):
		arg_ref['to_stdout'] = 1
	if not arg_ref.get('to_log'):
		arg_ref['to_log'] = 1

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
	else:
		message_string = sprintf_unknown() +	message_string
	if arg_ref.get('to_stdout'):
		print message_string
	if arg_ref.get('to_log'):
		append_to_log ( sprintf_nocolor ( sprintf_timestamped ( message_string ) ) )


def append_to_log(string_to_append):
	logfile_name = ''
	if not string_to_append :
		return 1 
	try:
		if os.environ["LOGFILE_NAME"]:
			logfile_name = os.environ["LOGFILE_NAME"]
	except KeyError: 
		my_script		=	os.path.basename(main.__file__)
		my_prefix		=	my_script.split('.')[0]
		my_PID			=	str(os.getpid()) 
		my_suffix		=	"log"
		logfile_name	=	my_prefix + "." + my_PID  + "." + my_suffix
		
	append_to_file(logfile_name,string_to_append)

def append_to_file(logfile_name,string_to_append):
	try:
		with open(logfile_name, "a") as logfile:
			logfile.write(string_to_append)
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
    return Fore.YELLOW +	Back.BLUE +	Style.DIM +		"DEBUG" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_fatal():
    return Fore.GREEN +	Back.BLUE +		Style.BRIGHT +	"FATAL" + Fore.RESET + Back.RESET + Style.RESET_ALL		+ " : "

def sprintf_unknown():
    return Fore.WHITE +	Back.BLACK +	Style.NORMAL +	"UNKNOWN" + Fore.RESET + Back.RESET + Style.RESET_ALL	+ " : "

def sprintf_nocolor(string):
	ansi_escape = re.compile("\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]", re.UNICODE,re.DOTALL)
	ansi_escape.sub('', string)
	return string

def get_system_date():
	now = time.strftime("%c")
	return now