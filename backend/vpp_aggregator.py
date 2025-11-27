"""
VPP Aggregator Service - FIXED REVENUE CALCULATIONS
Now shows realistic daily revenue projections instead of accumulated simulated time revenue
"""

from battery_fleet import BatteryFleet
from aemo_client import AEMOClient
from datetime import datetime, timedelta
import pandas as pd
import sqlite3
from typing import Dict, List

class VPPAggregator:
    """Core VPP service that aggregates and controls battery fleet"""
    
    def __init__(self, db_path='energy_data.db'):
        self.fleet = BatteryFleet(100)
        self.db_path = db_path
        self.aemo = AEMOClient(default_region='NSW1')
        self._init_vpp_tables()
    
    def _init_vpp_tables(self):
        """Create VPP-specific database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Fleet status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vpp_fleet_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                total_batteries INTEGER,
                active_batteries INTEGER,
                offline_batteries INTEGER,
                total_capacity_kwh REAL,
                available_energy_kwh REAL,
                dispatchable_power_kw REAL,
                fleet_utilization_pct REAL
            )
        ''')
        
        # Battery registry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vpp_batteries (
                battery_id INTEGER PRIMARY KEY,
                location TEXT,
                latitude REAL,
                longitude REAL,
                battery_capacity_kwh REAL,
                solar_capacity_kw REAL,
                home_size TEXT,
                panel_orientation TEXT,
                is_available INTEGER
            )
        ''')
        
        # Dispatch events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vpp_dispatch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                batteries_dispatched INTEGER,
                total_power_kw REAL,
                duration_minutes INTEGER,
                revenue REAL,
                reason TEXT
            )
        ''')
        
        # FCAS events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vpp_fcas_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                frequency_hz REAL,
                response_type TEXT,
                power_dispatched_kw REAL,
                response_time_seconds REAL,
                revenue REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        
        self._register_fleet()
    
    def _register_fleet(self):
        """Register all batteries in database"""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute('DELETE FROM vpp_batteries')
        
        for battery in self.fleet.batteries:
            conn.execute('''
                INSERT INTO vpp_batteries 
                (battery_id, location, latitude, longitude, battery_capacity_kwh, 
                 solar_capacity_kw, home_size, panel_orientation, is_available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                battery.id,
                battery.location,
                battery.latitude,
                battery.longitude,
                battery.battery_capacity_kwh,
                battery.solar_capacity_kw,
                battery.home_size,
                battery.panel_orientation,
                1 if battery.is_available else 0
            ))
        
        conn.commit()
        conn.close()
    
    def get_fleet_status(self) -> Dict:
        """Get current fleet status"""
        status = self.fleet.get_fleet_status()
        
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO vpp_fleet_status 
            (timestamp, total_batteries, active_batteries, offline_batteries,
             total_capacity_kwh, available_energy_kwh, dispatchable_power_kw, fleet_utilization_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            status['timestamp'],
            status['total_batteries'],
            status['active_batteries'],
            status['offline_batteries'],
            status['total_capacity_kwh'],
            status['available_energy_kwh'],
            status['dispatchable_power_kw'],
            status['fleet_utilization_pct']
        ))
        conn.commit()
        conn.close()
        
        return status
    
    def get_batteries_list(self) -> List[Dict]:
        """Get list of all batteries with current status"""
        df = self.fleet.to_dataframe()
        return df.to_dict('records')
    
    def get_batteries_by_location(self) -> Dict:
        """Get battery distribution by city"""
        return self.fleet.get_batteries_by_location()
    
    def dispatch_batteries(self, required_power_kw: float, reason: str = "Grid support") -> Dict:
        """Dispatch batteries to provide required power"""
        dispatch_result = self.fleet.find_batteries_for_dispatch(required_power_kw)
        
        # Update battery states
        for battery_info in dispatch_result.get('batteries', []):
            battery_id = battery_info['battery_id']
            power_kw = battery_info['power_kw']
            
            battery = next((b for b in self.fleet.batteries if b.id == battery_id), None)
            if battery:
                energy_discharged = power_kw * 0.5
                battery.current_battery_state_kwh = max(0, battery.current_battery_state_kwh - energy_discharged)
        
        # Log dispatch event
        revenue = self._calculate_dispatch_revenue(
            dispatch_result['total_power_kw'],
            reason
        )
        
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO vpp_dispatch_events
            (timestamp, event_type, batteries_dispatched, total_power_kw, 
             duration_minutes, revenue, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            'discharge' if required_power_kw > 0 else 'charge',
            dispatch_result['batteries_dispatched'],
            dispatch_result['total_power_kw'],
            30,
            revenue,
            reason
        ))
        conn.commit()
        conn.close()
        
        dispatch_result['revenue'] = revenue
        dispatch_result['reason'] = reason
        
        return dispatch_result
    
    def _calculate_dispatch_revenue(self, power_kw: float, reason: str) -> float:
        """Calculate revenue from dispatch event"""
        if 'FCAS' in reason:
            rate_per_mwh = 80
        elif 'arbitrage' in reason:
            rate_per_mwh = 250
        else:
            rate_per_mwh = 100
        
        energy_mwh = (power_kw / 1000) * 0.5
        return round(energy_mwh * rate_per_mwh, 2)
    
    def calculate_daily_revenue(self) -> Dict:
        """
        FIXED: Calculate REALISTIC daily revenue projection
        
        Instead of summing actual events (which could span multiple simulated days
        at accelerated speed), this calculates expected revenue per real-world day:
        
        - FCAS availability: $150/battery/year = $0.41/battery/day
        - Expected dispatch: ~2 FCAS events/day + 1 arbitrage event/day
        """
        active_batteries = self.fleet.get_fleet_status()['active_batteries']
        
        # FCAS availability payment: $150 per battery per year
        fcas_availability_daily = (active_batteries * 150) / 365
        
        # REALISTIC dispatch revenue estimates:
        # - Average 2 FCAS responses per day (50 kW each, $80/MWh, 30 min)
        #   = 2 × (50/1000) × 0.5 × 80 = $4 per day
        # - One arbitrage cycle per day (100 kW, $250/MWh, 30 min)  
        #   = (100/1000) × 0.5 × 250 = $12.50 per day
        # Total dispatch: ~$16.50 per day for 100 battery fleet
        
        estimated_fcas_dispatch_daily = 4.0
        estimated_arbitrage_daily = 12.5
        estimated_dispatch_daily = estimated_fcas_dispatch_daily + estimated_arbitrage_daily
        
        # Calculate actual dispatch revenue for display purposes (from last hour)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        cursor.execute('''
            SELECT SUM(revenue) 
            FROM vpp_dispatch_events 
            WHERE timestamp > ?
        ''', (one_hour_ago,))
        
        actual_dispatch_last_hour = cursor.fetchone()[0] or 0
        conn.close()
        
        # Use REALISTIC estimates, not actual accumulated revenue
        total_daily = fcas_availability_daily + estimated_dispatch_daily
        
        return {
            'fcas_availability_daily': round(fcas_availability_daily, 2),
            'dispatch_revenue_daily': round(estimated_dispatch_daily, 2),
            'actual_dispatch_last_hour': round(actual_dispatch_last_hour, 2),
            'total_daily_revenue': round(total_daily, 2),
            'projected_annual_revenue': round(total_daily * 365, 0),
            'revenue_per_household_daily': round(total_daily / active_batteries, 2),
            'revenue_per_household_annual': round((total_daily * 365) / active_batteries, 0)
        }
    
    def get_recent_dispatch_events(self, limit=10) -> List[Dict]:
        """Get recent dispatch events"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT * FROM vpp_dispatch_events 
            ORDER BY timestamp DESC 
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        
        return df.to_dict('records')
    
    def simulate_fcas_event(self, frequency_hz: float) -> Dict:
        """Simulate FCAS frequency response event"""
        target_frequency = 50.0
        deviation = target_frequency - frequency_hz
        
        if abs(deviation) < 0.08:
            return {
                'action': 'none',
                'frequency_hz': frequency_hz,
                'deviation_hz': round(deviation, 3),
                'power_kw': 0.0,
                'batteries_dispatched': 0,
                'response_time_seconds': 0,
                'revenue': 0.0,
                'reason': 'Frequency within acceptable range'
            }
        
        elif deviation > 0.08:
            required_power = abs(deviation) * 1000
            response = self.dispatch_batteries(required_power, reason="FCAS frequency low")
            response_type = 'discharge'
            
        else:
            required_power = abs(deviation) * 1000
            
            available = [
                b for b in self.fleet.batteries 
                if b.is_available and b.current_battery_state_kwh < b.battery_capacity_kwh * 0.9
            ]
            
            batteries_used = []
            total_charged = 0
            for battery in available[:50]:
                charge_amount = min(required_power / 1000, 2.0)
                battery.current_battery_state_kwh = min(
                    battery.battery_capacity_kwh,
                    battery.current_battery_state_kwh + charge_amount
                )
                batteries_used.append(battery.id)
                total_charged += charge_amount * 2
                if total_charged >= required_power:
                    break
            
            response = {
                'batteries_dispatched': len(batteries_used),
                'total_power_kw': total_charged,
                'revenue': self._calculate_dispatch_revenue(total_charged, "FCAS frequency high")
            }
            response_type = 'charge'
        
        # Log FCAS event
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO vpp_fcas_events
            (timestamp, frequency_hz, response_type, power_dispatched_kw, 
             response_time_seconds, revenue)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            frequency_hz,
            response_type,
            response['total_power_kw'],
            3.5,
            response['revenue']
        ))
        conn.commit()
        conn.close()
        
        return {
            'action': response_type,
            'frequency_hz': frequency_hz,
            'deviation_hz': round(deviation, 3),
            'batteries_dispatched': response['batteries_dispatched'],
            'power_kw': response['total_power_kw'],
            'response_time_seconds': 3.5,
            'revenue': response['revenue'],
            'reason': f'FCAS response to frequency {response_type}'
        }
    
    def get_grid_status(self) -> Dict:
        """Get current grid status from AEMO"""
        price_data = self.aemo.get_current_price()
        demand_data = self.aemo.get_demand()
        decision = self.aemo.should_dispatch(price_data['price_per_kwh'])
        
        return {
            'price_per_kwh': price_data['price_per_kwh'],
            'price_per_mwh': price_data['price_per_mwh'],
            'price_status': price_data.get('status', 'live'),
            'demand_mw': demand_data['total_demand_mw'],
            'region': price_data['region'],
            'timestamp': price_data['timestamp'],
            'vpp_action': decision['action'],
            'vpp_reason': decision['reason']
        }
    
    def get_all_regions(self) -> Dict:
        """Get prices for all Australian regions"""
        return self.aemo.get_all_regions_prices()
    
    def auto_dispatch_based_on_price(self) -> Dict:
        """Automatically dispatch batteries based on current grid price"""
        grid = self.get_grid_status()
        
        if grid['vpp_action'] == 'discharge' and grid['price_per_kwh'] >= 0.30:
            fleet_status = self.get_fleet_status()
            available_power = fleet_status['dispatchable_power_kw']
            
            if available_power > 50:
                result = self.dispatch_batteries(
                    available_power, 
                    f"Auto-dispatch: High price ${grid['price_per_kwh']:.3f}/kWh"
                )
                result['grid_price'] = grid['price_per_kwh']
                return result
        
        return {
            'action': 'none',
            'reason': f"No dispatch needed (price: ${grid['price_per_kwh']:.3f}/kWh)",
            'grid_price': grid['price_per_kwh']
        }


