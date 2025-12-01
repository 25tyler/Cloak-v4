"""
Vercel serverless function wrapper for Flask app
Routes API requests to Flask app endpoints using vercel-python-wsgi
"""
import sys
import os

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from encrypt_api import app

# For Vercel, we can use the Flask app directly if we have vercel-python-wsgi
# Otherwise, we need to create a handler that converts Vercel request to WSGI
try:
    from vercel import wsgi
    handler = wsgi(app)
except ImportError:
    # Fallback: create a simple handler
    def handler(request):
        """Simple handler that returns API info"""
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': '{"message": "API endpoint - use /api/encrypt/pdf for PDF encryption"}'
        }

