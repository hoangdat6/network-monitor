#!/usr/bin/env python3
"""
Model Exporter - Copy models to detection directory

Quick script to verify and copy trained models
"""

import os
import shutil
from pathlib import Path

# Paths
NOTEBOOK_DIR = Path(__file__).parent
TARGET_DIR = NOTEBOOK_DIR.parent.parent / 'detection' / 'ddos-detector' / 'models'

MODEL_FILES = [
    'rf_ddos_model.pkl',
    'rf_scaler.pkl',
    'rf_label_encoder.pkl',
    'rf_features.pkl'
]

def main():
    print("🔍 Checking trained models...")
    
    # Check if models exist
    missing = []
    for filename in MODEL_FILES:
        filepath = NOTEBOOK_DIR / filename
        if not filepath.exists():
            missing.append(filename)
            print(f"   ❌ Missing: {filename}")
        else:
            size = filepath.stat().st_size / 1024  # KB
            print(f"   ✅ Found: {filename} ({size:.1f} KB)")
    
    if missing:
        print("\n❗ Please run the notebook to train and export models first!")
        return
    
    # Create target directory
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Target directory: {TARGET_DIR}")
    
    # Copy models
    print("\n📦 Copying models...")
    for filename in MODEL_FILES:
        src = NOTEBOOK_DIR / filename
        dst = TARGET_DIR / filename
        shutil.copy2(src, dst)
        print(f"   ✅ Copied: {filename}")
    
    print("\n✨ Models exported successfully!")
    print(f"\nModels are ready in: {TARGET_DIR}")
    print("\nNext steps:")
    print("  1. cd ../../src")
    print("  2. docker-compose -f docker-compose.network.yml up -d --build ddos-detector")

if __name__ == "__main__":
    main()
