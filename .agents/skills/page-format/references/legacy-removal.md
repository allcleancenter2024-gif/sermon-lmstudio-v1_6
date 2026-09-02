# Legacy Removal

Before removal, inventory imports and runtime call sites and classify them as UNUSED, FALLBACK_ONLY, ACTIVE, TEST_ONLY, MIGRATION_COMPAT, or UNKNOWN. Any UNKNOWN dependency or Legacy-only critical feature blocks deletion. Run a no-fallback test and a dry run first; the dry run must delete zero files.
