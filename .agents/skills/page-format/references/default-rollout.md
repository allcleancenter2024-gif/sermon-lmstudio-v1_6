# Default Rollout

Keep legacy exporters and fallback paths available while promoting V2 in order: internal, canary percentage, then 100. After the 100% gate passes, V2 is the default; set `PAGE_FORMAT_V2=false` and `PAGE_FORMAT_ROLLOUT=legacy` to roll back. A critical source, security, Unicode, PDF, DOCX, or accessibility failure stops promotion.
