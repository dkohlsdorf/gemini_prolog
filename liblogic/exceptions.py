"""Custom exceptions for Gemini Prolog."""


class GeminiPrologError(Exception):
    """Base exception for the project."""
    pass


class WikidataError(GeminiPrologError):
    """Error fetching from Wikidata."""
    pass


class WikidataSearchError(WikidataError):
    """Error searching Wikidata entities."""
    pass


class WikidataSPARQLError(WikidataError):
    """Error executing SPARQL query."""
    pass


class PrologError(GeminiPrologError):
    """Error related to Prolog operations."""
    pass


class PrologQueryError(PrologError):
    """Error generating Prolog query."""
    pass


class PrologExecutionError(PrologError):
    """Error executing Prolog query."""
    pass


class LLMError(GeminiPrologError):
    """Error from LLM API."""
    pass


class LLMResponseError(LLMError):
    """Error parsing LLM response."""
    pass


class EntityExtractionError(GeminiPrologError):
    """Error extracting entities from question."""
    pass
