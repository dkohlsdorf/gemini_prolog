import json
import sys

from liblogic.llm_helpers import AI
from liblogic.question_classifier import question_classifier
from liblogic.entity_extraction import (
    wiki_query_preparation,
    extract_entity_ids,
    expand_query,
    all_search_results
)
from liblogic.prolog import facts, query_prompt, run_query
from liblogic.answer import generate_answer
from liblogic.logger import logger, setup_logger
from liblogic.exceptions import (
    GeminiPrologError,
    WikidataError,
    PrologError,
    LLMError
)


def run_pipeline(question, ai):
    """
    Run the full question-answering pipeline.

    Args:
        question: The user's question
        ai: AI instance for LLM queries

    Returns:
        str: The answer to the question
    """
    # Step 1: Classify question
    logger.info(f"Processing question: {question}")
    logic_result = ai.query_json(question_classifier(question))
    use_logic = logic_result['fit_for_prolog']
    logger.info(f"Question fit for Prolog: {use_logic}")

    if not use_logic:
        logger.info("Using direct LLM response")
        return ai.query(question)

    # Step 2: Extract search plan
    wiki_concept_query = ai.query_json(wiki_query_preparation(question))
    search_plan = wiki_concept_query['search_plan']
    logger.info(f"Search plan: {[q['query'] for q in search_plan]}")

    # Step 3: Search Wikidata
    search_results = all_search_results(search_plan)
    entity_ids = extract_entity_ids(search_results, top_n=2)
    logger.info(f"Found {len(entity_ids)} entity IDs: {entity_ids}")

    if not entity_ids:
        logger.warning("No entities found, falling back to LLM")
        return ai.query(question)

    # Step 4: Expand knowledge graph
    expanded_results = expand_query(entity_ids, depth=2)
    fact_count = len(expanded_results.get('results', {}).get('bindings', []))
    logger.info(f"Expanded to {fact_count} facts")

    # Step 5: Generate Prolog facts
    prolog_facts = facts(expanded_results)

    # Step 6: Generate Prolog query
    prolog = ai.query(query_prompt(question, prolog_facts))

    # Save for debugging
    with open('prolog_query.pro', 'w') as f:
        f.write(prolog_facts)
        f.write('\n\n')
        f.write(prolog)
    logger.debug("Saved Prolog facts and query to prolog_query.pro")

    # Step 7: Check if answerable
    if prolog.startswith('UNANSWERABLE'):
        logger.warning(f"Query deemed unanswerable: {prolog[:100]}...")
        logger.info("Falling back to LLM")
        return f"{prolog}\n\n--- Fallback to LLM ---\n{ai.query(question)}"

    # Step 8: Execute Prolog query
    result = run_query(prolog_facts, prolog)

    # Save result for debugging
    with open('result.txt', 'w') as f:
        f.write(json.dumps(result, indent=2))

    logger.info(f"Query success: {result.get('success')}, bindings: {len(result.get('bindings', []))}")

    # Step 9: Generate answer
    if result.get('success') and result.get('bindings'):
        answer = generate_answer(ai, question, prolog, result)
        if answer:
            return f"Query: {result.get('query')}\nResults: {len(result.get('bindings', []))} bindings\n\n{answer}"

    # Fallback
    logger.info("No results from Prolog, falling back to LLM")
    return f"No results found in knowledge base.\n\n--- Fallback to LLM ---\n{ai.query(question)}"


def main():
    """Main entry point."""
    # Setup logging
    setup_logger()

    # Default question (can be overridden via command line)
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "List all dinosaurs with names related to king"

    try:
        # Initialize AI
        ai = AI()

        # Run pipeline
        answer = run_pipeline(question, ai)
        print("\n" + "=" * 50)
        print(answer)
        print("=" * 50)

    except WikidataError as e:
        logger.error(f"Wikidata error: {e}")
        print(f"Error: Could not fetch data from Wikidata: {e}")
        sys.exit(1)

    except PrologError as e:
        logger.error(f"Prolog error: {e}")
        print(f"Error: Prolog execution failed: {e}")
        sys.exit(1)

    except LLMError as e:
        logger.error(f"LLM error: {e}")
        print(f"Error: LLM request failed: {e}")
        sys.exit(1)

    except GeminiPrologError as e:
        logger.error(f"Pipeline error: {e}")
        print(f"Error: {e}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\nInterrupted.")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
