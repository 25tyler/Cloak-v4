"""
Vercel serverless function wrapper for Flask app
Uses vercel-python-wsgi adapter
"""
import sys
import os

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from encrypt_api import app

# Export the Flask app for Vercel
# Vercel will automatically detect and use it

