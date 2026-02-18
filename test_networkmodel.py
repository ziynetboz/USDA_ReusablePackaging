import random
import numpy as np

from networkmodel import run_simulation, NetworkState, SIMULATION_DAYS


def test_short_run_conservation_and_invariants():
    random.seed(42)
    np.random.seed(42)

    days = 60
    state, metrics = run_simulation(days=days)

    # No per-node conservation violations should be recorded
    assert len(state.conservation_violations) == 0, f"Conservation violations: {state.conservation_violations[:3]}"

    # Inventories are non-negative
    assert np.all(state.inventory >= -1e-9)

    # Metrics present and sized correctly
    assert len(metrics['time']) == days
    assert len(metrics['active_packages']) == days
    assert len(metrics['unmet_demand']) == days

    # Basic sanity: total produced non-decreasing
    assert all(x <= y for x, y in zip(metrics['total_produced'][:-1], metrics['total_produced'][1:]))


if __name__ == "__main__":
    test_short_run_conservation_and_invariants()
    print("Tests passed.") 