import random
import datetime

class BMSService:
    def __init__(self):
        # Initial state
        self.soc = 50.0  # %
        self.voltage = 48.0  # V (nominal 48V system)
        self.current = 0.0  # A (+ charging, - discharging)
        self.temperature = 25.0  # Celsius
        self.status = "Idle"  # Idle, Charging, Discharging
        self.health = "Normal"
        
        # Configuration
        self.max_voltage = 54.6
        self.min_voltage = 42.0
        self.capacity_ah = 100.0 # Ampere-hours
        
        # Simulation parameters
        self.charging_current = 20.0 # A
        self.discharging_current = -15.0 # A
        self.ambient_temp = 25.0
        
        # Limits
        self.temp_warning = 45.0
        self.soc_max_limit = 80.0
        self.soc_min_limit = 20.0
        
        # History
        self.history = {
            'timestamp': [],
            'soc': [],
            'voltage': [],
            'current': [],
            'temperature': []
        }

    def update(self, action=None):
        """
        Updates the BMS state based on action and time step.
        action: 'charge', 'discharge', 'stop', or None (continue current)
        """
        # Update Status based on action
        if action == 'charge':
            self.status = "Charging"
            self.current = self.charging_current
        elif action == 'discharge':
            self.status = "Discharging"
            self.current = self.discharging_current
        elif action == 'stop':
            self.status = "Idle"
            self.current = 0.0
            
        # Physics Simulation (Simplified)
        dt = 2.0 / 3600.0 # 2 seconds in hours (update interval)
        
        # Update SOC
        delta_soc = (self.current * dt / self.capacity_ah) * 100
        self.soc += delta_soc
        self.soc = max(0.0, min(100.0, self.soc))
        
        # Update Voltage (Simple linear model based on SOC + IR drop)
        open_circuit_voltage = self.min_voltage + (self.max_voltage - self.min_voltage) * (self.soc / 100.0)
        internal_resistance = 0.05 # Ohm
        self.voltage = open_circuit_voltage + (self.current * internal_resistance)
        
        # Update Temperature
        # Heat generation = I^2 * R
        heat_gen = (self.current ** 2) * internal_resistance * 0.5 # factor
        cooling = (self.temperature - self.ambient_temp) * 0.1
        self.temperature += (heat_gen - cooling) * 0.1 # thermal mass factor
        
        # Safety Checks (Auto-Stop)
        msg = ""
        if self.status == "Charging" and self.soc >= self.soc_max_limit:
            self.status = "Idle"
            self.current = 0.0
            msg = "Pengisian berhenti otomatis (Batas Atas SOC tercapai)."
            
        if self.status == "Discharging" and self.soc <= self.soc_min_limit:
            self.status = "Idle"
            self.current = 0.0
            msg = "Pengosongan berhenti otomatis (Batas Bawah SOC tercapai)."
            
        if self.temperature > self.temp_warning:
            self.status = "Idle"
            self.current = 0.0
            self.health = "Overheated"
            msg = "Sistem berhenti darurat: Suhu terlalu tinggi!"
        elif self.temperature > 40:
             self.health = "Warning"
        else:
             self.health = "Normal"
             
        # Record History
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._add_history(now)
        
        return {
            'soc': self.soc,
            'voltage': self.voltage,
            'current': self.current,
            'temperature': self.temperature,
            'status': self.status,
            'health': self.health,
            'message': msg
        }
        
    def _add_history(self, timestamp):
        max_len = 50
        self.history['timestamp'].append(timestamp)
        self.history['soc'].append(self.soc)
        self.history['voltage'].append(self.voltage)
        self.history['current'].append(self.current)
        self.history['temperature'].append(self.temperature)
        
        # Trim
        if len(self.history['timestamp']) > max_len:
            for key in self.history:
                self.history[key].pop(0)

    def get_history(self):
        return self.history

# Global BMS Instance
bms_service = BMSService()
