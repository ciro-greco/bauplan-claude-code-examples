# NYC Taxi Analytics Dashboard 🚕

A beautiful, interactive Streamlit dashboard for visualizing NYC taxi pickup location statistics from the Bauplan data pipeline.

## Features

### 📊 Key Metrics
- Total trips across all locations
- Average trip distance
- Top pickup location
- Real-time statistics

### 📈 Four Interactive Views

1. **Top Locations** - Bar charts showing the busiest pickup zones with color-coded average distances
2. **By Borough** - Analysis grouped by NYC boroughs (Manhattan, Brooklyn, Queens, etc.)
3. **Distance Analysis** - Scatter plots and histograms exploring trip distance patterns
4. **Data Table** - Interactive, filterable table with CSV export

### 🎨 Visualizations
- Interactive bar charts and scatter plots
- Pie charts for borough distribution
- Histograms for distance distribution
- Color-coded metrics
- Hover tooltips with detailed information

## Prerequisites

1. **Bauplan pipeline must be run first:**
   ```bash
   cd pipeline
   bauplan run
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements-dashboard.txt
   ```

## Running the Dashboard

### Option 1: From taxi-pipeline directory
```bash
streamlit run dashboard.py
```

### Option 2: From project root
```bash
streamlit run taxi-pipeline/dashboard.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

## Usage

### Sidebar Settings
- **Number of locations**: Choose how many top locations to display (10, 25, 50, 100, or All)
- **Refresh Data**: Clear cache and reload fresh data from Bauplan

### Filters (Data Table tab)
- **Borough filter**: Select specific boroughs to analyze
- **Minimum trips**: Filter locations by minimum trip count

### Export
- Download filtered data as CSV from the Data Table tab

## Dashboard Tabs

### 🏆 Top Locations
- Horizontal bar chart of top 20 pickup zones
- Color intensity shows average trip distance
- Borough distribution pie chart
- Summary statistics

### 🗺️ By Borough
- Total trips by borough
- Average distance by borough
- Number of zones per borough
- Detailed borough statistics table

### 📏 Distance Analysis
- Scatter plot: trip count vs average distance
- Distance distribution histogram
- Distance category breakdown (Short/Medium/Long/Very Long)

### 📋 Data Table
- Full data table with all metrics
- Multi-select borough filter
- Minimum trips threshold
- CSV download button

## Data Source

The dashboard queries the `top_pickup_locations_demo` table from your active Bauplan branch.

**Columns:**
- `PULocationID` - Pickup location ID
- `Borough` - NYC borough name
- `Zone` - Specific zone name
- `number_of_trips` - Total trips from this location
- `avg_trip_distance` - Average distance in miles

## Troubleshooting

### "No data available"
**Solution:** Run the pipeline first
```bash
cd pipeline
bauplan run
```

### "Table not found"
**Solution:** Check your active branch
```bash
bauplan info
bauplan branch checkout <branch-name>
```

### Data is stale
**Solution:** Click "Refresh Data" in the sidebar or clear cache
```bash
# Or restart Streamlit with cache clearing
streamlit run dashboard.py --server.runOnSave true
```

## Customization

### Change default limit
Edit `dashboard.py` line ~82:
```python
index=2  # Change to 0 (Top 10), 1 (Top 25), etc.
```

### Adjust cache TTL
Edit `dashboard.py` line ~36:
```python
@st.cache_data(ttl=300)  # Change 300 (5 minutes) to desired seconds
```

### Add more visualizations
Add new tabs in the visualization section (around line ~200)

## Performance

- **Data caching**: Results cached for 5 minutes
- **Query optimization**: Only fetches requested number of rows
- **Responsive design**: Adapts to screen size

## Technologies

- **Streamlit** - Dashboard framework
- **Plotly** - Interactive visualizations
- **Pandas** - Data manipulation
- **Bauplan SDK** - Data querying

---

**Enjoy exploring your NYC taxi data!** 🚕📊
