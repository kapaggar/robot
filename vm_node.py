#!/usr/bin/env python 
import paramiko
import string, re
import time
import traceback
import commands
import os,sys
import random
from session import session
from Toolkit import message,terminate_self

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
		self._host_ssh_session		= config['HOSTS'][host]['ssh_session']
		self._brMgmt				= config['HOSTS'][host]['brMgmt']
		self._brStor				= config['HOSTS'][host]['brStor']
		self._template				= config['HOSTS'][host]['template_file']
		self._enabledusers			= config['HOSTS'][host][vm]['enabled_users']
		self._clusterVIP			= config['HOSTS'][host][vm]['cluster_vip']
		self._namenode				= config['HOSTS'][host][vm]['name_node']
		self._journalnode			= config['HOSTS'][host][vm]['journal_node']
		self._initiatorname_iscsi	= config['HOSTS'][host][vm]['storage']['initiatorname_iscsi']
		self._iscsi_target			= config['HOSTS'][host][vm]['storage']['iscsi_target']
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

	def registerNameNode(self):
		self.name_nodes.append(self._name)
		message ( "registerNameNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )

	def unregisterNameNode(self):
		self.name_nodes.remove(self._name)
		self._namenode = None
		self.config_ref['HOSTS'][self._host][self._name]['name_node'] = None
		message ( "unregisterNameNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
	
	def registerJournalNode(self):
		self.journal_nodes.append(self._name)
		message ( "registerJournalNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
	
	def unregisterJournalNode(self):
		self.journal_nodes.remove(self._name)
		self._journalnode = None
		self.config_ref['HOSTS'][self._host][self._name]['journal_node'] = None
		message ( "unregisterJournalNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		
	def registerDataNode(self):
		self.data_nodes.append(self._name)
		message ( "registerDataNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )

	def unregisterDataNode(self):
		self.data_nodes.remove(self._name)
		message ( "unregisterDataNode %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		
	def unregisterCluster(self):
		self._clusterVIP = None
		self.config_ref['HOSTS'][self._host][self._name]['cluster_vip'] = None
		message ( "unregisterCluster %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
	
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

	def randomMAC(self):
		mac = [ 0x52, 0x54, 0x00,
		random.randint(0x00, 0x7f),
		random.randint(0x00, 0xff),
		random.randint(0x00, 0xff) ]
		return ':'.join(map(lambda x: "%02x".upper() % x, mac))

	def hostid_generator(self):
		return ''.join([random.choice('0123456789abcdef') for x in range(12)])

	def clone_volume(self):
		output =  self._host_ssh_session.executeCli("_exec /bin/cp -f --sparse=always %s %s" % (self._template,self._diskimageFull))
		message ( "cloned volume for %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		return output
	
	def delete_volume(self):
		output =  self._host_ssh_session.executeCli("no virt volume file %s" % self._diskimage)
		message ( "deleted volume for %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
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
		output +=  self._host_ssh_session.executeCli('_exec /sbin/losetup %s %s -o %s ' % ( loop_dev , self._diskimageFull , offset_bytes )) #TODO fix this for variable size Disk instead of  $((59510305 * 512)) 
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

	def disable_paging(remote_conn):
		output = ''
		output += self._host_ssh_session.executeCli("no cli default paging enable")
		return output

	def power_on(self):
		output = ''
		output += self._host_ssh_session.executeCli('virt vm %s power on' % self._name )
		return output

	def power_off(self):
		output = ''
		output += self._host_ssh_session.executeCli('virt vm %s power off force' % self._name )
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

	def ssh_self(self):
		vm_up = False
		if not self._ssh_session:           
			timeOut = 600
			while timeOut > 0:
				if self.pingable(self._ip):
					message ( "VM %s responds from %s "%(self._name,self._ip),
							 {'style': 'DEBUG'}
							 )
					vm_up = True
					break
				else:
					message ( "Waiting for VM %s %s to come up, sleeping for 5 seconds"%(self._name,self._ip),
							 {'style': 'DEBUG'}
							 )
					time.sleep(5)
					timeOut = timeOut - 5       
			if vm_up :
				#Find out admin user pass ( if not in config set default)
				username = 'admin'
				password = 'admin@123'
				for cred in self._enabledusers:
					user,passwd = cred.split(":")
					if user.find('admin') != -1:
						username	= user
						password	= passwd
				self._ssh_session = session(self._ip, username , password)
				return self._ssh_session
			else :
				message ( "Exception that SSH connection can;t be made to the VM"  ,
						 {'style': 'FATAL'}
						 )
				return False
		elif  self._ssh_session :
			return self._ssh_session
		else:
			return False

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

	def set_user(self,user,password):
		output = ''
		output += self._ssh_session.executeCli('no user %s disable'%user)
		output += self._ssh_session.executeCli('user %s password %s' %(user, password))
		return output

	def configusers(self):
		for creds in self._enabledusers:
			user,password = creds.split(":")
			self.set_user(user,password)

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

	def factory_revert(self):
		output = ''
		output += self._ssh_session.executeCli('configuration revert factory',wait=10)
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
	
	def removeAuthKeys(self):
		output = ''
		for creds in self._enabledusers:
			user,password = creds.split(":")
			if user == "root":
				continue
			output += self._ssh_session.executeCli('_exec mdreq set delete - /ssh/server/username/%s/auth-key/sshv2/ '%user)
		return output
	
	def authPubKeys(self):
		output = ''
		output += self._ssh_session.executeCli('ssh client global host-key-check no')
		for creds in self.pub_keys:
			user,pubkey = creds.split(":")
			if user == "root":
				continue
			output += self._ssh_session.executeCli('ssh client user %s authorized-key sshv2 \"%s\"'%(user,pubkey))
		return output

	def rotate_logs(self):
		output = ''
		output += self._ssh_session.executeCli('logging files rotation force')
		return output
	
	def setSnmpServer(self):
		output = ''
		output += self._ssh_session.executeCli('snmp-server host %s traps version 2c' %self._snmpsink)
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
		output += self._ssh_session.executePmx(cmd)
		output += self._ssh_session.executeCli('pm process tps restart')
		message ( " tps restarted in node %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
		return output

	def is_ResManUp(self):
		response = self.get_psef()
		try:
			m1 = re.search(ur'^(?P<javaProcess>.*?\/bin\/java\s+-Dproc_resourcemanager[\s+\S+]*?)$',response,re.MULTILINE)
			if m1:
				javaProcess = m1.group("javaProcess")
				return javaProcess
			else:
				return False
		except Exception:
			message ( "Error matching javaProcess" , {'to_log':1 , 'style': 'DEBUG'} ) 
			return False

	def info_yarn_Setup(self):
		return self._ssh_session.executeCli('_exec /opt/hadoop/bin/hdfs dfsadmin -report') 
		
	def validate_HDFS(self):
		if not self.is_clustermaster():
			return "Not cluster master. skipping."
		output = ''
		retry = 0
		validate_status = False
		while retry <= 3:
			try:
				if self.is_ResManUp():
					message ("Resource Manager is up in %s" % self._name, {'style':'ok'} )
					output += self.info_yarn_Setup()
					validate_status = True
					break
				else:
					retry += 1
					message ("Try %s. Resource Manager is not running. Waiting 5 min" % retry, {'style':'WARNING'})
					time.sleep(300)
			except Exception:
				message ("Not able to validate HDFS %s." % output, {'style':'FATAL'})
				return False
		return output

	def has_storage(self):
		return self._initiatorname_iscsi
	
	def bring_storage(self):
		output = ''
		output += self._ssh_session.executeCli('tps iscsi initiator-name %s' %self._initiatorname_iscsi)
		output += self._ssh_session.executeCli('_exec service iscsid restart')
		output += self._ssh_session.executeCli('tps iscsi show targets %s' % self._iscsi_target)
		output += self._ssh_session.executeCli('tps iscsi restart')
		time.sleep(15)
		output += self._ssh_session.executeCli('tps multipath renew ')
		return output
	
	def get_psef(self):
		output = ''
		output += self._ssh_session.executeCli("cli session terminal width 999")
		output += self._ssh_session.executeCli('_exec /bin/ps -ef')
		return output


	def remove_storage(self):
		output = ''
		for fs_name in self._tps_fs.keys():
			output +=  self._ssh_session.executeCli('no tps fs %s enable' %(fs_name))
		time.sleep(10)
		for fs_name in self._tps_fs.keys():
			output +=  self._ssh_session.executeCli('no tps fs %s' %(fs_name))
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
				return
			
			count = 10
			wwid = self._tps_fs[fs_name]['wwid'].lower()
			while count > 0 :
				current_multipaths = self._ssh_session.executeCli('tps multipath show')
				message ( "Current multipaths =  %s " % (current_multipaths,self._name),{'to_trace': '1' ,'style': 'TRACE'}  )
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

	def config_write(self):
		output = ''
		output += self._ssh_session.executeCli('config write')
		return output
	
	def dottedQuadToNum(self,ip):
		hexn = ''.join(["%02X" % long(i) for i in ip.split('.')])
		return long(hexn, 16)
	
	def setHostName(self):
		output = ''
		output += self._ssh_session.executeCli('hostname %s' % self._name )
		output += self._ssh_session.executeCli('config write')
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
		
	def disable_clustering(self):
		if not self.is_clusternode():
			return False
		return session.executeCli('no cluster enable')
	
	def is_clustermaster(self):
		output = ''
		output += self._ssh_session.executeCli('_exec mdreq -v query get - /cluster/state/local/master')
		if output.find("true") != -1:
			return True
		else:
			return False

	def set_clusterMaster(self):
		output = ''
		if not self.is_clusternode():
			message ( "Improper calling of set_clusterMaster in %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			return False # raise exception
		output =  session.executeCli('cluster master self')
		return output 

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

	def reload(self):
		output = ''
		output += self._ssh_session.executeCli('config write')
		output += self._ssh_session.executeCli('reload')
		return output

	def install_license(self):
		output = ''
		output += self._ssh_session.executeCli('license install LK2-RESTRICTED_CMDS-88A4-FNLG-XCAU-U')
		return output
	


if __name__ == '__main__':
    pass
    vm = vm_node(config,"FIVE","five-one")
