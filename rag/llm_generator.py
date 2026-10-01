
import os
import re

from dotenv import load_dotenv

from groq import Groq


load_dotenv()


class LLMGenerator:

    def __init__(self):

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY not found")

        self.client = Groq(
            api_key=api_key
        )
        self.model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    def _completion_with_retry(self, max_retries=5, initial_delay=3, **kwargs):
        if "model" not in kwargs:
            kwargs["model"] = self.model
        import time
        import groq
        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except groq.RateLimitError as e:
                if attempt == max_retries - 1:
                    raise e
                wait_time = initial_delay * (attempt + 1)
                print(f"[LLMGenerator] Groq rate limit hit (attempt {attempt+1}/{max_retries}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            except (groq.NotFoundError, groq.AuthenticationError, groq.BadRequestError, groq.UnprocessableEntityError, groq.PermissionDeniedError) as fatal_err:
                print(f"[LLMGenerator] Fatal Groq API Error ({type(fatal_err).__name__}): {fatal_err}")
                raise fatal_err
            except groq.APIStatusError as status_err:
                if status_err.status_code in [400, 401, 403, 404, 422]:
                    print(f"[LLMGenerator] Fatal Groq Status Error ({status_err.status_code}): {status_err}")
                    raise status_err
                if attempt == max_retries - 1:
                    raise status_err
                print(f"[LLMGenerator] Groq status error ({status_err.status_code}). Retrying...")
                time.sleep(initial_delay)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"[LLMGenerator] Unexpected LLM error ({type(e).__name__}): {e}. Retrying...")
                time.sleep(initial_delay)



    def _resolve_bare_symbol(self, token, functions):
        if not token:
            return None
        clean_token = token.strip("()").strip().lower()
        if not clean_token:
            return None
        # Exact match
        for fn in functions:
            if fn.lower() == clean_token:
                return fn
        # Leaf name match (e.g. module::parse -> parse)
        matches = [fn for fn in functions if fn.split("::")[-1].lower() == clean_token]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            return f"AMBIGUOUS:{clean_token}"
        return None

    # Identify the function explicitly mentioned as being changed

    def identify_changed_function( # used for impact analysis
        self,
        query,
        function_names
    ):
        query_lower = query.lower()
        impact_kws = ["change", "changing", "modify", "modifying", "update", "updating", "refactor", "refactoring", "delete", "deleting", "replace", "replacing", "break", "breaking", "affect", "affecting", "impact", "impacting", "risk"]
        has_impact = any(kw in query_lower for kw in impact_kws)

        if has_impact:
            for fname in sorted(function_names, key=len, reverse=True):
                clean = fname.split("::")[-1]
                pattern = r'\b' + re.escape(clean.lower()) + r'\b'
                if re.search(pattern, query_lower):
                    resolved = self._resolve_bare_symbol(clean, function_names)
                    if resolved:
                        return resolved

        prompt = f"""

You are an AI Software Engineering Copilot.

Repository function names:

{function_names}

User question:

{query}

Your task is ONLY to determine whether the user is explicitly asking
about CHANGING a specific function.

Return the exact function name ONLY if the user explicitly talks about:

- changing a function
- modifying a function
- updating a function
- refactoring a function
- deleting a function
- replacing a function
- breaking a function
- what happens if a function is changed

Examples:

"What happens if I change clean_text?"
-> clean_text

"If I modify analyze, what will be affected?"
-> analyze

"What happens if analyze is deleted?"
-> analyze

"Which functions are affected if I change home?"
-> home

For questions such as:

"Where are embeddings generated?"
"What does analyze do?"
"Where is clean_text defined?"
"Which function generates the vector store?"
"How does the chatbot work?"
"Which function calls analyze?"

DO NOT identify a changed function.

For those questions, return:

NONE

IMPORTANT RULES:

1. Do NOT infer a changed function from the topic of the question.

2. Do NOT assume that the function being discussed is being changed.

3. The user must explicitly indicate a change/modification/update/deletion
   or similar action.

4. Return ONLY an exact function name from the provided function list.

5. If there is no explicit change request, return ONLY:

NONE

Do not explain your answer.

"""

        response = self._completion_with_retry(

            model=self.model,
            max_tokens=50,

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You identify explicitly changed functions "
                        "from software engineering questions."
                    )
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ]
        )

        raw_text = (
            response.choices[0]
            .message
            .content
            .strip()
        )

        if raw_text == "NONE":
            return None

        if raw_text in function_names:
            return raw_text

        resolved = self._resolve_bare_symbol(raw_text, function_names)
        if resolved:
            return resolved

        for fname in sorted(function_names, key=len, reverse=True):
            if re.search(r'\b' + re.escape(fname) + r'\b', raw_text):
                return fname

        return None


    # Generate AI recommendation based on impact analysis

    def generate_recommendation(
        self,
        changed_function,
        direct_impact,
        indirect_impact,
        impact_percentage,
        risk
    ):

        prompt = f"""

You are an AI Software Engineering Copilot.

Generate a practical recommendation for changing a function
in a software repository.

Use ONLY the provided impact analysis information.

Changed Function:
{changed_function}

Directly Affected Functions:
{list(direct_impact)}

Indirectly Affected Functions:
{list(indirect_impact)}

Impact Percentage:
{impact_percentage:.2f}%

Risk Level:
{risk}

Instructions:

1. Consider the changed function.
2. Consider all directly affected functions.
3. Consider all indirectly affected functions.
4. Consider the impact percentage.
5. Consider the risk level.
6. Give a practical software engineering recommendation.
7. Explain what should be reviewed or tested before and after the change.
8. If the risk is HIGH, recommend more thorough testing and review.
9. If the risk is MEDIUM, recommend reviewing and testing affected functions.
10. If the risk is LOW, recommend basic testing of the changed function.
11. Do not invent functions or dependencies.
12. Do not claim that a function is affected unless it is provided above.
13. Keep the recommendation concise.
14. Return ONLY the recommendation. Do not add a heading.

"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=300,
            messages=[

                {
                    "role": "system",
                    "content": (
                        "You generate software engineering "
                        "recommendations based only on "
                        "provided impact analysis."
                    )
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ]
        )

        return (
            response.choices[0]
            .message
            .content
            .strip()
        )


    # Generate the final answer for the user

    def generate_answer(
        self,
        question,
        context
    ):

        prompt = f"""

