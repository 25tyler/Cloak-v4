# Vercel Deployment Guide

This project is configured to deploy on Vercel with both frontend and backend API.

## Project Structure

- `frontend/` - React/Vite frontend application
- `api/` - Vercel serverless functions for the backend API
- `encrypt_api.py` - Main Flask API (used by serverless functions)
- `EncTestNewTestF.py` - PDF encryption logic
- `generate_font.py` - Font generation utilities

## Deployment Steps

1. **Connect to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Sign in with GitHub
   - Import the repository: `25tyler/Cloak-v4`

2. **Configure Build Settings:**
   - Framework Preset: Other
   - Root Directory: (leave as root)
   - Build Command: `cd frontend && npm install && npm run build`
   - Output Directory: `frontend/dist`

3. **Environment Variables (if needed):**
   - `DEFAULT_SECRET_KEY` - Default encryption key (optional, defaults to 29202393)
   - `DEBUG` - Set to `true` for debug mode (optional)

4. **Deploy:**
   - Vercel will automatically detect the `vercel.json` configuration
   - The frontend will be served from `frontend/dist`
   - API routes under `/api/*` will be handled by serverless functions

## API Endpoints

- `POST /api/encrypt/pdf` - Encrypt a PDF file
  - Request body: JSON with `file` (base64 encoded), `filename`, and optional `secret_key`
  - Response: Base64 encoded encrypted PDF

## Local Development

1. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. **Backend API:**
   ```bash
   pip install -r requirements.txt
   python encrypt_api.py
   ```

The frontend is configured to proxy `/api/*` requests to `http://localhost:5001` during development.

## Notes

- Font files (Supertest*.ttf) are included in the repository
- Generated fonts are created at runtime and stored in the `fonts/` directory
- PDF processing requires PyMuPDF which is included in requirements.txt

