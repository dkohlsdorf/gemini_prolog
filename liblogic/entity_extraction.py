import requests
import time

from liblogic.logger import logger
from liblogic.exceptions import WikidataSearchError, WikidataSPARQLError

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
MAX_RETRIES = 3
BASE_TIMEOUT = 120


def extract_entity_ids(search_results, top_n=1):
    """Extract the top N entity IDs from each search result."""
    entity_ids = []
    for result in search_results:
        for item in result.get("search", [])[:top_n]:
            entity_ids.append(item["id"])
    return entity_ids


MAX_ENTITIES_PER_QUERY = 50  # Prevent URL too long errors


def wikidata_sparql_query(entity_ids, limit=2000):
    """Query Wikidata SPARQL endpoint for all properties of given entities."""
    # Batch entities to avoid URL too long errors
    if len(entity_ids) > MAX_ENTITIES_PER_QUERY:
        all_results = {"results": {"bindings": []}}
        for i in range(0, len(entity_ids), MAX_ENTITIES_PER_QUERY):
            batch = entity_ids[i:i + MAX_ENTITIES_PER_QUERY]
            batch_results = wikidata_sparql_query(batch, limit=limit // max(1, len(entity_ids) // MAX_ENTITIES_PER_QUERY))
            all_results["results"]["bindings"].extend(batch_results.get("results", {}).get("bindings", []))
        return all_results

    values_clause = " ".join(f"wd:{eid}" for eid in entity_ids)

    # Wikimedia meta-properties to exclude
    excluded_properties = [
        "P6104",  # maintained by WikiProject
        "P2184",  # history of topic
        "P5125",  # Wikimedia outline
        "P910",   # topic's main category
        "P1424",  # topic's main template
        "P1151",  # topic's main Wikimedia portal
        "P7084",  # related category
        "P373",   # Commons category
        "P935",   # Commons gallery
        "P1753",  # list related to category
        "P1482",  # Stack Exchange tag
        "P8989",  # category for the interior of the item
        "P3921",  # Wikidata SPARQL query equivalent
        "P2959",  # permanent duplicated item
        "P1343",  # described by source
        "P972",   # catalog
        "P1687",  # Wikidata property
        "P1709",  # equivalent class
        "P2888",  # exact match
        "P1889",  # different from
        "P460",   # said to be the same as
        "P989",   # spoken text audio
        "P51",    # audio
        "P443",   # pronunciation audio
    ]
    excluded_props_clause = ", ".join(f"wd:{p}" for p in excluded_properties)

    query = f"""
    SELECT ?entity ?entityLabel ?propertyLabel ?value ?valueLabel WHERE {{
      VALUES ?entity {{ {values_clause} }}
      ?entity ?p ?value .
      ?property wikibase:directClaim ?p .
      ?property wikibase:propertyType ?type .
      FILTER(?type NOT IN (wikibase:ExternalId, wikibase:Url, wikibase:CommonsMedia))
      FILTER(?property NOT IN ({excluded_props_clause}))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT {limit}
    """

    headers = {
        "User-Agent": "DanielK-WikidataBot/1.0 (your@email.com)",
        "Accept": "application/sparql-results+json"
    }

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(
                WIKIDATA_SPARQL_URL,
                params={"query": query},
                headers=headers,
                timeout=BASE_TIMEOUT
            )
            # Retry on server errors (5xx)
            if r.status_code >= 500:
                raise requests.exceptions.HTTPError(f"Server error: {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** (attempt + 1)  # Exponential backoff: 2s, 4s, 8s
                logger.warning(f"SPARQL query error ({e}), retrying in {wait_time}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                logger.error(f"SPARQL query failed after {MAX_RETRIES} attempts: {e}")
                raise WikidataSPARQLError(f"Failed to query Wikidata SPARQL: {e}") from e


def wikidata_sparql_inverse_query(entity_ids, limit=500):
    """Query for entities that reference the given entities (inverse relationships)."""
    # Batch entities to avoid URL too long errors
    if len(entity_ids) > MAX_ENTITIES_PER_QUERY:
        all_results = {"results": {"bindings": []}}
        for i in range(0, len(entity_ids), MAX_ENTITIES_PER_QUERY):
            batch = entity_ids[i:i + MAX_ENTITIES_PER_QUERY]
            batch_results = wikidata_sparql_inverse_query(batch, limit=limit // max(1, len(entity_ids) // MAX_ENTITIES_PER_QUERY))
            all_results["results"]["bindings"].extend(batch_results.get("results", {}).get("bindings", []))
        return all_results

    values_clause = " ".join(f"wd:{eid}" for eid in entity_ids)

    # Properties useful for inverse lookups
    inverse_properties = [
        "P131",   # located in the administrative territorial entity
        "P17",    # country
        "P138",   # named after
        "P279",   # subclass of
        "P31",    # instance of
        "P361",   # part of
        "P39",    # position held
        "P69",    # educated at
        "P108",   # employer
        "P175",   # performer
        "P86",    # composer
        "P170",   # creator
        "P50",    # author
    ]
    props_clause = " ".join(f"wdt:{p}" for p in inverse_properties)

    query = f"""
    SELECT ?subject ?subjectLabel ?propertyLabel ?entity ?entityLabel WHERE {{
      VALUES ?entity {{ {values_clause} }}
      VALUES ?p {{ {props_clause} }}
      ?subject ?p ?entity .
      ?property wikibase:directClaim ?p .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT {limit}
    """

    headers = {
        "User-Agent": "DanielK-WikidataBot/1.0 (your@email.com)",
        "Accept": "application/sparql-results+json"
    }

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(
                WIKIDATA_SPARQL_URL,
                params={"query": query},
                headers=headers,
                timeout=BASE_TIMEOUT
            )
            if r.status_code >= 500:
                raise requests.exceptions.HTTPError(f"Server error: {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning(f"Inverse SPARQL query error ({e}), retrying in {wait_time}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                logger.error(f"Inverse SPARQL query failed after {MAX_RETRIES} attempts: {e}")
                raise WikidataSPARQLError(f"Failed to query Wikidata SPARQL (inverse): {e}") from e


def extract_subject_entity_ids(sparql_results):
    """Extract entity IDs from subject values in inverse SPARQL results."""
    entity_ids = set()
    for binding in sparql_results.get("results", {}).get("bindings", []):
        subject = binding.get("subject", {})
        if subject.get("type") == "uri":
            uri = subject.get("value", "")
            if "wikidata.org/entity/Q" in uri:
                entity_id = uri.split("/")[-1]
                entity_ids.add(entity_id)
    return list(entity_ids)


def iter_triples(sparql_results):
    """Iterate over SPARQL results as (subject, predicate, object) string tuples."""
    for binding in sparql_results.get("results", {}).get("bindings", []):
        subject = binding.get("entityLabel", {}).get("value", "")
        predicate = binding.get("propertyLabel", {}).get("value", "")
        obj = binding.get("valueLabel", {}).get("value", "")
        yield (subject, predicate, obj)


def extract_object_entity_ids(sparql_results):
    """Extract entity IDs from object values in SPARQL results."""
    entity_ids = set()
    for binding in sparql_results.get("results", {}).get("bindings", []):
        value = binding.get("value", {})
        if value.get("type") == "uri":
            uri = value.get("value", "")
            if "wikidata.org/entity/Q" in uri:
                entity_id = uri.split("/")[-1]
                entity_ids.add(entity_id)
    return list(entity_ids)


def expand_query(initial_entity_ids, depth=1, limit_per_query=500):
    """
    Expand the knowledge base by fetching triples for objects too.
    Also fetches inverse relationships (entities that reference our entities).

    Args:
        initial_entity_ids: Starting entity IDs (e.g., ['Q7251', 'Q8789'])
        depth: How many levels to expand (1 = fetch objects, 2 = fetch objects of objects)
        limit_per_query: Max triples per SPARQL query

    Returns:
        Combined SPARQL results with all triples
    """
    all_bindings = []
    seen_entities = set(initial_entity_ids)
    current_entities = initial_entity_ids

    for i in range(depth + 1):
        if not current_entities:
            break

        # Forward query: entity -> property -> value
        results = wikidata_sparql_query(current_entities, limit=limit_per_query)
        bindings = results.get("results", {}).get("bindings", [])
        all_bindings.extend(bindings)

        # Extract new entity IDs from forward query objects
        new_entity_ids = set(extract_object_entity_ids(results))

        # Inverse query: subject -> property -> entity (only on first 2 iterations to limit explosion)
        if i < 2:
            # Use higher limit for initial entities to find more references
            inverse_limit = 2000 if i == 0 else limit_per_query
            inverse_results = wikidata_sparql_inverse_query(current_entities, limit=inverse_limit)
            logger.debug(f"Inverse query found {len(inverse_results.get('results', {}).get('bindings', []))} references")
            inverse_bindings = inverse_results.get("results", {}).get("bindings", [])
            # Convert inverse bindings to same format as forward bindings
            for b in inverse_bindings:
                converted = {
                    "entityLabel": b.get("subjectLabel", {}),
                    "propertyLabel": b.get("propertyLabel", {}),
                    "valueLabel": b.get("entityLabel", {}),
                    "entity": b.get("subject", {}),
                    "value": b.get("entity", {})
                }
                all_bindings.append(converted)
            # Add subjects from inverse query to expansion
            inverse_entity_ids = extract_subject_entity_ids(inverse_results)
            new_entity_ids.update(inverse_entity_ids)

        # Combine forward and inverse entity IDs for next iteration
        current_entities = [eid for eid in new_entity_ids if eid not in seen_entities]
        # Cap entities per iteration to prevent explosion
        if len(current_entities) > 100:
            current_entities = current_entities[:100]
        seen_entities.update(current_entities)

    return {"results": {"bindings": all_bindings}}


def wikidata_search(term, limit=5):
    url = "https://www.wikidata.org/w/api.php"

    headers = {
        "User-Agent": "DanielK-WikidataBot/1.0 (your@email.com)"
    }

    params = {
        "action": "wbsearchentities",
        "search": term,
        "language": "en",
        "format": "json",
        "limit": limit,
    }

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=BASE_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                logger.warning(f"Wikidata search timeout for '{term}', retrying in {wait_time}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                logger.error(f"Wikidata search failed for '{term}' after {MAX_RETRIES} attempts: {e}")
                raise WikidataSearchError(f"Failed to search Wikidata for '{term}': {e}") from e


def all_search_results(search_plan):    
    search_results = []
    for query_term in search_plan:        
        result = wikidata_search(query_term['query'])
        search_results.append(result)
    return search_results


def wiki_query_preparation(question):
    return f"""
You are an extraction system for Wikidata entity resolution.

Return ONLY valid JSON.

Schema:
{{
  "entity_candidates": ["..."],
  "property_candidates": ["..."],
  "context_keywords": ["..."],
  "search_plan": [
    {{
      "type": "entity",
      "query": "..."
    }}
  ]
}}

Rules:
- Put proper names into entity_candidates.
- Put relations/attributes into property_candidates.
- Put domain/context terms into context_keywords.

CRITICAL - Search Query Rules:
- Keep search queries SHORT: 1-2 words maximum.
- Wikidata search is simple text matching, NOT semantic search.

IMPORTANT - Only search for SPECIFIC NAMED ENTITIES:
- DO search for: proper nouns, named places, named people, named organizations
- DO NOT search for: generic concepts like "bridge", "mayor", "city", "person", "mammal"
- Generic concepts pollute results with schema/ontology data instead of actual instances

For questions about "X in Y" or "Y's X":
- Search for the NAMED entity (Y), not the generic type (X)
- "Bridges in Bremen" → search only "Bremen" (bridges will be found via relationships)
- "Universities in California" → search only "California"

For questions involving NAMED THINGS (bridges, streets, buildings named after people):
- If you can infer likely names, search for those people directly
- "Bremen mayors with bridges named after them" → search "Bremen", "Wilhelm Kaisen", "Hans Koschnick" (famous Bremen mayors)
- Use your knowledge to add relevant historical figures that might be the answer

For BIOLOGICAL questions:
- Search for scientific names: "Delphinidae", "Mammalia", "Homo sapiens"
- These are specific taxa, not generic concepts

Examples:
- "List Bremen's mayors with bridges named after them" → search_plan: ["Bremen"]
- "What universities are in Boston?" → search_plan: ["Boston"]
- "Are dolphins mammals?" → search_plan: ["Delphinidae", "Mammalia"]
- "Where was Einstein born?" → search_plan: ["Albert Einstein"]

Bad examples (DO NOT DO):
- "bridge" (generic concept)
- "mayor" (generic concept)
- "university" (generic concept)
- "mammal" (generic - use "Mammalia" instead)

Question:
{question}
    """

