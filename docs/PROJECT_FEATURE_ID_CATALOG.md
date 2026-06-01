# SQLBot Project Feature ID Catalog

Last scanned: 2026-06-01

Feature IDs are stable documentation identifiers for planning, test mapping, and future prompts. They are not code constants.

Status values:

- `Implemented`: code and tests or runtime surface exist.
- `Partial`: code exists but coverage, integration, or UX is incomplete.
- `Support`: internal/supporting capability rather than a direct user feature.

## AUTH - Login, Admin Password, Security

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-AUTH-001 | Login window | Implemented | Select a database profile and enter credentials before opening the workspace. | `LoginWindow`, `LoginController` | README Module 1; MVC smoke tests in history |
| SQLBOT-AUTH-002 | Password-gated connection management | Implemented | Prevent casual edits to shared connection profiles. | `AdminPasswordDialog`, `AdminPasswordStore`, `ConnectionManagerDialog` | `tests/test_i18n.py`, dialog/controller coverage by smoke tests |
| SQLBOT-AUTH-003 | Change admin password | Implemented | Rotate the connection-management password from the UI. | `ChangeAdminPasswordDialog`, `AdminPasswordStore` | README Module 1 |
| SQLBOT-AUTH-004 | No stored database passwords in profiles | Implemented | Keep source DB credentials out of `data/connections.json`. | `ConnectionProfile`, `ProfileRepository`, connection dialogs | README Module 1; profile model lacks password field |

## CONN - Connection Profiles, Drivers, Schema Extraction

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-CONN-001 | MySQL/MariaDB profiles | Implemented | Connect to MySQL/MariaDB through bundled Python drivers. | `DatabaseManager`, `ConnectionFormDialog`, `ProfileRepository` | `scripts/check_sql_drivers.py`, build verification scripts |
| SQLBOT-CONN-002 | PostgreSQL profiles | Implemented | Connect to PostgreSQL without requiring separate client installs. | `DatabaseManager`, `SQLBot.spec`, `post_build_sql_drivers.py` | `verify_packaged_drivers.py` |
| SQLBOT-CONN-003 | Add/edit/delete/test profiles | Implemented | Manage connection profiles in-app. | `ConnectionManagerDialog`, `ConnectionFormDialog`, `ProfileRepository` | README Module 1 |
| SQLBOT-CONN-004 | Connect and get schema | Implemented | Inspect schema immediately after a connection test. | `ConnectionFormDialog`, `SchemaExtractor`, `SchemaAnnotationDialog` | `tests/test_schema_relationships.py`, schema tests |
| SQLBOT-CONN-005 | Schema extraction and profiling | Implemented | Discover tables, columns, foreign keys, samples, and enum-like values. | `SchemaExtractor`, `TableInfo`, `ColumnInfo` | `tests/test_schema_profiling.py`, `tests/test_schema_relationships.py` |

## UI - Main Window, Theme, I18n, Visual Builder

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-UI-001 | Main workspace layout | Implemented | Work in one screen for prompt, SQL editor, results, schema, and settings. | `MainWindow`, `MainController` | `tests/test_main_window_busy.py`, `tests/test_main_controller_pipeline.py` |
| SQLBOT-UI-002 | Busy/progress and stop controls | Implemented | Stop long-running AI work and see progress feedback. | `MainWindow.set_busy`, `MainController.cancel_task` | `tests/test_main_window_busy.py`, `tests/test_ai_engine.py` |
| SQLBOT-UI-003 | Shared QSS themes | Implemented | Consistent light/dark UI styling. | `views.theme`, `resources/ui/styles/*.qss` | `tests/test_theme.py` |
| SQLBOT-UI-004 | Localization resources | Implemented | Switch UI strings across configured languages. | `I18nManager`, `resources/i18n/{vi,en,jp}` | `tests/test_i18n.py` |
| SQLBOT-UI-005 | Schema viewer dock | Implemented | Browse loaded schema in the workspace. | `SchemaTreeWidget`, `MainWindow.show_schema_viewer` | `tests/test_schema_markdown_formatter.py`, schema viewer smoke coverage |
| SQLBOT-UI-006 | Visual Query Builder | Implemented | Build SELECT queries manually with table/column/filter controls. | `VisualQueryBuilderPanel`, visual builder row widgets | `tests/test_visual_query_builder.py` |
| SQLBOT-UI-007 | Query builder guide | Implemented | Explain operators, filters, group/order/limit features. | `QueryBuilderGuideDialog`, i18n guide resources | `resources/i18n/*/guide.strings.xml` |

