#!/usr/bin/env python3
"""Run Flask backend server"""
import os
import sys

os.chdir(r'c:\Users\User\cofind')
sys.path.insert(0, r'c:\Users\User\cofind')

from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting COFIND Backend with SQLite")
    print("=" * 60)
    app.run(debug=False, host='127.0.0.1', port=5000)
