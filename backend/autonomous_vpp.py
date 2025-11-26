"""
Autonomous VPP Simulator with Demo Speed Control
Runs continuously in background, simulating real VPP operations

NEW: Speed multiplier for demos (60x = 1 minute becomes 1 second)
"""

import threading
import time
import random
from datetime import datetime, timedelta
from typing import Callable

class AutonomousVPP:
    """
    Autonomous VPP that runs continuously:
    - Monitors simulated grid frequency
    - Auto-responds to frequency deviations (FCAS)
    - Executes time-based arbitrage (charge midnight, discharge 6pm)
    - Logs all events in real-time
    
    NEW: Configurable speed for demos
    """
    
    def __init__(self, vpp_aggregator, speed_multiplier=1):
        """
        Args:
            vpp_aggregator: VPP system to control
            speed_multiplier: Time speed multiplier
                - 1 = Real-time (default)
                - 10 = 10x faster (6 minutes = 1 minute)
                - 60 = 60x faster (1 hour = 1 minute) ← DEMO MODE
        """
        self.vpp = vpp_aggregator
        self.running = False
        self.thread = None
        self.speed_multiplier = speed_multiplier
        
        # Simulation state
        self.current_frequency = 50.0
        self.last_fcas_event = time.time()
        self.last_arbitrage_check = time.time()
        self.simulated_time = datetime.now()
        
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
            'type': event_type,
            'details': details
        }
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def _simulate_frequency(self):
        """
        Simulate realistic grid frequency behavior
        - Normal: 49.95-50.05 Hz
        - Minor events: 49.85-49.95 or 50.05-50.15 Hz
        - Major events: <49.85 or >50.15 Hz (rare)
        """
        # Random walk with mean reversion to 50.0 Hz
        change = random.uniform(-0.02, 0.02)
        
        # Mean reversion - pull back toward 50.0
        if self.current_frequency > 50.0:
            change -= 0.01
        elif self.current_frequency < 50.0:
            change += 0.01
        
        self.current_frequency += change
        
        # Occasional major events (higher probability for demo)
        event_probability = 0.05 * self.speed_multiplier / 10  # Scale with speed
        if random.random() < min(event_probability, 0.2):  # Cap at 20%
            if random.random() < 0.5:
                self.current_frequency = random.uniform(49.85, 49.92)  # Low frequency event
            else:
                self.current_frequency = random.uniform(50.08, 50.15)  # High frequency event
        
        # Keep within realistic bounds
        self.current_frequency = max(49.80, min(50.20, self.current_frequency))
        
        return self.current_frequency
    
    def _check_fcas_response(self, frequency: float):
        """
        Check if FCAS response is needed
        Responds if frequency deviates >0.08 Hz from 50.0
        """
        deviation = abs(50.0 - frequency)
        
        if deviation >= 0.08:
            # Cooldown: Don't trigger FCAS more than once per 30 seconds (scaled by speed)
            cooldown_seconds = 30 / self.speed_multiplier
            if time.time() - self.last_fcas_event < cooldown_seconds:
                return None
            
            self.last_fcas_event = time.time()
            
            # Trigger FCAS response
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
        """
        Check for time-based arbitrage opportunities
        - Charge batteries during off-peak (midnight-7am)
        - Discharge during peak (6pm-9pm)
        """
        # Use simulated time, not real time
        hour = self.simulated_time.hour
        
        # Check every 5 minutes (scaled by speed)
        check_interval = 300 / self.speed_multiplier  # 300 seconds = 5 minutes
        if time.time() - self.last_arbitrage_check < check_interval:
            return None
        
        self.last_arbitrage_check = time.time()
        
        fleet_status = self.vpp.get_fleet_status()
        
        # Off-peak charging (midnight to 7am)
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
        
        # Peak discharge (6pm to 9pm)
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
    
    def _simulation_loop(self):
        """Main simulation loop - runs continuously"""
        print(f"🔋 Autonomous VPP Started (Speed: {self.speed_multiplier}x)")
        print("=" * 60)
        
        # Calculate sleep interval based on speed
        # At 1x speed: 5 seconds
        # At 60x speed: 5/60 = 0.083 seconds
        sleep_interval = 5 / self.speed_multiplier
        
        # Calculate time increment per cycle
        # At 1x speed: 5 seconds simulated time
        # At 60x speed: 5 minutes simulated time
        time_increment = timedelta(seconds=5 * self.speed_multiplier)
        
        print(f"Sleep interval: {sleep_interval:.3f}s (updates every {sleep_interval:.3f} real seconds)")
        print(f"Time increment: {time_increment} per cycle")
        print(f"At this speed, 1 real minute = {self.speed_multiplier} simulated minutes")
        print("=" * 60)
        
        while self.running:
            try:
                # Advance simulated time
                self.simulated_time += time_increment
                
                # Simulate grid frequency
                frequency = self._simulate_frequency()
                
                # Check if FCAS response needed
                self._check_fcas_response(frequency)
                
                # Check for arbitrage opportunities
                self._check_arbitrage_opportunity()
                
                # Update fleet periodically
                if random.random() < 0.02 * (self.speed_multiplier / 10):
                    self.vpp.fleet.simulate_hour(self.simulated_time.hour)
                
                # Sleep for scaled interval
                time.sleep(sleep_interval)
                
            except Exception as e:
                print(f"Simulation error: {e}")
                time.sleep(sleep_interval)
        
        print("🛑 Autonomous VPP Stopped")
    
    def start(self):
        """Start autonomous simulation in background thread"""
        if self.running:
            print("⚠️  Autonomous VPP already running")
            return {
                'status': 'already_running',
                'message': 'Autonomous VPP simulation already running'
            }
        
        self.running = True
        self.simulated_time = datetime.now()  # Reset simulated time
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
            'message': 'Autonomous VPP simulation stopped'
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
            'simulated_hour': self.simulated_time.hour
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


if __name__ == "__main__":
    # Test autonomous simulator with different speeds
    from vpp_aggregator import VPPAggregator
    
    print("=" * 60)
    print("Testing Autonomous VPP Simulator with Speed Options")
    print("=" * 60)
    
    vpp = VPPAggregator()
    
    # Test with 10x speed for demo
    print("\n🚀 Testing with 10x speed (demo mode)")
    auto_vpp = AutonomousVPP(vpp, speed_multiplier=10)
    
    # Register event callback
    def print_event(event):
        sim_time = event.get('simulated_time', '')
        print(f"[{event['timestamp']}] (Sim: {sim_time}) {event['type']}: {event['details']}")
    
    auto_vpp.register_event_callback(print_event)
    
    # Start simulation
    auto_vpp.start()
    
    print("\n✅ Simulation running for 30 seconds (10x speed = 5 simulated minutes)...\n")
    
    # Let it run for 30 seconds
    time.sleep(30)
    
    # Stop
    auto_vpp.stop()
    
    print("\n✅ Simulation stopped")
    print("\n💡 For demo purposes, use speed_multiplier=60 for rapid-fire events!")