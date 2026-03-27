
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_drilldown():
    # 1. Test District -> Block
    district = "WEST JAINTIA HILLS"
    print(f"Testing Drilldown for District: {district}")
    try:
        url = f"{BASE_URL}/drilldown/district/{district}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get('features'):
            print("❌ No blocks found!")
            return
            
        print(f"✅ Found {len(data['features'])} blocks.")
        
        # Pick block
        block = "THADLASKEIN" # Known good block
        print(f"Testing Drilldown for Block: {block}")
        
        # 2. Test Block -> School
        url = f"{BASE_URL}/drilldown/block/{block}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get('features'):
            print("❌ No schools found!")
            return
            
        print(f"✅ Found {len(data['features'])} schools.")
        
        # Check for rich attributes
        school_props = data['features'][0]['properties']
        print("Sample School Properties:")
        # Note checking for 'eletricity' typo version
        keys_to_check = ['eletricity_connection_available', 'drinking_water_availability', 'library_facility']
        for k in keys_to_check:
            if k in school_props:
                print(f"  - {k}: {school_props[k]}")
            else:
                print(f"  ❌ Missing {k}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_drilldown()
