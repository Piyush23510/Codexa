"""
Phase 4A: Symbol Table & FQSN Foundation

Defines the core data structures for fully-qualified symbol names (FQSNs).

FQSN canonical format:
    module::function
    module::Class
    module::Class.method
    module::Class.method.nested_function

Where module_path is derived from the repository-relative file path:
    utils/similarity.py  →  utils.similarity
    app.py               →  app
    models/__init__.py   →  models
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class SymbolType(str, Enum):
    """Classification of Python symbols extracted from AST."""
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    NESTED_FUNCTION = "nested_function"


@dataclass
class Symbol:
    """
    A uniquely-identified Python symbol with its fully-qualified name.

    Attributes:
        fqsn:           Fully-qualified symbol name (e.g. "utils.similarity::clean_text")
        name:           Bare symbol name (e.g. "clean_text")
        symbol_type:    Classification (MODULE, CLASS, FUNCTION, METHOD, NESTED_FUNCTION)
        file_path:      Repository-relative file path (e.g. "utils/similarity.py")
        module_path:    Python-style module path (e.g. "utils.similarity")
        parent_fqsn:    FQSN of the enclosing scope, or None for top-level symbols
        start_line:     First line of the symbol definition (1-indexed)
        end_line:       Last line of the symbol definition (1-indexed)
        arguments:      List of argument names (empty for classes/modules)
        docstring:      The symbol's docstring, if any
        is_async:       Whether this is an async function/method
        source_code:    The extracted source text, if available
    """
    fqsn: str
    name: str
    symbol_type: SymbolType
    file_path: str
    module_path: str
    parent_fqsn: Optional[str]
    start_line: int
    end_line: int
    arguments: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    source_code: Optional[str] = None

    @property
    def display_name(self) -> str:
        """
        Short name for UI display.

        Returns the scope chain portion of the FQSN (after the "::").
        Examples:
            "utils.similarity::clean_text"                → "clean_text"
            "parser.ast_parser::ASTParser.get_functions"  → "ASTParser.get_functions"
            "app::analyze"                                → "analyze"
        """
        parts = self.fqsn.split("::", 1)
        if len(parts) == 2:
            return parts[1]
        return self.name

    @property
    def is_callable(self) -> bool:
        """True if this symbol can be called (function, method, class)."""
        return self.symbol_type in (
            SymbolType.FUNCTION,
            SymbolType.METHOD,
            SymbolType.NESTED_FUNCTION,
            SymbolType.CLASS,
        )

    def get_class_fqsn(self) -> Optional[str]:
        """
        If this symbol is a method, return its enclosing class FQSN.
        Otherwise return None.
        """
        if self.symbol_type == SymbolType.METHOD and self.parent_fqsn:
            return self.parent_fqsn
        return None



def file_to_module_path(file_path: Path, repo_root: Path) -> str:
    """
    Convert a filesystem path to a Python-style module path.

    This is the single canonical conversion used throughout Phase 4.

    Rules:
        1. Compute the path relative to repo_root.
        2. Use forward slashes, replace directory separators with dots.
        3. Strip the ".py" extension from the final component.
        4. For __init__.py, use the parent directory as the module name.

    Examples:
        repo_root/utils/similarity.py    → "utils.similarity"
        repo_root/app.py                 → "app"
        repo_root/models/__init__.py     → "models"
        repo_root/parser/ast_parser.py   → "parser.ast_parser"

    Args:
        file_path: Absolute or relative path to the Python file.
        repo_root: Absolute or relative path to the repository root.

    Returns:
        A dot-separated module path string.

    Raises:
        ValueError: If file_path is not under repo_root or not a .py file.
    """
    # Resolve both paths to handle relative paths and symlinks
    abs_file = Path(file_path).resolve()
    abs_root = Path(repo_root).resolve()

    try:
        rel = abs_file.relative_to(abs_root)
    except ValueError:
        raise ValueError(
            f"File '{file_path}' is not under repository root '{repo_root}'"
        )

    # Convert to forward-slash string for consistent handling
    rel_str = str(rel).replace("\\", "/")

    if not rel_str.endswith(".py"):
        raise ValueError(
            f"File '{file_path}' is not a Python file"
        )

    # Handle __init__.py: module path is the parent directory
    if rel_str.endswith("/__init__.py") or rel_str == "__init__.py":
        parent = str(rel.parent).replace("\\", "/")
        if parent == ".":
            # __init__.py at repo root — unusual but handle gracefully
            return "__init__"
        return parent.replace("/", ".")

    # Standard case: strip .py and replace slashes with dots
    module = rel_str[:-3]  # remove ".py"
    return module.replace("/", ".")


def build_fqsn(module_path: str, scope_chain: List[str]) -> str:
    """
    Construct a canonical FQSN from a module path and scope chain.

    Args:
        module_path: The dot-separated module path (e.g. "utils.similarity").
        scope_chain: List of scope names from outermost to innermost
                     (e.g. ["ASTParser", "get_functions"]).

    Returns:
        A canonical FQSN string.

    Examples:
        ("utils.similarity", ["clean_text"])
            → "utils.similarity::clean_text"
        ("parser.ast_parser", ["ASTParser", "get_functions"])
            → "parser.ast_parser::ASTParser.get_functions"
        ("parser.ast_parser", ["ASTParser"])
            → "parser.ast_parser::ASTParser"
    """
    if not scope_chain:
        raise ValueError("scope_chain must not be empty")
    return f"{module_path}::{'.'.join(scope_chain)}"


class SymbolTable:
    """
    Registry of all symbols in a repository, indexed by FQSN.

    Provides O(1) lookup by FQSN and O(1) lookup by bare name
    (returning a list of all symbols sharing that name).
    """

    def __init__(self):
        self._symbols: Dict[str, Symbol] = {}              # fqsn → Symbol
        self._by_name: Dict[str, List[Symbol]] = {}         # bare name → [Symbol, ...]
        self._by_file: Dict[str, List[Symbol]] = {}         # relative file path → [Symbol, ...]
        self._by_module: Dict[str, List[Symbol]] = {}       # module path → [Symbol, ...]

    def register(self, symbol: Symbol) -> None:
        """
        Register a symbol in the table.

        If a symbol with the same FQSN already exists, it is silently
        overwritten (last-write wins). This handles re-parsing scenarios.

        Args:
            symbol: The Symbol to register.
        """
        # Check for duplicate FQSN and remove old entry from secondary indexes
        if symbol.fqsn in self._symbols:
            old = self._symbols[symbol.fqsn]
            self._remove_from_secondary_indexes(old)

        self._symbols[symbol.fqsn] = symbol

        # Index by bare name
        if symbol.name not in self._by_name:
            self._by_name[symbol.name] = []
        self._by_name[symbol.name].append(symbol)

        # Index by file path (normalize to forward slashes)
        file_key = symbol.file_path.replace("\\", "/")
        if file_key not in self._by_file:
            self._by_file[file_key] = []
        self._by_file[file_key].append(symbol)

        # Index by module path
        if symbol.module_path not in self._by_module:
            self._by_module[symbol.module_path] = []
        self._by_module[symbol.module_path].append(symbol)

    def _remove_from_secondary_indexes(self, symbol: Symbol) -> None:
        """Remove a symbol from the secondary indexes (name, file, module)."""
        # Remove from _by_name
        if symbol.name in self._by_name:
            self._by_name[symbol.name] = [
                s for s in self._by_name[symbol.name] if s.fqsn != symbol.fqsn
            ]
            if not self._by_name[symbol.name]:
                del self._by_name[symbol.name]

        # Remove from _by_file
        file_key = symbol.file_path.replace("\\", "/")
        if file_key in self._by_file:
            self._by_file[file_key] = [
                s for s in self._by_file[file_key] if s.fqsn != symbol.fqsn
            ]
            if not self._by_file[file_key]:
                del self._by_file[file_key]

        # Remove from _by_module
        if symbol.module_path in self._by_module:
            self._by_module[symbol.module_path] = [
                s for s in self._by_module[symbol.module_path] if s.fqsn != symbol.fqsn
            ]
            if not self._by_module[symbol.module_path]:
                del self._by_module[symbol.module_path]

    def get(self, fqsn: str) -> Optional[Symbol]:
        """
        Look up a symbol by its exact FQSN.

        Args:
            fqsn: The fully-qualified symbol name.

        Returns:
            The Symbol if found, None otherwise.
        """
        return self._symbols.get(fqsn)

    def lookup_name(self, name: str) -> List[Symbol]:
        """
        Find all symbols with the given bare name.

        This is the primary method for resolving user queries that
        reference symbols by short name. If the result has exactly
        one element, the name is unambiguous. If it has multiple
        elements, disambiguation is needed.

        Args:
            name: The bare symbol name (e.g. "clean_text", "save").

        Returns:
            List of matching Symbol objects (may be empty).
        """
        return list(self._by_name.get(name, []))

    def lookup_file(self, file_path: str) -> List[Symbol]:
        """
        Find all symbols defined in the given file.

        Args:
            file_path: Repository-relative file path (forward slashes).

        Returns:
            List of Symbol objects in that file.
        """
        key = file_path.replace("\\", "/")
        return list(self._by_file.get(key, []))

    def lookup_module(self, module_path: str) -> List[Symbol]:
        """
        Find all symbols defined in the given module.

        Args:
            module_path: Dot-separated module path (e.g. "utils.similarity").

        Returns:
            List of Symbol objects in that module.
        """
        return list(self._by_module.get(module_path, []))

    def get_children(self, parent_fqsn: str) -> List[Symbol]:
        """
        Find all direct child symbols of the given parent FQSN.

        Args:
            parent_fqsn: The parent FQSN (e.g. "models.user::User").

        Returns:
            List of child Symbol objects.
        """
        return [
            s for s in self._symbols.values()
            if s.parent_fqsn == parent_fqsn
        ]

    def all_fqsns(self) -> List[str]:
        """Return a sorted list of all registered FQSNs."""
        return sorted(self._symbols.keys())

    def all_callable_fqsns(self) -> List[str]:
        """
        Return a sorted list of FQSNs for all callable symbols
        (functions, methods, nested functions, and classes).
        """
        return sorted(
            fqsn for fqsn, sym in self._symbols.items()
            if sym.is_callable
        )

    def all_names(self) -> List[str]:
        """Return a sorted list of all unique bare names."""
        return sorted(self._by_name.keys())

    def __len__(self) -> int:
        """Return the total number of registered symbols."""
        return len(self._symbols)

    def __contains__(self, fqsn: str) -> bool:
        """Check if a FQSN is registered."""
        return fqsn in self._symbols
