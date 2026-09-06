import pandas as pd
import numpy as np

# Load the datasets
app_data = pd.read_csv('data/app_channel_data.csv')
ussd_data = pd.read_csv('data/ussd_channel_data.csv')

# Define target features
app_features = ['typing_speed_deviation', 'pasted_char_ratio', 'screen_sequence_anomaly', 'amount_deviation']
ussd_features = ['amount_deviation', 'time_of_day_deviation', 'session_retry_deviation', 'sim_swap_risk']

results = []

# Process app_data
app_normal = app_data[app_data['label'] == 0]
for feat in app_features:
    abs_values = app_normal[feat].abs()
    p90 = abs_values.quantile(0.90)
    p95 = abs_values.quantile(0.95)
    results.append({'feature': feat, 'channel': 'app', 'p90': p90, 'p95': p95})

# Process ussd_data
ussd_normal = ussd_data[ussd_data['label'] == 0]
for feat in ussd_features:
    abs_values = ussd_normal[feat].abs()
    p90 = abs_values.quantile(0.90)
    p95 = abs_values.quantile(0.95)
    results.append({'feature': feat, 'channel': 'ussd', 'p90': p90, 'p95': p95})

# Print the table
print(f"{'Feature':<25} | {'Channel':<8} | {'90th Percentile':<15} | {'95th Percentile':<15}")
print("-" * 75)
for row in results:
    print(f"{row['feature']:<25} | {row['channel']:<8} | {row['p90']:<15.4f} | {row['p95']:<15.4f}")
