# Cloak Article Encryption API

Backend API server for encrypting article text using a custom font mapping algorithm.

## Features

- RESTful API for text encryption
- Batch encryption endpoint for multiple articles
- Health check endpoint
- CORS enabled for cross-origin requests
- Caching for improved performance

## API Endpoints

- `POST /api/encrypt` - Encrypt a single article
- `POST /api/encrypt/batch` - Encrypt multiple articles (batch)
- `GET /api/health` - Health check
- `POST /api/test` - Test encryption algorithm

## Heroku Deployment

### Prerequisites

- Heroku CLI installed
- Git repository initialized

### Quick Deploy

1. **Login to Heroku:**
   ```bash
   heroku login
   ```

2. **Create a new Heroku app:**
   ```bash
   heroku create your-app-name
   ```

3. **Set environment variables (optional):**
   ```bash
   heroku config:set FONT_URL=https://your-cdn.com/fonts/encrypted.woff2
   heroku config:set DEBUG=false
   ```

4. **Deploy to Heroku:**
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

   Or if your default branch is `master`:
   ```bash
   git push heroku master
   ```

5. **Open your app:**
   ```bash
   heroku open
   ```

### Using Heroku Button

You can also deploy using the Heroku button by clicking [here](https://heroku.com/deploy?template=https://github.com/yourusername/cloakv3) (after updating the repository URL in `app.json`).

### Verify Deployment

Test the health endpoint:
```bash
curl https://your-app-name.herokuapp.com/api/health
```

## Local Development

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Run the server:**
   ```bash
   python encrypt_api.py
   ```

   Or with gunicorn:
   ```bash
   gunicorn encrypt_api:app
   ```

3. **Set environment variables (optional):**
   ```bash
   export FONT_URL=https://your-cdn.com/fonts/encrypted.woff2
   export PORT=5000
   export DEBUG=true
   ```

## Environment Variables

- `FONT_URL` - URL to the encrypted font file (default: CDN URL)
- `PORT` - Port to run the server on (default: 5000, Heroku sets this automatically)
- `DEBUG` - Enable debug mode (default: false)
- `HOST` - Host to bind to (default: 0.0.0.0)

## Project Structure

```
Cloakv3/
├── backend/
│   ├── encrypt_api.py      # Main Flask application
│   ├── __init__.py         # Makes backend a Python package
│   ├── requirements.txt    # Python dependencies (also in root)
│   └── runtime.txt         # Python version (also in root)
├── Procfile               # Heroku process file (root level)
├── requirements.txt        # Python dependencies (for Heroku)
├── runtime.txt            # Python version (for Heroku)
├── app.json               # Heroku app configuration
└── README.md              # This file
```

## Notes

- The app uses Gunicorn as the WSGI server for production
- Python 3.11.7 is specified in `runtime.txt`
- The `Procfile` is in the root directory and runs the app from the backend directory
- `requirements.txt` and `runtime.txt` are in both root and backend for compatibility
- Deploy from the project root directory

