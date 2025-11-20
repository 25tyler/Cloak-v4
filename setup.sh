#!/bin/bash
# Automated Setup Script
# Runs everything automatically - you just need to deploy

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Automated Setup Script"
echo "=========================================="
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
    echo ""
fi

# Step 1: Install Python dependencies
echo "Step 1: Installing Python dependencies..."
cd backend
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"
echo ""

# Step 2: Install fonttools for font generation (if not in requirements)
echo "Step 2: Installing fonttools..."
pip install fonttools brotli --quiet
echo "✅ Fonttools installed"
echo ""

# Step 3: Generate font
echo "Step 3: Generating encrypted font..."
cd ..
python3 generate_font.py
echo ""

# Step 4: Create fonts directory structure
echo "Step 4: Setting up directories..."
mkdir -p fonts
mkdir -p client
echo "✅ Directories ready"
echo ""

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps (manual):"
echo "1. Upload fonts/encrypted.woff2 to CDN"
echo "2. Update backend/encrypt_api.py with font URL"
echo "3. Deploy backend to Heroku/AWS/etc"
echo "4. Update client/encrypt-articles.js with API URL"
echo "5. Upload client/encrypt-articles.js to CDN"
echo ""

