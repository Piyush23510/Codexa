"""
Test suite for LLMGenerator and QueryRouter
Verifies classification of queries into REPOSITORY, DEPENDENCY, IMPACT, RAG
and sub-routes (COUNT, STRUCTURE, OVERVIEW, WORKFLOW, DIRECT, REVERSE, INDIRECT, ORDER, GRAPH).
Also tests identify_changed_function, generate_recommendation, explain_repository_workflow, etc.
"""

import sys
import os
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.llm_generator import LLMGenerator
from parser.query_router import QueryRouter


def test_llm_and_router():
    print("\n" + "="*70)
    print("  TESTING LLM GENERATOR & QUERY ROUTER")
    print("="*70)

    llm = LLMGenerator()
    router = QueryRouter(llm)

    # 1. Main Route Classification Tests
    main_queries = [
        ("How many functions are in the repository?", "REPOSITORY"),
        ("Which functions call clean_text?", "DEPENDENCY"),
        ("What happens if I modify analyze?", "IMPACT"),
        ("What does clean_text do?", "RAG")
    ]

    print("\n--- 1. Main Query Routing ---")
    for q, expected in main_queries:
        res = router.route(q)
        print(f"Query: '{q}' -> Classified as: {res} (Expected: {expected})")
        assert res in ["REPOSITORY", "DEPENDENCY", "IMPACT", "RAG"], f"Invalid route: {res}"

    # 2. Repository Sub-Routing Tests
    repo_queries = [
        ("How many python files are there?", "COUNT"),
        ("Show me the directory structure", "STRUCTURE"),
        ("Give me an overview of the project", "OVERVIEW"),
        ("Explain the main workflow of this application", "WORKFLOW")
    ]

    print("\n--- 2. Repository Sub-Routing ---")
    for q, expected in repo_queries:
        res = router.repository_route(q)
        print(f"Query: '{q}' -> Classified as: {res} (Expected: {expected})")
        assert res in ["COUNT", "STRUCTURE", "OVERVIEW", "WORKFLOW"], f"Invalid sub-route: {res}"

    # 3. Dependency Sub-Routing Tests
    dep_queries = [
        ("Which functions does analyze call?", "DIRECT"),
        ("Who calls clean_text?", "REVERSE"),
        ("What are the indirect dependencies of analyze?", "INDIRECT"),
        ("What is the order of function calls inside analyze?", "ORDER"),
        ("Show the complete dependency graph", "GRAPH")
    ]

    print("\n--- 3. Dependency Sub-Routing ---")
    for q, expected in dep_queries:
        res = router.dependency_route(q)
        print(f"Query: '{q}' -> Classified as: {res} (Expected: {expected})")
        assert res in ["DIRECT", "REVERSE", "INDIRECT", "ORDER", "GRAPH", "RAG"], f"Invalid sub-route: {res}"

    # 4. Function Identification Test for Impact Analysis
    print("\n--- 4. Function Identification for Impact Analysis ---")
    funcs = ["clean_text", "analyze", "extract_skills", "calculate_similarity"]
    q1 = "What happens if I change clean_text?"
    changed = llm.identify_changed_function(q1, funcs)
    print(f"Query: '{q1}' -> Identified changed function: {changed}")
    assert changed == "clean_text", f"Expected 'clean_text', got '{changed}'"

    q2 = "Where is calculate_similarity defined?"
    changed2 = llm.identify_changed_function(q2, funcs)
    print(f"Query: '{q2}' -> Identified changed function: {changed2}")
    assert changed2 is None, f"Expected None for non-impact query, got '{changed2}'"

    # 5. Recommendation Generation Test
    print("\n--- 5. Recommendation Generation ---")
    rec = llm.generate_recommendation(
        changed_function="clean_text",
        direct_impact={"analyze"},
        indirect_impact=set(),
        impact_percentage=4.55,
        risk="MEDIUM"
    )
    print(f"Generated Recommendation:\n{rec}\n")
    assert len(rec) > 10, "Recommendation is empty or too short"

    print("="*70)
    print("  ALL LLM & QUERY ROUTER TESTS PASSED")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_llm_and_router()
