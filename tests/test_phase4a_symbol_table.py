"""
Phase 4A Test Suite: Symbol Table & FQSN Foundation

Tests:
  1. file_to_module_path() canonical conversion
  2. build_fqsn() construction
  3. Symbol dataclass properties
  4. SymbolTable registration and lookup
  5. SymbolTable deduplication and overwrite
  6. SymbolTable with the Phase 4 test fixture repository
  7. Edge cases (empty table, __init__.py, nested packages)
"""

import sys
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parser.symbol_table import (
    Symbol,
    SymbolTable,
    SymbolType,
    build_fqsn,
    file_to_module_path,
)

FIXTURE_REPO = PROJECT_ROOT / "tests" / "fixtures" / "phase4_test_repo"


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ---------------------------------------------------------------------------
# 1. file_to_module_path
# ---------------------------------------------------------------------------

def test_file_to_module_path_basic():
    separator("1a. file_to_module_path — basic conversions")

    cases = [
        (FIXTURE_REPO / "main.py", FIXTURE_REPO, "main"),
        (FIXTURE_REPO / "utils_a.py", FIXTURE_REPO, "utils_a"),
        (FIXTURE_REPO / "utils_b.py", FIXTURE_REPO, "utils_b"),
        (FIXTURE_REPO / "models" / "user.py", FIXTURE_REPO, "models.user"),
        (FIXTURE_REPO / "models" / "order.py", FIXTURE_REPO, "models.order"),
        (FIXTURE_REPO / "services" / "processor.py", FIXTURE_REPO, "services.processor"),
    ]

    for file_path, repo_root, expected in cases:
        result = file_to_module_path(file_path, repo_root)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {file_path.name:30s} → {result:30s} (expected: {expected})")
        assert result == expected, f"Expected '{expected}', got '{result}'"

    print("  [PASS] All basic file_to_module_path conversions correct")


def test_file_to_module_path_init():
    separator("1b. file_to_module_path — __init__.py handling")

    cases = [
        (FIXTURE_REPO / "models" / "__init__.py", FIXTURE_REPO, "models"),
        (FIXTURE_REPO / "services" / "__init__.py", FIXTURE_REPO, "services"),
    ]

    for file_path, repo_root, expected in cases:
        result = file_to_module_path(file_path, repo_root)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {file_path.name:30s} in {file_path.parent.name:15s} → {result} (expected: {expected})")
        assert result == expected, f"Expected '{expected}', got '{result}'"

    print("  [PASS] __init__.py module path handling correct")


def test_file_to_module_path_errors():
    separator("1c. file_to_module_path — error handling")

    # File not under repo root
    try:
        file_to_module_path(Path("/tmp/other/file.py"), FIXTURE_REPO)
        print("  [FAIL] Should have raised ValueError for file outside repo")
        assert False
    except ValueError as e:
        print(f"  [PASS] Correctly raised ValueError for file outside repo: {e}")

    # Non-Python file
    try:
        file_to_module_path(FIXTURE_REPO / "README.md", FIXTURE_REPO)
        print("  [FAIL] Should have raised ValueError for non-.py file")
        assert False
    except ValueError as e:
        print(f"  [PASS] Correctly raised ValueError for non-Python file: {e}")


# ---------------------------------------------------------------------------
# 2. build_fqsn
# ---------------------------------------------------------------------------

def test_build_fqsn():
    separator("2. build_fqsn — canonical FQSN construction")

    cases = [
        ("utils.similarity", ["clean_text"], "utils.similarity::clean_text"),
        ("app", ["analyze"], "app::analyze"),
        ("parser.ast_parser", ["ASTParser"], "parser.ast_parser::ASTParser"),
        ("parser.ast_parser", ["ASTParser", "get_functions"], "parser.ast_parser::ASTParser.get_functions"),
        ("parser.dependency_analyzer", ["DependencyAnalyzer", "get_impact_analysis", "find_impact"],
         "parser.dependency_analyzer::DependencyAnalyzer.get_impact_analysis.find_impact"),
    ]

    for module_path, scope_chain, expected in cases:
        result = build_fqsn(module_path, scope_chain)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {module_path}::{'.'.join(scope_chain):40s} → {result}")
        assert result == expected, f"Expected '{expected}', got '{result}'"

    # Error case: empty scope chain
    try:
        build_fqsn("module", [])
        print("  [FAIL] Should have raised ValueError for empty scope_chain")
        assert False
    except ValueError:
        print("  [PASS] Correctly raised ValueError for empty scope_chain")

    print("  [PASS] All build_fqsn constructions correct")


