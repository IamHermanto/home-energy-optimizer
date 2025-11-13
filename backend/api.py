from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
from optimizer import EnergyOptimizer
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

def index():
    return render_template('dashboard.html')

def query_db(query, args=(), one=False):
    """Helper to query database"""
    conn = sqlite3.connect('data/energy_data.db')
    conn.row_factory = sqlite3.Row
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

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
        data['grid_independence'] = round((1 - data['total_grid_import'] / data['total_consumption']) * 100, 1)
        return jsonify(data)
    
    return jsonify({'error': 'No data available'}), 404

@app.route('/api/energy/cost-analysis', methods=['GET'])
def cost_analysis():
    """Get cost comparison and savings analysis"""
    conn = sqlite3.connect('data/energy_data.db')
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
    conn = sqlite3.connect('data/energy_data.db')
    df = pd.read_sql_query('SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 24', conn)
    conn.close()
    
    optimizer = EnergyOptimizer()
    
    # Use recent patterns as forecast
    solar_forecast = df['solar_generation_kw'].tolist()[::-1]
    consumption_forecast = df['home_consumption_kw'].tolist()[::-1]
    
    recs = optimizer.optimize_battery_schedule(solar_forecast, consumption_forecast)
    
    return jsonify({'recommendations': recs})

if __name__ == '__main__':
    app.run(debug=True, port=5000)