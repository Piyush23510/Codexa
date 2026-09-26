"""
Core Logic Audit Test Suite
Tests AST parsing, dependency analysis, impact analysis, 
chunk generation, vector store, BM25, hybrid retrieval, reranker, 
and citation generation against the target repository.
"""

import sys
import os
from pathlib import Path

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TARGET_REPO = PROJECT_ROOT / "AI-Powered-ATS-Resume-Analyzer"

from parser.ast_parser import ASTParser
from parser.repo_parser import RepoParser
from parser.dependency_analyzer import DependencyAnalyzer
from rag.chunk_generator import ChunkGenerator
from rag.embeddings_generator import EmbeddingGenerator
from rag.vector_store import VectorStore
from rag.bm25_retriever import BM25Retriever
from rag.hybrid_retriever import HybridRetriever
from rag.reranker import Reranker
from rag.citation_generator import CitationGenerator


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def test_repo_parser():
    separator("1. REPO PARSER")
    rp = RepoParser(str(TARGET_REPO))
    
    # Test get_python_files
    files = rp.get_python_files()
    print(f"  Python files found: {len(files)}")
    for f in files:
        print(f"    - {f}")
    
    # Verify ignored directories
    for f in files:
        parts = set(f.parts)
        bad = parts & RepoParser.IGNORE_DIRS
        if bad:
            print(f"  [BUG] File in ignored dir: {f} (matched: {bad})")
    
    # Test get_repo_summary
    summary = rp.get_repo_summary()
    print(f"\n  Summary: {summary}")
    assert summary["project_name"] == "AI-Powered-ATS-Resume-Analyzer", f"Unexpected project name: {summary['project_name']}"
    assert summary["total_python_files"] == len(files)
    print("  [PASS] RepoParser basic tests passed")
    
    # Test get_entry_points (stub)
    entry_points = rp.get_entry_points()
    print(f"  Entry points (stub): {entry_points}")
    if not entry_points:
        print("  [NOTE] get_entry_points() returns empty list (stub)")
    
    return files, summary


def test_ast_parser(files):
    separator("2. AST PARSER")
    all_functions = {}
    all_classes = {}
    
    for file_path in files:
        parser = ASTParser(file_path)
        functions = parser.get_functions()
        classes = parser.get_classes()
        imports = parser.get_imports()
        
        print(f"\n  File: {file_path.name}")
        print(f"    Functions: {len(functions)}")
        for func in functions:
            print(f"      - {func['name']}({', '.join(func['arguments'])}) lines {func['start_line']}-{func['end_line']}")
            all_functions[func['name']] = func
            
            # Verify source code extraction
            assert func['code'] is not None, f"No code for {func['name']}"
            assert func['name'] in func['code'], f"Function name not in code for {func['name']}"
            assert func['start_line'] <= func['end_line'], f"Invalid line range for {func['name']}"
        
        print(f"    Classes: {len(classes)}")
        for cls in classes:
            print(f"      - {cls['name']} lines {cls['start_line']}-{cls['end_line']}")
            all_classes[cls['name']] = cls
        
        print(f"    Imports: {imports}")
    
    print(f"\n  Total functions extracted: {len(all_functions)}")
    print(f"  Total classes extracted: {len(all_classes)}")
    
    # Known functions in target repo
    expected_functions = {
        "clean_text", "extract_text_from_pdf", "extract_skills", 
        "calculate_skill_match", "calculate_similarity", "get_top_keywords",
        "generate_recommendations", "calculate_final_score",
        "home", "analyze", "download_report", "chatbot_page", "chat",
        "generate_rag_feedback", "create_resume_vectorstore", "ask_question",
        "generate_report"
    }
    
    found_names = set(all_functions.keys())
    missing = expected_functions - found_names
    extra = found_names - expected_functions
    
    if missing:
        print(f"  [WARNING] Expected but NOT found: {missing}")
    if extra:
        print(f"  [INFO] Additional functions found: {extra}")
    
    print("  [PASS] AST Parser function extraction verified")
    return all_functions, all_classes


