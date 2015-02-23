#!/bin/bash
runningActiveConfigFile=`mktemp`
runningStandByConfigFile=`mktemp`
configurableSetings=`mktemp`
configuredActiveSettings=`mktemp`
configuredStandBySettings=`mktemp`
mapIpHost=`mktemp`
ipHostMappingError=`mktemp`
selfHostAccess=`mktemp`
remoteHostAccess=`mktemp`
hostsMismatch=`mktemp`
clusterIDError=`mktemp`
freeSpaceError=`mktemp`
validInput=`mktemp`

currHost=`hostname`
export STOP_EXECUTION=0
validUsers="root admin"

FREE_SPACE_UPPERLIMIT=98

cleanUpFiles() {
	rm -rf $runningActiveConfigFile
	rm -rf $configurableSetings
	rm -rf $configuredActiveSettings
	rm -rf $runningStandByConfigFile
	rm -rf $configuredStandBySettings
	rm -rf $ipHostMappingError
	rm -rf $mapIpHost
	rm -rf $selfHostAccess
	rm -rf $remoteHostAccess
	rm -rf $clusterIDError
	rm -rf $freeSpaceError
	rm -rf $validInput
}

isValidRun() {
	setupType=`grep  -E "/tps/process/(hadoop|hadoop_yarn) value" ${runningActiveConfigFile}| awk '{print $NF}'`
	case $setupType in
		"hadoop" )
			setup="HADOOP"
			;;
		"hadoop_yarn" )
			setup="YARN"
			;;
		*)
			echo "Please Run This Script On HADOOP/YARN NameNode"
			cleanUpFiles
			exit 1
			;;
	esac
}

configDump () {
	echo "show running-config" | cli -m config |  grep  -E "/tps/process/(hadoop|hadoop_yarn)" >${runningActiveConfigFile}
}

configDumpRemote () {
	ssh -q -l root $1 'echo "show running-config" | /opt/tms/bin/cli -m config |  grep  -E "/tps/process/(hadoop|hadoop_yarn)"' >$2
}

checkConfigHA() {
	var=`grep '^config_ha' ${configuredActiveSettings} | cut -d ':' -f2 | tr '[:upper:]' '[:lower:]'`
	echo $var
}

checkNameNode1() {
	var=`grep '^namenode1' ${configuredActiveSettings} | cut -d ':' -f2`
	echo $var
}

checkNameNode2() {
	var=`grep '^namenode2' ${configuredActiveSettings} | cut -d ':' -f2`
	echo $var
}

checkNameService() {
	var=`grep '^nameservice' ${configuredActiveSettings} | cut -d ':' -f2`
	echo $var
}

getList() {
	var=""
	for val in `grep "^$1" ${configuredActiveSettings}`
	do
		sAdd=`echo "$val"| cut -d ':' -f2`
		var=$var" "$sAdd
	done
	echo "$var"
}

clusterApplicableConfig() {
	inConfig=$1
	outConfig=$2
	grep '/tps/process/hadoop_yarn/attribute'  ${inConfig} | sed -e '/values/{s#\(.*\)/attribute/\(.*\)/values/\(.*\) value \(.*\) \(.*\)#\2:\5#}' -e '/value value/{s#\(.*\)/attribute/\(.*\)/value value \(.*\) \(.*\)#\2:\4#}' -e '/value/{d}' | grep -v '"'| sed 's/ //g' >$outConfig
	grep '/tps/process/hadoop_yarn/config/' ${inConfig}  | grep attribute |grep 'value value'| sed 's#\(.*\)/values/\(.*\)/attribute/\(.*\)/value value \(.*\) \(.*\)#\2:\3=\5#'>>$outConfig
}

