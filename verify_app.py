import sys
import requests
import time
import threading
from app import app

def run_server():
    try:
        app.run(port=8050, debug=False)
    except Exception as e:
        print(f"Server error: {e}")

# Start the server in a separate thread
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

# Wait for server to start
time.sleep(3)

# Test if the server is responsive
try:
    response = requests.get('http://127.0.0.1:8050')
    if response.status_code == 200:
        print("SUCCESS: Dash app is running and responsive.")
        sys.exit(0)
    else:
        print(f"FAILURE: Server responded with status code {response.status_code}")
        sys.exit(1)
except requests.ConnectionError:
    print("FAILURE: Could not connect to the Dash server.")
    sys.exit(1)
except Exception as e:
    print(f"FAILURE: An error occurred: {e}")
    sys.exit(1)
