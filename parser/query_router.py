
class QueryRouter:

    def __init__(self, llm):
        self.llm = llm

    def route(self, query):
        q_lower = query.lower()
        if "dependency graph" in q_lower or "show graph" in q_lower or "visualize graph" in q_lower:
            return "DEPENDENCY"
        if "how many functions" in q_lower or "how many python files" in q_lower or "how many files" in q_lower or "how many folders" in q_lower:
            return "REPOSITORY"
        if "what python files" in q_lower or "repository structure" in q_lower or "folder structure" in q_lower:
            return "REPOSITORY"
        if "affected if" in q_lower or "what happens if" in q_lower or "if i change" in q_lower or "if i modify" in q_lower or "risk of changing" in q_lower:
            return "IMPACT"
        if "who calls" in q_lower or "functions does" in q_lower or "call sequence" in q_lower or "call order" in q_lower:
            return "DEPENDENCY"

        query_type = self.llm.classify_query(query)

        if query_type in ["REPOSITORY", "DEPENDENCY", "IMPACT", "RAG"]:
            return query_type
        return "RAG"

    def dependency_route(self, query):
        q_lower = query.lower()
        if "graph" in q_lower:
            return "GRAPH"
        if "who calls" in q_lower or "called by" in q_lower:
            return "REVERSE"
        if "indirect" in q_lower:
            return "INDIRECT"
        if "order" in q_lower or "sequence" in q_lower:
            return "ORDER"
        if "functions does" in q_lower or "calls" in q_lower:
            return "DIRECT"

        dependency_query_type = self.llm.classify_dependency_query(query)

        if dependency_query_type in ["GRAPH", "REVERSE", "INDIRECT", "DIRECT", "ORDER"]:
            return dependency_query_type
        return "RAG"

    def repository_route(self, query):
        q_lower = query.lower()
        if "how many" in q_lower or "count" in q_lower:
            return "COUNT"
        if "structure" in q_lower or "files" in q_lower or "folders" in q_lower:
            return "STRUCTURE"
        if "workflow" in q_lower or "execution flow" in q_lower:
            return "WORKFLOW"
        if "overview" in q_lower or "summary" in q_lower:
            return "OVERVIEW"

        repository_type = self.llm.classify_repository_query(query)

        if repository_type in ["COUNT", "STRUCTURE", "OVERVIEW", "WORKFLOW"]:
            return repository_type
        return "OVERVIEW"



