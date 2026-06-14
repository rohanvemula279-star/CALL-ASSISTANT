import json
with open("C:\\Users\\rohan\\AppData\\Local\\Temp\\job3.json") as f:
    d = json.load(f)
j = d["jobs"][0]
for s in j["steps"]:
    print(f"{s['number']}. {s['name']}: {s['conclusion']}")
