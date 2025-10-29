# app_v3.py (archived)
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Configure Google Places API
API_KEY = 'REDACTED_FOR_ARCHIVE'
PLACES_API_BASE = 'https://places.googleapis.com/v1/places'

@app.route('/')
def home():
	return jsonify({"message": "Welcome to COFIND API (archived v3)"})

if __name__ == '__main__':
	app.run(debug=True)

