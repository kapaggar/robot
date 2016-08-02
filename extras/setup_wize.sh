#--------------------------------
# Current Server Variables
#--------------------------------

DEPLOY_ARCHIVE="$HOME/work"



#--------------------------------
# Targe Server Variables
#--------------------------------
TARGET_DATADIR="/data/wize"

die() {
    echo "FATAL: $*; exiting"
    exit 1
}

error() {
    echo "ERROR: $*"
}

debug() {
    echo "DEBUG: $*"
}

generateInstall() {
    cat>${INTALL_SH} <<EOF
echo "#--------------------------------"
echo "# Installing Wize Setup"
echo "#--------------------------------"
source ${TARGET_DATADIR}/${target_envfile}
IS_NODE="\$(which node 2>/dev/null)"
if [ "\$IS_NODE" = "" ];then
   echo "No Node installtion Found. Exiting..."
   exit 1
fi
echo "1. Extracting Required tgzs" 

mkdir -p ${TARGET_DATADIR}/{server,client,data,client-code} || echo "Cannot make ${TARGET_DATADIR}/{server,client,data,client-code} "
tar -xf ${TARGET_DATADIR}/server.tgz -C ${TARGET_DATADIR}/server --strip-components 3 || echo "Cannot extract server zip in ${TARGET_DATADIR}/server "
tar -xf ${TARGET_DATADIR}/data.tgz -C ${TARGET_DATADIR}/data --strip-components 4 ||   echo "Cannot extract data zip in ${TARGET_DATADIR}/data"
tar -xf ${TARGET_DATADIR}/client.tgz -C ${TARGET_DATADIR}/client --strip-components 4 || echo "Cannot extract client zip in ${TARGET_DATADIR}/client "
rm -rf ${TARGET_DATADIR}/{client.tgz,server.tgz,data.tgz}

echo "2. Setting Up Wize Server" 

cd "${TARGET_DATADIR}/server"; mkdir -p logs
echo "Replacing server variables"
SERVER_CONF=server/config.js
##===============================[ SERVER VARIABLES ]===================================##
[[ -n \${_LDAP_URL_} ]] && sed -i -e "s/_LDAP_URL_/\${_LDAP_URL_}/g" \${SERVER_CONF}
[[ -n \${_BIND_USER_} ]] && sed -i -e "s/_BIND_USER_/\${_BIND_USER_}/g" \${SERVER_CONF}
[[ -n \${_BIND_PASSWORD_} ]] && sed -i -e "s/_BIND_PASSWORD_/\${_BIND_PASSWORD_}/g" \${SERVER_CONF}
[[ -n \${_LDAP_SEARCH_BASE_} ]] && sed -i -e "s/_LDAP_SEARCH_BASE_/\${_LDAP_SEARCH_BASE_}/g" \${SERVER_CONF}
[[ -n \${_MAIL_SERVICE_} ]] && sed -i -e "s/_MAIL_SERVICE_/\${_MAIL_SERVICE_}/g" \${SERVER_CONF}
[[ -n \${_MAIL_USER_} ]] && sed -i -e "s/_MAIL_USER_/\${_MAIL_USER_}/g" \${SERVER_CONF}
[[ -n \${_MAIL_PASSWORD_} ]] && sed -i -e "s/_MAIL_PASSWORD_/\${_MAIL_PASSWORD_}/g" \${SERVER_CONF}
[[ -n \${_GIT_CLIENT_ID_} ]] && sed -i -e "s/_GIT_CLIENT_ID_/\${_GIT_CLIENT_ID_}/g" \${SERVER_CONF}
[[ -n \${_GIT_SECRET_KEY_} ]] && sed -i -e "s/_GIT_SECRET_KEY_/\${_GIT_SECRET_KEY_}/g" \${SERVER_CONF}
[[ -n \${_GIT_REDIRECT_URL_} ]] && sed -i -e "s/_GIT_REDIRECT_URL_/\${_GIT_REDIRECT_URL_}/g" \${SERVER_CONF}
[[ -n \${activateAd} ]] && sed -i "s/activateAd\s*:\s*.*,/activateAd: \${isClusterEnvironment},/g" \${SERVER_CONF}
[[ -n \${mongoHost} ]] && sed -i "s/mongoHost\s*:\s*.*,/mongoHost: \${mongoHost},/g" \${SERVER_CONF}
[[ -n \${replicaSet} ]] && sed -i "s/replicaSet\s*:\s*.*,/replicaSet: \${replicaSet},/g" \${SERVER_CONF}
[[ -n \${authSource} ]] && sed -i "s/authSource\s*:\s*.*,/authSource: \${authSource},/g" \${SERVER_CONF}
[[ -n \${mongoDBName} ]] && sed -i "s/mongoDBName\s*:\s*.*,/mongoDBName: \${mongoDBName},/g" \${SERVER_CONF}
[[ -n \${numberOfWorkers} ]] && sed -i "s/numberOfWorkers\s*:\s*.*,/numberOfWorkers: \${numberOfWorkers},/g" \${SERVER_CONF} 
[[ -n \${isClusterEnvironment} ]] && sed -i "s/isClusterEnvironment\s*:\s*.*,/isClusterEnvironment: \${isClusterEnvironment},/g" \${SERVER_CONF}
##===============================[ SERVER VARIABLES ]===================================##

export TIMESTAMP=\$(date +%F_%H:%M:%S)
echo "Launching wize-server"
nohup nice -n 10 node app >>logs/server_\${TIMESTAMP}_stdout.log 2>>logs/server_\${TIMESTAMP}_stderr.log &

echo "3. Setting Up Wize Client" 

cd "${TARGET_DATADIR}/client"
MY_IPADDR=\$(/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1'|head -1)
SERVER_PORT=8080
MAIN_FILE=\$(ls -1 main*.bundle.js)
grep -q localhost:8080 \${MAIN_FILE} && sed -i.bak -e "s/localhost:8080/\${MY_IPADDR}:\${SERVER_PORT}/" \${MAIN_FILE} || echo "Cant find localhost:8080 to replace"
cd ${TARGET_DATADIR}
export TIMESTAMP=\$(date +%F_%H:%M:%S)
echo "Launching wize-client"
nohup nice -n 10 http-server client --cors -p 3000  >>client/client_\${TIMESTAMP}_stdout.log 2>>client/client_\${TIMESTAMP}_stderr.log &


echo "4. Setting Up Wize Data" 

cd "${TARGET_DATADIR}/data"
MY_IPADDR=\$(/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1'|head -1)
SERVER_PORT=8080
MAIN_FILE=\$(ls -1 main*.bundle.js)
grep -q localhost:8080 \${MAIN_FILE} && sed -i.bak -e "s/localhost:8080/\${MY_IPADDR}:\${SERVER_PORT}/" \${MAIN_FILE} || echo "Cant find localhost:8080 to replace"
cd ${TARGET_DATADIR}
export TIMESTAMP=\$(date +%F_%H:%M:%S)
echo "Launching wize-data"
nohup nice -n 10 http-server data --cors -p 4000  >>data/data_\${TIMESTAMP}_stdout.log 2>>data/data_\${TIMESTAMP}_stderr.log &

EOF
}


showUsage () {
    echo -e "Usage: `basename $0` -[uih]";
    echo -e "\t -u: Username for Deployment Server"
    echo -e "\t -i: IP/hostname of Deployment "
    echo -e "\t -f: ENV file of Deployment "
    echo -e "\t -h: help "
}

while getopts i:u:f:h opt ; do
        case "$opt" in
           i)
                deployAt="${OPTARG}"
                ;;
           u)
                deployWith="${OPTARG}"
                ;;
           f)
                target_envfile="${OPTARG}"
                ;;
          \?)
                showUsage
                exit 1
                ;;
        esac
