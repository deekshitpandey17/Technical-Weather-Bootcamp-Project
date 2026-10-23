-- City population is the population measure supplied in the assignment workbook.
-- The threshold below therefore applies to the sum of included city populations
-- for each country (not a separate national population statistic).
CREATE OR REPLACE VIEW `YOUR_GCP_PROJECT_ID.global_weather_data.vw_hottest_large_countries` AS
SELECT
  Country,
  SUM(Population) AS Population_Included_Cities,
  ROUND(AVG(Temperature_C), 2) AS Avg_Temperature_C,
  ROUND(MAX(Temperature_C), 2) AS Max_Temperature_C,
  ROUND(AVG(Wind_Speed_kmh), 2) AS Avg_Wind_Speed_kmh,
  COUNT(*) AS City_Count,
  CASE
    WHEN AVG(Temperature_C) < 10 THEN 'Cold'
    WHEN AVG(Temperature_C) < 25 THEN 'Mild'
    ELSE 'Hot'
  END AS Temperature_Category
FROM `YOUR_GCP_PROJECT_ID.global_weather_data.current_weather_stats`
GROUP BY Country
HAVING SUM(Population) > 10000000
QUALIFY ROW_NUMBER() OVER (ORDER BY AVG(Temperature_C) DESC, Country) <= 5;

