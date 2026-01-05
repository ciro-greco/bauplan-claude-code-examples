"""
Engagement Analysis Pipeline Models.

This pipeline analyzes correlations between user features and various target metrics
to identify which factors most strongly predict user behavior on Instagram.

DAG Structure:
    [social.social_media_data] --> [source_data] --> [correlation_analysis] --> [feature_importance_summary]
                                          |
                                          +--> [feed_time_correlation_analysis] --> [feed_time_importance_summary]
"""

import bauplan


@bauplan.model(
    columns=[
        'age',
        'exercise_hours_per_week',
        'sleep_hours_per_night',
        'perceived_stress_score',
        'self_reported_happiness',
        'body_mass_index',
        'blood_pressure_systolic',
        'blood_pressure_diastolic',
        'daily_steps_count',
        'weekly_work_hours',
        'hobbies_count',
        'social_events_per_month',
        'books_read_per_year',
        'volunteer_hours_per_month',
        'travel_frequency_per_year',
        'daily_active_minutes_instagram',
        'sessions_per_day',
        'posts_created_per_week',
        'reels_watched_per_day',
        'stories_viewed_per_day',
        'likes_given_per_day',
        'comments_written_per_day',
        'dms_sent_per_week',
        'dms_received_per_week',
        'ads_viewed_per_day',
        'ads_clicked_per_day',
        'time_on_feed_per_day',
        'time_on_explore_per_day',
        'time_on_messages_per_day',
        'time_on_reels_per_day',
        'followers_count',
        'following_count',
        'notification_response_rate',
        'account_creation_year',
        'average_session_length_minutes',
        'linked_accounts_count',
        'user_engagement_score',
    ]
)
@bauplan.python('3.11', pip={'polars': '1.18.0'})
def source_data(
    data=bauplan.Model(
        'social.social_media_data',
        columns=[
            'age',
            'exercise_hours_per_week',
            'sleep_hours_per_night',
            'perceived_stress_score',
            'self_reported_happiness',
            'body_mass_index',
            'blood_pressure_systolic',
            'blood_pressure_diastolic',
            'daily_steps_count',
            'weekly_work_hours',
            'hobbies_count',
            'social_events_per_month',
            'books_read_per_year',
            'volunteer_hours_per_month',
            'travel_frequency_per_year',
            'daily_active_minutes_instagram',
            'sessions_per_day',
            'posts_created_per_week',
            'reels_watched_per_day',
            'stories_viewed_per_day',
            'likes_given_per_day',
            'comments_written_per_day',
            'dms_sent_per_week',
            'dms_received_per_week',
            'ads_viewed_per_day',
            'ads_clicked_per_day',
            'time_on_feed_per_day',
            'time_on_explore_per_day',
            'time_on_messages_per_day',
            'time_on_reels_per_day',
            'followers_count',
            'following_count',
            'notification_response_rate',
            'account_creation_year',
            'average_session_length_minutes',
            'linked_accounts_count',
            'user_engagement_score',
        ]
    )
):
    """
    First node: reads numeric features from social_media_data for correlation analysis.
    Excludes user_id (identifier) and categorical columns for numeric correlation.

    | age | exercise_hours_per_week | sleep_hours_per_night | ... | user_engagement_score |
    |-----|------------------------|----------------------|-----|----------------------|
    | 19  | 2.5                    | 7.6                  | ... | 0.95                 |
    """
    import polars as pl

    df = pl.from_arrow(data)
    return df.to_arrow()


@bauplan.model(
    columns=[
        'feature_name',
        'correlation_coefficient',
        'abs_correlation',
        'p_value',
        'sample_size'
    ]
)
@bauplan.python('3.11', pip={'polars': '1.18.0', 'scipy': '1.11.4'})
def correlation_analysis(
    data=bauplan.Model('source_data')
):
    """
    Calculates Pearson correlation coefficients and p-values between all
    numeric features and user_engagement_score.

    | feature_name                  | correlation_coefficient | abs_correlation | p_value  | sample_size |
    |-------------------------------|------------------------|-----------------|----------|-------------|
    | daily_active_minutes_insta... | -0.53                  | 0.53            | 0.0      | 1547896     |
    """
    import polars as pl
    from scipy import stats
    import numpy as np

    df = pl.from_arrow(data)
    target_col = 'user_engagement_score'
    feature_cols = [col for col in df.columns if col != target_col]

    # Extract target as numpy array once
    target_values = df.select(target_col).to_numpy().flatten()

    correlations = []
    for feature in feature_cols:
        feature_values = df.select(feature).to_numpy().flatten()

        # Remove NaN pairs
        valid_mask = ~(np.isnan(feature_values) | np.isnan(target_values))
        valid_feature = feature_values[valid_mask]
        valid_target = target_values[valid_mask]

        if len(valid_feature) > 2:
            corr, p_value = stats.pearsonr(valid_feature, valid_target)
            correlations.append({
                'feature_name': feature,
                'correlation_coefficient': float(corr),
                'abs_correlation': float(abs(corr)),
                'p_value': float(p_value),
                'sample_size': int(len(valid_feature))
            })

    result_df = pl.DataFrame(correlations)
    result_df = result_df.sort('abs_correlation', descending=True)

    return result_df.to_arrow()


