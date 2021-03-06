#!/usr/bin/env python 
import paramiko
import string, re
import time
import traceback
import socket
import commands
import os,sys
import random
import logging
from logging.handlers import MemoryHandler
from configobj import ConfigObj,flatten_errors
from validate import Validator
from Toolkit import *

__all__ = ['executeCli','executePmx','executeShell','executeCliasUser','executeShellasUser',]

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
		self.session				= None
		self.transport				= None
		self.chan					= None
		self.newline 				= "\n"
		self.current_send_string	= ''
		if host and username and password:
			try:
				self.connect()
				message ( "session init for host %s@%s " % (self._username,self._host),{'to_trace': '1' ,'style': 'OK'}  )
			except Exception, e:
				message ( "session init FAILED for host %s@%s %s" % (self._username,self._host,str(e)),{'to_trace': '1' ,'style': 'NOK'}  )
				raise
	@property
	
	def __del__(self):
		try:
			if self.session:
				message ( "session del for  %s@%s " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
				self.session.close()
		except Exception, err:
			message ( "error deleting session del for %s@%s " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )

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

	def _read(self):
		data = ""
		got_data = False
		timeOut = 120
		while timeOut > 0 :
			if self.chan.recv_ready():
				data = unicode(self.chan.recv(4096), errors='ignore')
				got_data = True
				break
			else:
				time.sleep(0.5)
				timeOut = timeOut - 1
		try:
			if got_data:
				return data
		except Exception:
			message ( "Unable to read from channel" ,{'to_stdout':1, 'to_log':1 , 'style': 'FATAL'}) 
			return False
	
	def _read_all(self):
		data = ""
		while self.chan.recv_ready():
			data += unicode(self.chan.recv(4096), errors='ignore')
		return data

	def connect(self):
		""" Connect to the host at the IP address specified."""
		retry = 5
		while retry > 0:
			try:
				self.session = paramiko.SSHClient()
				self.session.load_host_keys(os.path.expanduser("/dev/null"))
				#self.session.load_system_host_keys()
				self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
				message ( "making coonection on host %s@%s" % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
				self.session.connect(self._host, username=self._username, password=self._password, allow_agent=False, look_for_keys=False,timeout=60,banner_timeout=60)
				message ( "connect on host %s@%s ok " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
				self.transport = self.session.get_transport()
				self.transport.set_keepalive(5)
				message ( "transport on host %s@%s ok" % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
				#self.transport.set_keepalive(15)
				self.chan = self.session.invoke_shell()
				message ( "shell invoke on host %s@%s ok " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
				self.chan.settimeout(1200)
				self.chan.set_combine_stderr(True)
				self.chan.send_ready()
				return
			except (paramiko.SSHException, EOFError, AttributeError):
				message ( "SSH shell invoke refused, will retry in 10 seconds", { 'style': 'DEBUG' } )
				time.sleep(10)
				retry -= 1
			except socket.error, (value):
				message ( "SSH Connection refused, will retry in 10 seconds", { 'style': 'DEBUG' } )
				time.sleep(10)
				retry -= 1
			except	paramiko.AuthenticationException:
				message ( 'Incorrect password %s for %s in %s'%(self._username,self._password,self._host), {'style': 'TRACE'} ) 
				terminate_self("Exiting")
			except paramiko.BadHostKeyException:
				message ( "%s has an entry in ~/.ssh/known_hosts and it doesn't match" % self._host, { 'style': 'FATAL' } ) 
				message ( 'Edit  ~/.ssh/known_hosts file to remove the entry and try again', {'style': 'TRACE'} ) 
				terminate_self("Exiting")
			except Exception,err:
				message ( 'Unexpected Error %s from SSH Connection, retrying in 5 seconds'%str(err), { 'style': 'DEBUG' } ) 
				time.sleep(5)
				retry -= 1
		return False

	def close(self):
		self.chan.close()
		message ( "channel closed for host %s@%s " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		self.transport.close()
		message ( "Transport closed for host %s@%s " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		self.session.close()
		message ( "Session closed for host %s@%s " % (self._username,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )

	def executeCli(self,cmd,prompt=re_cliPrompt,wait=1,timeout=60):
		output = ''
		prompt = self.getPrompt()
		message ( "executeCli| prompt=> %s| cmd=> %s| host=> %s|" % (prompt,cmd,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		if prompt == "cli":
			output += self.run_till_prompt(cmd,self.re_cliPrompt,wait,timeout)
			pass
		elif prompt == "shell":
			self.run_till_prompt("cli -m config",self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd,self.re_cliPrompt,wait,timeout)
			pass
		elif prompt == "pmx":
			output += self.run_till_prompt("quit",self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_cliPrompt,wait,timeout)
			pass
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_cliPrompt,wait,timeout)
			pass
		elif prompt == "en":
			output += self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_cliPrompt,wait,timeout)
			pass
		else:#Todo Raise exception"
			message ( "Was not able to run command %s on prompt=> %s on Host %s" % (cmd,prompt,self._host),{'style': 'FATAL'})
		message ( "host %s| prompt=> %s |cmd=> %s|output=>[%s] " % (self._host,cmd,prompt,output),{'to_trace': '1' ,'style': 'TRACE'})
		return output
		
	def executePmx(self,cmd,wait=1,timeout=60):
		output = ''
		prompt = self.getPrompt()
		message ( "In executePmx prompt = %s cmd = %s host = %s" % (prompt,cmd,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		if prompt == "cli":
			output += self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_pmxPrompt,wait,timeout)
			output += self.run_till_prompt("quit", self.re_cliPrompt,wait=1)
			pass
		elif prompt == "shell":
			output = self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_pmxPrompt,wait,timeout)
			output += self.run_till_prompt("exit", self.re_shellPrompt,wait=1)
			pass
		elif prompt == "pmx":
			output = self.run_till_prompt(cmd, self.re_pmxPrompt,wait=1)
			pass
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("configure terminal", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt("pmx", self.re_pmxPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_pmxPrompt,wait,timeout)
			output += self.run_till_prompt("quit", self.re_cliPrompt,wait=1)
			pass
		else:#Todo Raise exception"
			message ( "Was not able to run command %s on prompt=> %s on Host %s" % (cmd,prompt,self._host),{'style': 'FATAL'})
		message ( "host %s| prompt=> %s |cmd=> %s|output=>[%s] " % (self._host,cmd,prompt,output),{'to_trace': '1' ,'style': 'TRACE'})
		return output

	def executeShell(self,cmd,wait=1,timeout=300):
		output = ''
		prompt = self.getPrompt()
		message ( "In executeShell prompt = %s cmd = %s host = %s" % (prompt,cmd,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		if prompt == "cli":
			output += self.run_till_prompt("_shell", self.re_shellPrompt)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait,timeout)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt)
			pass
		elif prompt == "shell":
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait,timeout)
			pass
		elif prompt == "pmx":
			output += self.run_till_prompt("quit", self.re_cliPrompt)
			output += self.run_till_prompt("_shell", self.re_shellPrompt)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait,timeout)
			pass
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt)
			output += self.run_till_prompt("_shell", self.re_shellPrompt)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait,timeout)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt)
			pass
		else:#Todo Raise exception"
			message ( "Was not able to run command %s on prompt=> %s on Host %s" % (cmd,prompt,self._host),{'style': 'FATAL'})
		message ( "host %s| prompt=> %s |cmd=> %s|output=>[%s] " % (self._host,cmd,prompt,output),{'to_trace': '1' ,'style': 'TRACE'})
		return output

	def executeShellasUser(self,user,cmd,wait=1,timeout=180):
		# su - reflex -c "cli -m config <<< 'conf wr'"  
		output = ''
		prompt = self.getPrompt()
		message ( "In executexecuteShellasUser prompt = %s cmd = %s host = %s" % (prompt,cmd,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		if prompt == "cli":
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			output += self.run_till_prompt('runuser -l %s -c \"%s\" '% (user,cmd), self.re_shellPrompt,wait,timeout)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			return output
		elif prompt == "shell":
			output += self.run_till_prompt('runuser -l %s -c \"%s\" '% (user,cmd), self.re_shellPrompt,wait,timeout)
			return output
		elif prompt == "pmx":
			output += self.run_till_prompt("quit", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output = self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			return output
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			return output
		
	def executeCliasUser(self,user,cmd,wait=1,timeout=180):
		# su - reflex -c "cli -m config <<< 'conf wr'"  
		output = ''
		prompt = self.getPrompt()
		message ( "In executexecuteCliasUser prompt = %s cmd = %s host = %s" % (prompt,cmd,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
		if prompt == "cli":
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			output += self.run_till_prompt('runuser -l %s -c \"cli -m config <<< \'%s\'\" '% (user,cmd), self.re_shellPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			return output
		elif prompt == "shell":
			output += self.run_till_prompt('runuser -l %s -c \"cli -m config <<< \'%s\'\" '% (user,cmd), self.re_shellPrompt,wait=1,timeout=5)
			return output
		elif prompt == "pmx":
			output += self.run_till_prompt("quit", self.re_cliPrompt,wait=1)
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output = self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			return output
		elif prompt == "login":
			output += self.run_till_prompt("en", self.re_enPrompt,wait=1)
			output += self.run_till_prompt("_shell", self.re_shellPrompt,wait=1)
			output += self.run_till_prompt(cmd, self.re_shellPrompt,wait=1)
			output += self.run_till_prompt("cli -m config", self.re_cliPrompt,wait=1)
			return output
		
		
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
			message ( "Error matching getenPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
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
			message ( "Error matching getcliPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
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
			message ( "Error matching getshellPrompt" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

	def getPrompt(self):
		got_prompt = False
		timeOut = 60
		retry = 5
		prompt = False
		while not prompt and retry > 0 :
			retry = retry - 1
			try:
				while timeOut > 0:
					self.write("")
					buff = self._read()
					if buff is not None:
						lines = buff.splitlines()
					else:
						continue
					if len(lines) > 0:
						buff = lines[-1]
						if buff and not buff.isspace():   # the string is non-empty
							got_prompt = True
							break
						else :
							timeOut = timeOut - 1
					else :
						timeOut = timeOut - 1
				if got_prompt:
					prompt = self.tellPrompt(buff)
				else :
					message ( "Cannot to decide the Prompt. Buffer = %s ... %s retries left " %(buff,retry), {'to_log':1 , 'style': 'DEBUG'} ) 
			except Exception, err:
				message ( "Giving another chance to guess Prompt.", {'style': 'DEBUG'} ) 
		if not prompt :
			message ( "Giving up on finding Prompt.", {'to_log':1 , 'style': 'DEBUG'} )
			terminate_self("Giving up on finding Prompt.")
		return prompt   


	def run_till_prompt(self, cmd, prompt=re_cliPrompt, wait=1,timeout=300):
		data = ''
		output = ''
		lastline = ''
		alerted = None
		cmds = self._cmd_fix_input_data(cmd)
		message ( "sending=>\"%s\" on %s" %( cmd,self._host),{'to_trace':1, 'to_log':0 , 'style': 'TRACE'})

		for lines in cmds:
			 self.write(lines)
			 time.sleep(0.5)

		while True :
			TimeOut = timeout
			Channel_Ready = False
			while TimeOut > 0 :
				if self.chan.recv_ready() :
					Channel_Ready = True
					break
				else :
					time.sleep(wait)
					TimeOut = TimeOut - wait
					
			if Channel_Ready :
				data =  self.chan.recv(4096)
				data = data.replace('\r', '')
				if not output:
						 data = data.replace('.*\n'  ,'') 	# remove everything before the first new line ( buffer before our typed command)
						 data = data.replace(" \x08", '') 	# remove "space and ASCII backspace" with nothing
						 data = data.replace(cmd  ,'')		# remove our own command from buffer, so that we have only output
						 output += data
				else:
						 output += data
				#debug
				lines =  data.splitlines()
				if len(lines) > 0 :
					lastline = lines[-1]
					#message ( "debug long running cmd progress at =>\"%s\" on %s" % (lastline,self._host),{'to_trace': '1' ,'style': 'TRACE'}  )
				else:
					message ( "Client Disconnected.. reboot ?",{'to_stdout':1, 'to_log':1 , 'style': 'NOK'}) 
					return False #May be shell exited abruptly 
				if isinstance(prompt,re._pattern_type):
					if prompt.match(lastline):
						output = re.sub(prompt,'',output)
						message ( "Ran Successfully \"%s\" on %s" %( cmd,self._host),{'to_trace':1, 'to_log':0 , 'style': 'TRACE'})
						break
				else:
					if prompt in lastline:
						break
			else :
				if not alerted:
					message ( "Prompt not responding in %s for %s"%(self._host,cmd),{'to_stdout':0, 'to_log':1 , 'style': 'TRACE'})
					alerted = 1
				else :
					message ( "sending newline again",{'to_trace':1, 'style': 'TRACE'})
				self.write("")
		output.lstrip()
		return output

	def tellPrompt(self,line):
		try:
			if self.getshellPrompt(line):
				message ( "In shell prompt %s" % self._host,{'to_trace': 1 ,'style': 'TRACE'}  )
				return "shell"
			elif self.getcliPrompt(line):
				message ( "In cli prompt %s" % self._host,{'to_trace': 1 ,'style': 'TRACE'}  )
				return "cli"
			elif self.getenPrompt(line):
				message ( "In en prompt %s" % self._host,{'to_trace': 1 ,'style': 'TRACE'}  )
				return "en"
			elif self.getLoginPrompt(line):
				message ( "In login prompt %s" % self._host,{'to_trace': 1 ,'style': 'TRACE'}  )
				return "login"
			elif line.find("pm extension>") != -1:
				message ( "In pmx prompt %s" % self._host,{'to_trace': 1 ,'style': 'TRACE'}  )
				return "pmx"
			else:
				message ( "tellPrompt returned None. line = %s " % line ,{'to_trace': 1 ,'style': 'TRACE'}  )
				return False
		except Exception, err:
			errorMsg = "Error: %s" % traceback.format_exc()
			message ( "in tellPrompt = %s " % errorMsg,{'to_trace': 1 ,'style': 'TRACE'}  )
			terminate_self("Something bad happened with guessing current prompt. Exiting. see traces.")
			return None

	def transferFile(self,local_file,dir_remote,perm=0755):
		"""
		self._ssh_session.transferFile(local_file,dir_remote)
		"""
		sftp = paramiko.SFTPClient.from_transport(self.transport)
		#try:
		#	sftp.mkdir(dir_remote)
		#except IOError, e:
		#	mesg =  '(assuming ', dir_remote, 'exists)', e
		#	message ( mesg,  {'style': 'DEBUG'}  )
		#
		is_up_to_date = False
		fname = os.path.basename(os.path.abspath(local_file))
		dir_local = os.path.dirname(os.path.abspath(local_file))
		remote_file = dir_remote + '/' + os.path.basename(os.path.abspath(fname))
		# Todo fix below code to include paramiko.sftp_file.SFTPFile.check(md5) function.
		try:
			if sftp.stat(remote_file):
				local_file_data = open(local_file, "rb").read()
				remote_file_data = sftp.open(remote_file).read()
				md1 = md5.new(local_file_data).digest()
				md2 = md5.new(remote_file_data).digest()
				if md1 == md2:
					is_up_to_date = True
					message ( "UNCHANGED %s" % os.path.basename(fname),  {'style': 'DEBUG'}  )
					sftp.chmod (remote_file,perm)
					return
				else:
					message ( "MODIFIED %s" % os.path.basename(fname),  {'style': 'INFO'}  )
		except Exception:
			message ( "NEW %s" % os.path.basename(fname),  {'style': 'INFO'}  )

		if not is_up_to_date:
			sftp.put(local_file, remote_file)
			sftp.chmod (remote_file,perm)
			message ( "Copied file  %s to %s" % (local_file,remote_file),  {'style': 'DEBUG'}  )
			#except :
			#	message ( "Cannot copy file %s from % to %s" % (fname,dir_local,dir_remote),  {'style': 'nok'}  )

	def username(self):
		return self._username

	def write(self, cmd):
		timeOut = 60
		sent_data = False
		while timeOut > 0 :
			try:
				if self.chan.send_ready():
					self.current_send_string = cmd	
					self.chan.send(cmd + self.newline )
					sent_data = True
					break
				else:
					time.sleep(0.5)
					timeOut = timeOut - 1
				if sent_data:
					return True
			except Exception:
				message ( "Unable to write cmd %s to Channel (Channel not Ready)"%cmd,{'style': 'FATAL'}) 
				return False

if __name__ == '__main__':
	ssh_session = session('192.168.172.211', username='admin', password='admin@123')
	prompt = ssh_session.getPrompt()
	print prompt
	