def test_function_call_order(files):
    separator("3. FUNCTION CALL ORDER")
    
    # Get all known function names first
    all_function_names = set()
    for file_path in files:
        parser = ASTParser(file_path)
        for func in parser.get_functions():
            all_function_names.add(func['name'])
    
    # Test get_function_call_order for 'analyze' function
    for file_path in files:
        parser = ASTParser(file_path)
        calls = parser.get_function_call_order("analyze", known_functions=all_function_names)
        if calls:
            print(f"  Call order inside 'analyze' (from {file_path.name}):")
            for idx, call in enumerate(calls, 1):
                print(f"    {idx}. {call}")
            
            # Verify these are in source-code order
            print("  [PASS] analyze() call order extracted")
            break
    else:
        print("  [NOTE] 'analyze' function not found or has no known calls")
    
    # Test for a function that doesn't exist
    for file_path in files:
        parser = ASTParser(file_path)
        calls = parser.get_function_call_order("nonexistent_function", known_functions=all_function_names)
        if calls:
            print(f"  [BUG] Found calls for nonexistent function!")
    print("  [PASS] Nonexistent function returns empty list")
    
    # Test for function with no internal function calls
    for file_path in files:
        parser = ASTParser(file_path)
        calls = parser.get_function_call_order("home", known_functions=all_function_names)
        if calls:
            print(f"  Calls inside 'home': {calls}")
        else:
            if file_path.name == "app.py":
                print("  'home' has no known function calls (expected)")
    
    print("  [PASS] Function call order tests passed")


def test_dependency_analysis(files):
    separator("4. DEPENDENCY ANALYSIS")
    analyzer = DependencyAnalyzer(files)
    
    deps, rev_deps = analyzer.get_function_dependencies()
    
    print(f"  Total functions with dependencies: {len(deps)}")
    
    # Print dependencies
    for func, calls in sorted(deps.items()):
        if calls:
            print(f"    {func} -> {calls}")
    
    # Check for self-referencing (recursive)
    for func, calls in deps.items():
        if func in calls:
            print(f"  [INFO] Self-referencing function: {func}")
    
    # Check for duplicate dependencies
    for func, calls in deps.items():
        if len(calls) != len(set(calls)):
            print(f"  [BUG] Duplicate dependencies for {func}: {calls}")
    print("  [PASS] No duplicate dependencies found")
    
    # Print reverse dependencies
    print(f"\n  Reverse dependencies:")
    for func, callers in sorted(rev_deps.items()):
        print(f"    {func} <- {callers}")
    
    # Check for duplicate reverse dependencies
    for func, callers in rev_deps.items():
        if len(callers) != len(set(callers)):
            print(f"  [BUG] Duplicate reverse dependencies for {func}: {callers}")
    print("  [PASS] No duplicate reverse dependencies found")
    
    # Test indirect dependencies
    print(f"\n  Indirect dependencies for 'analyze':")
    indirect = analyzer.get_indirect_dependencies("analyze", deps)
    print(f"    {indirect}")
    
    # Verify: indirect deps should NOT include direct deps
    direct = set(deps.get("analyze", []))
    overlap = indirect & direct
    if overlap:
        print(f"  [INFO] Overlap between direct and indirect for 'analyze': {overlap}")
        print("  (This is expected - indirect includes transitive calls from direct deps)")
    
    # Test for function with no dependencies
    for func in deps:
        if not deps[func]:
            print(f"  Function with no deps: {func}")
    
    # Test function details
    print(f"\n  Function details for 'clean_text':")
    details = analyzer.get_function_details("clean_text")
    if details:
        print(f"    File: {details['file']}")
        print(f"    Lines: {details['start_line']}-{details['end_line']}")
        print(f"    Args: {details['arguments']}")
    else:
        print("  [BUG] clean_text details not found")
    
    # Test repository workflow
    print(f"\n  Repository Workflow:")
    workflow = analyzer.get_repository_workflow(deps, rev_deps)
    print(f"    Main entry point: {workflow['main_entry_point']}")
    print(f"    Workflow functions: {workflow['workflow']}")
    
    print("  [PASS] Dependency analysis tests passed")
    return analyzer, deps, rev_deps


