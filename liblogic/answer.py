"""Answer generation module for formulating natural language answers from Prolog results."""


def answer_prompt(question, query, results):
    """Generate prompt to formulate answer from Prolog results."""
    bindings_str = "\n".join(results.get('bindings', [])) if results.get('bindings') else "No results found."
    return f"""You are answering a user's question based on logical query results from a knowledge base.

Original Question: {question}

Prolog Query Executed: {query}

Query Results (variable bindings):
{bindings_str}

Instructions:
- Use ONLY the query results to answer the question
- Format the answer clearly and naturally
- If results are empty, say the knowledge base doesn't contain the answer
- List all matching entities found in the results
- Do not add information not present in the results

Answer:"""


def generate_answer(ai, question, query, results):
    """
    Generate a natural language answer from Prolog query results.

    Args:
        ai: AI instance for LLM queries
        question: Original user question
        query: Prolog query that was executed
        results: Dict with 'success', 'bindings', etc.

    Returns:
        str: Natural language answer
    """
    if not results.get('success') or not results.get('bindings'):
        return None

    prompt = answer_prompt(question, query, results)
    return ai.query(prompt)
