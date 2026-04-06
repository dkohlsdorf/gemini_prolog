import json
import re

from google import genai

from liblogic.logger import logger
from liblogic.exceptions import LLMError, LLMResponseError


MODEL = 'gemini-3-flash-preview'


def extract_json(text):
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    matches = re.findall(code_block_pattern, text)
    if matches:
        text = matches[0].strip()

    # Find JSON object or array boundaries
    text = text.strip()
    if text.startswith('{'):
        return text
    elif text.startswith('['):
        return text

    # Last resort: find first { or [ and extract from there
    start = min(
        (text.find('{') if text.find('{') != -1 else float('inf')),
        (text.find('[') if text.find('[') != -1 else float('inf'))
    )
    if start != float('inf'):
        return text[start:]

    return text


class AI:
    def __init__(self):
        try:
            self.client = genai.Client()
            logger.debug("AI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            raise LLMError(f"Failed to initialize AI client: {e}") from e

    def query(self, question):
        """Send a query to the LLM and return the response text."""
        try:
            logger.debug(f"Sending query to LLM ({len(question)} chars)")
            response = self.client.models.generate_content(
                model=MODEL, contents=question
            )
            logger.debug(f"Received response ({len(response.text)} chars)")
            return response.text
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise LLMError(f"LLM query failed: {e}") from e

    def query_json(self, question):
        """Send a query and parse the response as JSON."""
        raw_response = self.query(question)

        # Save raw response for debugging
        try:
            with open('question_query.txt', 'w') as f:
                f.write(raw_response)
        except IOError as e:
            logger.warning(f"Could not save debug file: {e}")

        # Extract and parse JSON
        cleaned = extract_json(raw_response)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {raw_response[:500]}...")
            raise LLMResponseError(f"Failed to parse LLM response as JSON: {e}") from e
