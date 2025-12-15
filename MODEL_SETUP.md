# Model Setup Guide

## Problem
The XGBoost model file (`xgb_calibrated_model_reduced.joblib`) is 63MB, which is too large to push directly to Git.

## Solution
Model files are compressed into `src/models/final_model.tar.gz` (21MB compressed).

## Setup Instructions

### After cloning the repository:

1. **Extract the model files:**
   ```bash
   ./setup_models.sh
   ```

   Or manually:
   ```bash
   cd src/models
   tar -xzf final_model.tar.gz -C final_model/
   ```

2. **Verify extraction:**
   ```bash
   ls -lh src/models/final_model/
   ```

   You should see:
   - `xgb_calibrated_model_reduced.joblib` (63MB)
   - `features_reduced.pkl` (588 bytes)
   - `threshold_reduced.json` (88 bytes)

3. **Start the services:**
   ```bash
   cd src
   docker-compose -f docker-compose.network.yml up -d
   ```

## Files Structure

```
src/models/
├── final_model.tar.gz          # Compressed archive (tracked by Git)
├── final_model/                 # Extracted files (ignored by Git)
│   ├── xgb_calibrated_model_reduced.joblib
│   ├── features_reduced.pkl
│   └── threshold_reduced.json
└── ...
```

## For Developers

### Re-compressing the model after updates:

```bash
cd src/models/final_model
tar -czf ../final_model.tar.gz *
```

### What's tracked by Git:
- ✅ `src/models/final_model.tar.gz` (compressed)
- ❌ `src/models/final_model/*.joblib` (ignored)
- ❌ `src/models/final_model/features_reduced.pkl` (ignored)
- ✅ `src/models/final_model/threshold_reduced.json` (small, tracked)

## Alternative: Git LFS

If you prefer, you can use Git Large File Storage:

```bash
# Install Git LFS
git lfs install

# Track large files
git lfs track "*.joblib"
git add .gitattributes
git add src/models/final_model/*.joblib
git commit -m "Add model files with Git LFS"
```

## Troubleshooting

**Q: Model files not found error when running containers?**
```bash
# Make sure you extracted the archive
./setup_models.sh

# Verify files exist
ls -lh src/models/final_model/
```

**Q: How to update the model?**
```bash
# 1. Train new model (generates files in final_model/)
# 2. Compress it
cd src/models/final_model
tar -czf ../final_model.tar.gz *

# 3. Commit
git add ../final_model.tar.gz
git commit -m "Update model"
```