done

if [ $# -eq 0 ]; then
        showUsage
        exit 1
fi

[[ -f ${target_envfile} ]] || die "Cannot continue. target envfile missing"
#-------------------------------------
# Create Uniqe Deployment Instance
#-------------------------------------
TIMESTAMP=$(date +%s)
DEPLOYMENT_SETUP_LOC="$DEPLOY_ARCHIVE/${deployAt}-${deployWith}-${TIMESTAMP}"
mkdir -p $DEPLOYMENT_SETUP_LOC
INTALL_SH="${DEPLOYMENT_SETUP_LOC}/install.sh"

echo "Creating Local Installation Setup at :$DEPLOYMENT_SETUP_LOC"
#------------------------------------
# Copy Required tgz
#------------------------------------
cp server.tgz data.tgz client.tgz ${target_envfile} $DEPLOYMENT_SETUP_LOC

#------------------------------------
# Generate install.sh 
#------------------------------------

generateInstall

#------------------------------------
# Scp To Target Server
#------------------------------------

ssh $SSH_OPTIONS $deployWith@$deployAt "mkdir -p $TARGET_DATADIR"
cd $DEPLOYMENT_SETUP_LOC; tar czf - * |ssh  $SSH_OPTIONS $deployWith@$deployAt "cd $TARGET_DATADIR; tar -zxf -"

#------------------------------------
# Trigger Install.sh on Destination Server
#------------------------------------

ssh $SSH_OPTIONS $deployWith@$deployAt "bash $TARGET_DATADIR/install.sh"
#------------------------------------
# target_end.sh template
#------------------------------------
make_envtemplate(){
TEMPLATE_FILE=$1
cat >TEMPLATE_FILE<<WOOF
_LDAP_URL_=
_BIND_USER_=
_BIND_PASSWORD_=
_LDAP_SEARCH_BASE_=
_MAIL_SERVICE_="Gmail"
_MAIL_USER_=
_MAIL_PASSWORD_=
_GIT_CLIENT_ID_=
_GIT_SECRET_KEY_=
_GIT_REDIRECT_URL_=
mongoHost=
replicaSet=
authSource=
mongoDBName=
numberOfWorkers=
isClusterEnvironment=
WOOF
}


