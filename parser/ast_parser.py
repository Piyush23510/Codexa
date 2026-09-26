import ast

from pathlib import Path


class ASTParser:

    def __init__(self, file_path):  # jab object banaoge to ye automatic run hoga parser = ASTParser('sample.py') to ye run hoga

        self.file_path = Path(file_path)  # ab file_path = 'sample.py' ab path object bn jayega

        with open(self.file_path, "r", encoding="utf-8") as file:

            self.source_code = file.read()  # puri file ek string bn jayegi

        self.source_lines = self.source_code.splitlines()  # string ko line wise split krke list mai dal diya(source_line ek list hai jisme har line ek element hai)

        self.tree = ast.parse(self.source_code)  # generates AST tree


    def get_source_code(self, node):

        start = node.lineno - 1

        end = node.end_lineno

        return "\n".join(self.source_lines[start:end])


    def get_imports(self):

        imports = []

        for node in ast.walk(self.tree):  # har node pe jayega tree ke (travetrse recursively)

            if isinstance(node, ast.Import):  # check if node is import or not

                for alias in node.names:

                    imports.append(alias.name)  # import ke andar jitne bhi modules hai unko append krdo imports list mai

            elif isinstance(node, ast.ImportFrom):  # ye iske liye from pathlib import Path(this is import from) check krta hai

                module = node.module if node.module else ""

                imports.append(module)

        return imports


    def get_functions(self):

        functions = []

        for node in ast.walk(self.tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

                arguments = []

                for arg in node.args.args:

                    if arg.arg == "self":

                        continue

                    arguments.append(arg.arg)

                if node.args.vararg:
                    arguments.append(f"*{node.args.vararg.arg}")

                for arg in node.args.kwonlyargs:
                    arguments.append(arg.arg)

                if node.args.kwarg:
                    arguments.append(f"**{node.args.kwarg.arg}")

                functions.append({

                    "name": node.name,

                    "arguments": arguments,

                    "start_line": node.lineno,

                    "end_line": node.end_lineno,

                    "code": self.get_source_code(node)

                })

        return functions



    def get_classes(self):

        classes = []

        for node in ast.walk(self.tree):

            if isinstance(node, ast.ClassDef):

                classes.append({

                    "name": node.name,

                    "start_line": node.lineno,

                    "end_line": node.end_lineno

                })

        return classes


    def get_function_call_order(self, function_name, known_functions=None):

        """
        Returns function calls inside a function in source-code order.
        """

        # Find the requested function in the AST
        target_function = None

        for node in ast.walk(self.tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

                if node.name == function_name:

                    target_function = node

                    break

        if target_function is None:

            return []

        # Collect function calls while avoiding nested function definitions
        class FunctionCallVisitor(ast.NodeVisitor):

            def __init__(self):

                self.calls = []

            def visit_FunctionDef(self, node):

                # Do not include calls inside nested function definitions
                return

            def visit_AsyncFunctionDef(self, node):

                # Do not include calls inside nested async functions
                return

            def visit_Lambda(self, node):

                # Do not include calls inside nested lambdas
                return

            def visit_Call(self, node):

                function_name_found = None

                # Example: clean_text(text)
                if isinstance(node.func, ast.Name):

                    function_name_found = node.func.id

                # Example: module.clean_text(text)
                elif isinstance(node.func, ast.Attribute):

                    function_name_found = node.func.attr

                if function_name_found is not None:

                    # Keep only known repository functions when provided
                    if (
                        known_functions is None
                        or function_name_found in known_functions
                    ):

                        self.calls.append(
                            (
                                node.lineno,
                                node.col_offset,
                                function_name_found
                            )
                        )

                # Continue traversing this call's arguments and children
                self.generic_visit(node)

        visitor = FunctionCallVisitor()

        # Visit the statements inside the target function
        for statement in target_function.body:

            visitor.visit(statement)

        # Sort calls by their source-code positions
        visitor.calls.sort(
            key=lambda item: (item[0], item[1])
        )

        return [
            function_name
            for _, _, function_name in visitor.calls
        ]