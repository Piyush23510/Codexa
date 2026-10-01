import sys
import os
import io
import json
import time
import zipfile
from pathlib import Path

# Force UTF-8 stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import app, get_engine, active_repo_id, DEFAULT_REPO_PATH


def create_zip(repo_name, files_dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files_dict.items():
            zf.writestr(f"{repo_name}/{rel_path}", content)
    buf.seek(0)
    return buf


SAMPLE_REPO_SOURCE = {
    "app.py": """
import os
from parser.parser_module import parse_resume, parse_job_description
from utils.exporter import export_to_pdf, export_to_json

class ATSApp:
    def __init__(self, config_path):
        self.config_path = config_path
        self.stats = {}

    def run_pipeline(self, resume_file, job_file):
        resume_data = parse_resume(resume_file)
        job_data = parse_job_description(job_file)
        score = self.calculate_score(resume_data, job_data)
        export_to_json(score, "result.json")
        return score

    def calculate_score(self, resume_data, job_data):
        return len(resume_data) * 10
""",
    "parser/parser_module.py": """
def parse_resume(file_path):
    # Parse resume PDF or docx file
    return {"name": "Applicant", "skills": ["Python", "Flask", "AI"]}

def parse_job_description(file_path):
    # Parse job posting content
    return {"role": "Engineer", "required_skills": ["Python", "AI"]}

def parse(data):
    # Module-level generic parse helper
    return str(data).strip()
""",
    "utils/exporter.py": """
from parser.parser_module import parse

def export_to_pdf(data, output_filename):
    clean_data = parse(data)
    with open(output_filename, "w") as f:
        f.write(clean_data)

def export_to_json(data, output_filename):
    clean_data = parse(data)
    with open(output_filename, "w") as f:
        f.write(clean_data)
"""
}


class QueryQualityAuditor:

    def __init__(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.results = []
        self.repo_ids = {}

    def setup_repositories(self):
        print("\n[Setup] Initializing Audit Repositories...")
        
        # 1. Switch to Default Repo
        res = self.client.post("/api/switch_repo", json={"repo_id": "default"})
        if res.status_code == 200:
            self.repo_ids["default"] = "default"
            print("  ✓ Default Repository registered.")
        else:
            print(f"  ⚠️ Warning: Default repository setup status {res.status_code}")

        # 2. Upload Sample Repo (Multi-module)
        zip_buf = create_zip("ats_sample_project", SAMPLE_REPO_SOURCE)
        res_upload = self.client.post(
            "/api/upload_repo",
            data={"file": (zip_buf, "ats_sample_project.zip")},
            content_type="multipart/form-data"
        )
        if res_upload.status_code == 200:
            data = res_upload.get_json()
            self.repo_ids["sample"] = data["active_repo_id"]
            print(f"  ✓ Sample Repository uploaded with repo_id='{self.repo_ids['sample']}'")
        else:
            print(f"  ❌ Failed uploading sample repository: {res_upload.get_data(as_text=True)}")

    def run_query(self, query, repo_key="default"):
        repo_id = self.repo_ids.get(repo_key, "default")
        t0 = time.time()
        res = self.client.post(
            "/api/query",
            json={"query": query, "repo_id": repo_id}
        )
        elapsed_ms = (time.time() - t0) * 1000

        if res.status_code != 200:
            return {
                "success": False,
                "status_code": res.status_code,
                "error": res.get_data(as_text=True),
                "elapsed_ms": elapsed_ms
            }

        payload = res.get_json()
        payload["elapsed_ms"] = elapsed_ms
        return payload

    def evaluate_query(self, category, query, expected_routing, evaluator_fn, repo_key="default"):
        print(f"\n----------------------------------------------------------------------")
        print(f"[{category}] Query: '{query}' (repo: {repo_key})")
        res = self.run_query(query, repo_key=repo_key)

        if not res.get("success", True) or "error" in res:
            result_status = "FAIL"
            root_cause = f"HTTP_{res.get('status_code', 500)}_ERROR"
            findings = f"Server returned error: {res.get('error')}"
            eval_details = {}
        else:
            query_type = res.get("query_type")
            sub_type = res.get("sub_type")
            answer = res.get("answer", "")
            citations = res.get("citations", [])

            print(f"  ➔ Routed to: type='{query_type}', sub_type='{sub_type}' ({res.get('elapsed_ms', 0):.1f}ms)")
            print(f"  ➔ Answer Length: {len(answer)} chars | Citations: {len(citations)}")
            print(f"  ➔ Answer Snippet: {answer[:180].replace(chr(10), ' ')}...")

            eval_details = evaluator_fn(query, res)
            result_status = eval_details.get("status", "PASS")
            root_cause = eval_details.get("root_cause", "NONE")
            findings = eval_details.get("findings", "")

        print(f"  ➔ AUDIT RESULT: [{result_status}] - {findings}")
        if root_cause != "NONE":
            print(f"  ➔ ROOT CAUSE: {root_cause}")

        audit_entry = {
            "category": category,
            "query": query,
            "repo_key": repo_key,
            "routed_type": res.get("query_type"),
            "routed_sub_type": res.get("sub_type"),
            "expected_routing": expected_routing,
            "status": result_status,
            "root_cause": root_cause,
            "findings": findings,
            "details": eval_details,
            "response_text": res.get("answer", ""),
            "citations_count": len(res.get("citations", [])),
            "elapsed_ms": res.get("elapsed_ms", 0)
        }
        self.results.append(audit_entry)
        return audit_entry


def run_comprehensive_audit():
    auditor = QueryQualityAuditor()
    auditor.setup_repositories()

    # =========================================================================
    # CATEGORY A: REPOSITORY QUERIES
    # =========================================================================
    def eval_repo_overview(q, res):
        ans = res.get("answer", "")
        # Checks if overview is just 4 lines of statistics or rich grounded content
        is_stats_only = ("Total Python Files:" in ans and "Total Functions:" in ans and len(ans.splitlines()) <= 6)
        has_grounding = len(ans) > 250 and ("Purpose" in ans or "Workflow" in ans or "Structure" in ans or "Main Entry" in ans or "python" in ans.lower())
        
        if is_stats_only:
            return {
                "status": "FAIL",
                "root_cause": "PROMPT_AND_ROUTING_PROBLEM",
                "findings": "Overview returned minimal stat numbers instead of a grounded explanatory overview."
            }
        elif not has_grounding:
            return {
                "status": "WARNING",
                "root_cause": "INSUFFICIENT_CONTEXT",
                "findings": "Overview is shallow or lacks structural repository insights."
            }
        return {"status": "PASS", "root_cause": "NONE", "findings": "Rich, grounded repository summary provided."}

    def eval_repo_tech(q, res):
        ans = res.get("answer", "").lower()
        if len(ans) < 50:
            return {"status": "FAIL", "root_cause": "INSUFFICIENT_CONTEXT", "findings": "Response too short to identify tech stack."}
        if "python" in ans or "flask" in ans or "library" in ans or "module" in ans:
            return {"status": "PASS", "root_cause": "NONE", "findings": "Accurately identified technologies/libraries."}
        return {"status": "WARNING", "root_cause": "GROUNDING_PROBLEM", "findings": "Technology details lack explicit grounding."}

    auditor.evaluate_query("A. Repository", "Give me an overview of this repository.", ["REPOSITORY", "OVERVIEW"], eval_repo_overview, "default")
    auditor.evaluate_query("A. Repository", "What does this project do?", ["REPOSITORY", "OVERVIEW"], eval_repo_overview, "default")
    auditor.evaluate_query("A. Repository", "What technologies are used?", ["RAG", "REPOSITORY"], eval_repo_tech, "default")
    auditor.evaluate_query("A. Repository", "What are the entry points?", ["REPOSITORY", "WORKFLOW"], eval_repo_tech, "sample")
    auditor.evaluate_query("A. Repository", "Where should I start exploring this repository?", ["REPOSITORY", "OVERVIEW"], eval_repo_overview, "sample")

    # =========================================================================
    # CATEGORY B: STRUCTURE QUERIES
    # =========================================================================
    def eval_structure(q, res):
        ans = res.get("answer", "")
        if "Python Files" in ans or ".py`" in ans or "app.py" in ans or "files:" in ans.lower():
            return {"status": "PASS", "root_cause": "NONE", "findings": "Project structure and file details provided."}
        return {"status": "FAIL", "root_cause": "RETRIEVAL_PROBLEM", "findings": "Failed to list or explain project structure."}

    auditor.evaluate_query("B. Structure", "Show me the project structure.", ["REPOSITORY", "STRUCTURE"], eval_structure, "sample")
    auditor.evaluate_query("B. Structure", "What are the important files?", ["REPOSITORY", "STRUCTURE"], eval_structure, "sample")
    auditor.evaluate_query("B. Structure", "What is the role of app.py?", ["RAG", "STRUCTURE"], eval_structure, "sample")

    # =========================================================================
    # CATEGORY C: DEPENDENCY QUERIES
    # =========================================================================
    def eval_dependency(q, res):
        ans = res.get("answer", "")
        if "Dependencies" in ans or "called by" in ans or "calls" in ans or "None" in ans or "`" in ans:
            return {"status": "PASS", "root_cause": "NONE", "findings": "Dependency details correctly retrieved."}
        return {"status": "FAIL", "root_cause": "DEPENDENCY_ANALYSIS_PROBLEM", "findings": "Dependency information missing or invalid."}

    auditor.evaluate_query("C. Dependency", "What functions does run_pipeline call?", ["DEPENDENCY", "DIRECT"], eval_dependency, "sample")
    auditor.evaluate_query("C. Dependency", "Who calls parse_resume?", ["DEPENDENCY", "REVERSE"], eval_dependency, "sample")
    auditor.evaluate_query("C. Dependency", "Show the dependencies of export_to_pdf.", ["DEPENDENCY", "DIRECT"], eval_dependency, "sample")

    # =========================================================================
    # CATEGORY D: IMPACT QUERIES
    # =========================================================================
    def eval_impact(q, res):
        ans = res.get("answer", "")
        has_impact_metrics = ("Impact Percentage" in ans or "Risk Level" in ans or "Directly Affected" in ans)
        if has_impact_metrics:
            return {"status": "PASS", "root_cause": "NONE", "findings": "Impact analysis & risk assessment calculated."}
        return {"status": "FAIL", "root_cause": "ROUTING_PROBLEM", "findings": "Failed to invoke impact analysis handler."}

    auditor.evaluate_query("D. Impact", "What would be affected if I change parse_resume?", ["IMPACT", "IMPACT"], eval_impact, "sample")
    auditor.evaluate_query("D. Impact", "What is the risk of changing parse?", ["IMPACT", "IMPACT"], eval_impact, "sample")

    # =========================================================================
    # CATEGORY E: RAG / CODE UNDERSTANDING QUERIES
    # =========================================================================
    def eval_rag(q, res):
        ans = res.get("answer", "")
        cits = res.get("citations", [])
        if len(ans) > 100 and len(cits) > 0:
            return {"status": "PASS", "root_cause": "NONE", "findings": "Retrieved context and generated citations."}
        elif len(ans) > 100:
            return {"status": "WARNING", "root_cause": "CITATION_PROBLEM", "findings": "Generated answer but missing citations."}
        return {"status": "FAIL", "root_cause": "RETRIEVAL_PROBLEM", "findings": "Failed to retrieve relevant code chunks."}

    auditor.evaluate_query("E. RAG Code Logic", "Explain how parse_pipeline works in app.py", ["RAG"], eval_rag, "sample")
    auditor.evaluate_query("E. RAG Code Logic", "Where is export_to_json implemented?", ["RAG"], eval_rag, "sample")

    # =========================================================================
    # CATEGORY F: SYMBOL-SPECIFIC QUERIES
    # =========================================================================
    def eval_symbol(q, res):
        ans = res.get("answer", "")
        if "ATSApp" in ans or "parse_resume" in ans or "export" in ans or "class" in ans.lower():
            return {"status": "PASS", "root_cause": "NONE", "findings": "Resolved symbol successfully."}
        return {"status": "WARNING", "root_cause": "DEPENDENCY_ANALYSIS_PROBLEM", "findings": "Symbol identity not clearly resolved."}

    auditor.evaluate_query("F. Symbol Resolution", "Explain the ATSApp class.", ["RAG"], eval_symbol, "sample")
    auditor.evaluate_query("F. Symbol Resolution", "What does ATSApp.run_pipeline do?", ["RAG"], eval_symbol, "sample")

    # =========================================================================
    # CATEGORY G: AMBIGUOUS QUERIES
    # =========================================================================
    def eval_ambiguous(q, res):
        ans = res.get("answer", "")
        # Ambiguous function 'parse' exists in both parser_module.py and as method parse_resume/parse_job_description
        if "parse" in ans or "module" in ans or "candidate" in ans.lower():
            return {"status": "PASS", "root_cause": "NONE", "findings": "Handled ambiguous symbol name gracefully."}
        return {"status": "WARNING", "root_cause": "DEPENDENCY_ANALYSIS_PROBLEM", "findings": "Did not indicate symbol candidates."}

    auditor.evaluate_query("G. Ambiguity", "Explain parse()", ["RAG", "DEPENDENCY"], eval_ambiguous, "sample")

    # =========================================================================
    # CATEGORY H: UNSUPPORTED / UNKNOWN QUERIES
    # =========================================================================
    def eval_unsupported(q, res):
        ans = res.get("answer", "")
        ans_lower = ans.lower()
        if "no relevant code context" in ans_lower or "does not contain" in ans_lower or "not provided" in ans_lower or "cannot determine" in ans_lower or "no evidence" in ans_lower:
            return {"status": "PASS", "root_cause": "NONE", "findings": "Gracefully reported lack of evidence."}
        return {"status": "WARNING", "root_cause": "GROUNDING_PROBLEM", "findings": "Model attempted to speculate on out-of-domain query."}

    auditor.evaluate_query("H. Unsupported", "What database will this project use next year?", ["RAG"], eval_unsupported, "sample")
    auditor.evaluate_query("H. Unsupported", "Who originally wrote this project?", ["RAG"], eval_unsupported, "sample")

    # =========================================================================
    # REPOSITORY CONTEXT ISOLATION (SWITCHING AUDIT)
    # =========================================================================
    print("\n----------------------------------------------------------------------")
    print("[Context Isolation Test] Switching Repo sample -> default -> sample...")
    res_s1 = auditor.run_query("What functions are in this repo?", repo_key="sample")
    res_def = auditor.run_query("What functions are in this repo?", repo_key="default")
    res_s2 = auditor.run_query("What functions are in this repo?", repo_key="sample")

    ans_s1 = res_s1.get("answer", "")
    ans_def = res_def.get("answer", "")
    ans_s2 = res_s2.get("answer", "")

    if "run_pipeline" in ans_s1 and "run_pipeline" not in ans_def and "run_pipeline" in ans_s2:
        print("  ➔ REPO ISOLATION: [PASS] Context properly isolated across repo switches.")
        auditor.results.append({
            "category": "Isolation",
            "query": "Context Isolation Test",
            "repo_key": "multi",
            "routed_type": "REPOSITORY",
            "routed_sub_type": "COUNT",
            "expected_routing": ["REPOSITORY"],
            "status": "PASS",
            "root_cause": "NONE",
            "findings": "Strict context isolation verified between repository switches.",
            "response_text": ans_s1,
            "citations_count": 0,
            "elapsed_ms": 0
        })
    else:
        print("  ➔ REPO ISOLATION: [FAIL] Stale context contamination detected!")
        auditor.results.append({
            "category": "Isolation",
            "query": "Context Isolation Test",
            "repo_key": "multi",
            "routed_type": "REPOSITORY",
            "routed_sub_type": "COUNT",
            "expected_routing": ["REPOSITORY"],
            "status": "FAIL",
            "root_cause": "REPOSITORY_STATE_PROBLEM",
            "findings": "Stale context leaked across repository switches.",
            "response_text": ans_s1,
            "citations_count": 0,
            "elapsed_ms": 0
        })

    # =========================================================================
    # AUDIT SUMMARY REPORT GENERATION
    # =========================================================================
    print("\n" + "="*80)
    print("                      QUERY QUALITY AUDIT SUMMARY REPORT")
    print("="*80)
    
    total = len(auditor.results)
    passed = sum(1 for r in auditor.results if r["status"] == "PASS")
    warnings = sum(1 for r in auditor.results if r["status"] == "WARNING")
    failed = sum(1 for r in auditor.results if r["status"] == "FAIL")

    print(f"\nTotal Query Scenarios Evaluated: {total}")
    print(f"  ✓ PASS:    {passed} ({(passed/total)*100:.1f}%)")
    print(f"  ⚠️ WARNING: {warnings} ({(warnings/total)*100:.1f}%)")
    print(f"  ❌ FAIL:    {failed} ({(failed/total)*100:.1f}%)")

    root_causes = {}
    for r in auditor.results:
        rc = r["root_cause"]
        if rc != "NONE":
            root_causes[rc] = root_causes.get(rc, 0) + 1

    if root_causes:
        print("\n[Identified Systemic Root Causes]")
        for rc, cnt in root_causes.items():
            print(f"  - {rc}: {cnt} query scenario(s)")

    print("\n" + "-"*80)
    print(f"{'Category':<16} | {'Status':<7} | {'Root Cause':<28} | {'Query'}")
    print("-" * 80)
    for r in auditor.results:
        print(f"{r['category'][:16]:<16} | {r['status']:<7} | {r['root_cause']:<28} | '{r['query'][:30]}'")

    return auditor.results


if __name__ == "__main__":
    run_comprehensive_audit()
