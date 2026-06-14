import json
checks = json.load(open("C:\\Users\\rohan\\AppData\\Local\\Temp\\checks.json"))
for cr in checks.get("check_runs", []):
    for a in cr.get("output", {}).get("annotations", []):
        print(a.get("path","") + ":" + str(a.get("start_line","")))
        print(a.get("message",""))
