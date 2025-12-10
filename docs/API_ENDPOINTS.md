# 📡 COFIND API Endpoints

## 🌐 Base URL
```
http://localhost:5000
```

---

## 📋 Endpoint List

### **1. Health Check**
```
GET /
```

**Response:**
```json
{
  "message": "Welcome to COFIND API"
}
```

---

### **2. Search Coffee Shops** ⭐

```
GET /api/search/coffeeshops
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lat` | float | Yes | Latitude coordinates |
| `lng` | float | Yes | Longitude coordinates |

**Example:**
```
http://localhost:5000/api/search/coffeeshops?lat=-0.026330&lng=109.342506
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "place_id": "ChIJv52soIZZHS4RIpP04VD5R8g",
      "name": "ASPECT COFFEE",
      "address": "Jl. Example Street, Pontianak",
      "rating": 4.5,
      "user_ratings_total": 171,
      "price_level": 2,
      "location": {
        "lat": -0.026330,
        "lng": 109.342506
      },
      "business_status": "OPERATIONAL",
      "photos": [
        "https://lh3.googleusercontent.com/..."
      ]
    },
    ...
  ]
}
```

---

### **3. Coffee Shop Detail** ⭐

```
GET /api/coffeeshops/detail/{place_id}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `place_id` | string | Yes | Google Places ID |

**Example URLs:**
```
http://localhost:5000/api/coffeeshops/detail/ChIJv52soIZZHS4RIpP04VD5R8g
http://localhost:5000/api/coffeeshops/detail/ChIJHdYrWU1ZHS4RuU_qB_QKTdI
http://localhost:5000/api/coffeeshops/detail/ChIJCzPS4zlZHS4RW4VztUIAgS8
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "place_id": "ChIJv52soIZZHS4RIpP04VD5R8g",
    "name": "ASPECT COFFEE",
    "formatted_address": "Jl. Example Street No.123, Pontianak",
    "formatted_phone_number": "+62 812-3456-7890",
    "website": "https://example.com",
    "rating": 4.5,
    "user_ratings_total": 171,
    "price_level": 2,
    "geometry": {
      "location": {
        "lat": -0.026330,
        "lng": 109.342506
      }
    },
    "opening_hours": {
      "open_now": true,
      "weekday_text": [
        "Monday: 8:00 AM – 10:00 PM",
        "Tuesday: 8:00 AM – 10:00 PM",
        ...
      ]
    },
    "photos": [
      "https://lh3.googleusercontent.com/..."
    ],
    "reviews": [
      {
        "author_name": "John Doe",
        "rating": 5,
        "text": "Great coffee and cozy atmosphere!",
        "time": 1234567890,
        "relative_time_description": "2 weeks ago"
      },
      ...
    ]
  }
}
```

---

### **4. LLM Chat**

```
POST /api/llm/chat
```

**Request Body:**
```json
{
  "message": "Rekomendasikan coffee shop yang cozy",
  "context": "Pontianak"
}
```

**Response:**
```json
{
  "status": "success",
  "response": "Berdasarkan lokasi Anda..."
}
```

---

### **5. LLM Analyze**

```
POST /api/llm/analyze
```

**Request Body:**
```json
{
  "place_id": "ChIJv52soIZZHS4RIpP04VD5R8g"
}
```

**Response:**
```json
{
  "status": "success",
  "analysis": "Coffee shop ini memiliki..."
}
```

---

## 🧪 Testing Endpoints

### **Method 1: Using curl**

**Search:**
```bash
curl "http://localhost:5000/api/search/coffeeshops?lat=-0.026330&lng=109.342506"
```

**Detail:**
```bash
curl "http://localhost:5000/api/coffeeshops/detail/ChIJv52soIZZHS4RIpP04VD5R8g"
```

---

### **Method 2: Using Python Script**

```bash
python test_detail_endpoint.py
```

This script will:
1. ✅ Fetch coffee shops from search endpoint
2. ✅ Show first 3 coffee shops with place_id
3. ✅ Test detail endpoint with first place_id
4. ✅ Display complete coffee shop details

---

### **Method 3: Using Browser**

**Search (copy-paste ke browser):**
```
http://localhost:5000/api/search/coffeeshops?lat=-0.026330&lng=109.342506
```

**Detail (replace {place_id} dengan ID dari search result):**
```
http://localhost:5000/api/coffeeshops/detail/{place_id}
```

**Example:**
```
http://localhost:5000/api/coffeeshops/detail/ChIJv52soIZZHS4RIpP04VD5R8g
```

---

## 📊 Sample place_id List

From test results:

| Coffee Shop Name | place_id |
|------------------|----------|
| ASPECT COFFEE | `ChIJv52soIZZHS4RIpP04VD5R8g` |
| CW COFFEE TANJUNG SARI CWTS | `ChIJHdYrWU1ZHS4RuU_qB_QKTdI` |
| Cia Yo Coffee | `ChIJCzPS4zlZHS4RW4VztUIAgS8` |

**Usage:**
```
http://localhost:5000/api/coffeeshops/detail/ChIJv52soIZZHS4RIpP04VD5R8g
http://localhost:5000/api/coffeeshops/detail/ChIJHdYrWU1ZHS4RuU_qB_QKTdI
http://localhost:5000/api/coffeeshops/detail/ChIJCzPS4zlZHS4RW4VztUIAgS8
```

---

## 🔄 Data Flow

### **Getting Coffee Shop Details:**

```
Step 1: Get List of Coffee Shops
┌─────────────────────────────────────────┐
│ GET /api/search/coffeeshops             │
│ ?lat=-0.026330&lng=109.342506           │
│                                         │
│ Response: Array of coffee shops         │
│ Each has: place_id, name, rating, etc  │
└─────────────────────────────────────────┘
           ↓
