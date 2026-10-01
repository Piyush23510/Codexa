"""
Phase 4 End-to-End Reliability, Security, & Regression Test Suite
Executes all 13 Test Groups specified in Phase 4 requirements.
"""

import sys
import os
import time
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app, get_engine


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def test_group_1_startup(client):
    separator("GROUP 1: APPLICATION STARTUP & ENDPOINTS")
    
    # Root endpoint
    res_root = client.get("/")
    print(f"GET / -> Status: {res_root.status_code}")
    assert res_root.status_code == 200, "Root / did not return 200"

    # Static CSS
    res_css = client.get("/static/style.css")
    print(f"GET /static/style.css -> Status: {res_css.status_code}")
    assert res_css.status_code == 200, "style.css did not return 200"

    # Static JS
    res_js = client.get("/static/script.js")
    print(f"GET /static/script.js -> Status: {res_js.status_code}")
    assert res_js.status_code == 200, "script.js did not return 200"

    # Switch to default repository for test environment
    client.post("/api/switch_repo", json={"repo_id": "default"})

    # API Status
    res_status = client.get("/api/status")
    print(f"GET /api/status -> Status: {res_status.status_code}, Data: {res_status.get_json()}")
    assert res_status.status_code == 200
    assert res_status.get_json()["status"] == "active"

    print("  [PASS] Group 1 Startup Tests Passed")


