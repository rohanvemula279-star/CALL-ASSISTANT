import json, urllib.request, os

headers = {
    "User-Agent": "Python",
    "Accept": "application/vnd.github+json"
}

# Get job info
url = "https://api.github.com/repos/rohanvemula279-star/CALL-ASSISTANT/actions/runs/27492870743/jobs"
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

job = data["jobs"][0]
print("Job:", job["name"])
print("Status:", job["status"])
print("Conclusion:", job["conclusion"])
print("Steps:")
for s in job["steps"]:
    print(f"  {s['number']}. {s['name']}: {s['conclusion']}")
    if s["conclusion"] == "failure":
        print("    Logs URL hidden - use web interface")

# Get the HTML URL for the user
print()
print("Open in browser to see full error:")
print(f"https://github.com/rohanvemula279-star/CALL-ASSISTANT/actions/runs/27492870743")