# ---------------------------------------------------------------------------
# 3. Symbol dataclass
# ---------------------------------------------------------------------------

def test_symbol_properties():
    separator("3. Symbol — dataclass properties")

    # Module-level function
    func_sym = Symbol(
        fqsn="utils.similarity::clean_text",
        name="clean_text",
        symbol_type=SymbolType.FUNCTION,
        file_path="utils/similarity.py",
        module_path="utils.similarity",
        parent_fqsn=None,
        start_line=7,
        end_line=41,
        arguments=["text"],
        docstring="Clean input text.",
        is_async=False,
        source_code="def clean_text(text): ...",
    )

    assert func_sym.display_name == "clean_text"
    assert func_sym.is_callable is True
    print(f"  [PASS] Function symbol: display_name='{func_sym.display_name}', is_callable={func_sym.is_callable}")

    # Class
    class_sym = Symbol(
        fqsn="models.user::User",
        name="User",
        symbol_type=SymbolType.CLASS,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn=None,
        start_line=9,
        end_line=25,
    )

    assert class_sym.display_name == "User"
    assert class_sym.is_callable is True  # classes are callable (instantiation)
    print(f"  [PASS] Class symbol: display_name='{class_sym.display_name}', is_callable={class_sym.is_callable}")

    # Method
    method_sym = Symbol(
        fqsn="models.user::User.save",
        name="save",
        symbol_type=SymbolType.METHOD,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn="models.user::User",
        start_line=17,
        end_line=20,
    )

    assert method_sym.display_name == "User.save"
    assert method_sym.is_callable is True
    assert method_sym.parent_fqsn == "models.user::User"
    print(f"  [PASS] Method symbol: display_name='{method_sym.display_name}', parent='{method_sym.parent_fqsn}'")

    # Module (not callable)
    mod_sym = Symbol(
        fqsn="utils.similarity::<module>",
        name="<module>",
        symbol_type=SymbolType.MODULE,
        file_path="utils/similarity.py",
        module_path="utils.similarity",
        parent_fqsn=None,
        start_line=1,
        end_line=84,
    )

    assert mod_sym.is_callable is False
    print(f"  [PASS] Module symbol: is_callable={mod_sym.is_callable}")

    # Nested function
    nested_sym = Symbol(
        fqsn="analyzer::outer.inner",
        name="inner",
        symbol_type=SymbolType.NESTED_FUNCTION,
        file_path="analyzer.py",
        module_path="analyzer",
        parent_fqsn="analyzer::outer",
        start_line=10,
        end_line=15,
    )

    assert nested_sym.display_name == "outer.inner"
    assert nested_sym.is_callable is True
    print(f"  [PASS] Nested function: display_name='{nested_sym.display_name}'")

    print("  [PASS] All Symbol property tests passed")


# ---------------------------------------------------------------------------
# 4. SymbolTable — registration and lookup
# ---------------------------------------------------------------------------

def test_symbol_table_basic():
    separator("4a. SymbolTable — register and get")

    st = SymbolTable()
    assert len(st) == 0
    print(f"  Empty table: len={len(st)}")

    # Register a function
    sym = Symbol(
        fqsn="utils_a::parse",
        name="parse",
        symbol_type=SymbolType.FUNCTION,
        file_path="utils_a.py",
        module_path="utils_a",
        parent_fqsn=None,
        start_line=8,
        end_line=11,
    )
    st.register(sym)

    assert len(st) == 1
    assert "utils_a::parse" in st
    assert st.get("utils_a::parse") is sym
    assert st.get("nonexistent::fqsn") is None
    print(f"  After registering 1 symbol: len={len(st)}, get works correctly")

    print("  [PASS] Basic register and get")


