#!/usr/bin/env python 
import paramiko
import string, re
import time
import traceback
import commands
import os,sys
import random
from session import session
from Toolkit import message,terminate_self,clear_collector_logs,get_startProcess

class vm_node(object):
	nodes_ip = {}
	pub_keys = []
	name_nodes = []
	journal_nodes = []
	data_nodes = []
	re_ssh_pubkey = re.compile( r"^(?P<pubkey>ssh-dss\s+\S+)",re.M)

	def __init__(self,config,host,vm):
		self._name 					= vm
		self._host 					= host
		self._ssh_session 			= None
		self._dsakey 				= None
		self._mgmtMac 				= self.randomMAC()
		self._storMac 				= self.randomMAC()
		self._hostid 				= self.hostid_generator()
		self._diskimageFull 		= "/data/virt/pools/default/%s.img" % self._name
		self._diskimage 			= "%s.img" % self._name
		self._ntpserver				= config['HOSTS']['ntp_server']
		self._name_server			= config['HOSTS']['name_server']
		self._snmpsink				= config['HOSTS']['snmpsink_server']
		self._release_ver			= config['HOSTS']['release_ver']
		self._upgrade_img			= config['HOSTS']['upgrade_img']
		self._centos_repo_path		= config['HOSTS']['centos_repo_path']
		self._brMgmt				= config['HOSTS'][host]['brMgmt']
		self._brStor				= config['HOSTS'][host]['brStor']
		self._template				= config['HOSTS'][host]['template_file']
		self._enabledusers			= config['HOSTS'][host][vm]['enabled_users']
		self._clusterVIP			= config['HOSTS'][host][vm]['cluster_vip']
		self._namenode				= config['HOSTS'][host][vm]['name_node']
		self._journalnode			= config['HOSTS'][host][vm]['journal_node']
		self._initiatorname_iscsi	= config['HOSTS'][host][vm]['storage']['initiatorname_iscsi']
		self._iscsi_target			= config['HOSTS'][host][vm]['storage']['iscsi_target']
		self._forbidden_nodes		= config['HOSTS'][host][vm]['storage']['forbidden_nodes']
		self._tps_fs				= config['HOSTS'][host][vm]['tps-fs']
		self._cluster_name			= config['HOSTS'][host][vm]['cluster_name']
		self._mgmtNic				= config['HOSTS'][host][vm]['mgmtNic']
		self._storNic				= config['HOSTS'][host][vm]['storNic']
		self.nodes_ip[vm]			= config['HOSTS'][host][vm]['mgmt_ip']
		self._ip					= config['HOSTS'][host][vm]['mgmt_ip']
		self._mask					= config['HOSTS'][host][vm]['mgmt_mask']
		self._gw					= config['HOSTS'][host][vm]['gw']
		self._stor_ip				= config['HOSTS'][host][vm]['stor_ip']
		self._stor_mask				= config['HOSTS'][host][vm]['stor_mask']
		self._cpu					= config['HOSTS'][host][vm]['cpus']
		self._memory				= config['HOSTS'][host][vm]['memory']
		try:
			self._host_ssh_session		= config['HOSTS'][host]['ssh_session']
		except Exception :
			self._host_ssh_session		= False
		self.config_ref				= config
		if self._namenode:
			self.registerNameNode()
		elif self._journalnode:
			self.registerJournalNode()
		else:
			self.registerDataNode()

	def __del__(self):
		if self._ssh_session != None:
			self._ssh_session.close()
			message ( "Deleting vm object for %s " % self._name, {'to_trace': '1' ,'style': 'TRACE'} )

	def _set_clusterName(self):
		if self._clusterVIP :
			computed_name = str(self.dottedQuadToNum(self._clusterVIP))
			message ( "Cluster VIP computed as %s " % computed_name, {'to_trace': '1','style': 'TRACE'} )
			return computed_name
		else:
			message ( "Raise Exception..not a clusterNode still you are asking clusterName", {'style': 'FATAL'} )

	def _get_loop_device(self):
		result = self._host_ssh_session.executeCli('_exec /sbin/losetup -f')
		next_loop_device = "".join(result.split())
		message ( "Next available Loop device is %s " % next_loop_device,{'to_trace': '1' ,'style': 'TRACE'}  )
		try:
			if "/dev/" in next_loop_device:
				return next_loop_device
		except Exception :
				message ( "Unable to get a free loop device on Host", {'style': 'FATAL'} )
				return False
	
	def authPubKeys(self):
		output = ''
		output += self._ssh_session.executeCli('ssh client global host-key-check no')
		for creds in self.pub_keys:
			user,pubkey = creds.split(":")
			if user == "root":
				continue
			output += self._ssh_session.executeCli('ssh client user %s authorized-key sshv2 \"%s\"'%(user,pubkey))
		return output

	def bring_storage(self):
		output = ''
		output += self._ssh_session.executeCli('tps iscsi initiator-name %s' %self._initiatorname_iscsi)
		output += self._ssh_session.executeCli('_exec service iscsid restart')
		output += self._ssh_session.executeCli('tps iscsi show targets %s' % self._iscsi_target)
		if self._forbidden_nodes:
			output += self.remove_iscsiForbidden()
		output += self._ssh_session.executeCli('tps iscsi restart')
		time.sleep(15)
		output += self._ssh_session.executeCli('tps multipath renew ')
		return output
	
	def centos_bring_storage(self):
		output = ''
		response = ''
		output += self._ssh_session.executeShell('echo \"InitiatorName=%s\" > /etc/iscsi/initiatorname.iscsi ' %self._initiatorname_iscsi)
		output += self._ssh_session.executeShell('service iscsi stop;echo')
		output += self._ssh_session.executeShell('service iscsid restart;echo')
		time.sleep(5)
		response = self._ssh_session.executeShell('iscsiadm -m discovery -t st -p %s' % self._iscsi_target)
		if response.find("Could not perform SendTargets discovery") != -1:
			message ( "Raise Exception.Could not perform SendTargets discovery in %s" %(self._name), {'style': 'FATAL'} )
			raise Exception("Could not perform SendTargets discovery in %s" %(self._name))
			return "Failure storage config in %s" %(self._name)

		output += self._ssh_session.executeShell('service iscsi restart')
		output += self._ssh_session.executeShell('chkconfig iscsi on')
		time.sleep(15)
		output += self._ssh_session.executeShell('mpathconf --enable --with_multipathd y --with_module y --find_multipaths  y  --user_friendly_names y')
		time.sleep(5)
		output += self._ssh_session.executeShell('multipath')
		return output
	
	def centos_validate_HDFS(self):
		if self.is_clusternode() and not self.is_clustermaster():
			return "Part of Cluster but not master. skipping node %s" % self._name
		output = ''
		report = ''
		retry = 0
		validate_status = False
		while retry <= 15:
			try:
				res_man = self.is_ResManUp()
				if res_man :
					message ("Resource Manager is up in %s" % self._name, {'style':'ok'} )
					res_manStart = get_startProcess(res_man)
					message ("Resource Manager is running since %s seconds" % res_manStart, {'style':'info'})
					if ( res_manStart < 300):
						time2wait = 300 - res_manStart
						message ("Waiting for %s seconds before running hdfs report" % time2wait, {'style':'info'})
						time.sleep(time2wait)
					output += self.info_yarn_Setup()
					validate_status = True
					break
				else:
					retry += 1
					message ("Attempt %s. Resource Manager is not running. Waiting total 15 min" % retry, {'style':'WARNING'})
					time.sleep(60)
			except Exception:
				message ("Not able to validate HDFS %s." % output, {'style':'FATAL'})
				return False
		
		message ("Now HDFS config report", {'style':'INFO'})
		report += str(self.hdfs_report())
		if report.find('ERROR') != -1 :
			message ("HDFS Report = %s" % report ,{'style':'NOK'} )
		else :
			message ("HDFS Report = %s" % report ,{'style':'OK'} )
		output += report 
		return output

	def centos_cfg_rsyslog(self):
		output = ''
		output += self._ssh_session.executeShell('grep -q \'$SystemLogRateLimitInterval 0\' /etc/rsyslog.conf  && echo \'rsyslog.conf already has $SystemLogRateLimitInterval 0\'  || echo \'$SystemLogRateLimitInterval 0\' >> /etc/rsyslog.conf ' )
		output += self._ssh_session.executeShell('service rsyslog restart')
		return output

	def centos_cfg_ntp(self):
		output = ''
		ntp_config = '''restrict default nomodify notrap noquery
driftfile /var/lib/ntp/drift
restrict 127.0.0.1
restrict -6 ::1
server %s iburst maxpoll 9
includefile /etc/ntp/crypto/pw
keys /etc/ntp/keys
''' %(self._ntpserver)
		output += self._ssh_session.executeShell('ntpdate -u %s' %(self._ntpserver))
		output += self._ssh_session.executeShell('echo \"%s\" > /etc/ntp.conf ' %(ntp_config))
		output += self._ssh_session.executeShell('service ntpd start' )
		output += self._ssh_session.executeShell('chkconfig ntpd on ')
		output += self._ssh_session.executeShell('chkconfig ntpdate on ')
		return output
	
	def centos_col_basic(self):
		output = ''
		try:
			output += self._ssh_session.executeCliasUser('reflex','pm process collector launch enable')
			output += self._ssh_session.executeCliasUser('reflex','pm process collector launch relaunch auto')
			output += self._ssh_session.executeCliasUser('reflex','pm process collector launch auto')
			output += self._ssh_session.executeCliasUser('reflex','pm liveness grace-period 600')
			output += self._ssh_session.executeCliasUser('reflex','internal set modify - /pm/process/collector/term_action value name /nr/collector/actions/terminate')
			output += " Success"
		except Exception:
			message ("Failed in config_collector" ,						{'style':'NOK'})
			return "Failed"
		return output
	
	def centos_format_storage(self):
		output = ''
		format_option = ""
		global_format_forced = self.config_ref['HOSTS']['force_format']
		if global_format_forced:
			format_option += "no-strict"
			message ( "Forcing format on %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			
		for fs_name in self._tps_fs.keys():
			ini_format_option = self._tps_fs[fs_name]['format']
			if ini_format_option is False:
				message ( "Skipping format in FS %s on %s" % (fs_name,self._name),{'to_trace': '1' ,'style': 'TRACE'}  )
				continue
			
			count = 10
			wwid = self._tps_fs[fs_name]['wwid'].lower()
			while count > 0 :
				current_multipaths = self._ssh_session.executeShell('multipath -ll')
				message ( "Current multipaths =  %s on %s" % (current_multipaths,self._name),{'to_trace': '1' ,'style': 'TRACE'}  )
				#output += current_multipaths 
				if wwid in current_multipaths:
					dm_device = self._ssh_session.executeShell('readlink -f /dev/disk/by-id/dm-uuid-mpath-%s' 			% (wwid)).splitlines()[-1]
					full_output =  self._ssh_session.executeShell('parted -s %s -- \"rm 1\"' 							% (dm_device))
					full_output =  self._ssh_session.executeShell('parted -s %s -- mklabel gpt ' 						% (dm_device))
					full_output =  self._ssh_session.executeShell('parted -s %s -- unit %% mkpart primary ext3 0 100' 	% (dm_device))
					dm_partition = self._ssh_session.executeShell('readlink -f /dev/disk/by-id/dm-uuid-part1-mpath-%s' 	% (wwid)).splitlines()[-1]
					full_output =  self._ssh_session.executeShell('mkfs.ext3 %s -L \"%s\"'				 				% (dm_partition,fs_name))
					output += full_output.splitlines()[-1]
					break
				elif wwid not in current_multipaths:
					count = count - 1
					output += self._ssh_session.executeShell('multipath')
					message ( "waiting for %s lun with wwid=%s to come in multipath. retrying in 1 sec" % (fs_name,wwid),
							 {'style': 'INFO'} )
					time.sleep(1)
					continue
		return output

	def centos_factory_revert(self):
		output = ''
		output += self._ssh_session.executeShell('service reflex stop')
		output += self._ssh_session.executeShell('yum erase -y reflex*')
		output += self._ssh_session.executeShell('rm -rf  /opt/reflex')
		return output
	
	def centos_get_repo(self):
		output = ''
		output += self._ssh_session.executeShell('curl %s -o /etc/yum.repos.d/CentOS-Base.repo' % (self._centos_repo_path))
		output += self._ssh_session.executeShell('yum clean all')
		return output
	
	def centos_distkeys(self,user):
		output = ''
		ssh_client_config = '''Host *
CheckHostIP no
ConnectionAttempts 1
IdentityFile ~/.ssh/id_dsa
KeepAlive yes
PubkeyAuthentication yes
StrictHostKeyChecking no
UsePrivilegedPort no
UserKnownHostsFile /dev/null
'''
		output += self._ssh_session.executeShell('echo \"%s\" > ~%s/.ssh/config ' %(ssh_client_config,user))
		for creds in self.pub_keys:
			username,pubkey = creds.split(":")
			if username != user:
				continue
			output += self._ssh_session.executeShell('echo \"%s\" >> ~%s/.ssh/authorized_keys ' %(pubkey,user))
		output += self._ssh_session.executeShell('chown -R %s:%s ~%s/.ssh ' %(user,user,user))
		output += self._ssh_session.executeShell('restorecon -R ~%s/.ssh ' %(user))
		return output
		
	def centos_genkeys(self,user):
		output = ''
		output += self._ssh_session.executeShell('mkdir -p ~%s/.ssh/' %(user))
		output += self._ssh_session.executeShell('yes | ssh-keygen -q -t dsa -N \"\" -f ~%s/.ssh/id_dsa;echo' %(user))
		output += self._ssh_session.executeShell('chown -R %s:%s ~%s/.ssh ' %(user,user,user))
		output += self._ssh_session.executeShell('restorecon -R ~%s/.ssh ' %(user))
		self._dsakey = self._ssh_session.executeShell('cat ~%s/.ssh/id_dsa.pub ' %(user))
		tuples = user + ":" + self._dsakey
		self.pub_keys.append(tuples)
		return output
	
	def centos_install_base(self):
		output = ''
		response = ''
		base_pkgs = "wget ntp ntpdate kpartx net-snmp net-snmp-utils parted yum-utils tcpdump lrzsz lsof screen xz strace"
		output 	+= self._ssh_session.executeShell('yum clean all' )
		message ( "Installing pkgs [%s] in %s " % ( base_pkgs, self._name) ,{'to_trace': '1' ,'style': 'TRACE'}  )
		response = self._ssh_session.executeShell('yum install -y %s'%(base_pkgs) )
		output += response[-80:]
		# I dont like hardcoding these packages location, but thats how it is now.
		message ( "Installing pkg jre1.8.0_31-1.8.0_31-fcs.x86_64.rpm in %s " % ( self._name) ,{'to_log': '1' ,'style': 'INFO'}  )
		response = self._ssh_session.executeShell('yum install -y http://192.168.104.78/users/kapil/RPM/java-rpms/jre1.8.0_31-1.8.0_31-fcs.x86_64.rpm' )
		message ( "Installing pkg virtual-java-1.8-31.noarch.rpm in %s " % ( self._name) ,{'to_log': '1' ,'style': 'INFO'}  )
		output += response[-80:]
		response = self._ssh_session.executeShell('yum install -y http://192.168.104.78/users/kapil/RPM/java-rpms/virtual-java-1.8-31.noarch.rpm' )
		output += response[-80:]
		return output
	
	def centos_mount_storage(self):
		output = ''
		for fs_name in self._tps_fs.keys():
			wwid 			= self._tps_fs[fs_name]['wwid'].lower()
			mount_point 	= self._tps_fs[fs_name]['mount-point']
			output		   += self._ssh_session.executeShell('mkdir -p %s' 	% (mount_point))
			dm_partition 	= self._ssh_session.executeShell('readlink -f /dev/disk/by-id/dm-uuid-part1-mpath-%s' 	% (wwid)).splitlines()[-1]
			uuid 			= self._ssh_session.executeShell('blkid %s |grep -o \'[A-Za-z0-9-]\\{36\\}\' ' %(dm_partition)).splitlines()[-1]
			mapper_device 	= self._ssh_session.executeShell('findfs UUID=%s ' %(uuid)).splitlines()[-1]
			if mapper_device.find("unable to resolve") != -1 :
				message ( "Cannot Resolve UUID for wwid=%s. Check if partition is present." %(wwid) , {'style': 'FATAL'} )
				return "Failure setting up mount-points"
#			output 			+= self._ssh_session.executeShell('sed -i -e \'s#^%s.*$#%s %s _netdev 0 0#\' /etc/fstab' %(mapper_device, mapper_device, mount_point))
			output 			+= self._ssh_session.executeShell('echo \"%s %s ext3 _netdev 0 0\" >> /etc/fstab' % (mapper_device, mount_point))
			output			+= self._ssh_session.executeShell('mount -av -O _netdev')
			output			+= self._ssh_session.executeShell('restorecon -R %s '	% (mount_point))
		return output
	
	def centos_rotate_logs(self):
		output = ''
		output += self._ssh_session.executeShell('logrotate -f /etc/logrotate.conf')
		return output
	
	def centos_setIpHostMaps(self):
		output = ''
		for vm in self.nodes_ip.keys():
			output += self._ssh_session.executeShell('grep -q %s /etc/hosts && sed -i -e \'s/^%s.*$/%s %s/\' /etc/hosts || echo \"%s %s\" >> /etc/hosts' %(vm, self.nodes_ip[vm],self.nodes_ip[vm],vm, self.nodes_ip[vm],vm))
		return output

	def centos_install_reflex(self):
		output = ''
		response = ''
		reflex_package_list = []
		reflex_package_list.append('reflex-tm')
		reflex_package_list.append('reflex-common')
		reflex_package_list.append('hadoop')
		reflex_package_list.append('reflex-tps')
		if self.is_namenode():
			reflex_package_list.append('reflex-collector')

		output 	+= self._ssh_session.executeShell('yum clean all ')
		for reflex_pkg in reflex_package_list:
			response = self._ssh_session.executeShell('yum install -y %s ' %(reflex_pkg))
		output += response[-80:]
		return output
	
	def centos_setclustering(self):
		output = ''
		cmd = ''
		if not self.is_clusternode():
			message ( "Improper calling of setclustering in %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			return False # TODO Raise exception
		if not self._cluster_name:
			self._cluster_name = self._set_clusterName()
			
		cmd += "cluster id %s \n" % (self._cluster_name)
		cmd += "cluster master address vip %s /%s \n" %(self._clusterVIP,self._mask)
		cmd += "cluster name %s \n" % (self._cluster_name)
		cmd += "cluster enable \n"
		output += self._ssh_session.executeCliasUser('reflex',cmd,timeout=15)
		return output

	def centos_setup_HDFS(self):
		HA =''
		journal_nodes = ''
		output = ''
		client_ip = None 
		cmd = "no register hadoop_yarn\n"
		cmd += "register hadoop_yarn\n"
		
		if self.is_clusternode():
			HA = 'True'
			client_ip = self._clusterVIP
		else:
			HA = 'False'
			client_ip = self.nodes_ip[self.name_nodes[0]]
			
		cmd += "set hadoop_yarn config_ha %s \n" % HA
		cmd += "set hadoop_yarn namenode1 %s \n" % self.name_nodes[0]
		
		if self.is_clusternode():
			cmd += "set hadoop_yarn namenode2 %s \n" % self.name_nodes[1]
			cmd += "set hadoop_yarn nameservice %s \n" % self.config_ref['HOSTS']['yarn_nameservice']
			for node in self.journal_nodes:
				cmd += "set hadoop_yarn journalnodes %s \n" % node
			for node in self.name_nodes:
				cmd += "set hadoop_yarn journalnodes %s \n" % node

		for node in self.journal_nodes:
			cmd += "set hadoop_yarn slave %s \n" % self.nodes_ip[node]
		for node in self.data_nodes:
			cmd += "set hadoop_yarn slave %s \n" % self.nodes_ip[node]

		cmd += "set hadoop_yarn client %s \n" % client_ip
		cmd += "set hadoop_yarn state UNINIT \n"
		
		if os.environ['BACKUP_HDFS'] and not os.environ['RPM_MODE']  :
			cmd += "register backup_hdfs\n"
			cmd += "set backup_hdfs namenode UNINIT\n"
			
		cmd = "pmx <<EOF\n" + cmd + "EOF\n"
		
		output += self._ssh_session.executeShellasUser('reflex',cmd)
		output += self._ssh_session.executeCliasUser('reflex',"pm process tps restart")
		message ( "TPS restarted in node %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		
		return output
	
	def clone_volume(self):
		output =  self._host_ssh_session.executeCli("_exec /bin/cp -f --sparse=always %s %s" % (self._template,self._diskimageFull))
		message ( "cloned volume for %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		return output

	def col_basic(self):
		output = ''
		try:
			output += self._ssh_session.executeCli('pm process collector launch enable')
			output += self._ssh_session.executeCli('pm process collector launch relaunch auto')
			output += self._ssh_session.executeCli('pm process collector launch auto')
			output += self._ssh_session.executeCli('pm liveness grace-period 600')
			output += self._ssh_session.executeCli('internal set modify - /pm/process/collector/term_action value name /nr/collector/actions/terminate')
			output += " Success"
		except Exception:
			message ("Failed in config_collector" ,						{'style':'NOK'})
			return "Failed"
		return output

	def collector_sanity(self):
		from subprocess import Popen, PIPE
		if self.is_clusternode() and not self.is_clustermaster():
			return "Part of Cluster but not master. skipping node %s" % self._name
		output = ''
		sanity_script = "collector_sanity.py"
		test_suite_path = os.environ["INSTALL_PATH"]  + "/" + "hubrix/GuavusAutomationPlatform/test_suite"
		clear_collector_logs()
		message ("Starting collector sanity in %s" % self._name, 		{'style':'INFO'} )
		output += Popen("python " + sanity_script + " -i " + self._ip , cwd=test_suite_path,shell=True, stdout=PIPE).communicate()[0]
		message ("Collector Sanity is complete in %s" % self._name, 	{'style':'OK'} )
		return output

	def configure(self):
		output = ''
		try:
			output += self._host_ssh_session.executeCli('no virt vm %s' % self._name)
			output += self._host_ssh_session.executeCli('virt vm %s vcpus count %s' % (self._name,self._cpu) )
			output += self._host_ssh_session.executeCli('virt vm %s memory %s' % (self._name,self._memory) )
			output += self._host_ssh_session.executeCli('virt vm %s storage device bus virtio drive-number 1 source file %s mode read-write' % (self._name,self._diskimage) )
			output += self._host_ssh_session.executeCli('virt vm %s interface 1  bridge %s' % (self._name,self._brMgmt) )
			output += self._host_ssh_session.executeCli('virt vm %s interface 1 macaddr %s' % (self._name,self._mgmtMac) )
			output += self._host_ssh_session.executeCli('virt vm %s interface 2  bridge %s' % (self._name,self._brStor) )
			output += self._host_ssh_session.executeCli('virt vm %s interface 2 macaddr %s' % (self._name,self._storMac) )    
			output += self._host_ssh_session.executeCli('virt vm %s comment %s' % (self._name, "\"Manufctd with Image %s\""%self._release_ver ))
			output += self._host_ssh_session.executeCli('virt vm %s memory %s' % (self._name,self._memory ))
			output += " Success"
		except Exception:
			message ("Failure configuring Err = %s in VM %s" % (output,self._name) ,{'style':'TRACE'})
			return False
		return output 

	def config_write(self):
		output = ''
		output += self._ssh_session.executeCli('config write')
		return output

	def config_ntp(self):
		output = ''
		output += self._ssh_session.executeCli('ntpdate  %s' % self._ntpserver)
		output += self._ssh_session.executeCli('ntp server %s' % self._ntpserver)
		output += self._ssh_session.executeCli('ntp enable ')
		return output

	def config_dns(self):
		output = ''
		output += self._ssh_session.executeCli('ip name-server %s' % self._name_server)
		return output

	def configusers(self):
		for creds in self._enabledusers:
			user,password = creds.split(":")
			self.set_user(user,password)
		
	def delete_iscsiNode(self,ip_port):
		output = ''
		if not ip_port :
			return False
		try :
			output += self._ssh_session.executeCli('_exec iscsiadm -m node -p %s -o delete' % ip_port )
			if output.find("a session is using it") != -1:
				message ("Cannot delete node %s , a session exists for it" % ip_port,{'style':'NOK'})
				return False
			else :
				message ("Deleted iscsi node %s " % ip_port,{'style':'OK'})
				return True
		except Exception:
			message ("Unable to delete node %s => %s" % (ip_port,output) ,{'style':'NOK'})

	def dottedQuadToNum(self,ip):
		hexn = ''.join(["%02X" % long(i) for i in ip.split('.')])
		return long(hexn, 16)

	def disable_clustering(self):
		if not self.is_clusternode():
			return False
		return session.executeCli('no cluster enable')

	def delete_volume(self):
		output =  self._host_ssh_session.executeCli("no virt volume file %s" % self._diskimage)
		message ( "deleted volume for %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		return output

	def disable_paging(self):
		output = ''
		output += self._ssh_session.executeCli("no cli default paging enable")
		return output

	def disable_timeout(self):
		output = ''
		output += self._ssh_session.executeCli("cli session auto-logout 300") # Setting 5 hour session timeout
		return output
	
	def factory_revert(self):
		output = ''
		output += self._ssh_session.executeCli('configuration revert factory',wait=10)
		return output

	def format_storage(self):
		output = ''
		format_option = ""
		global_format_forced = self.config_ref['HOSTS']['force_format']
		if global_format_forced:
			format_option += "no-strict"
			message ( "Forcing format on %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			
		for fs_name in self._tps_fs.keys():
			ini_format_option = self._tps_fs[fs_name]['format']
			if ini_format_option is False:
				message ( "Skipping format in FS %s on %s" % (fs_name,self._name),{'to_trace': '1' ,'style': 'TRACE'}  )
				continue
			
			count = 10
			wwid = self._tps_fs[fs_name]['wwid'].lower()
			while count > 0 :
				current_multipaths = self._ssh_session.executeCli('tps multipath show')
				message ( "Current multipaths =  %s on %s" % (current_multipaths,self._name),{'to_trace': '1' ,'style': 'TRACE'}  )
				#output += current_multipaths 
				if wwid in current_multipaths:
					full_output =  self._ssh_session.executeCli('tps fs format wwid %s %s label %s' % (wwid,format_option,fs_name),wait=30)
					output += full_output.splitlines()[-1]
					break
				elif wwid not in current_multipaths:
					count = count - 1
					output += self._ssh_session.executeCli('tps multipath show')
					message ( "waiting for %s lun with wwid=%s to come in multipath. retrying in 1 sec" % (fs_name,wwid),
							 {'style': 'INFO'} )
					time.sleep(1)
					continue
		return output
	
	def getName():
			return self._name

	def getIP():
			return self._ip

	def getDiskimage():
			return self._diskimageFull

	def getMgmtNic():
			return self._mgmtNic

	def getStorNic():
			return self._storNic

	def gen_dsakey(self):
		output = ''
		for creds in self._enabledusers:
			user,password = creds.split(":")
			if user == "root":
				continue
			output += self._ssh_session.executeCli('ssh client user %s identity dsa2 generate' % user)
			response = self._ssh_session.executeCli('_exec mdreq -v query get - /ssh/client/username/%s/keytype/dsa2/public' %user)
			output += response
			try:
				m1 = self.re_ssh_pubkey.search(response.strip())
				if m1:
					self._dsakey = m1.group("pubkey")
					tuples = user + ":" + self._dsakey
					self.pub_keys.append(tuples)
			except Exception:
				errorMsg = "Error:  Cannot obtain ssh public keys from host"
				message ( "Failure in gen_dsakey  %s " % errorMsg,{'to_trace': '1' ,'style': 'TRACE'}  )
				return False
		return output

	def get_iscsiSessions(self):
		output = ''
		output += self._ssh_session.executeCli('_exec iscsiadm -m session')
		if output.find("iscsiadm: No active sessions.") != -1:
			return False
		session_regex = re.compile(ur'^tcp:\s+\[\d+\]\s+(?P<session>.*?),.*$', re.MULTILINE)
		try :
			return re.findall(session_regex, output)
		except Exception:
			return False

	def get_iscsiNodes(self):
		output = ''
		output += self._ssh_session.executeCli('_exec iscsiadm -m node')
		if output.find("iscsiadm: No records found") != -1:
			return False
		node_regex = re.compile(ur'^(?P<node>.*?),.*$', re.MULTILINE)
		try :
			return re.findall(node_regex, output)
		except Exception:
			return False

	def get_psef(self):
		output = ''
		if os.environ['RPM_MODE'] :
			output += self._ssh_session.executeShell('ps -eo etime,args')
		else:
			output += self._ssh_session.executeCli("cli session terminal width 999")
			output += self._ssh_session.executeCli('_exec /bin/ps -eo etime,args')
		return output

	def hostid_generator(self):
		return ''.join([random.choice('0123456789abcdef') for x in range(12)])

	def hdfs_report(self):
		output = ''
		checkScript = os.environ["ROBOT_PATH"] + "/" + "extras/yarn-config-check.sh"
		#try :
		self._ssh_session.transferFile(checkScript,"/tmp")
		#except Exception:
		#	message ("Cannot copy file yarn-config-check.sh in /tmp/ of %s" % self._name ,{'style':'NOK'})
		#	return False
		try:
			if os.environ['RPM_MODE'] :
				output += self._ssh_session.executeShellasUser('reflex','/tmp/yarn-config-check.sh',wait=5,timeout=30)
			else :
				output += self._ssh_session.executeCli('_exec /tmp/yarn-config-check.sh')
			return output
		except Exception:
			message ("Cannot execute file yarn-config-check.sh from /tmp/ of %s" % self._name ,{'style':'NOK'})

	def has_storage(self):
		return self._initiatorname_iscsi

	def is_clusternode(self):
		if self._clusterVIP is not None:
			return True
		else:
			return False

	def is_namenode(self):
		if self._namenode:
			return self._namenode
		else:
			return False

	def is_clustermaster(self):
		output = ''
		if os.environ['RPM_MODE'] :
			output += self._ssh_session.executeShell('su - reflex -c \"mdreq -v query get - /cluster/state/local/master\"')
		else:
			output += self._ssh_session.executeCli('_exec mdreq -v query get - /cluster/state/local/master')
		if output.find("true") != -1:
			return True
		else:
			return False

	def image_fetch(self):
		output = ''
		output += self._ssh_session.executeCli('image fetch %s' % self._upgrade_img)
		return output
	
	def image_install(self):
		output		 = ''
		image_name	 = self._upgrade_img.split("/")[-1]
		output		+= self._ssh_session.executeCli('image install %s' % image_name )
		#TODO check error
		output		+= self._ssh_session.executeCli('image boot next')
		return output

	def install_license(self):
		output = ''
		output += self._ssh_session.executeCli('license install LK2-RESTRICTED_CMDS-88A4-FNLG-XCAU-U')
		return output

	def is_ResManUp(self):
		response = self.get_psef()
		try:
			m1 = re.search(ur'^(?P<javaProcess>.*?\/bin\/java\s+-Dproc_resourcemanager.*?)$',response,re.MULTILINE)
			if m1:
				javaProcess = m1.group("javaProcess")
				return javaProcess
			else:
				return False
		except Exception:
			message ( "Error matching javaProcess" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

	def info_yarn_Setup(self):
		if os.environ['RPM_MODE'] :
			return self._ssh_session.executeShellasUser('reflex','/opt/hadoop/bin/hdfs dfsadmin -report')
		else :
			return self._ssh_session.executeCli('_exec /opt/hadoop/bin/hdfs dfsadmin -report')

	def logout_iscsiNode(self,ip_port):
		output = ''
		if not ip_port :
			return False
		try :
			output += self._ssh_session.executeCli('_exec iscsiadm -m node -p %s -u' % ip_port )
			if output.find("successful") != -1:
				message ("Successfully logged out of node %s" % ip_port,{'style':'OK'})
				return True
			else :
				message ("Error logging out of iscsi node %s " % ip_port,{'style':'NOK'})
				return False
		except Exception:
			message ("Unable to logout of session node %s => %s " % (ip_port,output),{'style':'NOK'})
			return False

	def mount_storage(self):
		output = ''
		for fs_name in self._tps_fs.keys():
			wwid = self._tps_fs[fs_name]['wwid'].lower()
			mount_point = self._tps_fs[fs_name]['mount-point']
			output +=  self._ssh_session.executeCli('no tps fs %s enable' %(fs_name))
			output +=  self._ssh_session.executeCli('no tps fs %s ' %(fs_name))
			output +=  self._ssh_session.executeCli('tps fs %s wwid %s' %(fs_name,wwid))
			output +=  self._ssh_session.executeCli('tps fs %s mount-point %s' %(fs_name,mount_point))
			output +=  self._ssh_session.executeCli('tps fs %s enable' %(fs_name))
		return output
	
	def pingable(self,host):  
		try:
			if (os.name == "posix"):
				cmd = "ping -c 1 %s"%host
			else:
				cmd = "ping %s"%host
			if  commands.getstatusoutput(cmd)[0] == 0:
				return True
			return False
		except Exception:
			message ( "Canot Ping host %s" % host , {'style': 'FATAL'} )
			return False

	def power_on(self):
		output = ''
		output += self._host_ssh_session.executeCli('virt vm %s power on' % self._name )
		return output

	def power_off(self):
		output = ''
		output += self._host_ssh_session.executeCli('virt vm %s power off force' % self._name )
		return output

	def randomMAC(self):
		mac = [ 0x52, 0x54, 0x00,
		random.randint(0x00, 0x7f),
		random.randint(0x00, 0xff),
		random.randint(0x00, 0xff) ]
		return ':'.join(map(lambda x: "%02x".upper() % x, mac))

	def removeAuthKeys(self):
		output = ''
		for creds in self._enabledusers:
			user,password = creds.split(":")
			if user == "root":
				continue
			output += self._ssh_session.executeCli('_exec mdreq set delete - /ssh/server/username/%s/auth-key/sshv2/ '%user)
		return output

	def remove_storage(self):
		output = ''
		for fs_name in self._tps_fs.keys():
			output +=  self._ssh_session.executeCli('no tps fs %s enable' %(fs_name))
		time.sleep(10)
		for fs_name in self._tps_fs.keys():
			output +=  self._ssh_session.executeCli('no tps fs %s' %(fs_name))
		return output

	def reload(self):
		output = ''
		output += self._ssh_session.executeCli('config write')
		output += self._ssh_session.executeCli('reload')
		return output

	def remove_iscsiForbidden(self):
		output = ''
		nodes = []
		sessions = []
		
		if not self._forbidden_nodes :
			return False
		
		nodes = self.get_iscsiNodes()
		sessions = self.get_iscsiSessions()
		for node in self._forbidden_nodes:
			node += ":"  # avoids deletion of 192.168.181.111 when asked for 192.168.181.11 deletion 
			if sessions:
				for ip_port in sessions :
					if ip_port.find(node) != -1:
						self.logout_iscsiNode(ip_port)
			if nodes:
				for ip_port in nodes :
					if ip_port.find(node) != -1:
						self.delete_iscsiNode(ip_port)
						break
					else:
						continue
					message ("iScsi node %s not present in the system " % ip_port,{'style':'OK'})
			else :
				message ("No nodes present currently in system %s" % ip_port,{'style':'OK'})
				
		return "Success"	

	def registerNameNode(self):
		self.name_nodes.append(self._name)
		message ( "registerNameNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )

	def registerDataNode(self):
		self.data_nodes.append(self._name)
		message ( "registerDataNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
	
	def registerJournalNode(self):
		self.journal_nodes.append(self._name)
		message ( "registerJournalNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )

	def rotate_logs(self):
		output = ''
		output += self._ssh_session.executeCli('logging files rotation force')
		return output

	def setSnmpServer(self):
		output = ''
		output += self._ssh_session.executeCli('snmp-server host %s traps version 2c' %self._snmpsink)
		return output

	def setHostName(self):
		output = ''
		output += self._ssh_session.executeCli('hostname %s' % self._name )
		output += self._ssh_session.executeCli('config write')
		return output

	def set_snmpsink(self):
		output = ''
		output += self._ssh_session.executeCli('snmp-server host %s traps version 2c '%self._snmpsink)
		return output
	
	def setIpHostMaps(self):
		output = ''
		for vm in self.nodes_ip.keys():
			output += self._ssh_session.executeCli('ip host %s %s '%(vm,self.nodes_ip[vm]))
		return output
	
	def setclustering(self):
		output = ''
		if not self.is_clusternode():
			message ( "Improper calling of setclustering in %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			return False # TODO Raise exception
		if not self._cluster_name:
			self._cluster_name = self._set_clusterName() 
		output += self._ssh_session.executeCli('cluster id %s'%self._cluster_name)
		output += self._ssh_session.executeCli('cluster master address vip %s /%s'%(self._clusterVIP,self._mask))
		output += self._ssh_session.executeCli('cluster name %s'%self._cluster_name)
		output += self._ssh_session.executeCli('cluster enable')
		return output

	def setStorNw(self):
		output = ''
		if self._stor_ip is not None:
			output += self._ssh_session.executeCli('no interface %s ip address' %self._storNic)
			output += self._ssh_session.executeCli('interface %s ip address %s /%s' %(self._storNic, self._stor_ip, self._stor_mask))
		return output
	
	def setup_HDFS(self):
		HA =''
		journal_nodes = ''
		output = ''
		client_ip = None 
		cmd = "no register hadoop_yarn\n"
		cmd += "register hadoop_yarn\n"
		
		if self.is_clusternode():
			HA = 'True'
			client_ip = self._clusterVIP
		else:
			HA = 'False'
			client_ip = self.nodes_ip[self.name_nodes[0]]
			
		cmd += "set hadoop_yarn config_ha %s \n" % HA
		cmd += "set hadoop_yarn namenode1 %s \n" % self.name_nodes[0]
		
		if self.is_clusternode():
			cmd += "set hadoop_yarn namenode2 %s \n" % self.name_nodes[1]
			cmd += "set hadoop_yarn nameservice %s \n" % self.config_ref['HOSTS']['yarn_nameservice']
			for node in self.journal_nodes:
				cmd += "set hadoop_yarn journalnodes %s \n" % node
			for node in self.name_nodes:
				cmd += "set hadoop_yarn journalnodes %s \n" % node

		for node in self.journal_nodes:
			cmd += "set hadoop_yarn slave %s \n" % self.nodes_ip[node]
		for node in self.data_nodes:
			cmd += "set hadoop_yarn slave %s \n" % self.nodes_ip[node]

		cmd += "set hadoop_yarn client %s \n" % client_ip
		cmd += "set hadoop_yarn state UNINIT \n"
		
		if os.environ['BACKUP_HDFS'] :
			cmd += "register backup_hdfs \n"
			cmd += "set backup_hdfs namenode UNINIT \n"
			cmd += "set backup_hdfs version HADOOP_YARN \n"
			
		output += self._ssh_session.executePmx(cmd)
		output += self._ssh_session.executeCli('pm process tps restart')
		message ( " tps restarted in node %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		return output

	def set_clusterMaster(self):
		output = ''
		if not self.is_clusternode():
			message ( "Improper calling of set_clusterMaster in %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			return False # raise exception
		output =  session.executeCli('cluster master self')
		return output
	
	def set_centos_db(self):
		output = ''
		cfg_mgmtNic = '''DEVICE=%s
TYPE=Ethernet
HWADDR=%s
BOOTPROTO=static
IPADDR=%s
PREFIX=%s
GATEWAY=%s
DNS1=%s
DEFROUTE=yes
NAME=%s
ONBOOT=yes
IPV6INIT=no
''' % ( self._mgmtNic, self._mgmtMac, self._ip, self._mask, self._gw, self._name_server, self._mgmtNic )

		cfg_storNic = '''DEVICE=%s
TYPE=Ethernet
BOOTPROTO=none
IPADDR=%s
PREFIX=%s
DEFROUTE=yes
NAME=%s
ONBOOT=yes
IPV6INIT=no
''' % (self._storNic , self._stor_ip, self._stor_mask, self._storNic  )
		cfg_hostname = '''NETWORKING=yes
HOSTNAME=%s
''' % ( self._name)
		var_offset = None
		re_varoffset = re.compile( r"^\S+\.img1\s+\S\s+(?P<varOffset>\d+)\s+\S+\s+\S+\s+\S+\s+Linux",re.M)
		#output += self._host_ssh_session.executeCli('_exec tar -xf %s' % self._diskimageFull )
		layout_template = self._host_ssh_session.executeCli('_exec fdisk -lu %s' % self._diskimageFull )
		
		try:
			match = re_varoffset.search(layout_template)
			if match:
				var_offset = match.group("varOffset")
				message ( "offset in ROOT_FS is computed = %s " % var_offset,{'to_trace': '1' ,'style': 'TRACE'}  )
			else:
				message ( "Cannot find Offset for ROOTFS ",{'to_trace': '1' ,'style': 'TRACE'}  )
				return False
		except Exception:
			message ( "error matching Offset in %s" % self._diskimageFull			, {'style': 'INFO'} )
			return False
		
		offset_bytes = int(var_offset) * 512
		next_loop_available = self._host_ssh_session.executeCli('_exec /sbin/losetup -f')
		loop_dev = self._get_loop_device()
		output +=  self._host_ssh_session.executeCli('_exec /sbin/losetup %s %s -o %s ' % ( loop_dev , self._diskimageFull , offset_bytes )) 
		output +=  self._host_ssh_session.executeCli('_exec umount /mnt/cdrom/' )
		output +=  self._host_ssh_session.executeCli('_exec mount %s /mnt/cdrom/' % loop_dev )
		#TODO make a config.dir backp
		output +=  self._host_ssh_session.executeShell('echo \"%s\" > /mnt/cdrom/etc/sysconfig/network-scripts/ifcfg-%s' %(cfg_mgmtNic, self._mgmtNic))
		output +=  self._host_ssh_session.executeShell('echo \"%s\" > /mnt/cdrom/etc/sysconfig/network-scripts/ifcfg-%s' %(cfg_storNic, self._storNic))
		output +=  self._host_ssh_session.executeShell('echo \"%s\" > /mnt/cdrom/etc/sysconfig/network' %(cfg_hostname))
		output +=  self._host_ssh_session.executeCli('_exec /bin/rm -f /mnt/cdrom/etc/udev/rules.d/70-persistent-net.rules' )
		output +=  self._host_ssh_session.executeCli('_exec /bin/rm -f /mnt/cdrom/lib/udev/rules.d/75-persistent-net-generator.rules' )
		output +=  self._host_ssh_session.executeCli('_exec umount /mnt/cdrom')
		output +=  self._host_ssh_session.executeCli('_exec losetup -d %s' % loop_dev)
		return output
	
	def set_user(self,user,password):
		output = ''
		output += self._ssh_session.executeCli('no user %s disable'%user)
		output += self._ssh_session.executeCli('user %s password %s' %(user, password))
		return output

	def set_mfgdb(self):
		output = ''
		var_offset = None
		re_varoffset = re.compile( r"^\S+\.img8\s+(?P<varOffset>\d+)\s+\S+\s+\S+\s+\S+\s+Linux",re.M)
		layout_template = self._host_ssh_session.executeCli('_exec fdisk -lu %s' % self._diskimageFull )
		
		try:
			match = re_varoffset.search(layout_template)
			if match:
				var_offset = match.group("varOffset")
				message ( "varoffset in set_mfgdb is computed = %s " % var_offset,{'to_trace': '1' ,'style': 'TRACE'}  )
			else:
				message ( "Cannot find VarOffset in  set_mfgdb ",{'to_trace': '1' ,'style': 'TRACE'}  )
				return False
		except Exception:
			message ( "error matching varOffset in %s" % self._diskimageFull					, {'style': 'INFO'} )
			return False
		
		offset_bytes = int(var_offset) * 512
		next_loop_available = self._host_ssh_session.executeCli('_exec /sbin/losetup -f')
		loop_dev = self._get_loop_device()
		output +=  self._host_ssh_session.executeCli('_exec /sbin/losetup %s %s -o %s ' % ( loop_dev , self._diskimageFull , offset_bytes ))
		output +=  self._host_ssh_session.executeCli('_exec umount /mnt/cdrom/')
		output +=  self._host_ssh_session.executeCli('_exec mount %s /mnt/cdrom/' % loop_dev )
		#TODO make a config.dir backp
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/system/hostid string %s" % self._hostid )
		
		#/opt/tms/bin/mddbreq  -l /config/mfg/mfdb query  get - /mfg/mfdb/system/hostid 
		#/opt/tms/bin/mddbreq  -l /config/mfg/mfdb query  get - /mfg/mfdb/net/interface/config/eth0/addr/ipv4/static/1/ip ipv4addr
		#/opt/tms/bin/mddbreq  -l /config/mfg/mfdb query  get -  /mfg/mfdb/net/interface/config/eth0/addr/ipv4/dhcp
		#/opt/tms/bin/mddbreq  -l /config/mfg/mfdb query  get - /mfg/mfdb/net/routes/config/ipv4/prefix/0.0.0.0\\\/0/nh/1/gw
		
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/net/interface/config/%s/addr/ipv4/static/1/ip ipv4addr %s" % (self._mgmtNic ,self._ip))
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/net/interface/config/%s/addr/ipv4/static/1/mask_len uint8 %s" % (self._mgmtNic ,self._mask))
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/net/interface/config/%s/addr/ipv4/dhcp bool false" % (self._mgmtNic))
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" \"/mfg/mfdb/net/routes/config/ipv4/prefix/0.0.0.0\\/0/nh/1/gw\" ipv4addr %s" % (self._gw))
		
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/interface/map/macifname/1 uint32 1" )
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/interface/map/macifname/1/name string %s" % self._mgmtNic )
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/interface/map/macifname/1/macaddr macaddr802 %s" % self._mgmtMac)
		
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/interface/map/macifname/2 uint32 2" )
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/interface/map/macifname/2/name string %s" % self._storNic )
		output +=  self._host_ssh_session.executeCli("_exec /opt/tms/bin/mddbreq -c /mnt/cdrom/mfg/mfdb set modify \"\" /mfg/mfdb/interface/map/macifname/2/macaddr macaddr802 %s" % self._storMac )

		output +=  self._host_ssh_session.executeCli('_exec umount /mnt/cdrom')
		output +=  self._host_ssh_session.executeCli('_exec losetup -d %s' % loop_dev)
		return output
	
	def ssh_self(self):
		vm_up = False
		if not self._ssh_session:           
			timeOut = 600
			while timeOut > 0:
				if self.pingable(self._ip):
					message ( "VM %s responds from %s " % (self._name,self._ip),				{'style': 'DEBUG'})
					vm_up = True
					break
				else:
					message ( "Waiting for VM %s %s to come up, sleeping for 5 seconds" % (self._name,self._ip),{'style': 'DEBUG'})
					time.sleep(5)
					timeOut = timeOut - 5       
			if vm_up :
				#Find out admin user pass ( if not in config set default)
				#username = 'admin'
				#password = 'admin@123'
				for cred in self._enabledusers:
					user,passwd = cred.split(":")
					if os.environ['RPM_MODE'] :
						if user.find('root') != -1:
							username	= user
							password	= passwd
					else :
						if user.find('admin') != -1:
							username	= user
							password	= passwd
				self._ssh_session = session(self._ip, username , password)
				if not os.environ['RPM_MODE'] :
					self.disable_paging()
					self.disable_timeout()
				return self._ssh_session
			else :
				message ( "Exception that SSH connection can;t be made to the VM"  ,			{'style': 'FATAL'})
				return False
		elif  self._ssh_session :
			return self._ssh_session
		else:
			return False

	def unregisterNameNode(self):
		self.name_nodes.remove(self._name)
		self._namenode = None
		self.config_ref['HOSTS'][self._host][self._name]['name_node'] = None
		message ( "unregisterNameNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
	
	def unregisterJournalNode(self):
		self.journal_nodes.remove(self._name)
		self._journalnode = None
		self.config_ref['HOSTS'][self._host][self._name]['journal_node'] = None
		message ( "unregisterJournalNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )

	def unregisterDataNode(self):
		self.data_nodes.remove(self._name)
		message ( "unregisterDataNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		
	def unregisterCluster(self):
		self._clusterVIP = None
		self.config_ref['HOSTS'][self._host][self._name]['cluster_vip'] = None
		message ( "unregisterCluster %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )

	def validate_HDFS(self):
		if self.is_clusternode() and not self.is_clustermaster():
			return "Part of Cluster but not master. skipping node %s" % self._name
		output = ''
		report = ''
		retry = 0
		validate_status = False
		while retry <= 15:
			try:
				res_man = self.is_ResManUp()
				if res_man :
					message ("Resource Manager is up in %s" % self._name, {'style':'ok'} )
					res_manStart = get_startProcess(res_man)
					message ("Resource Manager is running since %s seconds" % res_manStart, {'style':'info'})
					if ( res_manStart < 300):
						time2wait = 300 - res_manStart
						message ("Waiting for %s seconds before running hdfs report" % time2wait, {'style':'info'})
						time.sleep(time2wait)
					output += self.info_yarn_Setup()
					validate_status = True
					break
				else:
					retry += 1
					message ("Attempt %s. Resource Manager is not running. Waiting total 15 min" % retry, {'style':'WARNING'})
					time.sleep(60)
			except Exception:
				message ("Not able to validate HDFS %s." % output, {'style':'FATAL'})
				return False
		
		message ("Now HDFS config report", {'style':'INFO'})
		report += str(self.hdfs_report())
		if report.find('ERROR') != -1 :
			message ("HDFS Report = %s" % report ,{'style':'NOK'} )
		else :
			message ("HDFS Report = %s" % report ,{'style':'OK'} )
		output += report 
		return output

if __name__ == '__main__':
    pass
    vm = vm_node(config,"FIVE","five-one")
