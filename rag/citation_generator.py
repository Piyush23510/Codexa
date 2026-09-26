class CitationGenerator:

    def generate_citations(self, results):

        citations = []

        for result in results:

            metadata = result["metadata"]
            file_path = str(metadata.get("file", ""))

            # Convert backslashes to forward slashes
            clean_file = self.clean_path(file_path)

            citation = {
                "file": clean_file or file_path,
                "type": metadata.get("type", "code"),
                "name": metadata.get("name"),
                "start_line": metadata.get("start_line"),
                "end_line": metadata.get("end_line")
            }

            citations.append(citation)

        return citations

    @staticmethod
    def clean_path(raw_path):
        clean = str(raw_path).replace("\\", "/")
        if "uploaded_repositories/" in clean:
            tail = clean.split("uploaded_repositories/", 1)[1]
            parts = tail.split("/", 1)
            if len(parts) > 1:
                return parts[1]
            return parts[0]
        elif "AI-Powered-ATS-Resume-Analyzer/" in clean:
            parts = clean.split("AI-Powered-ATS-Resume-Analyzer/", 1)
            if len(parts) > 1:
                return parts[1]
        return clean
