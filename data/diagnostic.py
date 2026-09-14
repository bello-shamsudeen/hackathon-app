import pandas as pd
import numpy as np

old = pd.read_csv(r'C:\Users\Maryam Bello\OneDrive\Desktop\hackathon-app\data\old_app_channel_data.csv', encoding='utf-16')
new = pd.read_csv(r'C:\Users\Maryam Bello\OneDrive\Desktop\hackathon-app\data\app_channel_data.csv')

print('=' * 60)
print('FRESH DIAGNOSTIC: app_channel_data.csv (newly regenerated)')
print('=' * 60)

# 1. first_action_deviation by label
print()
print('1. first_action_deviation mean by label:')
for label in [0, 1]:
    subset = new[new['label'] == label]
    print('   label=%d: %.4f' % (label, subset['first_action_deviation'].mean()))

# 2. pasted_char_ratio: mean and label==0 95th percentile
print()
print('2. pasted_char_ratio:')
print('   Overall mean:', new['pasted_char_ratio'].mean())
for label in [0, 1]:
    subset = new[new['label'] == label]
    print('   label=%d mean: %.4f' % (label, subset['pasted_char_ratio'].mean()))
    if label == 0:
        p95 = subset['pasted_char_ratio'].quantile(0.95)
        old_p95 = old[old['label'] == 0]['pasted_char_ratio'].quantile(0.95)
        print('   label=0 95th pct: NEW=%.4f  OLD=%.4f  delta=%+.4f' % (p95, old_p95, p95 - old_p95))

# 3. typing_speed_deviation and amount_deviation by label
print()
print('3. typing_speed_deviation:')
for label in [0, 1]:
    old_subset = old[old['label'] == label]
    new_subset = new[new['label'] == label]
    print('   label=%d:' % label)
    print('     mean:  NEW=%.4f  OLD=%.4f  delta=%+.4f' % (new_subset['typing_speed_deviation'].mean(), old_subset['typing_speed_deviation'].mean(), new_subset['typing_speed_deviation'].mean() - old_subset['typing_speed_deviation'].mean()))
    print('     std:   NEW=%.4f  OLD=%.4f  delta=%+.4f' % (new_subset['typing_speed_deviation'].std(), old_subset['typing_speed_deviation'].std(), new_subset['typing_speed_deviation'].std() - old_subset['typing_speed_deviation'].std()))

print()
print('   amount_deviation:')
for label in [0, 1]:
    old_subset = old[old['label'] == label]
    new_subset = new[new['label'] == label]
    print('   label=%d:' % label)
    print('     mean:  NEW=%.4f  OLD=%.4f  delta=%+.4f' % (new_subset['amount_deviation'].mean(), old_subset['amount_deviation'].mean(), new_subset['amount_deviation'].mean() - old_subset['amount_deviation'].mean()))
    print('     std:   NEW=%.4f  OLD=%.4f  delta=%+.4f' % (new_subset['amount_deviation'].std(), old_subset['amount_deviation'].std(), new_subset['amount_deviation'].std() - old_subset['amount_deviation'].std()))