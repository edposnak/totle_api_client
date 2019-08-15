while true; do
    echo "running ..."
    python3 totle_api_client_v2.py
    sleep 300
    python3 totle_api_client_v2.py --sell
    echo "sleeping ..."
    sleep 300
done

    
