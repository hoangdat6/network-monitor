import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.ensemble import IsolationForest
import joblib
import os
import json

class DriftMonitor:
    def __init__(self, features, p_value_threshold=0.05):
        """
        Monitor for data drift using Kolmogorov-Smirnov (KS) Test.
        
        Args:
            features (list): List of numerical features to monitor.
            p_value_threshold (float): Threshold for p-value. If p < threshold, drift is detected.
        """
        self.features = features
        self.p_value_threshold = p_value_threshold
        self.baseline_stats = {}
        self.baseline_data = None

    def fit_baseline(self, df_baseline):
        """
        Store the baseline data (or a sample of it) for comparison.
        """
        # Store a sample to keep memory usage low if dataset is huge, 
        # but for accuracy we keep as much as reasonable.
        # Let's cap at 10,000 samples for the baseline reference to ensure speed.
        if len(df_baseline) > 10000:
            self.baseline_data = df_baseline[self.features].sample(n=10000, random_state=42)
        else:
            self.baseline_data = df_baseline[self.features].copy()
            
        print(f"DriftMonitor: Baseline fitted with {len(self.baseline_data)} samples.")

    def check_drift(self, df_current):
        """
        Compare current data batch against baseline.
        Returns a dict of drift results per feature.
        """
        drift_report = {}
        drift_detected = False
        
        for feature in self.features:
            if feature not in df_current.columns:
                continue
                
            # KS Test
            # Null Hypothesis (H0): Two samples are drawn from the same distribution.
            # If p-value < threshold, we reject H0 -> Drift Detected.
            stat, p_value = ks_2samp(self.baseline_data[feature], df_current[feature])
            
            is_drift = p_value < self.p_value_threshold
            
            drift_report[feature] = {
                'p_value': p_value,
                'drift_detected': is_drift,
                'ks_stat': stat
            }
            if is_drift:
                drift_detected = True
                
        return drift_detected, drift_report
    
    def save(self, path):
        joblib.dump(self, path)
        
    @staticmethod
    def load(path):
        return joblib.load(path)


class AnomalyDetector:
    def __init__(self, contamination=0.01, random_state=42):
        """
        Wrapper for Isolation Forest to detect unknown attacks.
        
        Args:
            contamination (float): Expected proportion of outliers in the data.
                                   In a 'Zero Trust' model, we might set this low 
                                   to only catch extreme outliers, or tune it.
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1
        )
        self.features = None

    def fit(self, X):
        """
        Fit on BENIGN data (mostly) to learn normality.
        """
        self.features = X.columns.tolist()
        self.model.fit(X)
        print("AnomalyDetector: Fitted IsolationForest.")

    def predict(self, X):
        """
        Returns:
            1 for Inliers (Normal)
            -1 for Outliers (Anomaly/Possible Attack)
        """
        return self.model.predict(X)

    def score_samples(self, X):
        """
        Opposite of the anomaly score defined in the original paper.
        The lower, the more abnormal.
        """
        return self.model.score_samples(X)
    
    def save(self, path):
        joblib.dump(self, path)
    
    @staticmethod
    def load(path):
        return joblib.load(path)
