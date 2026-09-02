# Fallback Analysis

V2 exceptions may use Legacy fallback only when the failure is not document validation or a critical integrity decision. Every fallback records a format-specific `PF_FALLBACK_*` code without content. Validation, source-loss, security, and Unicode failures remain explicit and must be investigated.
