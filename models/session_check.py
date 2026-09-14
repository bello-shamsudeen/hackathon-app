import pandas as pd
import sys

# Old data (UTF-16 encoded)
old_df = pd.read_csv('data/old_app_channel_data.csv', encoding='utf-16')

# New data
new_df = pd.read_csv('data/app_channel_data.csv')

old_fraud_ids = set(old_df[old_df['label']==1]['session_id'])
new_fraud_ids = set(new_df[new_df['label']==1]['session_id'])

print('OLD only:', len(old_fraud_ids - new_fraud_ids))
print('NEW only:', len(new_fraud_ids - old_fraud_ids))
print('BOTH:', len(old_fraud_ids & new_fraud_ids))