import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class EnergyOptimizer:
    def __init__(self, electricity_rates=None):
        """
        Initialize optimizer with electricity rates
        rates: dict with 'peak', 'off_peak' prices per kWh
        """
        self.rates = electricity_rates or {
            'peak': 0.35,      # $0.35/kWh (4pm-9pm)
            'shoulder': 0.25,  # $0.25/kWh (7am-4pm, 9pm-10pm)
            'off_peak': 0.15   # $0.15/kWh (10pm-7am)
        }
    
    def get_rate_for_hour(self, hour):
        """Get electricity rate based on time of day"""
        if 16 <= hour < 21:  # 4pm-9pm
            return self.rates['peak']
        elif 22 <= hour or hour < 7:  # 10pm-7am
            return self.rates['off_peak']
        else:
            return self.rates['shoulder']
    
    def calculate_costs(self, df):
        """Calculate costs for grid import/export"""
        costs = []
        revenue = []
        
        for idx, row in df.iterrows():
            hour = pd.to_datetime(row['timestamp']).hour
            rate = self.get_rate_for_hour(hour)
            
            # Cost of importing from grid
            import_cost = row['grid_import_kw'] * rate
            costs.append(round(import_cost, 2))
            
            # Revenue from exporting to grid (typically lower than import rate)
            export_revenue = row['grid_export_kw'] * rate * 0.7  # Export rate ~70% of import
            revenue.append(round(export_revenue, 2))
        
        df['grid_cost'] = costs
        df['export_revenue'] = revenue
        df['net_cost'] = df['grid_cost'] - df['export_revenue']
        
        return df
    
    def optimize_battery_schedule(self, solar_forecast, consumption_forecast, 
                                   battery_capacity=13.5, current_battery=6.75):
        """
        Suggest optimal battery charge/discharge schedule
        Returns: recommendations for next 24 hours
        """
        recommendations = []
        
        for hour in range(24):
            solar = solar_forecast[hour] if hour < len(solar_forecast) else 0
            consumption = consumption_forecast[hour] if hour < len(consumption_forecast) else 1.0
            rate = self.get_rate_for_hour(hour)
            
            net = solar - consumption
            
            # Decision logic
            if net > 0:  # Excess solar
                action = "charge_battery"
                reason = "Store excess solar generation"
            elif rate >= self.rates['peak'] and current_battery > 2:  # Peak hours
                action = "discharge_battery"
                reason = f"Avoid peak rate (${rate}/kWh)"
            elif rate == self.rates['off_peak'] and current_battery < battery_capacity * 0.8:
                action = "charge_from_grid"
                reason = f"Cheap off-peak rate (${rate}/kWh)"
            else:
                action = "hold"
                reason = "Maintain current state"
            
            recommendations.append({
                'hour': hour,
                'rate': rate,
                'solar_forecast': solar,
                'consumption_forecast': consumption,
                'action': action,
                'reason': reason
            })
        
        return recommendations
    
    def compare_scenarios(self, df_with_battery, consumption_only):
        """
        Compare costs: with battery system vs grid-only
        Returns: savings analysis
        """
        # Grid-only cost (no battery)
        grid_only_cost = 0
        for idx, row in consumption_only.iterrows():
            hour = pd.to_datetime(row['timestamp']).hour
            rate = self.get_rate_for_hour(hour)
            grid_only_cost += row['home_consumption_kw'] * rate
        
        # With battery system
        with_battery = df_with_battery.copy()
        with_battery = self.calculate_costs(with_battery)
        battery_system_cost = with_battery['net_cost'].sum()
        
        savings = grid_only_cost - battery_system_cost
        savings_pct = (savings / grid_only_cost) * 100 if grid_only_cost > 0 else 0
        
        return {
            'grid_only_cost': round(grid_only_cost, 2),
            'with_battery_cost': round(battery_system_cost, 2),
            'savings': round(savings, 2),
            'savings_percent': round(savings_pct, 1),
            'daily_average_savings': round(savings / (len(df_with_battery) / 24), 2),
            'annual_projection': round(savings * (365 / (len(df_with_battery) / 24)), 2)
        }

if __name__ == "__main__":
    import sqlite3
    
    # Load data from database
    conn = sqlite3.connect('/tmp/energy_data.db')
    df = pd.read_sql_query('SELECT * FROM energy_readings', conn)
    conn.close()
    
    # Initialize optimizer
    optimizer = EnergyOptimizer()
    
    # Calculate costs
    df = optimizer.calculate_costs(df)
    
    # Create grid-only comparison
    consumption_only = df[['timestamp', 'home_consumption_kw']].copy()
    
    # Compare scenarios
    analysis = optimizer.compare_scenarios(df, consumption_only)
    
    print("COST ANALYSIS")
    print("=" * 50)
    print(f"Grid-only cost: ${analysis['grid_only_cost']}")
    print(f"With battery system: ${analysis['with_battery_cost']}")
    print(f"Total savings: ${analysis['savings']} ({analysis['savings_percent']}%)")
    print(f"Daily average savings: ${analysis['daily_average_savings']}")
    print(f"Annual projection: ${analysis['annual_projection']}")
    
    # Show optimization recommendations for next 24 hours
    print("\n" + "=" * 50)
    print("OPTIMIZATION RECOMMENDATIONS (Next 24 Hours)")
    print("=" * 50)
    
    # Use last day's pattern as forecast
    last_day = df.tail(24)
    solar_forecast = last_day['solar_generation_kw'].tolist()
    consumption_forecast = last_day['home_consumption_kw'].tolist()
    
    recommendations = optimizer.optimize_battery_schedule(solar_forecast, consumption_forecast)
    
    for rec in recommendations[:8]:  # Show first 8 hours
        print(f"Hour {rec['hour']:02d}: {rec['action']:20s} - {rec['reason']}")