"""
Phase 3 UI Verification Test Suite.
Verifies that index.html, static/style.css, and static/script.js load cleanly,
contain all required DOM elements, connect to the Flask APIs, and do not break backend functionality.
"""

import sys
import os
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def test_ui_routes(client):
    separator("1. VERIFY FRONTEND ROOT & STATIC ASSETS")
    
    # 1. Root route /
    res_root = client.get("/")
    print(f"GET / -> Status Code: {res_root.status_code}")
    assert res_root.status_code == 200, f"Expected 200 OK, got {res_root.status_code}"
    
    html_content = res_root.data.decode("utf-8")
    assert "AI Software Engineering Copilot" in html_content, "Missing title in index.html"
    assert 'id="repoNameBadge"' in html_content, "Missing repoNameBadge in index.html"
    assert 'id="queryInput"' in html_content, "Missing queryInput in index.html"
    assert 'id="sendBtn"' in html_content, "Missing sendBtn in index.html"
    assert 'id="clearBtn"' in html_content, "Missing clearBtn in index.html"
    assert 'id="answerContent"' in html_content, "Missing answerContent in index.html"
    assert 'id="citationsSection"' in html_content, "Missing citationsSection in index.html"
    assert 'id="graphSection"' in html_content, "Missing graphSection in index.html"
    assert 'id="historySection"' in html_content, "Missing historySection in index.html"
    assert 'id="historyContainer"' in html_content, "Missing historyContainer in index.html"
    assert 'id="errorCard"' in html_content, "Missing errorCard in index.html"
    print("  [PASS] index.html structure verified")

    # 2. Static CSS
    res_css = client.get("/static/style.css")
    print(f"GET /static/style.css -> Status Code: {res_css.status_code}, Length: {len(res_css.data)} bytes")
    assert res_css.status_code == 200, f"Expected 200 OK, got {res_css.status_code}"
    assert b"--bg-color" in res_css.data or b"body" in res_css.data, "CSS content invalid"
    assert b".clear-btn" in res_css.data, "Missing .clear-btn in CSS"
    assert b".history-section" in res_css.data, "Missing .history-section in CSS"
    print("  [PASS] static/style.css verified")

    # 3. Static JS
    res_js = client.get("/static/script.js")
    print(f"GET /static/script.js -> Status Code: {res_js.status_code}, Length: {len(res_js.data)} bytes")
    assert res_js.status_code == 200, f"Expected 200 OK, got {res_js.status_code}"
    assert b"handleQuerySubmit" in res_js.data or b"fetchRepoStatus" in res_js.data, "JS content invalid"
    assert b"addToHistory" in res_js.data, "Missing addToHistory in JS"
    print("  [PASS] static/script.js verified")


def test_api_integration_for_ui(client):
    separator("2. VERIFY BACKEND API COMPATIBILITY FOR UI")
    
    # 1. /api/status for repository info card
    res_status = client.get("/api/status")
    print(f"GET /api/status -> Status: {res_status.status_code}")
    assert res_status.status_code == 200
    data_status = res_status.get_json()
    assert "project_name" in data_status
    assert "total_files" in data_status
    assert "total_functions" in data_status
    print("  [PASS] /api/status produces data required by repo info banner")

    # 2. Oversized query (>2000 chars) rejection
    res_oversized = client.post("/api/query", json={"query": "A" * 2005})
    print(f"POST /api/query (2005 chars) -> Status: {res_oversized.status_code}")
    assert res_oversized.status_code == 400
    assert "exceeds maximum allowed length" in res_oversized.get_json().get("error", "")
    print("  [PASS] Query > 2000 chars rejected with HTTP 400")

    # 3. Irrelevant query grounded fallback
    res_irrelevant = client.post("/api/query", json={"query": "What is the recipe for baking chocolate cake?"})
    print(f"POST /api/query (Irrelevant) -> Status: {res_irrelevant.status_code}")
    assert res_irrelevant.status_code == 200
    d_irr = res_irrelevant.get_json()
    assert "No relevant code context found" in d_irr.get("answer", "")
    print("  [PASS] Irrelevant query triggers grounded fallback response")

    # 4. /api/query for repository overview query
    res_q1 = client.post("/api/query", json={"query": "Give me an overview of the project."})
    print(f"POST /api/query (Overview) -> Status: {res_q1.status_code}")
    assert res_q1.status_code == 200
    d1 = res_q1.get_json()
    assert d1.get("query_type") == "REPOSITORY"
    assert d1.get("sub_type") == "OVERVIEW"
    print("  [PASS] REPOSITORY query works")

    # 5. /api/query for dependency graph query
    res_q2 = client.post("/api/query", json={"query": "Show the dependency graph."})
    print(f"POST /api/query (Dependency Graph) -> Status: {res_q2.status_code}")
    assert res_q2.status_code == 200
    d2 = res_q2.get_json()
    assert d2.get("query_type") == "DEPENDENCY"
    assert d2.get("graph_url") and "/api/graph/dependency_graph" in d2.get("graph_url")
    print("  [PASS] DEPENDENCY query works with graph_url")

    # 6. /api/query for impact query
    res_q3 = client.post("/api/query", json={"query": "What would be affected if clean_text changes?"})
    print(f"POST /api/query (Impact Analysis) -> Status: {res_q3.status_code}")
    assert res_q3.status_code == 200
    d3 = res_q3.get_json()
    assert d3.get("query_type") == "IMPACT"
    assert "risk" in d3
    assert "impact_percentage" in d3
    assert d3.get("graph_url") and "/api/graph/impact_graph" in d3.get("graph_url")
    print("  [PASS] IMPACT query works with risk, impact_percentage & graph_url")

    # 7. /api/query for RAG query
    res_q4 = client.post("/api/query", json={"query": "What does clean_text do?"})
    print(f"POST /api/query (RAG) -> Status: {res_q4.status_code}")
    assert res_q4.status_code == 200
    d4 = res_q4.get_json()
    assert d4.get("query_type") == "RAG"
    assert len(d4.get("citations", [])) > 0
    print("  [PASS] RAG query works with citations")


def main():
    print("\n" + "="*70)
    print("  PHASE 3 WEB UI VERIFICATION TEST SUITE")
    print("="*70)
    
    app.config["TESTING"] = True
    with app.test_client() as client:
        test_ui_routes(client)
        test_api_integration_for_ui(client)
        
    separator("ALL PHASE 3 UI TESTS PASSED SUCCESSFULLY")
    print("  Phase 3 Web UI implementation is complete and verified.\n")


if __name__ == "__main__":
    main()
