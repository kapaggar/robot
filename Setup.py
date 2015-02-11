#!/usr/bin/env python
import os, sys
import time
import signal
import re
import datetime
import argparse
from vm_node import vm_node
from Host import Host
from configobj import ConfigObj,flatten_errors
from validate import Validator
from colorama import Fore
from pprint import pprint
import threading

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

def wipe_vmpool(hosts):
	print Fore.RED + 'Wiping Hosts VM pools' + Fore.RESET
	for host_name in hosts:
		host = config['HOSTS'][host_name]['host_ref']
		print host.wipe_setup()

def do_manufacture(hosts):
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
				if not opt_skip_format :
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
		if not host.is_template_present():
			sys.exit( "Template missing in host %s" % host.getname())
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
	parser.add_argument("--force-format",
						dest='force_format',
						action='store_true',
						default=False,
						help='Format Volumes, Even if Filesystem present "no-strict"')
	parser.add_argument("--no-format",
						dest='skip_format',
						action='store_true',
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
	opt_skip_format = args.skip_format
	opt_force_format= args.force_format
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
	
	if opt_force_format:
		config['HOSTS']['force_format'] = True
	else:
		config['HOSTS']['force_format'] = False
		
	start_time = time.time()
	
	#Setup Hosts Connectivity 
	connect_hosts(hosts)
	if opt_wipe :
		wipe_vmpool(hosts)
	if 'manufacture' in install_type:
		if not opt_reconfig:
			do_manufacture(hosts)

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


# Debug Command
# pydbgp -d localhost:9001  Host.py  INIFILE
# Validate iso and img files are present and are iso & image files