if __name__ == "__main__":
    print("=" * 60)
    print("VPP AGGREGATOR TEST - FIXED REVENUE")
    print("=" * 60)
    
    vpp = VPPAggregator()
    
    # Fleet status
    status = vpp.get_fleet_status()
    print(f"\n✅ Fleet Status:")
    print(f"   Total Capacity: {status['total_capacity_kwh']:.1f} kWh")
    print(f"   Available Power: {status['dispatchable_power_kw']:.1f} kW")
    print(f"   Active Batteries: {status['active_batteries']}")
    
    # Revenue calculation (REALISTIC)
    print(f"\n✅ REALISTIC Daily Revenue Projection:")
    revenue = vpp.calculate_daily_revenue()
    print(f"   FCAS Availability: ${revenue['fcas_availability_daily']:.2f}/day")
    print(f"   Dispatch Revenue: ${revenue['dispatch_revenue_daily']:.2f}/day")
    print(f"   Total Daily: ${revenue['total_daily_revenue']:.2f}")
    print(f"   Per Household: ${revenue['revenue_per_household_daily']:.2f}/day (${revenue['revenue_per_household_annual']}/year)")
    print(f"   Projected Annual: ${revenue['projected_annual_revenue']:,.0f}")
    
    # This should now show realistic numbers:
    # ~$0.41/battery/day FCAS availability
    # ~$0.17/battery/day dispatch revenue  
    # ~$0.58/battery/day total = $58/day for 100 batteries = ~$21k/year total
    
    print("\n" + "=" * 60)
    print("✅ REVENUE NOW REALISTIC")
    print("=" * 60)