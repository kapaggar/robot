#!/usr/bin/env python
import re
from session import session
from vm_node import vm_node
from Toolkit import message
from urlgrabber import urlopen,grabber
from os.path import basename

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

	def getname(self):
		return self._name

	def getip(self):
		return self._ip

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
		cmd  = "pkill  /usr/libexec/qemu-kvm \n"
		cmd += "rm -rf /data/virt/pools/default/*.iso \n"
		cmd += "rm -rf /data/virt/pools/default/*.img \n"
		output +=  self._ssh_session.executeShell(cmd)
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
		output +=  self._ssh_session.executeCli('_exec ls -l %s' % self._template_file)
		if "No such file or directory" in output:
			return False
		else :
			return True
		
	def get_iso_path(self):
		if self._iso_path == "nightly" :
			nightly_base_dir = self.config['HOSTS']['nightly_dir']
			full_iso_path = self.get_nightly (nightly_base_dir)
			return full_iso_path
		elif self._iso_path is not None:
			return self._iso_path

	def get_nightly(self,base_path):
		re_mfgiso = re.compile( r"(?P<mfgiso>mfgcd-\S+?.iso)",re.M)
		try:
			page = urlopen(base_path)
		except grabber.URLGrabError as e:
			raise IOError
			sys.exit(1)
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
		return "Success"
	
	def instantiateVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			message ( "Clone-Volume_Output = %s " % vm.clone_volume()	, {'style': 'INFO'} )
			message ( "VM-Configure_Output = %s " % vm.configure()		, {'style': 'INFO'} )
			message ( "VM-SetMfgDB_Output = %s " % vm.set_mfgdb()		, {'style': 'INFO'} )

	
	def startVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			message ( "VM-Poweron= %s " % vm.poweron()					, {'style': 'INFO'} )

	def upgradeVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			if vm.ssh_self():
				message ( "VM-Fetch		= %s " % vm.image_fetch()		, {'style': 'INFO'} )
				message ( "VM-Install	= %s " % vm.image_install()		, {'style': 'INFO'} )
				message ( "VM-Reload	= %s " % vm.reload()			, {'style': 'INFO'} )

if __name__ == '__main__':
	pass