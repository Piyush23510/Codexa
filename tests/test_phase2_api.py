"""
Phase 2 API Test Suite for AI Software Engineering Copilot.
Tests Flask endpoints: /api/status, /api/query, /api/graph/<graph_name>, error handling,
and graph artifact serving using Flask's test client.
"""

import sys
import os
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


def test_api_status(client):
    separator("1. TEST /api/status ENDPOINT")
    res = client.get("/api/status")
    print(f"Status Code: {res.status_code}")
    data = res.get_json()
    print(f"Response Payload: {data}")
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert data.get("success") is True, "Expected success=True"
    assert data.get("status") == "active", "Expected status=active"
    assert "project_name" in data, "Missing project_name"
    assert "total_functions" in data, "Missing total_functions"
    print("  [PASS] /api/status test passed")


def test_api_error_handling(client):
    separator("2. TEST API ERROR HANDLING & VALIDATION")
    
    # 1. Empty payload
    res1 = client.post("/api/query", json={})
    print(f"Empty Payload -> Status: {res1.status_code}, Response: {res1.get_json()}")
    assert res1.status_code == 400
    assert res1.get_json()["success"] is False

    # 2. Empty string query
    res2 = client.post("/api/query", json={"query": "   "})
    print(f"Whitespace Query -> Status: {res2.status_code}, Response: {res2.get_json()}")
    assert res2.status_code == 400
    assert res2.get_json()["success"] is False

    # 3. Nonexistent graph file
    res3 = client.get("/api/graph/nonexistent_file.html")
    print(f"Nonexistent Graph -> Status: {res3.status_code}, Response: {res3.get_json()}")
    assert res3.status_code == 404
    assert res3.get_json()["success"] is False

    # 4. Path traversal attempt
    res4 = client.get("/api/graph/../../app.py")
    print(f"Path Traversal Attempt -> Status: {res4.status_code}, Response: {res4.get_json()}")
    assert res4.status_code == 404

    print("  [PASS] API error handling tests passed")


