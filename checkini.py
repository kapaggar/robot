#!/usr/bin/env python
import os, sys	
import signal
import re
import argparse
from configobj import ConfigObj,flatten_errors 
from validate import Validator 
from Toolkit import message


parser = argparse.ArgumentParser(description='Validate INI File' )
parser.add_argument("INIFILE",
					nargs=1,
					type=str,
					help='INI file to choose as Input')
args = parser.parse_args()
config_filename = args.INIFILE[0]
#results = config.validate(validator)
config = ConfigObj(config_filename,list_values=True,interpolation=True,configspec='config.spec')
validator = Validator()
results = config.validate(validator, preserve_errors=True)

if results != True:
	for (section_list, key, _) in flatten_errors(config, results):
		if key is not None:
			message ( 'The "%s" key in the section "%s" failed validation' % (key, ', '.join(section_list)), {'style':'DEBUG'} )
		else:
			message ( 'The following section was missing:%s ' % ", ".join(section_list) , {'style':'DEBUG'} )
	message ('Config file %s validation failed!'% config_filename, {'style':'FATAL'})
else :
	message ( 'INI is OK', {'style':'ok'} )