def test_symbol_table_lookup_name():
    separator("4b. SymbolTable — lookup_name (duplicate names)")

    st = SymbolTable()

    # Two functions with the same bare name in different modules
    sym_a = Symbol(
        fqsn="utils_a::parse",
        name="parse",
        symbol_type=SymbolType.FUNCTION,
        file_path="utils_a.py",
        module_path="utils_a",
        parent_fqsn=None,
        start_line=8,
        end_line=11,
    )

    sym_b = Symbol(
        fqsn="utils_b::parse",
        name="parse",
        symbol_type=SymbolType.FUNCTION,
        file_path="utils_b.py",
        module_path="utils_b",
        parent_fqsn=None,
        start_line=8,
        end_line=12,
    )

    st.register(sym_a)
    st.register(sym_b)

    matches = st.lookup_name("parse")
    assert len(matches) == 2, f"Expected 2 matches for 'parse', got {len(matches)}"

    fqsns = {s.fqsn for s in matches}
    assert "utils_a::parse" in fqsns
    assert "utils_b::parse" in fqsns
    print(f"  lookup_name('parse') returned {len(matches)} matches: {fqsns}")

    # Non-existent name
    no_matches = st.lookup_name("nonexistent")
    assert len(no_matches) == 0
    print(f"  lookup_name('nonexistent') returned {len(no_matches)} matches")

    print("  [PASS] lookup_name correctly returns multiple symbols with same bare name")


def test_symbol_table_lookup_file():
    separator("4c. SymbolTable — lookup_file")

    st = SymbolTable()

    sym1 = Symbol(
        fqsn="models.user::User",
        name="User",
        symbol_type=SymbolType.CLASS,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn=None,
        start_line=9,
        end_line=25,
    )

    sym2 = Symbol(
        fqsn="models.user::User.save",
        name="save",
        symbol_type=SymbolType.METHOD,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn="models.user::User",
        start_line=17,
        end_line=20,
    )

    sym3 = Symbol(
        fqsn="models.user::User.validate",
        name="validate",
        symbol_type=SymbolType.METHOD,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn="models.user::User",
        start_line=22,
        end_line=25,
    )

    st.register(sym1)
    st.register(sym2)
    st.register(sym3)

    file_symbols = st.lookup_file("models/user.py")
    assert len(file_symbols) == 3, f"Expected 3 symbols in models/user.py, got {len(file_symbols)}"
    print(f"  lookup_file('models/user.py') returned {len(file_symbols)} symbols")

    # Test backslash normalization
    file_symbols_bs = st.lookup_file("models\\user.py")
    assert len(file_symbols_bs) == 3, f"Backslash lookup should also work, got {len(file_symbols_bs)}"
    print(f"  lookup_file('models\\\\user.py') (backslash) returned {len(file_symbols_bs)} symbols")

    # Non-existent file
    no_file = st.lookup_file("nonexistent.py")
    assert len(no_file) == 0
    print(f"  lookup_file('nonexistent.py') returned {len(no_file)} symbols")

    print("  [PASS] lookup_file correctly returns all symbols in a file")


def test_symbol_table_lookup_module():
    separator("4d. SymbolTable — lookup_module")

    st = SymbolTable()

    sym1 = Symbol(
        fqsn="models.user::User",
        name="User",
        symbol_type=SymbolType.CLASS,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn=None,
        start_line=9,
        end_line=25,
    )

    sym2 = Symbol(
        fqsn="models.user::User.save",
        name="save",
        symbol_type=SymbolType.METHOD,
        file_path="models/user.py",
        module_path="models.user",
        parent_fqsn="models.user::User",
        start_line=17,
        end_line=20,
    )

    st.register(sym1)
    st.register(sym2)

    module_symbols = st.lookup_module("models.user")
    assert len(module_symbols) == 2
    print(f"  lookup_module('models.user') returned {len(module_symbols)} symbols")

    no_module = st.lookup_module("nonexistent.module")
    assert len(no_module) == 0
    print(f"  lookup_module('nonexistent.module') returned {len(no_module)} symbols")

    print("  [PASS] lookup_module works correctly")


