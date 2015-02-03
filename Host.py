#!/usr/bin/env python
import os, sys, getopt
import time
import re
import datetime
from session import session
from vm_node import vm_node
from configobj import ConfigObj,flatten_errors
from validate import Validator
from urlgrabber import urlopen
from colorama import Fore
from pprint import pprint
import threading
######################################################
##            Class HOST
######################################################

class Host(object):
	re_pmxPrompt = re.compile( r"^(?P<pmxPrompt>pm\s+extension\s*>)\s*",re.M)    
	
	def __init__(self,config_ref,host):
		self._name = host
		self.config = config_ref
		self._ip = self.config['HOSTS'][self._name ]['ip']
		self._username = self.config['HOSTS'][self._name ]['username']
		self._password = self.config['HOSTS'][self._name ]['password']
		self._name_server = self.config['HOSTS']['name_server']
		self._ntp_server = self.config['HOSTS']['ntp_server']
		self._iso_path = self.config['HOSTS']['iso_path']
		self._release_ver = self.config['HOSTS']['release_ver']
		self._vms = self.get_vms()
		self._ssh_session = None

	def connectSSH(self):
		self._ssh_session = session(self._ip, self._username, self._password)
		self.config['HOSTS'][self._name]['ssh_session'] = self._ssh_session
		return self._ssh_session
	
	def enableVirt(self):
		output = ''
		output += self._ssh_session.executeCli('virt enable')
		return output
	
	def delete_template(self):
		output = ''
		output += self._ssh_session.executeCli('virt vm template install cancel')
		output += self._ssh_session.executeCli('no virt vm template ') 
		return output
	
	def get_common(self):
		commons = {}	
		for section in config['HOSTS'][self._name]:
			if not isinstance(config['HOSTS'][self._name][section], dict):
				commons[section] = config['HOSTS'][self._name][section]
		return commons
	
	def get_vms(self):
		vms = []
		host = self._name
		for section in self.config['HOSTS'][host]:
			if isinstance(self.config['HOSTS'][host][section], dict):
				vms.append(section)
		return vms
	
	def synctime(self):
		output = ''
		output += self._ssh_session.executeCli('ntpdate  %s' %self._ntp_server )
		output += self._ssh_session.executeCli('ntp server %s' % self._ntp_server )
		output += self._ssh_session.executeCli('ntp enable ')
		return output

	def setDNS(self):
		return self._ssh_session.executeCli('ip name-server %s '%self._name_server)

	def create_template(self,template_img='/data/virt/pools/default/template.img'):
		output = ''
		iso_path = self.get_iso_path()
		iso_name = iso_path.split('/')[-1]
		output +=  self._ssh_session.executeCli('_exec qemu-img create %s 100G' % template_img)
		output +=  self._ssh_session.executeCli('virt vm template storage device drive-number 1 source file template.img mode read-write')
		output +=  self._ssh_session.executeCli('virt vm template vcpus count 4')
		output +=  self._ssh_session.executeCli('virt vm template memory 16384')
		output +=  self._ssh_session.run_till_prompt('virt vm template install cdrom file %s disk-overwrite connect-console text timeout 60' % iso_name , "(none) login:",wait=30)
		output +=  self._ssh_session.run_till_prompt('root', "#",wait=1)
		output +=  self._ssh_session.run_till_prompt('PS1="my_PROMPT"', "my_PROMPT",wait=1)
		output +=  self._ssh_session.run_till_prompt("sed -i 's/^TMPFS_SIZE_MB=[0-9]*/TMPFS_SIZE_MB=8192/g' /etc/customer_rootflop.sh ","my_PROMPT",wait=1)
		output +=  self._ssh_session.run_till_prompt('/sbin/manufacture.sh -i -v -f /mnt/cdrom/image.img -a -m 1D -d /dev/vda',"my_PROMPT",wait=60)
		output +=  self._ssh_session.run_till_prompt('reboot')
		return output

	def get_iso_path(self):
		if self._iso_path == "nightly" :
			nightly_base_dir = self.config['HOSTS']['nightly_dir']
			full_iso_path = self.get_nightly (nightly_base_dir)
			return full_iso_path
		elif self._iso_path is not None:
			return self._iso_path

	def get_nightly(self,base_path):
		re_mfgiso = re.compile( r"(?P<mfgiso>mfgcd-\S+?.iso)",re.M)
		page = urlopen(base_path)
		page_read = page.read()
		match = re_mfgiso.search(page_read)
		if match:
			iso_filename = match.group("mfgiso")
			return base_path + "/" + iso_filename
		return False
	
	def getMfgCd(self):
		output = ''
		iso_path = self.get_iso_path()
		output +=  self._ssh_session.executeCli('virt volume fetch url %s' % iso_path,wait=2 )
		return output
	
	def get_common(self):
		commons = {}	
		for section in self.config['HOSTS'][self._name]:
			if not isinstance(self.config['HOSTS'][self._name][section], dict):
				commons[section] = self.config['HOSTS'][self._name][section]
		return commons
	
	def get_vms(self):
		vms = []	
		for section in self.config['HOSTS'][self._name]:
			if isinstance(self.config['HOSTS'][self._name][section], dict):
				vms.append(section)
		return vms
	
	def deleteVMs(self):
		output = ''
		for vm_name in self._vms:
			output +=  self._ssh_session.executeCli('no virt vm %s' % vm_name )
		return output
	
	def declareVMs(self):
		for vm_name in self._vms:
			vm = vm_node(self.config,self._name,vm_name)
			self.config['HOSTS'][self._name][vm_name]['vm_ref'] = vm
	
	def instantiateVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			print vm.set_storage()
			print vm.configure()
			print vm.set_mfgdb()
	
	def startVMs(self):
		for vm_name in self._vms:
			vm = vm_node(self.config,self._name,vm_name)
			print vm.power_on()

	def upgradeVMs(self):
		for vm_name in self._vms:
			vm = vm_node(self.config,self._name,vm_name)
			if vm.ssh_self():
				print vm.image_fetch()
				print vm.image_install()
				print vm.reload()
	
		
	
