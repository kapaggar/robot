#!/usr/bin/env python
import re
from session import session
from vm_node import vm_node
from Toolkit import message,terminate_self,get_nightly
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
		self._centos_template	= self.config['HOSTS']['centos_template_path']
		self._template_file		= self.config['HOSTS'][self._name ]['template_file']
		self._ip				= self.config['HOSTS'][self._name ]['ip']
		self._username			= self.config['HOSTS'][self._name ]['username']
		self._password			= self.config['HOSTS'][self._name ]['password']
		self._brMgmt			= self.config['HOSTS'][self._name ]['brMgmt']
		self._brStor			= self.config['HOSTS'][self._name ]['brStor']
		self._vms				= self.get_vms()
		message ( "Host init object %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )


	def __del__(self):
		if self._ssh_session != None:
			message ( "Host del object  %s " % self._name,{'to_trace': '1' ,'style': 'TRACE'}  )
			self._ssh_session.close()

	def connectSSH(self):
		self._ssh_session = session(self._ip, self._username, self._password)
		self.config['HOSTS'][self._name]['ssh_session'] = self._ssh_session
		return self._ssh_session
	
	def create_template(self):
		output = ''
		template_name = basename(self._template_file)
		iso_path = self.get_iso_path()
		message ( "Making template from iso_path = %s " % iso_path,{'to_trace': '1' ,'style': 'INFO'}  )
		iso_name = basename(iso_path)
		try:
			output +=  self._ssh_session.executeCli('_exec qemu-img create %s 100G' % self._template_file)
			output +=  self._ssh_session.executeCli('virt vm template storage device drive-number 1 source file %s mode read-write' % template_name)
			output +=  self._ssh_session.executeCli('virt vm template vcpus count 4')
			output +=  self._ssh_session.executeCli('virt vm template memory 16384')
			message ( "Starting vm-node with iso = %s " % iso_name,{ 'style': 'OK'}  )
			output +=  self._ssh_session.run_till_prompt('virt vm template install cdrom file %s disk-overwrite connect-console text timeout 60' % iso_name , "(none) login:",wait=30)
			output +=  self._ssh_session.run_till_prompt('root', "#",wait=1)
			output +=  self._ssh_session.run_till_prompt('PS1="my_PROMPT"', "my_PROMPT",wait=1)
			message ( "Invoking manufacture.sh inside vm-node as '/sbin/manufacture.sh -i -v -f /mnt/cdrom/image.img -a -m 1D -d /dev/vda'" ,{ 'style': 'OK'}  )
			output +=  self._ssh_session.run_till_prompt("sed -i 's/^TMPFS_SIZE_MB=[0-9]*/TMPFS_SIZE_MB=8192/g' /etc/customer_rootflop.sh ","my_PROMPT",wait=1)
			output +=  self._ssh_session.run_till_prompt('/sbin/manufacture.sh -i -v -f /mnt/cdrom/image.img -a -m 1D -d /dev/vda',"my_PROMPT",wait=60)
			output +=  self._ssh_session.run_till_prompt('reboot')
		except Exception:
			message ( "Template creation failed  %s " % self._name,{'style': 'FATAL'}  )
			output = output + " Failed "
		return output

	def deleteVMs(self):
		output = ''
		try:
			for vm_name in self._vms:
				output +=  self._ssh_session.executeCli('no virt vm %s' % vm_name )
			output = str ( output ) + " Success"
		except Exception:
			message ( "Cannot delete vms  %s " % output,{'to_trace': '1' ,'style': 'FATAL'}  )
			output = output + " Failed"
		return output
	
	def declareVMs(self):
		for vm_name in self._vms:
			vm = vm_node(self.config,self._name,vm_name)
			self.config['HOSTS'][self._name][vm_name]['vm_ref'] = vm
		return "Success"

	def delete_template(self):
		output = ''
		response = self._ssh_session.executeCli('virt vm template install cancel')
		output += response
		if response.find("No installation in progress on VM") != -1 :
			message ("Similar installation was already Running on host %s."% self.getname(), {'style':'WARNING'})
			output += self._ssh_session.executeCli('no virt vm template ')
			message ("Older installation stopped on host %s."% self.getname(), {'style':'OK'})
			output = str(output) + " Success"
		else :
			message ("No Template installation in progess", {'style':'OK'})
			output = str(output) + " Success"
		return output

	def enableVirt(self):
		output = ''
		output += self._ssh_session.executeCli('virt enable',wait=5)
		return output

	def getname(self):
		return self._name

	def getip(self):
		return self._ip
	
	def get_iso_path(self):
		if self._iso_path == "nightly" :
			nightly_base_dir = self.config['HOSTS']['nightly_dir']
			full_iso_path = get_nightly (nightly_base_dir)
			return full_iso_path
		elif self._iso_path is not None:
			return self._iso_path

	def get_template_path(self):
		centos_template_path = self.config['HOSTS']['centos_template_path']
		return centos_template_path

	def get_centos_template(self):
		output = ''
		response = ''
		centos_template_path = self.get_template_path()
		message ("CentOS template to fetch = %s" % centos_template_path,{'style':'INFO'})
		try :
			response =  self._ssh_session.executeCli('virt volume fetch url %s' % centos_template_path,wait=2 )
			output += self._ssh_session.executeCli('_exec tar -C /data/virt/pools/default/ -xf /data/virt/pools/default/%s' %( self._centos_template.split("/")[-1] ) )
			if "failed" in response:
				message ("Cannot fetch url %s on host %s"% (centos_template_path,self.getname()),{'style':'NOK'})
				message ("Reason %s" % response,{'style':'DEBUG'})
				terminate_self("Exiting.")
			else :
				output += response[-80:] + "Success"
		except Exception :
			message ("Unable to fetch url %s in host %s"% (centos_template_path,self.getname()),{'style':'NOK'})
			terminate_self("Exiting.") 
		return output
	
	def getMfgCd(self):
		output = ''
		response = ''
		iso_path = self.get_iso_path()
		message ("iso to fetch = %s" % iso_path,{'style':'INFO'})
		try :
			response =  self._ssh_session.executeCli('virt volume fetch url %s' % iso_path,wait=2 )
			if "failed" in response:
				message ("Unable to fetch url %s on host %s"% (iso_path,self.getname()),{'style':'NOK'})
				message ("Reason %s" % response,{'style':'DEBUG'})
				terminate_self("Exiting.")
			else :
				output += response[-80:] + "Success"
		except Exception :
			message ("Unable to fetch url %s in host %s"% (iso_path,self.getname()),{'style':'NOK'})
			terminate_self("Exiting.") 
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

	def is_template_present(self):
		output = ''
		output +=  self._ssh_session.executeCli('_exec ls -l %s' % self._template_file)
		if output.find("No such file or directory") != -1:
			return False
		else :
			return True

	def is_centos_template_present(self):
		output = ''
		output +=  self._ssh_session.executeCli('_exec ls -l /data/virt/pools/default/%s' % (self._centos_template.split("/")[-1] ))
		if output.find("No such file or directory") != -1:
			return False
		else :
			return True
		
	def instantiateVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			message ( "Clone-Volume_Output	= [%s]" % vm.clone_volume()		, {'style': 'INFO'} )
			message ( "VM-Configure_Output	= [%s]" % vm.configure()		, {'style': 'INFO'} )
			message ( "VM-SetMfgDB_Output	= [%s]" % vm.set_mfgdb()		, {'style': 'INFO'} )
		return "Success"

	def instantiate_centos_VMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			message ( "Clone-Volume_Output	= [%s]" % vm.clone_volume()		, {'style': 'INFO'} )
			message ( "VM-Configure_Output	= [%s]" % vm.configure()		, {'style': 'INFO'} )
			message ( "VM-SetMfgDB_Output	= [%s]" % vm.set_centos_db()	, {'style': 'INFO'} )
		return "Success"
			
	def synctime(self):
		output = ''
		output += self._ssh_session.executeCli('ntpdate  %s' %self._ntp_server )
		output += self._ssh_session.executeCli('ntp server %s' % self._ntp_server )
		output += self._ssh_session.executeCli('ntp enable ')
		if output.find("adjust") != -1 :
			output += " Success"
		else:
			output += " Fail"
		return output

	def setDNS(self):
		output = ''
		try:
			output += self._ssh_session.executeCli('ip name-server %s '%self._name_server)
			output = output + " Success"
		except Exception:
			message ( "Cannot set dns server on %s " % self._host,{ 'style': 'WARNING'}  )
		return output
	
	def startVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			message ( "VM-Poweron = [%s]" % vm.power_on()					, {'style': 'INFO'} )

	def upgradeVMs(self):
		for vm_name in self._vms:
			vm = self.config['HOSTS'][self._name][vm_name]['vm_ref']
			if vm.ssh_self():
				message ( "VM-Fetch		= [%s]" % vm.image_fetch()		, {'style': 'INFO'} )
				message ( "VM-Install	= [%s]" % vm.image_install()	, {'style': 'INFO'} )
				message ( "VM-Reload	= [%s]" % vm.reload()			, {'style': 'INFO'} )
	
	def wipe_setup(self):
		output = ''
		cmd  = "pkill -9 qemu-kvm \n"
		cmd += "rm -rf /data/virt/pools/default/*.iso \n"
		cmd += "rm -rf /data/virt/pools/default/*.img \n"
		cmd += "rm -rf /data/virt/pools/default/*.tgz \n"
		output +=  self._ssh_session.executeShell(cmd)
		if output.find("cannot") != -1:
			return output + "Fail"
		else:
			return output + "Success"

if __name__ == '__main__':
    pass
    host = Host(config,"FIVE")
