"""
NYC Taxi Pickup Locations Dashboard
====================================

A Streamlit dashboard visualizing NYC taxi pickup statistics from Bauplan.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import bauplan

# Page configuration
st.set_page_config(
    page_title="NYC Taxi Analytics Dashboard",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def load_data(limit=None):
    """Load data from Bauplan with caching."""
    client = bauplan.Client()

    if limit:
        query = f"""
        SELECT
            PULocationID,
            Borough,
            Zone,
            number_of_trips,
            avg_trip_distance
        FROM top_pickup_locations_demo
        ORDER BY number_of_trips DESC
        LIMIT {limit}
        """
    else:
        query = """
        SELECT
            PULocationID,
            Borough,
            Zone,
            number_of_trips,
            avg_trip_distance
        FROM top_pickup_locations_demo
        ORDER BY number_of_trips DESC
        """

    df = client.query(query).to_pandas()
    return df

# Header
st.title("🚕 NYC Taxi Pickup Analytics Dashboard")
st.markdown("Real-time analytics of NYC taxi pickup locations from 2021 data")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")

    # Data limit selector
    limit_options = {
        "Top 10": 10,
        "Top 25": 25,
        "Top 50": 50,
        "Top 100": 100,
        "All": None
    }
    selected_limit = st.selectbox(
        "Number of locations to display",
        options=list(limit_options.keys()),
        index=2  # Default to Top 50
    )
    limit = limit_options[selected_limit]

    # Refresh button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This dashboard visualizes NYC taxi pickup locations based on:
    - **Trip Count**: Number of trips from each location
    - **Avg Distance**: Average trip distance in miles

    Data source: Bauplan lakehouse
    """)

