## Data to import 

### Prompts
```markdown
Hey, I have some data in my s3 bucket. I want to import the data in the lakehouse as an iceberg table, so I can run queries and pipelines in it.
the data is here: s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv
the table name is: instagram_engagement_data
After the data is successfully imported, Keep branch open for inspection (do not merge into main)
if the import fail, keep branch for debugging. 
```

```Let's now build a pipeline for the marketing team who needs to understand the engagment meterics for social media.

Let's say that we want to build a pipeline that calculates different user segments by engagement level. 
 
Do the entire pipeline as Python and use Polars because it is better for performance.                                ```
```

### Social media user analysis -> social_media_user_data
S3 Uri: 
```
s3://alpha-hello-bauplan/social-media-user-analysis/instagram_usage_lifestyle.csv  
```
Link to the original dataset: https://www.kaggle.com/datasets/rockyt07/social-media-user-analysis

#### About the Dataset
Social Media User Behavior & Lifestyle – 1 Million Synthetic Users (Instagram 2025–2026 based)
This dataset contains 1,000,000+ fully synthetic user profiles that realistically simulate Instagram usage patterns combined with detailed demographic, lifestyle, health, and behavioral attributes.

All data is 100% synthetic — generated using statistical distributions and realistic correlations.
No real user data was used or collected. Perfectly safe for research, education, prototyping, and Kaggle competitions.

```markdown
Rows: 1,000,000 users
Columns: 57
File: instagram_usage_lifestyle_1million.csv (~250–350 MB uncompressed)
License: CC0: Public Domain (use, modify, share freely)

Key Themes & Columns

Demographics & Background (19 columns)
age, gender, country, urban_rural, income_level, employment_status, education_level, relationship_status, has_children

Lifestyle & Health (10 columns)
exercise_hours_per_week, sleep_hours_per_night, diet_quality, smoking, alcohol_frequency, perceived_stress_score, self_reported_happiness, body_mass_index, blood_pressure_systolic, blood_pressure_diastolic, daily_steps_count

Daily/Weekly Habits (8 columns)
weekly_work_hours, hobbies_count, social_events_per_month, books_read_per_year, volunteer_hours_per_month, travel_frequency_per_year

Instagram Usage & Engagement (17 columns)
daily_active_minutes_instagram, 
sessions_per_day, 
posts_created_per_week, 
reels_watched_per_day, 
stories_viewed_per_day, 
likes_given_per_day, 
comments_written_per_day, 
dms_sent_per_week, 
dms_received_per_week, 
ads_viewed_per_day, 
ads_clicked_per_day, 
time_on_feed_per_day, 
time_on_explore_per_day, 
time_on_messages_per_day, 
time_on_reels_per_day, 
followers_count, 
following_count, 
notification_response_rate, 
average_session_length_minutes, 
content_type_preference, 
preferred_content_theme, 
privacy_setting_level, 
two_factor_auth_enabled, 
biometric_login_used, 
linked_accounts_count, 
subscription_status, 
user_engagement_score, 
account_creation_year, 
last_login_date, 
uses_premium_features

Built-in Realistic Correlations
- Higher perceived stress → increased daily active minutes & more reels/stories consumption
- Lower self-reported happiness → longer sessions & higher feed/reels time
- Younger age → significantly higher reels watched, posts created, follower growth
- More exercise & better sleep → slightly higher happiness & lower compulsive usage
- Higher income → increased likelihood of premium features & business accounts

Use Cases
- Exploratory Data Analysis (EDA) – discover links between screen time & well-being
- Predictive modeling – predict happiness/stress/sleep from usage patterns
- Clustering – identify user personas (doom-scroller, casual poster, aspiring influencer, etc.)
- A/B testing simulation – study behavioral effects
- Education & tutorials – great for teaching correlation, regression, feature engineering, large dataset handling
- Benchmarking – compare synthetic patterns vs real-world social media studies -100% synthetic – no real user data was accessed or used
- Feedback, notebooks, or extensions welcome in the discussion tab.
```

### Taxi rides NYC 

S3 Uri:
```markdown
s3://alpha-hello-bauplan/taxi_fhvhv_2021/taxi_fhvhv_2021.parquet
```