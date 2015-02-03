#!/usr/bin/env python 
import paramiko
import string, re
import time
import traceback
import commands
import os,sys
import random
from configobj import ConfigObj,flatten_errors
from validate import Validator



class session(object):
	#    re_newlines = re.compile(r'[\n|\r]', re.UNICODE + re.I + re.M)
	#    re_color_codes = re.compile(r'(\[0m)|(\[0\d\;\d{2}m)', re.UNICODE)
	re_loginPrompt = re.compile( r"^(?P<enPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+>)\s*",re.M)
	re_enPrompt = re.compile( r"^(?P<enPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+#)\s*",re.M)
	re_cliPrompt = re.compile( r"^(?P<cliPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+\(config\)\s+#)\s*",re.M)
	re_shellPrompt = re.compile( r"^(?P<shellPrompt>\[\S+@\S+\s+\S+\]\s*#)\s*",re.M)
	re_pmxPrompt = re.compile( r"^(?P<pmxPrompt>pm\s+extension\s*>)\s*",re.M)    

	def __init__(self, host=None, username=None, password=None):
		self._host = host
		self._username = username
		self._password = password
		self._session = None
		self._stdin = None
		self._stdout = None
		self._stderr = None
		self.loginPrompt = None
		self.enPrompt = None
		self.cliPrompt  = None
		self.pmxPrompt = None
		self.shellPrompt = None
		self.currentPrompt = None
		self.newline = "\n"
		self.current_send_string = ''
		if host and username and password:
			self.connect()
			#self.checkPrompts()
	@property

	def username(self):
		return self._username
	
	def connect(self):
		""" Connect to the host at the IP address specified."""
		self.session = paramiko.SSHClient()
		self.session.load_system_host_keys()
		self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		self.session.connect(self._host, username=self._username, password=self._password, allow_agent=False, look_for_keys=False)
		self.transport = self.session.get_transport()
		#self.transport.set_keepalive(15)
		self.chan = self.session.invoke_shell()
		self.chan.settimeout(1200)
		self.chan.set_combine_stderr(True)

	def close(self):
		self.chan.close()
		self.transport.close()	    
		self.session.close()

	def disable_paging(remote_conn):
		return self.executeCli("no cli default paging enable")
	
	def getLoginPrompt(self,line):
		try:
			m1 = re.search("^(?P<loginPrompt>\S+(\s+\[\S+:\s+\S+\])?\s+>)\s*",line.strip(),re.MULTILINE)
			if m1:
				loginPrompt = m1.group("loginPrompt")
				return loginPrompt
			else:
				return False
		except Exception:
			print "error matching getLoginPrompt"
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
			print "error matching getLoginPrompt"
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
			print "error matching getLoginPrompt"
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
			print "error matching getLoginPrompt"
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

	def checkPrompts(self):
		self.write("enable\n")
		buff = self.read()
		buff = buff.splitlines()[-1]
		self.enPrompt =  buff
		self.loginPrompt =  self.enPrompt.replace("#",">")         
		self.write("configure terminal\n")
		buff = self.read()
		buff = buff.splitlines()[-1]
		self.cliPrompt =  buff         
		self.write("_exec bash\n")
		buff = self.read()
		buff = buff.splitlines()[-1]
		self.write("exit\n")
		self.shellPrompt =  buff         
		self.write("pmx\n")
		buff = self.read()
		buff = buff.splitlines()[-1]
		self.pmxPrompt =  buff
		#print "buff = %s , self.pmxPrompt %s" % (buff, self.pmxPrompt)
		self.write("quit")

	def getPrompt(self):
		self.write("")
		buff = self.read()
		buff = buff.splitlines()[-1]
		prompt =  self.tellPrompt(buff) 
		return prompt         

	def executeCli(self,cmd,prompt=re_cliPrompt,wait=1):
		prompt = self.getPrompt()
		if prompt == "cli":
			output = self.run_till_prompt(cmd,self.re_cliPrompt,wait)
			return output
		elif prompt == "shell":
			self.run_till_prompt("cli -m config",self.re_cliPrompt,wait=1)
			output = self.run_till_prompt(cmd,self.re_cliPrompt,wait)
			return output
		elif prompt == "pmx":
			self.run_till_prompt("quit",self.re_pmxPrompt,wait=1)
			self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			output = self.run_till_prompt(cmd, self.re_cliPrompt,wait=1)
		elif prompt == "login":
			self.run_till_prompt("en", self.re_enPrompt,wait=1)
			self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output = self.run_till_prompt(cmd, self.re_cliPrompt,wait=1)
			return output
		print "Was not able to run command #Todo Raise exception"
			


	def run_till_prompt(self, cmd, prompt=re_cliPrompt, wait=1):
		cmds = self._cmd_fix_input_data(cmd)
		for lines in cmds:
			 self.write(lines)
			 time.sleep(0.5)
		print ("sent command => \"%s\" on remote-host %s" %( cmd,self._host))
		 
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
			#print lastline
			lines =  data.splitlines()
			if len(lines) > 0 :
				lastline = lines[-1]
			else:
				return "Client Disconnected" #May be shell exited abruptly
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
		prompt = self.getPrompt()
		if prompt == "cli":
				output = self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
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


	def write(self, cmd):
		while not self.chan.send_ready():
			time.sleep(1)
		self.current_send_string = cmd	
		self.chan.send(cmd + self.newline )

	def read(self):
		data = ""
		time.sleep(1)
		if self.chan.recv_ready():
			data = unicode(self.chan.recv(4096), errors='replace')
		return data

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
	