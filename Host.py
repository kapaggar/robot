#!/usr/bin/env python
import os, sys
import time
import signal
import re
import datetime
import argparse
from session import session
from vm_node import vm_node
from configobj import ConfigObj,flatten_errors
from validate import Validator
from urlgrabber import urlopen
from colorama import Fore
from pprint import pprint
from os.path import basename
import threading
######################################################
##            Class HOST
######################################################

class Host(object):

	def __init__(self,config_ref,host):
		self._ssh_session = None
		self._name = host
		self.config = config_ref
		self._name_server		= self.config['HOSTS']['name_server']
		self._ntp_server		= self.config['HOSTS']['ntp_server']
		self._iso_path			= self.config['HOSTS']['iso_path']
		self._release_ver		= self.config['HOSTS']['release_ver']
		self._template_file		= self.config['HOSTS'][self._name ]['template_file']
		self._ip				= self.config['HOSTS'][self._name ]['ip']
		self._username			= self.config['HOSTS'][self._name ]['username']
		self._password			= self.config['HOSTS'][self._name ]['password']
		self._brMgmt			= self.config['HOSTS'][self._name ]['brMgmt']
		self._brStor			= self.config['HOSTS'][self._name ]['brStor']
		self._vms				= self.get_vms()

	def __del__(self):
		if self._ssh_session != None:
			self._ssh_session.close()

	def connectSSH(self):
		self._ssh_session = session(self._ip, self._username, self._password)
		self.config['HOSTS'][self._name]['ssh_session'] = self._ssh_session
		return self._ssh_session
	
	def enableVirt(self):
		output = ''
		output += self._ssh_session.executeCli('virt enable',wait=5)
		return output
	
	def wipe_setup(self):
		output = ''
		template_name = basename(self._template_file)
		output +=  self._ssh_session.executeCli('no virt volume file %s' % template_name)
		for vm_name in self._vms:
			output +=  self._ssh_session.executeCli('no virt volume file %s.img'%vm_name)
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

	def create_template(self):
		output = ''
		template_name = basename(self._template_file)
		iso_path = self.get_iso_path()
		iso_name = basename(iso_path)
		output +=  self._ssh_session.executeCli('_exec qemu-img create %s 100G' % self._template_file)
		output +=  self._ssh_session.executeCli('virt vm template storage device drive-number 1 source file %s mode read-write' % template_name)
		output +=  self._ssh_session.executeCli('virt vm template vcpus count 4')
		output +=  self._ssh_session.executeCli('virt vm template memory 16384')
		output +=  self._ssh_session.run_till_prompt('virt vm template install cdrom file %s disk-overwrite connect-console text timeout 60' % iso_name , "(none) login:",wait=30)
		output +=  self._ssh_session.run_till_prompt('root', "#",wait=1)
		output +=  self._ssh_session.run_till_prompt('PS1="my_PROMPT"', "my_PROMPT",wait=1)
		output +=  self._ssh_session.run_till_prompt("sed -i 's/^TMPFS_SIZE_MB=[0-9]*/TMPFS_SIZE_MB=8192/g' /etc/customer_rootflop.sh ","my_PROMPT",wait=1)
		output +=  self._ssh_session.run_till_prompt('/sbin/manufacture.sh -i -v -f /mnt/cdrom/image.img -a -m 1D -d /dev/vda',"my_PROMPT",wait=60)
		output +=  self._ssh_session.run_till_prompt('reboot')
		return output

	def is_template_present(self):
		output = ''
		output +=  self._ssh_session.executeCli('_exec qemu-img create %s 100G' % self._template_file)
		
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
			print vm.clone_volume()
			print vm.configure()
			print vm.set_mfgdb()
	
	def startVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			print vm.power_on()

	def upgradeVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			if vm.ssh_self():
				print vm.image_fetch()
				print vm.image_install()
				print vm.reload()
'''
Now non-Member functions
'''

def connect_hosts (hosts):
	for host_name in hosts:
		host = Host(config,host_name)
		config['HOSTS'][host_name]['host_ref'] = host
		host.connectSSH()
		
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

def exit_cleanup(signal, frame):
	print Fore.RED + 'Caught signal .. Cleaning Up' + Fore.RESET
	for host_name in hosts:
		if config['HOSTS'][host_name]['host_ref']:
			host = config['HOSTS'][host_name]['host_ref']
			for vm in host.get_vms() :
				try:
					vm_ref = config['HOSTS'][host][vm]['vm_ref']
					del vm_ref
				except Exception:
					print "VM reference %s already clean"% host_name
			try:
				del config['HOSTS'][host_name]['host_ref']
			except Exception:
				print "Host reference %s already clean"% host_name
			else:
				print "host %s untouched"% host_name


def do_manufacture():
        print Fore.RED + 'Manufacture Option Set' + Fore.RESET
        threads = []
        for host_name in hosts:
                host = config['HOSTS'][host_name]['host_ref']
                newThread = threading.Thread(target=manufVMs, args = (host,))
                newThread.start()
                threads.append(newThread)
        for thread in threads:
                thread.join()

def do_upgrade():
	print Fore.RED + 'Upgrade Option set' + Fore.RESET
	threads = []
	for host_name in hosts:
		host = config['HOSTS'][host_name]['host_ref']
		newThread = threading.Thread(target=host.upgradeVMs(), args = (host,))
	for thread in threads:
		thread.join()