Step 2: Pick a place_id
           ↓
Step 3: Get Detailed Information
┌─────────────────────────────────────────┐
│ GET /api/coffeeshops/detail/{place_id}  │
│                                         │
│ Response: Complete details including:   │
│ - Phone number                          │
│ - Website                               │
│ - Opening hours                         │
│ - Reviews                               │
│ - Photos                                │
└─────────────────────────────────────────┘
```

---

## ⚡ Quick Reference

### **Get All Coffee Shops:**
```
http://localhost:5000/api/search/coffeeshops?lat=-0.026330&lng=109.342506
```

### **Get Specific Coffee Shop Detail:**
```
http://localhost:5000/api/coffeeshops/detail/{place_id}
```

**Example:**
```
http://localhost:5000/api/coffeeshops/detail/ChIJv52soIZZHS4RIpP04VD5R8g
```

---

## 🐛 Common Issues

### **404 Not Found**
- ❌ Wrong URL format
- ✅ Make sure: `/api/coffeeshops/detail/{place_id}`
- ✅ NOT: `/api/coffeeshops/{place_id}`

### **Invalid place_id**
- ❌ place_id not found in Google Places
- ✅ Get place_id from search endpoint first
- ✅ Copy exact place_id (case-sensitive)

### **Backend Not Running**
- ❌ Connection refused
- ✅ Start backend: `python app.py`
- ✅ Check: `http://localhost:5000/`

---

## 📝 Response Status

| Status | Description |
|--------|-------------|
| `success` | Request successful, data available |
| `error` | Request failed, see message for details |

**Example Error Response:**
```json
{
  "status": "error",
  "message": "Coffee shop not found"
}
```

---

## 🎯 Usage in Frontend

### **ShopList.jsx:**
```javascript
// Get all coffee shops
const apiUrl = `${API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506`;
const result = await fetchWithCache(apiUrl);
const coffeeShops = result.data.data;
```

### **ShopDetail.jsx:**
```javascript
// Get specific coffee shop detail
const detailUrl = `${API_BASE}/api/coffeeshops/detail/${place_id}`;
const result = await fetchWithCache(detailUrl);
const shopDetail = result.data.data;
```

---

## 📚 Related Files

- `test_detail_endpoint.py` - Test script for detail endpoint
- `app.py` - Backend API implementation
- `ShopDetail.jsx` - Frontend detail page
- `ShopList.jsx` - Frontend list page

---

**Created:** November 2025  
**Base URL:** http://localhost:5000  
**Status:** ✅ Operational