You are an AI Software Engineering Copilot.

Answer the user's question using only the provided code context and
dependency/impact analysis information.

For function-related questions, always mention when available:

1. Function name
2. File name
3. Start and end line
4. Arguments
5. A short explanation of what the function does

For dependency-related questions:

- Direct dependency means a function directly calls another function.
- Reverse dependency means which functions call the given function.
- Indirect dependency means a function is reached through one or more
  intermediate function calls.

For impact-analysis questions:

- Identify the function the user wants to change.
- Explain which functions are directly affected.
- Explain which functions are indirectly affected.
- Direct impact means the functions that directly call the changed function.
- Indirect impact means the functions that call the changed function
  through one or more intermediate functions.
- Do not invent dependencies or affected functions.
- Use the provided dependency and impact-analysis results only.

For impact-analysis recommendations:

If impact analysis information is provided in the context:

- Mention the changed function.
- Mention direct and indirect impact.
- Mention impact percentage.
- Mention risk.
- Include the provided AI recommendation.
- Do not create a different recommendation.
- Do not invent affected functions.

For recommendations:
- The recommendation is already provided separately in the context.
- Do NOT generate, repeat, rewrite, or summarize the recommendation.
- Do NOT include a "Recommendation" section in your answer.

If dependency, impact-analysis, risk, impact percentage,
or recommendation information is provided in the context,
use it in the answer.

Strict Grounding Rules:
- Answer ONLY using the code and dependency context provided below.
- Do NOT invent, assume, or fabricate functions, files, classes, line numbers, variable names, or citations that do not exist in the provided context.
- If the provided context is insufficient to answer the question, state: "The provided repository context does not contain enough information to answer this question."

Code and Dependency Context:

{context}

User Question:

{question}

Give a concise and technically accurate answer.

