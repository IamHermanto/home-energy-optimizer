import requests
from datetime import datetime
from typing import Dict, Optional

class AEMOClient:
    """
    Client for Australian Energy Market Operator (AEMO) public APIs
    Provides real-time grid data: prices, demand, frequency
    """
    
    BASE_URL = "https://visualisations.aemo.com.au/aemo/apps/api/report"
    
    def __init__(self, default_region='NSW1'):
        """
        Initialize AEMO client
        
        Regions: NSW1, QLD1, SA1, TAS1, VIC1
        """
        self.default_region = default_region
    
    def get_current_price(self, region: Optional[str] = None) -> Dict:
        """
        Get current electricity spot price
        
        Returns:
            {
                'price_per_mwh': float,  # $/MWh
                'price_per_kwh': float,  # $/kWh
                'timestamp': str,
                'region': str
            }
        """
        region = region or self.default_region
        
        try:
            url = f"{self.BASE_URL}/5MIN"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Find latest price for region
            for record in data['5MIN']['PRICE']:
                if record['REGIONID'] == region:
                    price_mwh = float(record['RRP'])
                    return {
                        'price_per_mwh': round(price_mwh, 2),
                        'price_per_kwh': round(price_mwh / 1000, 4),
                        'timestamp': record['SETTLEMENTDATE'],
                        'region': region,
                        'status': 'live'
                    }
            
            # Fallback if region not found
            return self._fallback_price(region)
            
        except Exception as e:
            print(f"AEMO API error: {e}")
            return self._fallback_price(region)
    
    def get_demand(self, region: Optional[str] = None) -> Dict:
        """
        Get current grid demand
        
        Returns:
            {
                'total_demand_mw': float,
                'timestamp': str,
                'region': str
            }
        """
        region = region or self.default_region
        
        try:
            url = f"{self.BASE_URL}/5MIN"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Find demand for region
            for record in data['5MIN']['DEMAND']:
                if record['REGIONID'] == region:
                    return {
                        'total_demand_mw': round(float(record['TOTALDEMAND']), 1),
                        'timestamp': record['SETTLEMENTDATE'],
                        'region': region
                    }
            
            return {'total_demand_mw': 0, 'timestamp': datetime.now().isoformat(), 'region': region}
            
        except Exception as e:
            print(f"AEMO demand API error: {e}")
            return {'total_demand_mw': 0, 'timestamp': datetime.now().isoformat(), 'region': region}
    
    def get_all_regions_prices(self) -> Dict[str, float]:
        """
        Get current prices for all regions
        
        Returns:
            {'NSW1': 287.50, 'VIC1': 195.30, ...}
        """
        try:
            url = f"{self.BASE_URL}/5MIN"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            prices = {}
            for record in data['5MIN']['PRICE']:
                region = record['REGIONID']
                price = round(float(record['RRP']) / 1000, 4)  # Convert to $/kWh
                prices[region] = price
            
            return prices
            
        except Exception as e:
            print(f"AEMO regions API error: {e}")
            return {}
    
    def should_dispatch(self, price_per_kwh: float, threshold: float = 0.30) -> Dict:
        """
        Decision logic: should VPP discharge batteries?
        
        Args:
            price_per_kwh: Current grid price
            threshold: Price above which to discharge (default $0.30/kWh)
        
        Returns:
            {
                'action': 'discharge' | 'charge' | 'hold',
                'reason': str,
                'price': float
            }
        """
        if price_per_kwh >= threshold:
            return {
                'action': 'discharge',
                'reason': f'High price (${price_per_kwh:.3f}/kWh >= ${threshold}/kWh)',
                'price': price_per_kwh
            }
        elif price_per_kwh <= 0.15:
            return {
                'action': 'charge',
                'reason': f'Low price (${price_per_kwh:.3f}/kWh - cheap energy)',
                'price': price_per_kwh
            }
        else:
            return {
                'action': 'hold',
                'reason': f'Normal price (${price_per_kwh:.3f}/kWh)',
                'price': price_per_kwh
            }
    
    def _fallback_price(self, region: str) -> Dict:
        """Fallback pricing when API unavailable"""
        hour = datetime.now().hour
        
        # Simulate time-of-use pricing
        if 16 <= hour < 21:  # Peak
            price_kwh = 0.35
        elif 22 <= hour or hour < 7:  # Off-peak
            price_kwh = 0.15
        else:  # Shoulder
            price_kwh = 0.25
        
        return {
            'price_per_mwh': price_kwh * 1000,
            'price_per_kwh': price_kwh,
            'timestamp': datetime.now().isoformat(),
            'region': region,
            'status': 'simulated'
        }


if __name__ == "__main__":
    # Test AEMO client
    client = AEMOClient(default_region='NSW1')
    
    print("=" * 60)
    print("AEMO GRID DATA TEST")
    print("=" * 60)
    
    # Get current price
    print("\n1. Current Electricity Price (NSW):")
    price = client.get_current_price()
    print(f"   Price: ${price['price_per_kwh']:.4f}/kWh (${price['price_per_mwh']:.2f}/MWh)")
    print(f"   Status: {price['status']}")
    print(f"   Time: {price['timestamp']}")
    
    # Get demand
    print("\n2. Current Grid Demand (NSW):")
    demand = client.get_demand()
    print(f"   Demand: {demand['total_demand_mw']} MW")
    
    # Get all regions
    print("\n3. All Regions Prices:")
    all_prices = client.get_all_regions_prices()
    for region, price in all_prices.items():
        print(f"   {region}: ${price:.4f}/kWh")
    
    # Dispatch decision
    print("\n4. VPP Dispatch Decision:")
    decision = client.should_dispatch(price['price_per_kwh'])
    print(f"   Action: {decision['action'].upper()}")
    print(f"   Reason: {decision['reason']}")
    
    print("=" * 60)