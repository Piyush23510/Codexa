"""
Phase 4B Test Suite: Hierarchical AST & Scope-Stack Symbol Extraction

Tests:
  1. test_class_method_hierarchy: User.save vs Order.save FQSN separation
  2. test_nested_function_extraction: Nested functions inside functions & methods
  3. test_async_function_support: Async functions/methods marked is_async=True
  4. test_argument_extraction: Arguments captured, 'self'/'cls' stripped for methods
  5. test_docstring_extraction: Docstrings attached to classes, methods, functions
  6. test_source_code_extraction: Source code snippet slicing
  7. test_line_numbers: start_line and end_line bounds
  8. test_symbol_types: Correct classification (CLASS, METHOD, FUNCTION, NESTED_FUNCTION)
  9. test_parent_fqsn_chain: Parent FQSN linking across nesting levels
 10. test_ast_parser_integration: ASTParser.get_symbol_tree() interface
 11. test_fixture_repo_full_parse: Multi-file parse of phase4_test_repo
 12. test_smoke_actual_codexa_files: Smoke test on parser/ast_parser.py
 13. test_get_class_fqsn_and_children: Symbol.get_class_fqsn() and SymbolTable.get_children()
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
from parser.hierarchical_visitor import HierarchicalASTVisitor
from parser.symbol_table import SymbolTable, SymbolType


class TestPhase4BHierarchicalAST(unittest.TestCase):

    def setUp(self):
        self.fixture_dir = Path(__file__).parent / "fixtures" / "phase4_test_repo"
        self.repo_root = self.fixture_dir.resolve()

    def test_class_method_hierarchy(self):
        """User.save and Order.save must produce distinct FQSNs and never collapse."""
        user_file = self.fixture_dir / "models" / "user.py"
        order_file = self.fixture_dir / "models" / "order.py"

        st = SymbolTable()
        user_parser = ASTParser(user_file)
        user_parser.get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

        order_parser = ASTParser(order_file)
        order_parser.get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

        save_symbols = st.lookup_name("save")
        self.assertEqual(len(save_symbols), 2)

        fqsns = {s.fqsn for s in save_symbols}
        self.assertIn("models.user::User.save", fqsns)
        self.assertIn("models.order::Order.save", fqsns)

        for sym in save_symbols:
            self.assertEqual(sym.symbol_type, SymbolType.METHOD)
            self.assertIsNotNone(sym.parent_fqsn)

    def test_nested_function_extraction(self):
        """Nested functions inside functions or methods must be classified as NESTED_FUNCTION."""
        code = '''
def outer_func(x):
    """Outer docstring."""
    def inner_func(y):
        """Inner docstring."""
        return x + y
    return inner_func
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "nested_test.py"
            file_path.write_text(code, encoding="utf-8")

            parser = ASTParser(file_path)
            st = parser.get_symbol_tree(repo_root=tmp_path)

            outer_sym = st.get("nested_test::outer_func")
            self.assertIsNotNone(outer_sym)
            self.assertEqual(outer_sym.symbol_type, SymbolType.FUNCTION)

            inner_sym = st.get("nested_test::outer_func.inner_func")
            self.assertIsNotNone(inner_sym)
            self.assertEqual(inner_sym.symbol_type, SymbolType.NESTED_FUNCTION)
            self.assertEqual(inner_sym.parent_fqsn, "nested_test::outer_func")
            self.assertEqual(inner_sym.docstring, "Inner docstring.")

    def test_async_function_support(self):
        """Async functions and async methods must be flagged with is_async=True."""
        code = '''
class AsyncHandler:
    async def fetch_data(self, url):
        pass

async def process_queue():
    pass
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "async_test.py"
            file_path.write_text(code, encoding="utf-8")

            parser = ASTParser(file_path)
            st = parser.get_symbol_tree(repo_root=tmp_path)

            fetch_sym = st.get("async_test::AsyncHandler.fetch_data")
            self.assertIsNotNone(fetch_sym)
            self.assertTrue(fetch_sym.is_async)
            self.assertEqual(fetch_sym.symbol_type, SymbolType.METHOD)

            proc_sym = st.get("async_test::process_queue")
            self.assertIsNotNone(proc_sym)
            self.assertTrue(proc_sym.is_async)
            self.assertEqual(proc_sym.symbol_type, SymbolType.FUNCTION)

    def test_argument_extraction(self):
        """Method arguments must exclude 'self'/'cls', but capture positional, vararg, kwarg."""
        user_file = self.fixture_dir / "models" / "user.py"
        parser = ASTParser(user_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        init_sym = st.get("models.user::User.__init__")
        self.assertIsNotNone(init_sym)
        self.assertEqual(init_sym.arguments, ["name"])

        code = '''
def complex_args(a, b=1, *args, key=None, **kwargs):
    pass
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "args_test.py"
            file_path.write_text(code, encoding="utf-8")

            p = ASTParser(file_path)
            st2 = p.get_symbol_tree(repo_root=tmp_path)
            sym = st2.get("args_test::complex_args")
            self.assertIsNotNone(sym)
            self.assertIn("a", sym.arguments)
            self.assertIn("b", sym.arguments)
            self.assertIn("*args", sym.arguments)
            self.assertIn("key", sym.arguments)
            self.assertIn("**kwargs", sym.arguments)

    def test_docstring_extraction(self):
        """Docstrings should be cleanly extracted for classes and methods."""
        user_file = self.fixture_dir / "models" / "user.py"
        parser = ASTParser(user_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        user_class = st.get("models.user::User")
        self.assertIsNotNone(user_class)
        self.assertEqual(user_class.docstring, "Represents a user entity.")

        save_method = st.get("models.user::User.save")
        self.assertIsNotNone(save_method)
        self.assertEqual(save_method.docstring, "Persist user to storage.")

    def test_source_code_extraction(self):
        """Extracted source code snippet should match the definition."""
        user_file = self.fixture_dir / "models" / "user.py"
        parser = ASTParser(user_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        validate_sym = st.get("models.user::User.validate")
        self.assertIsNotNone(validate_sym)
        self.assertIsNotNone(validate_sym.source_code)
        self.assertIn("def validate(self):", validate_sym.source_code)
        self.assertIn("User name is required", validate_sym.source_code)

    def test_line_numbers(self):
        """start_line and end_line bounds must be positive and start_line <= end_line."""
        user_file = self.fixture_dir / "models" / "user.py"
        parser = ASTParser(user_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        for sym in st.lookup_file("models/user.py"):
            self.assertGreater(sym.start_line, 0)
            self.assertGreaterEqual(sym.end_line, sym.start_line)

    def test_symbol_types(self):
        """Verify correct SymbolType assignment across class, method, function, nested function."""
        code = '''
class Service:
    def execute(self):
        def helper():
            pass
        helper()

def standalone():
    pass
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "types_test.py"
            file_path.write_text(code, encoding="utf-8")

            parser = ASTParser(file_path)
            st = parser.get_symbol_tree(repo_root=tmp_path)

            self.assertEqual(st.get("types_test::Service").symbol_type, SymbolType.CLASS)
            self.assertEqual(st.get("types_test::Service.execute").symbol_type, SymbolType.METHOD)
            self.assertEqual(st.get("types_test::Service.execute.helper").symbol_type, SymbolType.NESTED_FUNCTION)
            self.assertEqual(st.get("types_test::standalone").symbol_type, SymbolType.FUNCTION)

    def test_parent_fqsn_chain(self):
        """Parent FQSN chain should accurately reflect enclosing hierarchy."""
        processor_file = self.fixture_dir / "services" / "processor.py"
        parser = ASTParser(processor_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        proc_class = st.get("services.processor::Processor")
        self.assertIsNotNone(proc_class)
        self.assertIsNone(proc_class.parent_fqsn)

        process_method = st.get("services.processor::Processor.run")
        self.assertIsNotNone(process_method)
        self.assertEqual(process_method.parent_fqsn, "services.processor::Processor")

        standalone = st.get("services.processor::process_all")
        self.assertIsNotNone(standalone)
        self.assertIsNone(standalone.parent_fqsn)

    def test_ast_parser_integration(self):
        """ASTParser.get_symbol_tree() should properly delegate to HierarchicalASTVisitor."""
        main_file = self.fixture_dir / "main.py"
        parser = ASTParser(main_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        self.assertIsInstance(st, SymbolTable)
        self.assertIn("main::run_pipeline", st)
        run_sym = st.get("main::run_pipeline")
        self.assertEqual(run_sym.symbol_type, SymbolType.FUNCTION)

    def test_fixture_repo_full_parse(self):
        """Parse all Python files in phase4_test_repo into one SymbolTable and verify disambiguation."""
        st = SymbolTable()
        py_files = list(self.fixture_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 0)

        for pf in py_files:
            parser = ASTParser(pf)
            parser.get_symbol_tree(repo_root=self.repo_root, symbol_table=st)

        # Disambiguation check for parse()
        parse_syms = st.lookup_name("parse")
        self.assertEqual(len(parse_syms), 2)
        parse_fqsns = {s.fqsn for s in parse_syms}
        self.assertIn("utils_a::parse", parse_fqsns)
        self.assertIn("utils_b::parse", parse_fqsns)

        # Disambiguation check for helper()
        helper_syms = st.lookup_name("helper")
        self.assertEqual(len(helper_syms), 2)
        helper_fqsns = {s.fqsn for s in helper_syms}
        self.assertIn("utils_a::helper", helper_fqsns)
        self.assertIn("utils_b::helper", helper_fqsns)

        # Disambiguation check for validate()
        validate_syms = st.lookup_name("validate")
        self.assertEqual(len(validate_syms), 2)
        validate_fqsns = {s.fqsn for s in validate_syms}
        self.assertIn("models.user::User.validate", validate_fqsns)
        self.assertIn("models.order::Order.validate", validate_fqsns)

    def test_smoke_actual_codexa_files(self):
        """Smoke test: Parse parser/ast_parser.py and parser/symbol_table.py from Codexa codebase."""
        codexa_root = Path(__file__).parent.parent
        ast_parser_file = codexa_root / "parser" / "ast_parser.py"
        symbol_table_file = codexa_root / "parser" / "symbol_table.py"

        st = SymbolTable()

        if ast_parser_file.exists():
            p1 = ASTParser(ast_parser_file)
            p1.get_symbol_tree(repo_root=codexa_root, symbol_table=st)
            self.assertIn("parser.ast_parser::ASTParser", st)
            self.assertIn("parser.ast_parser::ASTParser.get_symbol_tree", st)

        if symbol_table_file.exists():
            p2 = ASTParser(symbol_table_file)
            p2.get_symbol_tree(repo_root=codexa_root, symbol_table=st)
            self.assertIn("parser.symbol_table::SymbolTable", st)
            self.assertIn("parser.symbol_table::SymbolTable.register", st)

    def test_get_class_fqsn_and_children(self):
        """Verify Symbol.get_class_fqsn() and SymbolTable.get_children()."""
        user_file = self.fixture_dir / "models" / "user.py"
        parser = ASTParser(user_file)
        st = parser.get_symbol_tree(repo_root=self.repo_root)

        user_class = st.get("models.user::User")
        self.assertIsNone(user_class.get_class_fqsn())

        save_method = st.get("models.user::User.save")
        self.assertEqual(save_method.get_class_fqsn(), "models.user::User")

        children = st.get_children("models.user::User")
        child_names = {c.name for c in children}
        self.assertIn("__init__", child_names)
        self.assertIn("save", child_names)
        self.assertIn("validate", child_names)


if __name__ == "__main__":
    unittest.main()
