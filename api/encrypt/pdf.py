"""
Vercel serverless function for PDF encryption endpoint
"""
import sys
import os
import json
import tempfile
import base64

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from encrypt_api import DEFAULT_SECRET_KEY

def handler(req):
    """Handle PDF encryption request - Vercel serverless function format"""
    try:
        # Parse request - Vercel format
        method = req.get('method', 'GET')
        if method != 'POST':
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
        # Get body from request
        body = req.get('body', '')
        
        # Parse JSON body
        try:
            if isinstance(body, str):
                data = json.loads(body)
            else:
                data = body if body else {}
        except:
            data = {}
        
        # Check if file is provided
        if 'file' not in data:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'No file provided'})
            }
        
        # Get file data (base64 encoded)
        file_data = base64.b64decode(data['file'])
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
        
        # Import PDF processing
        try:
            import fitz  # PyMuPDF
            from EncTestNewTestF import redact_and_overwrite
        except ImportError as e:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': f'PDF processing library not available: {str(e)}'})
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
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': error_msg, 'type': type(e).__name__})
        }

