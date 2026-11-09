# import requests

# url = "https://gamma-api.polymarket.com/events"

# params = {
#     "active": "true",
#     "closed": "false",
#     "limit": 5,
#     "offset": 0,
# }

# response = requests.get(url, params=params, timeout=30)
# response.raise_for_status()

# events = response.json()

# print(f"Retrieved {len(events)} events")

# for event in events:
#     print(event.get("id"), event.get("title"))

import requests

BASE_URL = "https://gamma-api.polymarket.com"

response = requests.get(
    f"{BASE_URL}/tags",
    params={"limit": 100, "offset": 0},
    timeout=30,
)
response.raise_for_status()

for tag in response.json():
    print(tag.get("id"), tag.get("label"), tag.get("slug"))



# python3 polymarket_collector.py