def objectify_vms(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		if not config['HOSTS'][host][vm_name]['vm_ref']:
			vm = vm_node(config,host,vm_name)
			config['HOSTS'][host][vm_name]['vm_ref'] = vm

def basic_settings(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		print Fore.YELLOW +"Now going inside VM %s, setting up ssh connections"%vm_name + Fore.RESET
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			print vm.rotate_logs()
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

def clear_ha(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		"""
		The logic for below could be wrong.. Double Check
		"""
		if vm.is_namenode() == 2 :   
			vm.unregisterNameNode()
			vm.registerDataNode()
		if vm.is_clusternode():
			vm.unregisterCluster()

def manufVMs(host):
	time.sleep(1)
	print host.enableVirt()
	print host.synctime()
	print host.setDNS()
	if opt_lazy:
		print "Skipping Template Creation. Exiting if not exists"
		
	else:
		print host.getMfgCd()
		print host.delete_template()
		print host.create_template()
	
	print host.deleteVMs()
	print host.declareVMs()
	print host.instantiateVMs()
	print host.startVMs()

def validate(config):
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

'''
Steps:
1. Take Config as Input
2. Validate this config
3. Connect to Hosts and make template and powerUp cloned VMs ( parallely in threads - 1 per Host)
4. On All VMs ( rotate_logs, factory_revert, install_license, SnmpServer, dns, ntp, users, hostname, hostmaps, extra nics, config_write )
5. On All VMs Generate SSH_keys
6. On All VMs Share Keys generated Above
7. On All VMs Setup Clustering if present
8. On All VMs Setup Yarn config if present
9. Connect to Hosts and upgrade VMs  ( parallely in threads - 1 per Host)
'''
if __name__ == '__main__':	
	########################################################
	#     MAIN
	########################################################
	signal.signal(signal.SIGINT,	exit_cleanup)
	signal.signal(signal.SIGTERM,	exit_cleanup)
	parser = argparse.ArgumentParser(description='Make Appliance setups from INI File' )
	parser.add_argument("INIFILE",
						nargs=1,
						type=str,
						help='INI file to choose as Input')
	parser.add_argument("--lazy",
						dest='lazy',
						action='store_true',
						default=False,
						help='Skip creating template. Use previous one')
	parser.add_argument("--reconfig",
						dest='reconfig',
						action='store_true',
						default=False,
						help='Skip manuf. VMS . Just factory revert and apply INI')
	parser.add_argument("--no-storage",
						dest='storage',
						action='store_false',
						default=True,
						help='Skip iscsi config and remote storage')
	parser.add_argument("--format",
						dest='force_format',
						action='store_true',
						default=False,
						help='Force format remote storage, override ini settings')
	parser.add_argument("--no-format",
						dest='force_format',
						action='store_false',
						default=False,
						help='Don\'t format remote storage, override ini settings')
	parser.add_argument("--no-ha",
						dest='setup_ha',
						action='store_false',
						default=True,
						help='skip configuring clustering.')
	parser.add_argument("--no-hdfs",
						dest='setup_hdfs',
						action='store_false',
						default=True,
						help='skip configuring HDFS')
	parser.add_argument("--wipe",
						dest='wipe_host',
						action='store_true',
						default=False,
						help='First delete Host VM-Pool')
	parser.add_argument("--skip-vm",
						nargs='+',
						dest='skip_vm',
						type=str,
						help='TOBE_IMPLEMENTED skip vm in ini with these names')

	args = parser.parse_args()
	config_filename = args.INIFILE[0]
	opt_format 		= args.force_format
	opt_storage		= args.storage
	opt_ha			= args.setup_ha
	opt_hdfs		= args.setup_hdfs
	opt_wipe		= args.wipe_host
	opt_skipvm		= args.skip_vm
	opt_lazy		= args.lazy
	opt_reconfig	= args.reconfig
	allvms = None

	print Fore.RED + "Got input file as %s"%config_filename + Fore.RESET
	configspec='config.spec'
	
	config = ConfigObj(config_filename,list_values=True,interpolation=True,configspec=configspec)
	validate(config)
	
	hosts = get_hosts(config)
	install_type = config['HOSTS']['install_type']
	start_time = time.time()
	
	#TODO Method Extraction
	#Setup Hosts Connectivity 
	connect_hosts(hosts)

	if 'manufacture' in install_type:
		if not opt_reconfig:
			do_manufacture()

	allvms = get_allvms(config)
	objectify_vms(allvms)
	
	basic_settings(allvms)
	generate_keys(allvms)
	shareKeys(allvms)
	if opt_ha is True:
		setupClusters(allvms)
	else:
		clear_ha(allvms) # Remove Clustering config nodes & convert NameNode2 config node to dataNode
	if opt_storage is True:
		setupStorage(allvms)
	if opt_hdfs is True:
		setupHDFS(allvms)
	
	manuf_runtime = time.time() - start_time
	print Fore.BLUE + 'Manufacture Runtime:' + str(datetime.timedelta(seconds=manuf_runtime)) + Fore.RESET

	if 'upgrade' in install_type:
		do_upgrade()

	total_runtime = time.time() - start_time
	print Fore.BLUE + 'Total Runtime:' + str(datetime.timedelta(seconds=total_runtime)) + Fore.RESET

#TODO: optional / force format iscsi
# force noHA noyarnHA noyarn
