"""
Phase 4C: Import Graph Module

Extracts, resolves, and indexes module-level import relationships across a Python repository.

Distinguishes:
- LOCAL: Imports referencing modules/packages inside the repository
- EXTERNAL: Standard library or third-party packages (os, sys, flask, etc.)
- UNRESOLVED: Relative or absolute imports that cannot be resolved safely
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple

from parser.symbol_table import file_to_module_path


class ImportType(str, Enum):
    STANDARD = "standard"   # import x, import x as y
    FROM = "from"           # from x import y, from x import y as z
    WILDCARD = "wildcard"   # from x import *


class ResolutionStatus(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"


@dataclass
class ImportRecord:
    """
    Metadata for a single imported symbol or module statement.

    Attributes:
        source_module:     Module path of file containing import (e.g. "services.processor")
        source_file:       Relative file path of source file (e.g. "services/processor.py")
        raw_statement:     Original import code representation (e.g. "from models.user import User as U")
        import_type:       STANDARD, FROM, or WILDCARD
        imported_module:   Raw target module string from import statement (e.g. "models.user")
        imported_symbol:   Symbol imported via 'from' syntax (e.g. "User"), or None for 'import' syntax
        alias:             Alias assigned via 'as' syntax, or None
        relative_level:    Number of leading dots (0 for absolute, 1 for '.', 2 for '..', etc.)
        resolved_module:   Canonical module path resolved within repository (e.g. "models.user"), or None
        resolution_status: LOCAL, EXTERNAL, or UNRESOLVED
        is_wildcard:       True if 'from module import *'
    """
    source_module: str
    source_file: str
    raw_statement: str
    import_type: ImportType
    imported_module: str
    imported_symbol: Optional[str] = None
    alias: Optional[str] = None
    relative_level: int = 0
    resolved_module: Optional[str] = None
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    is_wildcard: bool = False


class ImportExtractor(ast.NodeVisitor):
    """
    AST Visitor that extracts raw ImportRecord items from a Python file.
    """

    def __init__(self, source_module: str, source_file: str):
        self.source_module = source_module
        self.source_file = source_file
        self.records: List[ImportRecord] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import foo', 'import foo as bar', 'import foo, bar'."""
        for alias in node.names:
            raw = f"import {alias.name}"
            if alias.asname:
                raw += f" as {alias.asname}"

            record = ImportRecord(
                source_module=self.source_module,
                source_file=self.source_file,
                raw_statement=raw,
                import_type=ImportType.STANDARD,
                imported_module=alias.name,
                imported_symbol=None,
                alias=alias.asname,
                relative_level=0,
                is_wildcard=False,
            )
            self.records.append(record)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from mod import sym', 'from . import sym', 'from mod import *'."""
        module = node.module or ""
        level = node.level or 0
        dots = "." * level

        for alias in node.names:
            if alias.name == "*":
                imp_type = ImportType.WILDCARD
                is_wc = True
                symbol = None
            else:
                imp_type = ImportType.FROM
                is_wc = False
                symbol = alias.name

            raw = f"from {dots}{module} import {alias.name}"
            if alias.asname:
                raw += f" as {alias.asname}"

            record = ImportRecord(
                source_module=self.source_module,
                source_file=self.source_file,
                raw_statement=raw,
                import_type=imp_type,
                imported_module=module,
                imported_symbol=symbol,
                alias=alias.asname,
                relative_level=level,
                is_wildcard=is_wc,
            )
            self.records.append(record)


