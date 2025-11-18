#!/usr/bin/env python
"""
Minimal Flask test server to debug startup issues
"""
import os
import sys
from flask import Flask, jsonify

# Create minimal Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Flask is running!"})

if __name__ == '__main__':
    print("Starting minimal Flask server on port 5000...")
    try:
        # Try binding to all interfaces first
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        print(f"Error starting Flask: {e}")
        sys.exit(1)
