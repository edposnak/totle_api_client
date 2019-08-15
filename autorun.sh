while true; do
    echo "running ..."
    python3 totle_api_client_v2.py
    sleep 1200
    python3 totle_api_client_v2.py --sell
    echo "sleeping ..."
    sleep 1200
done

    
