# Self-Correction Feature

SQLBot can run a bounded self-correction loop for text-to-SQL generation:

1. Build a prompt from the Vietnamese question, linked schema metadata, few-shot examples, and internal skeleton guidance.
2. Ask the active AI backend for SQL.
3. Extract safe SELECT statements only.
4. Execute the first SELECT through `DatabaseManager.execute_select`.
5. If execution fails, pass the SQL error back into the next prompt and retry.
6. Stop after the configured retry limit and return the final success or failure.

## Safety

- Source databases are never modified by this loop.
- Execution is routed through `QueryValidator.is_readonly_select`.
- Non-SELECT, mutating keywords, and stacked statements are rejected before execution.
- Credentials and connection strings are not logged or sent to the prompt.

## Configuration

Default settings live in `config.yaml`:

```yaml
self_correction:
  enabled: true
  max_retries: 3
  log_errors: true
  retry_delay_seconds: 0.0
  include_error_in_prompt: true
  stop_on_syntax_error: false
```

The AI Settings dialog also exposes the retry limit as `Self-Correct`, clamped from 1 to 5 attempts.

## Debugging

The pipeline emits Python logging records for each attempt, execution success, and execution failure. Use the diagnostics returned by `TextToSqlResult.diagnostics` to inspect:

- selected tables and columns;
- attempt count;
- last error;
- error history.
