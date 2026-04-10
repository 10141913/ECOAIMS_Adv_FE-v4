import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecoaims_frontend.services.optimization_service import run_energy_optimization

def print_result(scenario_name, usage, recommendation):
    print(f"\n--- {scenario_name} ---")
    print("Distribusi Energi:")
    for source, amount in usage.items():
        print(f"  - {source}: {amount:.2f} kW")
    print(f"Rekomendasi: {recommendation}")

def main():
    print("=== Demo Simulasi Optimasi Energi ECO-AIMS ===")
    
    # Scenario 1: Renewable Priority
    usage, rec = run_energy_optimization(
        priority='renewable',
        battery_capacity_usage=50.0,
        grid_limit=100.0,
        solar_available=60.0,
        wind_available=40.0,
        total_demand=120.0
    )
    print_result("Skenario 1: Prioritas Renewable", usage, rec)

    # Scenario 2: Battery Priority (Peak Shaving)
    usage, rec = run_energy_optimization(
        priority='battery',
        battery_capacity_usage=80.0, # Aggressive battery use
        grid_limit=100.0,
        solar_available=20.0, # Low renewable
        wind_available=10.0,
        total_demand=150.0
    )
    print_result("Skenario 2: Prioritas Baterai (Malam Hari / Peak Load)", usage, rec)

    # Scenario 3: Grid Priority
    usage, rec = run_energy_optimization(
        priority='grid',
        battery_capacity_usage=20.0,
        grid_limit=200.0,
        solar_available=50.0,
        wind_available=30.0,
        total_demand=100.0
    )
    print_result("Skenario 3: Prioritas Grid (Stabil)", usage, rec)

if __name__ == "__main__":
    main()
