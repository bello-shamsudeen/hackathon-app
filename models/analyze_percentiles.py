import pandas as pd

# Load data
app_df = pd.read_csv("data/app_channel_data.csv")
ussd_df = pd.read_csv("data/ussd_channel_data.csv")

# Verify first_action_deviation exists in app data
if "first_action_deviation" not in app_df.columns:
    print("STOP: Brief A's data hasn't been regenerated yet — first_action_deviation not found in app_channel_data.csv")
    exit(1)

# APP channel: only label==0 rows, 95th percentile of abs(typing_speed_deviation), abs(pasted_char_ratio), abs(amount_deviation)
app_normal = app_df[app_df["label"] == 0]

app_features = ["typing_speed_deviation", "pasted_char_ratio", "amount_deviation"]
app_percentiles = {}
for feat in app_features:
    app_percentiles[feat] = app_normal[feat].abs().quantile(0.95)

# USSD channel: 95th percentile of all 4 features
ussd_features = ["amount_deviation", "time_of_day_deviation", "session_retry_deviation", "sim_swap_risk"]
ussd_percentiles = {}
for feat in ussd_features:
    ussd_percentiles[feat] = ussd_df[feat].quantile(0.95)

# Print clean table
print(f"{'Feature':<30} {'APP (label==0)':<20} {'USSD':<20}")
print("-" * 70)

# Determine max row span
all_features = sorted(set(app_features + ussd_features))

# Print APP rows
for feat in app_features:
    print(f"{feat:<30} {app_percentiles[feat]:<20.6f} {'—':<20}")

print("-" * 70)

# Print USSD rows
for feat in ussd_features:
    print(f"{feat:<30} {'—':<20} {ussd_percentiles[feat]:<20.6f}")

print("-" * 70)

# Print combined section for shared features
shared = set(app_features) & set(ussd_features)
if shared:
    print(f"\n{'Feature':<30} {'APP (label==0)':<20} {'USSD':<20}")
    print("-" * 70)
    for feat in sorted(shared):
        print(f"{feat:<30} {app_percentiles[feat]:<20.6f} {ussd_percentiles[feat]:<20.6f}")
