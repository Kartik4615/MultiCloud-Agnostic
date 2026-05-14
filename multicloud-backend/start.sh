#!/bin/bash
echo "================================================"
echo "  MultiCloud Backend - Local Setup"
echo "================================================"
echo ""

echo "[1/3] Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "[2/3] Dependencies installed!"
echo ""
echo "[3/3] Starting Flask on http://localhost:5000"
echo "      Press Ctrl+C to stop."
echo ""
python app.py
