from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import pandas as pd
from optimizer import EnergyOptimizer

app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:////tmp/energy_data.db')

# If using PostgreSQL from Render, fix the URL format
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

def get_db_connection():
    """Get database connection based on DATABASE_URL"""
    if DATABASE_URL.startswith('postgresql://'):
        import psycopg2
        from urllib.parse import urlparse
        
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect('/tmp/energy_data.db')
        conn.row_factory = sqlite3.Row
        return conn

def query_db(query, args=(), one=False):
    """Helper to query database"""
    conn = get_db_connection()
    
    if DATABASE_URL.startswith('postgresql://'):
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, args)
        rv = cur.fetchall()
        conn.close()
        return (rv[0] if rv else None) if one else rv
    else:
        cur = conn.execute(query, args)
        rv = cur.fetchall()
        conn.close()
        return (rv[0] if rv else None) if one else rv

def init_db():
    """Initialize database with sample data if empty"""
    try:
        # Check if data exists
        result = query_db('SELECT COUNT(*) as count FROM energy_readings', one=True)
        
        if result and result['count'] == 0:
            print("Database empty, generating sample data...")
            from energy_simulator import generate_week_data, save_to_database
            start_date = datetime.now().date() - timedelta(days=7)
            week_data = generate_week_data(start_date, num_days=7)
            save_to_database(week_data, DATABASE_URL)
            print("Sample data generated successfully")
    except Exception as e:
        print(f"Database initialization: {e}")
        # Create table if it doesn't exist
        create_table()
        # Generate initial data
        from energy_simulator import generate_week_data, save_to_database
        start_date = datetime.now().date() - timedelta(days=7)
        week_data = generate_week_data(start_date, num_days=7)
        save_to_database(week_data, DATABASE_URL)

def create_table():
    """Create energy_readings table if it doesn't exist"""
    conn = get_db_connection()
    
    if DATABASE_URL.startswith('postgresql://'):
        query = '''
            CREATE TABLE IF NOT EXISTS energy_readings (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP,
                solar_generation_kw REAL,
                home_consumption_kw REAL,
                net_energy_kw REAL,
                battery_state_kwh REAL,
                battery_charge_kw REAL,
                grid_import_kw REAL,
                grid_export_kw REAL
            )
        '''
    else:
        query = '''
            CREATE TABLE IF NOT EXISTS energy_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                solar_generation_kw REAL,
                home_consumption_kw REAL,
                net_energy_kw REAL,
                battery_state_kwh REAL,
                battery_charge_kw REAL,
                grid_import_kw REAL,
                grid_export_kw REAL
            )
        '''
    
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/energy/current-status', methods=['GET'])
def current_status():
    """Get latest energy readings"""
    latest = query_db(
        'SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 1',
        one=True
    )
    
    if latest:
        return jsonify(dict(latest))
    return jsonify({'error': 'No data available'}), 404

@app.route('/api/energy/daily-summary', methods=['GET'])
def daily_summary():
    """Get daily energy summary"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if DATABASE_URL.startswith('postgresql://'):
        query = '''
            SELECT 
                DATE(timestamp) as date,
                SUM(solar_generation_kw) as total_solar,
                SUM(home_consumption_kw) as total_consumption,
                SUM(grid_import_kw) as total_grid_import,
                SUM(grid_export_kw) as total_grid_export,
                AVG(battery_state_kwh) as avg_battery_state
            FROM energy_readings
            WHERE DATE(timestamp) = %s
            GROUP BY DATE(timestamp)
        '''
    else:
        query = '''
            SELECT 
                DATE(timestamp) as date,
                SUM(solar_generation_kw) as total_solar,
                SUM(home_consumption_kw) as total_consumption,
                SUM(grid_import_kw) as total_grid_import,
                SUM(grid_export_kw) as total_grid_export,
                AVG(battery_state_kwh) as avg_battery_state
            FROM energy_readings
            WHERE DATE(timestamp) = ?
            GROUP BY DATE(timestamp)
        '''
    
    result = query_db(query, [date], one=True)
    
    if result:
        return jsonify(dict(result))
    return jsonify({'error': 'No data for this date'}), 404

@app.route('/api/energy/hourly', methods=['GET'])
def hourly_data():
    """Get hourly data for a date range"""
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    if DATABASE_URL.startswith('postgresql://'):
        query = '''
            SELECT * FROM energy_readings
            WHERE DATE(timestamp) BETWEEN %s AND %s
            ORDER BY timestamp
        '''
    else:
        query = '''
            SELECT * FROM energy_readings
            WHERE DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
        '''
    
    results = query_db(query, [start_date, end_date])
    
    return jsonify([dict(row) for row in results])

@app.route('/api/energy/stats', methods=['GET'])
def overall_stats():
    """Get overall statistics"""
    query = '''
        SELECT 
            COUNT(*) as total_hours,
            SUM(solar_generation_kw) as total_solar,
            SUM(home_consumption_kw) as total_consumption,
            SUM(grid_import_kw) as total_grid_import,
            SUM(grid_export_kw) as total_grid_export,
            MIN(timestamp) as start_date,
            MAX(timestamp) as end_date
        FROM energy_readings
    '''
    
    result = query_db(query, one=True)
    
    if result:
        data = dict(result)
        # Calculate savings
        if data['total_consumption'] > 0:
            data['grid_independence'] = round((1 - data['total_grid_import'] / data['total_consumption']) * 100, 1)
        else:
            data['grid_independence'] = 0
        return jsonify(data)
    
    return jsonify({'error': 'No data available'}), 404

@app.route('/api/energy/cost-analysis', methods=['GET'])
def cost_analysis():
    """Get cost comparison and savings analysis"""
    if DATABASE_URL.startswith('postgresql://'):
        import psycopg2.extras
        conn = get_db_connection()
        df = pd.read_sql_query('SELECT * FROM energy_readings', conn)
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('/tmp/energy_data.db')
        df = pd.read_sql_query('SELECT * FROM energy_readings', conn)
        conn.close()
    
    optimizer = EnergyOptimizer()
    df = optimizer.calculate_costs(df)
    
    consumption_only = df[['timestamp', 'home_consumption_kw']].copy()
    analysis = optimizer.compare_scenarios(df, consumption_only)
    
    return jsonify(analysis)

@app.route('/api/energy/recommendations', methods=['GET'])
def recommendations():
    """Get battery optimization recommendations for next 24 hours"""
    if DATABASE_URL.startswith('postgresql://'):
        conn = get_db_connection()
        df = pd.read_sql_query('SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 24', conn)
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect('/tmp/energy_data.db')
        df = pd.read_sql_query('SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 24', conn)
        conn.close()
    
    optimizer = EnergyOptimizer()
    
    # Use recent patterns as forecast
    solar_forecast = df['solar_generation_kw'].tolist()[::-1]
    consumption_forecast = df['home_consumption_kw'].tolist()[::-1]
    
    recs = optimizer.optimize_battery_schedule(solar_forecast, consumption_forecast)
    
    return jsonify({'recommendations': recs})

# Initialize database on startup
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)