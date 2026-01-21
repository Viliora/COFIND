#!/usr/bin/env python3
"""
Web-based SQLite Database Viewer
Simple web interface untuk melihat database SQLite seperti PHPMyAdmin

Run: python start_db_viewer.py
Then open: http://localhost:5001
"""
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import sqlite3
import os
import json

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

# HTML Template untuk viewer
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQLite Database Viewer - COFIND</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
        .sidebar {
            width: 250px;
            background: #f8f9fa;
            padding: 20px;
            float: left;
            min-height: 600px;
            border-right: 1px solid #dee2e6;
        }
        .content {
            margin-left: 250px;
            padding: 30px;
        }
        .table-list {
            list-style: none;
        }
        .table-item {
            padding: 12px 15px;
            margin: 5px 0;
            background: white;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s;
            border: 2px solid transparent;
        }
        .table-item:hover {
            background: #667eea;
            color: white;
            transform: translateX(5px);
        }
        .table-item.active {
            background: #667eea;
            color: white;
            border-color: #764ba2;
        }
        .table-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #dee2e6;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .loading {
            text-align: center;
            padding: 50px;
            color: #667eea;
            font-size: 1.2em;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card h3 { font-size: 2em; margin-bottom: 5px; }
        .stat-card p { opacity: 0.9; }
        .sql-editor {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .sql-editor textarea {
            width: 100%;
            min-height: 100px;
            padding: 15px;
            border: 2px solid #dee2e6;
            border-radius: 5px;
            font-family: monospace;
            font-size: 14px;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 10px;
            transition: transform 0.2s;
        }
        .btn:hover {
            transform: scale(1.05);
        }
        .refresh-btn {
            float: right;
            padding: 8px 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗄️ SQLite Database Viewer</h1>
            <p>COFIND Database Management - Like PHPMyAdmin but for SQLite</p>
        </div>
        
        <div class="sidebar">
            <h3 style="margin-bottom: 15px; color: #667eea;">📊 Tables</h3>
            <ul class="table-list" id="tableList">
                <li class="loading">Loading...</li>
            </ul>
        </div>
        
        <div class="content">
            <button class="btn refresh-btn" onclick="loadTables()">🔄 Refresh</button>
            
            <h2 id="tableName">Select a table from sidebar</h2>
            
            <div class="stats" id="stats"></div>
            
            <div class="table-info" id="tableInfo"></div>
            
            <div id="tableData">
                <p style="text-align: center; padding: 50px; color: #999;">
                    👈 Pilih table dari sidebar untuk melihat data
                </p>
            </div>
            
            <div class="sql-editor">
                <h3 style="margin-bottom: 10px;">SQL Query Editor</h3>
                <textarea id="sqlQuery" placeholder="Enter SQL query here... (e.g., SELECT * FROM users WHERE is_admin = 1)"></textarea>
                <button class="btn" onclick="executeQuery()">▶️ Execute Query</button>
            </div>
        </div>
    </div>
    
    <script>
        let currentTable = null;
        
        async function loadTables() {
            try {
                const response = await fetch('/api/tables');
                const data = await response.json();
                
                const tableList = document.getElementById('tableList');
                tableList.innerHTML = '';
                
                if (data.tables && data.tables.length > 0) {
                    // Show stats
                    const stats = document.getElementById('stats');
                    stats.innerHTML = `
                        <div class="stat-card">
                            <h3>${data.tables.length}</h3>
                            <p>Total Tables</p>
                        </div>
                        <div class="stat-card">
                            <h3>${data.total_rows || 0}</h3>
                            <p>Total Rows</p>
                        </div>
                        <div class="stat-card">
                            <h3>${(data.database_size / 1024).toFixed(2)} KB</h3>
                            <p>Database Size</p>
                        </div>
                    `;
                    
                    data.tables.forEach(table => {
                        const li = document.createElement('li');
                        li.className = 'table-item';
                        li.innerHTML = `
                            <strong>${table.name}</strong><br>
                            <small style="opacity: 0.7;">${table.rows} rows</small>
                        `;
                        li.onclick = () => loadTable(table.name);
                        tableList.appendChild(li);
                    });
                } else {
                    tableList.innerHTML = '<li>No tables found</li>';
                }
            } catch (error) {
                console.error('Error loading tables:', error);
                document.getElementById('tableList').innerHTML = '<li>Error loading tables</li>';
            }
        }
        
        async function loadTable(tableName) {
            currentTable = tableName;
            
            // Update active state
            document.querySelectorAll('.table-item').forEach(item => {
                item.classList.remove('active');
                if (item.querySelector('strong').textContent === tableName) {
                    item.classList.add('active');
                }
            });
            
            document.getElementById('tableName').textContent = `📋 Table: ${tableName}`;
            document.getElementById('tableData').innerHTML = '<p class="loading">Loading...</p>';
            
            try {
                const response = await fetch(`/api/table/${tableName}`);
                const data = await response.json();
                
                // Show table info
                const info = document.getElementById('tableInfo');
                info.innerHTML = `
                    <strong>Columns:</strong> ${data.columns.join(', ')}<br>
                    <strong>Total Rows:</strong> ${data.total_rows}
                `;
                
                // Show table data
                let html = '<table><thead><tr>';
                data.columns.forEach(col => {
                    html += `<th>${col}</th>`;
                });
                html += '</tr></thead><tbody>';
                
                if (data.rows.length === 0) {
                    html += `<tr><td colspan="${data.columns.length}" style="text-align: center;">No data</td></tr>`;
                } else {
                    data.rows.forEach(row => {
                        html += '<tr>';
                        data.columns.forEach(col => {
                            let value = row[col];
                            if (value === null) value = '<em style="color: #999;">NULL</em>';
                            else if (typeof value === 'string' && value.length > 100) {
                                value = value.substring(0, 97) + '...';
                            }
                            html += `<td>${value}</td>`;
                        });
                        html += '</tr>';
                    });
                }
                
                html += '</tbody></table>';
                document.getElementById('tableData').innerHTML = html;
                
                // Update SQL query placeholder
                document.getElementById('sqlQuery').placeholder = `SELECT * FROM ${tableName} WHERE ...`;
                
            } catch (error) {
                console.error('Error loading table:', error);
                document.getElementById('tableData').innerHTML = '<p style="color: red;">Error loading table data</p>';
            }
        }
        
        async function executeQuery() {
            const query = document.getElementById('sqlQuery').value.trim();
            if (!query) {
                alert('Please enter a SQL query');
                return;
            }
            
            document.getElementById('tableData').innerHTML = '<p class="loading">Executing query...</p>';
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('tableData').innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                    return;
                }
                
                // Show results
                document.getElementById('tableName').textContent = '🔍 Query Results';
                document.getElementById('tableInfo').innerHTML = `<strong>Rows returned:</strong> ${data.rows.length}`;
                
                if (data.rows.length === 0) {
                    document.getElementById('tableData').innerHTML = '<p style="text-align: center; padding: 50px;">Query executed successfully. No rows returned.</p>';
                    return;
                }
                
                let html = '<table><thead><tr>';
                Object.keys(data.rows[0]).forEach(col => {
                    html += `<th>${col}</th>`;
                });
                html += '</tr></thead><tbody>';
                
                data.rows.forEach(row => {
                    html += '<tr>';
                    Object.values(row).forEach(value => {
                        if (value === null) value = '<em style="color: #999;">NULL</em>';
                        else if (typeof value === 'string' && value.length > 100) {
                            value = value.substring(0, 97) + '...';
                        }
                        html += `<td>${value}</td>`;
                    });
                    html += '</tr>';
                });
                
                html += '</tbody></table>';
                document.getElementById('tableData').innerHTML = html;
                
            } catch (error) {
                console.error('Error executing query:', error);
                document.getElementById('tableData').innerHTML = '<p style="color: red;">Error executing query</p>';
            }
        }
        
        // Load tables on page load
        loadTables();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/tables')
