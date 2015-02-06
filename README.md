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
# wget http://eagle.ggn.in.guavus.com/users/kapil/python_env.bzip2
# tar -xf python_env.bzip2
# echo "alias activate='source ~/python_env/bin/activate'" >> ~/.bashrc
# source ~/.bashrc
# activate
# cd python_env/robot
# ./Host.py -i setup.ini
```

##How to make ini file
```ini
[HOSTS]
iso_path = ( Values can be "nightly" or "http://station117_iso_path )
upgrade_img = ( If upgrade too will be done then give upgrade.img file )
name_server = (DNS server 103.14.2.35 )
release_ver = ( Its used as 
install_type = ( Values can be manufacture , upgrade OR manufacture+upgrade )
ntp_server = (Values can be any ntp server default is 198.55.111.5 )
yarn_nameservice = (String that would be used as yarn_name_service )
snmpsink_server = ( SNMP Sink for the whole setup )

        [[ANY-DESCRIPTOR-FOR-HOST]] <== Choose any name , this wont change any thing on system just a desc.
        ip = (Value is HOST-IP )
        username = ( username for host eg. admin )
        password = ( password for host eg. admin@123)

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

FIVE.ini:
- Auto picks kite nightly
- manufacture + upgrade
- clustering enabled
- storage enabled
- yarn HA



FOUR.ini
-manufacture
- no clustering
- storage enabled
- no yarn HA



THREE.ini 
- Auto picks eagle's 4.2 nightly
- manufacture
- clustering enabled
- storage enabled
- yarn HA



TWO.ini
- manufacture
- only mgmt n/w
- clustering 
- hdfs
- no storage

License
----
**Free Software, Hell Yeah!**
