#!/usr/bin/env python3
"""
Test script to demonstrate the network flow visualization.
Runs a short simulation and generates the network diagram.
"""

import random
import numpy as np
from networkmodel import run_simulation, plot_network_flow, plot_cost_and_carbon_analysis, print_cost_summary

def test_network_visualization():
    """Run a short simulation and generate network flow diagram."""
    
    # Seed for reproducible results
    random.seed(42)
    np.random.seed(42)
    
    print("Running 30-day simulation to generate network flow data...")
    state, metrics = run_simulation(days=30)
    
    print(f"Simulation complete!")
    print(f"  Active packages: {sum(1 for pkg in state.packages.values() if not pkg.retired)}")
    print(f"  Total produced: {state.total_produced}")
    print(f"  Conservation violations: {len(state.conservation_violations)}")
    
    print("\nGenerating network flow diagram...")
    plot_network_flow(state, metrics, day_range=(0, 30))
    
    print("\nGenerating cost and carbon analysis...")
    plot_cost_and_carbon_analysis(state, metrics)
    
    print("\nCost Summary:")
    print_cost_summary(state, metrics)
    
    print("Network visualization complete!")

if __name__ == "__main__":
    test_network_visualization()
