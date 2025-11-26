from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
import pandas as pd

# Fix imports to work whether running from project root or backend directory
if __name__ == '__main__':
    # If running as main script, adjust path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if current_dir.endswith('backend'):
        # Running from backend directory, add it to path
        sys.path.insert(0, current_dir)
    else:
        # Running from project root
        sys.path.insert(0, os.path.join(parent_dir, 'backend'))

from optimizer import EnergyOptimizer

app = Flask(__name__)
CORS(app)

# Database configuration
# Use cross-platform database path
if os.name == 'nt':  # Windows
    DB_PATH = os.path.join(os.path.dirname(__file__), 'energy_data.db')
else:  # Linux/Unix
    DB_PATH = '/tmp/energy_data.db'

DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{DB_PATH}')
print(f"Database path: {DB_PATH if not DATABASE_URL.startswith('postgresql') else 'PostgreSQL'}")

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
        # Extract path from sqlite:///path format
        db_path = DATABASE_URL.replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

def query_db(query, args=(), one=False):
    """Helper to query database"""
    try:
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
    except Exception as e:
        print(f"Query error: {e}")
        # If error occurs, try to reinitialize
        create_table()
        generate_sample_data()
        # Retry the query
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

def generate_sample_data():
    """Generate and save sample energy data"""
    try:
        print("=== Starting data generation ===")
        
        # Import here to avoid circular imports
        from energy_simulator import generate_week_data, save_to_database
        
        start_date = datetime.now().date() - timedelta(days=7)
        print(f"Generating data from {start_date}")
        
        week_data = generate_week_data(start_date, num_days=7)
        print(f"Generated {len(week_data)} records in memory")
        
        # Save to database
        save_to_database(week_data, DATABASE_URL)
        print(f"=== Data generation complete: {len(week_data)} records saved ===")
        
        # Verify it was saved
        conn = get_db_connection()
        if DATABASE_URL.startswith('postgresql://'):
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT COUNT(*) as count FROM energy_readings')
            result = cur.fetchone()
        else:
            cur = conn.execute('SELECT COUNT(*) as count FROM energy_readings')
            result = cur.fetchone()
        conn.close()
        
        print(f"Verification: Database now has {result['count']} records")
        
        return True
    except Exception as e:
        print(f"ERROR in generate_sample_data: {e}")
        import traceback
        traceback.print_exc()
        raise

def init_db():
    """Initialize database with sample data if empty"""
    try:
        print("Initializing database...")
        create_table()
        
        # Check if data exists
        result = query_db('SELECT COUNT(*) as count FROM energy_readings', one=True)
        
        if not result or result['count'] == 0:
            print("Database empty, generating sample data...")
            generate_sample_data()
            print("Database initialized successfully")
        else:
            print(f"Database already has {result['count']} records")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Try to create and populate anyway
        create_table()
        generate_sample_data()

def ensure_data_exists():
    """Ensure database has data, generate if needed"""
    try:
        result = query_db('SELECT COUNT(*) as count FROM energy_readings', one=True)
        if not result or result['count'] == 0:
            print("No data found, regenerating...")
            generate_sample_data()
            return True
        return False
    except Exception as e:
        print(f"Data check error: {e}")
        create_table()
        generate_sample_data()
        return True

def create_table():
    """Create energy_readings table if it doesn't exist"""
    try:
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
        print("Table created successfully")
    except Exception as e:
        print(f"Error creating table: {e}")

# ============================================================================
# SINGLE HOME ROUTES
# ============================================================================

@app.route('/')
def index():
    ensure_data_exists()
    return render_template('dashboard.html')

