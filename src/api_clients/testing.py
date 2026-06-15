from openelectricity.types import MarketMetric
from openelectricity import OEClient
from datetime import datetime, timedelta
import pandas as pd

# Get latest curtailment data (omit date_end for latest)
client = OEClient()
response = client.get_market(
    network_code="NEM",
    metrics=[
        MarketMetric.CURTAILMENT_SOLAR_UTILITY,
        MarketMetric.CURTAILMENT_WIND,
        MarketMetric.CURTAILMENT
    ],
    interval="5m",
    date_start=datetime.now() - timedelta(hours=2),
    # date_end omitted to get latest data
    primary_grouping="network_region"
)

# Convert to DataFrame
data = []
for timeseries in response.data:
    for result in timeseries.results:
        region = result.name.split("_")[-1]  # Extract region from name
        for data_point in result.data:
            data.append({
                "timestamp": data_point.timestamp,
                "region": region,
                "metric": timeseries.metric,
                "value": data_point.value,
                "unit": timeseries.unit
            })

df = pd.DataFrame(data)
print(df.head(100))
print(df.tail(100))