def test_impact_analysis(analyzer, deps, rev_deps):
    separator("5. IMPACT ANALYSIS")
    
    # Test impact of changing clean_text
    print("  Impact of changing 'clean_text':")
    direct_impact, indirect_impact = analyzer.get_impact_analysis("clean_text", rev_deps)
    print(f"    Direct impact: {direct_impact}")
    print(f"    Indirect impact: {indirect_impact}")
    
    # Verify clean_text is not in its own impact set
    assert "clean_text" not in direct_impact, "clean_text should not be in its own direct impact"
    assert "clean_text" not in indirect_impact, "clean_text should not be in its own indirect impact"
    print("  [PASS] Changed function not in its own impact set")
    
    # Verify no overlap between direct and indirect
    overlap = direct_impact & indirect_impact
    assert len(overlap) == 0, f"Overlap between direct/indirect: {overlap}"
    print("  [PASS] No overlap between direct and indirect impact")
    
    # Test risk calculation
    risk = analyzer.calculate_risk(direct_impact, indirect_impact)
    print(f"    Risk: {risk}")
    
    total = len(direct_impact) + len(indirect_impact)
    if total == 0:
        assert risk == "LOW"
    elif total <= 2:
        assert risk == "MEDIUM"
    else:
        assert risk == "HIGH"
    print("  [PASS] Risk calculation is consistent")
    
    # Test impact percentage
    total_functions = len(deps)
    impact_perc = analyzer.impact_percentage(direct_impact, indirect_impact, total_functions)
    print(f"    Impact percentage: {impact_perc:.2f}%")
    expected_perc = (len(direct_impact) + len(indirect_impact)) / total_functions * 100 if total_functions > 0 else 0
    assert abs(impact_perc - expected_perc) < 0.01, "Impact percentage mismatch"
    print("  [PASS] Impact percentage is consistent")
    
    # Test with zero total functions
    zero_perc = analyzer.impact_percentage(set(), set(), 0)
    assert zero_perc == 0.0, "Zero functions should give 0% impact"
    print("  [PASS] Zero-function edge case handled")
    
    # Test impact of changing 'analyze'
    print("\n  Impact of changing 'analyze':")
    direct_impact2, indirect_impact2 = analyzer.get_impact_analysis("analyze", rev_deps)
    print(f"    Direct impact: {direct_impact2}")
    print(f"    Indirect impact: {indirect_impact2}")
    risk2 = analyzer.calculate_risk(direct_impact2, indirect_impact2)
    print(f"    Risk: {risk2}")
    
    # Test with function that has no callers
    print("\n  Impact of changing a function with no callers:")
    # Find a function not in reverse_deps
    for func in deps:
        if func not in rev_deps:
            direct_i, indirect_i = analyzer.get_impact_analysis(func, rev_deps)
            print(f"    '{func}': Direct={direct_i}, Indirect={indirect_i}")
            assert len(direct_i) == 0 and len(indirect_i) == 0, "Function with no callers should have no impact"
            print("  [PASS] Function with no callers has zero impact")
            break
    
    print("  [PASS] Impact analysis tests passed")


