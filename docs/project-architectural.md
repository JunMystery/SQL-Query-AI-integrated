# SQLBot Architectural Notes

Last scanned: 2026-06-01

SQLBot Desktop is a Windows-focused Python/PySide6 desktop application that turns Vietnamese natural-language requests into safe SQL SELECT queries. The architecture is a small MVC desktop app with service and infrastructure layers for AI, schema metadata, persistence, and SQL execution.

## Architecture Style

SQLBot follows a pragmatic MVC shape:

- **Views** render UI and emit PySide6 signals. They should not own database, AI, or persistence workflows.
- **Controllers** connect view signals to application workflows, manage background `QThread` tasks, and coordinate services/repositories.
- **Services** implement domain behavior such as AI generation, prompt building, schema linking, validation, embeddings, evaluation, CPU limiting, and self-correction logging.
- **Infrastructure** owns external/local persistence and database access.
- **Models** are shared dataclasses/enums that cross layer boundaries.
- **Agents** provide an advanced, more structured SQL planning path beside the prompt-based pipeline.

The main runtime boundary is `MainController`: it owns the active view, active DB connection name, `AIEngine`, `TextToSqlPipeline`, activity storage, annotation storage, and schema context.

## Data Boundaries

SQLBot separates the user source database from local application data:

| Boundary | Write policy | Owner |
|---|---:|---|
| Source MySQL/PostgreSQL database | Generated/user SQL must be SELECT-only | `DatabaseManager.execute_select`, `QueryValidator` |
| Connection profiles | Local JSON, no database passwords | `ProfileRepository` |
| Admin password | Local salted hash | `AdminPasswordStore` |
| Schema annotations | Local JSON | `AnnotationRepository` |
| Schema metadata/sample values/embeddings | Local SQLite | `SchemaMetadataRepository` |
| History/bookmarks | Local SQLite | `ActivityRepository` |
| AI settings | Local JSON | `AISettingsRepository` |
| Query attempt logs | Local JSONL under `logs/queries` | `QueryLogger` |

Generated SQL execution is guarded by `QueryValidator.is_readonly_select()`, which rejects non-SELECT statements, mutating keywords, and stacked statements. Sample value refreshes use service-owned SELECT queries and write only to the local metadata store.

## AI and Text-to-SQL Architecture

`AIEngine` is the backend adapter:

- Local mode loads `.gguf` through `llama_cpp.Llama`.
- API mode calls an OpenAI-compatible chat completions endpoint with optional stored `api_key`.
- Both modes expose prompt generation through `generate_prompt()`.
- `unload()` clears the active model/config and runs garbage collection.

`TextToSqlPipeline` is the primary orchestration service:

1. Build schema context from `SchemaLinker` and `SchemaMarkdownFormatter`.
2. Try `AdvancedSQLAgent` using structured JSON intent parsing.
3. Fall back to `PromptBuilder` with English system instructions, internal skeleton planning, few-shot examples, and previous SQL errors.
4. Extract safe SELECTs with `SQLExtractor`.
5. Optionally execute the first SELECT through a caller-provided `execute_sql` function.
6. Feed execution errors into the next prompt until `max_retries`.
7. Return `TextToSqlResult` with SQL candidates, raw response, diagnostics, and optional execution result.

Embeddings are optional but preferred:

- `SentenceTransformersEmbeddingModel` lazily loads `all-MiniLM-L6-v2`.
- If `sentence-transformers` or the model is unavailable, the app falls back to `DeterministicEmbeddingModel`.
- Embeddings are used by schema linking and few-shot selection.

The advanced agent path is composed from:

- `AdvancedSQLAgent`: gets metadata and asks the AI backend for JSON query intent.
- `Orchestrator`: coordinates join planning, filter parsing, grouping, set operations, subquery helpers, and validation.
- `SchemaGraph`, `JoinPlanner`, `OperatorClassifier`, `GroupingHandler`, `SubqueryGenerator`, `SetOpHandler`, `CorrectionLoop`: specialized helpers.

## UI Architecture

The UI is signal-driven:

- `LoginWindow` emits login and connection-management requests.
- `MainWindow` emits generation, execution, bookmark, schema, settings, load/unload, refresh-samples, cancel, language, and result-view requests.
- Controllers wire those signals to services and repositories.

Important UI surfaces:

