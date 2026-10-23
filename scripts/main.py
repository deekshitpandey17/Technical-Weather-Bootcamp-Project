"""Fetch current weather, enrich it with city demographics, and optionally load BigQuery."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any
import pandas as pd
import requests

KEY_PATH = Path("scripts/gcp-key.json")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
POPULATION_FILE = PROJECT_ROOT / "data" / "population.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "current_weather_stats.csv"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUIRED_COLUMNS = {"City", "Country", "Population", "Latitude", "Longitude"}
LOG = logging.getLogger("weather_pipeline")


def load_population(path: Path = POPULATION_FILE, limit: int = 50) -> pd.DataFrame:
    """Read and validate the assignment's city demographic dataset."""
    if not path.exists():
        raise FileNotFoundError(
            f"Population file not found: {path}. See the README for download/conversion steps."
        )
    population = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(population.columns)
    if missing:
        raise ValueError(f"population.csv is missing required columns: {sorted(missing)}")
    population = population.dropna(subset=["City", "Country", "Population", "Latitude", "Longitude"]).copy()
    population["Population"] = pd.to_numeric(population["Population"], errors="coerce")
    population["Latitude"] = pd.to_numeric(population["Latitude"], errors="coerce")
    population["Longitude"] = pd.to_numeric(population["Longitude"], errors="coerce")
    population = population.dropna(subset=["Population", "Latitude", "Longitude"])
    population["Population"] = population["Population"].astype("int64")
    population["City"] = population["City"].astype(str).str.strip()
    population["Country"] = population["Country"].astype(str).str.strip()
    if limit > 0:
        population = population.head(limit)
    if population.empty:
        raise ValueError("No valid population records found.")
    return population.reset_index(drop=True)


def fetch_weather(locations: pd.DataFrame, timeout: int = 30) -> pd.DataFrame:
    """Fetch current conditions in one Open-Meteo multi-location request."""
    params = {
        "latitude": ",".join(f"{value:.5f}" for value in locations["Latitude"]),
        "longitude": ",".join(f"{value:.5f}" for value in locations["Longitude"]),
        "current": "temperature_2m,wind_speed_10m",
        "timezone": "auto",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
    response.raise_for_status()
    payload: Any = response.json()
    records = payload if isinstance(payload, list) else [payload]
    if len(records) != len(locations):
        raise ValueError(
            f"Open-Meteo returned {len(records)} locations for {len(locations)} requested."
        )

    weather_rows = []
    for location, result in zip(locations.itertuples(index=False), records):
        current = result.get("current") or {}
        weather_rows.append(
            {
                "City": location.City,
                "Country": location.Country,
                "Latitude": location.Latitude,
                "Longitude": location.Longitude,
                "Temperature_C": current.get("temperature_2m"),
                "Wind_Speed_kmh": current.get("wind_speed_10m"),
                "Observation_Time": current.get("time"),
                "Temperature_Unit": (result.get("current_units") or {}).get("temperature_2m", "°C"),
                "Wind_Speed_Unit": (result.get("current_units") or {}).get("wind_speed_10m", "km/h"),
            }
        )
    return pd.DataFrame(weather_rows)


def build_dataset(population: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Merge on city and country, clean values, and add Fahrenheit/category fields."""
    merged = population.merge(weather, on=["City", "Country", "Latitude", "Longitude"], how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("Population and weather records did not match; check city names and coordinates.")
    merged["Population"] = pd.to_numeric(merged["Population"], errors="coerce").astype("Int64")
    merged["Temperature_C"] = pd.to_numeric(merged["Temperature_C"], errors="coerce").astype("float64")
    merged["Wind_Speed_kmh"] = pd.to_numeric(merged["Wind_Speed_kmh"], errors="coerce").astype("float64")
    merged["Temperature_F"] = merged["Temperature_C"] * 9 / 5 + 32
    merged["Temperature_Category"] = pd.cut(
        merged["Temperature_C"],
        bins=[float("-inf"), 10, 25, float("inf")],
        labels=["Cold", "Mild", "Hot"],
        right=False,
    ).astype("string")
    merged = merged.dropna(subset=["Population", "Temperature_C", "Wind_Speed_kmh", "Observation_Time"])
    merged["Population"] = merged["Population"].astype("int64")
    return merged.reset_index(drop=True)


def load_bigquery(dataset: pd.DataFrame, project_id: str | None = None) -> None:
    """Replace the configured BigQuery table with the current local snapshot."""
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError("BigQuery loading requires google-cloud-bigquery; install requirements.txt.") from exc

    project_id = project_id or os.getenv("GCP_PROJECT_ID")
    if not project_id:
        raise ValueError("Set GCP_PROJECT_ID or pass --project-id to load BigQuery.")
    dataset_id = os.getenv("BIGQUERY_DATASET", "global_weather_data")
    table_id = os.getenv("BIGQUERY_TABLE", "current_weather_stats")
    client = bigquery.Client(project=project_id)
    destination = f"{project_id}.{dataset_id}.{table_id}"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(dataset, destination, job_config=job_config)
    job.result()
    LOG.info("Loaded %s rows into %s", len(dataset), destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population-file", type=Path, default=POPULATION_FILE)
    parser.add_argument("--limit", type=int, default=50, help="Number of input cities; use 0 for all rows (default: 50).")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--load-bigquery", action="store_true", help="Replace the BigQuery table with this run's data.")
    parser.add_argument("--project-id", help="GCP project ID; defaults to GCP_PROJECT_ID environment variable.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")

    population = load_population(args.population_file, args.limit)
    LOG.info("Fetching weather for %d cities", len(population))
    weather = fetch_weather(population)
    dataset = build_dataset(population, weather)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False)
    print(dataset.to_string(index=False))
    print(f"\nSaved {len(dataset)} rows to {args.output}")
    if args.load_bigquery:
        load_bigquery(dataset, args.project_id)

if __name__ == "__main__":
    main()

