import os
import zipfile
import shutil
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory

from parser.ast_parser import ASTParser
from parser.repo_parser import RepoParser
from parser.dependency_analyzer import DependencyAnalyzer
from parser.query_router import QueryRouter
from parser.dependency_graph import create_dependency_graph, create_impact_graph

from rag.chunk_generator import ChunkGenerator
from rag.embeddings_generator import EmbeddingGenerator
from rag.vector_store import VectorStore
from rag.bm25_retriever import BM25Retriever
from rag.hybrid_retriever import HybridRetriever
from rag.reranker import Reranker
from rag.llm_generator import LLMGenerator
from rag.citation_generator import CitationGenerator
from rag.overview_service import OverviewService

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB upload limit

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_WORKSPACE = BASE_DIR / "uploaded_repositories"
UPLOAD_WORKSPACE.mkdir(parents=True, exist_ok=True)
GRAPH_DIR = BASE_DIR / "graphs"
GRAPH_DIR.mkdir(parents=True, exist_ok=True)


def _get_effective_root(container_dir: Path) -> Path:
    """
    Given an extracted ZIP container directory, determine the effective
    repository root.  If the container holds exactly one subdirectory
    and zero top-level .py files, the inner subdirectory is the real root.
    """
    filtered = [p for p in container_dir.iterdir() if p.name not in ["__MACOSX", ".DS_Store"]]
    top_py = [p for p in filtered if p.is_file() and p.suffix.lower() == ".py"]
    top_dirs = [p for p in filtered if p.is_dir()]
    if len(top_dirs) == 1 and len(top_py) == 0:
        return top_dirs[0]
    return container_dir


def clean_repo_display_name(raw_name):
    """
    Format a clean, human-readable repository display name.
    Example: 'Capstone-Project-I---Mutual-Fund-Analytics-main' -> 'Mutual Fund Analytics'
    """
    if not raw_name:
        return "Repository"
    import re
    name = str(raw_name).strip()
    # Strip common git/branch suffixes
    name = re.sub(r'[-_](main|master)(\.git)?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.git$', '', name, flags=re.IGNORECASE)
    # Strip junk prefixes (e.g. Capstone-Project-I---)
    name = re.sub(r'^capstone[-_]project[-_][a-z0-9]+[-_]+', '', name, flags=re.IGNORECASE)
    # Strip trailing random UUID hex hashes (e.g. _3c7c3d)
    name = re.sub(r'_[a-f0-9]{6}$', '', name)
    # Replace dashes/underscores with spaces
    name = re.sub(r'[-_]+', ' ', name).strip()
    if name:
        name = " ".join([word.capitalize() for word in name.split()])
    return name or str(raw_name)


def clean_file_path(raw_path, repo_path=None):
    """
    Strip absolute / server-specific prefixes from a file path so that
    user-facing citations show only repository-relative paths.
    """
    clean = str(raw_path).replace("\\", "/")

    # Strip using the known repo_path if provided
    if repo_path:
        repo_prefix = str(repo_path).replace("\\", "/")
        if clean.startswith(repo_prefix):
            clean = clean[len(repo_prefix):].lstrip("/")
            return clean or str(raw_path)

    # Fallback: strip uploaded_repositories/<repo_id>/<inner_dir>/ prefix
    if "uploaded_repositories/" in clean:
        tail = clean.split("uploaded_repositories/", 1)[1]
        # tail is  <repo_folder_id>/<inner_dir>/file.py  or  <repo_folder_id>/file.py
        parts = tail.split("/", 1)
        if len(parts) > 1:
            clean = parts[1]
        else:
            clean = parts[0]

    # Fallback: strip default repo prefix
    if "AI-Powered-ATS-Resume-Analyzer/" in clean:
        clean = clean.split("AI-Powered-ATS-Resume-Analyzer/", 1)[1]

    return clean or str(raw_path)


def safe_extract_zip(file_obj, extract_to_dir: Path):
    """
    Safely extract a ZIP archive with strict Zip Slip / Path Traversal protection.
    Ensures every extracted file resolves to a path strictly inside target_dir.
    """
    target_dir_abs = extract_to_dir.resolve()
    with zipfile.ZipFile(file_obj, "r") as zip_ref:
        for member in zip_ref.infolist():
            member_path = (extract_to_dir / member.filename).resolve()
            try:
                member_path.relative_to(target_dir_abs)
            except ValueError:
                raise ValueError(f"Zip Slip / Path Traversal attempt detected in archive member: {member.filename}")
            zip_ref.extract(member, extract_to_dir)


