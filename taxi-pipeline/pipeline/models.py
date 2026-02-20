"""
NYC Taxi Analytics Pipeline
============================

Joins taxi trips with zone metadata, then computes pickup location
statistics including average trip distance.
"""

import bauplan

@bauplan.model()
@bauplan.python('3.10', pip={'duckdb': '1.2.0'})
def ny_taxi_trips_and_zones(
    zones=bauplan.Model(
        'taxi_zones',
    ),
    trips=bauplan.Model(
        'taxi_trips_2021',
        columns=[
            'pickup_datetime',
            'dropoff_datetime',
            'PULocationID',
            'DOLocationID',
            'trip_miles',
        ],
        filter="pickup_datetime >= '2021-02-01' AND pickup_datetime < '2021-02-15'",
    ),
):
    """
    Joins NYC taxi trip records with zone metadata using DuckDB.

    | pickup_datetime     | PULocationID | trip_miles | Borough   | Zone         |
    |---------------------|--------------|------------|-----------|--------------|
    | 2021-02-01 08:15:00 | 132          | 5.2        | Manhattan | Midtown East |
    """
    import duckdb

    joined_table = duckdb.sql("""
        SELECT
            trips.* EXCLUDE (trip_miles),
            CAST(trips.trip_miles AS DOUBLE) AS trip_miles,
            zones.*  EXCLUDE (LocationID)
        FROM trips
        JOIN zones ON trips.PULocationID = zones.LocationID
    """).arrow()

    size_in_gb = joined_table.nbytes / (1024 ** 3)
    print(f'\n number of rows {joined_table.num_rows}\n')
    print(f'\n size in GB {size_in_gb} \n')

    return joined_table

@bauplan.expectation()
@bauplan.python('3.10', pip={'pyarrow': '17.0.0'})
def check_trip_miles_is_numeric(
    data=bauplan.Model(
        'ny_taxi_trips_and_zones',
        columns=['trip_miles'],
    ),
):
    """Verify trip_miles is a floating-point type, not string."""
    import pyarrow as pa

    return pa.types.is_floating(data.schema.field('trip_miles').type)


@bauplan.model(materialization_strategy='REPLACE')
@bauplan.python('3.11', pip={'pandas': '2.2.0'})
def top_pickup_locations_demo(data=bauplan.Model('ny_taxi_trips_and_zones')):
    """
    Computes the most popular NYC taxi pickup locations by trip count
    and average trip distance.

    | PULocationID | Borough   | Zone         | number_of_trips | avg_trip_distance |
    |--------------|-----------|--------------|-----------------|-------------------|
    | 132          | Manhattan | Midtown East | 48210           | 4.3               |
    """
    import pandas as pd

    df = data.to_pandas()

    top_pickup_table = (
        df
        .groupby(['PULocationID', 'Borough', 'Zone'])
        .agg(
            number_of_trips=('pickup_datetime', 'count'),
            avg_trip_distance=('trip_miles', 'mean'),  # ← fails if trip_miles is string
        )
        .reset_index()
        .sort_values(by='number_of_trips', ascending=False)
    )

    return top_pickup_table
