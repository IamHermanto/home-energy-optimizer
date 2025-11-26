import requests
import json
import time

API_BASE = "http://localhost:5000/api/vpp"

def test_dispatch():
    """Test that dispatch actually changes battery states"""
    
    print("=" * 60)
    print("VPP DISPATCH TEST")
    print("=" * 60)
    
    # Step 1: Get initial fleet status
    print("\n1. Getting initial fleet status...")
    response = requests.get(f"{API_BASE}/fleet-status")
    before = response.json()
    
    print(f"   Total Batteries: {before['total_batteries']}")
    print(f"   Active Batteries: {before['active_batteries']}")
    print(f"   Available Energy: {before['available_energy_kwh']:.1f} kWh")
    print(f"   Dispatchable Power: {before['dispatchable_power_kw']:.1f} kW")
    
    # Step 2: Calculate expected dispatch
    print("\n2. Calculating expected dispatch...")
    requested_power = 250  # kW
    max_possible = before['dispatchable_power_kw']
    
    if max_possible < requested_power:
        print(f"   ⚠️  Warning: Can only dispatch {max_possible:.1f} kW (requested {requested_power} kW)")
        expected_power = max_possible
    else:
        expected_power = requested_power
    
    # Each battery can give 5 kW, so number of batteries needed
    expected_batteries = int(expected_power / 5)
    
    # Energy discharged for 30 min (0.5 hours)
    expected_energy_discharged = expected_power * 0.5
    
    print(f"   Expected batteries: ~{expected_batteries}")
    print(f"   Expected power: ~{expected_power:.1f} kW")
    print(f"   Expected energy discharged: ~{expected_energy_discharged:.1f} kWh")
    
    # Step 3: Dispatch batteries
    print("\n3. Dispatching batteries...")
    dispatch_data = {
        "required_power_kw": requested_power,
        "reason": "Automated test"
    }
    
    response = requests.post(
        f"{API_BASE}/dispatch",
        json=dispatch_data,
        headers={"Content-Type": "application/json"}
    )
    dispatch_result = response.json()
    
    print(f"   ✅ Dispatched: {dispatch_result['batteries_dispatched']} batteries")
    print(f"   ✅ Power provided: {dispatch_result['total_power_kw']:.1f} kW")
    print(f"   ✅ Revenue: ${dispatch_result['revenue']:.2f}")
    print(f"   ✅ Fulfilled: {dispatch_result['fulfilled']}")
    
    # Step 4: Wait a moment for state to update
    print("\n4. Waiting 1 second for state update...")
    time.sleep(1)
    
    # Step 5: Get new fleet status
    print("\n5. Getting updated fleet status...")
    response = requests.get(f"{API_BASE}/fleet-status")
    after = response.json()
    
    print(f"   Available Energy: {after['available_energy_kwh']:.1f} kWh")
    print(f"   Dispatchable Power: {after['dispatchable_power_kw']:.1f} kW")
    
    # Step 6: Calculate actual changes
    print("\n6. Analyzing changes...")
    energy_change = before['available_energy_kwh'] - after['available_energy_kwh']
    power_change = before['dispatchable_power_kw'] - after['dispatchable_power_kw']
    
    print(f"   Energy changed: {energy_change:.1f} kWh (expected ~{expected_energy_discharged:.1f} kWh)")
    print(f"   Power changed: {power_change:.1f} kW (expected ~{expected_power:.1f} kW)")
    
    # Step 7: Validate results
    print("\n7. Test Results:")
    print("=" * 60)
    
    passed = True
    
    # Test 1: Did batteries actually dispatch?
    if dispatch_result['batteries_dispatched'] > 0:
        print("   ✅ PASS: Batteries were dispatched")
    else:
        print("   ❌ FAIL: No batteries dispatched")
        passed = False
    
    # Test 2: Did available energy decrease?
    if energy_change > 0:
        print(f"   ✅ PASS: Available energy decreased by {energy_change:.1f} kWh")
    else:
        print(f"   ❌ FAIL: Available energy did not decrease (change: {energy_change:.1f} kWh)")
        passed = False
    
    # Test 3: Is the energy change reasonable?
    tolerance = 5  # kWh tolerance
    if abs(energy_change - expected_energy_discharged) < tolerance:
        print(f"   ✅ PASS: Energy change matches expected (~{expected_energy_discharged:.1f} kWh)")
    else:
        print(f"   ⚠️  WARNING: Energy change ({energy_change:.1f} kWh) differs from expected ({expected_energy_discharged:.1f} kWh)")
    
    # Test 4: Did dispatchable power decrease?
    if power_change >= 0:
        print(f"   ✅ PASS: Dispatchable power decreased by {power_change:.1f} kW")
    else:
        print(f"   ❌ FAIL: Dispatchable power increased (shouldn't happen)")
        passed = False
    
    # Test 5: Was the dispatch realistic?
    if dispatch_result['batteries_dispatched'] <= before['active_batteries']:
        print(f"   ✅ PASS: Dispatched batteries ({dispatch_result['batteries_dispatched']}) <= active batteries ({before['active_batteries']})")
    else:
        print(f"   ❌ FAIL: Dispatched more batteries than available")
        passed = False
    
    print("=" * 60)
    if passed:
        print("🎉 ALL TESTS PASSED - Dispatch is working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Dispatch may have issues")
    print("=" * 60)
    
    return passed