def test_symbol_table_all_fqsns():
    separator("4e. SymbolTable — all_fqsns and all_callable_fqsns")

    st = SymbolTable()

    symbols = [
        Symbol(fqsn="main::run_pipeline", name="run_pipeline", symbol_type=SymbolType.FUNCTION,
               file_path="main.py", module_path="main", parent_fqsn=None, start_line=1, end_line=10),
        Symbol(fqsn="models.user::User", name="User", symbol_type=SymbolType.CLASS,
               file_path="models/user.py", module_path="models.user", parent_fqsn=None, start_line=9, end_line=25),
        Symbol(fqsn="models.user::User.save", name="save", symbol_type=SymbolType.METHOD,
               file_path="models/user.py", module_path="models.user", parent_fqsn="models.user::User", start_line=17, end_line=20),
        Symbol(fqsn="main::<module>", name="<module>", symbol_type=SymbolType.MODULE,
               file_path="main.py", module_path="main", parent_fqsn=None, start_line=1, end_line=30),
    ]

    for sym in symbols:
        st.register(sym)

    all_fqsns = st.all_fqsns()
    assert len(all_fqsns) == 4
    assert all_fqsns == sorted(all_fqsns)  # verify sorted
    print(f"  all_fqsns() returned {len(all_fqsns)} FQSNs (sorted)")

    callable_fqsns = st.all_callable_fqsns()
    assert len(callable_fqsns) == 3  # function, class, method — not module
    assert "main::<module>" not in callable_fqsns
    print(f"  all_callable_fqsns() returned {len(callable_fqsns)} (excludes MODULE)")

    print("  [PASS] all_fqsns and all_callable_fqsns correct")


# ---------------------------------------------------------------------------
# 5. SymbolTable — deduplication / overwrite
# ---------------------------------------------------------------------------

def test_symbol_table_overwrite():
    separator("5. SymbolTable — FQSN overwrite behavior")

    st = SymbolTable()

    sym_v1 = Symbol(
        fqsn="utils_a::parse",
        name="parse",
        symbol_type=SymbolType.FUNCTION,
        file_path="utils_a.py",
        module_path="utils_a",
        parent_fqsn=None,
        start_line=8,
        end_line=11,
        docstring="Version 1",
    )

    sym_v2 = Symbol(
        fqsn="utils_a::parse",
        name="parse",
        symbol_type=SymbolType.FUNCTION,
        file_path="utils_a.py",
        module_path="utils_a",
        parent_fqsn=None,
        start_line=8,
        end_line=15,  # extended
        docstring="Version 2",
    )

    st.register(sym_v1)
    assert len(st) == 1
    assert st.get("utils_a::parse").docstring == "Version 1"

    st.register(sym_v2)
    assert len(st) == 1  # still 1 — overwritten, not duplicated
    assert st.get("utils_a::parse").docstring == "Version 2"

    # Secondary indexes should not have duplicates
    matches = st.lookup_name("parse")
    assert len(matches) == 1, f"Expected 1 match after overwrite, got {len(matches)}"

    file_matches = st.lookup_file("utils_a.py")
    assert len(file_matches) == 1, f"Expected 1 file match after overwrite, got {len(file_matches)}"

    print(f"  After overwrite: len={len(st)}, lookup_name count={len(matches)}")
    print("  [PASS] FQSN overwrite correctly replaces symbol and cleans secondary indexes")


# ---------------------------------------------------------------------------
# 6. SymbolTable with fixture repository (data-driven)
# ---------------------------------------------------------------------------

