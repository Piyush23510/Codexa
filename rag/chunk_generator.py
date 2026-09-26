class ChunkGenerator:

    def __init__(self, file_path, ast_parser):
        self.file_path = file_path  # tells the path of the file for which we are generating chunks
        self.ast_parser = ast_parser # creaye structured code representation of the file using ASTParser

    def generate_chunks(self):

        chunks = []

        functions = self.ast_parser.get_functions() # calling get_functions method of ast_parser to get all functions in the file

        for function in functions:

            chunk = {
                "text": ( # this is given to the embedding model to generate embeddings for the function
                    f"File: {self.file_path}\n"
                    f"Type: function\n"
                    f"Name: {function['name']}\n"
                    f"Arguments: {', '.join(function['arguments'])}\n"
                    f"Lines: {function['start_line']}-{function['end_line']}\n\n"
                    f"Code:\n{function['code']}"
                ),

                "metadata": { # it is used for filtering and identifying the chunks in the vector database
                    "file": str(self.file_path),
                    "type": "function",
                    "name": function["name"],
                    "start_line": function["start_line"],
                    "end_line": function["end_line"]
                }
            }

            chunks.append(chunk)

        # Fallback for Python files with no function definitions (e.g. standalone scripts)
        if not chunks and hasattr(self.ast_parser, "source_code") and self.ast_parser.source_code.strip():
            chunks.append({
                "text": (
                    f"File: {self.file_path}\n"
                    f"Type: module\n"
                    f"Name: {self.file_path.name if hasattr(self.file_path, 'name') else str(self.file_path)}\n"
                    f"Lines: 1-{len(self.ast_parser.source_lines)}\n\n"
                    f"Code:\n{self.ast_parser.source_code}"
                ),
                "metadata": {
                    "file": str(self.file_path),
                    "type": "module",
                    "name": self.file_path.name if hasattr(self.file_path, 'name') else str(self.file_path),
                    "start_line": 1,
                    "end_line": len(self.ast_parser.source_lines)
                }
            })

        return chunks