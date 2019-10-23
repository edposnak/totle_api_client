FILE='autorun.stop'

cex=$1

if [[ -z $1 ]] ; then
    cmd=`basename $0`
    echo "usage: $cmd exchange_name"
    echo "e.g. $cmd kraken"
    exit 1
fi

echo vs_${1}.py
    
while : ; do    
    if [ ! -f "$FILE" ] ; then
        echo "$(date "+%Y-%m-%d-%H:%M:%S") running ..."
        python3 -u vs_${1}.py $*
    fi
    
    if [ ! -f "$FILE" ] ; then
        echo "$(date "+%Y-%m-%d-%H:%M:%S") sleeping ..."
        sleep 60
    else
        echo "terminating due to existence of $FILE"
        break
    fi
done