def get_tables():
    """Get all tables with row counts"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        table_info = []
        total_rows = 0
        
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            table_info.append({
                'name': table_name,
                'rows': count
            })
            total_rows += count
        
        # Get database file size
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        
        conn.close()
        
        return jsonify({
            'tables': table_info,
            'total_rows': total_rows,
            'database_size': db_size
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/table/<table_name>')
def get_table_data(table_name):
    """Get data from specific table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Get total rows
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_rows = cursor.fetchone()[0]
        
        # Get data (limit to 100 rows)
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 100")
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'columns': columns,
            'rows': rows,
            'total_rows': total_rows
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute custom SQL query"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
        
        # Only allow SELECT queries for safety
        if not query.upper().startswith('SELECT'):
            return jsonify({'error': 'Only SELECT queries are allowed'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({'rows': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database tidak ditemukan: {DB_PATH}")
        print("Pastikan file cofind.db ada di folder yang sama dengan script ini")
        exit(1)
    
    print("\n" + "="*70)
    print("🗄️  SQLite Database Viewer - COFIND")
    print("="*70)
    print(f"\nDatabase: {DB_PATH}")
    print("\n🌐 Web Interface:")
    print("   http://localhost:5001")
    print("\n📝 Features:")
    print("   - Browse all tables")
    print("   - View table data (like PHPMyAdmin)")
    print("   - Execute SQL queries")
    print("   - Database statistics")
    print("\n⚠️  Press Ctrl+C to stop the server")
    print("="*70 + "\n")
    
    app.run(debug=True, port=5001, host='0.0.0.0')
