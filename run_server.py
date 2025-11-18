#!/usr/bin/env python
"""
Simple Flask server runner without debug mode
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment
os.environ['FLASK_ENV'] = 'production'

# Import and run app
from app import app

if __name__ == '__main__':
    print("Starting COFIND Flask Server...")
    print("Server running at http://127.0.0.1:5000")
    print("Press Ctrl+C to stop\n")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
