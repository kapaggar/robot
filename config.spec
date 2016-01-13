[HOSTS]
iso_path 				= string(	default = nightly)
upgrade_img 			= string(	default = None)
nightly_dir 			= string(	default = http://kite.ggn.in.guavus.com/snoopy/work/platform-master/output/product-guavus-x86_64/release/mfgcd)
centos_template_path	= string(	default = http://192.168.104.78/users/kapil/RPM/template-6.5.tgz)
centos_repo_path 		= string(	default = http://192.168.104.78/users/kapil/RPM/CentOS-Base.repo)
name_server 			= ip_addr(	default = 103.14.2.35)
release_ver 			= string(	default = nightly)
install_type 			= string(	default = manufacture)
ntp_server 				= ip_addr(	default = 198.55.111.5)
yarn_nameservice 		= string(	default = JeSuisYarn )
snmpsink_server 		= ip_addr(	default = None)
notifyFrom 				= string(	default = Hubrix<kapil.aggarwal@guavus.com>)
notifyTo 				= string_list(min=0, max=10, default = list('kapil.aggarwal@guavus.com'))
pub_keys				= string_list(min=0, max=10, default = list(''))

[[__many__]]
ip 						= ip_addr(	default = None)
username 				= string(	default = admin)
password 				= string(	default = admin@123)
brMgmt 					= string(	default = mgmt)
brStor 					= string(	default = stor)
template_file 			= string(	default = /data/virt/pools/default/template.img )
template_disk_size			= integer(      default = 100,  min=50, max=900, )

[[[__many__]]]
mgmt_ip 				= ip_addr(	default = None)
mgmt_mask 				= integer(	default = 24, min=8, max=32, )
gw 						= ip_addr(	default = None)
stor_ip 				= ip_addr(	default = None)
cpus 					= integer(	default = 4, min=1, max=24, )
memory 					= integer(	default = 16384, min=8192, max=96000, )
stor_mask 				= integer(	default = 24, min=8, max=32, )
mgmtNic 				= string(	default = eth0 )
storNic 				= string(	default = eth1 )
cluster_vip 			= ip_addr(	default = None)
name_node 				= integer(	default = None)
journal_node 			= integer(	default = None,	min=1, max=6, )
data_node 				= integer(	default = None,	min=1, max=6, )
rubix_node				= integer(      default = None, min=1, max=6, )
insta_node				= integer(      default = None, min=1, max=6, )
cluster_name 			= string(	default = None)
vm_ref 					= string(	default = None)
enabled_users			= string_list(  default = list('admin:admin@123' , 'root:root@123' , 'monitor:monitor@123'))
disk_size				= integer(	default = 100,	min=50, max=250, )

[[[[storage]]]]
initiatorname_iscsi 	= string(	default = None)
iscsi_target 			= ip_addr(	default=None)
forbidden_nodes 		= string_list(default = list())

[[[[multipath-alias]]]]
pgsql 					= string(	default=None)

[[[[tps-fs]]]]

[[[[[__many__]]]]]
wwid 					= string
mount-point 			= string
format 					= boolean(	default = no )
