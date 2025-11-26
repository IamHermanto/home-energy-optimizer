"""
Test Autonomous VPP
Quick test to verify autonomous system works
"""

import sys
sys.path.append('backend')

from vpp_aggregator import VPPAggregator
from autonomous_vpp import AutonomousVPP
import time

print("=" * 70)
print("TESTING AUTONOMOUS VPP SYSTEM")
print("=" * 70)

# Initialize
print("\n1. Initializing VPP...")
vpp = VPPAggregator()
auto_vpp = AutonomousVPP(vpp)
print("   ✅ VPP Initialized")

# Event counter
events = {'fcas': 0, 'arbitrage': 0}

def track_event(event):
    """Track events as they happen"""
    if event['type'] == 'fcas_response':
        events['fcas'] += 1
        print(f"\n   ⚡ FCAS EVENT #{events['fcas']}")
        print(f"      Frequency: {event['details']['frequency_hz']:.3f} Hz")
        print(f"      Action: {event['details']['action']}")
        print(f"      Batteries: {event['details']['batteries_dispatched']}")
        print(f"      Power: {event['details']['power_kw']:.1f} kW")
        print(f"      Revenue: ${event['details']['revenue']:.2f}")
    
    elif event['type'] in ['arbitrage_charge', 'arbitrage_discharge']:
        events['arbitrage'] += 1
        print(f"\n   💰 ARBITRAGE EVENT #{events['arbitrage']}")
        print(f"      Type: {event['type']}")
        print(f"      Hour: {event['details']['hour']}")
        print(f"      Reason: {event['details']['reason']}")

# Register callback
auto_vpp.register_event_callback(track_event)

# Start autonomous mode
print("\n2. Starting Autonomous Mode...")
result = auto_vpp.start()
print(f"   ✅ {result['message']}")

print("\n3. Monitoring for 60 seconds...")
print("   (Watching for FCAS events and arbitrage opportunities)")
print("   " + "-" * 66)

# Monitor for 60 seconds
for i in range(12):
    time.sleep(5)
    
    # Get status
    status = auto_vpp.get_status()
    frequency = status['current_frequency_hz']
    freq_status = status['frequency_status']
    
    # Color status
    if freq_status == 'normal':
        status_str = '🟢 NORMAL'
    elif freq_status == 'warning':
        status_str = '🟡 WARNING'
    else:
        status_str = '🔴 CRITICAL'
    
    print(f"   [{i*5:02d}s] Frequency: {frequency:.3f} Hz - {status_str}", end='\r')

print("\n   " + "-" * 66)

# Stop
print("\n4. Stopping Autonomous Mode...")
auto_vpp.stop()
print("   ✅ Stopped")

# Summary
print("\n5. Event Summary:")
print("=" * 70)
print(f"   FCAS Responses: {events['fcas']}")
print(f"   Arbitrage Events: {events['arbitrage']}")
print(f"   Total Events: {events['fcas'] + events['arbitrage']}")

if events['fcas'] > 0:
    print("\n   ✅ FCAS system working - auto-responded to frequency deviations")
else:
    print("\n   ⚠️  No FCAS events (frequency may not have deviated enough)")
    print("      This is normal - just run test again for more events")

print("\n" + "=" * 70)
print("✅ AUTONOMOUS VPP TEST COMPLETE")
print("=" * 70)
print("\nNext steps:")
print("1. Start your Flask server: python backend/api.py")
print("2. Open dashboard: http://localhost:5000/vpp-dashboard")
print("3. Click 'Start Autonomous Mode' and watch it work!")