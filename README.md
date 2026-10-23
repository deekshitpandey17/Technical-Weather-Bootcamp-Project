# Technical-Weather-Bootcamp-Project
# Weather and Demographics Pipeline

Local implementation of the Technical Foundational Training Bootcamp assignment. It reads the provided city-demographics workbook, fetches current weather from Open-Meteo, joins and cleans the data with pandas, writes a local CSV snapshot, and can optionally replace a BigQuery table.

## Project layout

```text
weather_pipeline/
├── data/                 # local source and generated files; ignored by Git
├── scripts/main.py       # ingestion, cleaning, and optional BigQuery load
├── sql/                  # BigQuery exploration and view SQL
├── .env.example
├── .gitignore
└── requirements.txt
```

## Prepare the input data

The assignment links to [its demographic dataset repository](https://github.com/yashhh0001/Training_Bootcamp_Assignment_Resources). The provided workbook has 70 city records and columns `City`, `Country`, `Population`, `Latitude`, and `Longitude`. Keep the source workbook local in `data/` and export its `Countries` sheet as `data/population.csv` using those same column names. The assignment's `.gitignore` requirement excludes local data files from Git.

The workbook contains large cities, not 70 national capitals, and some coordinates/population values are supplied as-is. The script uses the first 50 valid rows by default to meet the assignment's 50-location target. Use `--limit 0` to process every source row. For a capital-only analysis, replace the CSV with a reviewed capital-city dataset using the same schema.

## Run locally

From this directory, create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/main.py --verbose
```

The script prints the merged rows and writes `data/current_weather_stats.csv`. It calls Open-Meteo's forecast endpoint with current temperature and wind-speed fields for the selected coordinates. The result includes city/country, coordinates, population, current observation time, Celsius/Fahrenheit, wind speed, and a temperature category (`Cold` < 10°C, `Mild` 10–24.99°C, `Hot` ≥ 25°C).

## Optional BigQuery load

1. In your personal Google Cloud account, create/select a project, enable BigQuery, and create dataset `global_weather_data` in the same location you will use for the table and Looker Studio.
2. Create a service account with the permissions required by your organization, download a JSON key to `scripts/gcp-key.json`, and keep it private. That filename is ignored by Git.
3. Install the requirements and set the environment variables (never commit a credential file):

   ```bash
   # Linux/macOS
   export GOOGLE_APPLICATION_CREDENTIALS="scripts/gcp-key.json"
   export GCP_PROJECT_ID="your-project-id"
   # Windows PowerShell
   $env:GOOGLE_APPLICATION_CREDENTIALS = "scripts/gcp-key.json"
   $env:GCP_PROJECT_ID = "your-project-id"
   ```

4. Run `python scripts/main.py --load-bigquery`. The load uses `WRITE_TRUNCATE` so the table is a fresh current-weather snapshot on each run. Dataset and table can be overridden with `BIGQUERY_DATASET` and `BIGQUERY_TABLE`.
5. Replace `YOUR_GCP_PROJECT_ID` in `sql/explore.sql` and `sql/create_views.sql`, run the exploration query, then create the `vw_hottest_large_countries` view.

The view treats the workbook's city population values as the available population measure. Its 10-million threshold is the sum of included city populations per country, not an independently sourced national population total. The view summarizes countries, so connect Looker Studio using `Country` as the geographic dimension and `Avg_Temperature_C` as the color metric; use `Temperature_Category` for the drop-down filter.

## Git workflow and submissions

```bash
git init
git add .gitignore README.md requirements.txt scripts sql .env.example
git commit -m "Create weather pipeline project structure"
git checkout -b feature/data-ingestion
# make the implementation commits required by the assignment
git status --ignored
```

Keep `data/`, `.env`, virtual environments, Python cache, and `scripts/gcp-key.json` out of commits. The final assignment submissions also require a GitHub pull request link and a shared Looker Studio dashboard link; those account-specific publishing actions must be completed in your own GitHub and Google Cloud accounts.


