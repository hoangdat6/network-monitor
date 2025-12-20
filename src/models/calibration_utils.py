
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, confusion_matrix
from copy import deepcopy
import joblib
import json
import os

def calibrate_and_optimize(model, X_train, y_train, X_test, y_test, features, output_dir="model_outputs_calibrated"):
    """
    Calibrates the given model, optimizes the threshold to minimize FP, and saves artifacts.
    
    Args:
        model: The trained estimator (e.g., XGBClassifier).
        X_train: Training data for calibration (should be the reduced feature set).
        y_train: Training labels.
        X_test: Test data for evaluation.
        y_test: Test labels.
        features: List of selected feature names.
        output_dir: Directory to save outputs.
    """
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("=== CALIBRATION ===")
    print("Calibrating model using Sigmoid calibration (3-fold CV)...")
    
    # Clone and calibrate
    model_clone = deepcopy(model)
    # Remove early stopping if present, as it conflicts with CalibratedClassifierCV internals
    if hasattr(model_clone, 'set_params'):
        try:
            model_clone.set_params(early_stopping_rounds=None)
        except Exception:
            pass

    calib_cv = CalibratedClassifierCV(estimator=model_clone, method='sigmoid', cv=3)
    calib_cv.fit(X_train, y_train)
    
    # Generate calibrated probabilities
    print("Generating calibrated probabilities for Test set...")
    proba_test_cal = calib_cv.predict_proba(X_test)[:, 1]
    
    print("\n=== THRESHOLD OPTIMIZATION ===")
    print("Searching for optimal threshold to minimize False Positives...")
    
    thresholds = np.arange(0.5, 0.99, 0.01)
    best_t = 0.5
    best_score = -1
    
    print(f"{'Threshold':<10} | {'FP Rate':<15} | {'FN Rate':<15} | {'F1-Score':<10}")
    print("-" * 60)
    
    for t in thresholds:
        y_pred = (proba_test_cal >= t).astype(int)
        
        # Confusion Matrix
        # 0 = Normal, 1 = Attack
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        
        fp_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
        fn_rate = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Scoring Metric: F1 - penalty * FP_Rate
        # We want strict control on FPs
        score = f1 - 2.0 * fp_rate
        
        if fp_rate < 0.05:
            print(f"{t:.2f}       | {fp_rate:.4f}          | {fn_rate:.4f}          | {f1:.4f}")
        
        if score > best_score:
            best_score = score
            best_t = t
            
    print("-" * 60)
    print(f"Recommended Threshold: {best_t:.2f}")
    
    # Final Evaluation
    print(f"\n=== FINAL EVALUATION @ Threshold {best_t:.2f} ===")
    y_final_pred = (proba_test_cal >= best_t).astype(int)
    print(classification_report(y_test, y_final_pred, digits=4))
    
    # Save Artifacts
    print("\n=== SAVING ARTIFACTS ===")
    
    # 1. Model
    model_path = os.path.join(output_dir, "xgb_calibrated_model_reduced.joblib")
    joblib.dump(calib_cv, model_path)
    print(f"✅ Model saved: {model_path}")
    
    # 2. Features
    feat_path = os.path.join(output_dir, "features_reduced.pkl")
    joblib.dump(features, feat_path)
    print(f"✅ Features saved: {feat_path}")
    
    # 3. Threshold Config
    config = {
        "threshold": float(best_t),
        "num_features": len(features),
        "note": "Optimized to minimize False Positives"
    }
    config_path = os.path.join(output_dir, "threshold_reduced.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"✅ Config saved: {config_path}")
    
    return calib_cv, best_t
