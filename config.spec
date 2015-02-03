[HOSTS]
iso_path = string(default=nightly)
upgrade_img = string(default=None)
nightly_dir = string(default=http://kite.ggn.in.guavus.com/snoopy/work/platform-master/output/product-guavus-x86_64/release/mfgcd)
name_server = ip_addr(default = 103.14.2.35)
release_ver = string(default = nightly)
install_type = string(default  = manufacture)
ntp_server = ip_addr( default = 198.55.111.5)
yarn_nameservice = string( default = JeSuisYarn )
snmpsink_server = ip_addr

[[__many__]]
ip = ip_addr
username = string(default=admin)
password = string(default=admin@123)
brMgmt = string(default = mgmt)
brStor = string(default = stor)

[[[__many__]]]
mgmt_ip = ip_addr
mgmt_mask =  integer(min=8, max=32, default=24)
gw = ip_addr
stor_ip = ip_addr
cpus =  integer(min=1, max=24, default=4)
memory =  integer(min=8192, max=96000, default=16384)
stor_mask = integer(min=8, max=32, default=24)
enabled_users = string_list
cluster_vip = ip_addr(default = None)
name_node = integer(default = None)
journal_node =  integer(min=1, max=6, default=None)
cluster_name = string(default = None)
[[[[storage]]]]
initiatorname_iscsi = string(default = None)
iscsi_target = ip_addr
forbidden_nodes = 
[[[[multipath-alias]]]]
pgsql = string
[[[[tps-fs]]]]
[[[[[__many__]]]]]
wwid = string
mount-point = string


