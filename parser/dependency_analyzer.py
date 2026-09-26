import ast


class DependencyAnalyzer:

    def __init__(self, files):
        self.files = files

    def get_function_dependencies(self):
        dependencies = {}
        function_names = set()

        # First collect all function names from the entire repository
        for file_path in self.files:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    code = file.read()

                tree = ast.parse(code)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        function_name = node.name
                        function_names.add(function_name)
            except Exception as e:
                print(f"[DependencyAnalyzer] Warning: Failed reading/parsing AST for function collection in '{file_path}': {e}")
                continue

        # Now find function calls in the entire repository
        for file_path in self.files:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    code = file.read()

                tree = ast.parse(code)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        function_name = node.name
                        if function_name not in dependencies:
                            dependencies[function_name] = []

                        for child in ast.walk(node):
                            if isinstance(child, ast.Call):
                                called_function = None
                                if isinstance(child.func, ast.Name):
                                    called_function = child.func.id
                                elif isinstance(child.func, ast.Attribute):
                                    called_function = child.func.attr

                                if called_function and called_function in function_names:
                                    if called_function not in dependencies[function_name]:
                                        dependencies[function_name].append(
                                            called_function
                                        )
            except Exception as e:
                print(f"[DependencyAnalyzer] Warning: Failed reading/parsing AST for dependency extraction in '{file_path}': {e}")
                continue

        reverse_dependencies = {}

        for function_name, called_functions in dependencies.items():
            for called_function in called_functions:
                if called_function not in reverse_dependencies:
                    reverse_dependencies[called_function] = []

                reverse_dependencies[called_function].append(
                    function_name
                )

        return dependencies, reverse_dependencies

    def get_indirect_dependencies(
        self,
        function_name,
        dependencies,
        visited=None,
        is_root=True
    ):
        if visited is None:
            visited = set()

        indirect = set()

        for called_function in dependencies.get(function_name, []):

            # CHANGED: Avoid cycles and repeated traversal
            if called_function in visited:
                continue

            visited.add(called_function)

            result = self.get_indirect_dependencies(
                called_function,
                dependencies,
                visited,
                False
            )

            indirect.update(result)

            if not is_root:
                indirect.add(called_function)

        return indirect

    def get_impact_analysis(
        self,
        changed_function,
        reverse_dependencies,
    ):
        direct_impact = set()
        indirect_impact = set()

        # CHANGED: Mark the changed function as visited from the beginning.
        # This prevents circular dependencies from coming back to the root.
        visited = {changed_function}

        def find_impact(
            function,
            is_direct=True
        ):
            for caller in reverse_dependencies.get(function, []):

                # CHANGED: Prevent duplicate traversal and circular dependencies
                if caller in visited:
                    continue

                visited.add(caller)

                if is_direct:
                    direct_impact.add(caller)
                else:
                    indirect_impact.add(caller)

                # CHANGED: Continue recursively to find
                # functions indirectly affected by the changed function
                find_impact(
                    caller,
                    is_direct=False
                )

        # Start impact analysis from changed function
        find_impact(changed_function)

        # CHANGED: Make absolutely sure that a direct dependency
        # is not also reported as an indirect dependency.
        indirect_impact -= direct_impact

        # CHANGED: Make sure the changed function itself
        # is never reported as impacted.
        direct_impact.discard(changed_function)
        indirect_impact.discard(changed_function)

        return direct_impact, indirect_impact

    def calculate_risk(
        self,
        direct_impact,
        indirect_impact
    ):
        total_impact = (
            len(direct_impact) +
            len(indirect_impact)
        )

        if total_impact == 0:
            return "LOW"

        elif total_impact <= 2:
            return "MEDIUM"

        else:
            return "HIGH"

    def impact_percentage(
        self,
        direct_impact,
        indirect_impact,
        total_functions
    ):
        total_impact = (
            len(direct_impact) +
            len(indirect_impact)
        )

        if total_functions == 0:
            return 0.0

        return (
            total_impact /
            total_functions
        ) * 100

    def get_function_details(self, function_name):

        for file_path in self.files:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    code = file.read()

                tree = ast.parse(code)

                for node in ast.walk(tree):

                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

                        if node.name == function_name:

                            # Extract function arguments
                            arguments = []

                            for arg in node.args.args:
                                if arg.arg == "self":
                                    continue
                                arguments.append(arg.arg)

                            # Extract the complete function source code
                            function_code = ast.get_source_segment(
                                code,
                                node
                            )

                            return {
                                "name": node.name,
                                "file": str(file_path),
                                "start_line": node.lineno,
                                "end_line": node.end_lineno,
                                "arguments": arguments,
                                "code": function_code
                            }
            except Exception as e:
                print(f"[DependencyAnalyzer] Warning: Failed reading/parsing AST for function details in '{file_path}': {e}")
                continue

        return None

    def get_repository_workflow(
    self,
    dependencies,
    reverse_dependencies
):
     """
     Returns the main workflow of the repository.
     """

    # Find functions that are not called by any other function
     entry_points = []

     for function_name in dependencies:
        if function_name not in reverse_dependencies:
            entry_points.append(function_name)

    # Calculate how many functions are reachable from each entry point
     def get_reachable_functions(function_name, visited=None):
        if visited is None:
            visited = set()

        for called_function in dependencies.get(function_name, []):
            if called_function not in visited:
                visited.add(called_function)
                get_reachable_functions(
                    called_function,
                    visited
                )

        return visited

    # Find the entry point with the largest reachable workflow
     main_entry_point = None
     largest_workflow = set()

     for entry_point in entry_points:
        reachable_functions = get_reachable_functions(
            entry_point
        )

        if len(reachable_functions) > len(largest_workflow):
            largest_workflow = reachable_functions
            main_entry_point = entry_point

     return {
        "main_entry_point": main_entry_point,
        "workflow": list(largest_workflow)
     }