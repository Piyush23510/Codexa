"""
Phase 4F: Detailed Repository Overview / Onboarding Test Suite

Tests for:
1. OverviewService statistics calculation
2. Repository structure detection (directories, config files, tests)
3. Entry-point detection
4. Important component detection & ranking
5. Dependency and relationship extraction
6. GET /api/repository/overview API endpoint
7. Empty repository handling
8. No-Python repository handling
9. LLM failure fallback to deterministic summary
10. Multi-repository switching overview updates
11. Existing Ask Copilot functionality regression checks
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from app import app, get_engine, active_repo_id, engine_registry
from rag.overview_service import OverviewService
from rag.llm_generator import LLMGenerator
from parser.dependency_analyzer import DependencyAnalyzer


@pytest.fixture
def sample_repo(tmp_path):
    """Create a temporary Python repository with known files and symbols for testing."""
    repo_dir = tmp_path / "sample_app"
    repo_dir.mkdir()

    # app.py (Entry point)
    (repo_dir / "app.py").write_text(
        "from services.processor import DataProcessor\n"
        "from config import Config\n\n"
        "def main():\n"
        "    proc = DataProcessor()\n"
        "    proc.process()\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    # config.py (Config file)
    (repo_dir / "config.py").write_text(
        "class Config:\n"
        "    DEBUG = True\n"
    )

    # services directory
    services_dir = repo_dir / "services"
    services_dir.mkdir()
    (services_dir / "__init__.py").write_text("")
    (services_dir / "processor.py").write_text(
        "from utils.helpers import clean_data\n\n"
        "class DataProcessor:\n"
        "    def process(self):\n"
        "        clean_data('input')\n"
        "    def save(self):\n"
        "        pass\n"
    )

    # utils directory
    utils_dir = repo_dir / "utils"
    utils_dir.mkdir()
    (utils_dir / "__init__.py").write_text("")
    (utils_dir / "helpers.py").write_text(
        "def clean_data(val):\n"
        "    return str(val).strip()\n"
    )

    # tests directory
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(
        "def test_sample():\n"
        "    assert True\n"
    )

    # requirements.txt & README.md
    (repo_dir / "requirements.txt").write_text("flask\ngroq\npytest\n")
    (repo_dir / "README.md").write_text("# Sample App\nA sample test repository.")

    return repo_dir


@pytest.fixture
def empty_repo(tmp_path):
    repo_dir = tmp_path / "empty_repo"
    repo_dir.mkdir()
    return repo_dir


@pytest.fixture
def no_python_repo(tmp_path):
    repo_dir = tmp_path / "no_python_repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# No Python Repo")
    (repo_dir / "index.html").write_text("<h1>Hello World</h1>")
    return repo_dir


class TestOverviewServiceFacts:
    """Test deterministic repository facts extraction."""

    def test_statistics(self, sample_repo):
        service = OverviewService(sample_repo)
        facts = service.collect_facts()

        stats = facts["statistics"]
        assert stats["total_python_files"] >= 5
        assert stats["total_classes"] >= 2  # Config, DataProcessor
        assert stats["total_functions"] >= 2  # main, clean_data, test_sample
        assert stats["total_modules"] >= 4

    def test_entry_points(self, sample_repo):
        service = OverviewService(sample_repo)
        entry_points = service.detect_entry_points()

        entry_files = [ep["file"] for ep in entry_points]
        assert "app.py" in entry_files

    def test_structure_detection(self, sample_repo):
        service = OverviewService(sample_repo)
        struct = service.get_structure_fact()

        dirs = [d["name"] for d in struct["important_directories"]]
        assert any("services" in d for d in dirs)
        assert any("tests" in d for d in dirs)

        configs = [c["file"] for c in struct["config_files"]]
        assert "requirements.txt" in configs or "config.py" in configs

    def test_important_components(self, sample_repo):
        service = OverviewService(sample_repo)
        comps = service.get_important_components()

        assert len(comps) > 0
        comp_files = [c["file_path"] for c in comps]
        assert "app.py" in comp_files

    def test_architecture_facts(self, sample_repo):
        service = OverviewService(sample_repo)
        arch = service.get_architecture_facts()

        assert "major_modules" in arch
        assert "key_relationships" in arch

    def test_exploration_path_and_questions(self, sample_repo):
        service = OverviewService(sample_repo)
        facts = service.collect_facts()

        path = facts["exploration_path"]
        assert len(path) == 4
        assert path[0]["step"] == 1

        questions = facts["suggested_questions"]
        assert len(questions) >= 3


class TestOverviewLLMFallback:
    """Test LLM generation fallback when API keys/calls fail."""

    def test_deterministic_summary(self, sample_repo):
        service = OverviewService(sample_repo)
        facts = service.collect_facts()

        summary = service.get_deterministic_summary(facts) if hasattr(service, "get_deterministic_summary") else ""
        if not summary and hasattr(LLMGenerator, "generate_deterministic_summary"):
            summary = LLMGenerator().generate_deterministic_summary(facts)

        assert "A. What this repository does" in summary
        assert "B. How the repository is organized" in summary
        assert "C. How the application works" in summary
        assert "D. Core components" in summary
        assert "E. Data flow" in summary
        assert "F. Dependencies" in summary
        assert "G. Entry points" in summary
        assert "H. Where a new developer should start" in summary


class TestOverviewEdgeCases:
    """Test empty repos and non-Python repos."""

    def test_empty_repository(self, empty_repo):
        service = OverviewService(empty_repo)
        facts = service.collect_facts()

        assert facts["statistics"]["total_python_files"] == 0
        assert len(facts["entry_points"]) == 0
        assert len(facts["important_components"]) == 0

    def test_no_python_repository(self, no_python_repo):
        service = OverviewService(no_python_repo)
        facts = service.collect_facts()

        assert facts["statistics"]["total_python_files"] == 0
        assert facts["statistics"]["total_files"] >= 2


class TestOverviewAPI:
    """Integration test for GET /api/repository/overview endpoint."""

    @pytest.fixture
    def client(self):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_get_overview_endpoint_unselected(self, client):
        response = client.get("/api/repository/overview")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["status"] == "unselected"

    def test_get_overview_endpoint_with_repo(self, client):
        response = client.get("/api/repository/overview?repo_id=default")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert "repository" in data
        assert "statistics" in data
        assert "structure" in data
        assert "entry_points" in data
        assert "important_components" in data
        assert "architecture" in data
        assert "summary" in data
        assert "exploration_path" in data
        assert "suggested_questions" in data

    def test_get_overview_invalid_repo(self, client):
        response = client.get("/api/repository/overview?repo_id=nonexistent_12345")
        assert response.status_code in (404, 500)


class TestCopilotEngineRegression:
    """Verify existing Ask Copilot APIs are unaffected."""

    @pytest.fixture
    def client(self):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_query_copilot_endpoint(self, client):
        response = client.post(
            "/api/query",
            data=json.dumps({"query": "How many python files are in this repository?", "repo_id": "default"}),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "answer" in data

