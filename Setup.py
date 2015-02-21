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
from Toolkit import message
import threading

def connect_hosts (hosts):
	for host_name in hosts:
		host = Host(config,host_name)
		config['HOSTS'][host_name]['host_ref'] = host
		host.connectSSH()
	return "Success"
		
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
	message ( 'Caught signal %s.. Cleaning Up'% signal, {'style': 'INFO'} ) 
	for host_name in hosts:
		if config['HOSTS'][host_name]['host_ref']:
			host = config['HOSTS'][host_name]['host_ref']
			for vm in host.get_vms() :
				try:
					vm_ref = config['HOSTS'][host][vm]['vm_ref']
					del vm_ref
				except Exception:
					message( "VM reference %s already clean"% vm , { 'to_log':1 } )
			try:
				del config['HOSTS'][host_name]['host_ref']
				break
			except Exception:
				message ( "Host reference %s already clean"% host_name , {'style': 'OK'} )
			else:
				message ( "Host %s untouched"% host_name , {'style': 'OK'} )
	sys.exit("Cleaned")
	os._exit()

def wipe_vmpool(hosts):
	message ( 'Wiping Hosts VM pools', {'style': 'INFO'} )
	for host_name in hosts:
		host = config['HOSTS'][host_name]['host_ref']
		message ( "WipeSetup_Output = %s " %host.wipe_setup()             , {'style': 'INFO'} )
		return "Success"

def do_manufacture(hosts):
	message ( 'Manufacture Option Set', {'style': 'INFO'} ) 
	threads = []
	for host_name in hosts:
			host = config['HOSTS'][host_name]['host_ref']
			newThread = threading.Thread(target=manufVMs, args = (host,))
			newThread.setDaemon(True)
			newThread.start()
			threads.append(newThread)
	for thread in threads:
			thread.join()
	return "Success"

def do_upgrade():
	message ( 'Upgrade Option set', {'style': 'INFO'} ) 
	threads = []
	for host_name in hosts:
		host = config['HOSTS'][host_name]['host_ref']
		newThread = threading.Thread(target=host.upgradeVMs(), args = (host,))
	for thread in threads:
		thread.join()
	return "Success"

