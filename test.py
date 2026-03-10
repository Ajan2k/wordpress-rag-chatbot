import json, urllib.request, urllib.error
req = urllib.request.Request(
    'http://localhost:8000/api/chat/ask',
    data=json.dumps({"question": "test"}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    response = urllib.request.urlopen(req)
    print(response.read().decode())
except urllib.error.HTTPError as e:
    print(e.read().decode())
