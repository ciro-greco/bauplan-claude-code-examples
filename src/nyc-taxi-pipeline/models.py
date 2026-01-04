import bauplan
from typing import Any


@bauplan.model(
    columns=['PULocationID', 'DOLocationID', 'Zone', 'Borough', 'total_fare_amount']
)
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def trips_with_zones(
    trips=bauplan.Model(
        'taxi_fhvhv',
        columns=[
            'pickup_datetime', 
            'PULocationID', 
            'DOLocationID',
            'base_passenger_fare',
            'tolls',
            'bcf',
            'sales_tax',
            'congestion_surcharge',
            'airport_fee',
            'tips'
        ],
        filter="pickup_datetime >= '2023-01-01' AND base_passenger_fare > 0"
    ),
    zones=bauplan.Model(
        'taxi_zones',
        columns=['LocationID', 'Borough', 'Zone']
    )
) -> Any:
    """
    Reads taxi trip data, calculates total fare, and enriches with zone information.
    Filters to 2023+ data with positive base fares.
    
    | PULocationID | DOLocationID | Zone               | Borough   | total_fare_amount |
    |--------------|--------------|-------------------|-----------|-------------------|
    | 236          | 142          | Upper East Side   | Manhattan | 19.9              |
    | 142          | 249          | Lincoln Square    | Manhattan | 40.66             |
    """
    import polars as pl
    
    # Convert Arrow tables to Polars DataFrames
    df_trips = pl.from_arrow(trips)
    df_zones = pl.from_arrow(zones)
    
    # Calculate total fare amount
    df_trips = df_trips.with_columns(
        (
            pl.col('base_passenger_fare') + 
            pl.col('tolls') + 
            pl.col('bcf') + 
            pl.col('sales_tax') + 
            pl.col('congestion_surcharge') + 
            pl.col('airport_fee') + 
            pl.col('tips')
        ).alias('total_fare_amount')
    )
    
    # Join trips with pickup location zones
    df = df_trips.join(
        df_zones,
        left_on='PULocationID',
        right_on='LocationID',
        how='left'
    )
    
    # Select final columns
    df = df.select([
        pl.col('PULocationID'),
        pl.col('DOLocationID'),
        pl.col('Zone'),
        pl.col('Borough'),
        pl.col('total_fare_amount')
    ])
    
    return df.to_arrow()


@bauplan.model(
    columns=['PULocationID', 'Zone', 'Borough', 'total_trips', 'total_fare_amount', 'avg_fare_amount'],
    materialization_strategy='REPLACE'  # Materialize this as final output
)
@bauplan.python('3.11', pip={'polars': '1.15.0'})
def top_locations_by_fare(
    data=bauplan.Model(
        'trips_with_zones',
        columns=['PULocationID', 'Zone', 'Borough', 'total_fare_amount']
    )
) -> Any:
    """
    Aggregates taxi trips by pickup location and calculates total fare amounts.
    Returns top 100 locations sorted by total fare revenue.
    
    | PULocationID | Zone               | Borough   | total_trips | total_fare_amount | avg_fare_amount |
    |--------------|-------------------|-----------|-------------|-------------------|-----------------|
    | 132          | JFK Airport       | Queens    | 45234       | 2850456.23       | 63.02          |
    | 138          | LaGuardia Airport | Queens    | 38912       | 1892345.67       | 48.65          |
    | 236          | Upper East Side   | Manhattan | 125678      | 1756432.89       | 13.98          |
    """
    import polars as pl
    
    df = pl.from_arrow(data)
    
    # Aggregate by pickup location
    agg_df = df.group_by(['PULocationID', 'Zone', 'Borough']).agg([
        pl.count().alias('total_trips'),
        pl.col('total_fare_amount').sum().alias('total_fare_amount'),
        pl.col('total_fare_amount').mean().alias('avg_fare_amount')
    ])
    
    # Sort by total fare amount descending and take top 100 locations
    result_df = agg_df.sort('total_fare_amount', descending=True).head(100)
    
    # Round monetary values to 2 decimal places
    result_df = result_df.with_columns([
        pl.col('total_fare_amount').round(2),
        pl.col('avg_fare_amount').round(2)
    ])
    
    return result_df.to_arrow()