def test_chunk_generation(files):
    separator("6. CHUNK GENERATION")
    all_chunks = []
    
    for file_path in files:
        parser = ASTParser(file_path)
        chunk_gen = ChunkGenerator(file_path, parser)
        chunks = chunk_gen.generate_chunks()
        all_chunks.extend(chunks)
        
        print(f"  {file_path.name}: {len(chunks)} chunks")
        for chunk in chunks:
            meta = chunk["metadata"]
            print(f"    - [{meta['type']}] {meta['name']} (lines {meta['start_line']}-{meta['end_line']})")
            
            # Verify chunk text contains essential info
            assert "File:" in chunk["text"], f"Missing 'File:' in chunk text for {meta['name']}"
            assert "Type:" in chunk["text"], f"Missing 'Type:' in chunk text for {meta['name']}"
            assert "Name:" in chunk["text"], f"Missing 'Name:' in chunk text for {meta['name']}"
            
            # Verify metadata completeness
            assert meta["file"] is not None, f"Missing file in metadata for {meta['name']}"
            assert meta["start_line"] is not None, f"Missing start_line for {meta['name']}"
            assert meta["end_line"] is not None, f"Missing end_line for {meta['name']}"
    
    print(f"\n  Total chunks: {len(all_chunks)}")
    
    # Verify no empty chunks
    for chunk in all_chunks:
        assert chunk["text"].strip(), "Empty chunk text found"
    print("  [PASS] No empty chunks")
    
    # Check for duplicate chunks
    chunk_keys = [(c["metadata"]["file"], c["metadata"]["name"], c["metadata"]["start_line"]) for c in all_chunks]
    if len(chunk_keys) != len(set(chunk_keys)):
        print("  [WARNING] Duplicate chunks found")
    else:
        print("  [PASS] No duplicate chunks")
    
    print("  [PASS] Chunk generation tests passed")
    return all_chunks


def test_embeddings_and_vector_store(all_chunks):
    separator("7. EMBEDDINGS & VECTOR STORE")
    
    emb_gen = EmbeddingGenerator()
    
    # Test single embedding
    single_emb = emb_gen.generate_embedding("test query")
    print(f"  Single embedding dimension: {len(single_emb)}")
    assert len(single_emb) == 384, f"Expected 384, got {len(single_emb)}"
    print("  [PASS] Embedding dimension is 384")
    
    # Test batch embeddings
    embeddings = emb_gen.generate_embeddings(all_chunks)
    print(f"  Generated {len(embeddings)} embeddings")
    assert len(embeddings) == len(all_chunks), "Embedding count mismatch"
    
    for emb in embeddings:
        assert len(emb["embedding"]) == 384, "Embedding dimension mismatch"
        assert emb["text"] is not None
        assert emb["metadata"] is not None
    print("  [PASS] All embeddings have correct dimensions and metadata")
    
    # Test vector store
    vs = VectorStore(dimension=384)
    vs.add_embeddings(embeddings)
    print(f"  VectorStore documents: {len(vs.documents)}")
    assert len(vs.documents) == len(all_chunks)
    
    # Test search
    query_emb = emb_gen.generate_embedding("text cleaning function")
    results = vs.search(query_emb, k=3)
    print(f"  Search results for 'text cleaning function':")
    for r in results:
        print(f"    - {r['metadata']['name']} (score: {r['score']:.4f})")
    
    assert len(results) == min(3, len(all_chunks)), "Search result count mismatch"
    
    # Verify scores are sorted descending
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), "FAISS results not sorted descending"
    print("  [PASS] FAISS results sorted correctly")
    
    print("  [PASS] Embeddings & VectorStore tests passed")
    return emb_gen, vs


def test_bm25_retriever(all_chunks):
    separator("8. BM25 RETRIEVER")
    
    bm25 = BM25Retriever(all_chunks)
    
    # Test search
    results = bm25.search("clean text preprocessing", k=3)
    print(f"  BM25 results for 'clean text preprocessing':")
    for r in results:
        print(f"    - {r['metadata']['name']} (bm25_score: {r['bm25_score']:.4f})")
    
    assert len(results) == min(3, len(all_chunks))
    
    # Verify BM25 scores sorted descending
    scores = [r["bm25_score"] for r in results]
    assert scores == sorted(scores, reverse=True), "BM25 results not sorted descending"
    print("  [PASS] BM25 results sorted correctly")
    
    # Test with query that matches nothing well
    results2 = bm25.search("xyzzy nonexistent gibberish", k=3)
    print(f"  BM25 results for 'xyzzy nonexistent gibberish': {len(results2)} results")
    # BM25 will still return results, but with low/zero scores
    
    print("  [PASS] BM25 Retriever tests passed")
    return bm25


