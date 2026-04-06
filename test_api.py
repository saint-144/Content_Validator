"""
test_api.py — Quick smoke test for all API endpoints.
Run: python test_api.py  (while backend is running on port 8000)
"""

import requests, sys, json

BASE = "http://localhost:8084"

def check(label, resp, expected=200):
    ok = resp.status_code == expected
    icon = "✅" if ok else "❌"
    print(f"  {icon}  {label}: HTTP {resp.status_code}")
    if not ok:
        try: print(f"      Detail: {resp.json().get('detail','')}")
        except: pass
    return ok

def run():
    print("=== ContentGuard API Smoke Tests ===\n")
    all_pass = True

    # Health
    r = requests.get(f"{BASE}/health")
    all_pass &= check("GET /health", r)

    # Dashboard
    r = requests.get(f"{BASE}/api/dashboard/stats")
    all_pass &= check("GET /api/dashboard/stats", r)

    # Templates - create
    r = requests.post(f"{BASE}/api/templates", json={"name": "__test_template__", "description": "CI test"})
    all_pass &= check("POST /api/templates", r)
    if r.status_code == 200:
        tid = r.json()["id"]

        # Get
        r2 = requests.get(f"{BASE}/api/templates/{tid}")
        all_pass &= check("GET /api/templates/{id}", r2)

        # List
        r3 = requests.get(f"{BASE}/api/templates")
        all_pass &= check("GET /api/templates", r3)

        # Delete
        r4 = requests.delete(f"{BASE}/api/templates/{tid}")
        all_pass &= check("DELETE /api/templates/{id}", r4)

    # Validations list
    r = requests.get(f"{BASE}/api/validations")
    all_pass &= check("GET /api/validations", r)

    # Reports list
    r = requests.get(f"{BASE}/api/reports")
    all_pass &= check("GET /api/reports", r)

    # Export (should return xlsx binary)
    r = requests.get(f"{BASE}/api/reports/export")
    all_pass &= check("GET /api/reports/export", r)
    if r.status_code == 200:
        ct = r.headers.get("content-type","")
        if "spreadsheet" in ct or "xlsx" in ct:
            print("     ✅ Excel content-type correct")
        else:
            print(f"     ⚠️  Unexpected content-type: {ct}")

    print(f"\n{'✅ All tests passed!' if all_pass else '❌ Some tests failed.'}")
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    run()