def objectify_vms(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		if not config['HOSTS'][host][vm_name]['vm_ref']:
			vm = vm_node(config,host,vm_name)
			config['HOSTS'][host][vm_name]['vm_ref'] = vm
	return "Success"

def basic_settings(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now going inside VM %s, setting up ssh connections" % vm_name, {'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "RotateLog_Output = %s " %vm.rotate_logs()			, {'style': 'INFO'} )
			if opt_reconfig:
				message ( "Factory-Revert_Output = %s " %vm.factory_revert()	, {'style': 'INFO'} )
			message ( "License-Install_Output = %s " %vm.install_license()	, {'style': 'INFO'} )
			message ( "SnmpConfig_Output = %s " %vm.setSnmpServer()			, {'style': 'INFO'} )
			message ( "DNS-Config_Output = %s " %vm.config_dns()			, {'style': 'INFO'} )
			message ( "NTP-Config_Output = %s " %vm.config_ntp()			, {'style': 'INFO'} )
			message ( "User-Config_Output = %s " %vm.configusers()			, {'style': 'INFO'} )
			message ( "Hostname-Config_Output = %s " %vm.setHostName()		, {'style': 'INFO'} )
			message ( "HostMaps_Output = %s " %vm.setIpHostMaps()			, {'style': 'INFO'} )
			message ( "Storage-nw_Output = %s " %vm.setStorNw()				, {'style': 'INFO'} )
			message ( "Config-Write_Output = %s " %vm.config_write()		, {'style': 'INFO'} )
		else :
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
	return "Success"

def generate_keys(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "GenDSAKey_Output = %s " % vm.gen_dsakey()		, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
	return "Success"

def shareKeys(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		message ( "Now sharing pub-keys inside VM %s" % vm_name, {'style': 'INFO'} ) 
		if vm.ssh_self():
			message ( "RemoveAuthKeys_Output = %s " % vm.removeAuthKeys()		, {'style': 'INFO'} )
			message ( "AuthPubKeys_Output = %s " % vm.authPubKeys()				, {'style': 'INFO'} )
			message ( "Config-Write_Output = %s " % vm.config_write()			, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
	return "Success"

def setupClusters(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting clusters inside VM %s" % vm_name, {'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			if vm.is_clusternode():
				message ( "Setup-Cluster_Output = %s " % vm.setclustering()			, {'style': 'INFO'} )
				time.sleep(5) # Let clustering settle down
				message ( "Config-Write_Output = %s " % vm.config_write()			, {'style': 'INFO'} )
			else:
				message ( "nothing to do in %s" %vm_name				, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
			
	return "Success"

def setupStorage(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting up storage inside VM %s"%vm_name, {'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			if vm.has_storage():
				message ("Bring-Strogage_Output = %s " %  vm.bring_storage() ,			{'style': 'INFO'} )
				if not opt_skip_format :
					message ( "FormatStorage_Output = %s " % vm.format_storage() ,	{'style': 'INFO'} )
				message ( "MountStorage_Output = %s " %  vm.mount_storage(),			{'style': 'INFO'} )
				message ( "Config-Write_Output = %s " %  vm.config_write(),			{'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
	return "Success"

def setupHDFS(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting up HDFS inside VM %s"%vm_name,{'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				message ("Setup-HDFS_Output = %s " %  vm.setup_HDFS(),{'style': 'INFO'} )
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
				terminate_self("Exiting")
	return "Success"

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
	return "Success"

def manufVMs(host):
	time.sleep(1)
	message (  "Enable-Virt_Output = [%s]" % host.enableVirt()			,{'style': 'INFO'} )
	message (  "Sync-Time_Output = [%s] " % host.synctime()				,{'style': 'INFO'} )
	message (  "SetHostDNS_Output = [%s] " % host.setDNS()				,{'style': 'INFO'} )
	if opt_lazy:
		if host.is_template_present():
			message ( "Found template file in host %s " % host.getname()	,{'style': 'OK'} ) 
		else :
			message ( "Cannot find template file in host %s .Exiting.." % host.getname()	,{'style': 'FATAL'} )
			terminate_self("Template missing in host %s" % host.getname())
			sys.exit( "Template missing in host %s" % host.getname()) # this should never get executed
	else:
		message (  "GetMfgISO_Output = %s " % host.getMfgCd()				,{'style': 'INFO'} )
		message (  "Delete-Template_Output = %s " % host.delete_template()	,{'style': 'INFO'} )
		message (  "Create-Template_Output = %s " % host.create_template()	,{'style': 'INFO'} )
	message ( "DeleteVMs_Output = %s " % host.deleteVMs()					,{'style': 'INFO'} )
	message ( "DeclareVMs_Output = %s " % host.declareVMs()					,{'style': 'INFO'} )
	message ( "CreateVMs_Output = %s " % host.instantiateVMs()				,{'style': 'INFO'} )
	message ( "PowerON-VMs_Output = %s " % host.startVMs()					,{'style': 'INFO'} )
	return "Success"

def validate(config):
	validator = Validator()
	results = config.validate(validator)
	if results != True:
		for (section_list, key, _) in flatten_errors(config, results):
			if key is not None:
				message ( 'The "%s" key in the section "%s" failed validation' % (key, ', '.join(section_list)), {'style':'DEBUG'} )
			else:
				message ( 'The following section was missing:%s ' % " ".join(section_list)   , {'style':'DEBUG'} )
		message ('Config file %s validation failed!'% config_filename, {'style':'FATAL'})
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
	parser.add_argument("-l","--log",
						metavar='LOGFILE',
						nargs=1,
						type=str,
						help='Custom logfile name. default is script.PID.log (DoesNOT redirects stdout)')
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
	if args.log:
		os.environ["LOGFILE_NAME"] = args.log[0]
	message ("Got input file as %s "%config_filename,
			 {'to_stdout' : 1, 'to_log' : 1, 'style' : 'info'}
			 )	

	configspec='config.spec'
	config = ConfigObj(config_filename,list_values=True,interpolation=True,configspec=configspec)
	validate(config)
	if opt_skip_format and opt_force_format :
		message ( "No-Format and force format options cannot be used together." ,	{'style':'FATAL'} )
		sys.exit(1)
	if opt_wipe and opt_lazy :
		message ( "Wipe and Lazy options cannot be used together.", 				{'style':'FATAL'} )
		sys.exit(1)
	if opt_wipe and opt_reconfig:
		message ( "Wipe and Reconfig cannot be used together.",						{'style':'FATAL'} )
		sys.exit(1)
	
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
	message (' Manufacture Runtime: ' + str(datetime.timedelta(seconds=manuf_runtime)),
			 {'style' : 'info'}
			 )

	if 'upgrade' in install_type:
		do_upgrade()

	total_runtime = time.time() - start_time
	message (' Total Runtime: ' + str(datetime.timedelta(seconds=total_runtime)),
			 {'style' : 'info'}
			 )



# Debug Command
# pydbgp -d localhost:9001  Setup.py  INIFILE

#TODO
# Exception if there is one "virt volume fetch url" already running on Host system
# Validate iso and img files are present and are iso & image files
# validate other config.spec parameters.
# Write message . log . info generic logging moduli in common library
# from vm consoles loop a arping updating Host arp cache
# Remove forbidden nodes from the iscsi connection after the setup
