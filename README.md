# Robot

Project is WIP and is subjected to change with updates in framework

For quick and smooth testing on Appliance images, current design is to make exact same h/w profiled VMs and same method of installation ( 1D ) with manual manufacturing inside console.  
Remote-storage inside VMs is also via iscsi targets.
Host machine having bridged n/w can install local as well as remote setups.
A setup can comprise of multiple VMs on one host OR single VMs on multiple hosts OR multiple VMs on multiple hosts.  
Setup defination is all at one place in INI file that is given runtime to setup-making scripts.
One box can be used to run many automation tests in parallel of different setups

##Prerequisites

This guide asssumes that the machines submitted for this automation setup are Appliance TM boxes ( preferrably same build version )

  -  A mgmt Bridge must be present,  grouping Host management NIC with VMs management NICs
  - Bridge stor should be present if storage is also to be tested. ( otherwise not required )





### Preparation

You need mgmt & stor(optional) configured on all Hosts that would be part of setup

**mgmt**
```sh
MGMT_NIC=eth0
MGMT_IP=192.168.172.NN
MGMT_MASK=24

# cli -m config <<END
bridge mgmt
interface ${MGMT_NIC} bridge-group mgmt
no interface ${MGMT_NIC}  ip address
interface ${MGMT_NIC} ip address ${MGMT_IP} /${MGMT_MASK}
END
```
**stor**
```sh
STOR_NIC=eth1
STOR_IP=192.168.181.NN
STOR_MASK=24

# cli -m config <<END
bridge mgmt
interface ${STOR_NIC} bridge-group mgmt
no interface ${STOR_NIC}  ip address
interface ${STOR_NIC} ip address ${STOR_IP} /${STOR_MASK}
END
```


##Setting up Automation Scripts

Download the virtual python env containing all necessary scripts. Below is one time activity.

```
# wget http://kite.ggn.in.guavus.com/users/kapil/hubrix/hubrix-latest.bzip
# tar -xf hubrix-latest.bzip
# echo "alias activate='source ~/hubrix/bin/activate'" >> ~/.bashrc
# source ~/.bashrc
# activate
# cd python_env/robot
# ./Setup.py setup.ini

Full help Section
=================
# ./Setup.py -h
usage: Setup.py [-h] [-l LOGFILE] [-c] [--lazy] [--reconfig] [--no-storage]
                [--force-format] [--no-format] [--no-ha] [--no-hdfs] [--wipe]
                [--no-backup-hdfs] [--col-sanity] [--col-sanity-only]
                [--email] [--rpm] [--skip-vm SKIP_VM [SKIP_VM ...]]
                INIFILE

Make Appliance setups from INI File

positional arguments:
  INIFILE               INI file to choose as Input

optional arguments:
  -h, --help            show this help message and exit
  -l LOGFILE, --log LOGFILE
                        Custom logfile name. Default is <ScriptName.Time.log>
  -c, --check-ini       Just validate INI file
  --lazy                Skip creating template. Use previous one
  --reconfig            Skip manuf. VMS . Just factory revert and apply INI
  --no-storage          Skip iscsi config and remote storage
  --force-format        Format Volumes, Even if Filesystem present "no-strict"
  --no-format           Don't format remote storage, override ini settings
  --no-ha               skip configuring clustering.
  --no-hdfs             skip configuring HDFS
  --wipe                Delete Host's complete VM-Pool in initialisation
  --no-backup-hdfs      Skip configuring backup hdfs if configuring yarn
  --col-sanity          Execute Collector Sanity test-suite
  --col-sanity-only     Execute Only Collector Sanity test-suite. Implies that
                        setup is collector ready
  --email               Send results and report in email
  --rpm                 Test Platform rpm model
  --skip-vm SKIP_VM [SKIP_VM ...]
                        TOBE_IMPLEMENTED skip vm in ini with these names


```
## Extend hubrix
To install additional python packages for addon functionality
```
# symlink_headers 
Now you will be able to install / upgrade the python packages inside hubrix ( Not touching the Appliance ENV )
# pip install --upgrade setuptools
Collecting setuptools
  Downloading setuptools-17.1.1-py2.py3-none-any.whl (461kB)
    100% |################################| 462kB 541kB/s 
Installing collected packages: setuptools
      Successfully uninstalled setuptools-11.0
Successfully installed setuptools-17.1.1
```

##How to make ini file
```ini
[HOSTS]
iso_path = ( Values can be "nightly" or "http://station117_iso_path" )
upgrade_img = ( If upgrade too will be done then give upgrade.img file )
name_server = (DNS server 103.14.2.35 )
release_ver = ( Its used as marking comment for the VM in Host..shows up in "show virt vm" )
install_type = ( Values can be manufacture , upgrade OR manufacture+upgrade )
ntp_server = (Values can be any ntp server default is 198.55.111.5 )
yarn_nameservice = (String that would be used as yarn_name_service )
snmpsink_server = ( SNMP Sink for the whole setup )

        [[ANY-DESCRIPTOR-FOR-HOST]] <== Choose any name , this wont change any thing on system just a desc.
        ip = (Value is HOST-IP )
        username = ( username for host eg. admin )
        password = ( password for host eg. admin@123)
	brMgmt = Name of the management bridge on Host (default = mgmt)
	brStor = Name of the Storage bridge (default = stor)
	template_file = If in any rare circustance you want to change the name of template file used (default = /data/virt/pools/default/template.img )

                [[[five-one]]]   <== Choose any name for VM, used as host-name inside VMs , hence be unique.
                mgmt_ip = 192.168.NN.NN
                mgmt_mask = 22
                gw = 192.168.NN.NN
                stor_ip = 192.168.NN.NN
                stor_mask = 24
                enabled_users = admin:admin@123 , root:root@123 , monitor:monitor@123
                cluster_vip = 192.168.NN.NN
                name_node = 1

                        [[[[storage]]]]

                        initiatorname_iscsi = ( Value Initiator name assigned by IT )
                        iscsi_target = ( Value storage target IPs )
                        forbidden_nodes = [] ( Values iscsi nodes to ignore, unreachable IPs on target )

                        [[[[tps-fs]]]]

                                [[[[[pgsql]]]]] <=== This is the tps-fs name entry
                                wwid = 3600...000000   <== WWID given by IT
                                mount-point = /data/pgsql  <== Mount point where this would be mounted after formatting

                                [[[[[yarn]]]]]
                                wwid = 3600....00000
                                mount-point = /data/yarn

        [[ANOTHER-DESCRIPTOR-FOR-HOST]]
		....(same like above )
```
INI examples

setup.ini
- 3-3 VMs on 2 Hosts
- Multiple threads for Host preparation
- manufacture 
- clustering 
- HDFS HA





License
----
**Free , Hell Yeah!**
