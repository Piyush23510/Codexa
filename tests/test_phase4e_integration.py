"""
Phase 4E Test Suite: FQSN System Integration & Regression Verification

Tests:
  1. test_1_existing_dependency_analyzer_integration: DependencyAnalyzer initializes Phase 4 infrastructure
  2. test_2_fqsn_direct_dependency: FQSN direct dependency mapping
  3. test_3_fqsn_reverse_dependency: FQSN reverse dependency mapping
  4. test_4_fqsn_indirect_dependency: FQSN indirect transitive dependency
  5. test_5_duplicate_function_names_across_files: Duplicate function names remain isolated
  6. test_6_duplicate_method_names_across_classes: User.save vs Order.save remain isolated
  7. test_7_self_method_call: self.method() resolution
  8. test_8_imported_alias: from mod import func as alias resolution
  9. test_9_module_alias: import mod as alias resolution
 10. test_10_cross_file_call: Cross-file dependency resolution
 11. test_11_constructor_relationship: User() -> User.__init__
 12. test_12_ambiguous_bare_name_lookup: Ambiguous symbol returns candidate list
 13. test_13_impact_isolation_for_duplicate_symbols: Impact analysis isolates User.validate vs Order.validate
 14. test_14_multi_repository_isolation: Per-repository analyzer isolation
 15. test_15_existing_api_compatibility: get_function_dependencies() returns legacy (deps, rev_deps)
 16. test_16_existing_graph_generation_compatibility: PyVis graph HTML generation with FQSNs
 17. test_17_legacy_bare_name_compatibility: get_function_details returns additive fqsn metadata
 18. test_18_cycle_handling: Circular dependencies terminate safely
 19. test_19_existing_frontend_api_smoke_test: CopilotEngine dependency/impact query handlers
 20. test_20_real_codexa_repository_integration_smoke_test: Full integration test on Codexa codebase
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

from parser.dependency_analyzer import DependencyAnalyzer
from parser.dependency_graph import create_dependency_graph, create_impact_graph
from parser.fqsn_resolver import CallResolutionStatus


class TestPhase4EIntegration(unittest.TestCase):

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "phase4_test_repo"
        self.repo_root = self.fixture_dir.resolve()
        self.fixture_files = list(self.fixture_dir.rglob("*.py"))
        self.analyzer = DependencyAnalyzer(self.fixture_files, repo_root=self.repo_root)

    def test_1_existing_dependency_analyzer_integration(self):
        """DependencyAnalyzer initializes Phase 4 infrastructure correctly."""
        self.assertIsNotNone(self.analyzer.symbol_table)
        self.assertIsNotNone(self.analyzer.import_graph)
        self.assertIsNotNone(self.analyzer.fqsn_graph)
        self.assertIsNotNone(self.analyzer.adapter)
        self.assertGreater(len(self.analyzer.symbol_table), 0)

    def test_2_fqsn_direct_dependency(self):
        """FQSN direct dependency extraction."""
        fqsn_deps, _ = self.analyzer.get_fqsn_dependencies()
        self.assertIn("main::run_pipeline", fqsn_deps)
        callees = fqsn_deps["main::run_pipeline"]
        self.assertIn("utils_a::parse", callees)
        self.assertIn("utils_b::parse", callees)
        self.assertIn("models.user::User.__init__", callees)

    def test_3_fqsn_reverse_dependency(self):
        """FQSN reverse dependency extraction."""
        _, fqsn_rev = self.analyzer.get_fqsn_dependencies()
        self.assertIn("utils_a::parse", fqsn_rev)
        callers = fqsn_rev["utils_a::parse"]
        self.assertIn("main::run_pipeline", callers)
        self.assertIn("services.processor::process_all", callers)

    def test_4_fqsn_indirect_dependency(self):
        """FQSN indirect dependency resolution."""
        indirect = self.analyzer.get_indirect_dependencies("main::run_pipeline")
        self.assertTrue(any("User.validate" in item for item in indirect))
        self.assertTrue(any("Order.validate" in item for item in indirect))

    def test_5_duplicate_function_names_across_files(self):
        """utils_a::parse and utils_b::parse remain isolated symbols."""
        st = self.analyzer.symbol_table
        matches = st.lookup_name("parse")
        self.assertEqual(len(matches), 2)
        fqsns = {s.fqsn for s in matches}
        self.assertIn("utils_a::parse", fqsns)
        self.assertIn("utils_b::parse", fqsns)

    def test_6_duplicate_method_names_across_classes(self):
        """models.user::User.save and models.order::Order.save remain separate nodes."""
        st = self.analyzer.symbol_table
        user_save = st.get("models.user::User.save")
        order_save = st.get("models.order::Order.save")

        self.assertIsNotNone(user_save)
        self.assertIsNotNone(order_save)
        self.assertNotEqual(user_save.fqsn, order_save.fqsn)

    def test_7_self_method_call(self):
        """self.validate() inside User.save() resolves to models.user::User.validate."""
        edges = self.analyzer.fqsn_graph.get_resolved_direct_dependencies("models.user::User.save")
        callees = [e.callee_fqsn for e in edges]
        self.assertIn("models.user::User.validate", callees)

    def test_8_imported_alias(self):
        """from utils_a import parse as clean_parse in services/processor.py resolves to utils_a::parse."""
        edges = self.analyzer.fqsn_graph.get_resolved_direct_dependencies("services.processor::process_all")
        callees = [e.callee_fqsn for e in edges]
        self.assertIn("utils_a::parse", callees)

    def test_9_module_alias(self):
        """import utils_a as ua -> ua.parse() resolves correctly."""
        code = '''
import utils_a as ua
def caller():
    ua.parse("data")
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "mod_alias.py"
            file_path.write_text(code, encoding="utf-8")
            (tmp_path / "utils_a.py").write_text("def parse(data): pass", encoding="utf-8")

            da = DependencyAnalyzer([file_path, tmp_path / "utils_a.py"], repo_root=tmp_path)
            edges = da.fqsn_graph.get_resolved_direct_dependencies("mod_alias::caller")
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0].callee_fqsn, "utils_a::parse")

    def test_10_cross_file_call(self):
        """Cross-file dependency resolution in fixture repository."""
        edges = self.analyzer.fqsn_graph.get_resolved_direct_dependencies("main::run_pipeline")
        files = {e.callee_file for e in edges}
        self.assertIn("utils_a.py", files)
        self.assertIn("utils_b.py", files)
        self.assertIn("models/user.py", files)

    def test_11_constructor_relationship(self):
        """User("test") resolves to User.__init__."""
        edges = self.analyzer.fqsn_graph.get_resolved_direct_dependencies("main::run_pipeline")
        callees = [e.callee_fqsn for e in edges]
        self.assertIn("models.user::User.__init__", callees)

    def test_12_ambiguous_bare_name_lookup(self):
        """Ambiguous symbol details report is_ambiguous=True and candidate list."""
        details = self.analyzer.get_function_details("parse")
        self.assertIsNotNone(details)
        self.assertTrue(details.get("is_ambiguous"))
        self.assertEqual(len(details.get("candidates", [])), 2)

    def test_13_impact_isolation_for_duplicate_symbols(self):
        """Changing User.validate impacts User.save and main, NOT Order.save."""
        direct, indirect = self.analyzer.get_impact_analysis("models.user::User.validate")

        # User.save calls User.validate
        self.assertIn("models.user::User.save", direct)
        # Order.save calls Order.validate (different class), so Order.save should not be impacted!
        self.assertNotIn("models.order::Order.save", direct)
        self.assertNotIn("models.order::Order.save", indirect)

    def test_14_multi_repository_isolation(self):
        """Per-repository DependencyAnalyzer instances remain completely isolated."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            p1 = Path(tmp1)
            p2 = Path(tmp2)

            (p1 / "mod_a.py").write_text("def func_a(): pass", encoding="utf-8")
            (p2 / "mod_b.py").write_text("def func_b(): pass", encoding="utf-8")

            da1 = DependencyAnalyzer([p1 / "mod_a.py"], repo_root=p1)
            da2 = DependencyAnalyzer([p2 / "mod_b.py"], repo_root=p2)

            self.assertIn("mod_a::func_a", da1.symbol_table)
            self.assertNotIn("mod_b::func_b", da1.symbol_table)

            self.assertIn("mod_b::func_b", da2.symbol_table)
            self.assertNotIn("mod_a::func_a", da2.symbol_table)

    def test_15_existing_api_compatibility(self):
        """get_function_dependencies() returns legacy (deps, rev_deps) dict tuple."""
        deps, rev_deps = self.analyzer.get_function_dependencies()
        self.assertIsInstance(deps, dict)
        self.assertIsInstance(rev_deps, dict)
        self.assertIn("run_pipeline", deps)
        self.assertTrue("parse" in rev_deps or "utils_a::parse" in rev_deps)

    def test_16_existing_graph_generation_compatibility(self):
        """create_dependency_graph and create_impact_graph render valid HTML with FQSNs."""
        deps, rev_deps = self.analyzer.get_function_dependencies()
        direct, indirect = self.analyzer.get_impact_analysis("models.user::User.validate")

        with tempfile.TemporaryDirectory() as tmpdir:
            dep_html = Path(tmpdir) / "dep_graph.html"
            imp_html = Path(tmpdir) / "imp_graph.html"

            create_dependency_graph(deps, filename=dep_html)
            create_impact_graph("models.user::User.validate", direct, indirect, rev_deps, filename=imp_html)

            self.assertTrue(dep_html.exists())
            self.assertTrue(imp_html.exists())
            self.assertGreater(dep_html.stat().st_size, 100)
            self.assertGreater(imp_html.stat().st_size, 100)

    def test_17_legacy_bare_name_compatibility(self):
        """get_function_details(bare_name) returns details dict with additive fqsn field."""
        details = self.analyzer.get_function_details("run_pipeline")
        self.assertIsNotNone(details)
        self.assertEqual(details["name"], "run_pipeline")
        self.assertIn("fqsn", details)
        self.assertEqual(details["fqsn"], "main::run_pipeline")

    def test_18_cycle_handling(self):
        """Circular dependencies terminate safely in indirect/impact methods."""
        synthetic_deps = {
            "node_a": ["node_b"],
            "node_b": ["node_c"],
            "node_c": ["node_a"]
        }
        indirect = self.analyzer.get_indirect_dependencies("node_a", synthetic_deps)
        self.assertIn("node_c", indirect)

        synthetic_rev = {
            "node_a": ["node_b"],
            "node_b": ["node_c"],
            "node_c": ["node_a"]
        }
        direct, indirect_imp = self.analyzer.get_impact_analysis("node_a", synthetic_rev)
        self.assertNotIn("node_a", direct)
        self.assertNotIn("node_a", indirect_imp)

    def test_19_existing_frontend_api_smoke_test(self):
        """CopilotEngine integration smoke test for dependency overview and graph generation."""
        from app import CopilotEngine
        engine = CopilotEngine(str(self.repo_root), repo_id="phase4e_test_repo")

        # Test graph handler
        graph_res = engine.handle_dependency_graph()
        self.assertEqual(graph_res["query_type"], "DEPENDENCY")
        self.assertIn("graph_url", graph_res)

        # Test count handler
        count_res = engine.handle_repository_count("functions")
        self.assertIn("Total Functions", count_res["answer"])

    def test_20_real_codexa_repository_integration_smoke_test(self):
        """Full integration test on real Codexa repository files."""
        codexa_root = PROJECT_ROOT
        files = [
            codexa_root / "app.py",
            codexa_root / "parser" / "dependency_analyzer.py",
            codexa_root / "parser" / "fqsn_resolver.py",
        ]

        da = DependencyAnalyzer(files, repo_root=codexa_root)
        deps, rev_deps = da.get_function_dependencies()

        self.assertGreater(len(deps), 0)
        self.assertIn("DependencyAnalyzer", da.symbol_table.all_names())


if __name__ == "__main__":
    unittest.main()