"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=500,
            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are an AI Software Engineering Copilot."
                    )
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ]
        )

        return response.choices[0].message.content


    
    def classify_query(self, query):  # query type
        query_lower = query.lower()
        if "how does" in query_lower and "work" in query_lower:
            if not any(k in query_lower for k in ["project", "repository", "app", "codebase", "system", "workflow"]):
                return "RAG"

        prompt = f"""

You are an AI Software Engineering Copilot.

Classify the user's question into exactly ONE of these categories:

1. REPOSITORY

Questions about the repository as a whole, such as:

- all functions in the repository
- all files in the repository
- how many functions are present
- how many Python files are present
- repository structure
- project overview
- main workflow of the project
- project workflow or execution flow


2. DEPENDENCY

Questions about function relationships, such as:

- which functions call a function
- which functions are called by a function
- direct dependencies
- reverse dependencies
- indirect dependencies
- function call order
- sequence of function calls
- order in which functions are called

Examples:

- "Which functions does analyze call?"
- "Who calls clean_text?"
- "What functions are indirectly dependent on analyze?"
- "What is the sequence of calls inside analyze?"
- "What is the order in which analyze calls its functions?"
- "How does analyze execute its function calls?"


3. IMPACT

Questions about changing a function, such as:

- what happens if I change a function
- what happens if I modify a function
- what will be affected if a function is deleted
- impact of changing a function
- risk of changing a function


4. RAG

General questions about the code, such as:

- what does a function do
- where is something implemented
- where are embeddings generated
- how does a particular function work
- explain a piece of code

User Question:

{query}

Rules:

- Return ONLY one category.
- Questions about function calls, dependencies, reverse dependencies,
  indirect dependencies, call sequence, or call order MUST be classified
  as DEPENDENCY.
- Return exactly one of:

  REPOSITORY
  DEPENDENCY
  IMPACT
  RAG

- Do not explain your answer.

"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=150,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify software engineering "
                        "questions into predefined categories."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        raw_text = response.choices[0].message.content or ""
        match = re.search(r'\b(REPOSITORY|DEPENDENCY|IMPACT|RAG)\b', raw_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "RAG"


   
    def classify_dependency_query(self, query):

        prompt = f"""

You are an AI Software Engineering Copilot.

Classify the dependency query into exactly ONE
of the following types:

DIRECT

REVERSE

INDIRECT

ORDER

GRAPH


Definitions:


DIRECT:

The user wants to know which functions are
called by a function.

Example:

"Which functions does analyze call?"


REVERSE:

The user wants to know which functions call
a particular function.

Example:

"Who calls clean_text?"


INDIRECT:

The user wants to know indirect or transitive
dependencies of a function.

Example:

"What functions are indirectly dependent on analyze?"


ORDER:

The user wants to know the source-code order
or sequence in which function calls appear
inside a function.

Examples:

"What is the order in which analyze calls its functions?"

"How does analyze execute its calls?"

"What is the sequence of function calls inside analyze?"

"Show me the order in which analyze calls its functions."


GRAPH:

The user wants to see the complete dependency
graph of the repository.

Examples:

"Show the complete dependency graph of the repository"

"Visualize the dependency graph"

"Show the dependency graph"

"Display all function dependencies as a graph"


Important:

If the user asks about the sequence, order,
or source-code order of function calls inside
a particular function, classify it as ORDER.

If the user asks to SHOW, DISPLAY, or VISUALIZE
the COMPLETE dependency graph of the repository,
classify it as GRAPH.


User Query:

{query}


Return ONLY one of:

DIRECT

REVERSE

INDIRECT

ORDER

GRAPH