## AI - AI Settings, Load/Unload, Local/API Generation

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-AI-001 | Local GGUF backend | Implemented | Load a local `.gguf` model for offline text-to-SQL. | `AIEngine._load_local`, `AISettingsDialog`, `MainWindow` | `tests/test_ai_engine.py`, README Module 2.2 |
| SQLBOT-AI-002 | API AI backend | Implemented | Use an OpenAI-compatible endpoint and model. | `AIEngine._generate_api`, `AISettingsRepository`, settings dialogs | README Module 2.2 |
| SQLBOT-AI-003 | Load/unload lifecycle | Implemented | Release model resources manually or on app close. | `AIEngine.load`, `AIEngine.unload`, `MainController.load_model` | `tests/test_ai_engine.py` |
| SQLBOT-AI-004 | CPU-only laptop defaults | Implemented | Safer defaults for i5 laptop, 16GB RAM, no discrete GPU. | `AIModelConfig`, `CpuLimiter`, `AISettingsDialog` | `tests/test_cpu_limiter.py`, `tests/test_ai_settings_dialog.py` |
| SQLBOT-AI-005 | Persisted AI settings | Implemented | Save backend/model/token/thread/retry settings locally. | `AISettingsRepository`, `AIModelConfig` | `tests/test_ai_settings_dialog.py`, `tests/test_app_config.py` |

## T2SQL - Prompting, Schema Linking, Pipeline, Self-Correction

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-T2SQL-001 | English system prompt with Vietnamese reply instruction | Implemented | Better LLM guidance while preserving Vietnamese user-facing responses. | `PromptBuilder.system_prompt` | `tests/test_prompt_builder.py` |
| SQLBOT-T2SQL-002 | Internal SQL skeleton prompting | Implemented | Improve SQL shape without exposing placeholders to users. | `PromptBuilder.SKELETON_INSTRUCTION` | `tests/test_prompt_builder.py` |
| SQLBOT-T2SQL-003 | Few-shot examples | Implemented | Provide syntax references for common SELECT patterns. | `PromptBuilder`, `FewShotRepository`, `ExampleStore` | `tests/test_few_shot_repository.py`, `tests/test_example_store.py` |
| SQLBOT-T2SQL-004 | Neural schema linking with fallback | Implemented | Prefer relevant schema columns while still working offline. | `SchemaLinker`, `SentenceTransformersEmbeddingModel`, `DeterministicEmbeddingModel` | `tests/test_schema_linker.py`, `tests/test_embedding_service.py` |
| SQLBOT-T2SQL-005 | Text-to-SQL pipeline | Implemented | Convert natural language to validated SQL candidates. | `TextToSqlPipeline`, `AIEngine`, `SQLExtractor` | `tests/test_text_to_sql_pipeline.py` |
| SQLBOT-T2SQL-006 | Self-correction loop | Implemented | Retry generated SQL using execution errors. | `TextToSqlPipeline`, `PromptBuilder._error_block`, `config.yaml` | `tests/test_text_to_sql_pipeline.py`, `docs/SELF_CORRECTION.md` |
| SQLBOT-T2SQL-007 | Query attempt logging | Implemented | Debug self-correction attempts without credentials. | `QueryLogger`, `QueryAttempt`, `logs/queries` | `tests/test_query_logger.py` |
| SQLBOT-T2SQL-008 | Advanced SQL Agent | Implemented | Structured JSON intent path for joins, grouping, filters, set ops, and correction. | `AdvancedSQLAgent`, `Orchestrator`, `agents/*` | `tests/test_advanced_sql_agent.py`, `tests/test_orchestrator.py`, handler tests |

## SCHEMA - Metadata, Sample Values, Annotations, Viewer

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-SCHEMA-001 | Local schema metadata repository | Implemented | Store enriched schema outside source DB. | `SchemaMetadataRepository`, `ColumnMetadata` | `tests/test_schema_metadata_repository.py` |
| SQLBOT-SCHEMA-002 | Metadata import service | Implemented | Convert extracted schema to searchable metadata. | `SchemaMetadataService.import_tables` | `tests/test_schema_metadata_service.py` |
| SQLBOT-SCHEMA-003 | Sample value refresh | Implemented | Add useful examples for prompts while preserving source DB. | `SchemaMetadataService.refresh_sample_values` | `tests/test_schema_metadata_service.py`, README Module 2.3 |
| SQLBOT-SCHEMA-004 | Sensitive sample redaction | Implemented | Avoid prompt leakage of passwords/tokens/email/phone-like columns. | `SchemaMetadataService.SENSITIVE_MARKERS` | `tests/test_schema_metadata_service.py` |
| SQLBOT-SCHEMA-005 | Business annotations | Implemented | Add user-friendly table/column descriptions. | `AnnotationRepository`, `SchemaAnnotationWidget`, `SchemaAnnotationDialog` | README Module 1 |
| SQLBOT-SCHEMA-006 | Markdown schema context | Implemented | Compact LLM schema context with descriptions and samples. | `SchemaMarkdownFormatter`, `PromptBuilder.build_schema_context` | `tests/test_schema_markdown_formatter.py`, `tests/test_prompt_builder.py` |
| SQLBOT-SCHEMA-007 | Schema graph for joins | Implemented | Plan join paths from foreign keys and fallback conventions. | `SchemaGraph`, `JoinPlanner` | `tests/test_schema_graph.py`, `tests/test_join_planner.py` |

