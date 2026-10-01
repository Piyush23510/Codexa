"""
Phase 4D: Fully Qualified Symbol Name (FQSN) Dependency Resolver

Uses SymbolTable (Phase 4A), HierarchicalAST (Phase 4B), and ImportGraph (Phase 4C)
to statically resolve function and method calls to canonical FQSNs.

Resolves:
- Direct local function calls
- Imported functions and aliases
- Module-qualified calls (utils.similarity.clean_text)
- Module aliases (sim.clean_text)
- Self method calls (self.method())
- Class instantiations (User() → User.__init__)
- Instance method calls (user.save() where user = User())
- Ambiguous calls with multiple candidates (marked AMBIGUOUS, no arbitrary selection)
- External library calls (marked UNRESOLVED, excluded from local dependency graph)

Provides FQSNDependencyGraph with direct, reverse, and indirect dependency queries,
plus CompatibilityAdapter for legacy flat-name interfaces.
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from parser.import_graph import ImportGraph, ResolutionStatus
from parser.symbol_table import Symbol, SymbolTable, SymbolType, build_fqsn, file_to_module_path


class CallResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


@dataclass
class FQSNDependencyEdge:
    """
    Dependency relationship between a caller symbol and a callee symbol.
    """
    caller_fqsn: str
    callee_fqsn: Optional[str]
    caller_file: str
    callee_file: Optional[str]
    call_line: int
    resolution_status: CallResolutionStatus
    resolution_reason: str
    candidates: List[str] = field(default_factory=list)


class FQSNDependencyGraph:
    """
    Graph of FQSN dependency edges supporting direct, reverse, and indirect queries.
    """

    def __init__(self):
        self._edges: List[FQSNDependencyEdge] = []
        self._caller_to_edges: Dict[str, List[FQSNDependencyEdge]] = {}
        self._callee_to_edges: Dict[str, List[FQSNDependencyEdge]] = {}

    def add_edge(self, edge: FQSNDependencyEdge) -> None:
        """Add an edge to the graph and update lookup indexes."""
        self._edges.append(edge)

        if edge.caller_fqsn not in self._caller_to_edges:
            self._caller_to_edges[edge.caller_fqsn] = []
        self._caller_to_edges[edge.caller_fqsn].append(edge)

        if edge.resolution_status == CallResolutionStatus.RESOLVED and edge.callee_fqsn:
            if edge.callee_fqsn not in self._callee_to_edges:
                self._callee_to_edges[edge.callee_fqsn] = []
            self._callee_to_edges[edge.callee_fqsn].append(edge)

    def get_direct_dependencies(self, fqsn: str) -> List[FQSNDependencyEdge]:
        """Return direct outgoing call edges from fqsn."""
        return list(self._caller_to_edges.get(fqsn, []))

    def get_resolved_direct_dependencies(self, fqsn: str) -> List[FQSNDependencyEdge]:
        """Return only RESOLVED direct outgoing call edges from fqsn."""
        return [
            e for e in self._caller_to_edges.get(fqsn, [])
            if e.resolution_status == CallResolutionStatus.RESOLVED and e.callee_fqsn
        ]

    def get_reverse_dependencies(self, fqsn: str) -> List[FQSNDependencyEdge]:
        """Return direct incoming call edges targeting fqsn."""
        return list(self._callee_to_edges.get(fqsn, []))

    def get_indirect_dependencies(self, fqsn: str) -> List[str]:
        """
        Return transitive closure of all downstream callees reachable from fqsn.
        Implements BFS traversal with cycle detection.
        """
        visited = set()
        queue = [
            e.callee_fqsn for e in self.get_resolved_direct_dependencies(fqsn)
            if e.callee_fqsn
        ]
        indirect = []

        while queue:
            curr = queue.pop(0)
            if curr in visited or curr == fqsn:
                continue
            visited.add(curr)
            indirect.append(curr)

            for next_edge in self.get_resolved_direct_dependencies(curr):
                if next_edge.callee_fqsn and next_edge.callee_fqsn not in visited:
                    queue.append(next_edge.callee_fqsn)

        return indirect

    def get_impact_analysis(self, fqsn: str) -> Dict[str, List[str]]:
        """
        Return direct and indirect upstream callers that depend on fqsn.
        """
        direct_edges = self.get_reverse_dependencies(fqsn)
        direct_callers = sorted({e.caller_fqsn for e in direct_edges})

        visited = set(direct_callers)
        queue = list(direct_callers)
        indirect_callers = []

        while queue:
            curr = queue.pop(0)
            for prev_edge in self.get_reverse_dependencies(curr):
                caller = prev_edge.caller_fqsn
                if caller and caller not in visited and caller != fqsn:
                    visited.add(caller)
                    indirect_callers.append(caller)
                    queue.append(caller)

        return {
            "direct_impact": direct_callers,
            "indirect_impact": sorted(indirect_callers),
        }

    def all_edges(self) -> List[FQSNDependencyEdge]:
        """Return all edges in the graph."""
        return list(self._edges)

    def __len__(self) -> int:
        return len(self._edges)


class CallExpressionVisitor(ast.NodeVisitor):
    """
    AST Visitor that scans statements inside a single symbol scope,
    tracking local variable types and recording call edges.
    """

    def __init__(self, resolver: "FQSNDependencyResolver", caller_symbol: Symbol, alias_map: Dict, local_symbols: Dict):
        self.resolver = resolver
        self.caller_symbol = caller_symbol
        self.alias_map = alias_map
        self.local_symbols = local_symbols
        self.local_var_types: Dict[str, str] = {}
        self.edges: List[FQSNDependencyEdge] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Do not recurse into nested function definitions
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Do not recurse into nested async function definitions
        return

    def visit_Assign(self, node: ast.Assign) -> None:
        # Track local variable instantiation: e.g. user = User("test") or obj = Order()
        if isinstance(node.value, ast.Call):
            func_node = node.value.func
            type_name = None
            if isinstance(func_node, ast.Name):
                type_name = func_node.id
            elif isinstance(func_node, ast.Attribute):
                type_name = func_node.attr

            if type_name:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.local_var_types[target.id] = type_name

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        edge = self.resolver.resolve_call_node(
            node=node,
            caller_symbol=self.caller_symbol,
            alias_map=self.alias_map,
            local_symbols=self.local_symbols,
            local_var_types=self.local_var_types,
        )
        if edge:
            self.edges.append(edge)
        self.generic_visit(node)


class FQSNDependencyResolver:
    """
    Resolver that analyzes symbol AST bodies and produces an FQSNDependencyGraph.
    """

    def __init__(self, symbol_table: SymbolTable, import_graph: ImportGraph, repo_root: Path):
        self.symbol_table = symbol_table
        self.import_graph = import_graph
        self.repo_root = Path(repo_root).resolve()
        self.graph = FQSNDependencyGraph()

    def build_graph(self, file_paths: Optional[List[Path]] = None) -> FQSNDependencyGraph:
        """
        Build the complete FQSNDependencyGraph for all callable symbols in the repository.
        """
        self.graph = FQSNDependencyGraph()

        if file_paths is None:
            rel_files = {s.file_path for s in self.symbol_table._symbols.values()}
            abs_files = [self.repo_root / f for f in rel_files]
        else:
            abs_files = [Path(p).resolve() for p in file_paths]

        for abs_file in abs_files:
            if not abs_file.is_file():
                continue
            try:
                rel_file = str(abs_file.relative_to(self.repo_root)).replace("\\", "/")
                module_path = file_to_module_path(abs_file, self.repo_root)
            except ValueError:
                continue

            symbols_in_file = self.symbol_table.lookup_file(rel_file)
            if not symbols_in_file:
                continue

            try:
                content = abs_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(abs_file))
            except Exception:
                continue

            # Build alias map for current module from ImportGraph
            alias_map = self._build_alias_map(module_path)
            local_symbols = {s.name: s for s in symbols_in_file}

            # Map AST function/class nodes to Symbols
            self._process_file_ast(tree, symbols_in_file, alias_map, local_symbols)

        return self.graph

    def _build_alias_map(self, module_path: str) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """
        Build a scope map for imported names: alias_name → (imported_module, imported_symbol).
        """
        alias_map = {}
        records = self.import_graph.get_imports(module_path)

        for r in records:
            mod = r.resolved_module or r.imported_module
            if r.alias:
                alias_map[r.alias] = (mod, r.imported_symbol)
            elif r.imported_symbol:
                alias_map[r.imported_symbol] = (mod, r.imported_symbol)
            elif r.imported_module:
                # import foo.bar → foo is alias for top module
                top_name = r.imported_module.split(".")[0]
                alias_map[top_name] = (mod, None)
                alias_map[r.imported_module] = (mod, None)

        return alias_map

    def _process_file_ast(
        self,
        tree: ast.AST,
        symbols_in_file: List[Symbol],
        alias_map: Dict,
        local_symbols: Dict,
    ) -> None:
        """Walk file AST and extract call edges for matching callable symbols."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                matching_sym = self._find_matching_symbol(node, symbols_in_file)
                if not matching_sym:
                    continue

                visitor = CallExpressionVisitor(self, matching_sym, alias_map, local_symbols)
                for stmt in node.body:
                    visitor.visit(stmt)

                for edge in visitor.edges:
                    self.graph.add_edge(edge)

    def _find_matching_symbol(self, node: ast.AST, symbols_in_file: List[Symbol]) -> Optional[Symbol]:
        """Find the Symbol object corresponding to an AST FunctionDef node by name and start_line."""
        lineno = getattr(node, "lineno", -1)
        name = getattr(node, "name", "")

        for sym in symbols_in_file:
            if sym.name == name and sym.start_line == lineno:
                return sym

        # Fallback by name if line numbers slightly differ
        matches = [s for s in symbols_in_file if s.name == name]
        if len(matches) == 1:
            return matches[0]

        return None

    def _extract_dotted_attr(self, node: ast.AST) -> Optional[str]:
        """Extract dot-separated name string from nested ast.Attribute nodes."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._extract_dotted_attr(node.value)
            if base:
                return f"{base}.{node.attr}"
        return None

    def resolve_call_node(
        self,
        node: ast.Call,
        caller_symbol: Symbol,
        alias_map: Dict[str, Tuple[Optional[str], Optional[str]]],
        local_symbols: Dict[str, Symbol],
        local_var_types: Dict[str, str],
    ) -> Optional[FQSNDependencyEdge]:
        """
        Core resolution function: Maps an ast.Call node to an FQSNDependencyEdge.
        """
        func = node.func
        call_line = getattr(node, "lineno", caller_symbol.start_line)

        # 1. Direct Name Call: clean_text(data) or User("name") or Processor()
        if isinstance(func, ast.Name):
            name = func.id

            # a) Same-file Class instantiation
            local_sym = local_symbols.get(name)
            if local_sym and local_sym.symbol_type == SymbolType.CLASS:
                init_fqsn = f"{local_sym.fqsn}.__init__"
                target_fqsn = init_fqsn if init_fqsn in self.symbol_table else local_sym.fqsn
                target_sym = self.symbol_table.get(target_fqsn)
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=target_fqsn,
                    caller_file=caller_symbol.file_path,
                    callee_file=target_sym.file_path if target_sym else caller_symbol.file_path,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.RESOLVED,
                    resolution_reason="same-file class instantiation",
                )

            # b) Imported Symbol (Class or Function)
            if name in alias_map:
                mod_path, sym_name = alias_map[name]
                if mod_path and sym_name:
                    target_fqsn = build_fqsn(mod_path, [sym_name])
                    target_sym = self.symbol_table.get(target_fqsn)

                    # Check if imported symbol is a Class
                    if target_sym and target_sym.symbol_type == SymbolType.CLASS:
                        init_fqsn = f"{target_fqsn}.__init__"
                        final_fqsn = init_fqsn if init_fqsn in self.symbol_table else target_fqsn
                        f_sym = self.symbol_table.get(final_fqsn)
                        return FQSNDependencyEdge(
                            caller_fqsn=caller_symbol.fqsn,
                            callee_fqsn=final_fqsn,
                            caller_file=caller_symbol.file_path,
                            callee_file=f_sym.file_path if f_sym else target_sym.file_path,
                            call_line=call_line,
                            resolution_status=CallResolutionStatus.RESOLVED,
                            resolution_reason="imported class instantiation",
                        )

                    # Imported Function
                    if target_sym:
                        return FQSNDependencyEdge(
                            caller_fqsn=caller_symbol.fqsn,
                            callee_fqsn=target_fqsn,
                            caller_file=caller_symbol.file_path,
                            callee_file=target_sym.file_path,
                            call_line=call_line,
                            resolution_status=CallResolutionStatus.RESOLVED,
                            resolution_reason="explicit imported function",
                        )

            # c) Same-file function call
            if local_sym and local_sym.is_callable:
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=local_sym.fqsn,
                    caller_file=caller_symbol.file_path,
                    callee_file=local_sym.file_path,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.RESOLVED,
                    resolution_reason="same-file function call",
                )

            # d) Global SymbolTable lookup
            global_matches = [
                s for s in self.symbol_table.lookup_name(name)
                if s.is_callable
            ]
            if len(global_matches) == 1:
                target_sym = global_matches[0]
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=target_sym.fqsn,
                    caller_file=caller_symbol.file_path,
                    callee_file=target_sym.file_path,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.RESOLVED,
                    resolution_reason="unique global symbol match",
                )
            elif len(global_matches) > 1:
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=None,
                    caller_file=caller_symbol.file_path,
                    callee_file=None,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.AMBIGUOUS,
                    resolution_reason="multiple candidate symbols match bare name",
                    candidates=[s.fqsn for s in global_matches],
                )
            else:
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=None,
                    caller_file=caller_symbol.file_path,
                    callee_file=None,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.UNRESOLVED,
                    resolution_reason="unknown symbol",
                )

        # 2. Attribute Call: self.save() or sim.clean_text() or user.save() or User.save()
        elif isinstance(func, ast.Attribute):
            attr = func.attr

            # a) self.method() or cls.method()
            if isinstance(func.value, ast.Name) and func.value.id in ("self", "cls"):
                class_fqsn = caller_symbol.get_class_fqsn()
                if class_fqsn:
                    method_fqsn = f"{class_fqsn}.{attr}"
                    m_sym = self.symbol_table.get(method_fqsn)
                    if m_sym:
                        return FQSNDependencyEdge(
                            caller_fqsn=caller_symbol.fqsn,
                            callee_fqsn=method_fqsn,
                            caller_file=caller_symbol.file_path,
                            callee_file=m_sym.file_path,
                            call_line=call_line,
                            resolution_status=CallResolutionStatus.RESOLVED,
                            resolution_reason="self method call",
                        )

            # b) Object / Module attribute call (e.g. sim.clean_text or User.save or user.save)
            if isinstance(func.value, ast.Name):
                obj_name = func.value.id

                # Module alias call (import utils.similarity as sim → sim.clean_text)
                if obj_name in alias_map:
                    mod_path, sym_name = alias_map[obj_name]
                    if mod_path and not sym_name:
                        target_fqsn = build_fqsn(mod_path, [attr])
                        t_sym = self.symbol_table.get(target_fqsn)
                        if t_sym:
                            return FQSNDependencyEdge(
                                caller_fqsn=caller_symbol.fqsn,
                                callee_fqsn=target_fqsn,
                                caller_file=caller_symbol.file_path,
                                callee_file=t_sym.file_path,
                                call_line=call_line,
                                resolution_status=CallResolutionStatus.RESOLVED,
                                resolution_reason="module alias function call",
                            )

                    # Imported class method call (from models.user import User → User.save)
                    if mod_path and sym_name:
                        class_fqsn = build_fqsn(mod_path, [sym_name])
                        c_sym = self.symbol_table.get(class_fqsn)
                        if c_sym and c_sym.symbol_type == SymbolType.CLASS:
                            method_fqsn = f"{class_fqsn}.{attr}"
                            m_sym = self.symbol_table.get(method_fqsn)
                            if m_sym:
                                return FQSNDependencyEdge(
                                    caller_fqsn=caller_symbol.fqsn,
                                    callee_fqsn=method_fqsn,
                                    caller_file=caller_symbol.file_path,
                                    callee_file=m_sym.file_path,
                                    call_line=call_line,
                                    resolution_status=CallResolutionStatus.RESOLVED,
                                    resolution_reason="imported class method call",
                                )

                # Instance variable method call (user = User(...) → user.save())
                if obj_name in local_var_types:
                    type_name = local_var_types[obj_name]
                    class_sym = None
                    if type_name in alias_map:
                        m_path, s_name = alias_map[type_name]
                        if m_path and s_name:
                            class_sym = self.symbol_table.get(build_fqsn(m_path, [s_name]))
                    elif type_name in local_symbols:
                        class_sym = local_symbols[type_name]

                    if class_sym:
                        method_fqsn = f"{class_sym.fqsn}.{attr}"
                        m_sym = self.symbol_table.get(method_fqsn)
                        if m_sym:
                            return FQSNDependencyEdge(
                                caller_fqsn=caller_symbol.fqsn,
                                callee_fqsn=method_fqsn,
                                caller_file=caller_symbol.file_path,
                                callee_file=m_sym.file_path,
                                call_line=call_line,
                                resolution_status=CallResolutionStatus.RESOLVED,
                                resolution_reason="instance variable method call",
                            )

            # c) Dotted module access (utils.similarity.clean_text)
            dotted_path = self._extract_dotted_attr(func.value)
            if dotted_path:
                target_fqsn = build_fqsn(dotted_path, [attr])
                t_sym = self.symbol_table.get(target_fqsn)
                if t_sym:
                    return FQSNDependencyEdge(
                        caller_fqsn=caller_symbol.fqsn,
                        callee_fqsn=target_fqsn,
                        caller_file=caller_symbol.file_path,
                        callee_file=t_sym.file_path,
                        call_line=call_line,
                        resolution_status=CallResolutionStatus.RESOLVED,
                        resolution_reason="dotted module function call",
                    )

            # d) Global method lookup fallback for attribute calls
            global_matches = [
                s for s in self.symbol_table.lookup_name(attr)
                if s.symbol_type == SymbolType.METHOD
            ]
            if len(global_matches) == 1:
                target_sym = global_matches[0]
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=target_sym.fqsn,
                    caller_file=caller_symbol.file_path,
                    callee_file=target_sym.file_path,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.RESOLVED,
                    resolution_reason="unique global method match",
                )
            elif len(global_matches) > 1:
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=None,
                    caller_file=caller_symbol.file_path,
                    callee_file=None,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.AMBIGUOUS,
                    resolution_reason="multiple candidate methods match attribute name",
                    candidates=[s.fqsn for s in global_matches],
                )
            else:
                return FQSNDependencyEdge(
                    caller_fqsn=caller_symbol.fqsn,
                    callee_fqsn=None,
                    caller_file=caller_symbol.file_path,
                    callee_file=None,
                    call_line=call_line,
                    resolution_status=CallResolutionStatus.UNRESOLVED,
                    resolution_reason="unresolved attribute method call",
                )

        return None


class CompatibilityAdapter:
    """
    Adapter providing legacy flat function-name dependency queries
    while delegating underneath to FQSNDependencyGraph and SymbolTable.
    """

    def __init__(self, symbol_table: SymbolTable, fqsn_graph: FQSNDependencyGraph):
        self.symbol_table = symbol_table
        self.fqsn_graph = fqsn_graph

    def get_function_dependencies(self, bare_name: str) -> Dict[str, List[str]]:
        """
        Legacy interface: returns dict mapping function_name -> [called_function_names].
        If bare_name is ambiguous across files, maps all matching symbols safely.
        """
        symbols = self.symbol_table.lookup_name(bare_name)
        if not symbols:
            return {}

        result = {}
        for sym in symbols:
            edges = self.fqsn_graph.get_resolved_direct_dependencies(sym.fqsn)
            callee_names = []
            for e in edges:
                if e.callee_fqsn:
                    callee_sym = self.symbol_table.get(e.callee_fqsn)
                    name = callee_sym.name if callee_sym else e.callee_fqsn.split("::")[-1]
                    if name not in callee_names:
                        callee_names.append(name)
            result[sym.name] = callee_names

        return result

    def get_impact_analysis(self, bare_name: str) -> Dict[str, List[str]]:
        """
        Legacy impact analysis interface: returns dict with direct and indirect impacts by bare name.
        """
        symbols = self.symbol_table.lookup_name(bare_name)
        if not symbols:
            return {"direct_impact": [], "indirect_impact": []}

        direct = set()
        indirect = set()

        for sym in symbols:
            impact_res = self.fqsn_graph.get_impact_analysis(sym.fqsn)
            for d_fqsn in impact_res["direct_impact"]:
                s = self.symbol_table.get(d_fqsn)
                direct.add(s.name if s else d_fqsn.split("::")[-1])

            for i_fqsn in impact_res["indirect_impact"]:
                s = self.symbol_table.get(i_fqsn)
                name = s.name if s else i_fqsn.split("::")[-1]
                if name not in direct and name != bare_name:
                    indirect.add(name)

        return {
            "direct_impact": sorted(list(direct)),
            "indirect_impact": sorted(list(indirect)),
        }
