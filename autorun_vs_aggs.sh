FILE='autorun.stop'

while : ; do    
    if [ ! -f "$FILE" ] ; then
        echo "$(date "+%Y-%m-%d-%H:%M:%S") running ..."
        python3 -u totle_vs_aggs.py $*
    fi
    
    if [ ! -f "$FILE" ] ; then
        echo "$(date "+%Y-%m-%d-%H:%M:%S") sleeping ..."
        sleep 300
    else
        echo "terminating due to existence of $FILE"
        break
    fi
done