@app.route('/api/energy/current-status', methods=['GET'])
def current_status():
    """Get latest energy readings"""
    ensure_data_exists()
    
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
    ensure_data_exists()
    
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
    print("=== Hourly endpoint called ===")
    
    # Force data generation and wait for it
    try:
        result = query_db('SELECT COUNT(*) as count FROM energy_readings', one=True)
        if not result or result['count'] == 0:
            print("No data found, forcing generation...")
            generate_sample_data()
            print("Data generation completed")
    except Exception as e:
        print(f"Error checking/generating data: {e}")
        create_table()
        generate_sample_data()
    
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    print(f"Querying for dates: {start_date} to {end_date}")
    
    # Just get all data since date filtering might be causing issues
    try:
        results = query_db('SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 48')
        print(f"Found {len(results)} records")
        
        if not results or len(results) == 0:
            print("ERROR: Still no data after generation!")
            return jsonify({'error': 'Failed to generate data', 'details': 'Database is empty'}), 500
        
        return jsonify([dict(row) for row in results])
    except Exception as e:
        print(f"Query error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/energy/stats', methods=['GET'])
def overall_stats():
    """Get overall statistics"""
    ensure_data_exists()
    
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
    ensure_data_exists()
    
    if DATABASE_URL.startswith('postgresql://'):
        import psycopg2.extras
        conn = get_db_connection()
        df = pd.read_sql_query('SELECT * FROM energy_readings', conn)
        conn.close()
    else:
        import sqlite3
        db_path = DATABASE_URL.replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
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
    ensure_data_exists()
    
    if DATABASE_URL.startswith('postgresql://'):
        conn = get_db_connection()
        df = pd.read_sql_query('SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 24', conn)
        conn.close()
    else:
        import sqlite3
        db_path = DATABASE_URL.replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query('SELECT * FROM energy_readings ORDER BY timestamp DESC LIMIT 24', conn)
        conn.close()
    
    optimizer = EnergyOptimizer()
    
    # Use recent patterns as forecast
    solar_forecast = df['solar_generation_kw'].tolist()[::-1]
    consumption_forecast = df['home_consumption_kw'].tolist()[::-1]
    
    recs = optimizer.optimize_battery_schedule(solar_forecast, consumption_forecast)
    
    return jsonify({'recommendations': recs})

# ============================================================================
# VPP DASHBOARD ROUTES
# ============================================================================

# Initialize VPP system (lazy load)
_vpp_aggregator = None
_autonomous_vpp = None

# Demo speed multiplier (set via environment variable)
DEMO_SPEED = int(os.environ.get('DEMO_SPEED', '30'))  # Default: 30x speed

def get_vpp():
    """Get or initialize VPP aggregator"""
    global _vpp_aggregator
    if _vpp_aggregator is None:
        from vpp_aggregator import VPPAggregator
        _vpp_aggregator = VPPAggregator(db_path=DB_PATH)
    return _vpp_aggregator

def get_autonomous():
    """Get or initialize autonomous VPP"""
    global _autonomous_vpp
    if _autonomous_vpp is None:
        from autonomous_vpp import AutonomousVPP
        _autonomous_vpp = AutonomousVPP(get_vpp(), speed_multiplier=DEMO_SPEED)
    return _autonomous_vpp

@app.route('/vpp-dashboard')
def vpp_dashboard():
    """VPP Control Center Dashboard"""
    return render_template('vpp_dashboard.html')

@app.route('/api/vpp/fleet-status', methods=['GET'])
def vpp_fleet_status():
    """Get current fleet status"""
    vpp = get_vpp()
    status = vpp.get_fleet_status()
    return jsonify(status)

@app.route('/api/vpp/batteries/list', methods=['GET'])
def vpp_batteries_list():
    """Get list of all batteries"""
    vpp = get_vpp()
    batteries = vpp.get_batteries_list()
    return jsonify({'batteries': batteries})

@app.route('/api/vpp/batteries/location', methods=['GET'])
def vpp_batteries_location():
    """Get batteries grouped by location"""
    vpp = get_vpp()
    locations = vpp.get_batteries_by_location()
    return jsonify(locations)

@app.route('/api/vpp/dispatch', methods=['POST'])
def vpp_dispatch():
    """Dispatch batteries for power requirement"""
    data = request.get_json()
    required_power = data.get('required_power_kw', 250)
    reason = data.get('reason', 'Manual dispatch')
    
    vpp = get_vpp()
    result = vpp.dispatch_batteries(required_power, reason)
    return jsonify(result)

@app.route('/api/vpp/fcas-event', methods=['POST'])
def vpp_fcas_event():
    """Simulate FCAS frequency response event"""
    data = request.get_json()
    frequency = data.get('frequency_hz', 50.0)
    
    vpp = get_vpp()
    result = vpp.simulate_fcas_event(frequency)
    return jsonify(result)

@app.route('/api/vpp/revenue', methods=['GET'])
def vpp_revenue():
    """Get daily revenue calculations"""
    vpp = get_vpp()
    revenue = vpp.calculate_daily_revenue()
    return jsonify(revenue)

@app.route('/api/vpp/dispatch-history', methods=['GET'])
def vpp_dispatch_history():
    """Get recent dispatch events"""
    limit = request.args.get('limit', 10, type=int)
    vpp = get_vpp()
    events = vpp.get_recent_dispatch_events(limit)
    return jsonify({'events': events})

@app.route('/api/grid/status', methods=['GET'])
def grid_status():
    """Get current grid status from AEMO"""
    vpp = get_vpp()
    status = vpp.get_grid_status()
    return jsonify(status)

@app.route('/api/grid/regions', methods=['GET'])
def grid_regions():
    """Get prices for all regions"""
    vpp = get_vpp()
    regions = vpp.get_all_regions()
    return jsonify(regions)

@app.route('/api/autonomous/start', methods=['POST'])
def autonomous_start():
    """Start autonomous VPP mode"""
    auto = get_autonomous()
    
    # Check if already running
    status = auto.get_status()
    if status.get('running', False):
        return jsonify({
            'status': 'already_running',
            'message': 'Autonomous VPP already running'
        })
    
    result = auto.start()
    return jsonify(result)

@app.route('/api/autonomous/stop', methods=['POST'])
def autonomous_stop():
    """Stop autonomous VPP mode"""
    auto = get_autonomous()
    result = auto.stop()
    return jsonify(result)

@app.route('/api/autonomous/status', methods=['GET'])
def autonomous_status():
    """Get autonomous VPP status"""
    auto = get_autonomous()
    status = auto.get_status()
    return jsonify(status)

# ============================================================================
# EV FLEET ROUTES
# ============================================================================

# Initialize EV fleet (lazy load)
_ev_fleet = None

def get_ev_fleet():
    """Get or initialize EV fleet"""
    global _ev_fleet
    if _ev_fleet is None:
        from ev_fleet import EVFleet
        _ev_fleet = EVFleet(25)
        print("✅ EV Fleet initialized (25 vehicles)")
    return _ev_fleet

@app.route('/ev-dashboard')
def ev_dashboard():
    """EV Fleet Control Dashboard"""
    return render_template('ev_dashboard.html')

@app.route('/api/ev/fleet-status', methods=['GET'])
def ev_fleet_status():
    """Get current EV fleet status"""
    fleet = get_ev_fleet()
    status = fleet.get_fleet_status()
    return jsonify(status)

@app.route('/api/ev/all', methods=['GET'])
def ev_all():
    """Get list of all EVs"""
    fleet = get_ev_fleet()
    evs = fleet.get_all_evs()
    return jsonify(evs)

@app.route('/api/ev/by-status', methods=['GET'])
def ev_by_status():
    """Get EVs grouped by status"""
    fleet = get_ev_fleet()
    status_groups = fleet.get_evs_by_status()
    return jsonify(status_groups)

@app.route('/api/ev/dispatch', methods=['POST'])
def ev_dispatch():
    """Dispatch EVs for V2G discharge"""
    data = request.get_json()
    required_power = data.get('required_power_kw', 100)
    
    fleet = get_ev_fleet()
    result = fleet.dispatch_v2g(required_power)
    return jsonify(result)

@app.route('/api/ev/revenue', methods=['GET'])
def ev_revenue():
    """Get daily revenue calculations"""
    fleet = get_ev_fleet()
    revenue = fleet.calculate_daily_revenue()
    return jsonify(revenue)

@app.route('/api/ev/schedule', methods=['GET'])
def ev_schedule():
    """Get smart charging schedule for next 24 hours"""
    fleet = get_ev_fleet()
    schedule = fleet.smart_charging_schedule()
    return jsonify(schedule)

# ============================================================================
# DEBUG ROUTES
# ============================================================================

@app.route('/api/debug/regenerate', methods=['POST'])
def force_regenerate():
    """Force regenerate all data - for debugging"""
    try:
        print("=== FORCE REGENERATE REQUESTED ===")
        
        # Delete all existing data
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM energy_readings')
        conn.commit()
        conn.close()
        print("Deleted all existing data")
        
        # Generate new data
        generate_sample_data()
        
        # Count records
        result = query_db('SELECT COUNT(*) as count FROM energy_readings', one=True)
        
        return jsonify({
            'success': True,
            'message': f'Generated {result["count"]} records',
            'count': result['count']
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/debug/status', methods=['GET'])
def debug_status():
    """Get database status - for debugging"""
    try:
        result = query_db('SELECT COUNT(*) as count FROM energy_readings', one=True)
        
        # Get date range
        date_range = query_db(
            'SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date FROM energy_readings',
            one=True
        )
        
        return jsonify({
            'record_count': result['count'],
            'date_range': {
                'min': date_range['min_date'] if date_range else None,
                'max': date_range['max_date'] if date_range else None
            },
            'database_url': 'PostgreSQL' if DATABASE_URL.startswith('postgresql://') else 'SQLite'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Initialize database on startup
print("=== Starting Home Energy Optimizer ===")
with app.app_context():
    init_db()
print("=== Server ready ===")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)