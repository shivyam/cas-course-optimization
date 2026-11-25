"""LLM extraction of course outline data.

Turns the page-by-page text of a course outline into the JSON structure in
`src/backend/helper/outline-text-structure.json`, which the highlighting and
traceability step reads. Modules:

- `llm_client`: the only place that knows which model is used and how (MG: LLM Client).
- `schemas`: the output structure, used both to constrain and to check replies.
- `prompts`: the instructions for each extraction step.
- `extractor`: the entry point, extract() (MG: Extraction). It uses:
  - `model_steps`: the five model calls, each checked and retried once.
  - `output_builder`: builds the output JSON, adds ids and source pages.
  - `quote_search`: finds each quote in the PDF text, repairs bad quotes.
  - `report`: the shared Pages type and the ExtractionReport.
"""