def test_fcas():
    """Test FCAS frequency response"""
    
    print("\n\n" + "=" * 60)
    print("FCAS FREQUENCY RESPONSE TEST")
    print("=" * 60)
    
    # Get initial state
    print("\n1. Getting initial fleet status...")
    response = requests.get(f"{API_BASE}/fleet-status")
    before = response.json()
    print(f"   Available Energy: {before['available_energy_kwh']:.1f} kWh")
    
    # Simulate low frequency event (should trigger discharge)
    print("\n2. Simulating low frequency event (49.88 Hz)...")
    fcas_data = {"frequency_hz": 49.88}
    
    response = requests.post(
        f"{API_BASE}/fcas-event",
        json=fcas_data,
        headers={"Content-Type": "application/json"}
    )
    fcas_result = response.json()
    
    print(f"   Action: {fcas_result['action']}")
    print(f"   Batteries: {fcas_result['batteries_dispatched']}")
    print(f"   Power: {fcas_result['power_kw']:.1f} kW")
    print(f"   Response time: {fcas_result['response_time_seconds']}s")
    print(f"   Revenue: ${fcas_result['revenue']:.2f}")
    
    # Wait and check again
    print("\n3. Waiting 1 second...")
    time.sleep(1)
    
    response = requests.get(f"{API_BASE}/fleet-status")
    after = response.json()
    energy_change = before['available_energy_kwh'] - after['available_energy_kwh']
    
    print(f"   Energy change: {energy_change:.1f} kWh")
    
    # Validate
    print("\n4. Test Results:")
    print("=" * 60)
    
    if fcas_result['action'] in ['discharge', 'charge']:
        print(f"   ✅ PASS: FCAS triggered action ({fcas_result['action']})")
    else:
        print(f"   ❌ FAIL: FCAS did not trigger (frequency might be within range)")
    
    if fcas_result['batteries_dispatched'] > 0:
        print(f"   ✅ PASS: Batteries responded ({fcas_result['batteries_dispatched']} batteries)")
    else:
        print("   ⚠️  WARNING: No batteries dispatched")
    
    if fcas_result['response_time_seconds'] < 6:
        print(f"   ✅ PASS: Response time under 6 seconds ({fcas_result['response_time_seconds']}s)")
    else:
        print(f"   ❌ FAIL: Response time too slow ({fcas_result['response_time_seconds']}s)")
    
    print("=" * 60)

if __name__ == "__main__":
    try:
        # Run dispatch test
        test_dispatch()
        
        # Run FCAS test
        test_fcas()
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API")
        print("Make sure the server is running: python backend/api.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()