- `views/login_window.py`: modern login screen.
- `views/main_window.py`: main workspace, AI panel, chat/results surfaces, schema dock, visual query builder integration, theme/language controls.
- `views/dialogs/settings_dialog.py`: broader settings and schema annotation surfaces.
- `views/dialogs/ai_settings_dialog.py`: compact AI configuration dialog.
- `views/components/visual_query_builder.py`: manual query builder with tables, selected columns, WHERE, GROUP BY, ORDER BY, LIMIT, guide dialog, and SQL preview.
- `views/components/schema_tree_widget.py`: schema viewer tree.

Styling and assets:

- `resources/ui/styles/light.qss` and `dark.qss` are shared themes.
- `resources/ui/icons/*.svg` provide shared icon assets.
- `views.theme.project_root()` and `load_stylesheet()` resolve resources both in source and PyInstaller contexts.

Localization:

- `I18nManager` loads `resources/i18n/<lang>/*.strings.xml`.
- Supported resource folders currently include `vi`, `en`, and `jp`.
- Language preference is stored in `QSettings("SQLBot", "SQLBotDesktop")`.

## Persistence and Build Architecture

Local persistence is intentionally simple:

- JSON for profiles, annotations, and AI settings.
- SQLite for activity and schema metadata.
- JSONL for self-correction attempt logs.

Build packaging:

- `scripts/build_app.py` installs requirements, checks direct SQL drivers, runs PyInstaller, copies PostgreSQL `LIBPQ.dll`, and verifies packaged MySQL/PostgreSQL drivers.
- `SQLBot.spec` bundles `resources`, `llama_cpp` data/dynamic libs, PySide6 plugins, SQLAlchemy dialect imports, `pymysql`, `psycopg`, and all `sqlbot_desktop` submodules.
- `scripts/build_exe.bat` is a wrapper around the Python build script.

Driver approach:

- MySQL/MariaDB uses SQLAlchemy + PyMySQL.
- PostgreSQL uses SQLAlchemy + psycopg binary package.
- Qt SQL drivers are not the primary DB path for queries.

## Configuration

`config.yaml` currently defines self-correction defaults:

```yaml
self_correction:
  enabled: true
  max_retries: 3
  log_errors: true
  retry_delay_seconds: 0.0
  include_error_in_prompt: true
  stop_on_syntax_error: false
```

`AIModelConfig` carries runtime AI settings:

- backend (`local` or `api`);
- local model path;
- API endpoint/model/key;
- context size, max tokens, LLM worker threads, GPU layers;
- CPU affinity limit;
- self-correction retry limit.

## Key Architectural Constraints

- Do not execute generated SQL through any path that bypasses `QueryValidator` and `DatabaseManager.execute_select`.
- Do not store source database passwords in connection profiles.
- Keep schema enrichment writes in local metadata, not in source databases.
- Keep UI logic signal-driven; views render and emit, controllers orchestrate.
- Keep long AI/load/query operations off the UI thread through background tasks.
- Preserve PyInstaller resource compatibility when adding resources.
- Treat neural embeddings as optional; offline startup must still work.

## Extension Points

| Extension | Preferred place | Notes |
|---|---|---|
| Add a DB backend | `DatabaseManager`, profile form/dialog labels, build driver checks | Keep direct SQLAlchemy driver path and update packaging verification. |
| Add an AI backend | `AIBackend`, `AIModelConfig`, `AIEngine`, settings dialogs | Preserve `generate_prompt()` as the pipeline-facing interface. |
| Add prompt behavior | `PromptBuilder`, `TextToSqlPipeline` tests | Keep final generated output SELECT-only. |
| Add schema enrichment | `SchemaMetadataService`, `SchemaMetadataRepository`, schema tests | Store enrichment locally. |
| Add visual query feature | `VisualQueryBuilderPanel` and agent helper tests | Emit SQL through existing execute/copy/bookmark flow. |
| Add evaluation case | `docs/evaluation_dataset_sample.json`, `tests/test_evaluation.py` | Unit tests must not require a real LLM. |
| Add theme/i18n strings | `resources/ui`, `resources/i18n`, relevant view tests | Keep keys stable across language files. |

## Known Maintenance Notes

- Some user-facing strings in source may display mojibake in PowerShell output even when Python reads them; verify encoding with targeted grep or UTF-8-aware reads before bulk edits.
- `docs/project-graph.md`, this file, and `PROJECT_FEATURE_ID_CATALOG.md` should be refreshed after major architecture, module, or feature changes.
- Feature IDs in `PROJECT_FEATURE_ID_CATALOG.md` are documentation identifiers, not code constants.
