"""
Overview Service for Detailed Repository Overview & Developer Onboarding.

Collects deterministic repository facts using existing Phase 4 components:
- SymbolTable (4A)
- HierarchicalASTVisitor (4B)
- ImportGraph (4C)
- FQSNDependencyResolver & FQSNDependencyGraph (4D)
- DependencyAnalyzer (4E)
- RepoParser

Provides grounded repository facts for UI display and LLM summary generation.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from parser.dependency_analyzer import DependencyAnalyzer
from parser.import_graph import ImportGraph, ResolutionStatus
from parser.repo_parser import RepoParser
from parser.symbol_table import SymbolTable, SymbolType, file_to_module_path


STD_LIB_MODULES = {
    "os", "sys", "ast", "json", "math", "re", "typing", "pathlib", "uuid",
    "zipfile", "shutil", "time", "dataclasses", "enum", "collections",
    "functools", "itertools", "io", "copy", "threading", "multiprocessing",
    "subprocess", "inspect", "importlib", "unittest", "logging", "hashlib",
    "datetime", "urllib", "traceback", "tempfile", "glob", "base64", "socket",
    "sqlite3", "xml", "csv", "random", "string", "warnings"
}

IGNORE_DIRS = {
    "__pycache__", ".git", ".pytest_cache", "venv", ".venv", "node_modules",
    ".idea", ".vscode", "dist", "build", "uploaded_repositories", "graphs",
    "brain", "scratch", "__MACOSX"
}


class OverviewService:
    """
    Service responsible for extracting deterministic facts, statistics,
    component rankings, exploration paths, and starter questions for any Python repository.
    """

    def __init__(
        self,
        repo_path: str | Path,
        dependency_analyzer: Optional[DependencyAnalyzer] = None,
        files: Optional[List[str | Path]] = None,
        repo_id: Optional[str] = None
    ):
        self.repo_path = Path(repo_path).resolve()
        self.repo_id = repo_id or self.repo_path.name

        # Parse repository structure
        self.repo_parser = RepoParser(str(self.repo_path))
        self.summary = self.repo_parser.get_repo_summary()

        if files is not None:
            self.files = [Path(f).resolve() for f in files if Path(f).exists()]
        else:
            self.files = [Path(f).resolve() for f in self.repo_parser.get_python_files()]

        # Use or build Phase 4 DependencyAnalyzer
        if dependency_analyzer is not None:
            self.analyzer = dependency_analyzer
        else:
            self.analyzer = DependencyAnalyzer(self.files, repo_root=self.repo_path)

        self.symbol_table: SymbolTable = self.analyzer.symbol_table
        self.import_graph: ImportGraph = self.analyzer.import_graph
        self.fqsn_graph = self.analyzer.fqsn_graph

    def _rel_path(self, path: str | Path) -> str:
        """Helper to get a clean repository-relative string path."""
        p = Path(path).resolve()
        try:
            return str(p.relative_to(self.repo_path)).replace("\\", "/")
        except ValueError:
            return str(p.name)

    def _mod_path(self, path: str | Path) -> str:
        """Helper to get canonical module path safely."""
        try:
            return file_to_module_path(path, self.repo_path)
        except Exception:
            p = Path(path)
            parts = [part for part in p.parts if part not in (".", "..")]
            if not parts:
                return "module"
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__" and len(parts) > 1:
                parts.pop()
            return ".".join(parts)


    def detect_entry_points(self) -> List[Dict[str, Any]]:
        """
        Detect repository entry points deterministically using file names, AST patterns,
        Flask/FastAPI routes, CLI decorators, and main functions.
        """
        entry_points = []
        entry_filenames = {"app.py", "main.py", "run.py", "server.py", "cli.py", "manage.py", "index.py", "wsgi.py", "asgi.py"}

        for file_path in self.files:
            rel_file = self._rel_path(file_path)
            file_name = file_path.name.lower()
            is_entry = False
            reasons = []

            if file_name in entry_filenames:
                is_entry = True
                reasons.append(f"Standard entry point file name ({file_path.name})")

            # Inspect AST for entry point signatures
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    # Check for `if __name__ == '__main__':`
                    if isinstance(node, ast.If):
                        if isinstance(node.test, ast.Compare):
                            left = node.test.left
                            if isinstance(left, ast.Name) and left.id == "__name__":
                                is_entry = True
                                if "main block" not in reasons:
                                    reasons.append("Contains `if __name__ == '__main__':` execution block")

                    # Check for Flask / FastAPI / Click / Argparse / Route decorators
                    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                        if node.name == "main":
                            is_entry = True
                            if "main() function" not in reasons:
                                reasons.append("Defines `main()` function")
                        for decorator in node.decorator_list:
                            dec_str = ast.unparse(decorator) if hasattr(ast, "unparse") else ""
                            if any(kw in dec_str for kw in ["route", "get", "post", "put", "delete", "command", "cli"]):
                                is_entry = True
                                if "API routes or CLI commands" not in reasons:
                                    reasons.append("Defines API route handlers or CLI commands")

                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id in ("app", "application", "router", "api"):
                                is_entry = True
                                if "Web application instance" not in reasons:
                                    reasons.append(f"Instantiates web application `{target.id}`")

            except Exception:
                pass

            if is_entry:
                entry_points.append({
                    "file": rel_file,
                    "module": self._mod_path(rel_file),
                    "type": "Application Entry Point",
                    "reasons": reasons,
                    "description": f"Entry point detected via {', '.join(reasons)}."
                })


        return entry_points

    def get_structure_fact(self) -> Dict[str, Any]:
        """
        Detect important directories, config files, test directories, documentation files.
        """
        directories: Dict[str, Dict[str, Any]] = {}
        config_files = []
        test_directories = []
        doc_files = []

        config_names = {
            "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
            "pipfile", ".env.example", "dockerfile", "docker-compose.yml",
            "config.py", "settings.py"
        }
        doc_names = {"readme.md", "contributing.md", "changelog.md", "architecture.md", "license"}

        # Scan repository root and subdirectories
        for item in self.repo_path.rglob("*"):
            if any(part in IGNORE_DIRS for part in item.parts):
                continue

            rel_item = self._rel_path(item)
            item_lower = item.name.lower()

            if item.is_file():
                if item_lower in config_names or item.suffix in (".toml", ".ini", ".env"):
                    config_files.append({"file": rel_item, "type": "Configuration File"})
                elif item_lower in doc_names or item.suffix == ".md":
                    doc_files.append({"file": rel_item, "type": "Documentation"})

            elif item.is_dir():
                folder_name = item.name.lower()

                # Categorize directory
                role = None
                if folder_name in ("tests", "test", "testing", "spec"):
                    role = "Test Suite & Behavioral Verification"
                    test_directories.append({"name": rel_item, "role": role})
                elif folder_name in ("api", "routes", "controllers", "endpoints", "views", "handlers", "server", "backend"):
                    role = "API & Route Controllers"
                elif folder_name in ("services", "parser", "core", "logic", "domain", "processors"):
                    role = "Core Business Logic & Processing Services"
                elif folder_name in ("rag", "retrieval", "llm", "embeddings", "search", "ai"):
                    role = "Retrieval, Vector Search & LLM Engine"
                elif folder_name in ("models", "schemas", "entities", "db", "data"):
                    role = "Data Models & Schemas"
                elif folder_name in ("static", "templates", "ui", "frontend", "components"):
                    role = "Frontend & UI Assets"
                elif folder_name in ("utils", "helpers", "common", "lib"):
                    role = "Utilities & Common Helpers"

                if role:
                    py_count = len(list(item.glob("*.py")))
                    directories[rel_item] = {
                        "name": rel_item,
                        "role": role,
                        "python_files_count": py_count
                    }

        return {
            "important_directories": list(directories.values()),
            "config_files": config_files,
            "test_directories": test_directories,
            "doc_files": doc_files
        }

    def get_important_components(self) -> List[Dict[str, Any]]:
        """
        Identify and rank important components using deterministic signals:
        - Application entry points (+10)
        - Import indegree (+2 per incoming import)
        - Symbol density (+1 per class/function)
        - Call graph edge centrality (+1 per call edge)
        - Configuration/manifest (+5)
        """
        entry_points = {ep["file"] for ep in self.detect_entry_points()}

        # Calculate import indegree (how many other local modules import a given module)
        import_indegree: Dict[str, int] = {}
        for record in self.import_graph._records:
            if record.resolution_status == ResolutionStatus.LOCAL and record.resolved_module:
                target_mod = record.resolved_module
                import_indegree[target_mod] = import_indegree.get(target_mod, 0) + 1

        components = []

        for file_path in self.files:
            rel_file = self._rel_path(file_path)
            module_path = self._mod_path(rel_file)


            # Collect symbols defined in this file from symbol table
            file_symbols = [
                sym for sym in self.symbol_table._symbols.values()
                if sym.file_path == rel_file or self._rel_path(sym.file_path) == rel_file
            ]

            classes = [s for s in file_symbols if s.symbol_type == SymbolType.CLASS]
            functions = [s for s in file_symbols if s.symbol_type in (SymbolType.FUNCTION, SymbolType.METHOD)]

            # Compute centrality from FQSN dependency graph
            call_edges_count = 0
            for sym in file_symbols:
                calls = self.fqsn_graph.get_resolved_direct_dependencies(sym.fqsn)
                callers = self.fqsn_graph.get_reverse_dependencies(sym.fqsn)
                call_edges_count += len(calls) + len(callers)


            indegree = import_indegree.get(module_path, 0)
            is_entry = rel_file in entry_points

            score = 0
            if is_entry:
                score += 10
            score += (indegree * 2)
            score += len(classes) * 2
            score += len(functions) * 1
            score += min(call_edges_count, 10)

            # Determine component type
            comp_type = "Core Module"
            if is_entry:
                comp_type = "Application Entry Point"
            elif any(part in rel_file.lower() for part in ["service", "logic", "parser", "core", "processor"]):
                comp_type = "Business Service"
            elif any(part in rel_file.lower() for part in ["model", "schema", "entity"]):
                comp_type = "Data Model"
            elif any(part in rel_file.lower() for part in ["api", "route", "controller", "endpoint"]):
                comp_type = "API Controller"
            elif any(part in rel_file.lower() for part in ["rag", "retriever", "vector", "llm", "embed"]):
                comp_type = "Retrieval & AI Engine"
            elif any(part in rel_file.lower() for part in ["util", "helper", "common"]):
                comp_type = "Utility Module"

            # Format top important symbols
            important_symbols = []
            for c in classes[:3]:
                important_symbols.append({
                    "name": c.display_name,
                    "type": "class",
                    "fqsn": c.fqsn,
                    "line": c.start_line,
                    "docstring": (c.docstring or "").strip().split("\n")[0] if c.docstring else ""
                })
            for f in functions[:4]:
                important_symbols.append({
                    "name": f.display_name,
                    "type": "function",
                    "fqsn": f.fqsn,
                    "line": f.start_line,
                    "docstring": (f.docstring or "").strip().split("\n")[0] if f.docstring else ""
                })

            # Extract module docstring or description summary
            module_doc = ""
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                parsed = ast.parse(content, filename=str(file_path))
                doc = ast.get_docstring(parsed)
                if doc:
                    module_doc = doc.strip().split("\n")[0]
            except Exception:
                pass

            if not module_doc:
                module_doc = f"Defines {len(classes)} classes and {len(functions)} functions for {module_path}."

            components.append({
                "file_path": rel_file,
                "module_path": module_path,
                "component_type": comp_type,
                "importance_score": score,
                "classes_count": len(classes),
                "functions_count": len(functions),
                "import_indegree": indegree,
                "important_symbols": important_symbols,
                "description": module_doc
            })

        # Sort by importance score descending
        components.sort(key=lambda x: x["importance_score"], reverse=True)
        return components

    def get_architecture_facts(self) -> Dict[str, Any]:
        """
        Derive high-level module architecture and key component relationships
        using ImportGraph and FQSNDependencyGraph.
        """
        local_edges = []
        seen_edges = set()

        for record in self.import_graph._records:
            if record.resolution_status == ResolutionStatus.LOCAL and record.resolved_module:
                src = record.source_module
                dst = record.resolved_module
                if src != dst and (src, dst) not in seen_edges:
                    seen_edges.add((src, dst))
                    local_edges.append({
                        "from_module": src,
                        "to_module": dst,
                        "type": "import",
                        "raw_statement": record.raw_statement
                    })

        # Extract major modules (packages or top-level python files)
        modules_map: Dict[str, Dict[str, Any]] = {}
        for sym in self.symbol_table._symbols.values():
            mod = sym.module_path
            if mod not in modules_map:
                modules_map[mod] = {
                    "module_path": mod,
                    "file_path": self._rel_path(sym.file_path),
                    "classes_count": 0,
                    "functions_count": 0
                }
            if sym.symbol_type == SymbolType.CLASS:
                modules_map[mod]["classes_count"] += 1
            elif sym.symbol_type in (SymbolType.FUNCTION, SymbolType.METHOD):
                modules_map[mod]["functions_count"] += 1

        important_comps = self.get_important_components()
        central_comps = [c["file_path"] for c in important_comps[:5]]

        return {
            "major_modules": list(modules_map.values()),
            "central_components": central_comps,
            "key_relationships": local_edges[:15]
        }

    def get_external_dependencies(self) -> List[str]:
        """Extract third-party external dependencies imported across the codebase."""
        external_deps = set()
        for record in self.import_graph._records:
            if record.resolution_status == ResolutionStatus.EXTERNAL:
                top_pkg = record.imported_module.split(".")[0]
                if top_pkg and top_pkg not in STD_LIB_MODULES and not top_pkg.startswith("_"):
                    external_deps.add(top_pkg)
        return sorted(list(external_deps))

    def get_exploration_path(self) -> List[Dict[str, Any]]:
        """
        Generate a dynamic 4-step onboarding exploration path for developers.
        """
        entry_points = self.detect_entry_points()
        important_comps = self.get_important_components()
        struct = self.get_structure_fact()

        step1_target = entry_points[0]["file"] if entry_points else (important_comps[0]["file_path"] if important_comps else "app.py")
        step1_desc = f"Main application entry point. Start here to understand initialization and request/execution flow."

        # Step 2: Core service or business logic
        non_entry_comps = [c for c in important_comps if c["file_path"] != step1_target]
        step2_target = non_entry_comps[0]["file_path"] if non_entry_comps else "services/"
        step2_role = non_entry_comps[0]["component_type"] if non_entry_comps else "Core Business Logic"
        step2_desc = f"Central domain component ({non_entry_comps[0]['module_path'] if non_entry_comps else 'business logic'}). Key functions and domain algorithms reside here."

        # Step 3: Secondary logic, data models, or RAG engine
        step3_comp = non_entry_comps[1] if len(non_entry_comps) > 1 else (non_entry_comps[0] if non_entry_comps else None)
        step3_target = step3_comp["file_path"] if step3_comp else "models/"
        step3_role = step3_comp["component_type"] if step3_comp else "Supporting Services & Schemas"
        step3_desc = f"Supporting module ({step3_comp['module_path'] if step3_comp else 'data structures'}). Check this for data definitions, vector retrieval, or helper utilities."

        # Step 4: Test directory or verification suite
        test_dirs = struct["test_directories"]
        step4_target = test_dirs[0]["name"] if test_dirs else "tests/"
        step4_desc = "Automated test suite. Inspect unit and integration tests to verify expected system behavior and API contracts."

        return [
            {"step": 1, "target": step1_target, "role": "Application Entry Point", "reason": step1_desc},
            {"step": 2, "target": step2_target, "role": step2_role, "reason": step2_desc},
            {"step": 3, "target": step3_target, "role": step3_role, "reason": step3_desc},
            {"step": 4, "target": step4_target, "role": "Test Suite & Verification", "reason": step4_desc}
        ]

    def get_suggested_questions(self) -> List[str]:
        """Generate repository-specific starter questions."""
        proj_name = self.summary.get("project_name", self.repo_id)
        important_components = self.get_important_components()

        suggested_questions = [
            f"How is {proj_name} structured?",
            "What is the main entry point and how does it execute?",
            f"Explain the architecture and main components of {proj_name}."
        ]

        if important_components:
            top_comp = important_components[0]
            suggested_questions.append(f"What does `{top_comp['file_path']}` do?")
            suggested_questions.append(f"Which modules depend on `{top_comp['module_path']}`?")
            if top_comp["important_symbols"]:
                sym_name = top_comp["important_symbols"][0]["name"]
                suggested_questions.append(f"What would be affected if I modify `{sym_name}`?")
            if len(important_components) > 1:
                comp2 = important_components[1]
                suggested_questions.append(f"How do `{top_comp['module_path']}` and `{comp2['module_path']}` interact?")

        return suggested_questions


    def collect_facts(self) -> Dict[str, Any]:
        """
        Collect full structured deterministic facts for the repository.
        """
        entry_points = self.detect_entry_points()
        structure_fact = self.get_structure_fact()
        important_components = self.get_important_components()
        architecture_facts = self.get_architecture_facts()
        external_deps = self.get_external_dependencies()

        # Compute statistics
        symbols = list(self.symbol_table._symbols.values())
        classes_count = sum(1 for s in symbols if s.symbol_type == SymbolType.CLASS)
        functions_count = sum(1 for s in symbols if s.symbol_type == SymbolType.FUNCTION)
        methods_count = sum(1 for s in symbols if s.symbol_type == SymbolType.METHOD)
        modules_count = len({s.module_path for s in symbols})
        imports_count = len(self.import_graph._records)

        # Count total files in repo
        total_files = len([p for p in self.repo_path.rglob("*") if p.is_file() and not any(part in IGNORE_DIRS for part in p.parts)])

        statistics = {
            "total_files": max(total_files, len(self.files)),
            "total_python_files": len(self.files),
            "total_classes": classes_count,
            "total_functions": functions_count,
            "total_methods": methods_count,
            "total_modules": modules_count,
            "total_imports": imports_count,
            "total_local_dependencies": len(architecture_facts["key_relationships"])
        }

        proj_name = self.summary.get("project_name", self.repo_id)
        suggested_questions = self.get_suggested_questions()


        return {
            "repository": {
                "id": self.repo_id,
                "name": proj_name,
                "path": str(self.repo_path)
            },
            "statistics": statistics,
            "structure": structure_fact,
            "entry_points": entry_points,
            "important_components": important_components[:10],
            "architecture": architecture_facts,
            "dependencies": {
                "top_local_modules": [m["module_path"] for m in architecture_facts["major_modules"][:5]],
                "external_dependencies": external_deps
            },
            "exploration_path": self.get_exploration_path(),
            "suggested_questions": suggested_questions
        }