class ImportGraph:
    """
    Module-level import dependency graph for a repository.

    Maintains all import records across files, resolves local vs external modules,
    and supports queries for imports, importers, and graph edges.
    """

    def __init__(self):
        self._records: List[ImportRecord] = []
        self._known_modules: Set[str] = set()
        self._module_to_file: Dict[str, str] = {}

    def add_known_module(self, module_path: str, file_path: Optional[str] = None) -> None:
        """Register a known local module path in the repository."""
        self._known_modules.add(module_path)
        if file_path:
            self._module_to_file[module_path] = file_path.replace("\\", "/")

    @property
    def known_modules(self) -> Set[str]:
        """Return the set of known local repository modules."""
        return set(self._known_modules)

    def add_record(self, record: ImportRecord) -> ImportRecord:
        """
        Add an import record to the graph, performing resolution if not yet resolved.
        """
        resolved_record = self.resolve_record(record)
        self._records.append(resolved_record)
        return resolved_record

    def resolve_record(self, record: ImportRecord) -> ImportRecord:
        """
        Determine whether an ImportRecord is LOCAL, EXTERNAL, or UNRESOLVED,
        and populate its resolved_module field.
        """
        # Create a shallow copy to avoid mutating caller's object unexpectedly
        rec = ImportRecord(
            source_module=record.source_module,
            source_file=record.source_file,
            raw_statement=record.raw_statement,
            import_type=record.import_type,
            imported_module=record.imported_module,
            imported_symbol=record.imported_symbol,
            alias=record.alias,
            relative_level=record.relative_level,
            resolved_module=record.resolved_module,
            resolution_status=record.resolution_status,
            is_wildcard=record.is_wildcard,
        )

        # Handle relative imports (relative_level > 0)
        if rec.relative_level > 0:
            source_parts = rec.source_module.split(".") if rec.source_module else []
            if rec.relative_level > len(source_parts):
                rec.resolution_status = ResolutionStatus.UNRESOLVED
                rec.resolved_module = None
                return rec

            base_parts = source_parts[: len(source_parts) - rec.relative_level]

            if rec.imported_module:
                candidate = (
                    ".".join(base_parts) + "." + rec.imported_module
                    if base_parts
                    else rec.imported_module
                )
            else:
                candidate = ".".join(base_parts) if base_parts else ""

            # Check if candidate is a known module
            if candidate and candidate in self._known_modules:
                rec.resolved_module = candidate
                rec.resolution_status = ResolutionStatus.LOCAL
                return rec

            # Check if candidate + imported_symbol is a known module (e.g. from . import utils)
            if rec.imported_symbol:
                symbol_candidate = (
                    f"{candidate}.{rec.imported_symbol}" if candidate else rec.imported_symbol
                )
                if symbol_candidate in self._known_modules:
                    rec.resolved_module = symbol_candidate
                    rec.resolution_status = ResolutionStatus.LOCAL
                    return rec

            # Unresolvable relative import
            rec.resolution_status = ResolutionStatus.UNRESOLVED
            rec.resolved_module = None
            return rec

        # Absolute imports (relative_level == 0)
        candidate = rec.imported_module

        # Check direct module match
        if candidate in self._known_modules:
            rec.resolved_module = candidate
            rec.resolution_status = ResolutionStatus.LOCAL
            return rec

        # Check if imported_symbol elevates module path (e.g. from models import user -> models.user)
        if rec.imported_symbol:
            combined = f"{candidate}.{rec.imported_symbol}"
            if combined in self._known_modules:
                rec.resolved_module = combined
                rec.resolution_status = ResolutionStatus.LOCAL
                return rec

        # Check top-level package of candidate against known modules
        top_pkg = candidate.split(".")[0] if candidate else ""
        if top_pkg in self._known_modules:
            # Package stem exists locally, but specific submodule is missing
            rec.resolution_status = ResolutionStatus.UNRESOLVED
            rec.resolved_module = None
            return rec

        # Otherwise, classify as EXTERNAL (stdlib or 3rd party package)
        rec.resolution_status = ResolutionStatus.EXTERNAL
        rec.resolved_module = candidate
        return rec

    def build_from_file(self, file_path: Path, repo_root: Path) -> List[ImportRecord]:
        """
        Extract and resolve all imports from a single Python file.
        """
        file_path = Path(file_path).resolve()
        repo_root = Path(repo_root).resolve()

        source_module = file_to_module_path(file_path, repo_root)
        rel_file = str(file_path.relative_to(repo_root)).replace("\\", "/")

        self.add_known_module(source_module, rel_file)

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return []

        extractor = ImportExtractor(source_module, rel_file)
        extractor.visit(tree)

        added = []
        for rec in extractor.records:
            added.append(self.add_record(rec))
        return added

    def build_from_repository(
        self, repo_root: Path, file_paths: Optional[List[Path]] = None
    ) -> None:
        """
        Parse all Python files in a repository to build the full import graph.

        Pass 1: Discover and register all local repository modules.
        Pass 2: Extract and resolve import records.
        """
        repo_root = Path(repo_root).resolve()

        if file_paths is None:
            file_paths = [
                p for p in repo_root.rglob("*.py")
                if not any(
                    part.startswith(".")
                    or part in ("venv", "env", "__pycache__", "uploaded_repositories", "node_modules")
                    for part in p.parts
                )
            ]
        else:
            file_paths = [Path(p).resolve() for p in file_paths]

        # Pass 1: Register all known local modules
        valid_files = []
        for fp in file_paths:
            if not fp.is_file() or not fp.name.endswith(".py"):
                continue
            try:
                mod_path = file_to_module_path(fp, repo_root)
                rel_f = str(fp.relative_to(repo_root)).replace("\\", "/")
                self.add_known_module(mod_path, rel_f)
                valid_files.append((fp, mod_path, rel_f))
            except ValueError:
                continue

        # Pass 2: Extract and resolve imports
        for fp, mod_path, rel_f in valid_files:
            try:
                content = fp.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(fp))
                extractor = ImportExtractor(mod_path, rel_f)
                extractor.visit(tree)
                for rec in extractor.records:
                    self.add_record(rec)
            except Exception:
                continue

    def get_imports(self, module_path: str) -> List[ImportRecord]:
        """
        Get all import records originating from the given module.
        """
        return [r for r in self._records if r.source_module == module_path]

    def get_importers(self, module_path: str) -> List[ImportRecord]:
        """
        Get all LOCAL import records that target/import the given module.
        """
        return [
            r for r in self._records
            if r.resolution_status == ResolutionStatus.LOCAL
            and r.resolved_module == module_path
        ]

    def get_record(self, source_module: str, target_module: str) -> List[ImportRecord]:
        """
        Find import records between a specific source and target module.
        """
        return [
            r for r in self._records
            if r.source_module == source_module
            and (r.resolved_module == target_module or r.imported_module == target_module)
        ]

    def all_modules(self) -> List[str]:
        """Return a sorted list of all known local repository module paths."""
        return sorted(self._known_modules)

    def all_records(self) -> List[ImportRecord]:
        """Return a copy of all registered ImportRecord objects."""
        return list(self._records)

    def all_edges(self) -> List[Tuple[str, str]]:
        """
        Return a sorted, unique list of (source_module, resolved_module) edges
        for all LOCAL resolved imports. Excludes self-referential edges.
        """
        edges = set()
        for r in self._records:
            if (
                r.resolution_status == ResolutionStatus.LOCAL
                and r.resolved_module
                and r.source_module != r.resolved_module
            ):
                edges.add((r.source_module, r.resolved_module))
        return sorted(edges)

    def __len__(self) -> int:
        """Return total number of import records."""
        return len(self._records)
