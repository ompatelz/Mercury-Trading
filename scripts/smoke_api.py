import urllib.request

with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as response:
    print(response.read().decode("utf-8"))
