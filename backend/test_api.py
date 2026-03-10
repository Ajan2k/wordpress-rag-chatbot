import json, urllib.request, urllib.error
req = urllib.request.Request(
    'http://localhost:8000/api/chat/stream',
    data=json.dumps({"question": "tell me about diabetes"}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        for chunk in response:
            print(chunk.decode(), end="")
except urllib.error.HTTPError as e:
    print("Code:", e.code)
    print("Body:", e.read().decode())
except Exception as e:
    import traceback
    traceback.print_exc()