moreConfigurableSettings() {
	grep '/tps/process/hadoop_yarn/' /opt/samples/yarn_conf/*.xml.* | sort -u | awk '{$1="";print $0}' | sed -e 's#\(.*\)\[\[\(.*\)\]\]\(.*\)#\2#' -e 's#\(.*\)/attribute/\(.*\)/value\}\,\(.*\)#\2\:\3#' | grep -v '/tps/process' | sort -u | sed 's/ //g'>${configurableSetings}
}

isKeyLessSSH(){
	var=$(ssh -q -oBatchMode=yes -oPreferredAuthentications=publickey -l $1 $2 'exit' || echo "false")
	echo $var | grep -q 'UNIX shell commands cannot be executed using this account'
	if [[ $? -eq 0 ]]
	then
		echo "Allowed"
	else
		if [[ $var = "false" ]];then
			echo "Denied"
		else
			echo "Allowed"
		fi
	fi
}

checkAllNodeAccess() {
	for tHost in ${validNodes[@]}
	do
		for usr in ${validUsers[@]}
		do
			testOut=$(isKeyLessSSH $usr $tHost)
			echo $usr"@"$tHost":"$testOut
		done
	done >$selfHostAccess
}

checkAllNodeAccessFromRemote() {
ssh -q -T -l root $1<<EOF
isKeyLessSSH(){
	var=\$(ssh -q -oBatchMode=yes -oPreferredAuthentications=publickey -l \$1 \$2 'exit' || echo "false")
	echo \$var | grep -q 'UNIX shell commands cannot be executed using this account'
	if [[ \$? -eq 0 ]]
	then
		echo "Allowed"
	else
		if [[ \$var = "false" ]];then
			echo "Denied"
		else
			echo "Allowed"
		fi
	fi
}
for tHost in ${validNodes[@]}
do
	for usr in ${validUsers[@]}
	do
		testOut=\$(isKeyLessSSH \$usr \$tHost)
		echo \$usr"@"\$tHost":"\$testOut
	done
done
EOF
}

checkClusterIdMisMatch ()
{
	for dn in ${slavesList[@]}
	do
		dataDirs=($(ssh -q -l root $dn "sed -n '/dfs.datanode.data.dir/{n;p}' /opt/hadoop/conf/hdfs-site.xml 2>/dev/null | sed 's#\(.*\)>\(.*\)<\(.*\)#\2#' | sed 's#,# #g'" ))
		if [[ ${#dataDirs[@]} -lt 1 ]];then
			echo "$currHost:$dn No Conf Found"
		else
			for dDir in "${dataDirs[@]}";do
				diff <(cat /data/yarn/namenode/current/VERSION  | grep clusterID | cut -d "=" -f2) <(ssh -q -l root $dn 'cat '$dDir'/current/VERSION  2>/dev/null | grep clusterID | cut -d "=" -f2') >/dev/null 2>&1
				if [[ $? -ne 0 ]];then
					echo "$currHost:$dn DataNode dir $dDir"
				fi
			done
		fi

	done

	for jn in ${journalnodeList[@]}
	do
		diff <(cat /data/yarn/namenode/current/VERSION  | grep clusterID | cut -d "=" -f2) <(ssh -q -l root $jn 'cat /data/yarn/journalnode/*/current/VERSION 2>/dev/null | grep clusterID | cut -d "=" -f2') >/dev/null 2>&1
		if [[ $? -ne 0 ]];then
			echo "$currHost:$jn JournalNode"
		fi
	done

	if [[ $standByNode != "" ]]
	then
		diff <(cat /data/yarn/namenode/current/VERSION  | grep clusterID | cut -d "=" -f2) <(ssh -q -l root $standByNode 'cat /data/yarn/namenode/current/VERSION 2>/dev/null | grep clusterID | cut -d "=" -f2') >/dev/null 2>&1
		if [[ $? -ne 0 ]];then
			echo "$currHost:$standByNode NameNode"
		fi
	fi
}



checkFreeSpace() {
	for tHost in ${validNodes[@]}
	do
		tSpace=$(ssh -q -l root $tHost "df -k  /data/  | sed 1d | awk '{print \$5}' | sed 's/%//'")
		if [[ $tSpace -gt $FREE_SPACE_UPPERLIMIT ]];then
			echo "$tHost:$tSpace"
		fi
	done>$freeSpaceError
}


checkValidInput () {
	if [[ ! -z $nameNode1 ]] && [[ $(isValidIPFormat $nameNode1) != "false" ]];then
		echo "namenode1:$nameNode1 not valid hostname"
	fi

	if [[ ! -z $nameNode2 ]] && [[ $(isValidIPFormat $nameNode2) != "false" ]];then
		echo "namenode2:$nameNode2 not valid hostname"
	fi

	for dn in ${slavesList[@]}
	do
		if [[  $(isValidIPFormat $dn) != "true" ]];then
			echo "slve:$dn not a valid IP address "
		fi
	done

	if [[ $isHASetup != "true" ]] && [[ ! -z $nameNode2 ]];then
		echo "namenode2:$nameNode2 Defined for NON-HA setup"
	fi

	if [[ $isHASetup = "true" ]] && [[  -z $nameNode2 ]];then
		echo "namenode2:Not Defined for HA setup"
	fi

	if [[ $isHASetup != "true" ]] && [[  ! -z $nameService ]];then
		echo "nameservice:$nameService Defined for NON-HA setup"
	fi

	if [[ $isHASetup = "true" ]] && [[  -z $nameService ]];then
		echo "nameservice:Not Defined for HA setup"
	fi

}


