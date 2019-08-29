FILE='autorun.stop'

while [ ! -f "$FILE" ]; do
    echo "$(date "+%Y-%m-%d-%H:%M:%S") running ..."
    python3 totle_api_client_v2.py $*
    echo "$(date "+%Y-%m-%d-%H:%M:%S") sleeping ..."
    sleep 60
done

echo "terminating and removing $FILE"
rm $FILE
    
