"""
Marketing Insights Dashboard - Engagement Analysis

A Streamlit app for the marketing team to explore user engagement predictors
and identify actionable insights for maximizing engagement score and feed time.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import bauplan

# Configuration
BRANCH = "ciro.wap_social_media_data_1767607536"
SOURCE_TABLE = "social.social_media_data"

st.set_page_config(
    page_title="Marketing Insights Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def get_bauplan_client():
    """Initialize bauplan client."""
    return bauplan.Client()


@st.cache_data(ttl=300)
def run_query(query: str) -> pd.DataFrame:
    """Execute a query against bauplan and return a DataFrame."""
    client = get_bauplan_client()
    result = client.query(query=query, ref=BRANCH)
    return result.to_pandas()


@st.cache_data(ttl=300)
def get_correlation_data(target: str) -> pd.DataFrame:
    """Get correlation data for a specific target metric."""
    if target == "engagement_score":
        table = "bauplan.feature_importance_summary"
    else:
        table = "bauplan.feed_time_importance_summary"

    query = f"SELECT * FROM {table} ORDER BY rank"
    return run_query(query)


@st.cache_data(ttl=300)
def get_categorical_breakdown(category: str, metric: str) -> pd.DataFrame:
    """Get breakdown by categorical variable."""
    query = f"""
    SELECT
        {category} as category,
        COUNT(*) as user_count,
        ROUND(AVG(user_engagement_score), 4) as avg_engagement,
        ROUND(AVG(time_on_feed_per_day), 2) as avg_feed_time,
        ROUND(AVG(perceived_stress_score), 2) as avg_stress,
        ROUND(AVG(self_reported_happiness), 2) as avg_happiness
    FROM {SOURCE_TABLE}
    GROUP BY {category}
    ORDER BY AVG({metric}) DESC
    """
    return run_query(query)


def classify_actionability(feature: str) -> str:
    """Classify feature actionability."""
    non_actionable = [
        'daily_active_minutes_instagram', 'sessions_per_day', 'posts_created_per_week',
        'reels_watched_per_day', 'stories_viewed_per_day', 'likes_given_per_day',
        'comments_written_per_day', 'dms_sent_per_week', 'dms_received_per_week',
        'ads_viewed_per_day', 'ads_clicked_per_day', 'time_on_feed_per_day',
        'time_on_explore_per_day', 'time_on_messages_per_day', 'time_on_reels_per_day',
        'average_session_length_minutes', 'user_engagement_score'
    ]

    actionable = [
        'perceived_stress_score', 'self_reported_happiness', 'age',
        'followers_count', 'following_count'
    ]

    if feature in non_actionable:
        return "Not Actionable (Platform Metric)"
    elif feature in actionable:
        return "Actionable"
    else:
        return "Limited Actionability"


def main():
    """Main app entry point."""
    st.sidebar.title("📊 Marketing Insights")

    page = st.sidebar.radio(
        "Navigate to:",
        ["Executive Summary", "Correlation Analysis", "Categorical Analysis", "Data Explorer"]
    )

    if page == "Executive Summary":
        show_executive_summary()
    elif page == "Correlation Analysis":
        show_correlation_analysis()
    elif page == "Categorical Analysis":
        show_categorical_analysis()
    else:
        show_data_explorer()


def show_executive_summary():
    """Display executive summary page."""
    st.title("📈 Marketing Insights Dashboard")
    st.markdown("### Executive Summary: User Engagement Analysis")

    st.markdown("""
    This dashboard helps the marketing team understand which factors predict
    **user engagement score** and **time on feed** - and which are actionable.
    """)

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Users", "1.55M", help="Users in analysis")
    with col2:
        st.metric("Avg Engagement", "1.645", help="Average engagement score")
    with col3:
        st.metric("Avg Feed Time", "94.1 min", help="Average daily feed time")
    with col4:
        st.metric("Significant Predictors", "21", help="Features with p < 0.05")

    st.markdown("---")

    # Key findings
    st.markdown("### 🎯 Key Actionable Findings")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### For Engagement Score")
        st.markdown("""
        | Finding | Correlation | Action |
        |---------|-------------|--------|
        | **Lower stress → Higher engagement** | -0.44 | Target relaxed users |
        | **Higher happiness → Higher engagement** | +0.27 | Promote positive content |
        | **Older users engage more** | +0.11 | Don't over-index on Gen-Z |
        """)

    with col2:
        st.markdown("#### For Feed Time")
        st.markdown("""
        | Finding | Correlation | Action |
        |---------|-------------|--------|
        | **Higher stress → More feed time** | +0.81 | Stressed users scroll more |
        | **Lower happiness → More feed time** | -0.36 | Unhappy users stay longer |
        | **Younger users → More feed time** | -0.19 | Youth spends more time |
        """)

    st.markdown("---")

    # The stress paradox
    st.markdown("### ⚠️ The Stress Paradox")

    st.warning("""
    **Critical Insight**: Stressed users spend MORE time on feed (+0.81) but engage LESS (-0.44).

    - Optimizing purely for time-on-feed attracts passive, stressed scrollers
    - Optimizing for engagement attracts happy, active users
    - **Recommendation**: Prioritize engagement score as the primary KPI
    """)

    # Geographic insights
    st.markdown("### 🌍 Geographic Opportunities")

    geo_data = pd.DataFrame({
        'Country': ['Canada', 'Japan', 'Germany', 'UK', 'US', 'India', 'Brazil', 'Australia'],
        'Engagement': [1.658, 1.650, 1.650, 1.646, 1.645, 1.643, 1.642, 1.632],
        'Priority': ['High', 'High', 'High', 'Medium', 'Medium', 'Medium', 'Low', 'Low']
    })

    fig = px.bar(
        geo_data, x='Country', y='Engagement', color='Priority',
        color_discrete_map={'High': '#2ecc71', 'Medium': '#f1c40f', 'Low': '#e74c3c'},
        title="Average Engagement Score by Country"
    )
    fig.update_layout(yaxis_range=[1.62, 1.67])
    st.plotly_chart(fig, use_container_width=True)


def show_correlation_analysis():
    """Display correlation analysis page."""
    st.title("🔬 Correlation Analysis")

    # Target selector
    target = st.selectbox(
        "Select Target Metric:",
        ["engagement_score", "feed_time"],
        format_func=lambda x: "User Engagement Score" if x == "engagement_score" else "Time on Feed (minutes)"
    )

    # Load data
    with st.spinner("Loading correlation data..."):
        df = get_correlation_data(target)

    # Add actionability classification
    df['actionability'] = df['feature_name'].apply(classify_actionability)

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        show_significant_only = st.checkbox("Show significant only (p < 0.05)", value=True)
    with col2:
        actionability_filter = st.multiselect(
            "Filter by Actionability:",
            options=df['actionability'].unique().tolist(),
            default=df['actionability'].unique().tolist()
        )
    with col3:
        strength_filter = st.multiselect(
            "Filter by Strength:",
            options=df['correlation_strength'].unique().tolist(),
            default=df['correlation_strength'].unique().tolist()
        )

    # Apply filters
    filtered_df = df.copy()
    if show_significant_only:
        filtered_df = filtered_df[filtered_df['is_significant'] == True]
    filtered_df = filtered_df[filtered_df['actionability'].isin(actionability_filter)]
    filtered_df = filtered_df[filtered_df['correlation_strength'].isin(strength_filter)]

    # Visualization
    st.markdown("### Correlation Coefficients")

    fig = px.bar(
        filtered_df,
        x='correlation_coefficient',
        y='feature_name',
        color='actionability',
        orientation='h',
        color_discrete_map={
            'Actionable': '#2ecc71',
            'Limited Actionability': '#f1c40f',
            'Not Actionable (Platform Metric)': '#95a5a6'
        },
        title=f"Feature Correlations with {'Engagement Score' if target == 'engagement_score' else 'Feed Time'}",
        labels={'correlation_coefficient': 'Correlation Coefficient', 'feature_name': 'Feature'}
    )
    fig.update_layout(height=600, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.markdown("### Detailed Results")

    display_cols = ['rank', 'feature_name', 'correlation_coefficient', 'p_value',
                    'significance_level', 'correlation_strength', 'direction', 'actionability']
    st.dataframe(
        filtered_df[display_cols].style.background_gradient(
            subset=['correlation_coefficient'], cmap='RdYlGn', vmin=-1, vmax=1
        ),
        use_container_width=True,
        hide_index=True
    )

    # Summary stats
    st.markdown("### Summary Statistics")
    col1, col2, col3 = st.columns(3)

    with col1:
        actionable_count = len(filtered_df[filtered_df['actionability'] == 'Actionable'])
        st.metric("Actionable Features", actionable_count)
    with col2:
        strong_count = len(filtered_df[filtered_df['correlation_strength'].isin(['Strong', 'Very Strong'])])
        st.metric("Strong Predictors", strong_count)
    with col3:
        significant_count = len(filtered_df[filtered_df['is_significant'] == True])
        st.metric("Significant (p<0.05)", significant_count)


def show_categorical_analysis():
    """Display categorical analysis page."""
    st.title("📊 Categorical Analysis")

    st.markdown("""
    Explore how different user segments perform on engagement and feed time metrics.
    Use this to identify high-value segments for targeting.
    """)

    # Category selector
    categories = [
        'country', 'gender', 'income_level', 'employment_status',
        'education_level', 'relationship_status', 'urban_rural',
        'content_type_preference', 'preferred_content_theme',
        'subscription_status', 'diet_quality'
    ]

    col1, col2 = st.columns(2)

    with col1:
        selected_category = st.selectbox(
            "Select Category:",
            categories,
            format_func=lambda x: x.replace('_', ' ').title()
        )

    with col2:
        metric = st.selectbox(
            "Sort by Metric:",
            ["user_engagement_score", "time_on_feed_per_day"],
            format_func=lambda x: "Engagement Score" if x == "user_engagement_score" else "Feed Time"
        )

    # Load data
    with st.spinner("Loading categorical data..."):
        df = get_categorical_breakdown(selected_category, metric)

    # Visualizations
    col1, col2 = st.columns(2)

    with col1:
        fig1 = px.bar(
            df, x='category', y='avg_engagement',
            title=f"Avg Engagement by {selected_category.replace('_', ' ').title()}",
            color='avg_engagement',
            color_continuous_scale='RdYlGn'
        )
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = px.bar(
            df, x='category', y='avg_feed_time',
            title=f"Avg Feed Time by {selected_category.replace('_', ' ').title()}",
            color='avg_feed_time',
            color_continuous_scale='Blues'
        )
        fig2.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)

    # Variance analysis
    engagement_variance = df['avg_engagement'].max() - df['avg_engagement'].min()
    feed_time_variance = df['avg_feed_time'].max() - df['avg_feed_time'].min()

    st.markdown("### Segment Differentiation")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Engagement Variance",
            f"{engagement_variance:.4f}",
            help="Difference between best and worst segment"
        )
    with col2:
        st.metric(
            "Feed Time Variance",
            f"{feed_time_variance:.1f} min",
            help="Difference between best and worst segment"
        )
    with col3:
        actionability = "High" if engagement_variance > 0.015 else "Medium" if engagement_variance > 0.005 else "Low"
        st.metric("Actionability", actionability)

    # Data table
    st.markdown("### Detailed Breakdown")
    st.dataframe(
        df.style.background_gradient(subset=['avg_engagement'], cmap='RdYlGn')
               .background_gradient(subset=['avg_feed_time'], cmap='Blues'),
        use_container_width=True,
        hide_index=True
    )

    # Best/Worst segments
    st.markdown("### Key Segments")
    col1, col2 = st.columns(2)

    with col1:
        st.success(f"**Highest Engagement**: {df.iloc[0]['category']} ({df.iloc[0]['avg_engagement']:.4f})")
    with col2:
        st.error(f"**Lowest Engagement**: {df.iloc[-1]['category']} ({df.iloc[-1]['avg_engagement']:.4f})")


def show_data_explorer():
    """Display interactive data explorer."""
    st.title("🔍 Data Explorer")

    st.markdown("""
    Explore the raw data with custom filters to discover insights for specific user segments.
    """)

    # Filters
    st.sidebar.markdown("### Filters")

    # Country filter
    countries = ['All', 'United States', 'Canada', 'United Kingdom', 'Germany',
                 'Japan', 'Australia', 'Brazil', 'India', 'South Korea', 'Other']
    selected_country = st.sidebar.selectbox("Country:", countries)

    # Age range
    age_range = st.sidebar.slider("Age Range:", 13, 80, (18, 65))

    # Income level
    income_levels = ['All', 'Low', 'Lower-middle', 'Middle', 'Upper-middle', 'High']
    selected_income = st.sidebar.selectbox("Income Level:", income_levels)

    # Subscription status
    subscriptions = ['All', 'Free', 'Premium', 'Business']
    selected_subscription = st.sidebar.selectbox("Subscription:", subscriptions)

    # Build query
    conditions = [f"age BETWEEN {age_range[0]} AND {age_range[1]}"]

    if selected_country != 'All':
        conditions.append(f"country = '{selected_country}'")
    if selected_income != 'All':
        conditions.append(f"income_level = '{selected_income}'")
    if selected_subscription != 'All':
        conditions.append(f"subscription_status = '{selected_subscription}'")

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT
        COUNT(*) as user_count,
        ROUND(AVG(user_engagement_score), 4) as avg_engagement,
        ROUND(AVG(time_on_feed_per_day), 2) as avg_feed_time,
        ROUND(AVG(daily_active_minutes_instagram), 2) as avg_active_mins,
        ROUND(AVG(perceived_stress_score), 2) as avg_stress,
        ROUND(AVG(self_reported_happiness), 2) as avg_happiness,
        ROUND(AVG(age), 1) as avg_age,
        ROUND(AVG(followers_count), 0) as avg_followers,
        ROUND(AVG(sessions_per_day), 1) as avg_sessions
    FROM {SOURCE_TABLE}
    WHERE {where_clause}
    """

    # Execute query
    with st.spinner("Querying data..."):
        try:
            df = run_query(query)

            if len(df) > 0 and df.iloc[0]['user_count'] > 0:
                row = df.iloc[0]

                # Display metrics
                st.markdown("### Segment Metrics")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Users in Segment", f"{int(row['user_count']):,}")
                with col2:
                    st.metric("Avg Engagement", f"{row['avg_engagement']:.4f}")
                with col3:
                    st.metric("Avg Feed Time", f"{row['avg_feed_time']:.1f} min")
                with col4:
                    st.metric("Avg Active Mins", f"{row['avg_active_mins']:.1f}")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Avg Stress", f"{row['avg_stress']:.1f}")
                with col2:
                    st.metric("Avg Happiness", f"{row['avg_happiness']:.1f}")
                with col3:
                    st.metric("Avg Age", f"{row['avg_age']:.1f}")
                with col4:
                    st.metric("Avg Followers", f"{int(row['avg_followers']):,}")

                # Comparison to overall
                st.markdown("### Comparison to Overall Average")

                comparison_data = pd.DataFrame({
                    'Metric': ['Engagement', 'Feed Time', 'Stress', 'Happiness'],
                    'Segment': [row['avg_engagement'], row['avg_feed_time'], row['avg_stress'], row['avg_happiness']],
                    'Overall': [1.645, 94.1, 20.0, 5.5]
                })
                comparison_data['Difference'] = comparison_data['Segment'] - comparison_data['Overall']
                comparison_data['Pct_Diff'] = (comparison_data['Difference'] / comparison_data['Overall']) * 100

                fig = go.Figure()
                fig.add_trace(go.Bar(name='Segment', x=comparison_data['Metric'], y=comparison_data['Segment']))
                fig.add_trace(go.Bar(name='Overall', x=comparison_data['Metric'], y=comparison_data['Overall']))
                fig.update_layout(barmode='group', title="Segment vs Overall Comparison")
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.warning("No data found for the selected filters.")

        except Exception as e:
            st.error(f"Error querying data: {str(e)}")

    # Show query
    with st.expander("View SQL Query"):
        st.code(query, language='sql')


if __name__ == "__main__":
    main()
