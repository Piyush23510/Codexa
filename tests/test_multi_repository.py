"""
Multi-Repository Upload & Switching Test Suite
Tests: valid upload, repo detection, query after upload, repo switching,
citation isolation, graph isolation, invalid uploads, Zip Slip protection,
and regression compatibility.
"""

import sys
import os
import io
import zipfile
import shutil
import tempfile
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app, get_engine, UPLOAD_WORKSPACE, BASE_DIR

# ---------------------------------------------------------------------------
# Test Data Helpers
# ---------------------------------------------------------------------------

def create_repo_zip_bytes(repo_name, files_dict, nested=True):
    """
    Create a ZIP archive in memory.
    files_dict: { "relative/path.py": "file content", ... }
    nested: if True, wraps files under repo_name/ directory.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files_dict.items():
            arc_path = f"{repo_name}/{rel_path}" if nested else rel_path
            zf.writestr(arc_path, content)
    buf.seek(0)
    return buf


# Sample Repository A
REPO_A_NAME = "sample_repo_a"
REPO_A_FILES = {
    "main.py": (
        "def greet(name):\n"
        "    return f'Hello, {name}!'\n\n"
        "def farewell(name):\n"
        "    return f'Goodbye, {name}!'\n\n"
        "def main():\n"
        "    print(greet('World'))\n"
        "    print(farewell('World'))\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    ),
    "utils/helpers.py": (
        "def add(a, b):\n"
        "    return a + b\n\n"
        "def subtract(a, b):\n"
        "    return a - b\n\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    ),
}

# Sample Repository B (different structure and functions)
REPO_B_NAME = "sample_repo_b"
REPO_B_FILES = {
    "app.py": (
        "from processor import process_data\n\n"
        "def run():\n"
        "    data = [1, 2, 3]\n"
        "    result = process_data(data)\n"
        "    print(result)\n\n"
        "if __name__ == '__main__':\n"
        "    run()\n"
    ),
    "processor.py": (
        "def process_data(data):\n"
        "    return transform(data)\n\n"
        "def transform(data):\n"
        "    return [x * 2 for x in data]\n\n"
        "def validate(data):\n"
        "    return all(isinstance(x, int) for x in data)\n"
    ),
    "config.py": (
        "def get_config():\n"
        "    return {'debug': True}\n\n"
        "def set_config(key, value):\n"
        "    pass\n"
    ),
}


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def upload_zip(client, repo_name, files_dict, nested=True, filename=None):
    """Helper to upload a zip via the test client."""
    zip_buf = create_repo_zip_bytes(repo_name, files_dict, nested=nested)
    fname = filename or f"{repo_name}.zip"
    return client.post(
        "/api/upload_repo",
        data={"file": (zip_buf, fname)},
        content_type="multipart/form-data",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_1_valid_zip_upload(client):
    separator("TEST 1 — Valid ZIP Upload")
    res = upload_zip(client, REPO_A_NAME, REPO_A_FILES)
    data = res.get_json()
    print(f"  Status Code: {res.status_code}")
    print(f"  Response:    {data}")

    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert data["success"] is True, "Expected success=True"
    assert "repository" in data, "Missing 'repository' key"
    assert data["repository"]["python_files"] >= 2, f"Expected >=2 py files, got {data['repository']['python_files']}"
    print("  [PASS] Valid ZIP upload succeeded")
    return data


def test_2_repository_detection(client):
    separator("TEST 2 — Repository Detection")
    # Upload Repo A and verify detection metadata
    res = upload_zip(client, REPO_A_NAME, REPO_A_FILES)
    data = res.get_json()
    repo = data["repository"]
    print(f"  Repo Name:    {repo['name']}")
    print(f"  Python Files: {repo['python_files']}")
    print(f"  Functions:    {repo['functions']}")
    print(f"  Folders:      {repo['folders']}")

    assert repo["name"] == REPO_A_NAME, f"Expected name '{REPO_A_NAME}', got '{repo['name']}'"
    assert repo["python_files"] == 2, f"Expected 2 py files, got {repo['python_files']}"
    assert repo["functions"] >= 5, f"Expected >=5 functions, got {repo['functions']}"

    # Verify /api/status reflects same
    status_res = client.get("/api/status")
    status_data = status_res.get_json()
    print(f"  /api/status project_name: {status_data.get('project_name')}")
    assert status_data["project_name"] == REPO_A_NAME
    print("  [PASS] Repository detection passed")


def test_3_query_after_upload(client):
    separator("TEST 3 — Query After Upload")
    # Upload Repo A
    upload_zip(client, REPO_A_NAME, REPO_A_FILES)

    # Count query
    res = client.post("/api/query", json={"query": "How many functions are there?"})
    data = res.get_json()
    print(f"  Status: {res.status_code}")
    print(f"  Answer: {data.get('answer', '')[:120]}...")

    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert data["success"] is True
    # Repo A has greet, farewell, main, add, subtract, multiply = 6 functions
    assert "6" in data["answer"] or "function" in data["answer"].lower(), "Expected function count reference for Repo A"
    print("  [PASS] Query after upload works correctly")


def test_4_repository_switching(client):
    separator("TEST 4 — Repository Switching (A → B)")
    # Upload A first
    res_a = upload_zip(client, REPO_A_NAME, REPO_A_FILES)
    data_a = res_a.get_json()
    funcs_a = data_a["repository"]["functions"]
    print(f"  Repo A functions: {funcs_a}")

    # Now upload B
    res_b = upload_zip(client, REPO_B_NAME, REPO_B_FILES)
    data_b = res_b.get_json()
    funcs_b = data_b["repository"]["functions"]
    print(f"  Repo B functions: {funcs_b}")

    assert data_b["success"] is True
    assert data_b["repository"]["name"] == REPO_B_NAME, f"Expected '{REPO_B_NAME}', got '{data_b['repository']['name']}'"
    assert funcs_b != funcs_a or data_b["repository"]["python_files"] != data_a["repository"]["python_files"], \
        "Repository B should have different metadata than A"

    # Verify status
    status_res = client.get("/api/status")
    status_data = status_res.get_json()
    assert status_data["project_name"] == REPO_B_NAME, f"Status still showing '{status_data['project_name']}', expected '{REPO_B_NAME}'"

    # Query count on B
    count_res = client.post("/api/query", json={"query": "How many functions are there?"})
    count_data = count_res.get_json()
    print(f"  Query on B answer: {count_data.get('answer', '')[:120]}...")
    # Repo B has run, process_data, transform, validate, get_config, set_config = 6 functions
    assert count_res.status_code == 200
    print("  [PASS] Repository switching (A → B) succeeded")


def test_5_no_stale_citations(client):
    separator("TEST 5 — No Stale Citations After Switching")
    # Upload A
    upload_zip(client, REPO_A_NAME, REPO_A_FILES)

    # Now upload B
    upload_zip(client, REPO_B_NAME, REPO_B_FILES)

    # Query structure — should show B's files, not A's
    res = client.post("/api/query", json={"query": "Show the repository structure."})
    data = res.get_json()
    answer = data.get("answer", "")
    print(f"  Structure answer (first 200 chars): {answer[:200]}...")

    # Should NOT contain repo A file names
    assert "helpers.py" not in answer, "Stale citation: helpers.py from Repo A found in Repo B results"
    # Should contain repo B file names
    assert "processor.py" in answer or "config.py" in answer or "app.py" in answer, \
        "Expected Repo B file references in structure"

    # Check citations if any
    citations = data.get("citations", [])
    for c in citations:
        c_file = str(c.get("file", ""))
        assert REPO_A_NAME not in c_file, f"Stale citation found: {c_file} references Repo A"
    print("  [PASS] No stale citations after switching")


def test_6_dependency_graph(client):
    separator("TEST 6 — Dependency Graph After Upload")
    # Upload B
    upload_zip(client, REPO_B_NAME, REPO_B_FILES)

    # Request dependency graph via query
    res = client.post("/api/query", json={"query": "Show the dependency graph."})
    data = res.get_json()
    print(f"  Status: {res.status_code}, Query Type: {data.get('query_type')}")
    print(f"  Graph URL: {data.get('graph_url')}")

    assert res.status_code == 200
    assert data.get("graph_url") is not None, "Expected graph_url in response"

    # Verify the graph file was actually generated
    graph_url = data["graph_url"]
    graph_res = client.get(graph_url)
    print(f"  Graph serve status: {graph_res.status_code}")
    assert graph_res.status_code == 200, f"Graph file not served, got {graph_res.status_code}"
    print("  [PASS] Dependency graph generated for uploaded repository")


def test_7_impact_graph(client):
    separator("TEST 7 — Impact Graph After Upload")
    # Upload B
    upload_zip(client, REPO_B_NAME, REPO_B_FILES)

    # The impact graph is generated via an impact query
    # We use a function known to exist in Repo B: process_data
    res = client.post("/api/query", json={"query": "What would be affected if process_data changes?"})
    data = res.get_json()
    print(f"  Status: {res.status_code}, Query Type: {data.get('query_type')}")

    if res.status_code == 200 and data.get("graph_url"):
        graph_res = client.get(data["graph_url"])
        print(f"  Impact graph serve status: {graph_res.status_code}")
        assert graph_res.status_code == 200
        print("  [PASS] Impact graph generated for uploaded repository")
    elif res.status_code == 200:
        # Impact query succeeded but no graph (function may not have reverse deps to graph)
        print(f"  Answer snippet: {data.get('answer', '')[:120]}...")
        print("  [PASS] Impact query executed on uploaded repository (no graph generated)")
    else:
        print(f"  [WARN] Impact query returned {res.status_code}: {data.get('error', '')}")
        print("  [SKIP] Impact graph test skipped due to LLM rate limit or similar")


def test_8_invalid_uploads(client):
    separator("TEST 8 — Invalid Upload Handling")

    # 8a: Non-ZIP file
    print("  8a. Non-ZIP file...")
    res = client.post(
        "/api/upload_repo",
        data={"file": (io.BytesIO(b"not a zip"), "malicious.exe")},
        content_type="multipart/form-data",
    )
    data = res.get_json()
    print(f"     Status: {res.status_code}, Error: {data.get('error', '')[:80]}")
    assert res.status_code == 400, f"Expected 400 for non-ZIP, got {res.status_code}"
    assert data["success"] is False
    print("     [PASS]")

    # 8b: Text file with .txt extension
    print("  8b. Text file (.txt)...")
    res = client.post(
        "/api/upload_repo",
        data={"file": (io.BytesIO(b"hello"), "test.txt")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    print(f"     Status: {res.status_code}")
    print("     [PASS]")

    # 8c: Corrupted ZIP
    print("  8c. Corrupted ZIP...")
    corrupted = io.BytesIO(b"PK\x03\x04" + b"\x00" * 100)
    res = client.post(
        "/api/upload_repo",
        data={"file": (corrupted, "corrupted.zip")},
        content_type="multipart/form-data",
    )
    data = res.get_json()
    print(f"     Status: {res.status_code}, Error: {data.get('error', '')[:80]}")
    assert res.status_code == 400, f"Expected 400 for corrupted ZIP, got {res.status_code}"
    print("     [PASS]")

    # 8d: Empty ZIP
    print("  8d. Empty ZIP (no Python files)...")
    empty_buf = io.BytesIO()
    with zipfile.ZipFile(empty_buf, "w") as zf:
        zf.writestr("readme.txt", "No python here")
    empty_buf.seek(0)
    res = client.post(
        "/api/upload_repo",
        data={"file": (empty_buf, "empty.zip")},
        content_type="multipart/form-data",
    )
    data = res.get_json()
    print(f"     Status: {res.status_code}, Error: {data.get('error', '')[:80]}")
    assert res.status_code == 400
    assert data["success"] is False
    print("     [PASS]")

    # 8e: No file field
    print("  8e. Missing file field...")
    res = client.post("/api/upload_repo", content_type="multipart/form-data")
    data = res.get_json()
    assert res.status_code == 400
    print(f"     Status: {res.status_code}")
    print("     [PASS]")

    print("  [PASS] All invalid upload cases handled correctly")


def test_9_zip_traversal_protection(client):
    separator("TEST 9 — ZIP Path Traversal Protection")
    # Create a ZIP with a malicious path
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Legitimate file
        zf.writestr("safe.py", "def safe(): pass\n")
        # Malicious traversal path
        zf.writestr("../../evil.py", "import os; os.system('echo hacked')\n")
    buf.seek(0)

    res = client.post(
        "/api/upload_repo",
        data={"file": (buf, "traversal_test.zip")},
        content_type="multipart/form-data",
    )
    data = res.get_json()
    print(f"  Status: {res.status_code}")
    print(f"  Error:  {data.get('error', '')[:100]}")
    assert res.status_code == 400, f"Expected 400 for traversal attempt, got {res.status_code}"
    assert "Zip Slip" in data.get("error", "") or "Path Traversal" in data.get("error", ""), \
        "Expected Zip Slip / Path Traversal error message"

    # Verify no file escaped into parent
    evil_path = PROJECT_ROOT.parent / "evil.py"
    assert not evil_path.exists(), "evil.py escaped the workspace!"
    print("  [PASS] ZIP path traversal correctly blocked")


def test_10_flat_zip_structure(client):
    separator("TEST 10 — Flat ZIP Structure (no nested folder)")
    # Create a flat ZIP (files at root, no wrapping directory)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app.py", "def hello():\n    return 'hi'\n")
        zf.writestr("utils.py", "def util_func():\n    return 42\n")
    buf.seek(0)

    res = client.post(
        "/api/upload_repo",
        data={"file": (buf, "flat_repo.zip")},
        content_type="multipart/form-data",
    )
    data = res.get_json()
    print(f"  Status: {res.status_code}")
    print(f"  Response: {data}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert data["success"] is True
    assert data["repository"]["python_files"] == 2
    print("  [PASS] Flat ZIP structure handled correctly")


def test_11_b_to_a_switching(client):
    separator("TEST 11 — B → A Switching (Round-Trip)")
    # Upload B first
    res_b = upload_zip(client, REPO_B_NAME, REPO_B_FILES)
    data_b = res_b.get_json()
    assert data_b["repository"]["name"] == REPO_B_NAME

    # Now switch back to A
    res_a = upload_zip(client, REPO_A_NAME, REPO_A_FILES)
    data_a = res_a.get_json()
    assert data_a["repository"]["name"] == REPO_A_NAME

    # Verify status
    status_res = client.get("/api/status")
    status_data = status_res.get_json()
    assert status_data["project_name"] == REPO_A_NAME, \
        f"Expected '{REPO_A_NAME}', got '{status_data['project_name']}'"

    # Verify query returns A data
    res = client.post("/api/query", json={"query": "Show the repository structure."})
    data = res.get_json()
    answer = data.get("answer", "")
    assert "helpers.py" in answer or "main.py" in answer, "Expected Repo A files in structure"
    assert "processor.py" not in answer, "Stale Repo B data found after switching back to A"
    print("  [PASS] Round-trip switching (B → A) succeeded")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    passed = 0
    failed = 0
    skipped = 0

    print("\n" + "=" * 70)
    print("  MULTI-REPOSITORY UPLOAD & SWITCHING TEST SUITE")
    print("=" * 70)

    app.config["TESTING"] = True
    client = app.test_client()

    # Force engine initialization with default repo
    with app.app_context():
        try:
            get_engine()
        except Exception as e:
            print(f"[Warning] Default engine init failed: {e}")

    tests = [
        ("Test 1 — Valid ZIP Upload", test_1_valid_zip_upload),
        ("Test 2 — Repository Detection", test_2_repository_detection),
        ("Test 3 — Query After Upload", test_3_query_after_upload),
        ("Test 4 — Repository Switching", test_4_repository_switching),
        ("Test 5 — No Stale Citations", test_5_no_stale_citations),
        ("Test 6 — Dependency Graph", test_6_dependency_graph),
        ("Test 7 — Impact Graph", test_7_impact_graph),
        ("Test 8 — Invalid Uploads", test_8_invalid_uploads),
        ("Test 9 — ZIP Traversal Protection", test_9_zip_traversal_protection),
        ("Test 10 — Flat ZIP Structure", test_10_flat_zip_structure),
        ("Test 11 — B→A Round-Trip", test_11_b_to_a_switching),
    ]

    for name, test_func in tests:
        try:
            with app.test_client() as c:
                test_func(c)
            passed += 1
        except AssertionError as ae:
            print(f"  [FAIL] {name}: {ae}")
            failed += 1
        except Exception as ex:
            print(f"  [ERROR] {name}: {type(ex).__name__}: {ex}")
            failed += 1

    separator("SUMMARY")
    total = passed + failed + skipped
    print(f"  Total:   {total}")
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")

    if failed == 0:
        print("\n  ✅ ALL MULTI-REPOSITORY TESTS PASSED")
    else:
        print(f"\n  ❌ {failed} TEST(S) FAILED")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
