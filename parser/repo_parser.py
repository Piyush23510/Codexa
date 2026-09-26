from pathlib import Path


class RepoParser:
    """
    Parses a repository and returns useful Python source files.
    """

    IGNORE_DIRS = {  # ignore useless files
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".idea",
        ".vscode",
        "dist",
        "build"
    }

    def __init__(self, repo_path: str):

        self.repo_path = Path(repo_path)

        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository not found: {repo_path}") # check if folder exist or not


    def should_ignore(self, path: Path) -> bool:
        """
        Returns True if the file/folder should be ignored.
        """

        return any(part in self.IGNORE_DIRS for part in path.parts) # path.parts se folder ka har part ajata hai fir ek ek bar har 
        #part ko check krte hai ki vo IGNORE_DIRS MAI TO NHI

    def get_python_files(self):
        """
        Returns all python files from repository.
        """

        python_files = []

        for file in self.repo_path.rglob("*.py"): # gives all .py file

            if self.should_ignore(file): # check if .py file is inside should_ignore folders sdo skip them
                continue

            python_files.append(file)

        return python_files

    def get_repo_summary(self):

        """
        Returns repository summary.
        """

        python_files = self.get_python_files() # get all python files

        folders = {
            file.parent
            for file in python_files # get folder count by removing duplicate folders
        }

        return {
            "project_name": self.repo_path.name,
            "total_python_files": len(python_files),
            "total_folders": len(folders),
        }

    def get_entry_points(self):
        """
        Returns possible entry-point functions.
        """
        python_files = self.get_python_files()
        entry_points = []

        for file_path in python_files:
        # AST parsing here
        # identify functions that are not called by other functions
            pass

        return entry_points
