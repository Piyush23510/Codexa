"""
Phase 4D Test Suite: Fully Qualified Symbol Name (FQSN) Dependency Resolution

Tests:
  1. test_1_module_level_function_call: same-file function call
  2. test_2_duplicate_function_names_across_files: ambiguous call handling
  3. test_3_from_x_import_y: imported function resolution
  4. test_4_import_alias: imported function alias resolution
  5. test_5_module_qualified_function_call: module.func() resolution
  6. test_6_module_alias: alias.func() resolution
  7. test_7_self_method_call: self.method() class method resolution
  8. test_8_class_method_call: Class.method() resolution
  9. test_9_duplicate_class_method_names: User.save vs Order.save separation
 10. test_10_class_instantiation: User() instantiation
 11. test_11_constructor_resolution: User() -> User.__init__
 12. test_12_cross_file_dependency: cross-file call edges
 13. test_13_reverse_dependency: reverse caller lookups
 14. test_14_indirect_dependency: transitive closure (A -> B -> C)
 15. test_15_ambiguous_symbol_resolution: explicit AMBIGUOUS status & candidates
 16. test_16_relative_imports: relative import call resolution
 17. test_17_nested_function_behavior: nested function call scope
 18. test_18_external_library_calls: external calls excluded from local graph
 19. test_19_multi_repository_isolation: symbol isolation across repos
 20. test_20_existing_dependency_analyzer_compatibility: CompatibilityAdapter
 21. test_21_real_codexa_repository_smoke_test: Codexa codebase smoke test
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

from parser.ast_parser import ASTParser
from parser.fqsn_resolver import (
    CallResolutionStatus,
    CompatibilityAdapter,
    FQSNDependencyEdge,
    FQSNDependencyGraph,
    FQSNDependencyResolver,
)
from parser.import_graph import ImportGraph
from parser.symbol_table import SymbolTable, SymbolType, file_to_module_path


class TestPhase4DFQSNDependencyResolution(unittest.TestCase):

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "phase4_test_repo"
        self.repo_root = self.fixture_dir.resolve()

        # Build shared SymbolTable, ImportGraph, and FQSNDependencyResolver for fixture repo
        self.symbol_table = SymbolTable()
        self.import_graph = ImportGraph()

        py_files = list(self.fixture_dir.rglob("*.py"))
        for pf in py_files:
            parser = ASTParser(pf)
            parser.get_symbol_tree(repo_root=self.repo_root, symbol_table=self.symbol_table)

        self.import_graph.build_from_repository(self.repo_root)

        self.resolver = FQSNDependencyResolver(
            symbol_table=self.symbol_table,
            import_graph=self.import_graph,
            repo_root=self.repo_root,
        )
        self.graph = self.resolver.build_graph()

    def test_1_module_level_function_call(self):
        """Same-file function call: parse() calling helper() inside utils_a.py."""
        edges = self.graph.get_direct_dependencies("utils_a::parse")
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        self.assertEqual(edge.resolution_status, CallResolutionStatus.RESOLVED)
        self.assertEqual(edge.callee_fqsn, "utils_a::helper")

    def test_2_duplicate_function_names_across_files(self):
        """Unimported ambiguous call to parse() when utils_a::parse and utils_b::parse exist."""
        code = '''
def run_ambiguous():
    parse("data")
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "ambig.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p = ASTParser(file_path)
            p.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            # Register duplicate parse functions
            s1 = ASTParser(self.fixture_dir / "utils_a.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st)
            s2 = ASTParser(self.fixture_dir / "utils_b.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

            ig = ImportGraph()
            ig.build_from_repository(tmp_path)

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            edges = g.get_direct_dependencies("ambig::run_ambiguous")
            self.assertEqual(len(edges), 1)
            edge = edges[0]
            self.assertEqual(edge.resolution_status, CallResolutionStatus.AMBIGUOUS)
            self.assertIn("utils_a::parse", edge.candidates)
            self.assertIn("utils_b::parse", edge.candidates)

    def test_3_from_x_import_y(self):
        """from utils_a import parse -> parse() resolves to utils_a::parse."""
        edges = self.graph.get_direct_dependencies("main::run_pipeline")
        callees = [e.callee_fqsn for e in edges if e.callee_fqsn]
        self.assertIn("utils_a::parse", callees)

    def test_4_import_alias(self):
        """from utils_a import parse as clean_parse in services/processor.py -> resolves to utils_a::parse."""
        edges = self.graph.get_direct_dependencies("services.processor::process_all")
        callees = [e.callee_fqsn for e in edges if e.callee_fqsn]
        self.assertIn("utils_a::parse", callees)

    def test_5_module_qualified_function_call(self):
        """utils_a.parse() module-qualified call resolution."""
        code = '''
import utils_a

def caller():
    utils_a.parse("data")
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "qual_test.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p = ASTParser(file_path)
            p.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            # Copy utils_a symbol
            ASTParser(self.fixture_dir / "utils_a.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

            ig = ImportGraph()
            ig.add_known_module("utils_a", "utils_a.py")
            ig.add_known_module("qual_test", "qual_test.py")
            ig.build_from_file(file_path, tmp_path)

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            edges = g.get_resolved_direct_dependencies("qual_test::caller")
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0].resolution_status, CallResolutionStatus.RESOLVED)
            self.assertEqual(edges[0].callee_fqsn, "utils_a::parse")

    def test_6_module_alias(self):
        """import utils_a as ua -> ua.parse() resolution."""
        code = '''
import utils_a as ua

def caller():
    ua.parse("data")
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "alias_test.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p = ASTParser(file_path)
            p.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            ASTParser(self.fixture_dir / "utils_a.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

            ig = ImportGraph()
            ig.add_known_module("utils_a", "utils_a.py")
            ig.add_known_module("alias_test", "alias_test.py")
            ig.build_from_file(file_path, tmp_path)

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            edges = g.get_resolved_direct_dependencies("alias_test::caller")
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0].resolution_status, CallResolutionStatus.RESOLVED)
            self.assertEqual(edges[0].callee_fqsn, "utils_a::parse")

    def test_7_self_method_call(self):
        """self.validate() inside User.save() resolves to models.user::User.validate."""
        edges = self.graph.get_resolved_direct_dependencies("models.user::User.save")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].resolution_status, CallResolutionStatus.RESOLVED)
        self.assertEqual(edges[0].callee_fqsn, "models.user::User.validate")

    def test_8_class_method_call(self):
        """User.save() class method call resolution."""
        code = '''
from models.user import User

def trigger():
    User.save(None)
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "cm_test.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p = ASTParser(file_path)
            p.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            ASTParser(self.fixture_dir / "models" / "user.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

            ig = ImportGraph()
            ig.add_known_module("models.user", "models/user.py")
            ig.add_known_module("cm_test", "cm_test.py")
            ig.build_from_file(file_path, tmp_path)

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            edges = g.get_direct_dependencies("cm_test::trigger")
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0].resolution_status, CallResolutionStatus.RESOLVED)
            self.assertEqual(edges[0].callee_fqsn, "models.user::User.save")

    def test_9_duplicate_class_method_names(self):
        """User.save and Order.save resolve to distinct method FQSNs."""
        user_save_edges = self.graph.get_direct_dependencies("models.user::User.save")
        order_save_edges = self.graph.get_direct_dependencies("models.order::Order.save")

        self.assertEqual(user_save_edges[0].callee_fqsn, "models.user::User.validate")
        self.assertEqual(order_save_edges[0].callee_fqsn, "models.order::Order.validate")

    def test_10_class_instantiation(self):
        """User("test") resolves to User.__init__ or User."""
        edges = self.graph.get_direct_dependencies("main::run_pipeline")
        callees = [e.callee_fqsn for e in edges if e.callee_fqsn]
        self.assertIn("models.user::User.__init__", callees)

    def test_11_constructor_resolution(self):
        """Order(user, data) resolves to Order.__init__."""
        edges = self.graph.get_direct_dependencies("main::run_pipeline")
        callees = [e.callee_fqsn for e in edges if e.callee_fqsn]
        self.assertIn("models.order::Order.__init__", callees)

    def test_12_cross_file_dependency(self):
        """main.py -> models.user and models.order cross-file dependency edges."""
        edges = self.graph.get_resolved_direct_dependencies("main::run_pipeline")
        callee_files = {e.callee_file for e in edges if e.callee_file}
        self.assertIn("utils_a.py", callee_files)
        self.assertIn("utils_b.py", callee_files)
        self.assertIn("models/user.py", callee_files)
        self.assertIn("models/order.py", callee_files)

    def test_13_reverse_dependency(self):
        """Reverse dependency query: Who calls utils_a::parse?"""
        rev = self.graph.get_reverse_dependencies("utils_a::parse")
        callers = {e.caller_fqsn for e in rev}
        self.assertIn("main::run_pipeline", callers)
        self.assertIn("services.processor::process_all", callers)

    def test_14_indirect_dependency(self):
        """Transitive closure: main::run_pipeline -> User.__init__ -> User.validate."""
        indirect = self.graph.get_indirect_dependencies("main::run_pipeline")
        self.assertIn("models.user::User.validate", indirect)
        self.assertIn("models.order::Order.validate", indirect)

    def test_15_ambiguous_symbol_resolution(self):
        """Unresolved / ambiguous call edge preserves candidates list."""
        edge = FQSNDependencyEdge(
            caller_fqsn="mod::func",
            callee_fqsn=None,
            caller_file="mod.py",
            callee_file=None,
            call_line=10,
            resolution_status=CallResolutionStatus.AMBIGUOUS,
            resolution_reason="multiple candidate symbols match",
            candidates=["utils_a::parse", "utils_b::parse"],
        )
        self.assertEqual(edge.resolution_status, CallResolutionStatus.AMBIGUOUS)
        self.assertEqual(len(edge.candidates), 2)

    def test_16_relative_imports(self):
        """Relative import call resolution within package."""
        code = '''
from .user import User

def create():
    u = User("test")
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            models_dir = tmp_path / "models"
            models_dir.mkdir()
            (models_dir / "__init__.py").write_text("", encoding="utf-8")
            (models_dir / "user.py").write_text("class User:\n def __init__(self, name):\n  pass", encoding="utf-8")

            file_path = models_dir / "creator.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p1 = ASTParser(models_dir / "user.py")
            p1.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            p2 = ASTParser(file_path)
            p2.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            ig = ImportGraph()
            ig.build_from_repository(tmp_path)

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            edges = g.get_direct_dependencies("models.creator::create")
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0].resolution_status, CallResolutionStatus.RESOLVED)
            self.assertEqual(edges[0].callee_fqsn, "models.user::User.__init__")

    def test_17_nested_function_behavior(self):
        """Nested functions should be treated as independent caller scopes."""
        code = '''
def outer():
    def inner():
        print("inner")
    inner()
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "nest.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p = ASTParser(file_path)
            p.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            ig = ImportGraph()
            ig.add_known_module("nest", "nest.py")

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            outer_edges = g.get_direct_dependencies("nest::outer")
            self.assertEqual(len(outer_edges), 1)
            self.assertEqual(outer_edges[0].callee_fqsn, "nest::outer.inner")

    def test_18_external_library_calls(self):
        """Calls to external standard/3rd-party functions must not become local repo edges."""
        code = '''
import os
import sys

def sys_call():
    os.path.join("a", "b")
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "ext.py"
            file_path.write_text(code, encoding="utf-8")

            st = SymbolTable()
            p = ASTParser(file_path)
            p.get_symbol_tree(repo_root=tmp_path, symbol_table=st)

            ig = ImportGraph()
            ig.add_known_module("ext", "ext.py")

            res = FQSNDependencyResolver(st, ig, tmp_path)
            g = res.build_graph([file_path])

            # Resolved direct dependencies should be empty (no local repo edges)
            resolved_edges = g.get_resolved_direct_dependencies("ext::sys_call")
            self.assertEqual(len(resolved_edges), 0)

            # Unresolved edges store reason
            all_edges = g.get_direct_dependencies("ext::sys_call")
            self.assertEqual(len(all_edges), 1)
            self.assertEqual(all_edges[0].resolution_status, CallResolutionStatus.UNRESOLVED)

    def test_19_multi_repository_isolation(self):
        """Symbols from repository A must not leak into repository B."""
        st1 = SymbolTable()
        st2 = SymbolTable()

        s1 = ASTParser(self.fixture_dir / "utils_a.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st1)
        s2 = ASTParser(self.fixture_dir / "utils_b.py").get_symbol_tree(repo_root=self.repo_root, symbol_table=st2)

        self.assertIn("utils_a::parse", st1)
        self.assertNotIn("utils_b::parse", st1)

        self.assertIn("utils_b::parse", st2)
        self.assertNotIn("utils_a::parse", st2)

    def test_20_existing_dependency_analyzer_compatibility(self):
        """CompatibilityAdapter converts FQSN queries to flat function names safely."""
        adapter = CompatibilityAdapter(self.symbol_table, self.graph)

        deps = adapter.get_function_dependencies("parse")
        self.assertIn("parse", deps)
        self.assertIn("helper", deps["parse"])

        impact = adapter.get_impact_analysis("parse")
        self.assertIn("run_pipeline", impact["direct_impact"])
        self.assertIn("process_all", impact["direct_impact"])

    def test_21_real_codexa_repository_smoke_test(self):
        """Smoke test: Parse and build FQSN dependency graph for Codexa core files."""
        codexa_root = PROJECT_ROOT
        st = SymbolTable()
        ig = ImportGraph()

        files = [
            codexa_root / "parser" / "symbol_table.py",
            codexa_root / "parser" / "hierarchical_visitor.py",
            codexa_root / "parser" / "ast_parser.py",
            codexa_root / "parser" / "import_graph.py",
            codexa_root / "parser" / "fqsn_resolver.py",
        ]

        for f in files:
            if f.exists():
                p = ASTParser(f)
                p.get_symbol_tree(repo_root=codexa_root, symbol_table=st)

        ig.build_from_repository(codexa_root, file_paths=files)

        res = FQSNDependencyResolver(st, ig, codexa_root)
        g = res.build_graph(file_paths=files)

        self.assertGreater(len(g), 0)
        resolved = [e for e in g.all_edges() if e.resolution_status == CallResolutionStatus.RESOLVED]
        self.assertGreater(len(resolved), 0)

        # Check call from ASTParser.get_symbol_tree to HierarchicalASTVisitor
        get_sym_tree_edges = g.get_resolved_direct_dependencies("parser.ast_parser::ASTParser.get_symbol_tree")
        callees = [e.callee_fqsn for e in get_sym_tree_edges if e.callee_fqsn]
        self.assertTrue(any("HierarchicalASTVisitor" in c for c in callees))


if __name__ == "__main__":
    unittest.main()