## QUERY - SQL Safety, Execution, Results, CSV

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-QUERY-001 | SELECT-only validation | Implemented | Prevent destructive SQL execution. | `QueryValidator` | `tests/test_query_validator.py` |
| SQLBOT-QUERY-002 | SQL extraction from LLM output | Implemented | Pull safe SELECTs from markdown/plain model responses. | `SQLExtractor` | `tests/test_sql_extractor.py` |
| SQLBOT-QUERY-003 | Query correction against known schema | Implemented | Fix common table/column naming mismatches. | `QueryCorrector` | `tests/test_query_corrector.py` |
| SQLBOT-QUERY-004 | Execute SELECT with row cap | Implemented | Run queries and return columns/rows/elapsed status. | `DatabaseManager.execute_select` | `tests/test_query_validator.py` |
| SQLBOT-QUERY-005 | Query Results dialog | Implemented | Inspect generated query output in a separate dialog. | `QueryResultsDialog`, `MainWindow.set_query_results` | README Module 2.1 |
| SQLBOT-QUERY-006 | CSV export | Implemented | Export visible query results. | `QueryResultsDialog.export_csv`, `MainWindow.export_results_csv` | README Module 2.1 |

## HIST - History, Bookmarks, Activity

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-HIST-001 | Generation history | Implemented | Keep recent generated attempts and reload questions. | `ActivityRepository`, `HistoryDialog` | `tests/test_activity_repository.py`, README Module 2.4 |
| SQLBOT-HIST-002 | Date-filtered history | Implemented | Narrow history by date. | `HistoryDialog`, `ActivityRepository.list_history` | README Module 2.4 |
| SQLBOT-HIST-003 | Bookmarks | Implemented | Save reusable question/SQL/category/notes. | `AddBookmarkDialog`, `BookmarksDialog`, `ActivityRepository` | `tests/test_activity_repository.py` |
| SQLBOT-HIST-004 | Bookmark delete confirmation | Implemented | Avoid accidental bookmark removal. | `BookmarksDialog` | README Module 2.4 |

## EVAL - Evaluation Dataset, Scripts, Metrics

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-EVAL-001 | Evaluation dataset loader | Implemented | Load JSON/CSV test cases. | `EvaluationDatasetLoader` | `tests/test_evaluation.py` |
| SQLBOT-EVAL-002 | Text-to-SQL evaluator | Implemented | Compute exact match, valid SELECT, execution success, hallucination metrics. | `TextToSqlEvaluator`, `EvaluationReport` | `tests/test_evaluation.py` |
| SQLBOT-EVAL-003 | Failure analyzer | Implemented | Classify common schema/syntax/execution failures. | `FailureAnalyzer` | `tests/test_evaluation.py` |
| SQLBOT-EVAL-004 | Sample evaluation dataset | Implemented | Provide baseline coverage for select/filter/join/aggregate/order/date. | `docs/evaluation_dataset_sample.json` | `tests/test_evaluation.py` |
| SQLBOT-EVAL-005 | CLI evaluation script | Implemented | Run evaluation from PowerShell/CI. | `scripts/evaluate_text_to_sql.py` | `python scripts\\evaluate_text_to_sql.py ...` |

## BUILD - Packaging, Drivers, Runtime Resources

| ID | Name | Status | User value | Primary code surfaces | Tests / evidence |
|---|---|---|---|---|---|
| SQLBOT-BUILD-001 | PyInstaller build | Implemented | Produce `dist/SQLBot/SQLBot.exe`. | `scripts/build_app.py`, `SQLBot.spec` | build script output; README build section |
| SQLBOT-BUILD-002 | PySide6 resource packaging | Implemented | Ensure QSS/icons/i18n and Qt plugins load in EXE. | `SQLBot.spec`, `runtime.configure_qt_plugin_paths`, `views.theme` | `tests/test_theme.py` |
| SQLBOT-BUILD-003 | MySQL/PostgreSQL driver verification | Implemented | Verify packaged direct DB drivers. | `check_sql_drivers.py`, `post_build_sql_drivers.py`, `verify_packaged_drivers.py` | README build section |
| SQLBOT-BUILD-004 | Local GGUF dependency packaging | Implemented | Include `llama_cpp` data/dynamic libs in the bundle. | `SQLBot.spec`, `requirements.txt` | `SQLBot.spec` hidden imports/binaries |
| SQLBOT-BUILD-005 | Portable DB install helper | Implemented | Install only DB connectivity dependencies during setup. | `scripts/install_db_drivers.bat`, `requirements-db.txt` | README run section |

## Cross-Feature Acceptance Map

| Acceptance check | Feature IDs |
|---|---|
| `python -m unittest discover -s tests` | All tested feature areas |
| `python -m compileall src tests scripts` | BUILD, UI, AI, T2SQL, SCHEMA, QUERY |
| `python scripts\\evaluate_text_to_sql.py docs\\evaluation_dataset_sample.json --format json` | EVAL, T2SQL, QUERY |
| `python scripts\\build_app.py` | BUILD, AI, CONN, UI resources |
| Manual: login, connect, load AI, generate, execute SELECT, export CSV | AUTH, CONN, AI, T2SQL, QUERY, UI |
| Manual: schema viewer/annotation/sample refresh | CONN, SCHEMA, UI |
| Manual: history/bookmark reload/delete | HIST, UI |
