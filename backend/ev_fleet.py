"""
EV Fleet Simulator with Vehicle-to-Grid (V2G) Capability
Simulates 25 electric vehicles that can charge and discharge to grid
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict
import sqlite3

@dataclass
class ElectricVehicle:
    """Represents a single EV with V2G capability"""
    id: int
    owner_name: str
    address: str
    model: str
    battery_capacity_kwh: float  # Total battery capacity
    current_charge_kwh: float    # Current charge level
    is_plugged_in: bool          # Currently connected to charger
    v2g_enabled: bool            # Owner opted into V2G program
    last_charge_time: datetime
    total_v2g_revenue: float     # Lifetime V2G earnings

class EVFleet:
    """Manages fleet of 25 EVs with V2G capability"""
    
    def __init__(self, num_evs=25):
        self.evs = self._generate_fleet(num_evs)
    
    def _generate_fleet(self, num_evs) -> List[ElectricVehicle]:
        """Generate diverse fleet of EVs"""
        
        # EV models with realistic battery capacities
        ev_models = [
            ('Tesla Model 3', 60.0),
            ('Tesla Model Y', 75.0),
            ('BYD Atto 3', 60.5),
            ('MG ZS EV', 51.1),
            ('Hyundai Ioniq 5', 72.6),
            ('Kia EV6', 77.4),
            ('Nissan Leaf', 40.0),
            ('Polestar 2', 78.0),
            ('Ford F-150 Lightning', 131.0),  # The beast
        ]
        
        # Australian suburbs
        suburbs = [
            'Bondi, NSW',
            'Carlton, VIC',
            'Fortitude Valley, QLD',
            'North Adelaide, SA',
            'Fremantle, WA'
        ]
        
        # Owner names
        first_names = ['James', 'Sarah', 'Michael', 'Emma', 'David', 'Olivia', 'Daniel', 'Sophie', 'Matthew', 'Chloe']
        last_names = ['Smith', 'Jones', 'Williams', 'Brown', 'Taylor', 'Anderson', 'Thomas', 'Jackson', 'White', 'Martin']
        
        fleet = []
        
        for i in range(num_evs):
            model, capacity = random.choice(ev_models)
            
            # Start with varying charge levels (20-90%)
            current_charge = capacity * random.uniform(0.2, 0.9)
            
            # Most EVs plugged in at night (assume it's evening)
            is_plugged = random.random() > 0.3  # 70% plugged in
            
            # 80% of owners opt into V2G (it's profitable!)
            v2g_enabled = random.random() > 0.2
            
            ev = ElectricVehicle(
                id=i + 1,
                owner_name=f"{random.choice(first_names)} {random.choice(last_names)}",
                address=random.choice(suburbs),
                model=model,
                battery_capacity_kwh=capacity,
                current_charge_kwh=round(current_charge, 2),
                is_plugged_in=is_plugged,
                v2g_enabled=v2g_enabled,
                last_charge_time=datetime.now() - timedelta(hours=random.randint(0, 12)),
                total_v2g_revenue=round(random.uniform(50, 500), 2)  # Historical earnings
            )
            
            fleet.append(ev)
        
        return fleet
    
    def get_fleet_status(self) -> Dict:
        """Get overall fleet statistics"""
        
        total_evs = len(self.evs)
        plugged_in = sum(1 for ev in self.evs if ev.is_plugged_in)
        v2g_active = sum(1 for ev in self.evs if ev.is_plugged_in and ev.v2g_enabled)
        
        total_capacity = sum(ev.battery_capacity_kwh for ev in self.evs)
        available_capacity = sum(ev.current_charge_kwh for ev in self.evs if ev.is_plugged_in and ev.v2g_enabled)
        
        # Calculate dispatchable power (can discharge)
        # Assume 11kW charger max, but most EVs discharge slower
        dispatchable_power = 0
        for ev in self.evs:
            if ev.is_plugged_in and ev.v2g_enabled and ev.current_charge_kwh > 10:  # Keep 10kWh reserve
                # Most EVs can discharge at 7-11kW
                max_discharge = 10.0  # kW
                dispatchable_power += max_discharge
        
        # Charging stats
        charging = sum(1 for ev in self.evs if ev.is_plugged_in and ev.current_charge_kwh < ev.battery_capacity_kwh * 0.95)
        full = sum(1 for ev in self.evs if ev.current_charge_kwh >= ev.battery_capacity_kwh * 0.95)
        
        return {
            'total_evs': total_evs,
            'plugged_in': plugged_in,
            'v2g_active': v2g_active,
            'not_connected': total_evs - plugged_in,
            'charging': charging,
            'full': full,
            'total_capacity_kwh': round(total_capacity, 1),
            'available_capacity_kwh': round(available_capacity, 1),
            'dispatchable_power_kw': round(dispatchable_power, 1),
            'fleet_utilization_pct': round((sum(ev.current_charge_kwh for ev in self.evs) / total_capacity) * 100, 1),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_evs_by_status(self) -> Dict:
        """Group EVs by current status"""
        
        charging = [ev for ev in self.evs if ev.is_plugged_in and ev.current_charge_kwh < ev.battery_capacity_kwh * 0.9]
        full = [ev for ev in self.evs if ev.is_plugged_in and ev.current_charge_kwh >= ev.battery_capacity_kwh * 0.9]
        v2g_discharging = [ev for ev in self.evs if ev.is_plugged_in and ev.v2g_enabled and ev.current_charge_kwh > ev.battery_capacity_kwh * 0.7]
        not_connected = [ev for ev in self.evs if not ev.is_plugged_in]
        
        return {
            'charging': [self._ev_to_dict(ev) for ev in charging],
            'full': [self._ev_to_dict(ev) for ev in full],
            'v2g_ready': [self._ev_to_dict(ev) for ev in v2g_discharging],
            'not_connected': [self._ev_to_dict(ev) for ev in not_connected]
        }
    
    def get_all_evs(self) -> List[Dict]:
        """Get list of all EVs with details"""
        return [self._ev_to_dict(ev) for ev in self.evs]
    
    def _ev_to_dict(self, ev: ElectricVehicle) -> Dict:
        """Convert EV to dictionary"""
        return {
            'id': ev.id,
            'owner_name': ev.owner_name,
            'address': ev.address,
            'model': ev.model,
            'battery_capacity_kwh': ev.battery_capacity_kwh,
            'current_charge_kwh': round(ev.current_charge_kwh, 2),
            'charge_percent': round((ev.current_charge_kwh / ev.battery_capacity_kwh) * 100, 1),
            'is_plugged_in': ev.is_plugged_in,
            'v2g_enabled': ev.v2g_enabled,
            'total_v2g_revenue': ev.total_v2g_revenue
        }
    
    def dispatch_v2g(self, required_power_kw: float) -> Dict:
        """
        Dispatch EVs for V2G discharge
        
        Args:
            required_power_kw: Power needed from EVs
        
        Returns:
            Dispatch result with EVs used and power provided
        """
        
        # Find EVs available for V2G discharge
        available = [
            ev for ev in self.evs 
            if ev.is_plugged_in and ev.v2g_enabled and ev.current_charge_kwh > 15  # Keep 15kWh reserve
        ]
        
        # Sort by charge level (discharge fullest first)
        available.sort(key=lambda ev: ev.current_charge_kwh, reverse=True)
        
        dispatched_evs = []
        total_power = 0
        
        for ev in available:
            if total_power >= required_power_kw:
                break
            
            # Each EV can discharge at ~10kW max
            discharge_power = min(10.0, required_power_kw - total_power)
            
            # Discharge for 30 minutes (0.5 hour)
            energy_discharged = discharge_power * 0.5  # kWh
            
            # Update EV state
            ev.current_charge_kwh = max(10, ev.current_charge_kwh - energy_discharged)  # Keep 10kWh minimum
            
            # Calculate revenue ($0.35/kWh peak rate)
            revenue = energy_discharged * 0.35
            ev.total_v2g_revenue += revenue
            
            dispatched_evs.append({
                'ev_id': ev.id,
                'owner': ev.owner_name,
                'model': ev.model,
                'power_kw': discharge_power,
                'energy_discharged_kwh': round(energy_discharged, 2),
                'revenue': round(revenue, 2)
            })
            
            total_power += discharge_power
        
        return {
            'evs_dispatched': len(dispatched_evs),
            'total_power_kw': round(total_power, 2),
            'target_power_kw': required_power_kw,
            'fulfilled': total_power >= required_power_kw,
            'evs': dispatched_evs,
            'total_revenue': round(sum(ev['revenue'] for ev in dispatched_evs), 2)
        }
    
    def smart_charging_schedule(self) -> Dict:
        """
        Generate smart charging schedule for next 24 hours
        Charge during off-peak, discharge during peak
        """
        
        schedule = []
        
        for hour in range(24):
            if 0 <= hour < 7:  # Off-peak - charge
                action = "charge"
                rate = 0.15  # $/kWh
                evs_charging = len([ev for ev in self.evs if ev.is_plugged_in and ev.current_charge_kwh < ev.battery_capacity_kwh * 0.9])
            elif 18 <= hour < 21:  # Peak - V2G discharge
                action = "v2g_discharge"
                rate = 0.35  # $/kWh
                evs_charging = len([ev for ev in self.evs if ev.is_plugged_in and ev.v2g_enabled])
            else:  # Shoulder - hold
                action = "hold"
                rate = 0.25  # $/kWh
                evs_charging = 0
            
            schedule.append({
                'hour': hour,
                'action': action,
                'rate': rate,
                'evs_active': evs_charging
            })
        
        return {'schedule': schedule}
    
    def calculate_daily_revenue(self) -> Dict:
        """Calculate potential daily V2G revenue"""
        
        # FCAS availability payment for EVs
        v2g_active = sum(1 for ev in self.evs if ev.is_plugged_in and ev.v2g_enabled)
        fcas_daily = (v2g_active * 100) / 365  # $100/year per EV
        
        # Peak discharge revenue (assume 2 hours per day at 10kW per EV)
        discharge_revenue = v2g_active * 10 * 2 * 0.35  # 10kW * 2hrs * $0.35/kWh
        
        # Off-peak charging cost savings
        charging_savings = v2g_active * 5 * 0.10  # 5kWh saved by smart charging
        
        return {
            'fcas_availability_daily': round(fcas_daily, 2),
            'v2g_discharge_daily': round(discharge_revenue, 2),
            'smart_charging_savings_daily': round(charging_savings, 2),
            'total_daily_revenue': round(fcas_daily + discharge_revenue + charging_savings, 2),
            'projected_annual_revenue': round((fcas_daily + discharge_revenue + charging_savings) * 365, 0)
        }


if __name__ == "__main__":
    # Test EV fleet
    print("=" * 60)
    print("EV FLEET WITH V2G - TEST")
    print("=" * 60)
    
    fleet = EVFleet(25)
    
    # Fleet status
    status = fleet.get_fleet_status()
    print(f"\n✅ Fleet Status:")
    print(f"   Total EVs: {status['total_evs']}")
    print(f"   Plugged In: {status['plugged_in']}")
    print(f"   V2G Active: {status['v2g_active']}")
    print(f"   Total Capacity: {status['total_capacity_kwh']:.1f} kWh")
    print(f"   Available Capacity: {status['available_capacity_kwh']:.1f} kWh")
    print(f"   Dispatchable Power: {status['dispatchable_power_kw']:.1f} kW")
    
    # V2G dispatch test
    print(f"\n✅ V2G Dispatch Test (100 kW required):")
    dispatch = fleet.dispatch_v2g(100)
    print(f"   EVs Dispatched: {dispatch['evs_dispatched']}")
    print(f"   Power Provided: {dispatch['total_power_kw']:.1f} kW")
    print(f"   Revenue: ${dispatch['total_revenue']:.2f}")
    
    # Revenue calculation
    print(f"\n✅ Daily Revenue Potential:")
    revenue = fleet.calculate_daily_revenue()
    print(f"   FCAS Availability: ${revenue['fcas_availability_daily']:.2f}")
    print(f"   V2G Discharge: ${revenue['v2g_discharge_daily']:.2f}")
    print(f"   Smart Charging Savings: ${revenue['smart_charging_savings_daily']:.2f}")
    print(f"   Total Daily: ${revenue['total_daily_revenue']:.2f}")
    print(f"   Projected Annual: ${revenue['projected_annual_revenue']:,.0f}")
    
    print("\n" + "=" * 60)
    print("✅ EV FLEET WORKING")
    print("=" * 60)