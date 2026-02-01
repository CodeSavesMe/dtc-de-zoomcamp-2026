-- 3. Count trips with distance <= 1 mile in November 2025
WITH november_trips AS (
    SELECT 	trip_distance
    FROM 	green_tripdata_2025_11
    WHERE 	lpep_pickup_datetime >= '2025-11-01'
      AND 	lpep_pickup_datetime < '2025-12-01'
)
SELECT 	COUNT(*) AS short_trip_count
FROM 	november_trips
WHERE 	trip_distance <= 1;


-- 4. Pickup day with the longest trip distance (distance < 100 miles)
WITH valid_trips AS (
    SELECT
        	lpep_pickup_datetime,
        	trip_distance
    FROM 	green_tripdata_2025_11
    WHERE 	trip_distance < 100
      AND 	lpep_pickup_datetime >= '2025-11-01'
      AND 	lpep_pickup_datetime < '2025-12-01'
)
SELECT 		DATE(lpep_pickup_datetime) AS pickup_day
FROM 		valid_trips
ORDER BY 	trip_distance DESC;


-- 5. Pickup zone with largest total_amount on 2025-11-18
WITH trips_nov_18 AS (
    SELECT
        	"PULocationID",
        	total_amount
    FROM 	green_tripdata_2025_11
    WHERE 	DATE(lpep_pickup_datetime) = '2025-11-18'
),
zone_revenue AS (
    SELECT
        		"PULocationID",
        		SUM(total_amount) AS total_revenue
    FROM 		trips_nov_18
    GROUP BY 	"PULocationID"
)
SELECT 		z."Zone" AS pickup_zone
FROM 		zone_revenue zr
JOIN 		taxi_zone_lookup z
  ON 		zr."PULocationID" = z."LocationID"
ORDER BY 	zr.total_revenue DESC;


-- 6. Drop off zone with the largest single tip from "East Harlem North"
WITH east_harlem_pickups AS (
    SELECT
        	t."DOLocationID",
        	t.tip_amount
    FROM 	green_tripdata_2025_11 t
    JOIN 	taxi_zone_lookup z
      ON 	t."PULocationID" = z."LocationID"
    WHERE 	z."Zone" = 'East Harlem North'
      AND 	t.lpep_pickup_datetime >= '2025-11-01'
      AND 	t.lpep_pickup_datetime < '2025-12-01'
)
SELECT 		z."Zone" AS dropoff_zone
FROM 		east_harlem_pickups eh
JOIN 		taxi_zone_lookup z
  ON 		eh."DOLocationID" = z."LocationID"
ORDER BY 	eh.tip_amount DESC;