# SQLBot Desktop

SQLBot Desktop is a Windows desktop application for converting Vietnamese natural-language questions into safe SQL queries using local AI models.

## Current Scope

The first implemented screen is the modern login UI:

- Select a saved database connection profile.
- Enter SQL username and password.
- Open the future connection-management flow.
- Reuse shared QSS styles and SVG icons from `resources/ui`.
- Open the Module 2.1 main workspace after a successful connection.

## Source Structure

`src/sqlbot_desktop/` follows a small MVC layout:

```text
src/sqlbot_desktop/
├── main.py                  # QApplication bootstrap
├── models/                  # Dataclasses and domain objects
│   └── entities.py
├── views/                   # PySide6 windows, dialogs, and view assets
│   ├── login_window.py
│   ├── assets.py
│   ├── theme.py
│   └── dialogs/
├── controllers/             # UI flow orchestration
│   └── login_controller.py
└── infrastructure/          # SQLAlchemy connections, JSON stores, schema extraction, security storage
```

Views should emit signals and render state. Controllers coordinate workflows. Infrastructure handles external systems and file/database access.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SQLBOT_ADMIN_PASSWORD="your-local-admin-password"
python run.py
```

To install only database connectivity dependencies:

```powershell
.\scripts\install_db_drivers.bat
```

Check available drivers:

```powershell
python scripts\check_sql_drivers.py
```

Build Windows EXE:

```powershell
python scripts\build_app.py
```

The legacy batch wrapper `.\scripts\build_exe.bat` calls the same Python build script.

Local GGUF support is handled by a bundled C# sidecar built with LLamaSharp. The build machine needs the .NET 8 SDK to publish `SQLBot.LlmHost.exe`; end users do not need .NET installed because the sidecar is published self-contained.

```powershell
python scripts\build_app.py
```

The PyInstaller spec bundles direct Python DB packages for MySQL and PostgreSQL: `sqlalchemy`, `pymysql`, `psycopg`, and the PostgreSQL `libpq` runtime from `psycopg-binary`.

After PyInstaller finishes, `scripts\post_build_sql_drivers.py` copies the `LIBPQ.dll` alias needed by PostgreSQL, and `scripts\verify_packaged_drivers.py` verifies that the EXE folder contains the expected portable MySQL/PostgreSQL drivers.

Connection profiles are loaded from `data/connections.json` when available. If the file does not exist, create a MySQL or PostgreSQL profile from Connection Management.

## Module 1

The login and connection-management module now includes:

- Password-gated connection administration via `SQLBOT_ADMIN_PASSWORD`.
- Change the connection-management password from the manager dialog.
- Add, edit, delete, and test connection profiles.
- Support for MySQL/MariaDB and PostgreSQL connection profiles.
- `Connect & Get Schema` to open the schema annotation editor.
- Annotation import/export/save to `data/annotations/*.annotations.json`.

Database passwords are intentionally not stored in `connections.json`.
If no admin password is configured, the first access to connection management asks you to create one. SQLBot stores only a salted hash at `data/security/admin_password.json`.

Driver note: MySQL uses bundled PyMySQL and PostgreSQL uses bundled psycopg binary, so end users do not need to install MySQL/PostgreSQL client libraries separately.

## Module 2.1

The main workspace layout includes:

- Menu bar and visible connection status.
- Vietnamese natural-language question input.
- Action buttons for generate, copy, execute, and bookmark.
- Suggested SQL query list beside the question input.
- Settings icon/menu for History, Bookmarks, Schema, and Settings.
- Query Results renders executed SELECT data and can export CSV.

## Module 2.2

Text-to-SQL generation now supports two AI backends:

- Local GGUF: choose `Local GGUF`, click `Browse GGUF`, select a `.gguf` file, then `Load`.
- API AI: choose `API AI`, enter an OpenAI-compatible chat completions endpoint and model, set `SQLBOT_AI_API_KEY`, then `Load`.

Use `Unload` to release the active AI backend. Closing the application asks for confirmation and unloads the model.

Long-running AI load/generate operations run in a background worker and show an indeterminate progress view.

## Module 2.4

History and Bookmarks are stored locally in `data/sqlbot_activity.sqlite`.

- History keeps the latest 100 generated attempts and supports date filtering.
- Double-click a history row to reload the question.
- Bookmarks store question, SQL, category, and notes.
- Double-click a bookmark to reload the saved question and SQL.
- Deleting a bookmark requires confirmation.

## Module 3.1

`Settings` opens the AI Settings dialog:

- Local GGUF scans `models/` and `AI Models/` for `.gguf` files.
- Browse GGUF can select a model from any folder.
- Model info shows file size and detected quantization from the filename.
- Resource info shows CPU cores and Windows RAM estimate.
- API AI shows only endpoint/model inputs.
- Local GGUF and API AI settings are mutually hidden based on the selected backend.
- Saving settings does not load a model; use `Load` in the main workspace.
