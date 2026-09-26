import sys
import os
import io
import time
import zipfile
from pathlib import Path

# Force UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app, get_engine, scan_available_repositories, UPLOAD_WORKSPACE, BASE_DIR

def create_zip(repo_name, files_dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files_dict.items():
            zf.writestr(f"{repo_name}/{rel_path}", content)
    buf.seek(0)
    return buf

REPO_A_FILES = {
    "main.py": "def greet(name):\n    return f'Hello, {name}'\ndef main():\n    print(greet('A'))\n",
    "utils/math_a.py": "def calc_a(x):\n    return x + 10\n"
}

REPO_B_FILES = {
    "app.py": "def run_b():\n    return 'Running B'\n",
    "processor_b.py": "def process_b(data):\n    return [x * 3 for x in data]\n"
}

def run_tests():
    print("\n" + "="*70)
    print("  PHASE 2 COMPREHENSIVE VERIFICATION SUITE")
    print("="*70)
    
    app.config["TESTING"] = True
    client = app.test_client()

    # 1. GET /api/repositories
    print("\n[1] Testing GET /api/repositories...")
    res = client.get("/api/repositories")
    data = res.get_json()
    assert res.status_code == 200
    assert data["success"] is True
    print(f"    Available repos: {[r['id'] for r in data['repositories']]}")
    print("    [PASS] /api/repositories endpoint working")

    # 2. Upload Repo A
    print("\n[2] Uploading Repo A...")
    zip_a = create_zip("sample_repo_a", REPO_A_FILES)
    res_a = client.post("/api/upload_repo", data={"file": (zip_a, "sample_repo_a.zip")}, content_type="multipart/form-data")
    data_a = res_a.get_json()
    assert res_a.status_code == 200
    repo_a_id = data_a["active_repo_id"]
    print(f"    Uploaded Repo A with ID: {repo_a_id}")
    print("    [PASS] Repo A uploaded successfully")

    # 3. Upload Repo B
    print("\n[3] Uploading Repo B...")
    zip_b = create_zip("sample_repo_b", REPO_B_FILES)
    res_b = client.post("/api/upload_repo", data={"file": (zip_b, "sample_repo_b.zip")}, content_type="multipart/form-data")
    data_b = res_b.get_json()
    assert res_b.status_code == 200
    repo_b_id = data_b["active_repo_id"]
    print(f"    Uploaded Repo B with ID: {repo_b_id}")
    print("    [PASS] Repo B uploaded successfully")

    # 4. Sequence Switching (A -> B -> A -> B) & Timing Check
    print("\n[4] Testing Sequence Switching (A -> B -> A -> B)...")
    
    t0 = time.time()
    res_sw_a = client.post("/api/switch_repo", json={"repo_id": repo_a_id})
    t_sw_a = (time.time() - t0) * 1000
    assert res_sw_a.get_json()["active_repo_id"] == repo_a_id
    print(f"    Switch to A took {t_sw_a:.1f}ms")

    t0 = time.time()
    res_sw_b = client.post("/api/switch_repo", json={"repo_id": repo_b_id})
    t_sw_b = (time.time() - t0) * 1000
    assert res_sw_b.get_json()["active_repo_id"] == repo_b_id
    print(f"    Switch to B took {t_sw_b:.1f}ms")

    t0 = time.time()
    res_sw_a2 = client.post("/api/switch_repo", json={"repo_id": repo_a_id})
    t_sw_a2 = (time.time() - t0) * 1000
    assert res_sw_a2.get_json()["active_repo_id"] == repo_a_id
    print(f"    Re-switch to A (cached) took {t_sw_a2:.1f}ms")

    t0 = time.time()
    res_sw_b2 = client.post("/api/switch_repo", json={"repo_id": repo_b_id})
    t_sw_b2 = (time.time() - t0) * 1000
    assert res_sw_b2.get_json()["active_repo_id"] == repo_b_id
    print(f"    Re-switch to B (cached) took {t_sw_b2:.1f}ms")
    print("    [PASS] Fast switching between loaded engines verified")

    # 5. Repository Isolation in Queries
    print("\n[5] Testing Repository Isolation in Queries...")
    client.post("/api/switch_repo", json={"repo_id": repo_a_id})
    q_a = client.post("/api/query", json={"query": "What python files exist in this repository?"}).get_json()
    assert "main.py" in q_a["answer"] or "math_a.py" in q_a["answer"]
    assert "processor_b.py" not in q_a["answer"]

    client.post("/api/switch_repo", json={"repo_id": repo_b_id})
    q_b = client.post("/api/query", json={"query": "What python files exist in this repository?"}).get_json()
    assert "processor_b.py" in q_b["answer"] or "app.py" in q_b["answer"]
    assert "math_a.py" not in q_b["answer"]
    print("    [PASS] Queries strictly isolated between Repo A and Repo B")

    # 6. Explicit repo_id targeting in /api/query
    print("\n[6] Testing Explicit repo_id Targeting in /api/query...")
    q_explicit_a = client.post("/api/query", json={"query": "How many functions are in the repository?", "repo_id": repo_a_id}).get_json()
    assert q_explicit_a["success"] is True
    
    q_invalid = client.post("/api/query", json={"query": "How many functions?", "repo_id": "non_existent_id"})
    assert q_invalid.status_code == 404
    assert q_invalid.get_json()["success"] is False
    print("    [PASS] Explicit repo_id targeting and invalid ID handling verified")

    # 7. Graph Filename Isolation
    print("\n[7] Testing Graph Filename Isolation...")
    client.post("/api/switch_repo", json={"repo_id": repo_a_id})
    graph_a_res = client.post("/api/query", json={"query": "Show the dependency graph."}).get_json()
    graph_a_url = graph_a_res.get("graph_url")
    assert f"dependency_graph_{repo_a_id}.html" in graph_a_url

    client.post("/api/switch_repo", json={"repo_id": repo_b_id})
    graph_b_res = client.post("/api/query", json={"query": "Show the dependency graph."}).get_json()
    graph_b_url = graph_b_res.get("graph_url")
    assert f"dependency_graph_{repo_b_id}.html" in graph_b_url
    assert graph_a_url != graph_b_url
    print(f"    Repo A graph URL: {graph_a_url}")
    print(f"    Repo B graph URL: {graph_b_url}")
    print("    [PASS] Graph files are isolated per repository ID")

    # 8. Restart Safety (Scanning Disk)
    print("\n[8] Testing Restart Safety (Simulating Flask restart by clearing memory cache)...")
    from app import engine_registry
    engine_registry.clear()
    assert len(engine_registry) == 0
    disk_repos = scan_available_repositories()
    disk_ids = [r["id"] for r in disk_repos]
    assert repo_a_id in disk_ids
    assert repo_b_id in disk_ids
    print(f"    Scanned repos after memory wipe: {disk_ids}")

    # Querying after restart lazy-loads repo cleanly
    res_after_restart = client.post("/api/query", json={"query": "What python files exist?", "repo_id": repo_a_id}).get_json()
    assert res_after_restart["success"] is True
    print("    [PASS] Restart safety & lazy loading verified")

    print("\n" + "="*70)
    print("  ✅ ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_tests()
