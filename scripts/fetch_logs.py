import json, urllib.request, zipfile, os, tempfile

run_id = "27492870743"
headers = {"User-Agent": "Python"}
url = f"https://api.github.com/repos/rohanvemula279-star/CALL-ASSISTANT/actions/runs/{run_id}/logs"
req = urllib.request.Request(url, headers=headers)

tmp = os.path.join(tempfile.gettempdir(), "logs3.zip")
with urllib.request.urlopen(req) as resp:
    with open(tmp, "wb") as f:
        f.write(resp.read())

extract_dir = os.path.join(tempfile.gettempdir(), "logs3")
os.makedirs(extract_dir, exist_ok=True)

try:
    with zipfile.ZipFile(tmp) as z:
        z.extractall(extract_dir)
        for name in z.namelist():
            print(f"Log file: {name}")
except zipfile.BadZipFile:
    print("Not a zip, trying raw download...")
    with open(os.path.join(extract_dir, "raw_log.txt"), "wb") as f:
        with urllib.request.urlopen(req) as resp:
            f.write(resp.read())
    print("Saved as raw_log.txt")
