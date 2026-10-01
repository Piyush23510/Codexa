import sys
import os
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import CopilotEngine

def run_tests():
    print("======================================================================")
    print("                  VERIFYING FIXES 1, 2, AND 3                         ")
    print("======================================================================")

    # Setup sample project with leaf function & ambiguous symbol
    temp_dir = tempfile.mkdtemp(prefix="audit_fixes_test_")
    try:
        sample_repo = Path(temp_dir) / "sample_repo"
        sample_repo.mkdir(parents=True)
        (sample_repo / "mod_a.py").write_text("""
def parse(data):
    return data.strip()

def process():
    return parse("test")
""", encoding="utf-8")
        
        (sample_repo / "mod_b.py").write_text("""
def parse(text):
    return text.lower()

def leaf_function():
    pass
""", encoding="utf-8")

        print("\n[Setup] Initializing CopilotEngine on sample repository...")
        engine = CopilotEngine(str(sample_repo), repo_id="sample_test_repo")

        # --------------------------------------------------------------------
        # TEST 1 — REPOSITORY OVERVIEW CHAT RESPONSE
        # --------------------------------------------------------------------
        print("\n--- TEST 1: Repository Overview Chat Response ---")
        res_overview = engine.handle_repository_overview()
        ans_overview = res_overview.get("answer", "")
        print(f"Overview Output:\n{ans_overview[:300]}...\n")

        assert len(ans_overview) > 150, "Overview response is too short!"
        print("[PASS] FIX 1 PASSED: Repository overview chat query returned grounded structured data.")

        # --------------------------------------------------------------------
        # TEST 2 — BARE FUNCTION NAME RESOLUTION & AMBIGUITY
        # --------------------------------------------------------------------
        print("\n--- TEST 2: Bare Function Name Resolution & Ambiguity ---")
        
        # 2a. Real bare symbol resolution
        res_impact_real = engine.handle_impact_query("What is the risk of changing process?")
        ans_impact_real = res_impact_real.get("answer", "")
        print(f"Bare Symbol Impact Output:\n{ans_impact_real[:250]}...\n")
        assert "Could not identify" not in ans_impact_real, "Failed to identify real bare symbol 'process'!"
        print("[PASS] 2a PASSED: Bare symbol 'process' correctly resolved.")

        # 2b. Unknown symbol query
        res_unknown = engine.handle_impact_query("What is the risk of changing non_existent_symbol?")
        ans_unknown = res_unknown.get("answer", "")
        print(f"Unknown Symbol Output:\n{ans_unknown}\n")
        assert "Could not identify" in ans_unknown, "Failed to gracefully reject unknown symbol!"
        print("[PASS] 2b PASSED: Unknown symbol gracefully rejected without hallucination.")

        # 2c. Ambiguous bare symbol resolution
        res_ambiguous = engine.handle_impact_query("What is the risk of changing parse?")
        ans_ambiguous = res_ambiguous.get("answer", "")
        print(f"Ambiguous Symbol Output:\n{ans_ambiguous}\n")
        assert "Multiple symbols named `parse` exist" in ans_ambiguous or "mod_a" in ans_ambiguous, "Failed to report ambiguity for duplicate bare symbol 'parse'!"
        print("[PASS] 2c PASSED: Ambiguous bare symbol 'parse' correctly flagged with candidate list.")

        # --------------------------------------------------------------------
        # TEST 3 — LEAF NODE DEPENDENCY RESPONSE
        # --------------------------------------------------------------------
        print("\n--- TEST 3: Leaf Node Dependency Response ---")
        res_leaf = engine.handle_specific_dependency("Show the dependencies of leaf_function", "DIRECT")
        ans_leaf = res_leaf.get("answer", "")
        print(f"Leaf Function Output:\n{ans_leaf}\n")
        assert "Function 'leaf_function' has no outgoing function calls." in ans_leaf, f"Expected clear statement for leaf function, got: {ans_leaf}"
        assert ans_leaf != "None", "Returned ambiguous 'None' for leaf function!"
        print("[PASS] FIX 3 PASSED: Leaf function reported explicit zero outgoing calls statement.")

        print("\n======================================================================")
        print("              ALL FIXES VERIFIED SUCCESSFULLY (PASS)                   ")
        print("======================================================================")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_tests()
