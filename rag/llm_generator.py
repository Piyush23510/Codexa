
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



    # Identify the function explicitly mentioned as being changed

    def identify_changed_function( # used for impact analysis
        self,
        query,
        function_names
    ):
        query_lower = query.lower()
        # Fast deterministic check for known function names in change/impact queries
        for fname in sorted(function_names, key=len, reverse=True):
            if fname.lower() in query_lower and any(kw in query_lower for kw in ["change", "modify", "update", "refactor", "delete", "replace", "break", "affect", "impact"]):
                return fname

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
            if fname.lower() in query_lower:
                return fname
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