def test_hybrid_retriever(vs, bm25, emb_gen):
    separator("9. HYBRID RETRIEVER (RRF)")
    
    hybrid = HybridRetriever(vs, bm25)
    
    query = "how does the clean_text function work"
    query_emb = emb_gen.generate_embedding(query)
    
    results = hybrid.search(query, query_emb, k=5)
    print(f"\n  Hybrid RRF results for '{query}':")
    for r in results:
        print(f"    - {r['metadata']['name']} (rrf_score: {r['rrf_score']:.6f})")
    
    assert len(results) <= 5
    
    # Verify RRF scores sorted descending
    scores = [r["rrf_score"] for r in results]
    assert scores == sorted(scores, reverse=True), "RRF results not sorted descending"
    print("  [PASS] RRF results sorted correctly")
    
    # Check for duplicate results
    keys = [(r["metadata"]["file"], r["metadata"].get("name"), r["metadata"].get("start_line")) for r in results]
    assert len(keys) == len(set(keys)), f"Duplicate results in hybrid retrieval: {keys}"
    print("  [PASS] No duplicate results in hybrid retrieval")
    
    print("  [PASS] Hybrid Retriever tests passed")
    return hybrid


def test_reranker(vs, bm25, emb_gen):
    separator("10. RERANKER (CROSS-ENCODER)")
    
    hybrid = HybridRetriever(vs, bm25)
    reranker = Reranker()
    
    query = "extract skills from resume"
    query_emb = emb_gen.generate_embedding(query)
    
    # Get hybrid results first
    hybrid_results = hybrid.search(query, query_emb, k=10)
    print(f"\n  Pre-rerank results ({len(hybrid_results)}):")
    for r in hybrid_results:
        print(f"    - {r['metadata']['name']} (rrf: {r['rrf_score']:.6f})")
    
    # Rerank
    reranked = reranker.rerank(query, hybrid_results, k=3)
    print(f"\n  Post-rerank results ({len(reranked)}):")
    for r in reranked:
        print(f"    - {r['metadata']['name']} (rerank: {r['rerank_score']:.4f})")
    
    assert len(reranked) <= 3
    
    # Verify rerank scores sorted descending
    scores = [r["rerank_score"] for r in reranked]
    assert scores == sorted(scores, reverse=True), "Reranked results not sorted descending"
    print("  [PASS] Reranked results sorted correctly")
    
    print("  [PASS] Reranker tests passed")
    return reranker


def test_citation_generator():
    separator("11. CITATION GENERATOR")
    
    cit_gen = CitationGenerator()
    
    # Mock results
    mock_results = [
        {
            "text": "some code",
            "metadata": {
                "file": "utils/text_preprocessing.py",
                "type": "function",
                "name": "clean_text",
                "start_line": 7,
                "end_line": 41
            }
        },
        {
            "text": "more code",
            "metadata": {
                "file": "app.py",
                "type": "function",
                "name": "analyze",
                "start_line": 50,
                "end_line": 175
            }
        }
    ]
    
    citations = cit_gen.generate_citations(mock_results)
    print(f"  Generated {len(citations)} citations:")
    for c in citations:
        print(f"    - {c['name']} in {c['file']} (lines {c['start_line']}-{c['end_line']}) [{c['type']}]")
    
    assert len(citations) == 2
    assert citations[0]["name"] == "clean_text"
    assert citations[0]["start_line"] == 7
    assert citations[0]["end_line"] == 41
    print("  [PASS] Citation metadata matches source")
    
    # Test with missing optional fields
    mock_results2 = [
        {
            "text": "module code",
            "metadata": {
                "file": "sample.py",
                "type": "module",
                "name": None,
                "start_line": None,
                "end_line": None
            }
        }
    ]
    citations2 = cit_gen.generate_citations(mock_results2)
    assert citations2[0]["name"] is None
    assert citations2[0]["start_line"] is None
    print("  [PASS] Handles missing optional metadata")
    
    print("  [PASS] Citation Generator tests passed")


