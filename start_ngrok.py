import subprocess
import time
import urllib.request
import json
import sys

print("Starting ngrok...")
p = subprocess.Popen(['ngrok', 'http', '8000'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)

try:
    req = urllib.request.Request('http://127.0.0.1:4040/api/tunnels')
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        url = data['tunnels'][0]['public_url']
        print("NGROK_URL:", url)
except Exception as e:
    print("Failed to get ngrok url. Is it authenticated?", str(e))
    # kill the process if it failed
    p.kill()
    sys.exit(1)
