"""Verification script for Phase 2: Intelligence Engine."""
import requests
import json
import sys

BASE = "http://localhost:8000"

def test_endpoint(name, method, path, body=None):
    url = BASE + path
    try:
        if method == "GET":
            r = requests.get(url, timeout=90)
        else:
            r = requests.post(url, json=body, timeout=90)
        
        status = "PASS" if r.status_code == 200 else "FAIL"
        print(f"[{status}] {name}: status={r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                print(f"       Items returned: {len(data)}")
                if len(data) > 0:
                    print(f"       First item keys: {list(data[0].keys())}")
            elif isinstance(data, dict):
                if "features" in data:
                    print(f"       Features returned: {len(data['features'])}")
                else:
                    print(f"       Keys returned: {list(data.keys())}")
        else:
            print(f"       Error: {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"[FAIL] {name}: {str(e)[:200]}")
        return False

print("=" * 60)
print("Meghalaya GeoAI — Phase 2 Intelligence Verification")
print("=" * 60)

tests = []
tests.append(test_endpoint("Scoring: District", "POST", "/scoring", {"level": "district"}))
tests.append(test_endpoint("Scoring: Block", "POST", "/scoring", {"level": "block"}))
tests.append(test_endpoint("Heatmap: Road Density", "GET", "/heatmap?metric=avg_road_density&level=district"))
tests.append(test_endpoint("Heatmap: IFA Coverage", "GET", "/heatmap?metric=avg_ifa_coverage_girls&level=district"))

print("=" * 60)
passed = sum(tests)
total = len(tests)
print(f"Results: {passed}/{total} passed")
if passed != total:
    sys.exit(1)
