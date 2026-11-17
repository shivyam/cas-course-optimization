"""LLM extraction of course outline data.

Turns the page-by-page text of a course outline into the JSON structure in
`src/backend/helper/outline-text-structure.json`, which the highlighting and
traceability step reads. Modules:

- `llm_client`: the only place that knows which model is used and how (MG: LLM Client).
- `schemas`: the output structure, used both to constrain and to check replies.
- `prompts`: the instructions for each extraction step.
- `extractor`: runs the steps, checks replies, fills in source pages (MG: Extraction).
"""
