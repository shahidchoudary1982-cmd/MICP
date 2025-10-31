# MICP Data Manager

This project provides a lightweight web application for loading Microbial Induced Calcite Precipitation (MICP) well data from Excel workbooks, storing the results in a SQL database, and exploring the data through interactive tables and charts.

## Features

- Upload Excel workbooks with multiple sheets; every sheet is ingested.
- Create a named project for each upload and track sheets and records in a SQLite database.
- Persist key well attributes (Company, Field, Well Name, Formation) plus the full original row as JSON for flexible reuse.
- Browse data in a searchable table with sheet and row filters.
- View six different charts showing counts by company, field, formation, sheet, and well distribution statistics.
- Download project metadata through JSON APIs for integration or future extensions.

## Getting started

1. **Install dependencies**

   ```bash
   pip install -e .
   ```

2. **Run the application**

   ```bash
   uvicorn main:app --reload --app-dir app
   ```

   The site becomes available at http://127.0.0.1:8000.

3. **Upload data**

   - Open the web UI.
   - Provide a project name, optional description, and choose an Excel workbook.
   - After the upload, data will be saved to `app/data/app.db`.

## Project layout

```
app/
├── crud.py          # Database helpers
├── database.py      # SQLAlchemy engine and session utilities
├── excel_loader.py  # Helpers to normalize Excel sheets
├── main.py          # FastAPI entry point
├── models.py        # ORM models
├── schemas.py       # Pydantic response models
├── static/          # Front-end assets
│   ├── app.js
│   └── styles.css
└── templates/
    └── index.html
```

## Tests

Tests can be added under a `tests/` directory and run with `pytest` after installing the optional development dependencies:

```bash
pip install -e .[dev]
pytest
```

## Database notes

- The default database is SQLite and lives in `app/data/app.db`.
- On startup the app will create all required tables.
- The models use SQLAlchemy 2.x style type annotations.

## License

This project is provided as-is without any warranty.