def test_symbol_table_fixture_repo():
    separator("6. SymbolTable — fixture repository data-driven test")

    # Define all expected symbols from the fixture repo
    expected_symbols = [
        # main.py
        ("main::run_pipeline", "run_pipeline", SymbolType.FUNCTION, "main.py", "main", None),
        ("main::report", "report", SymbolType.FUNCTION, "main.py", "main", None),

        # utils_a.py
        ("utils_a::parse", "parse", SymbolType.FUNCTION, "utils_a.py", "utils_a", None),
        ("utils_a::helper", "helper", SymbolType.FUNCTION, "utils_a.py", "utils_a", None),

        # utils_b.py
        ("utils_b::parse", "parse", SymbolType.FUNCTION, "utils_b.py", "utils_b", None),
        ("utils_b::helper", "helper", SymbolType.FUNCTION, "utils_b.py", "utils_b", None),

        # models/user.py
        ("models.user::User", "User", SymbolType.CLASS, "models/user.py", "models.user", None),
        ("models.user::User.__init__", "__init__", SymbolType.METHOD, "models/user.py", "models.user", "models.user::User"),
        ("models.user::User.save", "save", SymbolType.METHOD, "models/user.py", "models.user", "models.user::User"),
        ("models.user::User.validate", "validate", SymbolType.METHOD, "models/user.py", "models.user", "models.user::User"),

        # models/order.py
        ("models.order::Order", "Order", SymbolType.CLASS, "models/order.py", "models.order", None),
        ("models.order::Order.__init__", "__init__", SymbolType.METHOD, "models/order.py", "models.order", "models.order::Order"),
        ("models.order::Order.save", "save", SymbolType.METHOD, "models/order.py", "models.order", "models.order::Order"),
        ("models.order::Order.validate", "validate", SymbolType.METHOD, "models/order.py", "models.order", "models.order::Order"),

        # services/processor.py
        ("services.processor::process_all", "process_all", SymbolType.FUNCTION, "services/processor.py", "services.processor", None),
        ("services.processor::_internal_helper", "_internal_helper", SymbolType.FUNCTION, "services/processor.py", "services.processor", None),
        ("services.processor::Processor", "Processor", SymbolType.CLASS, "services/processor.py", "services.processor", None),
        ("services.processor::Processor.__init__", "__init__", SymbolType.METHOD, "services/processor.py", "services.processor", "services.processor::Processor"),
        ("services.processor::Processor.run", "run", SymbolType.METHOD, "services/processor.py", "services.processor", "services.processor::Processor"),
        ("services.processor::Processor.reset", "reset", SymbolType.METHOD, "services/processor.py", "services.processor", "services.processor::Processor"),
    ]

    st = SymbolTable()

    for fqsn, name, sym_type, file_path, module_path, parent_fqsn in expected_symbols:
        sym = Symbol(
            fqsn=fqsn,
            name=name,
            symbol_type=sym_type,
            file_path=file_path,
            module_path=module_path,
            parent_fqsn=parent_fqsn,
            start_line=1,  # placeholder
            end_line=10,   # placeholder
        )
        st.register(sym)

    assert len(st) == len(expected_symbols), f"Expected {len(expected_symbols)} symbols, got {len(st)}"
    print(f"  Registered {len(st)} symbols from fixture repo")

    # Verify duplicate bare names are correctly tracked
    parse_matches = st.lookup_name("parse")
    assert len(parse_matches) == 2, f"Expected 2 'parse' symbols, got {len(parse_matches)}"
    parse_fqsns = {s.fqsn for s in parse_matches}
    assert parse_fqsns == {"utils_a::parse", "utils_b::parse"}
    print(f"  'parse' has {len(parse_matches)} matches: {parse_fqsns}")

    helper_matches = st.lookup_name("helper")
    assert len(helper_matches) == 2, f"Expected 2 'helper' symbols, got {len(helper_matches)}"
    print(f"  'helper' has {len(helper_matches)} matches")

    save_matches = st.lookup_name("save")
    assert len(save_matches) == 2, f"Expected 2 'save' methods, got {len(save_matches)}"
    save_fqsns = {s.fqsn for s in save_matches}
    assert save_fqsns == {"models.user::User.save", "models.order::Order.save"}
    print(f"  'save' has {len(save_matches)} matches: {save_fqsns}")

    validate_matches = st.lookup_name("validate")
    assert len(validate_matches) == 2, f"Expected 2 'validate' methods, got {len(validate_matches)}"
    print(f"  'validate' has {len(validate_matches)} matches")

    init_matches = st.lookup_name("__init__")
    assert len(init_matches) == 3, f"Expected 3 '__init__' methods, got {len(init_matches)}"
    print(f"  '__init__' has {len(init_matches)} matches (User, Order, Processor)")

    # Verify unique names
    run_pipeline_matches = st.lookup_name("run_pipeline")
    assert len(run_pipeline_matches) == 1
    print(f"  'run_pipeline' has {len(run_pipeline_matches)} match (unique)")

    # Verify file lookup
    user_symbols = st.lookup_file("models/user.py")
    assert len(user_symbols) == 4, f"Expected 4 symbols in models/user.py, got {len(user_symbols)}"
    print(f"  models/user.py has {len(user_symbols)} symbols (User + 3 methods)")

    # Verify module lookup
    processor_symbols = st.lookup_module("services.processor")
    assert len(processor_symbols) == 6, f"Expected 6 symbols in services.processor, got {len(processor_symbols)}"
    print(f"  services.processor module has {len(processor_symbols)} symbols")

    # Verify callable filtering
    callables = st.all_callable_fqsns()
    assert len(callables) == len(expected_symbols)  # all are callable (functions, methods, classes)
    print(f"  all_callable_fqsns: {len(callables)} (all symbols in fixture are callable)")

    print("  [PASS] Fixture repository symbol table populated and verified correctly")


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------

