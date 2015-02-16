#!/usr/bin/env python 
import paramiko
import string, re
import time
import traceback
import socket
import commands
import os,sys
import random
from configobj import ConfigObj,flatten_errors
from validate import Validator
from Toolkit import message


class session(object):
	#    re_newlines = re.compile(r'[\n|\r]', re.UNICODE + re.I + re.M)
	#    re_color_codes = re.compile(r'(\[0m)|(\[0\d\;\d{2}m)', re.UNICODE)
	re_loginPrompt 	= re.compile( r"^(?P<enPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+>)\s*",re.M)
	re_enPrompt 	= re.compile( r"^(?P<enPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+#)\s*",re.M)
	re_cliPrompt 	= re.compile( r"^(?P<cliPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+\(config\)\s+#)\s*",re.M)
	re_shellPrompt 	= re.compile( r"^(?P<shellPrompt>\[\S+@\S+\s+\S+\]\s*#)\s*",re.M)
	re_pmxPrompt 	= re.compile( r"^(?P<pmxPrompt>pm\s+extension\s*>)\s*",re.M)    

	def __init__(self, host=None, username=None, password=None):
		self._host 					= host
		self._username 				= username
		self._password 				= password
		self._session 				= None
		self._stdin 				= None
		self._stdout 				= None
		self._stderr 				= None
		self.loginPrompt 			= None
		self.enPrompt 				= None
		self.cliPrompt  			= None
		self.pmxPrompt 				= None
		self.shellPrompt 			= None
		self.currentPrompt 			= None
		self.newline 				= "\n"
		self.current_send_string	= ''
		if host and username and password:
			self.connect()
			#self.checkPrompts()
	@property

	def username(self):
		return self._username
	
	def connect(self):
		""" Connect to the host at the IP address specified."""
		retry = 0
		self.session = paramiko.SSHClient()
		self.session.load_host_keys(os.path.expanduser("/dev/null"))
		#self.session.load_system_host_keys()
		self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		while retry < 5:
			try:
				self.session.connect(self._host, username=self._username, password=self._password, allow_agent=False, look_for_keys=False)
				self.transport = self.session.get_transport()
				#self.transport.set_keepalive(15)
				self.chan = self.session.invoke_shell()
				self.chan.settimeout(1200)
				self.chan.set_combine_stderr(True)
				return
			except socket.error, (value):
				message ( "SSH Connection refused, will retry in 5 seconds", {'to_log':'1' , 'style': 'WARN'} )
				time.sleep(5)
				retry += 1
			except paramiko.BadHostKeyException:
				message ( "%s has an entry in ~/.ssh/known_hosts and it doesn't match" % self._host, {'to_log':1 , 'style': 'FATAL'} ) 
				message ( 'Edit that file to remove the entry and then hit return to try again', {'to_log':1 , 'style': 'DEBUG'} ) 
				rawinput('Hit Enter when ready')
				retry += 1
			except EOFError:
				message ( 'Unexpected Error from SSH Connection, retrying in 5 seconds', {'to_log':1 , 'style': 'WARN'} ) 
				time.sleep(5)
				retry += 1
				message ( 'Could not establish SSH connection', {'to_log':1 , 'style': 'FATAL'} ) 

	def close(self):
		self.chan.close()
		self.transport.close()	    
		self.session.close()
	
	def getLoginPrompt(self,line):
		try:
			m1 = re.search("^(?P<loginPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+>)\s*",line.strip(),re.MULTILINE)
			if m1:
				loginPrompt = m1.group("loginPrompt")
				return loginPrompt
			else:
				return False
		except Exception:
			message ( "Error matching getLoginPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False
			
	def getenPrompt(self,line):
		try:
			m1 = re.search("^(?P<enPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+#)\s*",line.strip(),re.MULTILINE)
			if m1:
				enPrompt = m1.group("enPrompt")
				return enPrompt
			else:
				return False
		except Exception:
			message ( "error matching getenPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

	def getcliPrompt(self,line):
		try:
			m1 = re.search("^(?P<cliPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+\(config\)\s+#)\s*",line.strip(),re.MULTILINE)
			if m1:
				cliPrompt = m1.group("cliPrompt")
				return cliPrompt
			else:
				return False
		except Exception:
			message ( "error matching getcliPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False
		
	def getshellPrompt(self,line):
		try:
			m1 = re.search("^(?P<shellPrompt>\[\S+@\S+\s+\S+\]\s*#)\s*",line.strip(),re.MULTILINE)
			if m1:
				shellPrompt = m1.group("shellPrompt")
				return shellPrompt
			else:
				return False
		except Exception:
			message ( "error matching getshellPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

	def tellPrompt(self,line):
		try:
			if self.getshellPrompt(line):
				return "shell"
			elif self.getcliPrompt(line):
				return "cli"
			elif self.getenPrompt(line):
				return "en"
			elif self.getLoginPrompt(line):
				return "login"
			elif line.find("pm extension>")!= -1:
				return "pmx"
			else:
				return None
		except Exception:
			errorMsg = "Error:  %s" % traceback.format_exc()
			BuiltIn().fail(errorMsg)
			return False

	def checkFileExist(self,filenameFullPath):
		command = '[ -f %s ] && echo "File exists" || echo "File does not exists"'%filenameFullPath
		output= self.executeShell(command).split("\n")[-1]
		if output == "File exists":
			trace.info("File '%s' exists"%filenameFullPath)
			return True
		else:
			trace.trace("File '%s' doesn't exists"%filenameFullPath)
		return False 

	def getPrompt(self):
		got_prompt = False
		timeOut = 60
		while timeOut > 0:
			self.write("")
			buff = self.read()
			lines = buff.splitlines()
			if len(lines) > 0:
				buff = lines[-1]
				if buff and not buff.isspace():   # the string is non-empty
					got_prompt = True
					break
				else :
					timeOut = timeOut - 1
			else :
				timeOut = timeOut - 1
		try:
			if got_prompt:
				prompt = self.tellPrompt(buff) 
				return prompt   
		except Exception:
			message ( "Unable to reach a Prompt in getPrompt", {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

	def executeCli(self,cmd,prompt=re_cliPrompt,wait=1):
		output = ''
		prompt = self.getPrompt()
		if prompt == "cli":
			output += self.run_till_prompt(cmd,self.re_cliPrompt,wait)
			return output
		elif prompt == "shell":
			self.run_till_prompt("cli -m config",self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd,self.re_cliPrompt,wait)
			return output
		elif prompt == "pmx":
			output += self.run_till_prompt("quit",self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_cliPrompt,wait=1)
			return output
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_cliPrompt,wait=1)
			return output
		elif prompt == "en":
			output += self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_cliPrompt,wait=1)
			return output
		#Todo Raise exception"
		message ( "Was not able to run command %s on prompt=> %s on Host %s" % (cmd,prompt,self._host),
				 {'to_log':1 , 'style': 'FATAL'}
				 ) 


	def run_till_prompt(self, cmd, prompt=re_cliPrompt, wait=1):
		cmds = self._cmd_fix_input_data(cmd)
		for lines in cmds:
			 self.write(lines)
			 time.sleep(0.5)
		message ( "sending => \"%s\" on remote-host %s" %( cmd,self._host),
				 {'to_stdout':1, 'to_log':1 , 'style': 'OK'}
				 ) 
		data = ''
		output = ''
		lastline = ''
		while True :
			data =  self.chan.recv(4096)
			data = data.replace('\r', '')
			if not output:
					 data = data.replace('.*\n'  ,'')
					 data = data.replace(cmd  ,'')
					 output += data
			else:
					 output += data
			#debug
			lines =  data.splitlines()
			if len(lines) > 0 :
				lastline = lines[-1]
			else:
				message ( "Client Disconnected",
						 {'to_stdout':1, 'to_log':1 , 'style': 'NOK'}
						 ) 
				return False #May be shell exited abruptly
			if isinstance(prompt,re._pattern_type):
				if prompt.match(lastline):
					output = re.sub(prompt,'',output)
					break
			else:
				if prompt in lastline:
					break
					if not self.chan.recv_ready():	   
						time.sleep(wait)
		output.lstrip()
		return output

	def executePmx(self,cmd):
		output = ''
		prompt = self.getPrompt()
		if prompt == "cli":
			output += self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt("quit", self.re_cliPrompt,wait=1)
			return output
		elif prompt == "shell":
			output = self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt("exit", self.re_shellPrompt,wait=1)
			return output
		elif prompt == "pmx":
			output = self.run_till_prompt(cmd, self.re_pmxPrompt,wait=1)
			return output
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt("quit", self.re_cliPrompt,wait=1)
			return output

	def executeShell(self,cmd):
		output = ''
		prompt = self.getPrompt()
		if prompt == "cli":
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			return output
		elif prompt == "shell":
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			return output
		elif prompt == "pmx":
			output = self.run_till_prompt(cmd, self.re_pmxPrompt,wait=1)
			return output
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			return output

	def write(self, cmd):
		timeOut = 60
		sent_data = False
		while timeOut > 0 :
			if self.chan.send_ready():
				self.current_send_string = cmd	
				self.chan.send(cmd + self.newline )
				sent_data = True
				break
			else:
				time.sleep(0.5)
				timeOut = timeOut - 1
		try:
			if sent_data:
				return True
		except Exception:
			message ( "Unable to write cmd %s to Channel (Channel not Ready)"%cmd,
					 {'to_stdout':1, 'to_log':1 , 'style': 'FATAL'}
					 ) 
			return False


	def read(self):
		data = ""
		got_data = False
		timeOut = 120
		while timeOut > 0 :
			if self.chan.recv_ready():
				data = unicode(self.chan.recv(4096), errors='replace')
				got_data = True
				break
			else:
				time.sleep(0.5)
				timeOut = timeOut - 1
		try:
			if got_data:
				return data
		except Exception:
			message ( "Unable to read from channel" ,
					 {'to_stdout':1, 'to_log':1 , 'style': 'FATAL'}
					 ) 
			return False

	def read_all(self):
		data = ""
		while self.chan.recv_ready():
			data += unicode(self.chan.recv(4096), errors='replace')
		return data
		
	def _cmd_fix_input_data(self, input_data):
		if input_data is not None:
			if len(input_data) > 0:
				if '\\n' in input_data:
					lines = input_data.split('\\n')
					input_data = '\n'.join(lines)
			return input_data.split('\n')
		return []


	def _clean_output_data(self, output):
		output = output.strip()
		output = self.re_newlines.sub(' ', output)
		output = output.split(' ')
		 
		out = [x.strip() for x in output if x not in ['', '\r', '\r\n', '\n\r', '\n']]
		ret = list()
		 
		for line in out:
			new_line = filter(lambda x: x in string.printable, line)
			new_line = self.re_color_codes.sub('', new_line)
			ret.append(new_line)
		return ret   


	def __del__(self):
		if self.session != None:
			self.session.close()


if __name__ == '__main__':
	ssh_session = session('192.168.173.211', username='admin', password='admin@123')
	prompt = ssh_session.getPrompt()
	