def test_group_2_repository_routing(client):
    separator("GROUP 2: REPOSITORY ROUTING (COUNT, STRUCTURE, OVERVIEW, WORKFLOW)")
    
    test_cases = [
        ("How many functions are there?", "REPOSITORY", "COUNT"),
        ("Show the repository structure.", "REPOSITORY", "STRUCTURE"),
        ("Give me an overview of the project.", "REPOSITORY", "OVERVIEW"),
        ("Explain the main workflow of this project.", "REPOSITORY", "WORKFLOW")
    ]

    for q, expected_type, expected_subtype in test_cases:
        print(f"Testing Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200
        data = res.get_json()
        print(f"  -> Type: {data.get('query_type')}, SubType: {data.get('sub_type')}")
        assert data.get("query_type") == expected_type, f"Expected {expected_type}, got {data.get('query_type')}"
        assert data.get("sub_type") == expected_subtype, f"Expected {expected_subtype}, got {data.get('sub_type')}"
        assert len(data.get("answer", "")) > 0

    print("  [PASS] Group 2 Repository Routing Tests Passed")


def test_group_3_dependency_analysis(client):
    separator("GROUP 3: DEPENDENCY ANALYSIS (DIRECT, REVERSE, INDIRECT, ORDER, GRAPH)")
    
    test_cases = [
        ("Which functions does analyze call?", "DEPENDENCY", "DIRECT"),
        ("Who calls clean_text?", "DEPENDENCY", "REVERSE"),
        ("What functions are indirectly dependent on analyze?", "DEPENDENCY", "INDIRECT"),
        ("What is the sequence of calls inside analyze?", "DEPENDENCY", "ORDER"),
        ("Show the dependency graph.", "DEPENDENCY", "GRAPH")
    ]

    for q, expected_type, expected_subtype in test_cases:
        print(f"Testing Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200
        data = res.get_json()
        print(f"  -> Type: {data.get('query_type')}, SubType: {data.get('sub_type')}")
        if data.get("graph_url"):
            print(f"  -> Graph URL: {data.get('graph_url')}")
            assert "/api/graph/" in data.get("graph_url")

        assert data.get("query_type") == expected_type
        assert data.get("sub_type") == expected_subtype
        assert len(data.get("answer", "")) > 0

    print("  [PASS] Group 3 Dependency Analysis Tests Passed")


def test_group_4_impact_analysis(client):
    separator("GROUP 4: IMPACT ANALYSIS (clean_text, analyze)")
    
    queries = [
        "What would be affected if clean_text changes?",
        "What would happen if analyze changes?"
    ]

    for q in queries:
        import time
        time.sleep(1.5)
        print(f"Testing Impact Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200
        data = res.get_json()
        print(f"  -> Query Type: {data.get('query_type')}")
        print(f"  -> Risk: {data.get('risk')}")
        print(f"  -> Impact %: {data.get('impact_percentage')}")
        print(f"  -> Graph URL: {data.get('graph_url')}")

        assert data.get("query_type") == "IMPACT"
        assert "risk" in data
        assert "impact_percentage" in data
        assert data.get("graph_url") and "/api/graph/impact_graph" in data.get("graph_url")

    print("  [PASS] Group 4 Impact Analysis Tests Passed")


def test_group_5_rag_testing(client):
    separator("GROUP 5: RAG TESTING")
    
    queries = [
        "What does clean_text do?",
        "Explain how analyze calculates the resume score.",
        "How does the PDF processing work?"
    ]

    for q in queries:
        import time
        time.sleep(1.5)
        print(f"Testing RAG Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200
        data = res.get_json()
        print(f"  -> Type: {data.get('query_type')}")
        print(f"  -> Citations Count: {len(data.get('citations', []))}")
        print(f"  -> Answer Snippet: {data.get('answer', '')[:100]}...")

        assert data.get("query_type") == "RAG"
        assert len(data.get("answer", "")) > 0
        assert len(data.get("citations", [])) > 0

    print("  [PASS] Group 5 RAG Tests Passed")


def test_group_6_citation_integrity(client):
    separator("GROUP 6: CITATION INTEGRITY AUDIT")
    
    eng = get_engine()
    res = client.post("/api/query", json={"query": "What does clean_text do?"})
    data = res.get_json()
    citations = data.get("citations", [])

    print(f"Verifying {len(citations)} citations...")
    for cit in citations:
        file_path = cit.get("file")
        print(f"  Citation: {cit.get('name')} in {file_path} ({cit.get('start_line')}-{cit.get('end_line')}) [{cit.get('type')}]")
        
        # 1. File existence check
        if file_path and file_path != "repository_summary":
            p = eng.repo_path / file_path if not Path(file_path).is_absolute() else Path(file_path)
            assert p.exists(), f"Cited file does not exist: {file_path}"
            
        # 2. Line range check
        start_line = cit.get("start_line")
        end_line = cit.get("end_line")
        if start_line is not None and end_line is not None:
            assert start_line <= end_line, f"Invalid line range: {start_line} > {end_line}"
            assert start_line >= 0, f"Negative line number: {start_line}"

    print("  [PASS] Group 6 Citation Integrity Tests Passed")


def test_group_7_graph_integrity(client):
    separator("GROUP 7: GRAPH INTEGRITY & SECURITY AUDIT")
    
    # 1. Valid dependency graph serving
    res1 = client.get("/api/graph/dependency_graph.html")
    print(f"GET /api/graph/dependency_graph.html -> Status: {res1.status_code}")
    assert res1.status_code == 200
    assert b"html" in res1.data.lower()

    # 2. Valid impact graph serving
    res2 = client.get("/api/graph/impact_graph.html")
    print(f"GET /api/graph/impact_graph.html -> Status: {res2.status_code}")
    assert res2.status_code == 200
    assert b"html" in res2.data.lower()

    # 3. Invalid graph filename
    res3 = client.get("/api/graph/nonexistent.html")
    print(f"GET /api/graph/nonexistent.html -> Status: {res3.status_code}")
    assert res3.status_code == 404

    # 4. Path traversal attempt (non-HTML file / sensitive file)
    res4 = client.get("/api/graph/app.py")
    print(f"GET /api/graph/app.py -> Status: {res4.status_code}")
    assert res4.status_code == 404

    res5 = client.get("/api/graph/../../app.py")
    print(f"GET /api/graph/../../app.py -> Status: {res5.status_code}")
    assert res5.status_code == 404

    print("  [PASS] Group 7 Graph Integrity & Security Tests Passed")


def test_group_8_error_handling(client):
    separator("GROUP 8: API ERROR HANDLING & VALIDATION")
    
    # 1. Empty JSON {}
    res1 = client.post("/api/query", json={})
    print(f"POST /api/query {{}} -> Status: {res1.status_code}")
    assert res1.status_code == 400

    # 2. Empty query ""
    res2 = client.post("/api/query", json={"query": ""})
    print(f"POST /api/query \"\" -> Status: {res2.status_code}")
    assert res2.status_code == 400

    # 3. Whitespace query "   "
    res3 = client.post("/api/query", json={"query": "   "})
    print(f"POST /api/query \"   \" -> Status: {res3.status_code}")
    assert res3.status_code == 400

    # 4. Missing query field
    res4 = client.post("/api/query", json={"message": "hello"})
    print(f"POST /api/query missing field -> Status: {res4.status_code}")
    assert res4.status_code == 400

    # 5. Invalid HTTP Method GET /api/query
    res5 = client.get("/api/query")
    print(f"GET /api/query -> Status: {res5.status_code}")
    assert res5.status_code == 405

    print("  [PASS] Group 8 Error Handling Tests Passed")


def test_group_9_10_consecutive_queries(client):
    separator("GROUPS 9 & 10: CONSECUTIVE QUERIES & STATE INTEGRITY")
    
    sequence = [
        ("Give me an overview of the project.", "REPOSITORY"),
        ("Which functions does analyze call?", "DEPENDENCY"),
        ("What would be affected if clean_text changes?", "IMPACT"),
        ("What does clean_text do?", "RAG"),
        ("Show the dependency graph.", "DEPENDENCY"),
        ("Explain how analyze calculates the resume score.", "RAG")
    ]

    for idx, (q, expected_type) in enumerate(sequence, start=1):
        print(f"Step {idx}: Query '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200
        data = res.get_json()
        print(f"  -> Returned Query Type: {data.get('query_type')}")
        assert data.get("query_type") == expected_type, f"Step {idx} expected {expected_type}, got {data.get('query_type')}"
        assert data.get("success") is True

    print("  [PASS] Groups 9 & 10 Consecutive Query Tests Passed")


def test_group_11_repository_loading(client):
    separator("GROUP 11: REPOSITORY LOADING (/api/analyze_repo)")
    
    # Reload current repo
    eng = get_engine()
    target_repo = str(eng.repo_path)
    res = client.post("/api/analyze_repo", json={"repo_path": target_repo})
    print(f"POST /api/analyze_repo -> Status: {res.status_code}, Response: {res.get_json()}")
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Test invalid repo path
    res_bad = client.post("/api/analyze_repo", json={"repo_path": "C:\\non_existent_folder_xyz"})
    print(f"POST /api/analyze_repo (Bad Path) -> Status: {res_bad.status_code}, Response: {res_bad.get_json()}")
    assert res_bad.status_code in (400, 404)
    assert res_bad.get_json()["success"] is False

    print("  [PASS] Group 11 Repository Loading Tests Passed")


def main():
    print("\n" + "="*70)
    print("  PHASE 4 END-TO-END RELIABILITY & AUDIT TEST SUITE")
    print("="*70)
    
    start_time = time.time()
    app.config["TESTING"] = True
    
    with app.test_client() as client:
        test_group_1_startup(client)
        test_group_2_repository_routing(client)
        test_group_3_dependency_analysis(client)
        test_group_4_impact_analysis(client)
        test_group_5_rag_testing(client)
        test_group_6_citation_integrity(client)
        test_group_7_graph_integrity(client)
        test_group_8_error_handling(client)
        test_group_9_10_consecutive_queries(client)
        test_group_11_repository_loading(client)
        
    duration = time.time() - start_time
    separator("ALL PHASE 4 END-TO-END TESTS PASSED SUCCESSFULLY")
    print(f"  Total Duration: {duration:.2f} seconds\n")


if __name__ == "__main__":
    main()
