import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import sqlite3
import os

def generate_solar_data(date, panel_capacity_kw=5.0):
    """Generate 24 hours of solar generation data"""
    hours = []
    generation = []
    
    for hour in range(24):
        timestamp = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
        
        # Solar generation curve (sunrise ~6am, sunset ~8pm)
        if 6 <= hour <= 20:
            # Peak at noon (hour 12)
            hour_angle = (hour - 12) / 6  # Normalize around noon
            output = panel_capacity_kw * np.cos(hour_angle * np.pi / 2) ** 2
            # Add some randomness (clouds, etc)
            output *= np.random.uniform(0.85, 1.0)
        else:
            output = 0.0
        
        hours.append(timestamp)
        generation.append(round(output, 2))
    
    return pd.DataFrame({
        'timestamp': hours,
        'solar_generation_kw': generation
    })

def generate_home_consumption(date):
    """Generate 24 hours of home energy consumption"""
    hours = []
    consumption = []
    
    for hour in range(24):
        timestamp = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
        
        # Base load (fridge, always-on devices)
        base = 0.5
        
        # Morning peak (7-9am: cooking, showers)
        if 7 <= hour <= 9:
            peak = np.random.uniform(2.0, 3.5)
        # Evening peak (6-10pm: cooking, TV, lights)
        elif 18 <= hour <= 22:
            peak = np.random.uniform(2.5, 4.0)
        # Daytime (moderate usage)
        elif 10 <= hour <= 17:
            peak = np.random.uniform(0.8, 1.5)
        # Night (minimal usage)
        else:
            peak = np.random.uniform(0.2, 0.8)
        
        total = base + peak
        hours.append(timestamp)
        consumption.append(round(total, 2))
    
    return pd.DataFrame({
        'timestamp': hours,
        'home_consumption_kw': consumption
    })


def simulate_battery(solar_data, consumption_data, battery_capacity_kwh=13.5, max_charge_rate_kw=5.0):
    """Simulate battery charge/discharge based on solar and consumption"""
    
    # Merge the data
    df = solar_data.merge(consumption_data, on='timestamp')
    
    # Calculate net energy (positive = excess solar, negative = need from grid)
    df['net_energy_kw'] = df['solar_generation_kw'] - df['home_consumption_kw']
    
    # Simulate battery state
    battery_state = []
    battery_charge_kw = []
    grid_import = []
    grid_export = []
    
    current_battery = battery_capacity_kwh * 0.5  # Start at 50%
    
    for idx, row in df.iterrows():
        net = row['net_energy_kw']
        
        if net > 0:  # Excess solar
            # Charge battery
            charge_amount = min(net, max_charge_rate_kw, battery_capacity_kwh - current_battery)
            current_battery += charge_amount
            
            # Excess after charging goes to grid
            export = net - charge_amount
            grid_import.append(0)
            grid_export.append(round(export, 2))
            battery_charge_kw.append(round(charge_amount, 2))
            
        else:  # Need energy
            # Discharge battery first
            needed = abs(net)
            discharge_amount = min(needed, max_charge_rate_kw, current_battery)
            current_battery -= discharge_amount
            
            # Remaining need comes from grid
            from_grid = needed - discharge_amount
            grid_import.append(round(from_grid, 2))
            grid_export.append(0)
            battery_charge_kw.append(round(-discharge_amount, 2))  # Negative = discharge
        
        battery_state.append(round(current_battery, 2))
    
    df['battery_state_kwh'] = battery_state
    df['battery_charge_kw'] = battery_charge_kw
    df['grid_import_kw'] = grid_import
    df['grid_export_kw'] = grid_export
    
    return df

def save_to_database(df, database_url='sqlite:////tmp/energy_data.db'):
    """Save energy data to database"""
    if database_url.startswith('postgresql://'):
        from sqlalchemy import create_engine
        engine = create_engine(database_url)
        df.to_sql('energy_readings', engine, if_exists='append', index=False)
        print(f"Saved {len(df)} records to PostgreSQL")
    else:
        # Extract the actual path from sqlite:///path format
        db_path = database_url.replace('sqlite:///', '')
        
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        print(f"Saving to: {db_path}")
        conn = sqlite3.connect(db_path)
        df.to_sql('energy_readings', conn, if_exists='append', index=False)
        conn.close()
        print(f"Saved {len(df)} records to SQLite at {db_path}")
    
def generate_week_data(start_date, num_days=7):
    """Generate data for multiple days"""
    all_data = []
    
    for day in range(num_days):
        date = start_date + timedelta(days=day)
        solar = generate_solar_data(date)
        consumption = generate_home_consumption(date)
        system = simulate_battery(solar, consumption)
        all_data.append(system)
    
    return pd.concat(all_data, ignore_index=True)

if __name__ == "__main__":
    # Determine correct database path based on OS
    if os.name == 'nt':  # Windows
        db_path = os.path.join(os.path.dirname(__file__), 'energy_data.db')
    else:  # Linux/Unix
        db_path = '/tmp/energy_data.db'
    
    database_url = f'sqlite:///{db_path}'
    
    # Generate a week of data
    start_date = datetime.now().date() - timedelta(days=7)
    week_data = generate_week_data(start_date, num_days=7)
    
    # Save to database
    save_to_database(week_data, database_url)
    
    print(f"Generated {len(week_data)} hours of data")
    print(f"\nWeekly totals:")
    print(f"Solar generated: {week_data['solar_generation_kw'].sum():.1f}kWh")
    print(f"Home consumed: {week_data['home_consumption_kw'].sum():.1f}kWh")
    print(f"Grid imported: {week_data['grid_import_kw'].sum():.1f}kWh")
    print(f"Grid exported: {week_data['grid_export_kw'].sum():.1f}kWh")