# Load data
try:
    with st.spinner("Loading data from Bauplan..."):
        df = load_data(limit)

    if df.empty:
        st.error("No data available. Please run the pipeline first.")
        st.stop()

    # Key Metrics
    st.header("📊 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)

    total_trips = df['number_of_trips'].sum()
    avg_distance = df['avg_trip_distance'].mean()
    top_location = df.iloc[0]['Zone']
    top_location_trips = df.iloc[0]['number_of_trips']

    with col1:
        st.metric(
            label="Total Trips",
            value=f"{total_trips:,.0f}",
            help="Total number of trips from displayed locations"
        )

    with col2:
        st.metric(
            label="Avg Trip Distance",
            value=f"{avg_distance:.2f} mi",
            help="Average trip distance across all locations"
        )

    with col3:
        st.metric(
            label="Top Location",
            value=top_location,
            help="Location with most pickups"
        )

    with col4:
        st.metric(
            label="Top Location Trips",
            value=f"{top_location_trips:,.0f}",
            help="Number of trips from top location"
        )

    st.markdown("---")

    # Visualizations
    st.header("📈 Visualizations")

    # Tab layout for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Top Locations",
        "🗺️ By Borough",
        "📏 Distance Analysis",
        "📋 Data Table"
    ])

    with tab1:
        st.subheader("Top Pickup Locations by Trip Count")

        # Bar chart - Top locations
        fig_top = px.bar(
            df.head(20),
            x='number_of_trips',
            y='Zone',
            orientation='h',
            color='avg_trip_distance',
            color_continuous_scale='Viridis',
            labels={
                'number_of_trips': 'Number of Trips',
                'Zone': 'Pickup Zone',
                'avg_trip_distance': 'Avg Distance (mi)'
            },
            title="Top 20 Pickup Zones",
            height=600
        )
        fig_top.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)

        # Show borough breakdown for top locations
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### Borough Distribution")
            borough_counts = df.head(20)['Borough'].value_counts()
            fig_borough_pie = px.pie(
                values=borough_counts.values,
                names=borough_counts.index,
                title="Borough Distribution (Top 20)"
            )
            st.plotly_chart(fig_borough_pie, use_container_width=True)

        with col2:
            st.markdown("##### Trip Statistics")
            stats_df = pd.DataFrame({
                'Metric': [
                    'Mean Trips',
                    'Median Trips',
                    'Std Dev Trips',
                    'Min Trips',
                    'Max Trips'
                ],
                'Value': [
                    f"{df['number_of_trips'].mean():,.0f}",
                    f"{df['number_of_trips'].median():,.0f}",
                    f"{df['number_of_trips'].std():,.0f}",
                    f"{df['number_of_trips'].min():,.0f}",
                    f"{df['number_of_trips'].max():,.0f}"
                ]
            })
            st.dataframe(stats_df, hide_index=True, use_container_width=True)

    with tab2:
        st.subheader("Analysis by Borough")

        # Group by borough
        borough_stats = df.groupby('Borough').agg({
            'number_of_trips': 'sum',
            'avg_trip_distance': 'mean',
            'Zone': 'count'
        }).reset_index()
        borough_stats.columns = ['Borough', 'Total Trips', 'Avg Distance', 'Number of Zones']
        borough_stats = borough_stats.sort_values('Total Trips', ascending=False)

        col1, col2 = st.columns(2)

        with col1:
            # Borough trips bar chart
            fig_borough_trips = px.bar(
                borough_stats,
                x='Borough',
                y='Total Trips',
                color='Avg Distance',
                title="Total Trips by Borough",
                labels={'Total Trips': 'Total Trips', 'Avg Distance': 'Avg Distance (mi)'}
            )
            st.plotly_chart(fig_borough_trips, use_container_width=True)

        with col2:
            # Borough average distance
            fig_borough_dist = px.bar(
                borough_stats,
                x='Borough',
                y='Avg Distance',
                color='Total Trips',
                title="Average Trip Distance by Borough",
                labels={'Avg Distance': 'Avg Distance (mi)', 'Total Trips': 'Total Trips'}
            )
            st.plotly_chart(fig_borough_dist, use_container_width=True)

        # Borough details table
        st.markdown("##### Borough Statistics")
        st.dataframe(
            borough_stats.style.format({
                'Total Trips': '{:,.0f}',
                'Avg Distance': '{:.2f}',
                'Number of Zones': '{:.0f}'
            }),
            hide_index=True,
            use_container_width=True
        )

    with tab3:
        st.subheader("Trip Distance Analysis")

        col1, col2 = st.columns(2)

        with col1:
            # Scatter plot: trips vs distance
            fig_scatter = px.scatter(
                df,
                x='avg_trip_distance',
                y='number_of_trips',
                color='Borough',
                hover_data=['Zone'],
                title="Trip Count vs Average Distance",
                labels={
                    'avg_trip_distance': 'Average Trip Distance (mi)',
                    'number_of_trips': 'Number of Trips'
                },
                height=500
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        with col2:
            # Distribution of average distances
            fig_hist = px.histogram(
                df,
                x='avg_trip_distance',
                nbins=30,
                title="Distribution of Average Trip Distances",
                labels={'avg_trip_distance': 'Average Trip Distance (mi)'},
                height=500
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        # Distance categories
        st.markdown("##### Distance Categories")
        df['distance_category'] = pd.cut(
            df['avg_trip_distance'],
            bins=[0, 2, 4, 6, float('inf')],
            labels=['Short (0-2mi)', 'Medium (2-4mi)', 'Long (4-6mi)', 'Very Long (6+mi)']
        )
        category_stats = df.groupby('distance_category').agg({
            'number_of_trips': 'sum',
            'Zone': 'count'
        }).reset_index()
        category_stats.columns = ['Distance Category', 'Total Trips', 'Number of Zones']

        fig_category = px.bar(
            category_stats,
            x='Distance Category',
            y='Total Trips',
            title="Trips by Distance Category",
            color='Number of Zones'
        )
        st.plotly_chart(fig_category, use_container_width=True)

    with tab4:
        st.subheader("Detailed Data Table")

        # Add filters
        col1, col2 = st.columns(2)

        with col1:
            selected_boroughs = st.multiselect(
                "Filter by Borough",
                options=sorted(df['Borough'].unique()),
                default=None
            )

        with col2:
            min_trips = st.number_input(
                "Minimum number of trips",
                min_value=0,
                max_value=int(df['number_of_trips'].max()),
                value=0,
                step=10000
            )

        # Apply filters
        filtered_df = df.copy()
        if selected_boroughs:
            filtered_df = filtered_df[filtered_df['Borough'].isin(selected_boroughs)]
        if min_trips > 0:
            filtered_df = filtered_df[filtered_df['number_of_trips'] >= min_trips]

        st.markdown(f"Showing **{len(filtered_df)}** locations")

        # Format and display table
        display_df = filtered_df.copy()
        display_df['number_of_trips'] = display_df['number_of_trips'].apply(lambda x: f"{x:,.0f}")
        display_df['avg_trip_distance'] = display_df['avg_trip_distance'].apply(lambda x: f"{x:.2f}")

        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=600
        )

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name="nyc_taxi_pickup_locations.csv",
            mime="text/csv"
        )

except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.error("Please ensure the pipeline has been run and the table exists on your active Bauplan branch.")

    with st.expander("🔍 Troubleshooting"):
        st.markdown("""
        **Common issues:**
        1. Pipeline not run yet - Run `bauplan run` in the pipeline directory
        2. Wrong branch - Check your active branch with `bauplan info`
        3. Table not materialized - Ensure the run completed successfully

        **To run the pipeline:**
        ```bash
        cd taxi-pipeline/pipeline
        bauplan run
        ```
        """)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>NYC Taxi Analytics Dashboard | Powered by Bauplan & Streamlit</p>
    </div>
""", unsafe_allow_html=True)
