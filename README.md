# Codexa
AI Software Intelligence Copilot
An enterprise-grade, local-first AI developer platform designed for multi-repository codebase understanding, AST-based dependency analysis, change impact scoring, and grounded RAG technical Q&A with line-level code citations.

TABLE OF CONTENTS
Project Overview

Core Features & Architecture

Technical Stack

Dual-Mode Workspace System

RAG Pipeline & Retrieval System

Repository Directory Structure

API Reference

Setup & Installation Guide

Verification & Testing

License

PROJECT OVERVIEW

AI Software Intelligence Copilot enables software engineers, code reviewers, and system architects to instantly analyze, navigate, and query complex software codebases. By unifying Abstract Syntax Tree (AST) static analysis with dense-sparse hybrid retrieval (FAISS + BM25) and Groq-powered Large Language Models, the Copilot provides precise answers, architectural call graphs, and predictive change impact risk scores.

CORE FEATURES & ARCHITECTURE
• Dual-Mode Workspace Workflow:

Standalone Dedicated Views: Focused full-canvas dashboards for Overview, Dependencies, Impact Analysis, PyVis Network Graphs, and Query History Stream.
Contextual Embedded Views in "Ask Copilot": Inline mini-graph visualization cards, side-by-side split-pane drawer (#sideCanvasDrawer), and one-click "Open in Dedicated Tab" deep linking.
• Multi-Repository Management:

Instant ZIP archive upload (/api/upload_repo).
Dynamic AST extraction and indexing across multiple repositories.
Hot-switching between loaded repositories (/api/switch_repo) without server restarts.
• AST Static Analysis & Dependency Engine:

Deep Python AST parsing extracting modules, classes, functions, and import statements.
Direct callers, reverse callers (called_by), and indirect dependency path resolution.
PyVis interactive HTML call graph & impact graph generation with physics controls, node filtering, and search.
• Change Impact & Risk Calculator:

Quantifies function change risk scores (LOW, MEDIUM, HIGH, CRITICAL).
Calculates downstream ripple effect percentages and affected functions list before committing code.
• Grounded Hybrid RAG Pipeline:

Dual FAISS vector search + Rank-BM25 sparse keyword search.
Reciprocal Rank Fusion (RRF) and CrossEncoder reranking for maximum precision.
Groq LLM inference with automated model fallback and exponential backoff retry.
Exact file and line-number code citations (e.g. utils/text_preprocessing.py → clean_text | Lines 7-41).
• Modern Developer UI (Linear x Cursor Aesthetics):

Premium dark theme design system with micro-animations.
Interactive canvas overlays with sleek dark loading skeletons and centered empty state cards.
Highlight.js code syntax highlighting, Marked.js markdown rendering, copyable citations, toast notifications, and URL hash deep-linking (#overview, #ask, #dependencies, #impact, #graph, #history).
TECHNICAL STACK
• Backend: Python 3.11, Flask REST Framework, NetworkX, PyVis • AST Parser: Native Python ast module, DependencyAnalyzer • Vector Index & Embeddings: FAISS (Facebook AI Similarity Search), SentenceTransformers (all-MiniLM-L6-v2) • Keyword Search & Fusion: Rank-BM25, Reciprocal Rank Fusion (RRF), CrossEncoder Reranking • LLM Engine: Groq API (qwen/qwen3.8-27b, llama-3.3-70b-versatile) • Frontend: Vanilla JavaScript (ES6+), HTML5, CSS3 Custom Tokens, Highlight.js, Marked.js

DUAL-MODE WORKSPACE SYSTEM
Ask Copilot (Chat & Split-Pane Canvas):

Interactive Q&A chat stream with character validation (2000 chars limit).
Embedded mini-graph cards and risk pills.
Collapsible side-canvas drawer (#sideCanvasDrawer) for side-by-side graph inspection.
"Open in Dedicated Tab" CTA buttons.
Overview View (#overview):

Hero metric banners (total files, total functions, total folders, AST indexing status).
Interactive card grid to launch specific dashboards.
Dependencies View (#dependencies):

Direct callers, reverse callers, and indirect dependency tree inspector.
Impact Analysis View (#impact):

Function change risk calculator with impact ratio score and downstream affected callers list.
Standalone Graph View (#graph):

Full-canvas PyVis network graph workspace.
Interactive dropdown selector (Dependency Graph vs Impact Graph).
Canvas node search filter, refresh button, fullscreen modal trigger.
Centered empty state card with CTA button "Generate Dependency Graph" and dark loading skeleton.
History Stream View (#history):

Persistent session query log with repository tags, query types, and copyable citations.
RAG PIPELINE & RETRIEVAL SYSTEM

Chunking: Codes are parsed at function/class boundaries with metadata (start line, end line, docstrings, signatures).

Embeddings & Vector Index: Chunks are converted into 384-dim dense vectors using all-MiniLM-L6-v2 and stored in FAISS index.

BM25 Sparse Search: Tokens are indexed using BM25Okapi for exact symbol/variable matching.

RRF Fusion: FAISS dense scores and BM25 sparse scores are merged using Reciprocal Rank Fusion: RRF_Score = 1 / (60 + Rank_FAISS) + 1 / (60 + Rank_BM25)

Reranking: Top candidate chunks are reranked using CrossEncoder.

Prompt Generation & LLM Inference: Reranked context is sent to Groq LLM with system instructions enforcing strict groundedness and line-level citations.

REPOSITORY DIRECTORY STRUCTURE

AI-Software-Copilot/ │ ├── app.py # Flask REST server & API endpoints │ ├── parser/ # Codebase AST Parser & Graph Generators │ ├── ast_parser.py # Python AST abstract syntax tree parser │ ├── dependency_analyzer.py # Call graph & downstream impact calculator │ ├── dependency_graph.py # PyVis HTML graph visualization builder │ └── query_router.py # Intent classifier (REPOSITORY, AST, IMPACT, DEPENDENCY) │ ├── rag/ # Retrieval Augmented Generation Engine │ ├── chunk_generator.py # Code chunking by function/class boundary │ ├── embeddings_generator.py # SentenceTransformer embedding generator │ ├── vector_store.py # FAISS vector store index & query engine │ ├── bm25_retriever.py # BM25 sparse keyword retriever │ ├── rrf_fusion.py # Reciprocal Rank Fusion implementation │ ├── hybrid_retriever.py # Hybrid FAISS + BM25 + CrossEncoder pipeline │ ├── llm_generator.py # Groq API client with fallback models & retries │ └── citation_generator.py # Citation builder with exact line numbers │ ├── templates/ │ └── index.html # Dual-mode Single Page Application (SPA) layout │ ├── static/ │ ├── style.css # Design system, CSS variables & responsive layout │ └── script.js # Dual-mode view switcher, hash router & API bindings │ ├── tests/ # Automated Test Suites │ ├── test_core_logic.py # Core parser & RAG verification │ ├── test_phase2_api.py # Flask API endpoints test │ ├── test_phase3_ui.py # Web UI & asset verification test │ └── test_multi_repository.py# Multi-repo switching test │ ├── requirements.txt # Python package dependencies └── .env # Environment configuration file

API REFERENCE
• GET / Description: Serves the Dual-Mode Workspace web application.

• GET /api/status Description: Returns repository statistics, active repo ID, total files, folders, and functions.

• POST /api/query Payload: { "query": "string", "repo_id": "optional_string" } Description: Processes developer questions, returns Markdown answer, citations, risk score, and graph URL.

• POST /api/upload_repo Payload: multipart/form-data with file (.zip) Description: Extracts, indexes, and activates uploaded repository archive.

• POST /api/switch_repo Payload: { "repo_id": "string" } Description: Switches active engine context to target repository ID.

• GET /api/graph/<graph_name> Description: Serves PyVis HTML visualization file (call_graph.html or impact_graph.html).

SETUP & INSTALLATION GUIDE
Prerequisites:

Python 3.10 or 3.11
Groq API Key
Step 1: Clone Repository git clone https://github.com/your-username/AI-Software-Copilot.git cd AI-Software-Copilot

Step 2: Create & Activate Virtual Environment python -m venv venv venv\Scripts\activate # Windows source venv/bin/activate # macOS/Linux

Step 3: Install Dependencies pip install -r requirements.txt

Step 4: Configure Environment Variables Create a .env file in the project root: GROQ_API_KEY=your_groq_api_key_here GROQ_MODEL=qwen/qwen3.8-27b PORT=5000

Step 5: Run Application python app.py

Access the application in your browser at: http://localhost:5000

VERIFICATION & TESTING
Run automated test suites:

Run UI & frontend asset tests:
python tests/test_phase3_ui.py

Run Flask REST API tests:
python tests/test_phase2_api.py

Run Core logic & parser tests:
python tests/test_core_logic.py

Run Multi-repository tests:
python tests/test_multi_repository.py