if __name__ == '__main__':
	def get_hosts(config):
		hosts = []	
		for section in config['HOSTS']:
			if isinstance(config['HOSTS'][section], dict):
				hosts.append(config['HOSTS'][section].name)
		return hosts
	def get_allvms(config):
		tuples = []	
		for host_section in config['HOSTS']:
			if isinstance(config['HOSTS'][host_section], dict):
				for vm_section in config['HOSTS'][host_section]:
					if isinstance(config['HOSTS'][host_section][vm_section], dict):
						tuples.append(host_section + ":" + vm_section)
		return tuples
	
	def basic_settings(tuples):
		for line in tuples:
			host,vm_name = line.split(":")
			print Fore.YELLOW +"Now going inside VM %s, setting up ssh connections"%vm_name + Fore.RESET
			vm = config['HOSTS'][host][vm_name]['vm_ref']
			if vm.ssh_self():
				print vm.factory_revert()
				print vm.install_license()
				print vm.setSnmpServer()
				print vm.config_dns()
				print vm.config_ntp()
				print vm.configusers()
				print vm.setHostName()
				print vm.setIpHostMaps()
				print vm.setStorNw()
				print vm.config_write()
	
	def generate_keys(tuples):
		for line in tuples:
			host,vm_name = line.split(":")
			vm = config['HOSTS'][host][vm_name]['vm_ref']
			if vm.ssh_self():
				print vm.gen_dsakey()
	
	def shareKeys(tuples):
		for line in tuples:
			host,vm_name = line.split(":")
			vm = config['HOSTS'][host][vm_name]['vm_ref']
			print "Now sharing pub-keys inside VM %s"%vm_name
			if vm.ssh_self():
				print vm.removeAuthKeys()
				print vm.authPubKeys()
				print vm.config_write()
	
	def setupClusters(tuples):
		for line in tuples:
			host,vm_name = line.split(":")
			print "Now setting clusters inside VM %s"%vm_name
			vm = config['HOSTS'][host][vm_name]['vm_ref']
			if vm.ssh_self():
				if vm.is_clusternode():
					print vm.setclustering()
					time.sleep(5) # Let clustering settle down
					print vm.config_write()
				else:
					print "nothing to do in %s" %vm_name
	
	def setupStorage(tuples):
		for line in tuples:
			host,vm_name = line.split(":")
			print(Fore.RED + "Now setting up storage inside VM %s"%vm_name + Fore.RESET) 
			vm = config['HOSTS'][host][vm_name]['vm_ref']
			if vm.ssh_self():
				if vm.has_storage():
					print vm.bring_storage()
					print vm.format_storage()
					print vm.mount_storage()
					print vm.config_write()
	
	def setupHDFS(tuples):
		for line in tuples:
			host,vm_name = line.split(":")
			print "Now setting up HDFS inside VM %s"%vm_name
			vm = config['HOSTS'][host][vm_name]['vm_ref']
			if vm.is_namenode():
				if vm.ssh_self():
					print vm.setup_HDFS()
					
	def manufVMs(host):
		host.enableVirt()
		host.synctime()
		host.setDNS()
		host.getMfgCd()
		host.delete_template()
		host.create_template()
		host.deleteVMs()
		host.declareVMs()
		host.instantiateVMs()
		host.startVMs()
		
	def take_choice(argv):
		inputfile = ''
		try:
			opts, args = getopt.getopt(argv,"hi:",["ifile="])
		except getopt.GetoptError:
			print 'Host.py -i <INI.File>'
			sys.exit(2)
		for opt, arg in opts:
			if opt == '-h':
				print 'Host.py -i <INI.File>'
				sys.exit()
			elif opt in ("-i", "--inifile"):
				inputfile = arg
		return inputfile
	
	########################################################
	#     MAIN
	########################################################
	
	config_filename = take_choice(sys.argv[1:])
	print Fore.RED + "Got input file as %s"%config_filename + Fore.RESET
	configspec='config.spec'
	
	config = ConfigObj(config_filename,list_values=True,interpolation=True,configspec=configspec)
	config.write_empty_values = False
	validator = Validator()
	results = config.validate(validator)
	
	if results != True:
		for (section_list, key, _) in flatten_errors(config, results):
			if key is not None:
				print 'The "%s" key in the section "%s" failed validation' % (key, ', '.join(section_list))
			else:
				print 'The following section was missing:%s ' % ', '.join(section_list)     
		print 'Config file %s validation failed!'% config_filename
		sys.exit(1)
	
	hosts = get_hosts(config)
	install_type = config['HOSTS']['install_type']

	start_time = time.time()
	
	#TODO Method Extraction
	
	#Setup Hosts Connectivity 
	for host_name in hosts:
		host = Host(config,host_name)
		config['HOSTS'][host_name]['host_ref'] = host
		host.connectSSH()
			
			
	if 'manufacture' in install_type:
		print Fore.RED + 'Manufacture Option Set' + Fore.RESET
		threads = []
		for host_name in hosts:
			host = config['HOSTS'][host_name]['host_ref']
			newThread = threading.Thread(target=manufVMs, args = (host,))
			newThread.start()
			threads.append(newThread)
			
		#Wait for all threads to complete and sync up. till the point when VMs have been booted 
		for thread in threads:
			thread.join()


	allvms = get_allvms(config)

	for line in allvms:
		host,vm_name = line.split(":")
		vm = vm_node(config,host,vm_name)
		config['HOSTS'][host][vm_name]['vm_ref'] = vm

	basic_settings(allvms)
	generate_keys(allvms)
	shareKeys(allvms)
	setupClusters(allvms)
	setupStorage(allvms)
	setupHDFS(allvms)	
	manuf_runtime = time.time() - start_time
	print Fore.BLUE + 'Manufacture Runtime:' + str(datetime.timedelta(seconds=manuf_runtime)) + Fore.RESET
		
	# TODO Method Extraction

	if 'upgrade' in install_type:
		print Fore.RED + 'Upgrade Option set' + Fore.RESET
		threads = []
		for host_name in hosts:
			host = config['HOSTS'][host_name]['host_ref']
			newThread = threading.Thread(target=host.upgradeVMs(), args = (host,))
			
		for thread in threads:
			thread.join()
			


	total_runtime = time.time() - start_time
	print Fore.BLUE + 'Total Runtime:' + str(datetime.timedelta(seconds=total_runtime)) + Fore.RESET
			
	#TODO: ROOT_2 ignore install
	#TODO: optional / force format iscsi
	
	

