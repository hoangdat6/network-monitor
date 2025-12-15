#!/bin/bash
# Script to extract final_model from compressed archive
# Run this after cloning the repository

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MODEL_DIR="$SCRIPT_DIR/src/models/final_model"
ARCHIVE="$SCRIPT_DIR/src/models/final_model.tar.gz"

echo "🔧 Extracting final_model..."

# Check if archive exists
if [ ! -f "$ARCHIVE" ]; then
    echo "❌ Error: Archive not found at $ARCHIVE"
    exit 1
fi

# Create directory if it doesn't exist
mkdir -p "$MODEL_DIR"

# Extract
echo "📦 Extracting to $MODEL_DIR"
tar -xzf "$ARCHIVE" -C "$MODEL_DIR"

# Verify extraction
if [ -f "$MODEL_DIR/xgb_calibrated_model_reduced.joblib" ]; then
    echo "✅ Model files extracted successfully!"
    echo ""
    echo "Files:"
    ls -lh "$MODEL_DIR"
else
    echo "❌ Error: Extraction failed"
    exit 1
fi

echo ""
echo "🚀 Ready to use! You can now run:"
echo "   cd src && docker-compose -f docker-compose.network.yml up -d"
