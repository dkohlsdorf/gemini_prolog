import re
import subprocess
import tempfile
import os

from liblogic.entity_extraction import iter_triples
from liblogic.logger import logger
from liblogic.exceptions import PrologExecutionError


def fact(strg):
    return re.sub(r'[^a-z0-9_]', '', strg.lower().replace(' ', '_'))


def normalize_for_matching(name):
    """Remove underscores and common suffixes for substring matching."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


# Etymology roots and their meanings
ETYMOLOGY_ROOTS = {
    # King/Royal
    'rex': 'king', 'regina': 'queen', 'regis': 'king', 'basileus': 'king',
    'raja': 'king', 'rani': 'queen', 'imperial': 'royal', 'tyrannus': 'tyrant',
    # Size
    'magnus': 'great', 'maximus': 'greatest', 'gigas': 'giant', 'titan': 'giant',
    'mega': 'large', 'micro': 'small', 'nano': 'tiny', 'minus': 'small',
    # Teeth/Claws
    'odon': 'tooth', 'dont': 'tooth', 'dens': 'tooth', 'onyx': 'claw', 'raptor': 'thief',
    # Body parts
    'saurus': 'lizard', 'ceratops': 'horned_face', 'cephalus': 'head', 'pteryx': 'wing',
    # Other
    'ferox': 'fierce', 'horridus': 'rough', 'terribilis': 'terrible',
}


def infer_etymology(fact_base_lines):
    """
    Infer name_meaning relationships by detecting etymology roots in entity names.
    E.g., tyrannosaurus_rex contains 'rex' which means 'king'.
    """
    inferred = []
    entities = set()

    # Collect all entities mentioned in facts
    for line in fact_base_lines:
        matches = re.findall(r'\((\w+),|\,\s*(\w+)\)', line)
        for m in matches:
            for entity in m:
                if entity:
                    entities.add(entity)

    # Check each entity for etymology roots
    for entity in entities:
        entity_lower = entity.lower()
        for root, meaning in ETYMOLOGY_ROOTS.items():
            if root in entity_lower:
                inferred.append(f"name_contains_meaning({entity}, {meaning}).")
                inferred.append(f"name_contains_root({entity}, {root}).")

    # Add root meanings as facts
    for root, meaning in ETYMOLOGY_ROOTS.items():
        inferred.append(f"root_meaning({root}, {meaning}).")

    return list(set(inferred))  # Remove duplicates


def infer_named_after(fact_base_lines):
    """
    Infer likely_named_after relationships by string matching.
    If a person's name appears as substring in a structure's name, they're likely related.
    """
    # Collect entities by type
    people = set()
    structures = set()
    structure_keywords = ['brcke', 'brucke', 'bridge', 'strasse', 'strae', 'street',
                          'platz', 'tower', 'turm', 'halle', 'stadium', 'airport',
                          'station', 'bahnhof', 'schule', 'school', 'park', 'weg']

    # Parse existing facts to find people and structures
    for line in fact_base_lines:
        # Find people (instance_of human or has position_held)
        match = re.match(r'instance_of\((\w+),\s*human\)', line)
        if match:
            people.add(match.group(1))
        match = re.match(r'position_held\((\w+),', line)
        if match:
            people.add(match.group(1))

        # Find structures by name pattern
        match = re.match(r'\w+\((\w+),', line)
        if match:
            entity = match.group(1)
            if any(kw in entity for kw in structure_keywords):
                structures.add(entity)

    # Find substring matches
    inferred = []
    for structure in structures:
        struct_normalized = normalize_for_matching(structure)
        for person in people:
            person_normalized = normalize_for_matching(person)
            # Check if person's name (without underscores) appears in structure name
            if len(person_normalized) >= 5 and person_normalized in struct_normalized:
                inferred.append(f"likely_named_after({structure}, {person}).")

    return inferred


def facts(sparql_results):
    fact_base = []
    for s, p, o in iter_triples(sparql_results):
        fact_base.append(f"{fact(p)}({fact(s)}, {fact(o)}).")

    # Add inferred named_after relationships
    inferred_names = infer_named_after(fact_base)
    if inferred_names:
        fact_base.append("\n% Inferred from name matching:")
        fact_base.extend(inferred_names)

    # Add inferred etymology relationships
    inferred_etymology = infer_etymology(fact_base)
    if inferred_etymology:
        fact_base.append("\n% Inferred from etymology:")
        fact_base.extend(inferred_etymology)

    return "\n".join(fact_base)


def extract_predicates(fact_base_str):
    """Extract unique predicates from the fact base."""
    predicates = set()
    for line in fact_base_str.strip().split('\n'):
        match = re.match(r'(\w+)\(', line)
        if match:
            predicates.add(match.group(1))
    return sorted(predicates)


def query_prompt(question, fact_base_str):
    """Generate a prompt for the LLM to create a Prolog query."""
    predicates = extract_predicates(fact_base_str)

    return f"""You are a Prolog query generator.

