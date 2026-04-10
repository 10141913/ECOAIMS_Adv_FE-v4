import os
import csv
import time
import datetime
import logging
from typing import Dict, Any, List
from ecoaims_frontend.config import (
    LIVE_CSV_DIR, LIVE_SUPPLY_FILE, LIVE_DEMAND_FILE, 
    SENSOR_STALE_THRESHOLD, SENSOR_MAPPING
)

logger = logging.getLogger(__name__)

def get_live_sensor_data() -> Dict[str, Any]:
    """
    Reads live sensor data from CSV files and calculates health status.
    Returns a dictionary containing supply, demand, and health info.
    """
    
    # Paths (Assumed to be relative to the running app, or absolute)
    # We try to find the output directory
    base_dir = os.getcwd()
    output_dir = os.path.join(base_dir, LIVE_CSV_DIR)
    
    supply_path = os.path.join(output_dir, LIVE_SUPPLY_FILE)
    demand_path = os.path.join(output_dir, LIVE_DEMAND_FILE)
    
    current_time = time.time()
    
    # Initialize result structure
    result = {
        'supply': {},
        'demand': {},
        'health': {
            'active_sensors': 0,
            'stale_sensors': 0,
            'missing_sensors': 0,
            'last_update': 'N/A',
            'status': 'normal'
        }
    }
    last_ts_epoch = None
    
    # Helper to process file
    def process_file(file_path: str, category: str):
        if not os.path.exists(file_path):
            logger.warning(f"Live data file not found: {file_path}")
            # Mark all expected sensors in this category as missing
            for sensor_id in SENSOR_MAPPING[category]:
                result['health']['missing_sensors'] += 1
            return

        try:
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                # Check for required columns
                if not reader.fieldnames or not {'timestamp', 'sensor_id', 'value'}.issubset(set(reader.fieldnames)):
                    logger.error(f"Invalid CSV format in {file_path}")
                    return

                # Read all rows (assuming one row per sensor, or taking latest if multiple)
                # We'll use a dict to keep only the latest value for each sensor_id
                latest_readings = {}
                
                for row in reader:
                    sensor_id = row['sensor_id']
                    if sensor_id in SENSOR_MAPPING[category]:
                        latest_readings[sensor_id] = row
                
                # Process latest readings
                for sensor_id, name in SENSOR_MAPPING[category].items():
                    if sensor_id in latest_readings:
                        row = latest_readings[sensor_id]
                        try:
                            # Parse value
                            val = float(row['value'])
                            result[category][name] = val
                            
                            # Parse timestamp & check stale
                            # Assuming timestamp is ISO format or epoch. 
                            # Let's try flexible parsing or assume ISO
                            ts_str = row['timestamp']
                            try:
                                s = str(ts_str).strip()
                                if s.endswith("Z"):
                                    s = s.replace("Z", "+00:00")
                                ts = datetime.datetime.fromisoformat(s).timestamp()
                            except ValueError:
                                # Try float (epoch)
                                ts = float(ts_str)
                                
                            age = current_time - ts
                            
                            if age > SENSOR_STALE_THRESHOLD:
                                result['health']['stale_sensors'] += 1
                                result[category][name] = None
                            else:
                                result['health']['active_sensors'] += 1
                                
                            nonlocal last_ts_epoch
                            if isinstance(ts, (int, float)):
                                if last_ts_epoch is None or float(ts) > float(last_ts_epoch):
                                    last_ts_epoch = float(ts)

                        except (ValueError, TypeError):
                            logger.warning(f"Corrupt data for sensor {sensor_id}")
                            result['health']['missing_sensors'] += 1
                    else:
                        result['health']['missing_sensors'] += 1
                        # IMPORTANT: Don't set default 0.0 here. Leave it missing (None) 
                        # so the hybrid logic knows to use simulation.
                        # result[category][name] = 0.0 

        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            
    process_file(supply_path, 'supply')
    process_file(demand_path, 'demand')
    
    if isinstance(last_ts_epoch, (int, float)) and float(last_ts_epoch) > 0:
        try:
            dt = datetime.datetime.fromtimestamp(float(last_ts_epoch), tz=datetime.timezone.utc).astimezone()
            result['health']['last_update'] = dt.strftime("%H:%M:%S")
        except Exception:
            result['health']['last_update'] = 'N/A'
    
    # Determine overall status
    if result['health']['missing_sensors'] > 0:
        result['health']['status'] = 'warning'
    if result['health']['active_sensors'] == 0:
        result['health']['status'] = 'critical'
        
    return result
