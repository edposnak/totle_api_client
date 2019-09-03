FILE='autorun.stop'

while : ; do    
    if [ ! -f "$FILE" ] ; then
        echo "$(date "+%Y-%m-%d-%H:%M:%S") running ..."
        python3 -u totle_api_client_v2.py $*
    fi
    
    if [ ! -f "$FILE" ] ; then
        echo "$(date "+%Y-%m-%d-%H:%M:%S") sleeping ..."
        sleep 60
    else
        echo "terminating due to existence of $FILE"
        break
    fi
done

