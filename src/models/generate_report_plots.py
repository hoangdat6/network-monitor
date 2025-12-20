
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix, roc_curve, precision_recall_curve, auc
from sklearn.model_selection import train_test_split
import joblib
import json
import os
import sys

# Setup Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "model_outputs_v5")
FIGURES_DIR = os.path.join(BASE_DIR, "report_figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

PATH_2019 = os.path.join(DATA_DIR, "cicddos2019_binary_processed.csv")
PATH_2017 = os.path.join(DATA_DIR, "cicids2017_binary_processed.csv")

# Set Visual Style
sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 12})

# ==========================================
# 1. HELPERS
# ==========================================
def clean_df(df):
    return df.replace([np.inf, -np.inf], np.nan).dropna()

def first_existing_series(df, candidates):
    for c in candidates:
        if c in df.columns:
            return df[c]
    return None

def add_derived_features(df):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = pd.to_numeric(df[c], errors='ignore')

    if 'total_fwd_packets' not in df.columns:
        df['total_fwd_packets'] = 0
    if 'total_backward_packets' not in df.columns:
        if 'total_backwards_packets' in df.columns:
            df['total_backward_packets'] = df['total_backwards_packets']
        else:
            df['total_backward_packets'] = 0

    df['total_packets'] = df['total_fwd_packets'].fillna(0) + df['total_backward_packets'].fillna(0)

    fwd_candidates = ['fwd_packets_length_total', 'total_length_of_fwd_packets', 'subflow_fwd_bytes', 'Subflow Fwd Bytes', 'subflow_fwd_bytes']
    bwd_candidates = ['bwd_packets_length_total', 'total_length_of_bwd_packets', 'subflow_bwd_bytes', 'Subflow Bwd Bytes', 'subflow_bwd_bytes']

    fwd_bytes = first_existing_series(df, fwd_candidates)
    bwd_bytes = first_existing_series(df, bwd_candidates)
    
    df['total_fwd_bytes'] = fwd_bytes.fillna(0) if fwd_bytes is not None else 0
    df['total_bwd_bytes'] = bwd_bytes.fillna(0) if bwd_bytes is not None else 0
    df['total_bytes'] = df['total_fwd_bytes'] + df['total_bwd_bytes']

    if 'flow_duration' in df.columns:
        df['flow_duration'] = pd.to_numeric(df['flow_duration'], errors='coerce').fillna(0).clip(lower=0) + 1e-6
    else:
        df['flow_duration'] = 1.0

    df['packet_rate'] = df['total_packets'] / df['flow_duration']
    df['byte_rate'] = df['total_bytes'] / df['flow_duration']
    
    df['mean_packet_size'] = (df['total_bytes'] / df['total_packets'].replace({0: np.nan})).fillna(0)
    df['fwd_ratio'] = (df['total_fwd_packets'] / df['total_packets'].replace({0: np.nan})).fillna(0)

    # iat_range if columns exist (safe)
    if 'flow_iat_max' in df.columns and 'flow_iat_min' in df.columns:
        df['iat_range'] = (pd.to_numeric(df['flow_iat_max'], errors='coerce').fillna(0) -
                           pd.to_numeric(df['flow_iat_min'], errors='coerce').fillna(0)).clip(lower=0)
    else:
        df['iat_range'] = 0.0
    
    df['log_packet_rate'] = np.log1p(df['packet_rate'].clip(lower=0))
    df['log_byte_rate'] = np.log1p(df['byte_rate'].clip(lower=0))
    df['log_total_bytes'] = np.log1p(df['total_bytes'].clip(lower=0))
    df['log_total_packets'] = np.log1p(df['total_packets'].clip(lower=0))
    
    return df

# ==========================================
# 2. LOAD DATA
# ==========================================
print("Loading Data...")
df_2019 = pd.read_csv(PATH_2019)
df_2017 = pd.read_csv(PATH_2017)

df_2019 = clean_df(df_2019)
df_2017 = clean_df(df_2017)

df_2019 = add_derived_features(df_2019)
df_2017 = add_derived_features(df_2017)

# Split 2017 (Sample vs Test) - Matching V5 logic
df_2017_test, df_2017_sample = train_test_split(
    df_2017, test_size=0.03, stratify=df_2017['label'], random_state=42
)
# Train Mix (for V5 replication context, though we only need Test for plotting results usually)
# df_train_mix = pd.concat([df_2019, df_2017_sample], axis=0) # For EDA

# ==========================================
# 3. LOAD ARTIFACTS
# ==========================================
print("Loading Model Artifacts...")
model = joblib.load(os.path.join(OUTPUT_DIR, "xgb_calibrated_model_reduced.joblib"))
features = joblib.load(os.path.join(OUTPUT_DIR, "features_reduced.pkl"))

