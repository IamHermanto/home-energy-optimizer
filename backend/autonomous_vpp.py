"""
Autonomous VPP Simulator with Proper Time Acceleration
FIXED: Now properly tracks simulated days and recharges batteries
"""

import threading
import time
import random
from datetime import datetime, timedelta
from typing import Callable

class AutonomousVPP:
    """Autonomous VPP that runs continuously with proper time simulation"""
    
    def __init__(self, vpp_aggregator, speed_multiplier=1):
        self.vpp = vpp_aggregator
        self.running = False
        self.thread = None
        self.speed_multiplier = speed_multiplier
        
        # Simulation state
        self.current_frequency = 50.0
        self.last_fcas_event = time.time()
        self.last_arbitrage_check = time.time()
        
        # FIXED: Track simulated time properly
        self.simulated_time = datetime.now()
        self.simulated_day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.simulated_days_elapsed = 0
        self.last_hour_simulated = self.simulated_time.hour
        
        # Event callbacks
        self.event_callbacks = []
        
        print(f"🚀 Autonomous VPP initialized (Speed: {speed_multiplier}x)")
    
    def register_event_callback(self, callback: Callable):
        """Register callback to be notified of events"""
        self.event_callbacks.append(callback)
    
    def _notify_event(self, event_type: str, details: dict):
        """Notify all registered callbacks of new event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'simulated_time': self.simulated_time.isoformat(),
            'simulated_day': self.simulated_days_elapsed,
            'type': event_type,
            'details': details
        }
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def _simulate_frequency(self):
        """Simulate realistic grid frequency behavior"""
        change = random.uniform(-0.02, 0.02)
        
        if self.current_frequency > 50.0:
            change -= 0.01
        elif self.current_frequency < 50.0:
            change += 0.01
        
        self.current_frequency += change
        
        event_probability = 0.05 * self.speed_multiplier / 10
        if random.random() < min(event_probability, 0.2):
            if random.random() < 0.5:
                self.current_frequency = random.uniform(49.85, 49.92)
            else:
                self.current_frequency = random.uniform(50.08, 50.15)
        
        self.current_frequency = max(49.80, min(50.20, self.current_frequency))
        return self.current_frequency
    
    def _check_fcas_response(self, frequency: float):
        """Check if FCAS response is needed"""
        deviation = abs(50.0 - frequency)
        
        if deviation >= 0.08:
            cooldown_seconds = 30 / self.speed_multiplier
            if time.time() - self.last_fcas_event < cooldown_seconds:
                return None
            
            self.last_fcas_event = time.time()
            result = self.vpp.simulate_fcas_event(frequency)
            
            self._notify_event('fcas_response', {
                'frequency_hz': frequency,
                'deviation_hz': round(deviation, 3),
                'action': result['action'],
                'batteries_dispatched': result['batteries_dispatched'],
                'power_kw': result['power_kw'],
                'response_time_seconds': result['response_time_seconds'],
                'revenue': result['revenue']
            })
            
            return result
        return None
    
    def _check_arbitrage_opportunity(self):
        """Check for time-based arbitrage opportunities"""
        hour = self.simulated_time.hour
        
        check_interval = 300 / self.speed_multiplier
        if time.time() - self.last_arbitrage_check < check_interval:
            return None
        
        self.last_arbitrage_check = time.time()
        fleet_status = self.vpp.get_fleet_status()
        
        if 0 <= hour < 7:
            utilization = fleet_status['fleet_utilization_pct']
            if utilization < 80:
                available_capacity = fleet_status['total_capacity_kwh'] - fleet_status['available_energy_kwh']
                if available_capacity > 50:
                    self._notify_event('arbitrage_charge', {
                        'hour': hour,
                        'reason': 'Off-peak charging (cheap power)',
                        'rate': 0.15,
                        'capacity_available_kwh': available_capacity
                    })
                    return {'action': 'charge', 'hour': hour}
        
        elif 18 <= hour < 21:
            if fleet_status['dispatchable_power_kw'] > 100:
                result = self.vpp.dispatch_batteries(
                    fleet_status['dispatchable_power_kw'],
                    f"Arbitrage: Peak discharge (${0.35:.2f}/kWh)"
                )
                
                self._notify_event('arbitrage_discharge', {
                    'hour': hour,
                    'reason': 'Peak discharge (high prices)',
                    'rate': 0.35,
                    'batteries_dispatched': result['batteries_dispatched'],
                    'power_kw': result['total_power_kw'],
                    'revenue': result['revenue']
                })
                return result
        return None
    
    def _recharge_batteries_for_hour(self, hour: int):
        """FIXED: Recharge batteries based on simulated hour"""
        self.vpp.fleet.simulate_hour(hour)
    
    def _check_new_simulated_day(self):
        """FIXED: Check if we've crossed into a new simulated day"""
        current_sim_day = self.simulated_time.date()
        if current_sim_day > self.simulated_day_start.date():
            self.simulated_days_elapsed += 1
            self.simulated_day_start = self.simulated_time.replace(hour=0, minute=0, second=0, microsecond=0)
            print(f"📅 Simulated Day {self.simulated_days_elapsed} started")
            
            self._notify_event('new_simulated_day', {
                'day_number': self.simulated_days_elapsed,
                'simulated_date': current_sim_day.isoformat()
            })
    
    def _simulation_loop(self):
        """FIXED: Main simulation loop"""
        print(f"🔋 Autonomous VPP Started (Speed: {self.speed_multiplier}x)")
        
        sleep_interval = 5 / self.speed_multiplier
        time_increment = timedelta(seconds=5 * self.speed_multiplier)
        
        while self.running:
            try:
                self.simulated_time += time_increment
                
                # FIXED: Recharge batteries when hour changes
                current_hour = self.simulated_time.hour
                if current_hour != self.last_hour_simulated:
                    self._recharge_batteries_for_hour(current_hour)
                    self.last_hour_simulated = current_hour
                
                # FIXED: Check if new day started
                self._check_new_simulated_day()
                
                frequency = self._simulate_frequency()
                self._check_fcas_response(frequency)
                self._check_arbitrage_opportunity()
                
                time.sleep(sleep_interval)
                
            except Exception as e:
                print(f"Simulation error: {e}")
                time.sleep(sleep_interval)
        
        print("🛑 Autonomous VPP Stopped")
    
    def start(self):
        """Start autonomous simulation"""
        if self.running:
            return {
                'status': 'already_running',
                'message': 'Autonomous VPP simulation already running'
            }
        
        # FIXED: Reset state on start
        self.running = True
        self.simulated_time = datetime.now()
        self.simulated_day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.simulated_days_elapsed = 0
        self.last_hour_simulated = self.simulated_time.hour
        
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()
        
        return {
            'status': 'started',
            'message': f'Autonomous VPP simulation started (Speed: {self.speed_multiplier}x)',
            'speed_multiplier': self.speed_multiplier
        }
    
    def stop(self):
        """Stop autonomous simulation"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        
        return {
            'status': 'stopped',
            'message': 'Autonomous VPP simulation stopped',
            'simulated_days_elapsed': self.simulated_days_elapsed
        }
    
    def get_status(self):
        """Get current simulation status"""
        return {
            'running': self.running,
            'current_frequency_hz': round(self.current_frequency, 3),
            'frequency_status': self._get_frequency_status(),
            'last_fcas_event': datetime.fromtimestamp(self.last_fcas_event).isoformat(),
            'simulation_mode': 'autonomous',
            'speed_multiplier': self.speed_multiplier,
            'simulated_time': self.simulated_time.isoformat(),
            'simulated_hour': self.simulated_time.hour,
            'simulated_days_elapsed': self.simulated_days_elapsed,
            'simulated_day_start': self.simulated_day_start.isoformat()
        }
    
    def _get_frequency_status(self):
        """Get human-readable frequency status"""
        deviation = abs(50.0 - self.current_frequency)
        
        if deviation < 0.05:
            return 'normal'
        elif deviation < 0.08:
            return 'warning'
        else:
            return 'critical'