"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=150,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify dependency queries into "
                        "DIRECT, REVERSE, INDIRECT, ORDER, or GRAPH."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        raw_text = response.choices[0].message.content or ""
        match = re.search(r'\b(DIRECT|REVERSE|INDIRECT|ORDER|GRAPH)\b', raw_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "RAG"




    def identify_dependency_function(self, query, functions): # Dependency query mein requested function identify karne ke liye
        query_lower = query.lower()
        for fname in sorted(functions, key=len, reverse=True):
            clean = fname.split("::")[-1]
            pattern = r'\b' + re.escape(clean.lower()) + r'\b'
            if re.search(pattern, query_lower):
                resolved = self._resolve_bare_symbol(clean, functions)
                if resolved:
                    return resolved

        prompt = f"""
Identify the function name mentioned in the user's dependency query.

Available functions:
{functions}

User query:
{query}

Return ONLY the exact function name from the available functions.
If no function is mentioned, return NONE.
"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=50,
            messages=[
                {
                    "role": "system",
                    "content": "You identify function names from software dependency queries."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = response.choices[0].message.content.strip()

        if result == "NONE":
            return None

        if result in functions:
            return result

        resolved = self._resolve_bare_symbol(result, functions)
        if resolved:
            return resolved

        for fname in sorted(functions, key=len, reverse=True):
            if re.search(r'\b' + re.escape(fname) + r'\b', result):
                return fname

        return None

    def explain_repository_workflow(self, repository_data):

        prompt = f"""
You are an AI Software Engineering Copilot analyzing a software repository.

Repository Information:

{repository_data}

Explain the main workflow of this repository.

Strict Rules:

1. Use ONLY the information provided above.
2. Do NOT infer a function's purpose from its name.
3. Use the provided function metadata to explain functions.
4. Preserve function names exactly.
5. Preserve file names and line numbers exactly.
6. Do NOT invent implementation details.
7. Do NOT assume execution order unless explicitly provided.
8. Do NOT add functions that are not present.
9. If function metadata is unavailable, say:
   "Function details not available from the repository analysis."
10. Clearly identify the main entry point.
11. Explain the relationship between the main entry point
    and its direct dependencies.
12. Keep the explanation concise and technically accurate.
13. Do NOT describe the dependencies as a sequence unless their
  execution order is explicitly provided.
14. Say that the entry point directly calls the listed functions.

Return ONLY the repository workflow explanation.
"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=400,
            messages=[
            {
                "role": "system",
                "content": (
                    "You explain repository workflows strictly "
                    "from provided structural analysis."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

        return (
        response.choices[0]
        .message
        .content
        .strip()
    )

    
    def classify_repository_query(self, query):

        prompt = f"""

You are an AI Software Engineering Copilot.

Classify the repository query into exactly ONE
of the following types:

COUNT

STRUCTURE

OVERVIEW

WORKFLOW


Definitions:


COUNT:

The user wants numerical information about
the repository.

Examples:

"How many functions are there?"

"How many Python files are present?"

"How many folders are there?"

"How many functions does this project contain?"


STRUCTURE:

The user wants information about the files,
folders, or organization of the repository.

Examples:

"Show the repository structure"

"How is the project organized?"

"What files are in the repository?"

"Explain the folder structure"


OVERVIEW:

The user wants a general overview or summary
of the repository.

Examples:

"Give me an overview of the project"

"What is this project about?"

"Summarize the repository"

"What does this project contain?"


WORKFLOW:

The user wants to understand the main workflow
or execution flow of the repository.

Examples:

"Explain the main workflow"

"How does this project work?"

"Explain the project workflow"

"What is the main workflow of this project?"

"How does the repository work from start to finish?"


Important:

If the user asks for a number or count of
repository components, classify it as COUNT.

If the user asks about files, folders, or
organization, classify it as STRUCTURE.

If the user asks for a general summary or
overview, classify it as OVERVIEW.

If the user asks how the project works or
asks about its workflow, classify it as WORKFLOW.


User Query:

{query}


Return ONLY one of:

COUNT
STRUCTURE
OVERVIEW
WORKFLOW

"""

        response = self._completion_with_retry(
            model=self.model,
            max_tokens=150,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify repository queries into "
                        "COUNT, STRUCTURE, OVERVIEW, or WORKFLOW."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        raw_text = response.choices[0].message.content or ""
        match = re.search(r'\b(COUNT|STRUCTURE|OVERVIEW|WORKFLOW)\b', raw_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "OVERVIEW"

    def generate_deterministic_summary(self, overview_facts: dict) -> str:
        """
        Generate a structured, grounded Markdown overview summary deterministically
        from extracted repository facts without requiring an LLM API call.
        """
        repo_info = overview_facts.get("repository", {})
        stats = overview_facts.get("statistics", {})
        struct = overview_facts.get("structure", {})
        entry_points = overview_facts.get("entry_points", [])
        comps = overview_facts.get("important_components", [])
        arch = overview_facts.get("architecture", {})
        deps = overview_facts.get("dependencies", {})
        path = overview_facts.get("exploration_path", [])

        proj_name = repo_info.get("name", "Project")

        # A. What this repository does
        section_a = (
            f"### A. What this repository does\n"
            f"**{proj_name}** is a Python codebase comprising **{stats.get('total_files', 0)} total files** "
            f"({stats.get('total_python_files', 0)} Python modules), **{stats.get('total_classes', 0)} classes**, "
            f"and **{stats.get('total_functions', 0) + stats.get('total_methods', 0)} functions/methods**.\n"
        )
        if deps.get("external_dependencies"):
            ext_str = ", ".join([f"`{d}`" for d in deps["external_dependencies"][:8]])
            section_a += f"Key external technologies and libraries detected: {ext_str}.\n"

        # B. How the repository is organized
        dirs_str = ""
        for d in struct.get("important_directories", []):
            dirs_str += f"- `{d['name']}/`: {d['role']} ({d.get('python_files_count', 0)} files)\n"
        if not dirs_str:
            dirs_str = "The repository consists primarily of top-level Python modules.\n"

        section_b = (
            f"### B. How the repository is organized\n"
            f"The codebase separates concerns across key directories and modules:\n"
            f"{dirs_str}"
        )

        # C. How the application works
        ep_str = ", ".join([f"`{ep['file']}`" for ep in entry_points]) if entry_points else "None detected"
        section_c = (
            f"### C. How the application works\n"
            f"Execution begins at entry point(s): {ep_str}. Core processing flows from these entry points "
            f"into central business modules and services.\n"
        )

        # D. Core components
        comps_str = ""
        for c in comps[:5]:
            syms = ", ".join([f"`{s['name']}`" for s in c.get("important_symbols", [])[:3]])
            comps_str += f"- **`{c['file_path']}`** ({c['component_type']}): {c['description']}\n"
            if syms:
                comps_str += f"  - Key symbols: {syms}\n"
        section_d = (
            f"### D. Core components\n"
            f"The primary components in this repository include:\n"
            f"{comps_str}"
        )

        # E. Data flow
        section_e = (
            f"### E. Data flow\n"
            f"Inputs enter through entry points (`{entry_points[0]['file'] if entry_points else 'main'}`), "
            f"are processed by business services, and output results to API callers or standard interfaces.\n"
        )

        # F. Dependencies
        rel_str = ""
        for r in arch.get("key_relationships", [])[:6]:
            rel_str += f"- `{r['from_module']}` → `{r['to_module']}` ({r['type']})\n"
        if not rel_str:
            rel_str = "Internal module dependencies are minimal or localized.\n"
        section_f = (
            f"### F. Dependencies\n"
            f"**Internal Module Dependencies:**\n{rel_str}\n"
        )

        # G. Entry points
        g_str = ""
        for ep in entry_points:
            g_str += f"- **`{ep['file']}`**: {ep['description']}\n"
        if not g_str:
            g_str = "No explicit entry points (`if __name__ == '__main__':` or web server instances) were detected.\n"
        section_g = f"### G. Entry points\n{g_str}"

        # H. Where a new developer should start
        h_str = ""
        for step in path:
            h_str += f"{step['step']}. **`{step['target']}`** ({step['role']}): {step['reason']}\n"
        section_h = f"### H. Where a new developer should start\n{h_str}"

        return f"{section_a}\n{section_b}\n{section_c}\n{section_d}\n{section_e}\n{section_f}\n{section_g}\n{section_h}"

    def generate_repository_overview(self, overview_facts: dict) -> str:
        """
        Generate a detailed natural language repository overview using Groq LLM
        grounded in deterministic repository facts. Falls back to deterministic summary on failure.
        """
        import json
        facts_summary = json.dumps(overview_facts, indent=2)

        prompt = f"""
You are an expert AI Software Architect.
Analyze the following structured repository facts derived strictly from static analysis of the repository:

{facts_summary}

Generate a comprehensive, detailed, and clear repository overview summary for a developer onboarding to this project.

You MUST structure your response into the following exact Markdown headers:

### A. What this repository does
Explain what problem the project appears to solve, its main purpose, application type, technologies detected, and major capabilities.

### B. How the repository is organized
Explain the directory structure, important modules, separation of responsibilities, and where core logic lives.

### C. How the application works
Describe the high-level execution flow starting from entry points based strictly on available evidence.

### D. Core components
Explain the purpose and relationships of the most important components listed in facts.

### E. Data flow
Describe input -> processing -> output data flow if supported by evidence. If evidence is insufficient, state: "The repository structure does not provide enough evidence to determine this."

### F. Dependencies
Explain internal module relationships and key external library dependencies.

### G. Entry points
Explain where execution begins and why those files/functions appear to be entry points.

### H. Where a new developer should start
Explain the suggested exploration path through the repository step-by-step.

STRICT ANTI-HALLUCINATION RULES:
1. Ground every claim strictly in the provided repository facts.
2. Do NOT invent files, classes, functions, architectures, dependencies, or execution flows not present in facts.
3. If evidence is insufficient for any claim or section, explicitly state: "The repository structure does not provide enough evidence to determine this."
"""

        try:
            response = self._completion_with_retry(
                model=self.model,
                max_tokens=800,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a grounded AI Software Architecture expert. Rely only on facts."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
        except Exception as e:
            print(f"[LLMGenerator] Overview LLM generation failed ({type(e).__name__}): {e}. Using deterministic fallback.")

        return self.generate_deterministic_summary(overview_facts)

