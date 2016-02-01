#!/usr/bin/env python
import os, sys
import time
import signal
import re
import datetime
import argparse
import threading
import random
import HTML
from vm_node import vm_node
from Host import Host
from configobj import ConfigObj,flatten_errors
from validate import Validator
from Toolkit import *
from pprint import pprint

hosts = list()
hdfs_report = []
setup_yarn_info = []

def basic_settings(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now going inside VM %s, setting up ssh connections" % vm_name		, {'style': 'DEBUG','to_log':'0',} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			record_status("Server startup after fresh manufacture",get_rc_ok())
			message ( "Rotating Logs in %s =\t\t%s " %(vm_name,vm.rotate_logs())			, {'style': 'INFO'} )
			if opt_reconfig:
				message ( "Factory-Revert in %s =\t\t%s " %(vm_name,vm.factory_revert())	, {'style': 'INFO'} )
			message ( "License Install in %s =\t\t%s " %(vm_name,vm.install_license())		, {'style': 'INFO'} )
			message ( "Snmp Config in %s =\t\t%s " %(vm_name,vm.setSnmpServer())			, {'style': 'INFO'} )
			message ( "DNS Config in %s =\t\t%s " %(vm_name,vm.config_dns())				, {'style': 'INFO'} )
			message ( "NTP Config in %s =\t\t%s " %(vm_name,vm.config_ntp())				, {'style': 'INFO'} )
			message ( "User Config in %s =\t\t%s " %(vm_name,vm.configusers())				, {'style': 'INFO'} )
			message ( "Hostname Config in %s =\t\t%s " %(vm_name,vm.setHostName())			, {'style': 'INFO'} )
			message ( "IP Host Mapping in %s =\t\t%s " %(vm_name,vm.setIpHostMaps())		, {'style': 'INFO'} )
			message ( "N/w Interface Config in %s =\t%s " %(vm_name,vm.setStorNw())		, {'style': 'INFO'} )
			message ( "Config-Write_Output in %s =\t\t%s " %(vm_name,vm.config_write())	, {'style': 'TRACE','to_trace':'1'} )
		else :
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			record_status("Server startup after fresh manufacture",get_rc_nok())
			terminate_self("Exiting")
	return get_rc_ok()

def centos_sync_basic_settings(tuples):
	threads = []
	for line in tuples:
		host,vm_name = line.split(":")
		newThread = threading.Thread(target=centos_basic_settings, args = (line,))
		newThread.setDaemon(True)
		message ( "Parallel base package installation inside VM %s\n" % vm_name,{'style': 'INFO'} )
		newThread.start()
		threads.append(newThread)
	for thread in threads:
			thread.join()
	return get_rc_ok()

def centos_basic_settings(line):
	host,vm_name = line.split(":")
	time.sleep(random.random())
	message ( "Now going inside VM %s, setting up ssh connections" % vm_name			, {'style': 'INFO'} )
	vm = config['HOSTS'][host][vm_name]['vm_ref']
	if vm.ssh_self():
		message ( "Centos RotateLog_Output in vm %s = %s " %(vm_name,vm.centos_rotate_logs())				, {'style': 'INFO'} )
		if opt_reconfig:
			message ( "Centos Factory-Revert_Output in vm %s = %s " %(vm_name,vm.centos_factory_revert())	, {'style': 'INFO'} )
		message ( "Centos get Base repo in vm %s = %s " 			%(vm_name,vm.centos_get_repo())			, {'style': 'INFO'} )
		message ( "Centos Install basic packages in vm %s = %s " %(vm_name,vm.centos_install_base())		, {'style': 'INFO'} )
		message ( "Centos Configure ntp in vm %s  = %s " 		%(vm_name,vm.centos_cfg_ntp())				, {'style': 'INFO'} )
		message ( "Centos Hostname maps Output in vm %s  = %s "	%(vm_name,vm.centos_setIpHostMaps())		, {'style': 'INFO'} )
		message ( "Centos rsyslog config in vm %s  = %s "	%(vm_name,vm.centos_cfg_rsyslog())				, {'style': 'INFO'} )
		message ( "Centos add reflex sudoer in vm %s  = %s "	%(vm_name,vm.centos_cfg_sudo())				, {'style': 'INFO'} )

		
	else:
		message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
		terminate_self("Exiting")
	return get_rc_ok()

def centos_cfg_storage(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting up storage inside Centos VM %s" % vm_name, {'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			if vm.has_storage():
				message ("Centos Bring-Storage_Output = [%s]" % vm.centos_bring_storage() ,			{'style': 'INFO'} )
				if not opt_skip_format :
					message ( "Centos FormatStorage_Output = [%s]" % vm.centos_format_storage() ,	{'style': 'INFO'} )
				message ( "Centos MountStorage_Output = [%s]" % vm.centos_mount_storage(),			{'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
	return get_rc_ok()

def centos_checkHDFS(tuples):
	output = ''
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now checking HDFS inside VM %s" % vm_name,{'style': 'DEBUG'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				response = vm.centos_validate_HDFS()
				message ("Centos Check-HDFS_Output in %s = [%s]" % (vm_name,response)	,{'style': 'INFO'} )
				output += response
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
	return output

def centos_sync_install_reflex(tuples):
	threads = []
	for line in tuples:
		host,vm_name = line.split(":")
		newThread = threading.Thread(target=centos_install_reflex, args = (line,))
		newThread.setDaemon(True)
		message ( "Parallel install of reflex components inside VM %s" % vm_name,{'style': 'INFO'} )
		newThread.start() # This return immediately, so if you want to catch Exception do it in threads.
		threads.append(newThread)
	for thread in threads:
			thread.join()
	return get_rc_ok()

def centos_install_reflex(line):
	host,vm_name = line.split(":")
	vm = config['HOSTS'][host][vm_name]['vm_ref']
	time.sleep(random.random())
	if vm.ssh_self():
		message ("Centos yum reflex install in %s  = [%s]" % (vm_name,vm.centos_install_reflex())	,{'style': 'INFO'} )
	else:
		message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
		terminate_self("Exiting")
	return get_rc_ok()

def centos_keygen(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "Centos generate keys for root in %s = %s " %(vm_name, vm.centos_genkeys('root'))	, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name				, {'style': 'Debug'} )
			terminate_self("Exiting")
	return get_rc_ok()

def centos_keyshare(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "Centos distribute keys for root in %s = %s " %(vm_name,vm.centos_distkeys('root'))	, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name	, {'style': 'Debug'} )
			terminate_self("Exiting")
	return get_rc_ok()

def centos_reflex_keygen(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "Centos distribute keys for reflex in %s = %s " %(vm_name,vm.centos_genkeys('reflex')), {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name	, {'style': 'Debug'} )
			terminate_self("Exiting")
	return get_rc_ok()

def centos_reflex_keyshare(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "Centos distribute keys for reflex in %s = %s " %(vm_name,vm.centos_distkeys('reflex'))		, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name				, {'style': 'Debug'} )
			terminate_self("Exiting")
	return get_rc_ok()

def centos_setupHDFS(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting up HDFS inside VM %s" % vm_name,{'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				message ("Centos Setup HDFS_Output = [%s]" % vm.centos_setup_HDFS(),{'style': 'INFO'} )
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
				terminate_self("Exiting")
	return get_rc_ok()

def centos_setupClusters(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting clusters inside VM %s" % vm_name, {'style': 'debug'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			if vm.is_clusternode():
				message ( "Centos Setup Cluster_Output = %s " % vm.centos_setclustering()			, {'style': 'INFO'} )
				time.sleep(5) # Let clustering settle down			else:
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")	
	return get_rc_ok()

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
	return get_rc_ok()

def collect_yarn_setup_info(tuples):
	output = ''
	response = ''
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now checking yarn info inside VM %s" % vm_name,{'style': 'DEBUG'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				response = vm.get_yarn_info()
				if response:
					message ("Show yarn Info in %s = \t%s" % (vm_name,response),{'style': 'INFO'} )
					output += response
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
	return output

def checkHDFS(tuples):
	output = ''
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now checking HDFS inside VM %s" % vm_name,{'style': 'DEBUG'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				response = vm.validate_HDFS()
				if not response :
					message ("Check-HDFS_Output in %s = \t\t%s" %(vm_name, record_status("HDFS Current Status",get_rc_error())),{'style': 'NOK'} )
				if response.find('ERROR') != -1 :
					message ("Check-HDFS_Output in %s = \t\t%s" %(vm_name, record_status("HDFS Current Status",get_rc_error())),{'style': 'NOK'} )
				elif response.find('SKIPPED') != -1 :
					message ("Check-HDFS_Output in %s = \t\t%s" %(vm_name, record_status("HDFS Current Status",get_rc_skipped())),{'style': 'INFO'} )
				else :
					message ("Check-HDFS_Output in %s = \t\t%s" %(vm_name, record_status("HDFS Current Status",get_rc_ok())),{'style': 'OK'} )
					hdfs_report.append(monospace_text(br_text_to_html(response)))
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )

def checkColSanity(tuples):
	output = ''
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now checking collector sanity inside VM %s" % vm_name,{'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				response = vm.collector_sanity()
				message ("CollectorSanity_Output = [%s]" % response,{'style': 'INFO'} )
				output += response
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
	return output

def config_collector(tuples):		
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now configuring collector basics inside VM %s" % vm_name,{'style': 'INFO'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				if os.environ['RPM_MODE']:
					message ("Centos Config-Collector_Output in %s = [%s]" % (vm_name,vm.centos_col_basic()),{'style': 'INFO'} )
				else :
					message ("Collector configution in %s = \t\t[%s]" % (vm_name,vm.col_basic()),{'style': 'INFO'} )
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )

def connect_hosts (hosts):
	for host_name in hosts:
		host = Host(config,host_name)
		config['HOSTS'][host_name]['host_ref'] = host
		host.connectSSH()
	return get_rc_ok()
	
def do_manufacture(hosts):
	message ( 'Manufacture Option Set', {'style': 'INFO'} ) 
	threads = []
	try :
		for host_name in hosts:
				host = config['HOSTS'][host_name]['host_ref']
				newThread = threading.Thread(target=manuf_VMs, args = (host,))
				newThread.setDaemon(True)
				newThread.start()
				threads.append(newThread)
		for thread in threads:
				thread.join()
	except Exception,err:
		message ( 'Exception inManufacturing VM %s'%(str(err)), {'style': 'FATAL'} )
		terminate_self('Exiting')
	return get_rc_ok()

def do_centosInstall(hosts):
	message ( 'RPM install Option Set', {'style': 'INFO'} ) 
	threads = []
	for host_name in hosts:
			host = config['HOSTS'][host_name]['host_ref']
			newThread = threading.Thread(target=manuf_Centos_VMs, args = (host,))
			newThread.setDaemon(True)
			newThread.start()
			threads.append(newThread)
	for thread in threads:
			thread.join()
	return get_rc_ok()

def do_upgrade():
	message ( 'Upgrade Option set', {'style': 'INFO'} ) 
	threads = []
	for host_name in hosts:
		host = config['HOSTS'][host_name]['host_ref']
		newThread = threading.Thread(target=host.upgradeVMs(), args = (host,))
	for thread in threads:
		thread.join()
	return get_rc_ok()

def exit_cleanup(signal, frame):
	message ( 'Caught signal %s.. Cleaning Up'% signal, {'style': 'INFO'} ) 
	for host_name in hosts:
		try :
			if config['HOSTS'][host_name]['host_ref']:
				host = config['HOSTS'][host_name]['host_ref']
				for vm in host.get_vms() :
					try:
						vm_ref = config['HOSTS'][host][vm]['vm_ref']
						del vm_ref
					except Exception:
						message( "VM reference %s already clean"% vm , { 'to_log':1 ,'style': 'OK'} )
				try:
					del config['HOSTS'][host_name]['host_ref']
					break
				except Exception:
					message ( "Host reference %s already clean"% host_name , {'style': 'OK'} )
				else:
					message ( "Host %s untouched"% host_name , {'style': 'OK'} )
		except Exception:
			message ( 'Nothing to clean', {'style': 'INFO'} )
	sys.exit("Cleaned")
	os._exit()

def generate_keys(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			message ( "GenDSAKey_Output %s = \t\t%s " % (vm_name,vm.gen_dsakey())		, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name, {'style': 'Debug'} )
			terminate_self("Exiting")
	return get_rc_ok()

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

def get_datanodesvms(config):
	tuples = []	
	for host_section in config['HOSTS']:
		if isinstance(config['HOSTS'][host_section], dict):
			for vm_section in config['HOSTS'][host_section]:
				if isinstance(config['HOSTS'][host_section][vm_section], dict):
					DN_id = config['HOSTS'][host_section][vm_section]['data_node']
					if DN_id :
						tuples.append(host_section + ":" + vm_section)
	return tuples

def get_namenodesvms(config):
	tuples = []	
	for host_section in config['HOSTS']:
		if isinstance(config['HOSTS'][host_section], dict):
			for vm_section in config['HOSTS'][host_section]:
				if isinstance(config['HOSTS'][host_section][vm_section], dict):
					NN_id = config['HOSTS'][host_section][vm_section]['name_node']
					if ( NN_id == 1 or NN_id == 2 ):
						tuples.append(host_section + ":" + vm_section)
	return tuples

def get_rubixvms(config):
	tuples = []	
	for host_section in config['HOSTS']:
		if isinstance(config['HOSTS'][host_section], dict):
			for vm_section in config['HOSTS'][host_section]:
				if isinstance(config['HOSTS'][host_section][vm_section], dict):
					rubix_id = config['HOSTS'][host_section][vm_section]['rubix_node']
					if rubix_id :
						tuples.append(host_section + ":" + vm_section)
	return tuples

def manuf_VMs(host):
	message (  "Enabling Virtualisation in %s = \t[%s]" % ( host.getname(),host.enableVirt())			,{'style': 'INFO'} )
	message (  "NTP Syncing in %s  = \t\t\t[%s] " % ( host.getname(),host.synctime())						,{'style': 'INFO'} )
	message (  "Configuring DNS in %s = \t\t[%s] " % ( host.getname(),host.setDNS())					,{'style': 'INFO'} )
	message (  "IP Host Mapping in %s  = \t\t[%s] " % ( host.getname(),host.vmHostMaps())				,{'style': 'INFO'} )
	if opt_lazy:
		if host.is_template_present():
			message ( "Found template file in host %s " % host.getname()	,{'style': 'OK'} )
			record_status("Manufacturing with ISO",get_rc_skipped())
		else :
			message ( "Cannot find template file in host %s .Exiting.." % host.getname()	,{'style': 'FATAL'} )
			return record_status("Manufacturing with ISO",get_rc_error())
			terminate_self("Template missing in host %s" % host.getname())
			return get_rc_error()
	else:
		message (  "MFG CD iso fetch = \t\t[%s]"		% host.getMfgCd()			,{'style': 'INFO'} )
		message (  "Deleting old templates = \t\t[%s]"	% host.delete_template()	,{'style': 'INFO'} )
		message (  "Create-Template_Output = \t\t[%s]"	% host.create_template()	,{'style': 'INFO'} )
	message ( "VM Deletion Status = \t\t\t[%s]"			% host.deleteVMs()				,{'style': 'INFO'} )
	message ( "DeclareVMs_Output = \t\t[%s]" 		% host.declareVMs()				,{'style': 'TRACE','to_trace':'1'} )
	message ( "VM Creation Status = \t\t[%s]" 		% host.instantiateVMs()			,{'style': 'INFO'} )
	message ( "Powering ON VMs Status = \t\t[%s]" 	% host.startVMs()				,{'style': 'INFO'} )
	return get_rc_ok()

def manuf_Centos_VMs(host):
	time.sleep(1)
	message (  "Enable-Virt_Output = [%s]" % host.enableVirt()			,{'style': 'INFO'} )
	message (  "Sync-Time_Output = [%s] " % host.synctime()				,{'style': 'INFO'} )
	message (  "SetHostDNS_Output = [%s] " % host.setDNS()				,{'style': 'INFO'} )
	message (  "HostMapping_Output = [%s] " % host.vmHostMaps()			,{'style': 'INFO'} )

	if opt_lazy:
		# if lazy option given we check if centos_template is present
		# otherwise we download from the location given in the INI file
		if host.is_centos_template_present():
			message ( "Found template file in host %s " % host.getname()	,{'style': 'OK'} ) 
		else :
			message ( "Cannot find template file in host %s .Exiting.." % host.getname()	,{'style': 'FATAL'} )
			terminate_self("Template missing in host %s" % host.getname())
			return get_rc_nok()
	else:
		message (  "Get_Centos_template_Output = [%s]"	% host.get_centos_template()	,{'style': 'INFO'} )
	message ( "DeleteVMs_Output = [%s]"				% host.deleteVMs()					,{'style': 'INFO'} )
	message ( "DeclareVMs_Output = [%s]" 			% host.declareVMs()					,{'style': 'INFO'} )
	message ( "Create_Centos_VM_Output = [%s]" 		% host.instantiate_centos_VMs()		,{'style': 'INFO'} )
	message ( "PowerON-VMs_Output = [%s]" 			% host.startVMs()					,{'style': 'INFO'} )
	return  get_rc_ok()

def objectify_vms(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		if not config['HOSTS'][host][vm_name]['vm_ref']:
			vm = vm_node(config,host,vm_name)
			config['HOSTS'][host][vm_name]['vm_ref'] = vm
	return get_rc_ok()

def shareKeys(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		message ( "Now sharing pub-keys inside VM %s" % vm_name									, {'style': 'DEBUG'} ) 
		if vm.ssh_self():
			message ( "old SSHkeys removal in %s = \t\t%s " % (vm_name,vm.removeAuthKeys())		, {'style': 'INFO'} )
			message ( "SSH Keys addition in %s = \t\t%s " % (vm_name,vm.authPubKeys())			, {'style': 'INFO'} )
			message ( "Config-Write_Output = %s " % vm.config_write()							, {'style': 'TRACE','to_trace':'1'} )
		else:
			message ( "SSH capability on %s not working." % vm_name								, {'style': 'DEBUG'} )
			terminate_self("Exiting")
	return get_rc_ok()

def setupClusters(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Setting clusters inside VM %s" % vm_name								, {'style': 'DEBUG'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.ssh_self():
			if vm.is_clusternode():
				message ( "Clustering Setup in %s = %s " % (vm_name,vm.setclustering())		, {'style': 'INFO'} )
				time.sleep(5) # Let clustering settle down
				message ( "Config-Write_Output = %s " % vm.config_write()			, {'style': 'TRACE','to_trace':'1'} )
			else:
				message ( "Nothing to do in %s" %vm_name							, {'style': 'INFO'} )
		else:
			message ( "SSH capability on %s not working." % vm_name					, {'style': 'DEBUG'} )
			terminate_self("Exiting")
			
	return get_rc_ok()

def setupStorage(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Setting up storage inside VM %s" % vm_name					,{'style': 'DEBUG'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		try:
			if vm.ssh_self():
				if vm.has_storage():
					message ("Storage Configuration in %s = \t%s" % (vm_name,vm.bring_storage()) 		,{'style': 'INFO'} )
					message ("Multipath LUN-Aliasing in %s = \t%s" % (vm_name,vm.mpio_alias())	 		,{'style': 'INFO'} )
					if not opt_skip_format :
						message ( "Storage LUN Format in %s = \t%s" % (vm_name,vm.format_storage()) 	,{'style': 'INFO'} )
					else:
						record_status("STORAGE Operations",get_rc_skipped())
					message ( "Gmountd Configuration in %s = \t%s" % (vm_name,vm.mount_storage())		,{'style': 'INFO'} )
					message ( "Config-Write_Output in %s = %s" % (vm_name,vm.config_write())			,{'style': 'TRACE','to_trace':'1'} )
				else:
					message ( "No storage configured for node %s" % vm_name							,{'style': 'DEBUG'} )
		except Exception,err:
			message ( "SSH capability on %s not working. %s" % (vm_name,str(err))					,{'style': 'DEBUG'} )
			terminate_self("Exiting")
	return get_rc_ok()

def setupHDFS(tuples):
	for line in tuples:
		host,vm_name = line.split(":")
		message ( "Now setting up HDFS inside VM %s" % vm_name,{'style': 'DEBUG'} )
		vm = config['HOSTS'][host][vm_name]['vm_ref']
		if vm.is_namenode():
			if vm.ssh_self():
				message ("Setup-HDFS_Output in %s = \t\t[%s]" % (vm_name,vm.setup_HDFS()),{'style': 'INFO'} )
			else:
				message ( "SSH capability on %s not working." % vm_name, {'style': 'DEBUG'} )
				terminate_self("Exiting")
	return get_rc_ok()

def validate(config):
	validator = Validator()
	results = config.validate(validator, preserve_errors=True)
	if results != True:
		for (section_list, key, _) in flatten_errors(config, results):
			if key is not None:
				message ( 'The "%s" key in the section "%s" failed validation' % (key, ', '.join(section_list)), {'style':'DEBUG'} )
			else:
				message ( 'The following section was missing:%s ' % ", ".join(section_list) , {'style':'DEBUG'} )
		message ('Config file %s validation failed!'% config_filename, {'style':'FATAL'})
		terminate_self("Exiting.")
	else :
		message ( 'INI validated', {'style':'OK'} )

def wipe_vmpool(hosts):
	message ( 'Wiping Hosts VM pools', {'style': 'INFO'} )
	for host_name in hosts:
		host = config['HOSTS'][host_name]['host_ref']
		message ( "WipeSetup_Output = %s " %host.wipe_setup()             , {'style': 'INFO'} )
		return get_rc_ok()


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
	robot_path		=	os.path.dirname(__file__)
	os.environ["ROBOT_PATH"] = os.path.abspath(robot_path)
	os.environ["INSTALL_PATH"] = os.path.dirname(os.environ["ROBOT_PATH"])
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
						help='Custom logfile name. Default is <ScriptName.Time.log>')
	parser.add_argument("-c","--check-ini",
						dest='checkini',
						action='store_true',
						default=False,
						help='Just validate INI file')
	parser.add_argument("--rpm",
						dest='rpm_model',
						action='store_true',
						default=False,
						help='Test Platform rpm model')
	parser.add_argument("--lazy",
						dest='lazy',
						action='store_true',
						default=False,
						help='Skip creating template. Use previous one')
	parser.add_argument("--reconfig",
						dest='reconfig',
						action='store_true',
						default=False,
						help='Skip manufacturing. Factory revert and apply INI')
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
						help='Delete Host\'s complete VM-Pool in initialisation')
	parser.add_argument("--backup-hdfs",
						dest='backup_hdfs',
						action='store_true',
						default=False,
						help='Configure backup hdfs also in collector-config')
	parser.add_argument("--col-sanity",
						dest='col_sanity',
						action='store_true',
						default=False,
						help='Execute Collector Sanity test-suite too.')
	parser.add_argument("--col-sanity-only",
						dest='col_sanity_only',
						action='store_true',
						default=False,
						help='Run Collector Sanity test-suite only')
	parser.add_argument("--email",
						dest='email',
						action='store_true',
						default=False,
						help='Send results and report in email')
	parser.add_argument("--mail_subject",
						nargs=1,
						dest='mail_subject',
						type=str,
						default=['Hubrix Notification'],
						help='Send hubrix notification with this subject')
	parser.add_argument("--mail_cc",
						nargs='*',
						dest='mail_cc',
						metavar='Recipient',
						type=str,
						default=False,
						help='Add extra email recipients to INI configuration')
	parser.add_argument("--skip-vm",
						nargs='+',
						dest='skip_vm',
						type=str,
						help='TOBE_IMPLEMENTED skip vm in ini with these names')

	args = parser.parse_args()
	config_filename 		= args.INIFILE[0]
	opt_skip_format 		= args.skip_format
	opt_force_format		= args.force_format
	opt_storage				= args.storage
	opt_ha					= args.setup_ha
	opt_hdfs				= args.setup_hdfs
	opt_wipe				= args.wipe_host
	opt_skipvm				= args.skip_vm
	opt_mail_subject		= args.mail_subject[0]
	opt_mail_recievers		= args.mail_cc
	opt_lazy				= args.lazy
	opt_checkini			= args.checkini
	opt_reconfig			= args.reconfig
	opt_backuphdfs			= args.backup_hdfs
	opt_colsanity			= args.col_sanity
	opt_colsanity_only		= args.col_sanity_only
	opt_email				= args.email
	opt_rpm					= args.rpm_model
	os.environ['BACKUP_HDFS'] = ("", "False")[opt_backuphdfs]
	os.environ['RPM_MODE']	= ("", "True")[opt_rpm]
	allvms = None
	if args.log:
		os.environ["LOGFILE_NAME"] = args.log[0]
		
	message ("Got input file as %s " % config_filename,{'to_stdout' : 1, 'to_log' : 1, 'style' : 'INFO'})
	if not os.path.isfile(config_filename):
		message ( "INI file %s doesnot exists."%(config_filename) ,	{'style':'FATAL'} )
		sys.exit(1)
	configspec='config.spec'
	config = ConfigObj(config_filename,raise_errors=False,list_values=True,interpolation=True,configspec=configspec)
	validate(config)
	config['HOSTS']['notifySubject'] = opt_mail_subject
	if isinstance(opt_mail_recievers, list):
		for recipient in opt_mail_recievers:
			config['HOSTS']['notifyTo'].append(recipient) 
		

	if opt_checkini :
		exit()
	if not opt_colsanity_only :
		if opt_skip_format and opt_force_format :
			message ( "No-Format and force format options cannot be used together." ,	{'style':'FATAL'} )
			sys.exit(1)
		if opt_wipe and opt_lazy :
			message ( "Wipe and Lazy options cannot be used together.", 				{'style':'FATAL'} )
			sys.exit(1)
		if opt_wipe and opt_reconfig:
			message ( "Wipe and Reconfig cannot be used together.",						{'style':'FATAL'} )
			sys.exit(1)
		if opt_lazy and opt_reconfig:
			message ( "Lazy and Reconfig cannot be used together.",						{'style':'FATAL'} )
			sys.exit(1)
		if not opt_lazy and not opt_reconfig and not opt_rpm :
			message ( "Verifying iso exists.",			{'style':'INFO'} )
			if not check_iso_exists(config):
				terminate_self("Cannot proceed further as iso not present")
			else:
				message ( "ISO url valid.",						{'style':'INFO'} )
		if opt_colsanity :
			message ( "Will be running Collector Test-Suite ",			{'style':'INFO'} )
	else :
		message ( "Will be running Collector Test-Suite Only",			{'style':'INFO'} )

	hosts = get_hosts(config)
	install_type = config['HOSTS']['install_type']	
	if opt_force_format:
		config['HOSTS']['force_format'] = True
	else:
		config['HOSTS']['force_format'] = False
		
	start_time = time.time()
	
#						,
#					/\^/`\   
#				   | \/   |
#				   | |    |                               
#				   \ \    /                             _ _
#					'\\//'                            _{ ' }_
#					  ||     MAIN Execution Section  { `.!.` }
#					  ||                             ',_/Y\_,'
#					  ||  ,                            {_,_}
#				  |\  ||  |\                             |
#				  | | ||  | |                          (\|  /)
#				  | | || / /                            \| //
#				   \ \||/ /                              |//
#					`\\//`   \   \./    \\   \./    \ \\ |/ /

			#+-------------------------+
			#| Manufacture if required |
			#+-------------------------+

	if not opt_colsanity_only:
		#Setup Hosts Connectivity 
		connect_hosts(hosts)
		if opt_wipe :
			wipe_vmpool(hosts)
		if opt_rpm  :
			install_type = 'rpm_model'
			if not opt_reconfig:
				do_centosInstall(hosts)
		if 'manufacture' in install_type:
			if not opt_reconfig:
				do_manufacture(hosts)
				pass
			else :
				record_status("Manufacturing with ISO",get_rc_skipped())

			#+---------------------------------------------+
			#| Scan INI and make necessary Data Structures |
			#+---------------------------------------------+

	allvms = get_allvms(config)
	objectify_vms(allvms)

	####terminate_self("Exiting")
	
			#+--------------------------+
			#| Appliance Mode Execution |
			#+--------------------------+

	if not opt_colsanity_only and not opt_rpm:
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
			setup_yarn_info.append(monospace_text(br_text_to_html(collect_yarn_setup_info(allvms))))
			checkHDFS(allvms)
			config_collector(allvms)
		else:
			record_status("HDFS Current Status",get_rc_skipped())
		
			#+--------------------+
			#| RPM Mode Execution |
			#+--------------------+

	if opt_rpm:
		centos_sync_basic_settings(allvms)
		centos_keygen(allvms)
		centos_keyshare(allvms)
		if opt_storage is True:
			centos_cfg_storage(allvms)
		centos_sync_install_reflex(allvms)
		centos_reflex_keygen(allvms)
		centos_reflex_keyshare(allvms)
		
		if opt_ha is True:
			centos_setupClusters(allvms)
		else:
			clear_ha(allvms)
			
		if opt_hdfs is True:
			centos_setupHDFS(allvms)
			hdfs_report = centos_checkHDFS(allvms)
			setup_yarn_info.append(collect_yarn_setup_info(allvms))
			config_collector(allvms)
		else:
			record_status("HDFS Current Status",get_rc_skipped())

	if opt_email:
		message ('Sending out emails: ' ,{'style' : 'info'})
		attachment = collect_results()
		hdfs_html_report = HTML.Table(header_row=['hdfs dfsadmin report'])
		hdfs_html_report.rows.append(setup_yarn_info)
		yarn_config_report = HTML.Table(header_row=['yarn config check'])
		yarn_config_report.rows.append(hdfs_report)
		notify_email(config,str(hdfs_html_report)+str(yarn_config_report),attachment)
		clean_results(attachment)
	else :
		message ('Not sending out emails' ,{'style' : 'info'})
	manuf_runtime = time.time() - start_time
	message ('Manufacture Runtime: ' + str(datetime.timedelta(seconds=manuf_runtime)),	{'style' : 'info'})
		
	if opt_colsanity or opt_colsanity_only :
		checkColSanity(allvms)
		attachment = collector_results()
		notify_email(config,"Collector Sanity Report",attachment)
		clean_results(attachment)

	if 'upgrade' in install_type:
		do_upgrade()

	total_runtime = time.time() - start_time
	message ('Summary Execution: \n%s'%(display_testresults()),{'style' : 'info'})
	message ('Total Runtime: ' + str(datetime.timedelta(seconds=total_runtime)),		{'style' : 'info'})

	message("-- Script Finished Execution --", { 'style':'ok' } )

# Debug Command
# pydbgp -d localhost:9001  Setup.py  INIFILE

#TODO
# FIX in case of --no-ha unregister cluster not called
# Exception if there is one "virt volume fetch url" already running on Host system.retry after 5 min
# validate other config.spec parameters.
# Remove forbidden nodes from the iscsi connection after the setup
