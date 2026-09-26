"""
Interactive CLI Testing Script for AI Software Engineering Copilot.
Runs queries against the existing CopilotEngine without starting the Flask web server.

Usage:
    python test_queries.py                     (Interactive Mode)
    python test_queries.py "<your query>"      (Single Query Mode)
"""

import sys
import os
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

# Ensure root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import existing CopilotEngine loader from app.py
from app import get_engine


SAMPLE_QUERIES = """
======================================================================
                     SAMPLE TEST QUERIES
======================================================================

[Repository Queries]
  • How many functions are there?
  • How many Python files are present?
  • Show me the repository structure.
  • Give me an overview of this project.
  • Explain the main workflow of this project.

[Dependency Queries]
  • Which functions does analyze call?
  • Who calls clean_text?
  • What functions are indirectly dependent on analyze?
  • What is the sequence of calls inside analyze?
  • Show me the dependency graph.

[Impact Analysis Queries]
  • What would be affected if clean_text changes?
  • What is the impact of changing analyze?

[RAG Queries]
  • What does clean_text do?
  • Explain how analyze calculates the resume score.
  • Where is calculate_similarity defined?

[Edge Case Queries]
  • What does xyz_function do?
  • Who calls a function that has no callers?
  • (Press Enter with empty query to test empty handling)
======================================================================
Type 'exit' or 'quit' to end the session.
Type 'help' or 'samples' to re-display sample queries.
"""


def format_and_display_result(query: str, result: dict):
    """
    Format and display the query execution results clearly in the terminal.
    """
    print("\n" + "=" * 70)
    print(f"  QUERY: {query}")
    print("=" * 70)
    print(f"  Query Type : {result.get('query_type', 'N/A')}")
    print(f"  Sub Type   : {result.get('sub_type', 'N/A')}")
    
    if "risk" in result:
        print(f"  Risk Level : {result.get('risk')}")
    if "impact_percentage" in result:
        print(f"  Impact %   : {result.get('impact_percentage'):.2f}%")
    if result.get("graph_url"):
        print(f"  Graph URL  : {result.get('graph_url')}")
        
    print("-" * 70)
    print("ANSWER:")
    print(result.get("answer", "No answer generated."))
    
    citations = result.get("citations", [])
    if citations:
        print("\nCITATIONS:")
        for idx, cit in enumerate(citations, 1):
            name_str = f" `{cit['name']}`" if cit.get('name') else ""
            lines_str = f" (lines {cit['start_line']}-{cit['end_line']})" if cit.get('start_line') else ""
            print(f"  [{idx}] File: {cit.get('file')}{name_str}{lines_str} [{cit.get('type')}]")
            
    print("=" * 70 + "\n")


def run_interactive_loop(engine):
    """
    Runs an interactive loop in the terminal for testing queries.
    """
    print(SAMPLE_QUERIES)
    
    while True:
        try:
            user_input = input("Copilot > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Copilot terminal testing. Goodbye!")
            break
            
        if not user_input:
            print("[Info] Empty query entered. Please type a query or 'exit' to quit.\n")
            continue
            
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting Copilot terminal testing. Goodbye!")
            break
            
        if user_input.lower() in ["help", "samples"]:
            print(SAMPLE_QUERIES)
            continue
            
        try:
            result = engine.process_query(user_input)
            format_and_display_result(user_input, result)
        except Exception as e:
            print(f"\n[Error] Exception occurred while processing query: {e}")
            import traceback
            traceback.print_exc()
            print()


def main():
    print("======================================================================")
    print("  AI SOFTWARE ENGINEERING COPILOT - STANDALONE TERMINAL TESTER")
    print("======================================================================")
    print("Initializing CopilotEngine...")
    
    try:
        engine = get_engine()
        print(f"CopilotEngine successfully loaded repository: {engine.summary['project_name']}\n")
    except Exception as e:
        print(f"[Fatal Error] Failed to initialize CopilotEngine: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Check if a query was passed directly as command line argument
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:]).strip()
        print(f"Processing command-line query: '{query}'")
        try:
            result = engine.process_query(query)
            format_and_display_result(query, result)
        except Exception as e:
            print(f"[Error] Failed to process query: {e}")
            import traceback
            traceback.print_exc()
    else:
        run_interactive_loop(engine)


if __name__ == "__main__":
    main()
