"""
Vercel serverless function for PDF encryption endpoint
Vercel Python runtime format

IMPORTANT: Keep imports minimal at module level to avoid Vercel handler detection issues
Vercel expects a simple function handler, not a class-based handler
"""
import sys
import os
import json
import tempfile
import base64

# Define DEFAULT_SECRET_KEY directly to avoid importing Flask and other heavy dependencies
# This matches the value from encrypt_api.py
# Do this at module level but keep it simple
try:
    DEFAULT_SECRET_KEY = int(os.environ.get('DEFAULT_SECRET_KEY', '29202393'))
except (ValueError, TypeError):
    DEFAULT_SECRET_KEY = 29202393

# Vercel Python functions need the handler to be exported at module level
# The function signature should match Vercel's expected format: handler(request)
# This must be a simple function, not a class method
def handler(request):
    """Handle PDF encryption request - Vercel serverless function format"""
    # Add parent directory to path inside handler to avoid Vercel detection issues
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Add logging at the very start to debug
    print(f"Handler called with request type: {type(request)}")
    if isinstance(request, dict):
        print(f"Request keys: {list(request.keys())}")
        print(f"Request method: {request.get('method', 'N/A')}")
        print(f"Request body type: {type(request.get('body', None))}")
        print(f"Request body preview: {str(request.get('body', ''))[:100]}")
    
    try:
        # Handle case where request might not be a dict (Vercel might pass it differently)
        if not isinstance(request, dict):
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Invalid request format. Expected dict, got {type(request).__name__}'})
            }
        
        # Parse request - Vercel Python format
        # Request object has: method, path, headers, body, query
        method = request.get('method', 'GET')
        if method != 'POST':
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
        # Get body from request (Vercel Python runtime format)
        # Vercel passes body as a string that needs to be parsed
        body = request.get('body', '')
        
        # Parse JSON body - handle both string and already-parsed dict
        try:
            if isinstance(body, str):
                # If body is a string, parse it
                if body:
                    data = json.loads(body)
                else:
                    data = {}
            elif isinstance(body, dict):
                # If body is already a dict, use it directly
                data = body
            else:
                data = {}
        except (json.JSONDecodeError, TypeError) as e:
            # Log the error for debugging
            error_msg = f"Error parsing request body: {e}, body type: {type(body)}, body preview: {str(body)[:200]}"
            print(error_msg)
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': error_msg})
            }
        
        # Check if file is provided
        if 'file' not in data:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'No file provided', 'received_keys': list(data.keys())})
            }
        
        # Get file data (base64 encoded)
        try:
            file_data = base64.b64decode(data['file'])
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Invalid base64 file data: {str(e)}'})
            }
        filename = data.get('filename', 'document.pdf')
        
        # Get secret key
        secret_key = data.get('secret_key')
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
            try:
                secret_key = int(secret_key)
            except (ValueError, TypeError):
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'secret_key must be an integer'})
                }
        
        # Import PDF processing - do this inside the try block to catch all errors
        # These imports might fail if dependencies aren't available
        print("Starting PDF processing imports...")
        try:
            print("Importing fitz (PyMuPDF)...")
            import fitz  # PyMuPDF
            print("fitz imported successfully")
        except ImportError as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"ERROR importing fitz: {e}\n{error_trace}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'error': f'PyMuPDF (fitz) not available: {str(e)}. Make sure PyMuPDF==1.24.0 is in requirements.txt',
                    'traceback': error_trace
                })
            }
        
        try:
            print("Importing EncTestNewTestF...")
            from EncTestNewTestF import redact_and_overwrite
            print("EncTestNewTestF imported successfully")
        except Exception as e:  # Catch all exceptions, not just ImportError
            import traceback
            traceback_str = traceback.format_exc()
            print(f"ERROR importing EncTestNewTestF: {e}")
            print(f"Full traceback:\n{traceback_str}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'error': f'Failed to import PDF encryption module: {str(e)}',
                    'type': type(e).__name__,
                    'traceback': traceback_str
                })
            }
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as input_file:
            input_file.write(file_data)
            input_pdf_path = input_file.name
        
        # Create output file path
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as output_file:
            output_pdf_path = output_file.name
        
        try:
            # Encrypt the PDF
            redact_and_overwrite(
                input_pdf_path,
                font_paths={},
                output_pdf=output_pdf_path,
                secret_key=secret_key,
                base_font_path=None
            )
            
            # Read encrypted PDF
            with open(output_pdf_path, 'rb') as f:
                pdf_data = f.read()
            
            # Clean up temporary files
            os.unlink(input_pdf_path)
            os.unlink(output_pdf_path)
            
            # Return PDF as base64 encoded
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': f'attachment; filename=encrypted_{filename}',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': pdf_base64,
                'isBase64Encoded': True
            }
        
        except Exception as e:
            # Clean up on error
            if os.path.exists(input_pdf_path):
                os.unlink(input_pdf_path)
            if os.path.exists(output_pdf_path):
                os.unlink(output_pdf_path)
            raise e
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        # Print full traceback for debugging - always print in serverless
        traceback_str = traceback.format_exc()
        print(f"ERROR in PDF encryption: {error_msg}")
        print(f"Full traceback:\n{traceback_str}")
        
        # Return error with traceback for debugging
        error_response = {
            'error': error_msg,
            'type': type(e).__name__,
        }
        
        # Include traceback in response for debugging (helpful for Vercel logs)
        DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
        if DEBUG:
            error_response['traceback'] = traceback_str
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(error_response)
        }