Available predicates: {', '.join(predicates)}

Fact base:
{fact_base_str}

CRITICAL RULES:
- Return ONLY a valid Prolog query, no explanations
- Use lowercase with underscores for atoms (e.g., alan_turing, world_war_ii)
- Format: ?- goal1, goal2, ...

LOGICAL CONNECTION RULES:
- Do NOT just conjoin unrelated facts. Each goal must share variables or entities with other goals.
- BAD: field_of_work(alan_turing, cryptography), subclass_of(world_war_ii, war).
  (These facts are unrelated - no shared variable connects them)
- GOOD: field_of_work(Person, cryptography), employer(Person, Org), participant(War, Org).
  (Person connects the goals logically)

SPECIAL PREDICATES:
- likely_named_after(Structure, Person): Inferred when a person's name appears in a structure's name (e.g., wilhelmkaisenbrcke likely named after wilhelm_kaisen)
- name_contains_meaning(Entity, Meaning): Inferred from etymology (e.g., tyrannosaurus_rex contains meaning 'king' because 'rex' = king)
- name_contains_root(Entity, Root): The etymology root found in the name (e.g., name_contains_root(tyrannosaurus_rex, rex))
- root_meaning(Root, Meaning): Maps roots to meanings (e.g., root_meaning(rex, king))
- Use these predicates for questions about name meanings or etymology

LIMITATIONS TO CONSIDER:
- The fact base may lack temporal relationships (e.g., "during" is not explicit)
- If you cannot construct a query that LOGICALLY answers the question with connected facts, respond with: UNANSWERABLE: <reason>
- A query succeeding only proves the conjunction of facts exists, not causation or temporal overlap

Question: {question}

Query:"""


def parse_query(query_str):
    """Parse query string, remove ?- prefix and trailing period."""
    query = query_str.strip()
    if query.startswith("?-"):
        query = query[2:].strip()
    if query.endswith("."):
        query = query[:-1].strip()
    return query


def run_query(fact_base_str, query_str, find_all=True):
    """
    Execute a Prolog query against the fact base using SWI-Prolog.

    Args:
        fact_base_str: The Prolog facts as a string
        query_str: The query (with or without ?- prefix)
        find_all: If True, find all solutions. If False, just check if query succeeds.

    Returns:
        dict with 'success', 'bindings', 'query', and 'error' (if any)
    """
    query = parse_query(query_str)

    if not query:
        return {"success": False, "error": "Empty query", "bindings": []}

    # Extract variables from query
    variables = list(set(re.findall(r'\b([A-Z][a-zA-Z0-9_]*)\b', query)))

    # Build the Prolog program
    if find_all and variables:
        # Create output format for variables
        var_format = ", ".join([f"'{v}=', {v}" for v in variables])
        program = f"""{fact_base_str}

run :-
    forall(
        ({query}),
        (write('SOLUTION: '), writeln([{var_format}]))
    ),
    halt(0).

run :- halt(1).

:- run.
"""
    else:
        # Just check success/failure
        program = f"""{fact_base_str}

run :- ({query}) -> halt(0) ; halt(1).

:- run.
"""

    # Write to temp file and execute
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pl', delete=False) as f:
        f.write(program)
        temp_path = f.name

    try:
        logger.debug(f"Executing Prolog query: {query}")
        result = subprocess.run(
            ['swipl', '-q', temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        success = result.returncode == 0
        bindings = []

        # Parse solutions
        for line in result.stdout.split('\n'):
            if line.startswith('SOLUTION:'):
                bindings.append(line[9:].strip())

        logger.info(f"Prolog query returned {len(bindings)} results")
        if result.stderr:
            logger.debug(f"Prolog stderr: {result.stderr}")

        return {
            "success": success or len(bindings) > 0,
            "bindings": bindings,
            "query": query,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        logger.error("Prolog query timed out after 30 seconds")
        raise PrologExecutionError("Query timeout after 30 seconds")
    except FileNotFoundError:
        logger.error("SWI-Prolog not found")
        raise PrologExecutionError("SWI-Prolog not found. Install with: brew install swi-prolog")
    finally:
        os.unlink(temp_path)
