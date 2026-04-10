import csv
import time
import os
import random
import datetime

# Configuration
OUTPUT_DIR = 'output'
SUPPLY_FILE = 'live_supply.csv'
DEMAND_FILE = 'live_demand.csv'
INTERVAL = 5 # seconds

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def generate_data():
    ensure_dir(OUTPUT_DIR)
    
    # Define sensors
    supply_sensors = ['pv', 'wt', 'biofuel', 'grid', 'battery']
    demand_sensors = ['hvac', 'lighting', 'pump', 'office']
    
    while True:
        timestamp = datetime.datetime.now().isoformat()
        
        # 1. Generate Supply Data
        supply_data = []
        for sensor in supply_sensors:
            # Simulate random values
            if sensor == 'pv': val = random.uniform(0, 100) # Day/Night logic omitted for simplicity
            elif sensor == 'wt': val = random.uniform(0, 150)
            elif sensor == 'biofuel': val = random.uniform(0, 50)
            elif sensor == 'grid': val = random.uniform(20, 80)
            elif sensor == 'battery': val = random.uniform(40, 160) # kWh (SOC 20%..80% dari kapasitas 200 kWh)
            else: val = 0
            
            supply_data.append({
                'timestamp': timestamp,
                'sensor_id': sensor,
                'value': round(val, 2)
            })
            
        with open(os.path.join(OUTPUT_DIR, SUPPLY_FILE), 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'sensor_id', 'value'])
            writer.writeheader()
            writer.writerows(supply_data)
            
        # 2. Generate Demand Data
        demand_data = []
        for sensor in demand_sensors:
            val = random.uniform(5, 30)
            demand_data.append({
                'timestamp': timestamp,
                'sensor_id': sensor,
                'value': round(val, 2)
            })
            
        with open(os.path.join(OUTPUT_DIR, DEMAND_FILE), 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'sensor_id', 'value'])
            writer.writeheader()
            writer.writerows(demand_data)
            
        print(f"[{timestamp}] Updated live data CSVs.")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    print("Starting Dummy Live Data Generator...")
    print(f"Writing to {os.path.join(OUTPUT_DIR, SUPPLY_FILE)} and {DEMAND_FILE}")
    try:
        generate_data()
    except KeyboardInterrupt:
        print("Stopped.")
