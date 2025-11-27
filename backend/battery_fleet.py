import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List
import random

@dataclass
class BatterySystem:
    """Represents a single home battery system"""
    id: int
    location: str
    latitude: float
    longitude: float
    battery_capacity_kwh: float
    solar_capacity_kw: float
    home_size: str  # 'small', 'medium', 'large'
    panel_orientation: str  # 'north', 'east', 'west'
    current_battery_state_kwh: float
    is_available: bool
    last_updated: datetime

class BatteryFleet:
    """Manages a fleet of 100+ battery systems"""
    
    def __init__(self, num_batteries=100):
        self.batteries = self._generate_fleet(num_batteries)
        
    def _generate_fleet(self, num_batteries) -> List[BatterySystem]:
        """Generate diverse fleet of batteries across Australia"""
        
        # Australian cities with coordinates
        locations = [
            ('Melbourne', -37.8136, 144.9631),
            ('Sydney', -33.8688, 151.2093),
            ('Brisbane', -27.4698, 153.0251),
            ('Adelaide', -34.9285, 138.6007),
            ('Perth', -31.9505, 115.8605),
        ]
        
        # Battery sizes (realistic Tesla Powerwall and competitors)
        battery_sizes = [10.0, 13.5, 16.0]  # kWh
        
        # Solar panel sizes
        solar_sizes = [3.0, 5.0, 6.6, 8.0, 10.0]  # kW
        
        # Home sizes
        home_sizes = ['small', 'medium', 'large']
        
        # Panel orientations
        orientations = ['north', 'east', 'west']
        
        fleet = []
        
        for i in range(num_batteries):
            location, lat, lon = random.choice(locations)
            battery_capacity = random.choice(battery_sizes)
            
            # Start batteries at random charge levels (30-80%)
            initial_charge = battery_capacity * random.uniform(0.3, 0.8)
            
            battery = BatterySystem(
                id=i + 1,
                location=location,
                latitude=lat + random.uniform(-0.5, 0.5),  # Spread around city
                longitude=lon + random.uniform(-0.5, 0.5),
                battery_capacity_kwh=battery_capacity,
                solar_capacity_kw=random.choice(solar_sizes),
                home_size=random.choice(home_sizes),
                panel_orientation=random.choice(orientations),
                current_battery_state_kwh=round(initial_charge, 2),
                is_available=random.random() > 0.1,  # 90% availability
                last_updated=datetime.now()
            )
            
            fleet.append(battery)
        
        return fleet
    
    def get_fleet_status(self):
        """Get overall fleet statistics"""
        total_capacity = sum(b.battery_capacity_kwh for b in self.batteries)
        available_capacity = sum(b.current_battery_state_kwh for b in self.batteries if b.is_available)
        active_batteries = sum(1 for b in self.batteries if b.is_available)
        
        # Calculate how much power we can discharge RIGHT NOW
        dispatchable_power_kw = sum(
            min(b.current_battery_state_kwh * 0.8, 5.0)  # Max 5kW discharge rate
            for b in self.batteries 
            if b.is_available and b.current_battery_state_kwh > 2.0  # Keep 2kWh reserve
        )
        
        return {
            'total_batteries': len(self.batteries),
            'active_batteries': active_batteries,
            'offline_batteries': len(self.batteries) - active_batteries,
            'total_capacity_kwh': round(total_capacity, 2),
            'available_energy_kwh': round(available_capacity, 2),
            'dispatchable_power_kw': round(dispatchable_power_kw, 2),
            'fleet_utilization_pct': round((available_capacity / total_capacity) * 100, 1),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_batteries_by_location(self):
        """Group batteries by city"""
        location_stats = {}
        
        for battery in self.batteries:
            if battery.location not in location_stats:
                location_stats[battery.location] = {
                    'count': 0,
                    'total_capacity_kwh': 0,
                    'available_capacity_kwh': 0
                }
            
            location_stats[battery.location]['count'] += 1
            location_stats[battery.location]['total_capacity_kwh'] += battery.battery_capacity_kwh
            if battery.is_available:
                location_stats[battery.location]['available_capacity_kwh'] += battery.current_battery_state_kwh
        
        return location_stats
    
    def find_batteries_for_dispatch(self, required_power_kw):
        """Find which batteries to dispatch for a given power requirement"""
        
        # Filter available batteries with sufficient charge
        available = [
            b for b in self.batteries 
            if b.is_available and b.current_battery_state_kwh > 2.0
        ]
        
        # Sort by state of charge (dispatch fullest batteries first)
        available.sort(key=lambda b: b.current_battery_state_kwh, reverse=True)
        
        selected_batteries = []
        total_power_kw = 0
        
        for battery in available:
            if total_power_kw >= required_power_kw:
                break
            
            # Each battery can discharge up to 5kW
            available_power = min(battery.current_battery_state_kwh * 0.8, 5.0)
            selected_batteries.append({
                'battery_id': battery.id,
                'location': battery.location,
                'power_kw': available_power
            })
            total_power_kw += available_power
        
        return {
            'batteries_dispatched': len(selected_batteries),
            'total_power_kw': round(total_power_kw, 2),
            'target_power_kw': required_power_kw,
            'fulfilled': total_power_kw >= required_power_kw,
            'batteries': selected_batteries
        }
    
    def simulate_hour(self, hour_of_day):
        """Simulate one hour of operation for entire fleet"""
        
        for battery in self.batteries:
            if not battery.is_available:
                continue
            
            # Generate solar for this battery (depends on panel orientation, time of day)
            solar_generation = self._calculate_solar(
                battery.solar_capacity_kw,
                battery.panel_orientation,
                hour_of_day
            )
            
            # Generate consumption for this battery
            consumption = self._calculate_consumption(
                battery.home_size,
                hour_of_day
            )
            
            # Update battery state
            net_energy = solar_generation - consumption
            new_state = battery.current_battery_state_kwh + net_energy
            
            # Clamp to battery limits
            battery.current_battery_state_kwh = max(0, min(battery.battery_capacity_kwh, new_state))
            battery.last_updated = datetime.now()
    
    def _calculate_solar(self, capacity_kw, orientation, hour):
        """Calculate solar generation for a given hour"""
        
        # No solar at night
        if hour < 6 or hour > 20:
            return 0.0
        
        # Peak solar hours differ by orientation
        if orientation == 'east':
            peak_hour = 9
        elif orientation == 'west':
            peak_hour = 15
        else:  # north (best)
            peak_hour = 12
        
        # Calculate output based on distance from peak (using normalization)
        # At peak hour (e.g., noon for north-facing): hour_angle = 0
        # 3 hours before/after peak: hour_angle = ±0.5
        # 6 hours away: hour_angle = ±1.0
        hour_angle = (hour - peak_hour) / 6
        
        # Bell-curve formula (NOT LINEAR)
        output = capacity_kw * np.cos(hour_angle * np.pi / 2) ** 2
        
        # Add randomness (clouds)
        output *= np.random.uniform(0.85, 1.0)
        
        return round(output, 2)
    
    def _calculate_consumption(self, home_size, hour):
        """Calculate consumption based on home size and time"""
        
        # Base load by home size
        base_loads = {
            'small': 0.3,
            'medium': 0.5,
            'large': 0.8
        }
        
        base = base_loads[home_size]
        
        # Time-of-day multiplier
        if 7 <= hour <= 9:  # Morning peak
            multiplier = np.random.uniform(4, 7)
        elif 18 <= hour <= 22:  # Evening peak
            multiplier = np.random.uniform(5, 8)
        elif 10 <= hour <= 17:  # Daytime
            multiplier = np.random.uniform(2, 4)
        else:  # Night
            multiplier = np.random.uniform(0.5, 1.5)
        
        return round(base * multiplier, 2)
    
    def to_dataframe(self):
        """Export fleet to pandas DataFrame"""
        data = []
        for b in self.batteries:
            data.append({
                'battery_id': b.id,
                'location': b.location,
                'latitude': b.latitude,
                'longitude': b.longitude,
                'battery_capacity_kwh': b.battery_capacity_kwh,
                'solar_capacity_kw': b.solar_capacity_kw,
                'home_size': b.home_size,
                'panel_orientation': b.panel_orientation,
                'current_state_kwh': b.current_battery_state_kwh,
                'state_of_charge_pct': round((b.current_battery_state_kwh / b.battery_capacity_kwh) * 100, 1),
                'is_available': b.is_available,
                'last_updated': b.last_updated
            })
        
        return pd.DataFrame(data)


def generate_fleet_data(start_date, num_days=7, num_batteries=100):
    """Generate week of data for entire fleet"""
    
    fleet = BatteryFleet(num_batteries)
    all_hourly_data = []
    
    for day in range(num_days):
        date = start_date + timedelta(days=day)
        
        for hour in range(24):
            timestamp = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
            
            # Simulate this hour
            fleet.simulate_hour(hour)
            
            # Record fleet status
            status = fleet.get_fleet_status()
            status['timestamp'] = timestamp
            all_hourly_data.append(status)
    
    return pd.DataFrame(all_hourly_data), fleet


if __name__ == "__main__":
    # Generate fleet
    fleet = BatteryFleet(100)
    
    print("=" * 60)
    print("VPP BATTERY FLEET STATUS")
    print("=" * 60)
    
    # Fleet overview
    status = fleet.get_fleet_status()
    print(f"\nTotal Batteries: {status['total_batteries']}")
    print(f"Active Batteries: {status['active_batteries']}")
    print(f"Offline Batteries: {status['offline_batteries']}")
    print(f"Total Capacity: {status['total_capacity_kwh']:.1f} kWh")
    print(f"Available Energy: {status['available_energy_kwh']:.1f} kWh")
    print(f"Dispatchable Power: {status['dispatchable_power_kw']:.1f} kW")
    print(f"Fleet Utilization: {status['fleet_utilization_pct']}%")
    
    # Location breakdown
    print("\n" + "=" * 60)
    print("BATTERIES BY LOCATION")
    print("=" * 60)
    
    locations = fleet.get_batteries_by_location()
    for city, stats in locations.items():
        print(f"\n{city}:")
        print(f"  Batteries: {stats['count']}")
        print(f"  Capacity: {stats['total_capacity_kwh']:.1f} kWh")
        print(f"  Available: {stats['available_capacity_kwh']:.1f} kWh")
    
    # Test dispatch
    print("\n" + "=" * 60)
    print("DISPATCH SIMULATION")
    print("=" * 60)
    
    required_power = 250  # kW
    dispatch = fleet.find_batteries_for_dispatch(required_power)
    
    print(f"\nTarget Power: {required_power} kW")
    print(f"Batteries Dispatched: {dispatch['batteries_dispatched']}")
    print(f"Total Power Available: {dispatch['total_power_kw']} kW")
    print(f"Requirement Fulfilled: {'Yes' if dispatch['fulfilled'] else 'No'}")
    
    # Export to CSV
    df = fleet.to_dataframe()
    df.to_csv('vpp_fleet_status.csv', index=False)
    print(f"\n✅ Fleet data exported to vpp_fleet_status.csv")
    
    # Generate week of historical data
    print("\n" + "=" * 60)
    print("GENERATING HISTORICAL DATA (7 DAYS)")
    print("=" * 60)
    
    start_date = datetime.now().date() - timedelta(days=7)
    history_df, _ = generate_fleet_data(start_date, num_days=7, num_batteries=100)
    history_df.to_csv('vpp_fleet_history.csv', index=False)
    print(f"✅ Historical data exported to vpp_fleet_history.csv")
    print(f"   Total records: {len(history_df)}")