class CopilotEngine:
    """
    Engine wrapper managing repository parsing, AST dependency analysis,
    hybrid FAISS+BM25 vector indexing, cross-encoder reranking, and Groq LLM generation.
    """
    def __init__(self, target_repo_path: str, repo_id: str = None):
        self.repo_path = Path(target_repo_path)
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {target_repo_path}")

        self.repo_id = repo_id or self.repo_path.name
        print(f"\n[CopilotEngine] Initializing target repository '{self.repo_id}' at: {self.repo_path}")

        # Clean up stale graph artifacts from previous repository loading for this repo_id
        for graph_filename in [f"dependency_graph_{self.repo_id}.html", f"impact_graph_{self.repo_id}.html"]:
            for search_dir in [GRAPH_DIR, BASE_DIR]:
                stale_file = search_dir / graph_filename
                if stale_file.exists():
                    try:
                        stale_file.unlink()
                        print(f"[CopilotEngine] Cleaned up stale graph artifact: {stale_file}")
                    except Exception as e:
                        print(f"[Warning] Could not remove stale graph artifact {graph_filename}: {e}")

        # 1. Repository parsing & file collection
        self.repo_parser = RepoParser(str(self.repo_path))
        self.files = self.repo_parser.get_python_files()
        self.summary = self.repo_parser.get_repo_summary()

        # 2. Citation & Chunking Setup
        self.citation_generator = CitationGenerator()
        self.all_chunks = []

        # Add repository summary chunk
        summary_chunk = {
            "text": (
                f"Repository Summary:\n"
                f"Project Name: {self.summary['project_name']}\n"
                f"Total Python Files: {self.summary['total_python_files']}\n"
                f"Total Folders: {self.summary['total_folders']}\n"
            ),
            "metadata": {
                "file": "repository_summary",
                "type": "repository_summary",
                "name": "repository_summary",
                "project_name": self.summary["project_name"],
                "start_line": 0,
                "end_line": 0
            }
        }
        self.all_chunks.append(summary_chunk)

        # Generate AST function chunks
        for file_path in self.files:
            try:
                parser = ASTParser(file_path)
                chunk_gen = ChunkGenerator(file_path, parser)
                chunks = chunk_gen.generate_chunks()
                self.all_chunks.extend(chunks)
            except Exception as e:
                print(f"[Warning] Failed to parse AST for {file_path}: {e}")

        print(f"[CopilotEngine] Loaded {len(self.files)} python files, {len(self.all_chunks)} chunks.")

        # 3. Vector Embeddings & Indexing
        self.embedding_generator = EmbeddingGenerator()
        embeddings = self.embedding_generator.generate_embeddings(self.all_chunks)

        self.vector_store = VectorStore(dimension=384)
        self.vector_store.add_embeddings(embeddings)

        # 4. Retrievers & Reranker & LLM Router
        self.bm25 = BM25Retriever(self.all_chunks)
        self.hybrid_retriever = HybridRetriever(self.vector_store, self.bm25)
        self.llm = LLMGenerator()
        self.reranker = Reranker()
        self.router = QueryRouter(self.llm)

        # 5. Dependency Analysis
        self.analyzer = DependencyAnalyzer(self.files)
        self.dependencies, self.reverse_dependencies = self.analyzer.get_function_dependencies()
        self.workflow = self.analyzer.get_repository_workflow(
            self.dependencies,
            self.reverse_dependencies
        )

        # 6. Repository Overview Service
        self.overview_service = OverviewService(
            self.repo_path,
            dependency_analyzer=self.analyzer,
            files=self.files,
            repo_id=self.repo_id
        )
        self._cached_overview = None

    def retrieve_and_rerank(self, query: str, top_k_hybrid=20, top_k_rerank=3):
        query_embedding = self.embedding_generator.generate_embedding(query)
        hybrid_results = self.hybrid_retriever.search(query, query_embedding, k=top_k_hybrid)
        final_results = self.reranker.rerank(query, hybrid_results, k=top_k_rerank)
        return final_results

    def build_context(self, final_results, additional_context=""):
        context = additional_context + "\n"
        for result in final_results:
            context += result["text"] + "\n\n"
        return context

    def get_repository_overview(self, force_refresh: bool = False):
        if self._cached_overview and not force_refresh:
            return self._cached_overview

        facts = self.overview_service.collect_facts()

        if self.llm:
            try:
                summary_md = self.llm.generate_repository_overview(facts)
            except Exception as e:
                print(f"[CopilotEngine] LLM overview generation error: {e}")
                summary_md = self.llm.generate_deterministic_summary(facts)
        else:
            summary_md = self.overview_service.get_deterministic_summary(facts) if hasattr(self.overview_service, "get_deterministic_summary") else ""

        overview_data = {
            "success": True,
            "repository": facts["repository"],
            "statistics": facts["statistics"],
            "structure": facts["structure"],
            "entry_points": facts["entry_points"],
            "important_components": facts["important_components"],
            "architecture": facts["architecture"],
            "dependencies": facts["dependencies"],
            "summary": summary_md,
            "exploration_path": facts["exploration_path"],
            "suggested_questions": facts["suggested_questions"]
        }

        self._cached_overview = overview_data
        return overview_data

    # ------------------------------------------------------------------------
    # Handlers preserving exact core business logic
    # ------------------------------------------------------------------------
    def handle_repository_count(self, query: str):
        query_lower = query.lower()
        if "function" in query_lower:
            answer = f"**Total Functions in Repository:** {len(self.dependencies)}"
        elif "python file" in query_lower or "file" in query_lower:
            answer = f"**Total Python Files:** {self.summary['total_python_files']}"
        elif "folder" in query_lower:
            answer = f"**Total Folders:** {self.summary['total_folders']}"
        else:
            answer = (
                f"### Repository Count Overview\n"
                f"- **Total Python Files:** {self.summary['total_python_files']}\n"
                f"- **Total Folders:** {self.summary['total_folders']}\n"
                f"- **Total Functions:** {len(self.dependencies)}"
            )
        return {
            "query_type": "REPOSITORY",
            "sub_type": "COUNT",
            "answer": answer,
            "citations": []
        }

    def handle_repository_structure(self):
        clean_files = [clean_file_path(f, self.repo_path) for f in self.files]
        file_list_str = "\n".join([f"- `{f}`" for f in clean_files])
        answer = (
            f"### Repository Structure\n"
            f"**Project Name:** {self.summary['project_name']}\n\n"
            f"**Python Files ({len(self.files)}):**\n{file_list_str}"
        )
        return {
            "query_type": "REPOSITORY",
            "sub_type": "STRUCTURE",
            "answer": answer,
            "citations": []
        }

    def handle_repository_overview(self):
        overview_data = self.get_repository_overview()
        summary_text = overview_data.get("summary", "")
        if not summary_text:
            summary_text = (
                f"### Repository Overview\n"
                f"- **Project Name:** {self.summary['project_name']}\n"
                f"- **Total Python Files:** {self.summary['total_python_files']}\n"
                f"- **Total Folders:** {self.summary['total_folders']}\n"
                f"- **Total Functions:** {len(self.dependencies)}"
            )
        return {
            "query_type": "REPOSITORY",
            "sub_type": "OVERVIEW",
            "answer": summary_text,
            "citations": []
        }

    def handle_repository_workflow(self):
        function_metadata = {}
        for func in self.workflow.get("workflow", []):
            details = self.analyzer.get_function_details(func)
            if details:
                function_metadata[func] = details

        repository_data = {
            "project_name": self.summary["project_name"],
            "total_python_files": self.summary["total_python_files"],
            "total_folders": self.summary["total_folders"],
            "total_functions": len(self.dependencies),
            "main_entry_point": self.workflow.get("main_entry_point"),
            "direct_dependencies": self.workflow.get("workflow", []),
            "function_metadata": function_metadata
        }

        explanation = self.llm.explain_repository_workflow(repository_data)
        answer = (
            f"### Main Entry Point\n`{self.workflow.get('main_entry_point')}`\n\n"
            f"### Workflow Explanation\n{explanation}"
        )
        return {
            "query_type": "REPOSITORY",
            "sub_type": "WORKFLOW",
            "answer": answer,
            "citations": []
        }

    def handle_dependency_graph(self):
        graph_filename = f"dependency_graph_{self.repo_id}.html"
        graph_file_path = GRAPH_DIR / graph_filename
        create_dependency_graph(self.dependencies, filename=graph_file_path)
        answer = (
            "### Repository Dependency Graph\n"
            "The full function dependency graph has been generated. You can view the interactive graph below."
        )
        return {
            "query_type": "DEPENDENCY",
            "sub_type": "GRAPH",
            "answer": answer,
            "graph_url": f"/api/graph/{graph_filename}",
            "citations": []
        }

    def handle_specific_dependency(self, query: str, dependency_type: str):
        function_name = self.llm.identify_dependency_function(query, list(self.dependencies.keys()))

        if not function_name and dependency_type != "INDIRECT":
            return {
                "query_type": "DEPENDENCY",
                "sub_type": dependency_type,
                "answer": "Could not identify a matching function name in the query from the repository function list.",
                "citations": []
            }

        if function_name and function_name.startswith("AMBIGUOUS:"):
            symbol_name = function_name.split(":", 1)[1]
            candidates = [f for f in self.dependencies.keys() if f.endswith(f"::{symbol_name}") or f == symbol_name]
            cand_str = "\n".join([f"- `{c}`" for c in candidates])
            return {
                "query_type": "DEPENDENCY",
                "sub_type": dependency_type,
                "answer": f"Multiple symbols named `{symbol_name}` exist in the repository. Please specify which fully qualified symbol you want to analyze:\n{cand_str}",
                "citations": []
            }

        citations = []
        if function_name:
            details = self.analyzer.get_function_details(function_name)
            if details:
                citations.append({
                    "file": clean_file_path(details["file"], self.repo_path),
                    "type": "function",
                    "name": details["name"],
                    "start_line": details["start_line"],
                    "end_line": details["end_line"]
                })

        if dependency_type == "DIRECT":
            calls = self.dependencies.get(function_name, [])
            if calls:
                calls_formatted = "\n".join([f"- `{c}`" for c in calls])
                answer = (
                    f"### Direct Dependencies for `{function_name}`\n"
                    f"Functions called directly by `{function_name}`:\n{calls_formatted}"
                )
            else:
                answer = f"Function '{function_name}' has no outgoing function calls."

        elif dependency_type == "REVERSE":
            callers = self.reverse_dependencies.get(function_name, [])
            if callers:
                callers_formatted = "\n".join([f"- `{c}`" for c in callers])
                answer = (
                    f"### Reverse Dependencies for `{function_name}`\n"
                    f"Functions that call `{function_name}`:\n{callers_formatted}"
                )
            else:
                answer = f"No other functions in the repository call '{function_name}'."

        elif dependency_type == "INDIRECT":
            if function_name:
                indirect = self.analyzer.get_indirect_dependencies(function_name, self.dependencies)
                if indirect:
                    indirect_formatted = "\n".join([f"- `{c}`" for c in indirect])
                    answer = (
                        f"### Indirect Dependencies for `{function_name}`\n"
                        f"Functions transitively called by `{function_name}`:\n{indirect_formatted}"
                    )
                else:
                    answer = f"Function '{function_name}' has no indirect outgoing dependencies."
            else:
                answer_lines = ["### Repository-Wide Indirect Dependencies\n"]
                found = False
                for func in self.dependencies:
                    indirect = self.analyzer.get_indirect_dependencies(func, self.dependencies)
                    if indirect:
                        found = True
                        answer_lines.append(f"**`{func}`** -> {', '.join([f'`{i}`' for i in indirect])}")
                if not found:
                    answer_lines.append("No indirect dependencies found in repository.")
                answer = "\n".join(answer_lines)

        elif dependency_type == "ORDER":
            ordered_calls = []
            for file_path in self.files:
                parser = ASTParser(file_path)
                ordered_calls = parser.get_function_call_order(function_name, known_functions=set(self.dependencies.keys()))
                if ordered_calls:
                    break

            if ordered_calls:
                order_formatted = "\n".join([f"{idx}. `{c}`" for idx, c in enumerate(ordered_calls, start=1)])
                answer = f"### Function Call Sequence inside `{function_name}`\n{order_formatted}"
            else:
                answer = f"No inner function calls found for `{function_name}`."
        else:
            answer = "Unknown dependency query subtype."

        return {
            "query_type": "DEPENDENCY",
            "sub_type": dependency_type,
            "answer": answer,
            "citations": citations
        }

    def handle_impact_query(self, query: str):
        changed_function = self.llm.identify_changed_function(query, list(self.dependencies.keys()))
        if not changed_function:
            return {
                "query_type": "IMPACT",
                "sub_type": "IMPACT",
                "answer": "Could not identify an explicitly changed function in your query.",
                "citations": []
            }

        if changed_function.startswith("AMBIGUOUS:"):
            symbol_name = changed_function.split(":", 1)[1]
            candidates = [f for f in self.dependencies.keys() if f.endswith(f"::{symbol_name}") or f == symbol_name]
            cand_str = "\n".join([f"- `{c}`" for c in candidates])
            return {
                "query_type": "IMPACT",
                "sub_type": "IMPACT",
                "answer": f"Multiple symbols named `{symbol_name}` exist in the repository. Please specify which fully qualified symbol you want to analyze:\n{cand_str}",
                "citations": []
            }

        direct_impact, indirect_impact = self.analyzer.get_impact_analysis(
            changed_function,
            self.reverse_dependencies
        )

        graph_filename = f"impact_graph_{self.repo_id}.html"
        graph_file_path = GRAPH_DIR / graph_filename
        create_impact_graph(
            changed_function,
            direct_impact,
            indirect_impact,
            self.reverse_dependencies,
            filename=graph_file_path
        )

        affected_details = []
        citations = []

        # Target function citation
        target_details = self.analyzer.get_function_details(changed_function)
        if target_details:
            citations.append({
                "file": clean_file_path(target_details["file"], self.repo_path),
                "type": "changed_function",
                "name": target_details["name"],
                "start_line": target_details["start_line"],
                "end_line": target_details["end_line"]
            })

        for func in direct_impact:
            details = self.analyzer.get_function_details(func)
            if details:
                clean_fp = clean_file_path(details["file"], self.repo_path)
                affected_details.append({"function": func, "impact": "Direct", "file": clean_fp, "start_line": details["start_line"], "end_line": details["end_line"]})
                citations.append({"file": clean_fp, "type": "direct_impact", "name": func, "start_line": details["start_line"], "end_line": details["end_line"]})

        for func in indirect_impact:
            details = self.analyzer.get_function_details(func)
            if details:
                clean_fp = clean_file_path(details["file"], self.repo_path)
                affected_details.append({"function": func, "impact": "Indirect", "file": clean_fp, "start_line": details["start_line"], "end_line": details["end_line"]})
                citations.append({"file": clean_fp, "type": "indirect_impact", "name": func, "start_line": details["start_line"], "end_line": details["end_line"]})

        impact_perc = self.analyzer.impact_percentage(direct_impact, indirect_impact, len(self.dependencies))
        risk = self.analyzer.calculate_risk(direct_impact, indirect_impact)

        recommendation = self.llm.generate_recommendation(
            changed_function,
            direct_impact,
            indirect_impact,
            impact_perc,
            risk
        )

        impact_context = (
            f"===== IMPACT ANALYSIS =====\n"
            f"Changed Function: {changed_function}\n"
            f"Direct Impact: {list(direct_impact)}\n"
            f"Indirect Impact: {list(indirect_impact)}\n"
            f"Impact Percentage: {impact_perc:.2f}%\n"
            f"Risk: {risk}\n"
            f"Recommendation: {recommendation}\n"
            f"Affected Function Details: {affected_details}\n"
        )

        final_results = self.retrieve_and_rerank(query)
        context = self.build_context(final_results, impact_context)
        ai_answer = self.llm.generate_answer(query, context)
        rag_citations = self.citation_generator.generate_citations(final_results)

        # Merge citations cleanly without duplicates
        existing_keys = {(c["file"], c.get("name"), c.get("start_line")) for c in citations}
        for c in rag_citations:
            key = (c["file"], c.get("name"), c.get("start_line"))
            if key not in existing_keys:
                citations.append(c)

        answer = (
            f"### Change Impact Analysis for `{changed_function}`\n"
            f"- **Impact Percentage:** {impact_perc:.2f}%\n"
            f"- **Risk Level:** `{risk}`\n"
            f"- **Directly Affected:** {', '.join([f'`{f}`' for f in direct_impact]) if direct_impact else 'None'}\n"
            f"- **Indirectly Affected:** {', '.join([f'`{f}`' for f in indirect_impact]) if indirect_impact else 'None'}\n\n"
            f"### Engineering Recommendation\n{recommendation}\n\n"
            f"### Detailed Analysis\n{ai_answer}"
        )

        return {
            "query_type": "IMPACT",
            "sub_type": "IMPACT",
            "answer": answer,
            "graph_url": f"/api/graph/{graph_filename}",
            "citations": citations,
            "impact_percentage": impact_perc,
            "risk": risk
        }

    def handle_rag_query(self, query: str):
        final_results = self.retrieve_and_rerank(query)

        # Relevance guard check: if top rerank score indicates no relevant context (< -7.0 logit), return grounded fallback
        if final_results and final_results[0].get("rerank_score", 0) < -7.0:
            return {
                "query_type": "RAG",
                "sub_type": "RAG",
                "answer": "No relevant code context found in the repository for this query.",
                "citations": []
            }

        context = self.build_context(final_results)
        ai_answer = self.llm.generate_answer(query, context)
        citations = self.citation_generator.generate_citations(final_results)

        return {
            "query_type": "RAG",
            "sub_type": "RAG",
            "answer": ai_answer,
            "citations": citations
        }

    def process_query(self, query: str):
        query_type = self.router.route(query)

        if query_type == "REPOSITORY":
            sub_type = self.router.repository_route(query)
            if sub_type == "COUNT":
                return self.handle_repository_count(query)
            elif sub_type == "STRUCTURE":
                return self.handle_repository_structure()
            elif sub_type == "OVERVIEW":
                return self.handle_repository_overview()
            elif sub_type == "WORKFLOW":
                return self.handle_repository_workflow()
            else:
                return self.handle_repository_overview()

        elif query_type == "DEPENDENCY":
            sub_type = self.router.dependency_route(query)
            if sub_type == "GRAPH":
                return self.handle_dependency_graph()
            elif sub_type in ["DIRECT", "REVERSE", "INDIRECT", "ORDER"]:
                return self.handle_specific_dependency(query, sub_type)
            else:
                return self.handle_rag_query(query)

        elif query_type == "IMPACT":
            return self.handle_impact_query(query)

        elif query_type == "RAG":
            return self.handle_rag_query(query)

        else:
            return self.handle_rag_query(query)

    def get_suggested_questions(self):
        proj_name = self.summary.get("project_name", "the project")
        func_names = [f for f in list(self.dependencies.keys()) if not f.startswith("__")]

        suggestions = []

        if func_names:
            f1 = func_names[0]
            suggestions.append(f"Which functions does {f1} call?")
            if len(func_names) > 1:
                f2 = func_names[1]
                suggestions.append(f"Who calls {f2}?")
                suggestions.append(f"What would be affected if {f1} changes?")
            else:
                suggestions.append(f"What would be affected if {f1} changes?")
                suggestions.append(f"What does {f1} do?")
        else:
            suggestions.append(f"Give me an overview of {proj_name}.")
            suggestions.append(f"What Python files are in {proj_name}?")

        suggestions.append(f"Explain the main workflow of {proj_name}.")
        suggestions.append("Show the dependency graph.")
        suggestions.append("How many functions are in the repository?")

        return suggestions