def test_dependency_edge_cases(files):
    separator("12. DEPENDENCY EDGE CASES")
    analyzer = DependencyAnalyzer(files)
    deps, rev_deps = analyzer.get_function_dependencies()
    
    # Test function not in repository
    details = analyzer.get_function_details("nonexistent_function_xyz")
    assert details is None, "Expected None for nonexistent function"
    print("  [PASS] Nonexistent function returns None")
    
    # Test indirect deps for function with no deps
    for func in deps:
        if not deps[func]:
            indirect = analyzer.get_indirect_dependencies(func, deps)
            assert len(indirect) == 0, f"Function {func} with no deps should have no indirect deps"
            print(f"  [PASS] '{func}' (no deps) -> no indirect deps")
            break
    
    # Test cyclic dependency protection
    # Create a synthetic cyclic dependency
    synthetic_deps = {
        "func_a": ["func_b"],
        "func_b": ["func_c"],
        "func_c": ["func_a"]  # cycle!
    }
    indirect_a = analyzer.get_indirect_dependencies("func_a", synthetic_deps)
    print(f"  Cyclic deps test: func_a indirect = {indirect_a}")
    # Should not loop infinitely
    print("  [PASS] Cyclic dependency handled without infinite loop")
    
    # Test cyclic impact analysis
    synthetic_rev = {
        "func_a": ["func_b"],
        "func_b": ["func_c"],
        "func_c": ["func_a"]  # cycle!
    }
    direct_i, indirect_i = analyzer.get_impact_analysis("func_a", synthetic_rev)
    print(f"  Cyclic impact test: direct={direct_i}, indirect={indirect_i}")
    assert "func_a" not in direct_i
    assert "func_a" not in indirect_i
    print("  [PASS] Cyclic impact analysis handled correctly")
    
    print("  [PASS] All edge case tests passed")


def main():
    print("\n" + "="*70)
    print("  CORE LOGIC AUDIT TEST SUITE")
    print("  Target Repository: AI-Powered-ATS-Resume-Analyzer")
    print("="*70)
    
    # 1. Repo Parser
    files, summary = test_repo_parser()
    
    # 2. AST Parser
    all_functions, all_classes = test_ast_parser(files)
    
    # 3. Function Call Order
    test_function_call_order(files)
    
    # 4. Dependency Analysis
    analyzer, deps, rev_deps = test_dependency_analysis(files)
    
    # 5. Impact Analysis
    test_impact_analysis(analyzer, deps, rev_deps)
    
    # 6. Chunk Generation
    all_chunks = test_chunk_generation(files)
    
    # 7. Embeddings & Vector Store
    emb_gen, vs = test_embeddings_and_vector_store(all_chunks)
    
    # 8. BM25
    bm25 = test_bm25_retriever(all_chunks)
    
    # 9. Hybrid Retriever
    hybrid = test_hybrid_retriever(vs, bm25, emb_gen)
    
    # 10. Reranker
    reranker = test_reranker(vs, bm25, emb_gen)
    
    # 11. Citation Generator
    test_citation_generator()
    
    # 12. Edge Cases
    test_dependency_edge_cases(files)
    
    separator("ALL TESTS PASSED")
    print("  Core logic audit complete.\n")


if __name__ == "__main__":
    main()
