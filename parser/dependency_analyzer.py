"""
Phase 4E: Integrated FQSN Dependency Analyzer

Combines SymbolTable (4A), HierarchicalAST (4B), ImportGraph (4C), and
FQSNDependencyResolver (4D) to power Codexa's dependency and impact analysis.

Maintains complete backward compatibility for legacy flat function-name calls while
using FQSN identities internally to prevent same-named symbol collisions across modules and classes.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from parser.ast_parser import ASTParser
from parser.fqsn_resolver import (
    CallResolutionStatus,
    CompatibilityAdapter,
    FQSNDependencyEdge,
    FQSNDependencyGraph,
    FQSNDependencyResolver,
)
from parser.import_graph import ImportGraph
from parser.symbol_table import Symbol, SymbolTable, SymbolType, file_to_module_path


class DependencyAnalyzer:

    def __init__(self, files: List[str | Path], repo_root: Optional[str | Path] = None):
        self.files = [Path(f).resolve() for f in files if Path(f).exists()]

        # Determine repo_root
        if repo_root:
            self.repo_root = Path(repo_root).resolve()
        elif self.files:
            # Determine common root directory
            common = self.files[0].parent
            for f in self.files[1:]:
                try:
                    while not f.is_relative_to(common) and common != common.parent:
                        common = common.parent
                except AttributeError: # Python < 3.9 compatibility check if needed
                    common = common.parent
            self.repo_root = common
        else:
            self.repo_root = Path.cwd()

        # Phase 4 Infrastructure initialization
        self.symbol_table = SymbolTable()
        self.import_graph = ImportGraph()

        # Build symbol table for all files
        for f in self.files:
            try:
                parser = ASTParser(f)
                parser.get_symbol_tree(repo_root=self.repo_root, symbol_table=self.symbol_table)
            except Exception as e:
                print(f"[DependencyAnalyzer] Warning: AST symbol extraction failed for '{f}': {e}")

        # Build import graph for repository
        try:
            self.import_graph.build_from_repository(self.repo_root, file_paths=self.files)
        except Exception as e:
            print(f"[DependencyAnalyzer] Warning: ImportGraph build failed: {e}")

        # Build FQSN dependency resolver and graph
        self.resolver = FQSNDependencyResolver(
            symbol_table=self.symbol_table,
            import_graph=self.import_graph,
            repo_root=self.repo_root,
        )
        self.fqsn_graph = self.resolver.build_graph(file_paths=self.files)
        self.adapter = CompatibilityAdapter(self.symbol_table, self.fqsn_graph)

    def get_function_dependencies(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Returns (dependencies, reverse_dependencies) mapping function names to called function names.

        Uses FQSN identities internally to ensure duplicate symbol names in different modules/classes
        do not collide or overwrite each other.
        """
        dependencies: Dict[str, List[str]] = {}
        reverse_dependencies: Dict[str, List[str]] = {}

        # Collect caller symbols
        all_symbols = [
            s for s in self.symbol_table._symbols.values()
            if s.is_callable
        ]

        for sym in all_symbols:
            # Use bare name if unique across repository, else use full FQSN
            key = sym.name if len(self.symbol_table.lookup_name(sym.name)) == 1 else sym.fqsn
            edges = self.fqsn_graph.get_resolved_direct_dependencies(sym.fqsn)

            callee_keys = []
            for edge in edges:
                if edge.callee_fqsn:
                    callee_sym = self.symbol_table.get(edge.callee_fqsn)
                    if callee_sym:
                        c_key = callee_sym.name if len(self.symbol_table.lookup_name(callee_sym.name)) == 1 else callee_sym.fqsn
                    else:
                        c_key = edge.callee_fqsn.split("::")[-1]

                    if c_key not in callee_keys:
                        callee_keys.append(c_key)

            dependencies[key] = callee_keys

            # If duplicate bare names exist, also populate bare name key if not present
            if sym.name not in dependencies:
                dependencies[sym.name] = list(callee_keys)

        # Build reverse_dependencies dict
        for caller_key, callee_keys in dependencies.items():
            for c_key in callee_keys:
                if c_key not in reverse_dependencies:
                    reverse_dependencies[c_key] = []
                if caller_key not in reverse_dependencies[c_key]:
                    reverse_dependencies[c_key].append(caller_key)

        return dependencies, reverse_dependencies

    def get_fqsn_dependencies(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Returns (fqsn_dependencies, fqsn_reverse_dependencies) keyed strictly by FQSN strings.
        """
        fqsn_deps: Dict[str, List[str]] = {}
        fqsn_rev: Dict[str, List[str]] = {}

        for fqsn in self.symbol_table.all_callable_fqsns():
            edges = self.fqsn_graph.get_resolved_direct_dependencies(fqsn)
            callees = sorted({e.callee_fqsn for e in edges if e.callee_fqsn})
            fqsn_deps[fqsn] = callees

            for c in callees:
                if c not in fqsn_rev:
                    fqsn_rev[c] = []
                fqsn_rev[c].append(fqsn)

        return fqsn_deps, fqsn_rev

    def get_indirect_dependencies(
        self,
        function_name: str,
        dependencies: Optional[Dict[str, List[str]]] = None,
        visited: Optional[Set[str]] = None,
        is_root: bool = True
    ) -> Set[str]:
        """
        Return transitive indirect dependencies for function_name.

        Uses FQSNDependencyGraph if function_name maps to registered FQSN,
        falling back to cycle-safe dictionary traversal for synthetic inputs.
        """
        syms = self.symbol_table.lookup_name(function_name)
        if not syms and function_name in self.symbol_table:
            syms = [self.symbol_table.get(function_name)]

        # If matching symbols exist in SymbolTable and input is standard
        if syms and (dependencies is None or not any(k for k in dependencies if "::" not in k and k not in [s.name for s in syms])):
            indirect_fqsns = set()
            for s in syms:
                indirect_fqsns.update(self.fqsn_graph.get_indirect_dependencies(s.fqsn))

            result = set()
            for fqsn in indirect_fqsns:
                sym = self.symbol_table.get(fqsn)
                if sym:
                    name = sym.name if len(self.symbol_table.lookup_name(sym.name)) == 1 else sym.fqsn
                else:
                    name = fqsn.split("::")[-1]
                result.add(name)
            return result

        # Fallback for synthetic dictionary inputs (e.g. unit tests with custom dicts)
        if dependencies is None:
            return set()

        if visited is None:
            visited = set()

        indirect = set()
        for called_function in dependencies.get(function_name, []):
            if called_function in visited:
                continue
            visited.add(called_function)
            res = self.get_indirect_dependencies(called_function, dependencies, visited, is_root=False)
            indirect.update(res)
            if not is_root:
                indirect.add(called_function)

        return indirect

    def get_impact_analysis(
        self,
        changed_function: str,
        reverse_dependencies: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[Set[str], Set[str]]:
        """
        Return (direct_impact, indirect_impact) sets of caller names affected by changed_function.
        """
        syms = self.symbol_table.lookup_name(changed_function)
        if not syms and changed_function in self.symbol_table:
            syms = [self.symbol_table.get(changed_function)]

        if syms:
            direct_res = set()
            indirect_res = set()

            for s in syms:
                impact_dict = self.fqsn_graph.get_impact_analysis(s.fqsn)

                for d_fqsn in impact_dict["direct_impact"]:
                    dsym = self.symbol_table.get(d_fqsn)
                    d_name = dsym.name if dsym and len(self.symbol_table.lookup_name(dsym.name)) == 1 else d_fqsn
                    direct_res.add(d_name)

                for i_fqsn in impact_dict["indirect_impact"]:
                    isym = self.symbol_table.get(i_fqsn)
                    i_name = isym.name if isym and len(self.symbol_table.lookup_name(isym.name)) == 1 else i_fqsn
                    if i_name not in direct_res and i_name != changed_function:
                        indirect_res.add(i_name)

            direct_res.discard(changed_function)
            indirect_res.discard(changed_function)
            return direct_res, indirect_res

        # Fallback for synthetic dictionary inputs
        if reverse_dependencies is None:
            return set(), set()

        direct_impact = set()
        indirect_impact = set()
        visited = {changed_function}

        def find_impact(func, is_direct=True):
            for caller in reverse_dependencies.get(func, []):
                if caller in visited:
                    continue
                visited.add(caller)
                if is_direct:
                    direct_impact.add(caller)
                else:
                    indirect_impact.add(caller)
                find_impact(caller, is_direct=False)

        find_impact(changed_function)
        indirect_impact -= direct_impact
        direct_impact.discard(changed_function)
        indirect_impact.discard(changed_function)

        return direct_impact, indirect_impact

    def calculate_risk(self, direct_impact, indirect_impact) -> str:
        """Calculate risk level based on total affected functions."""
        total = len(direct_impact) + len(indirect_impact)
        if total == 0:
            return "LOW"
        elif total <= 2:
            return "MEDIUM"
        else:
            return "HIGH"

    def impact_percentage(self, direct_impact, indirect_impact, total_functions: int) -> float:
        """Calculate percentage of repository functions impacted."""
        if total_functions == 0:
            return 0.0
        total = len(direct_impact) + len(indirect_impact)
        return (total / total_functions) * 100.0

    def get_function_details(self, function_name: str) -> Optional[Dict]:
        """
        Extract details (file, start_line, end_line, arguments, code, fqsn) for function_name.
        """
        syms = self.symbol_table.lookup_name(function_name)
        if not syms and function_name in self.symbol_table:
            syms = [self.symbol_table.get(function_name)]

        if syms:
            sym = syms[0]
            abs_path = self.repo_root / sym.file_path
            return {
                "name": sym.name,
                "fqsn": sym.fqsn,
                "file": str(abs_path if abs_path.exists() else sym.file_path),
                "file_path": sym.file_path,
                "start_line": sym.start_line,
                "end_line": sym.end_line,
                "arguments": sym.arguments,
                "code": sym.source_code or "",
                "is_ambiguous": len(syms) > 1,
                "candidates": [s.fqsn for s in syms] if len(syms) > 1 else [],
            }

        # Fallback scanner
        for file_path in self.files:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    code = file.read()
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == function_name:
                            arguments = [arg.arg for arg in node.args.args if arg.arg != "self"]
                            function_code = ast.get_source_segment(code, node)
                            return {
                                "name": node.name,
                                "file": str(file_path),
                                "start_line": node.lineno,
                                "end_line": node.end_lineno,
                                "arguments": arguments,
                                "code": function_code or "",
                            }
            except Exception:
                continue

        return None

    def get_repository_workflow(
        self,
        dependencies: Optional[Dict[str, List[str]]] = None,
        reverse_dependencies: Optional[Dict[str, List[str]]] = None,
    ) -> Dict:
        """
        Determine repository entry points and main workflow chain.
        """
        if dependencies is None or reverse_dependencies is None:
            dependencies, reverse_dependencies = self.get_function_dependencies()

        entry_points = [f for f in dependencies if f not in reverse_dependencies]

        def get_reachable(function_name, visited=None):
            if visited is None:
                visited = set()
            for called in dependencies.get(function_name, []):
                if called not in visited:
                    visited.add(called)
                    get_reachable(called, visited)
            return visited

        main_entry = None
        largest_workflow: Set[str] = set()

        for ep in entry_points:
            reachable = get_reachable(ep)
            if len(reachable) > len(largest_workflow):
                largest_workflow = reachable
                main_entry = ep

        return {
            "main_entry_point": main_entry,
            "workflow": list(largest_workflow),
        }