# ----------------------------------------------------------------------------
# Global Repository Engine Registry & Active State Manager
# ----------------------------------------------------------------------------
DEFAULT_REPO_PATH = BASE_DIR / "AI-Powered-ATS-Resume-Analyzer"
engine_registry = {}  # Map of repo_id -> CopilotEngine
active_repo_id = None



def resolve_repo_path(target_path_or_id):
    """
    Resolves a repository ID or filesystem path into (repo_id, Path_object).
    Returns the effective repository root (unwrapping single-subdirectory
    ZIP containers). Exact matches are always preferred over prefix matches.
    """
    if not target_path_or_id:
        return "default", DEFAULT_REPO_PATH

    target_str = str(target_path_or_id).strip()

    if target_str == "default" or target_str == DEFAULT_REPO_PATH.name or (DEFAULT_REPO_PATH.exists() and Path(target_str).resolve() == DEFAULT_REPO_PATH.resolve()):
        return "default", DEFAULT_REPO_PATH

    target_path = Path(target_str)
    if not target_path.is_absolute():
        target_path = UPLOAD_WORKSPACE / target_str

    if target_path.exists() and target_path.is_dir():
        try:
            rel_id = target_path.relative_to(UPLOAD_WORKSPACE).parts[0]
            container = UPLOAD_WORKSPACE / rel_id
            return rel_id, _get_effective_root(container)
        except ValueError:
            return target_path.name, target_path

    if UPLOAD_WORKSPACE.exists():
        # Exact directory name match only — no ambiguous prefix matching
        for item in UPLOAD_WORKSPACE.iterdir():
            if item.is_dir() and item.name == target_str:
                return item.name, _get_effective_root(item)

    raise FileNotFoundError(f"Repository not found for target identifier: '{target_path_or_id}'")


