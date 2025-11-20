# Postman Collection Details for Article Encryption API

## Base URL
```
http://localhost:5000
```
*Note: Change this to your deployed server URL if different*

---

## Endpoints

### 1. Encrypt Article (Single)
**Method:** `POST`  
**URL:** `{{base_url}}/api/encrypt`  
**Headers:**
```
Content-Type: application/json
```

**Request Body (JSON):**
```json
{
    "text": "The article text to encrypt"
}
```

**Example Request:**
```json
{
    "text": "Hello World! This is a test article."
}
```

**Success Response (200):**
```json
{
    "encrypted": "Encrypted text using exact algorithm",
    "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
}
```

**Error Responses:**
- `400` - No JSON data provided
- `400` - No text provided
- `500` - Server error

---

### 2. Encrypt Articles (Batch)
**Method:** `POST`  
**URL:** `{{base_url}}/api/encrypt/batch`  
**Headers:**
```
Content-Type: application/json
```

**Request Body (JSON):**
```json
{
    "texts": [
        "Article 1 text",
        "Article 2 text",
        "Article 3 text"
    ]
}
```

**Example Request:**
```json
{
    "texts": [
        "First article content here",
        "Second article content here",
        "Third article content here"
    ]
}
```

**Success Response (200):**
```json
{
    "encrypted": [
        "Encrypted text 1",
        "Encrypted text 2",
        "Encrypted text 3"
    ],
    "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
}
```

**Error Responses:**
- `400` - No JSON data provided
- `400` - No texts array provided
- `400` - Batch size too large (max 100)
- `500` - Server error

**Note:** Maximum batch size is 100 articles.

---

### 3. Health Check
**Method:** `GET`  
**URL:** `{{base_url}}/api/health`  
**Headers:** None required

**Success Response (200):**
```json
{
    "status": "healthy",
    "service": "article-encryption-api"
}
```

---

### 4. Test Encryption
**Method:** `POST`  
**URL:** `{{base_url}}/api/test`  
**Headers:**
```
Content-Type: application/json
```

**Request Body (JSON):**
```json
{
    "text": "Hello World"
}
```

**Example Request:**
```json
{
    "text": "Test encryption algorithm"
}
```

**Success Response (200):**
```json
{
    "original": "Test encryption algorithm",
    "encrypted": "Encrypted version",
    "algorithm": "exact_match_EncTestNewTestF"
}
```

**Error Response:**
- `500` - Server error

---

## Postman Environment Variables

Create a Postman environment with these variables:

| Variable | Initial Value | Current Value |
|----------|---------------|---------------|
| `base_url` | `http://localhost:5000` | `http://localhost:5000` |

---

## Postman Collection JSON

You can import this JSON directly into Postman:

```json
{
	"info": {
		"name": "Article Encryption API",
		"schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
	},
	"item": [
		{
			"name": "Encrypt Article",
			"request": {
				"method": "POST",
				"header": [
					{
						"key": "Content-Type",
						"value": "application/json"
					}
				],
				"body": {
					"mode": "raw",
					"raw": "{\n    \"text\": \"The article text to encrypt\"\n}"
				},
				"url": {
					"raw": "{{base_url}}/api/encrypt",
					"host": ["{{base_url}}"],
					"path": ["api", "encrypt"]
				}
			}
		},
		{
			"name": "Encrypt Articles (Batch)",
			"request": {
				"method": "POST",
				"header": [
					{
						"key": "Content-Type",
						"value": "application/json"
					}
				],
				"body": {
					"mode": "raw",
					"raw": "{\n    \"texts\": [\n        \"Article 1 text\",\n        \"Article 2 text\"\n    ]\n}"
				},
				"url": {
					"raw": "{{base_url}}/api/encrypt/batch",
					"host": ["{{base_url}}"],
					"path": ["api", "encrypt", "batch"]
				}
			}
		},
		{
			"name": "Health Check",
			"request": {
				"method": "GET",
				"url": {
					"raw": "{{base_url}}/api/health",
					"host": ["{{base_url}}"],
					"path": ["api", "health"]
				}
			}
		},
		{
			"name": "Test Encryption",
			"request": {
				"method": "POST",
				"header": [
					{
						"key": "Content-Type",
						"value": "application/json"
					}
				],
				"body": {
					"mode": "raw",
					"raw": "{\n    \"text\": \"Hello World\"\n}"
				},
				"url": {
					"raw": "{{base_url}}/api/test",
					"host": ["{{base_url}}"],
					"path": ["api", "test"]
				}
			}
		}
	],
	"variable": [
		{
			"key": "base_url",
			"value": "http://localhost:5000"
		}
	]
}
```

---

## Quick Start Guide

1. **Import Collection:**
   - Copy the Postman Collection JSON above
   - In Postman, click "Import" → "Raw text" → Paste the JSON

2. **Set Environment:**
   - Create a new environment in Postman
   - Add variable `base_url` with value `http://localhost:5000`
   - Select this environment before making requests

3. **Test the API:**
   - Start your Flask server: `python encrypt_api.py`
   - Run the "Health Check" request first to verify the server is running
   - Try the "Test Encryption" endpoint with sample text
   - Use "Encrypt Article" for single articles
   - Use "Encrypt Articles (Batch)" for multiple articles

---

## Example cURL Commands

### Encrypt Single Article
```bash
curl -X POST http://localhost:5000/api/encrypt \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World! This is a test article."}'
```

### Encrypt Batch
```bash
curl -X POST http://localhost:5000/api/encrypt/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Article 1", "Article 2", "Article 3"]}'
```

### Health Check
```bash
curl -X GET http://localhost:5000/api/health
```

### Test Encryption
```bash
curl -X POST http://localhost:5000/api/test \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```


