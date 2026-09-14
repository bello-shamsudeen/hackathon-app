import pandas as pd
import joblib
from sklearn.model_selection import train_test_split

df = pd.read_csv('data/app_channel_data.csv')
features = ['typing_speed_deviation', 'pasted_char_ratio', 'first_action_deviation', 'amount_deviation']
target = 'label'

X = df[features]
y = df[target]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

print('1. X_train.columns:', X_train.columns.tolist())
print('   X_test.columns:', X_test.columns.tolist())

model = joblib.load('models/app_model.pkl')
print()
print('3. Feature importances:')
for name, imp in zip(features, model.feature_importances_):
    print('   %s: %s' % (name, imp))

print()
print('4. Feature min/max by label:')
for feat in features:
    vals_0 = df[df['label'] == 0][feat]
    vals_1 = df[df['label'] == 1][feat]
    print('   %s:' % feat)
    print('     label=0: min=%.4f max=%.4f' % (vals_0.min(), vals_0.max()))
    print('     label=1: min=%.4f max=%.4f' % (vals_1.min(), vals_1.max()))

print()
print('   Overlap check (label=0 max < label=1 min):')
for feat in features:
    max_0 = df[df['label'] == 0][feat].max()
    min_1 = df[df['label'] == 1][feat].min()
    print('   %s: max(label=0)=%.4f < min(label=1)=%.4f ? %s' % (feat, max_0, min_1, max_0 < min_1))

print()
print('2. y_pred source verification:')
print('   X_test shape:', X_test.shape, 'y_test shape:', y_test.shape)
print('   y_test size:', len(y_test))
print('   y_pred = clf.predict(X_test)  <-- exact line')