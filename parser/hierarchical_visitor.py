"""
Phase 4B: Hierarchical AST Scope-Stack Visitor

Traverses Python AST using a scope stack to extract hierarchical symbols:
- Module
  └── Class
       ├── Method
       │    └── Nested Function
       └── Method
  └── Function
       └── Nested Function

Preserves nesting relationships, scope boundaries, docstrings, argument signatures,
async status, source code lines, and maps symbols to canonical FQSNs in a SymbolTable.
"""

import ast
from pathlib import Path
from typing import List, Optional, Union

from parser.symbol_table import (
    Symbol,
    SymbolTable,
    SymbolType,
    build_fqsn,
    file_to_module_path,
)


class HierarchicalASTVisitor(ast.NodeVisitor):
    """
    AST Visitor that uses a scope stack to extract hierarchical Symbol objects.

    Maintains:
    - scope_stack: List of bare scope names (e.g. ["User", "save", "validate"])
    - parent_fqsn_stack: List of corresponding FQSNs for parent calculation
    - scope_kind_stack: Stack tracking parent symbol types (CLASS, FUNCTION, etc.)
    - symbol_table: SymbolTable instance storing extracted symbols
    """

    def __init__(
        self,
        file_path: Path,
        repo_root: Path,
        source_lines: Optional[List[str]] = None,
        symbol_table: Optional[SymbolTable] = None,
    ):
        self.file_path = Path(file_path)
        self.repo_root = Path(repo_root)

        # Compute relative file path and module path using canonical utility
        try:
            abs_file = self.file_path.resolve()
            abs_root = self.repo_root.resolve()
            rel_path = abs_file.relative_to(abs_root)
            self.rel_file_path = str(rel_path).replace("\\", "/")
        except ValueError:
            self.rel_file_path = self.file_path.name

        self.module_path = file_to_module_path(self.file_path, self.repo_root)
        self.source_lines = source_lines or []
        self.symbol_table = symbol_table if symbol_table is not None else SymbolTable()

        # Scope state
        self.scope_stack: List[str] = []
        self.parent_fqsn_stack: List[str] = []
        self.scope_kind_stack: List[SymbolType] = []

    def _extract_source(self, node: ast.AST) -> Optional[str]:
        """Extract source code for an AST node if source_lines are available."""
        if not self.source_lines or not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            return None
        start = node.lineno - 1
        end = node.end_lineno
        return "\n".join(self.source_lines[start:end])

    def _extract_arguments(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> List[str]:
        """Extract argument names for function/method definitions."""
        arguments = []
        is_method = bool(
            self.scope_kind_stack and self.scope_kind_stack[-1] == SymbolType.CLASS
        )

        for i, arg in enumerate(node.args.args):
            # Skip 'self' or 'cls' for methods if first argument
            if is_method and i == 0 and arg.arg in ("self", "cls"):
                continue
            arguments.append(arg.arg)

        if node.args.vararg:
            arguments.append(f"*{node.args.vararg.arg}")

        for arg in node.args.kwonlyargs:
            arguments.append(arg.arg)

        if node.args.kwarg:
            arguments.append(f"**{node.args.kwarg.arg}")

        return arguments

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Handle class definitions."""
        scope_chain = self.scope_stack + [node.name]
        fqsn = build_fqsn(self.module_path, scope_chain)
        parent_fqsn = self.parent_fqsn_stack[-1] if self.parent_fqsn_stack else None

        docstring = ast.get_docstring(node)
        source_code = self._extract_source(node)

        symbol = Symbol(
            fqsn=fqsn,
            name=node.name,
            symbol_type=SymbolType.CLASS,
            file_path=self.rel_file_path,
            module_path=self.module_path,
            parent_fqsn=parent_fqsn,
            start_line=node.lineno,
            end_line=node.end_lineno,
            arguments=[],
            docstring=docstring,
            is_async=False,
            source_code=source_code,
        )
        self.symbol_table.register(symbol)

        # Push scope
        self.scope_stack.append(node.name)
        self.parent_fqsn_stack.append(fqsn)
        self.scope_kind_stack.append(SymbolType.CLASS)

        # Visit child nodes
        self.generic_visit(node)

        # Pop scope
        self.scope_stack.pop()
        self.parent_fqsn_stack.pop()
        self.scope_kind_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle synchronous function and method definitions."""
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Handle asynchronous function and method definitions."""
        self._visit_function(node, is_async=True)

    def _visit_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        is_async: bool,
    ) -> None:
        """Helper for processing function/method definitions."""
        parent_kind = self.scope_kind_stack[-1] if self.scope_kind_stack else None

        if parent_kind == SymbolType.CLASS:
            symbol_type = SymbolType.METHOD
        elif parent_kind in (
            SymbolType.FUNCTION,
            SymbolType.METHOD,
            SymbolType.NESTED_FUNCTION,
        ):
            symbol_type = SymbolType.NESTED_FUNCTION
        else:
            symbol_type = SymbolType.FUNCTION

        scope_chain = self.scope_stack + [node.name]
        fqsn = build_fqsn(self.module_path, scope_chain)
        parent_fqsn = self.parent_fqsn_stack[-1] if self.parent_fqsn_stack else None

        arguments = self._extract_arguments(node)
        docstring = ast.get_docstring(node)
        source_code = self._extract_source(node)

        symbol = Symbol(
            fqsn=fqsn,
            name=node.name,
            symbol_type=symbol_type,
            file_path=self.rel_file_path,
            module_path=self.module_path,
            parent_fqsn=parent_fqsn,
            start_line=node.lineno,
            end_line=node.end_lineno,
            arguments=arguments,
            docstring=docstring,
            is_async=is_async,
            source_code=source_code,
        )
        self.symbol_table.register(symbol)

        # Push scope
        self.scope_stack.append(node.name)
        self.parent_fqsn_stack.append(fqsn)
        self.scope_kind_stack.append(symbol_type)

        # Visit child nodes
        self.generic_visit(node)

        # Pop scope
        self.scope_stack.pop()
        self.parent_fqsn_stack.pop()
        self.scope_kind_stack.pop()
