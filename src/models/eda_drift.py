
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import ks_2samp

# 1. Load Data
PATH_2019 = "data/cicddos2019_binary_processed.csv"
PATH_2017 = "data/cicids2017_binary_processed.csv"

print(f"Loading 2019...")
df_2019 = pd.read_csv(PATH_2019)
print(f"Loading 2017...")
df_2017 = pd.read_csv(PATH_2017)

# Clean
def clean_df(df):
    return df.replace([np.inf, -np.inf], np.nan).dropna()
df_2019 = clean_df(df_2019)
df_2017 = clean_df(df_2017)

# 2. Add Basic Features for comparison
def add_features(df):
    df['total_packets'] = df.get('total_fwd_packets', 0) + df.get('total_backward_packets', 0)
    df['flow_duration'] = pd.to_numeric(df.get('flow_duration', 1.0), errors='coerce').fillna(1.0)
    # Packet Rate
    df['packet_rate'] = df['total_packets'] / (df['flow_duration'].clip(lower=1e-6))
    return df

df_2019 = add_features(df_2019)
df_2017 = add_features(df_2017)

# 3. Analyze Distribution Shift (Benign Only)
# We compare the 'Normal' traffic of both networks to see how different the 'Baseline' is.
benign_2019 = df_2019[df_2019['label'] == 0]
benign_2017 = df_2017[df_2017['label'] == 0]

print(f"Benign 2019 samples: {len(benign_2019)}")
print(f"Benign 2017 samples: {len(benign_2017)}")

# Check key statistics for a few critical features
features_to_check = ['packet_rate', 'flow_duration', 'total_fwd_packets', 'ack_flag_count']
# Ensure columns exist
features_to_check = [f for f in features_to_check if f in benign_2019.columns and f in benign_2017.columns]

print("\n--- Distribution Statistics (Mean / Median) ---")
results = []
for f in features_to_check:
    mean_19 = benign_2019[f].mean()
    mean_17 = benign_2017[f].mean()
    median_19 = benign_2019[f].median()
    median_17 = benign_2017[f].median()
    ratio_mean = mean_19 / mean_17 if mean_17 != 0 else np.nan
    
    results.append({
        'feature': f,
        'mean_2019': mean_19,
        'mean_2017': mean_17,
        'ratio (19/17)': ratio_mean,
        'median_2019': median_19,
        'median_2017': median_17
    })

res_df = pd.DataFrame(results)
print(res_df)

# 4. Plot Distributions
print("\nGenerating Plots...")
plt.figure(figsize=(15, 5))

for i, f in enumerate(features_to_check[:3]): # Plot first 3
    plt.subplot(1, 3, i+1)
    # Log scale often helps with network data
    sns.kdeplot(np.log1p(benign_2019[f]), label='2019 (Source)', fill=True, alpha=0.3)
    sns.kdeplot(np.log1p(benign_2017[f]), label='2017 (Target)', fill=True, alpha=0.3)
    plt.title(f"Log Distribution of {f}")
    plt.legend()

plt.tight_layout()
plt.savefig("distribution_check.png")
print("Saved plot to distribution_check.png")
