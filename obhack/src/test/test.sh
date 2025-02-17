#!/bin/bash

while true; do
    python3 test.py
    sleep 1800  # Sleep for 1 hour (3600 seconds)
done

# for i in {1..100}; do
#     curl -X POST "http://10.104.146.218/nobleapp/login" -d "username=admin&password=admin"
#     echo "Request $i completed"
#     sleep 1  # Adding a 1 second delay between requests to prevent overwhelming the server
# done