@bauplan.model(
    columns=[
        'rank',
        'feature_name',
        'correlation_coefficient',
        'p_value',
        'significance_level',
        'is_significant',
        'correlation_strength',
        'direction',
        'interpretation'
    ],
    materialization_strategy='REPLACE'
)
@bauplan.python('3.11', pip={'polars': '1.18.0'})
def feature_importance_summary(
    data=bauplan.Model(
        'correlation_analysis',
        columns=['feature_name', 'correlation_coefficient', 'abs_correlation', 'p_value', 'sample_size']
    )
):
    """
    Ranks features by correlation strength and provides interpretation
    for building a predictive model, including statistical significance.

    | rank | feature_name         | corr  | p_value | significance | is_sig | strength | direction |
    |------|----------------------|-------|---------|--------------|--------|----------|-----------|
    | 1    | stories_viewed_per.. | -0.56 | 0.0     | p < 0.001    | true   | Strong   | Negative  |
    """
    import polars as pl

    df = pl.from_arrow(data)
    df = df.sort('abs_correlation', descending=True)

    def get_strength(abs_corr: float) -> str:
        """Classify correlation strength."""
        if abs_corr >= 0.7:
            return 'Very Strong'
        elif abs_corr >= 0.5:
            return 'Strong'
        elif abs_corr >= 0.3:
            return 'Moderate'
        elif abs_corr >= 0.1:
            return 'Weak'
        else:
            return 'Negligible'

    def get_direction(corr: float) -> str:
        """Get correlation direction."""
        return 'Positive' if corr >= 0 else 'Negative'

    def get_significance_level(p: float) -> str:
        """Classify statistical significance level."""
        if p < 0.001:
            return 'p < 0.001 (***)'
        elif p < 0.01:
            return 'p < 0.01 (**)'
        elif p < 0.05:
            return 'p < 0.05 (*)'
        else:
            return 'not significant'

    def get_interpretation(feature: str, corr: float, strength: str, is_sig: bool) -> str:
        """Generate interpretation for the feature."""
        if not is_sig:
            return f"NOT SIGNIFICANT: correlation may be due to chance"

        direction = 'higher' if corr >= 0 else 'lower'
        impact = 'increases' if corr >= 0 else 'decreases'

        if strength in ['Very Strong', 'Strong']:
            return f"{strength} predictor: {direction} {feature} {impact} engagement"
        elif strength == 'Moderate':
            return f"Moderate predictor: some relationship with engagement"
        else:
            return f"Weak predictor: limited predictive value"

    # Add computed columns
    result = df.with_columns([
        pl.col('abs_correlation').map_elements(get_strength, return_dtype=pl.Utf8).alias('correlation_strength'),
        pl.col('correlation_coefficient').map_elements(get_direction, return_dtype=pl.Utf8).alias('direction'),
        pl.col('p_value').map_elements(get_significance_level, return_dtype=pl.Utf8).alias('significance_level'),
        (pl.col('p_value') < 0.05).alias('is_significant'),
    ])

    result = result.with_row_index('rank', offset=1)

    # Add interpretation with significance check
    interpretations = [
        get_interpretation(
            row['feature_name'],
            row['correlation_coefficient'],
            row['correlation_strength'],
            row['is_significant']
        )
        for row in result.iter_rows(named=True)
    ]
    result = result.with_columns(pl.Series('interpretation', interpretations))

    result = result.select([
        pl.col('rank').cast(pl.Int64),
        'feature_name',
        'correlation_coefficient',
        'p_value',
        'significance_level',
        'is_significant',
        'correlation_strength',
        'direction',
        'interpretation'
    ])

    return result.to_arrow()


# =============================================================================
# Feed Time Analysis Models
# Target: time_on_feed_per_day
# =============================================================================