isValidIPFormat() {
	echo $1|grep -qE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'
	if [[ $? -eq 0 ]]
	then
		echo "true"
	else
		echo "false"
	fi
}

getHostNameForIp () {
	echo `grep $1 /etc/hosts | awk '{print $2}'`
}

getIpForHostName () {
	echo `grep -w $1 /etc/hosts | awk '{print $1}'`
}

getAllNodesList() {
	tmpFile=`mktemp`
	allNodes=$nameNode1" "$nameNode2" "$slavesList" "$journalnodeList" "$clientList
	for node in ${allNodes[@]}
	do
		if [[ $(isValidIPFormat $node) = "false" ]]
		then
			tIp=$(getIpForHostName $node)
			if [[ $tIp = "" ]]
			then
				echo " :"$node>>$ipHostMappingError
			else
				nodes=$nodes" "$tIp
			fi
		else
			nodes=$nodes" "$node
		fi
	done
	uniqueNodes=`echo $nodes| tr " " "\n" | sort -u`
	grepS=`echo $uniqueNodes|sed 's/ /\|/g'`
	oFS=$IFS
	IFS=$'\n'
	for tString in `grep -E $grepS /etc/hosts`
	do
		echo "$tString"
	done >$tmpFile
	IFS=$oFS

	if [[ -s $ipHostMappingError ]]
	then
		STOP_EXECUTION=1
	else
		export validNodes="`echo $uniqueNodes`"
	fi

	awk  -v correctFile=$mapIpHost ' \
	{ \
		if(NF==2) \
		{ \
			if($1==$2) {\
				print $1":"$2; \
			}\
			else {\
				print $1":"$2>correctFile
			}\
		} \
		else { \
			t=$1; \
			$1=""; \
			print t":"$0 ; \
		} \
	}' $tmpFile >>$ipHostMappingError
	rm -rf $tmpFile
}

getStandByNode () {
	validNameNodeIp=$(isValidIPFormat $nameNode1)
	if [[ $currHost = $nameNode1 ]] && [[ $nameNode2 != "" ]]
	then
		remoteHost=${nameNode2}
	elif [[ $currHost = $nameNode2 ]] && [[ $nameNode1 != "" ]]
	then
		remoteHost=${nameNode1}
	elif [[ $validNameNodeIp = "true" ]]
	then
		tempNN=$(getHostNameForIp $nameNode1)

		if [[ $currHost = $tempNN ]] && [[ $nameNode2 != "" ]]
		then
			remoteHost=${nameNode2}
		elif [[ $currHost = $tempNN ]] && [[ $nameNode1 != "" ]]
		then
			remoteHost=${nameNode1}
		fi
	fi
	echo $remoteHost
}

getEtcHostDiff(){
	currIp=$(getIpForHostName $currHost)
	grepS=`echo $validNodes| sed 's# #\|#g'`
	for rHost in `echo $validNodes | sed "s/$currIp//"`
	do
		diff <(grep -wE "$grepS" /etc/hosts) <(ssh -q -l root $rHost "grep -wE \"$grepS\" /etc/hosts") >/dev/null 2>&1
		if [[ $? -ne 0 ]];then
			echo "Hosts File Mismatch:$currIp vs $rHost"
		fi
	done >$hostsMismatch
}


randerKeyValue() {
	sourceFile="$1"
	header="$2"
	keyTitle="$3"
	valueTitle="$4"
	awk -v tableHeader="$header" -v keyName="$keyTitle" -v valueName="$valueTitle" '
	BEGIN { \
		idx=0; \
		maxLen=20; \
	} \
	{ \
		split($0,temp,":"); \
		key[idx]=temp[1]; \
		value[idx]=temp[2]; \
		a=maxLen; \
		b=length(key[idx]); \
		c=length(value[idx]); \
		maxLen=a>b?(a>c?a:c):(b>c?b:c); \
		idx++; \
	} \
	END{ \
	\
		space=" "; \
		totalWidth=4*maxLen; \
		halfWidth=totalWidth/2; \
		leftHeaderMargin=int((totalWidth-length(tableHeader))/2); \
		rightHeaderMargin=totalWidth+1-(leftHeaderMargin+length(tableHeader)); \
		leftKeyTitleMargin=int((halfWidth-length(keyName))/2);  \
		rightKeyTitleMargin=halfWidth-(leftKeyTitleMargin+length(keyName)); \
		leftValueTitleMargin=int((halfWidth-length(valueName))/2); \
		rightValueTitleMargin=halfWidth-(leftValueTitleMargin+length(valueName)); \

		headerFmt="|%"leftHeaderMargin"s%s%"rightHeaderMargin"s|\n"; \
		titleFmt="|%"leftKeyTitleMargin"s%s%"rightKeyTitleMargin"s|%"leftValueTitleMargin"s%s%"rightValueTitleMargin"s|\n"; \
		rowFmt="|%-"halfWidth"s|%-"halfWidth"s|\n"; \
		tableUpperBorder="+%"totalWidth+1"s+"; \
		tableOtherBorder="+%"halfWidth"s+%"halfWidth"s+"; \

		upperLine=sprintf(tableUpperBorder,space); \
		gsub(/ /,"-",upperLine); \
		print upperLine; \
		printf headerFmt,space,tableHeader,space; \
		otherLine=sprintf(tableOtherBorder,space,space); \
		gsub(/ /,"-",otherLine); \
		print otherLine; \
		printf titleFmt,space,keyName,space,space,valueName,space; \
		print otherLine; \

		for(i=0;i<idx;i++){  \
			printf rowFmt,"  "key[i],"  "value[i]; \
		} \
		print otherLine; \
	}' $sourceFile
	echo ""
}