def test_edge_cases():
    separator("7. Edge cases")

    # 7a. Empty table
    st = SymbolTable()
    assert len(st) == 0
    assert st.all_fqsns() == []
    assert st.all_callable_fqsns() == []
    assert st.lookup_name("anything") == []
    assert st.lookup_file("any.py") == []
    assert st.lookup_module("any.module") == []
    assert st.get("any::fqsn") is None
    assert ("any::fqsn" in st) is False
    print("  [PASS] Empty table returns empty results for all lookups")

    # 7b. all_names
    st.register(Symbol(
        fqsn="a::x", name="x", symbol_type=SymbolType.FUNCTION,
        file_path="a.py", module_path="a", parent_fqsn=None,
        start_line=1, end_line=2,
    ))
    st.register(Symbol(
        fqsn="b::x", name="x", symbol_type=SymbolType.FUNCTION,
        file_path="b.py", module_path="b", parent_fqsn=None,
        start_line=1, end_line=2,
    ))
    st.register(Symbol(
        fqsn="a::y", name="y", symbol_type=SymbolType.FUNCTION,
        file_path="a.py", module_path="a", parent_fqsn=None,
        start_line=3, end_line=4,
    ))

    all_names = st.all_names()
    assert all_names == ["x", "y"], f"Expected ['x', 'y'], got {all_names}"
    print(f"  [PASS] all_names returns {all_names} (sorted, deduplicated)")

    # 7c. SymbolType values are strings (for JSON serialization)
    assert SymbolType.FUNCTION == "function"
    assert SymbolType.METHOD == "method"
    assert SymbolType.CLASS == "class"
    assert SymbolType.MODULE == "module"
    assert SymbolType.NESTED_FUNCTION == "nested_function"
    print("  [PASS] SymbolType values are plain strings (JSON-serializable)")

    # 7d. Contains operator
    st2 = SymbolTable()
    st2.register(Symbol(
        fqsn="test::func", name="func", symbol_type=SymbolType.FUNCTION,
        file_path="test.py", module_path="test", parent_fqsn=None,
        start_line=1, end_line=5,
    ))
    assert "test::func" in st2
    assert "test::other" not in st2
    print("  [PASS] __contains__ operator works correctly")

    print("  [PASS] All edge cases passed")


# ---------------------------------------------------------------------------
# 8. file_to_module_path with the actual fixture repo paths
# ---------------------------------------------------------------------------

def test_file_to_module_path_real_fixtures():
    separator("8. file_to_module_path — real fixture repo paths")

    fixture_files = list(FIXTURE_REPO.rglob("*.py"))

    expected_mapping = {
        "main.py": "main",
        "utils_a.py": "utils_a",
        "utils_b.py": "utils_b",
        "__init__.py": None,  # depends on parent
        "user.py": "models.user",
        "order.py": "models.order",
        "processor.py": "services.processor",
    }

    for file_path in fixture_files:
        result = file_to_module_path(file_path, FIXTURE_REPO)
        print(f"  {str(file_path.relative_to(FIXTURE_REPO)):40s} → {result}")

        # Verify specific expected values
        fname = file_path.name
        if fname in expected_mapping and expected_mapping[fname] is not None:
            assert result == expected_mapping[fname], \
                f"Expected '{expected_mapping[fname]}' for {fname}, got '{result}'"

    print("  [PASS] All real fixture paths converted correctly")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 70)
    print("  PHASE 4A TEST SUITE: Symbol Table & FQSN Foundation")
    print("=" * 70)

    test_file_to_module_path_basic()
    test_file_to_module_path_init()
    test_file_to_module_path_errors()
    test_build_fqsn()
    test_symbol_properties()
    test_symbol_table_basic()
    test_symbol_table_lookup_name()
    test_symbol_table_lookup_file()
    test_symbol_table_lookup_module()
    test_symbol_table_all_fqsns()
    test_symbol_table_overwrite()
    test_symbol_table_fixture_repo()
    test_edge_cases()
    test_file_to_module_path_real_fixtures()

    separator("ALL PHASE 4A TESTS PASSED")
    print("  Symbol Table & FQSN foundation is verified and isolated.\n")


if __name__ == "__main__":
    main()
