-- Confirm the loaded schema and inspect a small sample.
SELECT *
FROM `YOUR_GCP_PROJECT_ID.global_weather_data.current_weather_stats`
ORDER BY Country, City
LIMIT 10;

