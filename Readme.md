# 📘 Gemini-Prolog: LLM + Symbolic Reasoning Pipeline

A hybrid question-answering system that combines **LLMs**, **Wikidata**, and **Prolog** to perform **structured reasoning over real-world knowledge**.

Instead of doing pure RAG, this system:
- Builds a **temporary knowledge base from Wikidata**
- Converts it into **Prolog facts**
- Generates a **logical query**
- Executes it with **SWI-Prolog**
- Uses the LLM only for **planning and final answer formatting**

---

## 🚀 Overview

The pipeline (`run_pipeline`) works as follows:

```
User Question
    ↓
LLM Classifier → (Prolog vs direct LLM)
    ↓
Entity + Search Plan Extraction
    ↓
Wikidata Search + Expansion
    ↓
Convert to Prolog Facts
    ↓
LLM generates Prolog Query
    ↓
Execute in SWI-Prolog
    ↓
LLM formats final answer
```

---

## 🧠 Key Ideas

- **Not RAG** → builds a structured KB on the fly
- **Symbolic reasoning** → Prolog executes actual logic
- **LLM as planner, not source of truth**
- **Fallback mechanism** → if logic fails, revert to LLM

---

## 📂 Project Structure

```
.
├── gemini_prolog.py        # Main pipeline
├── answer.py               # Answer generation from Prolog results
├── entity_extraction.py    # Wikidata search + expansion
├── prolog.py               # Fact generation + query execution
├── llm_helpers.py          # Gemini client wrapper
├── question_classifier.py  # Decide if Prolog is suitable
├── logger.py               # Logging setup
├── exceptions.py           # Custom errors
├── requirements.txt
```

---

## ⚙️ Requirements

- Python 3.10+
- SWI-Prolog installed
- Google GenAI API access

Install dependencies:

```bash
pip install -r requirements.txt
```

Install SWI-Prolog:

```bash
brew install swi-prolog     # macOS
sudo apt install swi-prolog # Linux
```

---

## 🔧 Usage

Run the pipeline from CLI:

```bash
python gemini_prolog.py "Where was Einstein born?"
```

If no question is provided, a default is used.

---

## 🧩 Pipeline Details

### 1. Question Classification

Decides if symbolic reasoning is useful:

- Uses LLM → structured JSON output
- Falls back to LLM if not suitable

---

### 2. Wikidata Search & Expansion

- Generates **short search queries**
- Retrieves entities via Wikidata API
- Expands graph via:
  - forward relations
  - inverse relations

---

### 3. Prolog Fact Generation

Converts triples into facts:

```prolog
instance_of(tyrannosaurus_rex, dinosaur).
```

Also adds inferred facts:

- `likely_named_after/2`
- `name_contains_meaning/2`

---

### 4. Query Generation (LLM → Prolog)

The LLM generates a query like:

```prolog
?- instance_of(X, dinosaur), name_contains_meaning(X, king).
```

Strict rules:
- Must be logically connected
- No hallucinated predicates

---

### 5. Execution (SWI-Prolog)

- Runs query via subprocess
- Returns all bindings
- Timeout protection (30s)

---

### 6. Answer Generation

LLM formats result:

- Uses **only bindings**
- No hallucination allowed

---

## 🛑 Error Handling

Custom exceptions include:

- `WikidataError`
- `PrologError`
- `LLMError`

---

## 🧪 Example

```bash
python gemini_prolog.py "List dinosaurs with names related to king"
```

Possible reasoning:

- Detect "rex" → meaning "king"
- Match entities like `tyrannosaurus_rex`

---

## 🔁 Fallback Behavior

If any step fails:

- No entities found
- Query is unanswerable
- No Prolog results

→ System falls back to **direct LLM answer**

---

## ⚠️ Limitations

- No temporal reasoning
- Limited KB size (depends on expansion depth)
- Relies on LLM to generate correct queries
- Wikidata noise can affect results

---

## 🧭 Design Philosophy

This system explores:

> "Can we replace RAG with structured, symbolic reasoning over dynamically constructed knowledge bases?"

Key principle:

- **LLM = planner**
- **Prolog = executor**
- **Wikidata = ground truth**

---

## 🛠 Future Improvements

- Typed predicates / schema constraints
- Better query validation
- Caching Wikidata expansions
- Incremental KB building
- Replace Prolog with custom inference engine