with open(os.path.join(OUTPUT_DIR, "threshold_reduced.json"), "r") as f:
    best_threshold = json.load(f)["threshold"]

print(f"Model loaded. Selected Features: {len(features)}")
print(f"Optimal Threshold: {best_threshold}")

# Prepare Test Data
X_test = df_2017_test[features]
y_test = df_2017_test['label']

# Predict
print("Predicting...")
y_prob = model.predict_proba(X_test)[:, 1]
y_pred = (y_prob >= best_threshold).astype(int)

# ==========================================
# 4. GENERATE PLOTS
# ==========================================

# --- 4.1 EDA: Class Distribution ---
print("Generating EDA Plot...")
plt.figure(figsize=(10, 5))
counts_19 = df_2019['label'].value_counts(normalize=True).sort_index()
counts_17 = df_2017['label'].value_counts(normalize=True).sort_index()

bar_width = 0.35
index = np.arange(2)

p1 = plt.bar(index, counts_19, bar_width, label='Source (2019)', alpha=0.8, color='#3498db')
p2 = plt.bar(index + bar_width, counts_17, bar_width, label='Target (2017)', alpha=0.8, color='#e74c3c')

plt.xlabel('Label')
plt.ylabel('Proportion')
plt.title('Class Distribution: Source vs Target')
plt.xticks(index + bar_width / 2, ['Benign', 'Attack'])
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIGURES_DIR, "1_eda_class_distribution.png"))
plt.close()


# --- 4.2 ROC & PR Curve ---
print("Generating ROC & PR Curves...")
fpr, tpr, _ = roc_curve(y_test, y_prob)
roc_auc = auc(fpr, tpr)
precision, recall, _ = precision_recall_curve(y_test, y_prob)
pr_auc = auc(recall, precision)

plt.figure(figsize=(14, 6))

# ROC
plt.subplot(1, 2, 1)
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.4f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.xlim([-0.01, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Receiver Operating Characteristic (ROC)')
plt.legend(loc="lower right")

# PR
plt.subplot(1, 2, 2)
plt.plot(recall, precision, color='green', lw=2, label=f'PR curve (area = {pr_auc:.4f})')
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.title('Precision-Recall Curve')
plt.legend(loc="lower left")

plt.tight_layout()
plt.savefig(os.path.join(FIGURES_DIR, "2_roc_pr_curves.png"))
plt.close()


# --- 4.3 Threshold Tuning (F1 Score) ---
print("Generating Threshold Tuning Plot...")
# Calculate F1 for all thresholds
prec, rec, thresh = precision_recall_curve(y_test, y_prob)
f1_scores = 2 * (prec * rec) / (prec + rec)
# Remove nan
f1_scores = np.nan_to_num(f1_scores)

# Trim last element of prec/rec to match thresholds length
plt.figure(figsize=(10, 6))
plt.plot(thresh, f1_scores[:-1], label='F1 Score', color='blue')
plt.axvline(best_threshold, color='red', linestyle='--', label=f'Selected Threshold ({best_threshold:.3f})')
plt.xlabel('Threshold')
plt.ylabel('F1 Score')
plt.title('F1 Score vs Decision Threshold')
plt.legend(loc="best")
plt.savefig(os.path.join(FIGURES_DIR, "3_threshold_tuning.png"))
plt.close()


# --- 4.4 Prediction Distribution ---
print("Generating Prediction Distribution Plot...")
plt.figure(figsize=(10, 6))
sns.histplot(y_prob[y_test == 0], color="skyblue", label="Actual Benign", kde=True, stat="density", element="step")
sns.histplot(y_prob[y_test == 1], color="red", label="Actual Attack", kde=True, stat="density", element="step", alpha=0.5)
plt.axvline(best_threshold, color='green', linestyle='--', label='Threshold')
plt.yscale('log')
plt.title('Prediction Probability Distribution (Log Scale)')
plt.xlabel('Predicted Probability (Attack)')
plt.ylabel('Density (Log)')
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIGURES_DIR, "4_prediction_distribution.png"))
plt.close()


# --- 4.5 Confusion Matrix ---
print("Generating Confusion Matrix Plot...")
cm = confusion_matrix(y_test, y_pred)
# Normalized
cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

plt.figure(figsize=(8, 6))
sns.heatmap(cm_norm, annot=True, fmt='.2%', cmap='Blues', cbar=False,
            xticklabels=['Predicted Benign', 'Predicted Attack'],
            yticklabels=['True Benign', 'True Attack'])
plt.title(f'Confusion Matrix (Normalized)\nThreshold: {best_threshold:.3f}')
plt.ylabel('True Class')
plt.xlabel('Predicted Class')
plt.tight_layout()
plt.savefig(os.path.join(FIGURES_DIR, "5_confusion_matrix.png"))
plt.close()

print(f"All plots saved to {FIGURES_DIR}")
