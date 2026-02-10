--## Module 2 Homework

--1) Within the execution for `Yellow` Taxi data for the year `2020` and month `12`: what is the uncompressed file size (i.e. the output file `yellow_tripdata_2020-12.csv` of the `extract` task)?
--❯ curl -L -o yellow_tripdata_2020-12.csv.gz \
--  https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/yellow_tripdata_2020-12.csv.gz
--
--  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
--                                 Dload  Upload   Total   Spent    Left  Speed
--  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
--100 25.2M  100 25.2M    0     0  4510k      0  0:00:05  0:00:05 --:--:-- 5569k
--❯ gzip -dc yellow_tripdata_2020-12.csv.gz | wc -c
--
-- 134481400 bytes
-- 128.25145721435547 MiB




--2) What is the rendered value of the variable `file` when the inputs `taxi` is set to `green`, `year` is set to `2020`, and `month` is set to `04` during execution?
2026-01-30 02:04:11.5612026-01-29 19:04:11 | INFO | URL      : https://github.com/DataTalksClub/nyc-tlc-data/releases/download/green/green_tripdata_2020-04.csv.gz
--- `green_tripdata_2020-04.csv`


--3) How many rows are there for the `Yellow` Taxi data for all CSV files in the year 2020?

SELECT SUM(cnt)::bigint AS total_rows
FROM (
  SELECT COUNT(*) AS cnt FROM public.yellow_tripdata_2020_01
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_02
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_03
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_04
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_05
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_06
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_07
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_08
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_09
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_10
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_11
  UNION ALL SELECT COUNT(*) FROM public.yellow_tripdata_2020_12
) t;

-- ANSWER
-- total_rows
--------------
--   24648499
--- 24,648,499


--4) How many rows are there for the `Green` Taxi data for all CSV files in the year 2020?
FROM (
  SELECT COUNT(*) AS cnt FROM public.green_tripdata_2020_01
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_02
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_03
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_04
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_05
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_06
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_07
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_08
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_09
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_10
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_11
  UNION ALL SELECT COUNT(*) FROM public.green_tripdata_2020_12
) t;

-- ANSWER
-- total_rows
--------------
--    1734051
--(1 row)



--5) How many rows are there for the `Yellow` Taxi data for the March 2021 CSV file?
SELECT COUNT(*)::bigint AS rows
FROM public.yellow_tripdata_2021_03;

-- ANSWER
--  rows
-----------
-- 1925152

--6) How would you configure the timezone to New York in a Schedule trigger?
--- Add a `timezone` property set to `America/New_York` in the `Schedule` trigger configuration