randerCompareTable() {

	srcFile="$1"
	destFile="$2"
	header="$3"
	srcTitle="$4"
	destTitle="$5"

	diff -y -W 200 $srcFile $destFile | awk -v tableHeader="$header" -v srcName="$srcTitle" -v destName="$destTitle" '\
	BEGIN { \
		configured=0; \
		configurable=0; \
		propMaxLength=10; \
		valueMaxLength=10; \
	} \
	{ \
		if(NF==3) { \
			split($1,temp,":"); \
			configuredProperty[configured]=temp[1]; \
			configuredValue[configured]=temp[2]; \

			split($3,temp,":"); \
			configurableProperty[configurable]=temp[1]; \
			configurableValue[configurable]=temp[2]; \

			a=propMaxLength; \
			b=length(configuredProperty[configured]); \
			c=length(configurableProperty[configurable]); \
			propMaxLength=a>b?(a>c?a:c):(b>c?b:c); \

			a=valueMaxLength; \
			b=length(configuredValue[configured]); \
			c=length(configurableValue[configurable]); \
			valueMaxLength=a>b?(a>c?a:c):(b>c?b:c); \

			configured++; \
			configurable++; \
		} \
			else if (NF==2 && $1==">") { \
					split($2,temp,":"); \
			configurableProperty[configurable]=temp[1]; \
			configurableValue[configurable]=temp[2]; \

			a=propMaxLength; \
			b=length(configurableProperty[configurable]); \
			propMaxLength=a>b?a:b; \

			a=valueMaxLength; \
			b=length(configurableValue[configurable]); \
			valueMaxLength=a>b?a:b;     \

			configurable++; \

			} \
			else if (NF==2 && $2 == "<") { \
			split($1,temp,":"); \
			configuredProperty[configured]=temp[1]; \
			configuredValue[configured]=temp[2]; \
			a=propMaxLength; \
			b=length(configuredProperty[configured]); \
			propMaxLength=a>b?a:b; \
			a=valueMaxLength; \
			b=length(configuredValue[configured]); \
			valueMaxLength=a>b?a:b;     \
			configured++; \
		} \
				else  if(NF==2) { \
						split($1,temp,":"); \
						configuredProperty[configured]=temp[1]; \
						configuredValue[configured]=temp[2]; \

						split($2,temp,":"); \
						configurableProperty[configurable]=temp[1]; \
						configurableValue[configurable]=temp[2]; \

						a=propMaxLength; \
						b=length(configuredProperty[configured]); \
						c=length(configurableProperty[configurable]); \
						propMaxLength=a>b?(a>c?a:c):(b>c?b:c); \

						a=valueMaxLength; \
						b=length(configuredValue[configured]); \
						c=length(configurableValue[configurable]); \
						valueMaxLength=a>b?(a>c?a:c):(b>c?b:c); \

						configured++; \
						configurable++; \
				} \
	} \
	END { \
		if (configured>0 ||configurable) { \
			space=" "; \
			maxWidht=2*propMaxLength+2*valueMaxLength+8; \
			onePart=maxWidht/2; \

			headerMargin=int((maxWidht-length(tableHeader))/2) ; \
			srcTitleMargin=int((onePart-length(srcName))/2) ; \
			destTitleMargin=int((onePart-length(destName))/2) ; \

			headerFmt="|%"headerMargin+2"s%s%"maxWidht-(headerMargin+length(tableHeader))"s |\n" ; \
			titleFmt="|%"srcTitleMargin+1"s%s%"onePart-(srcTitleMargin+length(srcName))"s|%"destTitleMargin+1"s%s%"onePart-(destTitleMargin+length(destName))"s|\n"; \
			valueFmt="|%-"propMaxLength+2"s|%-"valueMaxLength+2"s|%-"propMaxLength+2"s|%-"valueMaxLength+2"s|\n"; \
			tableFmt="+%"propMaxLength+2"s%"valueMaxLength+4"s%"propMaxLength+2"s%"valueMaxLength+3"s+";  \

			dash=sprintf(tableFmt,space,space,space,space); \
			gsub(/ /,"-",dash); \
			print dash; \
			printf headerFmt,space,tableHeader,space; \
			print dash; \
			printf titleFmt,space,srcName,space,space,destName,space; \
			print dash; \
			maxData=configured>configurable?configured:configurable; \
			for(i=0;i<maxData;i++){ \
				printf valueFmt,"  "configuredProperty[i],"  "configuredValue[i],"  "configurableProperty[i],"  "configurableValue[i]; \
			} \
			print dash; \
		} \
	}'
	echo ""
}

