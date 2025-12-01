"""
Vercel serverless function wrapper for Flask app
Routes API requests to Flask app endpoints using vercel-python-wsgi

IMPORTANT: Do NOT import Flask app at module level - it causes Vercel handler detection errors
Import it inside the handler function instead
"""
import sys
import os

# Define handler function first to avoid Vercel detection issues
def handler(request):
    """Handle API requests - routes to Flask app or returns info"""
    # Add parent directory to path inside handler to avoid module-level import issues
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Import Flask app inside handler to avoid Vercel's issubclass() detection error
    # Vercel tries to check if module-level objects are classes, and Flask app is an instance
    try:
        from encrypt_api import app
        
        # Try to use vercel-python-wsgi if available
        try:
            from vercel import wsgi
            return wsgi(app)(request)
        except ImportError:
            # Fallback: return simple message
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': '{"message": "API endpoint - use /api/encrypt/pdf for PDF encryption"}'
            }
    except Exception as e:
        import traceback
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': f'{{"error": "Failed to load Flask app: {str(e)}", "traceback": "{traceback.format_exc()}"}}'
        }

