"""
Phase 4C Test Suite: Module-Level Import Graph & Dependency Resolution

Tests:
  1. import module (import utils_a)
  2. import module as alias (import utils_a as ua)
  3. from module import symbol (from models.user import User)
  4. from module import symbol as alias (from models.user import User as U)
  5. multiple imported symbols (from utils_a import parse, helper)
  6. relative imports (from . import utils)
  7. parent relative imports (from ..parser import ast_parser)
  8. wildcard imports (from utils_a import *)
  9. standard library imports (import os, sys, ast)
 10. external package imports (from flask import Flask)
 11. local repository imports (from models.user import User)
 12. unresolved imports (from .nonexistent import foo)
 13. duplicate import records handling
 14. reverse importer lookup (get_importers)
 15. module naming consistency with Phase 4A
 16. integration with Phase 4B fixture repository
 17. real repository smoke test (Codexa codebase)
"""

import ast
import sys
import tempfile
import unittest
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parser.import_graph import (
    ImportExtractor,
    ImportGraph,
    ImportRecord,
    ImportType,
    ResolutionStatus,
)
from parser.symbol_table import file_to_module_path


class TestPhase4CImportGraph(unittest.TestCase):

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "phase4_test_repo"
        self.repo_root = self.fixture_dir.resolve()

    def test_1_import_module(self):
        """Standard import: 'import utils_a'."""
        graph = ImportGraph()
        graph.add_known_module("utils_a", "utils_a.py")
        graph.add_known_module("main", "main.py")

        rec = ImportRecord(
            source_module="main",
            source_file="main.py",
            raw_statement="import utils_a",
            import_type=ImportType.STANDARD,
            imported_module="utils_a",
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "utils_a")
        self.assertIsNone(resolved.alias)

    def test_2_import_module_as_alias(self):
        """Import alias: 'import utils_a as ua'."""
        graph = ImportGraph()
        graph.add_known_module("utils_a", "utils_a.py")
        graph.add_known_module("main", "main.py")

        rec = ImportRecord(
            source_module="main",
            source_file="main.py",
            raw_statement="import utils_a as ua",
            import_type=ImportType.STANDARD,
            imported_module="utils_a",
            alias="ua",
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "utils_a")
        self.assertEqual(resolved.alias, "ua")

    def test_3_from_module_import_symbol(self):
        """From import: 'from models.user import User'."""
        graph = ImportGraph()
        graph.add_known_module("models.user", "models/user.py")
        graph.add_known_module("services.processor", "services/processor.py")

        rec = ImportRecord(
            source_module="services.processor",
            source_file="services/processor.py",
            raw_statement="from models.user import User",
            import_type=ImportType.FROM,
            imported_module="models.user",
            imported_symbol="User",
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "models.user")
        self.assertEqual(resolved.imported_symbol, "User")

    def test_4_from_module_import_symbol_as_alias(self):
        """From import alias: 'from models.user import User as U'."""
        graph = ImportGraph()
        graph.add_known_module("models.user", "models/user.py")

        rec = ImportRecord(
            source_module="services.processor",
            source_file="services/processor.py",
            raw_statement="from models.user import User as U",
            import_type=ImportType.FROM,
            imported_module="models.user",
            imported_symbol="User",
            alias="U",
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "models.user")
        self.assertEqual(resolved.alias, "U")

    def test_5_multiple_imported_symbols(self):
        """Multiple symbols from same module: 'from utils_a import parse, helper'."""
        code = "from utils_a import parse, helper"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "utils_a.py").write_text("def parse(): pass\ndef helper(): pass", encoding="utf-8")
            file_path = tmp_path / "main.py"
            file_path.write_text(code, encoding="utf-8")

            graph = ImportGraph()
            graph.add_known_module("utils_a", "utils_a.py")
            recs = graph.build_from_file(file_path, tmp_path)

            self.assertEqual(len(recs), 2)
            symbols = {r.imported_symbol for r in recs}
            self.assertEqual(symbols, {"parse", "helper"})
            for r in recs:
                self.assertEqual(r.resolution_status, ResolutionStatus.LOCAL)
                self.assertEqual(r.resolved_module, "utils_a")

    def test_6_relative_imports(self):
        """Relative import within package: 'from . import utils'."""
        graph = ImportGraph()
        graph.add_known_module("services.processor", "services/processor.py")
        graph.add_known_module("services.utils", "services/utils.py")

        rec = ImportRecord(
            source_module="services.processor",
            source_file="services/processor.py",
            raw_statement="from . import utils",
            import_type=ImportType.FROM,
            imported_module="",
            imported_symbol="utils",
            relative_level=1,
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "services.utils")

    def test_7_parent_relative_imports(self):
        """Parent relative import: 'from ..parser import ast_parser'."""
        graph = ImportGraph()
        graph.add_known_module("services.worker", "services/worker.py")
        graph.add_known_module("parser.ast_parser", "parser/ast_parser.py")

        rec = ImportRecord(
            source_module="services.worker",
            source_file="services/worker.py",
            raw_statement="from ..parser import ast_parser",
            import_type=ImportType.FROM,
            imported_module="parser",
            imported_symbol="ast_parser",
            relative_level=2,
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "parser.ast_parser")

    def test_8_wildcard_imports(self):
        """Wildcard import: 'from utils_a import *'."""
        graph = ImportGraph()
        graph.add_known_module("utils_a", "utils_a.py")

        rec = ImportRecord(
            source_module="main",
            source_file="main.py",
            raw_statement="from utils_a import *",
            import_type=ImportType.WILDCARD,
            imported_module="utils_a",
            is_wildcard=True,
        )
        resolved = graph.add_record(rec)

        self.assertTrue(resolved.is_wildcard)
        self.assertEqual(resolved.import_type, ImportType.WILDCARD)
        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "utils_a")

    def test_9_standard_library_imports(self):
        """Standard library imports: 'import os', 'import sys', 'import ast'."""
        graph = ImportGraph()
        graph.add_known_module("main", "main.py")

        for mod in ["os", "sys", "ast", "pathlib", "json"]:
            rec = ImportRecord(
                source_module="main",
                source_file="main.py",
                raw_statement=f"import {mod}",
                import_type=ImportType.STANDARD,
                imported_module=mod,
            )
            resolved = graph.add_record(rec)
            self.assertEqual(resolved.resolution_status, ResolutionStatus.EXTERNAL)
            self.assertEqual(resolved.resolved_module, mod)

    def test_10_external_package_imports(self):
        """External 3rd-party package imports: 'from flask import Flask'."""
        graph = ImportGraph()
        graph.add_known_module("app", "app.py")

        rec = ImportRecord(
            source_module="app",
            source_file="app.py",
            raw_statement="from flask import Flask",
            import_type=ImportType.FROM,
            imported_module="flask",
            imported_symbol="Flask",
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.EXTERNAL)
        self.assertEqual(resolved.resolved_module, "flask")

    def test_11_local_repository_imports(self):
        """Local repository import resolution."""
        graph = ImportGraph()
        graph.add_known_module("models.user", "models/user.py")
        graph.add_known_module("main", "main.py")

        rec = ImportRecord(
            source_module="main",
            source_file="main.py",
            raw_statement="from models.user import User",
            import_type=ImportType.FROM,
            imported_module="models.user",
            imported_symbol="User",
        )
        resolved = graph.add_record(rec)

        self.assertEqual(resolved.resolution_status, ResolutionStatus.LOCAL)
        self.assertEqual(resolved.resolved_module, "models.user")

    def test_12_unresolved_imports(self):
        """Unresolvable relative import level or missing subpackages."""
        graph = ImportGraph()
        graph.add_known_module("main", "main.py")

        # Exceeding package depth
        rec1 = ImportRecord(
            source_module="main",
            source_file="main.py",
            raw_statement="from ...nonexistent import foo",
            import_type=ImportType.FROM,
            imported_module="nonexistent",
            imported_symbol="foo",
            relative_level=5,
        )
        resolved1 = graph.add_record(rec1)
        self.assertEqual(resolved1.resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertIsNone(resolved1.resolved_module)

    def test_13_duplicate_import_records(self):
        """Duplicate import records preserved but all_edges returns clean unique pairs."""
        graph = ImportGraph()
        graph.add_known_module("main", "main.py")
        graph.add_known_module("utils_a", "utils_a.py")

        rec1 = ImportRecord("main", "main.py", "import utils_a", ImportType.STANDARD, "utils_a")
        rec2 = ImportRecord("main", "main.py", "from utils_a import parse", ImportType.FROM, "utils_a", "parse")

        graph.add_record(rec1)
        graph.add_record(rec2)

        self.assertEqual(len(graph), 2)
        edges = graph.all_edges()
        self.assertEqual(edges, [("main", "utils_a")])

    def test_14_reverse_importer_lookup(self):
        """Reverse lookup: get_importers('models.user')."""
        graph = ImportGraph()
        graph.add_known_module("models.user", "models/user.py")
        graph.add_known_module("main", "main.py")
        graph.add_known_module("services.processor", "services/processor.py")

        rec1 = ImportRecord("main", "main.py", "from models.user import User", ImportType.FROM, "models.user", "User")
        rec2 = ImportRecord("services.processor", "services/processor.py", "from models.user import User", ImportType.FROM, "models.user", "User")
        rec3 = ImportRecord("main", "main.py", "import os", ImportType.STANDARD, "os")

        graph.add_record(rec1)
        graph.add_record(rec2)
        graph.add_record(rec3)

        importers = graph.get_importers("models.user")
        self.assertEqual(len(importers), 2)
        importer_modules = {r.source_module for r in importers}
        self.assertEqual(importer_modules, {"main", "services.processor"})

    def test_15_module_naming_consistency(self):
        """Module path naming consistency with file_to_module_path from Phase 4A."""
        p = self.fixture_dir / "models" / "user.py"
        mod = file_to_module_path(p, self.repo_root)
        self.assertEqual(mod, "models.user")

        p2 = self.fixture_dir / "models" / "__init__.py"
        mod2 = file_to_module_path(p2, self.repo_root)
        self.assertEqual(mod2, "models")

    def test_16_integration_phase4_fixture_repo(self):
        """Full import graph build on phase4_test_repo fixture."""
        graph = ImportGraph()
        graph.build_from_repository(self.repo_root)

        modules = graph.all_modules()
        self.assertIn("main", modules)
        self.assertIn("utils_a", modules)
        self.assertIn("utils_b", modules)
        self.assertIn("models.user", modules)
        self.assertIn("models.order", modules)
        self.assertIn("services.processor", modules)

        edges = graph.all_edges()
        self.assertIn(("main", "utils_a"), edges)
        self.assertIn(("main", "utils_b"), edges)
        self.assertIn(("main", "models.user"), edges)
        self.assertIn(("main", "models.order"), edges)
        self.assertIn(("services.processor", "models.user"), edges)
        self.assertIn(("services.processor", "models.order"), edges)
        self.assertIn(("services.processor", "utils_a"), edges)

    def test_17_real_repository_smoke_test(self):
        """Smoke test: Build import graph for the actual Codexa codebase."""
        codexa_root = PROJECT_ROOT
        graph = ImportGraph()
        graph.build_from_repository(codexa_root)

        modules = graph.all_modules()
        self.assertIn("app", modules)
        self.assertIn("parser.ast_parser", modules)
        self.assertIn("parser.symbol_table", modules)
        self.assertIn("parser.hierarchical_visitor", modules)
        self.assertIn("parser.import_graph", modules)

        # Check local import edge from ast_parser to hierarchical_visitor or symbol_table
        ast_parser_imports = graph.get_imports("parser.ast_parser")
        local_target_modules = {r.resolved_module for r in ast_parser_imports if r.resolution_status == ResolutionStatus.LOCAL}
        self.assertIn("parser.hierarchical_visitor", local_target_modules)
        self.assertIn("parser.symbol_table", local_target_modules)


if __name__ == "__main__":
    unittest.main()