def test_repository_queries(client):
    separator("3. TEST REPOSITORY API QUERIES")
    queries = [
        ("How many functions are there?", "REPOSITORY", "COUNT"),
        ("Show the repository structure.", "REPOSITORY", "STRUCTURE"),
        ("Give me an overview of the project.", "REPOSITORY", "OVERVIEW"),
        ("Explain the main workflow of this project.", "REPOSITORY", "WORKFLOW")
    ]
    
    for q, expected_type, expected_subtype in queries:
        print(f"\nPosting Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200, f"Query '{q}' returned status {res.status_code}"
        data = res.get_json()
        
        print(f"  Success    : {data.get('success')}")
        print(f"  Query Type : {data.get('query_type')}")
        print(f"  Sub Type   : {data.get('sub_type')}")
        print(f"  Answer Snippet: {data.get('answer', '')[:100]}...")
        
        assert data.get("success") is True, f"Failed for query '{q}'"
        assert data.get("query_type") == expected_type, f"Expected {expected_type}, got {data.get('query_type')}"
        assert data.get("sub_type") == expected_subtype, f"Expected {expected_subtype}, got {data.get('sub_type')}"
        assert len(data.get("answer", "")) > 0, "Answer is empty"
        
    print("  [PASS] All repository queries passed")


def test_dependency_queries(client):
    separator("4. TEST DEPENDENCY API QUERIES")
    queries = [
        ("Which functions does analyze call?", "DEPENDENCY", "DIRECT"),
        ("Who calls clean_text?", "DEPENDENCY", "REVERSE"),
        ("What functions are indirectly dependent on analyze?", "DEPENDENCY", "INDIRECT"),
        ("What is the sequence of calls inside analyze?", "DEPENDENCY", "ORDER"),
        ("Show the dependency graph.", "DEPENDENCY", "GRAPH")
    ]
    
    for q, expected_type, expected_subtype in queries:
        print(f"\nPosting Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200, f"Query '{q}' returned status {res.status_code}"
        data = res.get_json()
        
        print(f"  Success    : {data.get('success')}")
        print(f"  Query Type : {data.get('query_type')}")
        print(f"  Sub Type   : {data.get('sub_type')}")
        if data.get("graph_url"):
            print(f"  Graph URL  : {data.get('graph_url')}")
            assert "/api/graph/" in data.get("graph_url"), f"Invalid graph URL format: {data.get('graph_url')}"
        print(f"  Answer Snippet: {data.get('answer', '')[:100]}...")
        
        assert data.get("success") is True, f"Failed for query '{q}'"
        assert data.get("query_type") == expected_type, f"Expected {expected_type}, got {data.get('query_type')}"
        assert data.get("sub_type") == expected_subtype, f"Expected {expected_subtype}, got {data.get('sub_type')}"
        assert len(data.get("answer", "")) > 0, "Answer is empty"

    print("  [PASS] All dependency queries passed")


def test_impact_queries(client):
    separator("5. TEST IMPACT ANALYSIS API QUERIES")
    queries = [
        "What would be affected if clean_text changes?",
        "What is the impact of changing analyze?"
    ]
    
    for q in queries:
        import time
        time.sleep(2)
        print(f"\nPosting Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200, f"Query '{q}' returned status {res.status_code}"
        data = res.get_json()
        
        print(f"  Success    : {data.get('success')}")
        print(f"  Query Type : {data.get('query_type')}")
        print(f"  Risk Level : {data.get('risk')}")
        print(f"  Impact %   : {data.get('impact_percentage')}")
        print(f"  Graph URL  : {data.get('graph_url')}")
        print(f"  Citations  : {len(data.get('citations', []))} citations")
        print(f"  Answer Snippet: {data.get('answer', '')[:120]}...")
        
        assert data.get("success") is True, f"Failed for query '{q}'"
        assert data.get("query_type") == "IMPACT", f"Expected IMPACT, got {data.get('query_type')}"
        assert "risk" in data, "Missing risk metric in impact response"
        assert "impact_percentage" in data, "Missing impact_percentage in impact response"
        assert data.get("graph_url") and "/api/graph/impact_graph" in data.get("graph_url"), "Invalid impact graph URL"

    print("  [PASS] All impact queries passed")


def test_rag_queries(client):
    separator("6. TEST RAG API QUERIES")
    queries = [
        "What does clean_text do?",
        "Explain how analyze calculates the resume score."
    ]
    
    for q in queries:
        print(f"\nPosting Query: '{q}'")
        res = client.post("/api/query", json={"query": q})
        assert res.status_code == 200, f"Query '{q}' returned status {res.status_code}"
        data = res.get_json()
        
        print(f"  Success    : {data.get('success')}")
        print(f"  Query Type : {data.get('query_type')}")
        print(f"  Citations  : {len(data.get('citations', []))} citations")
        print(f"  Answer Snippet: {data.get('answer', '')[:120]}...")
        
        assert data.get("success") is True, f"Failed for query '{q}'"
        assert data.get("query_type") == "RAG", f"Expected RAG, got {data.get('query_type')}"
        assert len(data.get("answer", "")) > 0, "Answer is empty"
        assert len(data.get("citations", [])) > 0, "Expected citations for RAG query"

    print("  [PASS] All RAG queries passed")


def test_graph_serving(client):
    separator("7. TEST GRAPH FILE SERVING (/api/graph/<graph_name>)")
    
    # Test serving generated dependency graph
    res1 = client.get("/api/graph/dependency_graph.html")
    print(f"Fetch /api/graph/dependency_graph.html -> Status: {res1.status_code}, Length: {len(res1.data)} bytes")
    assert res1.status_code == 200, f"Expected 200 for dependency_graph.html, got {res1.status_code}"
    assert b"vis-network" in res1.data or b"html" in res1.data.lower(), "Content is not valid HTML graph"

    # Test serving generated impact graph
    res2 = client.get("/api/graph/impact_graph.html")
    print(f"Fetch /api/graph/impact_graph.html -> Status: {res2.status_code}, Length: {len(res2.data)} bytes")
    assert res2.status_code == 200, f"Expected 200 for impact_graph.html, got {res2.status_code}"
    assert b"vis-network" in res2.data or b"html" in res2.data.lower(), "Content is not valid HTML graph"

    print("  [PASS] Graph file serving tests passed")


def main():
    print("\n" + "="*70)
    print("  PHASE 2 - FLASK BACKEND API TEST SUITE")
    print("="*70)
    
    app.config["TESTING"] = True
    with app.test_client() as client:
        test_api_status(client)
        test_api_error_handling(client)
        test_repository_queries(client)
        test_dependency_queries(client)
        test_impact_queries(client)
        test_rag_queries(client)
        test_graph_serving(client)

    separator("ALL PHASE 2 API TESTS PASSED SUCCESSFULLY")
    print("  Backend API integration is 100% complete and verified.\n")


if __name__ == "__main__":
    main()
