"""
Autonomous VPP Simulator
Runs continuously in background, simulating real VPP operations
"""

import threading
import time
import random
from datetime import datetime
from typing import Callable

class AutonomousVPP:
    """
    Autonomous VPP that runs continuously:
    - Monitors simulated grid frequency
    - Auto-responds to frequency deviations (FCAS)
    - Executes time-based arbitrage (charge midnight, discharge 6pm)
    - Logs all events in real-time
    """
    
    def __init__(self, vpp_aggregator):
        self.vpp = vpp_aggregator
        self.running = False
        self.thread = None
        
        # Simulation state
        self.current_frequency = 50.0
        self.last_fcas_event = time.time()
        self.last_arbitrage_check = time.time()
        
        # Event callbacks
        self.event_callbacks = []
    
    def register_event_callback(self, callback: Callable):
        """Register callback to be notified of events"""
        self.event_callbacks.append(callback)
    
    def _notify_event(self, event_type: str, details: dict):
        """Notify all registered callbacks of new event"""
        event = {
            'timestamp': datetime.now().isoformat(),
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
        
        # Occasional major events (5% chance)
        if random.random() < 0.05:
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
            # Cooldown: Don't trigger FCAS more than once per 30 seconds
            if time.time() - self.last_fcas_event < 30:
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
        now = datetime.now()
        hour = now.hour
        
        # Only check every 5 minutes
        if time.time() - self.last_arbitrage_check < 300:
            return None
        
        self.last_arbitrage_check = time.time()
        
        fleet_status = self.vpp.get_fleet_status()
        
        # Off-peak charging (midnight to 7am)
        if 0 <= hour < 7:
            # Only charge if batteries are below 80%
            utilization = fleet_status['fleet_utilization_pct']
            if utilization < 80:
                # Charge batteries (simulate buying cheap power)
                available_capacity = fleet_status['total_capacity_kwh'] - fleet_status['available_energy_kwh']
                
                if available_capacity > 50:  # Only if we have room
                    # Simulate charging by "reverse dispatch"
                    self._notify_event('arbitrage_charge', {
                        'hour': hour,
                        'reason': 'Off-peak charging (cheap power)',
                        'rate': 0.15,  # $/kWh off-peak
                        'capacity_available_kwh': available_capacity
                    })
                    
                    return {'action': 'charge', 'hour': hour}
        
        # Peak discharge (6pm to 9pm)
        elif 18 <= hour < 21:
            # Only discharge if we have power available
            if fleet_status['dispatchable_power_kw'] > 100:
                # Dispatch for arbitrage
                result = self.vpp.dispatch_batteries(
                    fleet_status['dispatchable_power_kw'],
                    f"Arbitrage: Peak discharge (${0.35:.2f}/kWh)"
                )
                
                self._notify_event('arbitrage_discharge', {
                    'hour': hour,
                    'reason': 'Peak discharge (high prices)',
                    'rate': 0.35,  # $/kWh peak
                    'batteries_dispatched': result['batteries_dispatched'],
                    'power_kw': result['total_power_kw'],
                    'revenue': result['revenue']
                })
                
                return result
        
        return None
    
    def _simulation_loop(self):
        """Main simulation loop - runs continuously"""
        print("🔋 Autonomous VPP Started")
        print("=" * 60)
        
        while self.running:
            try:
                # Simulate grid frequency
                frequency = self._simulate_frequency()
                
                # Check if FCAS response needed
                self._check_fcas_response(frequency)
                
                # Check for arbitrage opportunities
                self._check_arbitrage_opportunity()
                
                # Update fleet every hour (simulate solar/consumption changes)
                if random.random() < 0.02:  # ~2% chance per cycle
                    self.vpp.fleet.simulate_hour()
                
                # Sleep for simulation interval (5 seconds = fast simulation)
                time.sleep(5)
                
            except Exception as e:
                print(f"Simulation error: {e}")
                time.sleep(5)
        
        print("🛑 Autonomous VPP Stopped")
    
    def start(self):
        """Start autonomous simulation in background thread"""
        if self.running:
            print("Autonomous VPP already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()
        
        return {
            'status': 'started',
            'message': 'Autonomous VPP simulation started'
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
            'simulation_mode': 'autonomous'
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
    # Test autonomous simulator
    from vpp_aggregator import VPPAggregator
    
    print("Testing Autonomous VPP Simulator")
    print("=" * 60)
    
    vpp = VPPAggregator()
    auto_vpp = AutonomousVPP(vpp)
    
    # Register event callback
    def print_event(event):
        print(f"[{event['timestamp']}] {event['type']}: {event['details']}")
    
    auto_vpp.register_event_callback(print_event)
    
    # Start simulation
    auto_vpp.start()
    
    print("\n✅ Simulation running for 30 seconds...\n")
    
    # Let it run for 30 seconds
    time.sleep(30)
    
    # Stop
    auto_vpp.stop()
    
    print("\n✅ Simulation stopped")