def get_engine(target=None):
    """
    Retrieves or initializes a CopilotEngine for target repo_id or active_repo_id.
    Reuses existing engines cached in engine_registry for zero re-indexing overhead on switch.
    """
    global active_repo_id, engine_registry

    target_id = target if target is not None else active_repo_id
    repo_id, repo_path = resolve_repo_path(target_id)

    if repo_id in engine_registry:
        return engine_registry[repo_id]

    print(f"[EngineRegistry] Initializing engine for repo_id '{repo_id}' at path: {repo_path}")
    engine = CopilotEngine(str(repo_path), repo_id=repo_id)
    engine_registry[repo_id] = engine
    return engine


def scan_available_repositories():
    """
    Scans DEFAULT_REPO_PATH and UPLOAD_WORKSPACE to list all valid repositories.
    Guarantees restart safety by discovering all existing uploaded repositories from disk.
    """
    repos = []

    # Default Repository
    if DEFAULT_REPO_PATH.exists():
        try:
            r_parser = RepoParser(str(DEFAULT_REPO_PATH))
            summary = r_parser.get_repo_summary()
            is_act = (active_repo_id == "default")
            is_lod = ("default" in engine_registry)
            fn_cnt = len(engine_registry["default"].dependencies) if is_lod else 0
            repos.append({
                "id": "default",
                "name": clean_repo_display_name(summary["project_name"]),
                "path": str(DEFAULT_REPO_PATH),
                "python_files": summary["total_python_files"],
                "folders": summary["total_folders"],
                "functions": fn_cnt,
                "is_active": is_act,
                "loaded": is_lod
            })
        except Exception as e:
            print(f"[Warning] Failed scanning default repo: {e}")

    # Uploaded Repositories
    if UPLOAD_WORKSPACE.exists():
        for item in sorted(UPLOAD_WORKSPACE.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not item.is_dir() or item.name.startswith("."):
                continue

            filtered = [p for p in item.iterdir() if p.name not in ["__MACOSX", ".DS_Store"]]
            top_py = [p for p in filtered if p.is_file() and p.suffix.lower() == ".py"]
            top_dirs = [p for p in filtered if p.is_dir()]
            eff_root = top_dirs[0] if (len(top_dirs) == 1 and len(top_py) == 0) else item

            try:
                r_parser = RepoParser(str(eff_root))
                py_files = r_parser.get_python_files()
                if not py_files:
                    continue
                summary = r_parser.get_repo_summary()
                r_id = item.name
                is_act = (active_repo_id == r_id)
                is_lod = (r_id in engine_registry)
                fn_cnt = len(engine_registry[r_id].dependencies) if is_lod else 0

                disp_name = clean_repo_display_name(summary["project_name"])

                repos.append({
                    "id": r_id,
                    "name": disp_name,
                    "path": str(eff_root),
                    "python_files": summary["total_python_files"],
                    "folders": summary["total_folders"],
                    "functions": fn_cnt,
                    "is_active": is_act,
                    "loaded": is_lod
                })
            except Exception as e:
                print(f"[Warning] Failed scanning repository '{item.name}': {e}")

    return repos


# ----------------------------------------------------------------------------
# Flask API Routes & CORS Setup
# ----------------------------------------------------------------------------

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/repository/overview", methods=["GET", "OPTIONS"])
def get_repository_overview_endpoint():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200

    target_repo_id = request.args.get("repo_id") or active_repo_id
    force_refresh = request.args.get("refresh", "false").lower() == "true"

    if not target_repo_id:
        return jsonify({
            "success": True,
            "status": "unselected",
            "active_repo_id": None,
            "message": "No repository selected. Please select or upload a repository to view overview.",
            "repositories": scan_available_repositories()
        }), 200

    try:
        eng = get_engine(target_repo_id)
        overview = eng.get_repository_overview(force_refresh=force_refresh)
        return jsonify(overview), 200
    except FileNotFoundError as fnf:
        return jsonify({"success": False, "error": str(fnf)}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to generate repository overview: {str(e)}"}), 500



@app.route("/api/repositories", methods=["GET", "OPTIONS"])
def list_repositories():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200
    try:
        repos = scan_available_repositories()
        return jsonify({
            "success": True,
            "active_repo_id": active_repo_id,
            "repositories": repos
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/switch_repo", methods=["POST", "OPTIONS"])
def switch_repo():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200

    global active_repo_id
    data = request.get_json(silent=True) or {}
    target_id = data.get("repo_id") or data.get("repo_path")

    if not target_id:
        return jsonify({"success": False, "error": "Field 'repo_id' or 'repo_path' is required."}), 400

    try:
        repo_id, repo_path = resolve_repo_path(target_id)
        active_repo_id = repo_id
        eng = get_engine(repo_id)

        repo_data = {
            "id": eng.repo_id,
            "name": eng.summary["project_name"],
            "path": str(eng.repo_path),
            "python_files": eng.summary["total_python_files"],
            "folders": eng.summary["total_folders"],
            "functions": len(eng.dependencies)
        }

        return jsonify({
            "success": True,
            "message": f"Switched active repository to '{eng.summary['project_name']}'.",
            "active_repo_id": active_repo_id,
            "suggested_questions": eng.get_suggested_questions(),
            "repository": repo_data,
            "repositories": scan_available_repositories()
        }), 200
    except FileNotFoundError as fnf:
        return jsonify({"success": False, "error": str(fnf)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to switch repository: {str(e)}"}), 500


@app.route("/api/status", methods=["GET", "OPTIONS"])
def get_status():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200
    try:
        if not active_repo_id:
            return jsonify({
                "success": True,
                "status": "unselected",
                "active_repo_id": None,
                "project_name": "No Repository Loaded",
                "repo_path": "",
                "total_files": 0,
                "total_folders": 0,
                "total_functions": 0,
                "suggested_questions": [],
                "repository": None,
                "repositories": scan_available_repositories()
            }), 200

        eng = get_engine()
        repo_data = {
            "id": eng.repo_id,
            "name": eng.summary["project_name"],
            "path": str(eng.repo_path),
            "python_files": eng.summary["total_python_files"],
            "folders": eng.summary["total_folders"],
            "functions": len(eng.dependencies)
        }
        return jsonify({
            "success": True,
            "status": "active",
            "active_repo_id": active_repo_id,
            "project_name": eng.summary["project_name"],
            "repo_path": str(eng.repo_path),
            "total_files": eng.summary["total_python_files"],
            "total_folders": eng.summary["total_folders"],
            "total_functions": len(eng.dependencies),
            "suggested_questions": eng.get_suggested_questions(),
            "repository": repo_data,
            "repositories": scan_available_repositories()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@app.route("/api/upload_repo", methods=["POST", "OPTIONS"])
def upload_repo():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200
    global active_repo_id
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded. Field 'file' is required."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file selected for upload."}), 400

    filename = file.filename
    if not filename.lower().endswith(".zip"):
        return jsonify({"success": False, "error": "Invalid file type. Only .zip archives are allowed."}), 400

    # Stream check for valid zip
    try:
        file.stream.seek(0)
        if not zipfile.is_zipfile(file.stream):
            return jsonify({"success": False, "error": "Uploaded file is corrupted or not a valid ZIP archive."}), 400
        file.stream.seek(0)
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to read ZIP stream: {str(e)}"}), 400

    # Extract inside application-managed directory
    original_stem = Path(filename).stem
    clean_stem = "".join(c for c in original_stem if c.isalnum() or c in ("-", "_")).strip() or "repo"
    repo_folder_id = f"{clean_stem}_{uuid.uuid4().hex[:6]}"
    extract_dir = UPLOAD_WORKSPACE / repo_folder_id
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        safe_extract_zip(file.stream, extract_dir)
    except ValueError as ve:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return jsonify({"success": False, "error": f"Failed to extract ZIP archive: {str(e)}"}), 400

    # Effective repository root resolution
    filtered_items = [p for p in extract_dir.iterdir() if p.name not in ["__MACOSX", ".DS_Store"]]
    top_py = [p for p in filtered_items if p.is_file() and p.suffix.lower() == ".py"]
    top_dirs = [p for p in filtered_items if p.is_dir()]

    if len(top_dirs) == 1 and len(top_py) == 0:
        effective_root = top_dirs[0]
    else:
        effective_root = extract_dir

    # Validate presence of Python files
    ignore_set = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".idea", ".vscode", "dist", "build"}
    py_files = []
    for p in effective_root.rglob("*.py"):
        if not any(part in ignore_set for part in p.parts):
            py_files.append(p)

    if not py_files:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return jsonify({"success": False, "error": "Uploaded repository contains no Python source (.py) files."}), 400

    # Switch active engine to newly uploaded repository
    try:
        active_repo_id = repo_folder_id
        eng = get_engine(repo_folder_id)

        repo_data = {
            "id": repo_folder_id,
            "name": eng.summary["project_name"],
            "path": str(eng.repo_path),
            "python_files": eng.summary["total_python_files"],
            "folders": eng.summary["total_folders"],
            "functions": len(eng.dependencies)
        }
        return jsonify({
            "success": True,
            "message": "Repository uploaded and loaded successfully.",
            "active_repo_id": active_repo_id,
            "suggested_questions": eng.get_suggested_questions(),
            "repository": repo_data,
            "repositories": scan_available_repositories()
        }), 200
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return jsonify({"success": False, "error": f"Failed to parse uploaded repository: {str(e)}"}), 500


@app.route("/api/analyze_repo", methods=["POST", "OPTIONS"])
def analyze_repo():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200
    global active_repo_id
    data = request.get_json(silent=True) or {}
    new_path = data.get("repo_path") or data.get("repo_id")

    if new_path:
        target_path = new_path
    else:
        target_path = active_repo_id

    try:
        repo_id, repo_path = resolve_repo_path(target_path)
        active_repo_id = repo_id
        eng = get_engine(repo_id)

        repo_data = {
            "id": repo_id,
            "name": eng.summary["project_name"],
            "path": str(eng.repo_path),
            "python_files": eng.summary["total_python_files"],
            "folders": eng.summary["total_folders"],
            "functions": len(eng.dependencies)
        }
        return jsonify({
            "success": True,
            "message": f"Successfully loaded repository: {eng.summary['project_name']}",
            "active_repo_id": active_repo_id,
            "suggested_questions": eng.get_suggested_questions(),
            "summary": {
                "project_name": eng.summary["project_name"],
                "repo_path": str(eng.repo_path),
                "total_python_files": eng.summary["total_python_files"],
                "total_folders": eng.summary["total_folders"],
                "total_functions": len(eng.dependencies)
            },
            "repository": repo_data,
            "repositories": scan_available_repositories()
        }), 200
    except FileNotFoundError as fnf:
        return jsonify({"success": False, "error": str(fnf)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/query", methods=["POST", "OPTIONS"])
def query_copilot():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200
    data = request.get_json(silent=True) or {}
    user_query = data.get("query", "")
    target_repo_id = data.get("repo_id")
    
    if not isinstance(user_query, str) or not user_query.strip():
        return jsonify({"success": False, "error": "Query string is required and cannot be empty."}), 400

    user_query = user_query.strip()
    if len(user_query) > 2000:
        return jsonify({"success": False, "error": "Query length exceeds maximum allowed length of 2000 characters."}), 400

    try:
        resolved_target = target_repo_id if target_repo_id else active_repo_id
        if not resolved_target:
            return jsonify({"success": False, "error": "No active repository selected. Please select or upload a repository to analyze."}), 400

        try:
            eng = get_engine(resolved_target)
        except FileNotFoundError:
            return jsonify({"success": False, "error": f"Repository '{resolved_target}' not found."}), 404

        print(f"[/api/query] repo_id='{eng.repo_id}' query='{user_query[:80]}'")
        result = eng.process_query(user_query)

        response_payload = {
            "success": True,
            "query": user_query,
            "repo_id": eng.repo_id,
            "query_type": result.get("query_type"),
            "sub_type": result.get("sub_type"),
            "answer": result.get("answer"),
            "citations": result.get("citations", []),
            "graph_url": result.get("graph_url", None)
        }

        if "risk" in result:
            response_payload["risk"] = result["risk"]
        if "impact_percentage" in result:
            response_payload["impact_percentage"] = result["impact_percentage"]

        return jsonify(response_payload), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/graph/<path:graph_name>", methods=["GET"])
def serve_api_graph(graph_name):
    safe_name = os.path.basename(graph_name)
    graph_path = GRAPH_DIR / safe_name

    if not graph_path.exists() and safe_name in ["dependency_graph.html", "impact_graph.html"]:
        prefix = safe_name.rsplit(".", 1)[0]
        active_target = active_repo_id or "default"
        active_graph_name = f"{prefix}_{active_target}.html"
        active_graph_path = GRAPH_DIR / active_graph_name
        if not active_graph_path.exists():
            try:
                eng = get_engine(active_target)
                if "dependency" in prefix:
                    eng.handle_dependency_graph()
                else:
                    funcs = list(eng.dependencies.keys())
                    target_fn = funcs[0] if funcs else "analyze"
                    eng.handle_impact_query(f"What if I change {target_fn}?")
            except Exception as e:
                print(f"[serve_api_graph] Error auto-generating graph: {e}")

        if active_graph_path.exists():
            return send_from_directory(GRAPH_DIR, active_graph_name)

    if not safe_name.endswith(".html") or not graph_path.exists():
        # Fallback: check BASE_DIR for legacy graph files
        legacy_path = BASE_DIR / safe_name
        if legacy_path.exists() and safe_name.endswith(".html"):
            return send_from_directory(BASE_DIR, safe_name)
        return jsonify({"success": False, "error": f"Graph file '{safe_name}' not found."}), 404

    return send_from_directory(GRAPH_DIR, safe_name)


@app.route("/graphs/<path:filename>", methods=["GET"])
def serve_graph_legacy(filename):
    return serve_api_graph(filename)


if __name__ == "__main__":
    print("Starting Flask AI Software Engineering Copilot...")
    flask_debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=flask_debug, use_reloader=False)