configDump
isValidRun

moreConfigurableSettings
clusterApplicableConfig ${runningActiveConfigFile} $configuredActiveSettings

isHASetup=$(checkConfigHA)
nameNode1=$(checkNameNode1)
nameNode2=$(checkNameNode2)
nameService=$(checkNameService)

slavesList=$(getList slave)
journalnodeList=$(getList journalnodes)
clientList=$(getList client)
getAllNodesList

if [[ $STOP_EXECUTION -eq 1 ]]
then
	echo "**************************************************************************"
	echo "                  - Please Correct This Error First -"
	echo "**************************************************************************"
	randerKeyValue $ipHostMappingError "Invalid IP to Host Mapping" "IP" "HostName"
	exit 1
fi

if [[ -s $ipHostMappingError ]]
then
	randerKeyValue $ipHostMappingError "ERROR : Invalid IP to Host Mapping" "IP" "HostName"
fi

if [[ $(isValidIPFormat $nameNode1) = "true" ]] || [[ $(isValidIPFormat $nameNode2) = "true" ]]
then
	echo "namenode1 and namenode2 should be Hostnames not IPs"
	exit
fi

if [[ $isHASetup = "true" ]]
then
	standByNode=$(getStandByNode)
	sshAccess=$(isKeyLessSSH root $standByNode)
	if [[ $standByNode != "" ]] && [[ $sshAccess = "Allowed" ]]
	then
		( configDumpRemote $standByNode $runningStandByConfigFile;
			clusterApplicableConfig ${runningStandByConfigFile} $configuredStandBySettings )&
		( checkAllNodeAccessFromRemote $standByNode >$remoteHostAccess)&
	fi
fi
( getEtcHostDiff )&
( checkAllNodeAccess )&
( checkClusterIdMisMatch >$clusterIDError) &
( checkFreeSpace )&
( checkValidInput > $validInput )&
wait

if [[ -s $hostsMismatch ]];then
	randerKeyValue $hostsMismatch "ERROR : Ip Host Mapping" "Test" "Error"
fi

grep -q 'Denied' $selfHostAccess $remoteHostAccess
if [[ $? -eq 0 ]];then
	if [[ $isHASetup = "true" ]];then
		randerCompareTable $selfHostAccess $remoteHostAccess "ERROR : Key Sharing in between Nodes" "From : $currHost" "From : $standByNode"
	else
		randerKeyValue $selfHostAccess "ERROR : Key Sharing in between Nodes" "Checking" "Access"
	fi
fi

if [[ -s $validInput ]];then
	randerKeyValue $validInput "ERROR : Configured Yarn" "pmx Node" " Error"
fi


if [[ -s $freeSpaceError ]];then
	randerKeyValue $freeSpaceError "ERROR : Partition /data/" "Host" " Used %"
fi


if [[ -s $clusterIDError ]];then
	randerKeyValue $clusterIDError "ERROR : ClusterID Mismatch" "Compared With" "Compared To"
fi

if [[ $isHASetup = "true" ]]
then
	diff $configuredActiveSettings $configuredStandBySettings >/dev/null 2>&1
	if [[ $? -ne 0 ]];then
		randerCompareTable $configuredActiveSettings $configuredStandBySettings "ERROR : Configuration Mismatch in Master and Standby Nodes" "$currHost" "$standByNode"
	fi
fi


randerCompareTable $configuredActiveSettings $configurableSetings "INFO : YARN Cluster Configurtaion" "Configured Properties" "Configurable (Optional)"
cleanUpFiles

