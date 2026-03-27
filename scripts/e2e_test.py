"""End-to-end API test for the Meghalaya GeoAI platform."""
import requests
import json
import sys

BASE = "http://localhost:8000"

def test(name, method, path, body=None):
    url = BASE + path
    try:
        if method == "GET":
            r = requests.get(url, timeout=90)
        else:
            r = requests.post(url, json=body, timeout=90)
        d = r.json()

        # Count data items
        if "table" in d:
            rows = len(d["table"])
        elif "features" in d:
            rows = len(d["features"])
        elif "status" in d:
            rows = d["status"]
        else:
            rows = "?"

        geo = 0
        if isinstance(d.get("geojson"), dict):
            geo = len(d["geojson"].get("features", []))

        status = "PASS" if r.status_code == 200 else "FAIL"
        print(f"[{status}] {name}: status={r.status_code}, data_items={rows}, geo_features={geo}")

        if r.status_code != 200:
            print(f"       Detail: {r.text[:300]}")
        return r.status_code == 200
    except Exception as e:
        print(f"[FAIL] {name}: {str(e)[:200]}")
        return False

print("=" * 60)
print("Meghalaya GeoAI — End-to-End API Tests")
print("=" * 60)

results = []
results.append(test("Health Check", "GET", "/health"))
results.append(test("Basemap (district)", "GET", "/basemap?level=district"))
results.append(test("NLQ: Road Density", "POST", "/query",
    {"question": "Which districts have the highest road density?"}))
results.append(test("NLQ: Nutrition Priority", "POST", "/query",
    {"question": "Which districts should be top priority for nutrition?"}))
results.append(test("Drilldown: EAST KHASI HILLS", "GET",
    "/drilldown/district/EAST KHASI HILLS"))

print("=" * 60)
passed = sum(results)
total = len(results)
print(f"Results: {passed}/{total} passed")
if passed == total:
    print("ALL TESTS PASSED!")
else:
    print(f"WARNING: {total - passed} test(s) failed")
    sys.exit(1)
