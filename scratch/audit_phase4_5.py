"""
Phase 4.5 Audit Script
Tests natural query variations against QueryRouter and CopilotEngine 
to gather empirical evidence for the Functional & UI Audit.
"""

import sys
import os
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app, get_engine


def audit_query_variations():
    eng = get_engine()
    
    variations = [
        # REVERSE DEPENDENCY VARIATIONS
        ("Who calls clean_text?", "DEPENDENCY", "REVERSE"),
        ("Who uses clean_text?", "DEPENDENCY", "REVERSE"),
        ("Which functions depend on clean_text?", "DEPENDENCY", "REVERSE"),
        ("Where is clean_text used?", "DEPENDENCY", "REVERSE"),

        # DIRECT DEPENDENCY VARIATIONS
        ("Which functions does analyze call?", "DEPENDENCY", "DIRECT"),
        ("What does analyze call?", "DEPENDENCY", "DIRECT"),
        ("Show me analyze's direct dependencies.", "DEPENDENCY", "DIRECT"),

        # IMPACT VARIATIONS
        ("What happens if clean_text changes?", "IMPACT", "IMPACT"),
        ("What would be affected by modifying clean_text?", "IMPACT", "IMPACT"),
        ("Which functions could be impacted if clean_text is changed?", "IMPACT", "IMPACT"),

        # REPOSITORY VARIATIONS
        ("How many functions are in this project?", "REPOSITORY", "COUNT"),
        ("Show me all files in the project.", "REPOSITORY", "STRUCTURE"),
        ("Summarize the codebase.", "REPOSITORY", "OVERVIEW"),
        ("How does execution flow from start to finish?", "REPOSITORY", "WORKFLOW"),

        # RAG VARIATIONS
        ("What does clean_text do?", "RAG", "RAG"),
        ("Explain the implementation of clean_text.", "RAG", "RAG"),
        ("How does analyze calculate the resume score?", "RAG", "RAG")
    ]

    print("\n" + "="*70)
    print("  PHASE 4.5 QUERY ROUTING & INTENT VARIATION AUDIT")
    print("="*70)

    for query, exp_type, exp_sub in variations:
        try:
            res = eng.process_query(query)
            qtype = res.get("query_type")
            stype = res.get("sub_type")
            match = (qtype == exp_type)
            sub_match = (stype == exp_sub)
            status_str = "MATCH" if (match and sub_match) else "MISMATCH"
            print(f"[{status_str}] Query: '{query}' -> Type: {qtype} (Exp: {exp_type}), SubType: {stype} (Exp: {exp_sub})")
        except Exception as e:
            print(f"[ERROR] Query: '{query}' failed with error: {e}")


def main():
    app.config["TESTING"] = True
    audit_query_variations()


if __name__ == "__main__":
    main()
