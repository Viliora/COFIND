# Archived original app.py
"""(archived) original app.py content
See archive_servers/app_original.py for backup.
"""

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
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')
print(f"Loaded API Key: {GOOGLE_PLACES_API_KEY}")

# Root endpoint
@app.route('/')
def home():
	return jsonify({"message": "Welcome to COFIND API"})

if __name__ == '__main__':
	app.run(debug=True)

