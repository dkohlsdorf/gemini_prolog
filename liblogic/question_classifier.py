def question_classifier(question):
    return f"""
You are a classifier that decides whether a user question is a good candidate to be handled by a Prolog-based symbolic reasoning system.

Your task:
Given a user question, return JSON only.

A question is a good fit for Prolog if it is:
- precise enough to map to entities, relations, rules, or constraints
- answerable through logical inference, lookup, rule chaining, or structured predicates
- not mainly subjective, creative, emotional, or stylistic
- not requiring broad world knowledge unless that knowledge is already assumed to exist in the Prolog knowledge base
- not too ambiguous without clarification

A question is NOT a good fit for Prolog if it is:
- open-ended or philosophical
- primarily subjective, emotional, or preference-based
- creative writing or brainstorming
- underspecified and impossible to map into predicates
- dependent on missing external context or unstated background knowledge
- better suited for free-form LLM generation than symbolic reasoning

Return exactly this JSON schema:

{{
  "question": "<original question>",
  "fit_for_prolog": true,
  "decision": "yes|no|clarify",
  "confidence": 0.0,
  "reason": "<short explanation>",
  "prolog_characteristics": {{
    "has_clear_entities": true,
    "has_clear_relations": true,
    "requires_rules_or_inference": true,
    "is_subjective": false,
    "is_underspecified": false,
    "requires_external_world_knowledge": false
  }},
  "suggested_next_step": "<one short sentence>"
}}

Rules:
- Use "yes" if the question is a strong fit for Prolog.
- Use "no" if it is a poor fit.
- Use "clarify" if it could fit, but needs missing entities, relations, or assumptions first.
- confidence must be between 0.0 and 1.0
- Output valid JSON only
- Do not include markdown
- Do not include any extra commentary

Question: {question}
"""

