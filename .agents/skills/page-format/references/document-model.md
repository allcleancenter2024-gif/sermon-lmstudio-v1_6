# Document Model

`Document` contains document type, title, subtitle, neutral metadata, ordered sections, sources, and warnings. Sections contain stable IDs, semantic types, optional headings, neutral content blocks, and heading levels. Never store CSS classes, PDF coordinates, or DOCX style names in the model.

Source provenance belongs in `Source.metadata` and is preserved through adapters and renderers.