@bauplan.model(
    columns=[
        'feature_name',
        'correlation_coefficient',
        'abs_correlation',
        'p_value',
        'sample_size'
    ]
)
@bauplan.python('3.11', pip={'polars': '1.18.0', 'scipy': '1.11.4'})
def feed_time_correlation_analysis(
    data=bauplan.Model('source_data')
):
    """
    Calculates Pearson correlation coefficients and p-values between all
    numeric features and time_on_feed_per_day.

    | feature_name                  | correlation_coefficient | abs_correlation | p_value  | sample_size |
    |-------------------------------|------------------------|-----------------|----------|-------------|
    | daily_active_minutes_insta... | 0.85                   | 0.85            | 0.0      | 1547896     |
    """
    import polars as pl
    from scipy import stats
    import numpy as np

    df = pl.from_arrow(data)
    target_col = 'time_on_feed_per_day'
    feature_cols = [col for col in df.columns if col != target_col]

    # Extract target as numpy array once
    target_values = df.select(target_col).to_numpy().flatten()

    correlations = []
    for feature in feature_cols:
        feature_values = df.select(feature).to_numpy().flatten()

        # Remove NaN pairs
        valid_mask = ~(np.isnan(feature_values) | np.isnan(target_values))
        valid_feature = feature_values[valid_mask]
        valid_target = target_values[valid_mask]

        if len(valid_feature) > 2:
            corr, p_value = stats.pearsonr(valid_feature, valid_target)
            correlations.append({
                'feature_name': feature,
                'correlation_coefficient': float(corr),
                'abs_correlation': float(abs(corr)),
                'p_value': float(p_value),
                'sample_size': int(len(valid_feature))
            })

    result_df = pl.DataFrame(correlations)
    result_df = result_df.sort('abs_correlation', descending=True)

    return result_df.to_arrow()


@bauplan.model(
    columns=[
        'rank',
        'feature_name',
        'correlation_coefficient',
        'p_value',
        'significance_level',
        'is_significant',
        'correlation_strength',
        'direction',
        'interpretation'
    ],
    materialization_strategy='REPLACE'
)
@bauplan.python('3.11', pip={'polars': '1.18.0'})
def feed_time_importance_summary(
    data=bauplan.Model(
        'feed_time_correlation_analysis',
        columns=['feature_name', 'correlation_coefficient', 'abs_correlation', 'p_value', 'sample_size']
    )
):
    """
    Ranks features by correlation strength with time_on_feed_per_day
    and provides interpretation for building a predictive model.

    | rank | feature_name         | corr  | p_value | significance | is_sig | strength | direction |
    |------|----------------------|-------|---------|--------------|--------|----------|-----------|
    | 1    | daily_active_mins... | 0.85  | 0.0     | p < 0.001    | true   | V.Strong | Positive  |
    """
    import polars as pl

    df = pl.from_arrow(data)
    df = df.sort('abs_correlation', descending=True)

    def get_strength(abs_corr: float) -> str:
        """Classify correlation strength."""
        if abs_corr >= 0.7:
            return 'Very Strong'
        elif abs_corr >= 0.5:
            return 'Strong'
        elif abs_corr >= 0.3:
            return 'Moderate'
        elif abs_corr >= 0.1:
            return 'Weak'
        else:
            return 'Negligible'

    def get_direction(corr: float) -> str:
        """Get correlation direction."""
        return 'Positive' if corr >= 0 else 'Negative'

    def get_significance_level(p: float) -> str:
        """Classify statistical significance level."""
        if p < 0.001:
            return 'p < 0.001 (***)'
        elif p < 0.01:
            return 'p < 0.01 (**)'
        elif p < 0.05:
            return 'p < 0.05 (*)'
        else:
            return 'not significant'

    def get_interpretation(feature: str, corr: float, strength: str, is_sig: bool) -> str:
        """Generate interpretation for the feature."""
        if not is_sig:
            return "NOT SIGNIFICANT: correlation may be due to chance"

        direction = 'higher' if corr >= 0 else 'lower'
        impact = 'increases' if corr >= 0 else 'decreases'

        if strength in ['Very Strong', 'Strong']:
            return f"{strength} predictor: {direction} {feature} {impact} feed time"
        elif strength == 'Moderate':
            return f"Moderate predictor: some relationship with feed time"
        else:
            return f"Weak predictor: limited predictive value"

    # Add computed columns
    result = df.with_columns([
        pl.col('abs_correlation').map_elements(get_strength, return_dtype=pl.Utf8).alias('correlation_strength'),
        pl.col('correlation_coefficient').map_elements(get_direction, return_dtype=pl.Utf8).alias('direction'),
        pl.col('p_value').map_elements(get_significance_level, return_dtype=pl.Utf8).alias('significance_level'),
        (pl.col('p_value') < 0.05).alias('is_significant'),
    ])

    result = result.with_row_index('rank', offset=1)

    # Add interpretation with significance check
    interpretations = [
        get_interpretation(
            row['feature_name'],
            row['correlation_coefficient'],
            row['correlation_strength'],
            row['is_significant']
        )
        for row in result.iter_rows(named=True)
    ]
    result = result.with_columns(pl.Series('interpretation', interpretations))

    result = result.select([
        pl.col('rank').cast(pl.Int64),
        'feature_name',
        'correlation_coefficient',
        'p_value',
        'significance_level',
        'is_significant',
        'correlation_strength',
        'direction',
        'interpretation'
    ])

    return result.to_arrow()
