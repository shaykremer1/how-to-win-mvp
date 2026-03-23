import requests

url = "https://ibasketball.co.il/scoreboard/?object=sp_event&id=1201183"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
r.raise_for_status()

print("content-type:", r.headers.get("content-type"))
print(r.text[:2000])