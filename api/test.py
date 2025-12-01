"""
Simple test function to verify Vercel Python function format
"""
import json

def handler(request):
    """Test handler to verify request format"""
    try:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Test function works',
                'request_type': str(type(request)),
                'request_keys': list(request.keys()) if isinstance(request, dict) else 'Not a dict',
                'method': request.get('method') if isinstance(request, dict) else 'N/A',
                'body_type': str(type(request.get('body'))) if isinstance(request, dict) else 'N/A'
            })
        }
    except Exception as e:
        import traceback
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        }

