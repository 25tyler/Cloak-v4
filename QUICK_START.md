# Quick Start Guide

Get up and running in 5 minutes!

## 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 2. Test the Algorithm

```bash
cd ..
python test_algorithm.py
```

You should see encrypted outputs. Verify these match your PDF encryption.

## 3. Start the Server

```bash
cd backend
python encrypt_api.py
```

Server runs on `http://localhost:5000`

## 4. Test the API

In a new terminal:

```bash
curl -X POST http://localhost:5000/api/encrypt \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```

You should get:
```json
{"encrypted": "Heoov rWvaog", "font_url": "..."}
```

## 5. Test in Browser

1. Open `test.html` in your browser
2. Open Developer Tools (F12) → Network tab
3. Refresh page
4. You should see API calls to `/api/encrypt`

**Note:** For full functionality, you need to:
- Create the custom font (see `create_font.py`)
- Update API endpoint URL in `client/encrypt-articles.js`
- Deploy to production

## Next Steps

See `SETUP_INSTRUCTIONS.md` for complete deployment guide.

