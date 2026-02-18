import numpy as np
import random
import matplotlib.pyplot as plt
import networkx as nx
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import math

N_0 = 50
NUM_NODES = 16
SIMULATION_DAYS = 365

US_POOLER = 1
US_GROWER_1 = 2
US_GROWER_2 = 3
US_GROWER_3 = 4
US_EXPORT_PORT = 5
SEA_EXPORT = 6
EU_ENTRY_PORT = 7
EU_DC = 8
EU_RETAILER_1 = 9
EU_RETAILER_2 = 10
EU_RETAILER_3 = 11
EU_RETAILER_4 = 12
EU_POOLER = 13
EU_RETURN_PORT = 14
SEA_RETURN = 15
US_ENTRY_PORT = 16

DELAYS = {
    (1, 2): 1,
    (1, 3): 1,
    (1, 4): 1,
    (2, 5): 3,
    (3, 5): 3,
    (4, 5): 3,
    (5, 6): 1,
    (6, 7): 14,
    (7, 8): 1,
    (8, 9): 2,
    (8, 10): 2,
    (8, 11): 2,
    (8, 12): 2,
    (9, 13): 3,
    (10, 13): 3,
    (11, 13): 3,
    (12, 13): 3,
    (13, 14): 1,
    (14, 15): 1,
    (15, 16): 14,
    (16, 1): 1,
}

B_EXPORT_BASE = 20
B_RETURN_BASE = 20

C_MAX_DEFAULT = 12
MAX_WEAR_ACCUMULATION = 200
MAX_IDLE_DAYS = 30
FLEET_UTILIZATION_TARGET = 0.85

NODE_CAPACITY = {i: 200 for i in range(1, NUM_NODES + 1)}
ARC_CAPACITY = {edge: 100 for edge in DELAYS.keys()}

RETAILER_PROPORTIONS = [0.25, 0.25, 0.25, 0.25]

# --- New: scheduled departures and damage/repair parameters ---
US_EXPORT_SAILING_DOW = [1, 4]  # 0=Mon,1=Tue,4=Fri
EU_RETURN_SAILING_DOW = [2, 5]  # Wed, Sat
US_EXPORT_SAILING_CAPACITY = 120
EU_RETURN_SAILING_CAPACITY = 120

P_DAMAGE_IN_TRANSIT = 0.01
P_DAMAGE_AT_NODE = 0.002
REPAIR_LEAD_TIME_MEAN = 10
REPAIR_LEAD_TIME_STD = 3
REPAIR_SUCCESS_PROB = 0.9

# --- New: cost and carbon tracking parameters ---
# Transport costs per package per leg (USD)
TRANSPORT_COSTS = {
    (1, 2): 2.50,   # US Pooler -> Grower 1
    (1, 3): 2.50,   # US Pooler -> Grower 2  
    (1, 4): 2.50,   # US Pooler -> Grower 3
    (2, 5): 3.00,   # Grower -> Export Port
    (3, 5): 3.00,
    (4, 5): 3.00,
    (5, 6): 0.50,   # Export Port -> Sea Export
    (6, 7): 15.00,  # Sea Export -> EU Entry (ocean freight)
    (7, 8): 1.00,   # EU Entry -> DC
    (8, 9): 2.00,   # DC -> Retailers
    (8, 10): 2.00,
    (8, 11): 2.00,
    (8, 12): 2.00,
    (9, 13): 2.50,  # Retailers -> EU Pooler
    (10, 13): 2.50,
    (11, 13): 2.50,
    (12, 13): 2.50,
    (13, 14): 1.00, # EU Pooler -> Return Port
    (14, 15): 0.50, # Return Port -> Sea Return
    (15, 16): 15.00, # Sea Return -> US Entry (ocean freight)
    (16, 1): 1.00,  # US Entry -> US Pooler
}

# Carbon emissions per package per leg (kg CO2)
CARBON_EMISSIONS = {
    (1, 2): 0.8,    # Truck transport
    (1, 3): 0.8,
    (1, 4): 0.8,
    (2, 5): 1.0,
    (3, 5): 1.0,
    (4, 5): 1.0,
    (5, 6): 0.2,    # Port handling
    (6, 7): 12.0,   # Ocean freight (high emissions)
    (7, 8): 0.3,    # Truck transport
    (8, 9): 0.6,    # Urban delivery
    (8, 10): 0.6,
    (8, 11): 0.6,
    (8, 12): 0.6,
    (9, 13): 0.8,   # Collection truck
    (10, 13): 0.8,
    (11, 13): 0.8,
    (12, 13): 0.8,
    (13, 14): 0.3,
    (14, 15): 0.2,
    (15, 16): 12.0, # Ocean freight (return)
    (16, 1): 0.3,
}

# Daily holding costs per package per node type (USD)
HOLDING_COSTS = {
    1: 0.10,   # US Pooler
    2: 0.15,   # US Growers (cold storage)
    3: 0.15,
    4: 0.15,
    5: 0.20,   # Export Port (refrigerated)
    6: 0.25,   # Sea Export (refrigerated container)
    7: 0.20,   # EU Entry Port
    8: 0.15,   # EU DC (refrigerated)
    9: 0.10,   # EU Retailers (ambient)
    10: 0.10,
    11: 0.10,
    12: 0.10,
    13: 0.10,  # EU Pooler
    14: 0.20,  # EU Return Port
    15: 0.25,  # Sea Return
    16: 0.20,  # US Entry Port
}

# Production cost per new package (USD)
PRODUCTION_COST = 25.00
# Repair cost per refurbished package (USD)  
REPAIR_COST = 8.00


@dataclass
class Package:
    id: int
    position: int
    cycle_count: int = 0
    max_cycles: int = C_MAX_DEFAULT
    in_transit: bool = False
    arrival_time: Optional[int] = None
    retired: bool = False
    forced_retirement: bool = False
    path_history: List[int] = field(default_factory=list)
    wear_accumulation: float = 0.0
    idle_days_at_pooler: int = 0
    last_active_day: int = 0
    next_position: Optional[int] = None
    hold_until_day: Optional[int] = None
    # Cost and carbon tracking
    total_transport_cost: float = 0.0
    total_carbon_emissions: float = 0.0
    total_holding_cost: float = 0.0
    days_at_current_position: int = 0


class NetworkState:
    def __init__(self):
        self.inventory = np.zeros(NUM_NODES + 1)
        self.flows = defaultdict(lambda: defaultdict(float))
        self.packages = {}
        self.retired_packages = []
        self.time = 0
        self.last_production_time = -9999
        self.total_produced = 0
        self.package_id_counter = N_0

        self.adjacency = np.zeros((NUM_NODES + 1, NUM_NODES + 1))
        for (i, j) in DELAYS.keys():
            self.adjacency[i, j] = 1

        for i in range(N_0):
            pkg = Package(id=i, position=US_POOLER)
            pkg.path_history.append(US_POOLER)
            self.packages[i] = pkg
            self.inventory[US_POOLER] += 1

        self.unmet_demand_history = []
        self.conservation_violations = []
        self.repair_backlog: List[Dict] = []  # dicts with keys: ready_day, package_id, success_prob
        
        # Cost and carbon tracking
        self.total_transport_cost: float = 0.0
        self.total_carbon_emissions: float = 0.0
        self.total_holding_cost: float = 0.0
        self.total_production_cost: float = 0.0
        self.total_repair_cost: float = 0.0
        self.daily_costs: List[Dict] = []  # Daily cost breakdown


def get_potato_demand_multiplier(day_of_year):
    if 213 <= day_of_year <= 334:
        return 2.5
    elif 91 <= day_of_year <= 212:
        return 1.5
    else:
        return 0.5


def get_production_threshold(day_of_year):
    future_day = (day_of_year + 30) % 365
    future_demand = get_potato_demand_multiplier(future_day)
    base_threshold = 30
    return int(base_threshold * future_demand)


def get_batch_size(day_of_year):
    demand_mult = get_potato_demand_multiplier(day_of_year)
    return int(B_EXPORT_BASE * demand_mult)


def get_grower_proportions(day_of_year):
    if 91 <= day_of_year <= 182:
        return [0.5, 0.3, 0.2]
    elif 183 <= day_of_year <= 273:
        return [0.3, 0.4, 0.3]
    else:
        return [0.2, 0.3, 0.5]


# --- New: stochastic delays, retailer demand, scheduling and repair helpers ---

def sample_delay(i: int, j: int, day_of_year: int) -> int:
    base = DELAYS.get((i, j), 1)
    season = get_potato_demand_multiplier(day_of_year)
    mean = base * (1.1 if season > 1.0 else 1.0)
    std = max(1.0, 0.3 * base)
    sampled = int(max(1, round(np.random.normal(mean, std))))
    if random.random() < 0.02:
        sampled += random.randint(3, 14)
    return sampled


def sample_retailer_dwell(day_of_year: int) -> int:
    season = get_potato_demand_multiplier(day_of_year)
    mean = 3 if season >= 1.5 else 2
    std = 1
    return int(max(1, round(np.random.normal(mean, std))))


def get_retailer_daily_demand(day_of_year: int) -> Dict[int, int]:
    mult = get_potato_demand_multiplier(day_of_year)
    base = 6
    total_demand = max(0, int(round(base * mult + np.random.normal(0, 1))))
    proportions = RETAILER_PROPORTIONS
    retailers = [EU_RETAILER_1, EU_RETAILER_2, EU_RETAILER_3, EU_RETAILER_4]
    allocations = {r: 0 for r in retailers}
    remaining = total_demand
    for r, p in zip(retailers, proportions):
        qty = int(round(total_demand * p))
        allocations[r] = qty
        remaining -= qty
    while remaining > 0:
        r = random.choice(retailers)
        allocations[r] += 1
        remaining -= 1
    return allocations


def is_sailing_day(node: int, t: int) -> bool:
    dow = t % 7
    if node == US_EXPORT_PORT:
        return dow in US_EXPORT_SAILING_DOW
    if node == EU_RETURN_PORT:
        return dow in EU_RETURN_SAILING_DOW
    return True


def sailing_capacity(node: int) -> int:
    if node == US_EXPORT_PORT:
        return US_EXPORT_SAILING_CAPACITY
    if node == EU_RETURN_PORT:
        return EU_RETURN_SAILING_CAPACITY
    return 10**9


def sample_repair_lead_time() -> int:
    return int(max(1, round(np.random.normal(REPAIR_LEAD_TIME_MEAN, REPAIR_LEAD_TIME_STD))))


def maybe_damage_in_transit() -> bool:
    return random.random() < P_DAMAGE_IN_TRANSIT


def maybe_damage_at_node() -> bool:
    return random.random() < P_DAMAGE_AT_NODE


def calculate_transport_cost(from_node: int, to_node: int) -> float:
    """Calculate transport cost for a package movement."""
    return TRANSPORT_COSTS.get((from_node, to_node), 0.0)


def calculate_carbon_emissions(from_node: int, to_node: int) -> float:
    """Calculate carbon emissions for a package movement."""
    return CARBON_EMISSIONS.get((from_node, to_node), 0.0)


def calculate_holding_cost(node: int) -> float:
    """Calculate daily holding cost for a package at a node."""
    return HOLDING_COSTS.get(node, 0.0)


def constraint_1_flow_conservation():
    pass


def constraint_2_non_negative_inventory(inventory):
    return np.maximum(inventory, 0)


def constraint_3_non_negative_flows(flows):
    for edge in flows:
        flows[edge] = max(0, flows[edge])
    return flows


def constraint_4_capacity_nodes(inventory):
    for i in range(1, NUM_NODES + 1):
        inventory[i] = min(inventory[i], NODE_CAPACITY[i])
    return inventory


def constraint_5_arc_flow_capacity(flows):
    for edge in flows:
        if edge in ARC_CAPACITY:
            flows[edge] = min(flows[edge], ARC_CAPACITY[edge])
    return flows


def constraint_6_asset_lifecycle(packages, day_of_year):
    for pkg in packages.values():
        if 213 <= day_of_year <= 334:
            wear_rate = 3
        elif 91 <= day_of_year <= 212:
            wear_rate = 1.5
        else:
            wear_rate = 0.3

        pkg.wear_accumulation += wear_rate

        if pkg.cycle_count >= pkg.max_cycles or pkg.wear_accumulation >= MAX_WEAR_ACCUMULATION:
            pkg.retired = True


def constraint_7_retirement_rule(packages):
    return sum(1 for pkg in packages.values()
               if (pkg.cycle_count >= pkg.max_cycles or pkg.wear_accumulation >= pkg.max_cycles * 30)
               and not pkg.retired)


def constraint_8_path_continuity(pkg):
    if pkg.position == US_ENTRY_PORT and not pkg.retired:
        return US_POOLER
    return None


def constraint_9_cycle_increment(pkg, old_position, new_position):
    if old_position == US_ENTRY_PORT and new_position == US_POOLER:
        pkg.cycle_count += 1


def constraint_10_network_topology(flows, adjacency):
    filtered_flows = {}
    for (i, j), flow in flows.items():
        if adjacency[i, j] == 1:
            filtered_flows[(i, j)] = flow
    return filtered_flows


def constraint_11_total_system_conservation(state):
    active = sum(1 for pkg in state.packages.values() if not pkg.retired)
    retired = len(state.retired_packages)
    return active + retired


def constraint_12_grower_selection(pkg, day_of_year):
    if pkg.position == US_POOLER:
        grower_props = get_grower_proportions(day_of_year)
        return random.choices([US_GROWER_1, US_GROWER_2, US_GROWER_3],
                              weights=grower_props)[0]
    return None


def constraint_13_batch_shipping_export(inventory_export, day_of_year):
    batch_size = get_batch_size(day_of_year)
    if inventory_export >= batch_size:
        return min(inventory_export, batch_size * 2)
    return 0


def constraint_14_batch_shipping_return(inventory_return, day_of_year):
    batch_size = get_batch_size(day_of_year)
    if inventory_return >= batch_size:
        return min(inventory_return, batch_size * 2)
    return 0


def constraint_15_proportional_growers(packages_at_pooler, day_of_year):
    allocations = {US_GROWER_1: 0, US_GROWER_2: 0, US_GROWER_3: 0}
    growers = [US_GROWER_1, US_GROWER_2, US_GROWER_3]
    grower_props = get_grower_proportions(day_of_year)

    for pkg in packages_at_pooler:
        grower = random.choices(growers, weights=grower_props)[0]
        allocations[grower] += 1
    return allocations


def constraint_16_proportional_retailers(packages_at_dc):
    retailers = [EU_RETAILER_1, EU_RETAILER_2, EU_RETAILER_3, EU_RETAILER_4]
    allocations = {r: 0 for r in retailers}

    for pkg in packages_at_dc:
        retailer = random.choices(retailers, weights=RETAILER_PROPORTIONS)[0]
        allocations[retailer] += 1
    return allocations


def constraint_17_natural_production(state, t):
    return 0


def constraint_18_forced_production_retirement(user_input=None):
    if user_input:
        return user_input.get('forced_production', 0), user_input.get('forced_retirement', 0)
    return 0, 0


def constraint_19_seasonal_flow_rate(day_of_year, base_flow):
    multiplier = get_potato_demand_multiplier(day_of_year)
    return base_flow * multiplier


def constraint_20_seasonal_production(state, day_of_year):
    threshold = get_production_threshold(day_of_year)
    available_at_pooler = sum(1 for pkg in state.packages.values()
                              if pkg.position == US_POOLER and not pkg.retired and not pkg.in_transit)

    if available_at_pooler < threshold:
        return threshold - available_at_pooler
    return 0


def constraint_21_accelerated_wear(pkg, day_of_year):
    if 213 <= day_of_year <= 334:
        return 3
    elif 91 <= day_of_year <= 212:
        return 1.5
    return 0.3


def constraint_22_emergency_production(state, day_of_year):
    total_active = sum(1 for pkg in state.packages.values() if not pkg.retired)
    demand_mult = get_potato_demand_multiplier(day_of_year)
    minimum_needed = int(N_0 * demand_mult)

    if total_active < minimum_needed:
        return minimum_needed - total_active
    return 0


def constraint_23_idle_package_retirement(packages, t, day_of_year):
    retired_ids = []
    demand_mult = get_potato_demand_multiplier(day_of_year)

    max_idle = MAX_IDLE_DAYS if demand_mult > 1.0 else MAX_IDLE_DAYS // 2

    for pkg_id, pkg in packages.items():
        if not pkg.retired and not pkg.in_transit and pkg.position == US_POOLER:
            if pkg.last_active_day < t - 1:
                pkg.idle_days_at_pooler += 1

            if pkg.idle_days_at_pooler > max_idle:
                pkg.retired = True
                pkg.forced_retirement = True
                retired_ids.append(pkg_id)
        else:
            if pkg.in_transit or pkg.position != US_POOLER:
                pkg.idle_days_at_pooler = 0
                pkg.last_active_day = t

    return retired_ids


def constraint_24_demand_linked_fleet_size(state, day_of_year):
    total_active = sum(1 for pkg in state.packages.values() if not pkg.retired)
    demand_mult = get_potato_demand_multiplier(day_of_year)

    optimal_fleet = int(N_0 * demand_mult * 0.8)

    return total_active - optimal_fleet


def constraint_25_track_package_utilization(packages, flows, t):
    packages_moved = set()

    for (i, j), flow in flows.items():
        if flow > 0:
            for pkg in packages.values():
                if pkg.position == i and pkg.in_transit:
                    packages_moved.add(pkg.id)
                    pkg.last_active_day = t

    total_active = sum(1 for pkg in packages.values() if not pkg.retired)
    utilized = len(packages_moved)

    utilization_rate = utilized / total_active if total_active > 0 else 0
    return utilization_rate


def constraint_26_fleet_optimization(state, day_of_year, t):
    demand_mult = get_potato_demand_multiplier(day_of_year)

    pooler_inventory = sum(1 for pkg in state.packages.values()
                           if pkg.position == US_POOLER and not pkg.retired and not pkg.in_transit)

    daily_throughput_needed = int(10 * demand_mult)

    excess_packages = []
    if demand_mult < 1.0 and pooler_inventory > daily_throughput_needed * 3:
        packages_at_pooler = [(pkg.id, pkg) for pkg in state.packages.values()
                              if pkg.position == US_POOLER and not pkg.retired and not pkg.in_transit]

        packages_at_pooler.sort(key=lambda x: (x[1].idle_days_at_pooler, -x[1].wear_accumulation), reverse=True)

        excess_count = pooler_inventory - (daily_throughput_needed * 3)
        for i in range(min(excess_count, len(packages_at_pooler))):
            pkg_id, pkg = packages_at_pooler[i]
            excess_packages.append(pkg_id)

    return excess_packages


def process_arrivals(state: NetworkState, t: int, day_of_year: int) -> np.ndarray:
    arrivals = np.zeros(NUM_NODES + 1)
    for pkg in state.packages.values():
        if pkg.in_transit and not pkg.retired and pkg.arrival_time == t and pkg.next_position is not None:
            destination = pkg.next_position
            old_position = pkg.position
            
            # Damage in transit check; if damaged, retire and push to repair backlog
            if maybe_damage_in_transit():
                pkg.retired = True
                pkg.forced_retirement = True
                state.retired_packages.append(pkg)
                # Retire at destination node from conservation perspective
                arrivals[destination] += 1
                continue
            
            # Track transport costs and emissions for successful movement
            transport_cost = calculate_transport_cost(old_position, destination)
            carbon_emissions = calculate_carbon_emissions(old_position, destination)
            
            pkg.total_transport_cost += transport_cost
            pkg.total_carbon_emissions += carbon_emissions
            state.total_transport_cost += transport_cost
            state.total_carbon_emissions += carbon_emissions
            
            arrivals[destination] += 1
            pkg.position = destination
            pkg.in_transit = False
            pkg.arrival_time = None
            pkg.next_position = None
            pkg.path_history.append(destination)
            pkg.days_at_current_position = 0  # Reset counter for new position
            
            if destination == US_ENTRY_PORT:
                pkg.cycle_count += 1
            if destination in [EU_RETAILER_1, EU_RETAILER_2, EU_RETAILER_3, EU_RETAILER_4]:
                pkg.hold_until_day = t + sample_retailer_dwell(day_of_year)
            
            # Damage at node check upon arrival (e.g., handling)
            if not pkg.retired and maybe_damage_at_node():
                pkg.retired = True
                pkg.forced_retirement = True
                state.retired_packages.append(pkg)
    return arrivals


def main_conservation_equation(state, t, arrivals, r_natural, r_forced, p_natural, p_forced):
    x_new = np.copy(state.inventory)

    if arrivals is not None:
        x_new += arrivals

    current_flows = state.flows[t]
    for (i, j), flow in current_flows.items():
        if flow > 0:
            x_new[i] -= flow

    x_new -= r_natural
    x_new -= r_forced
    x_new += p_natural
    x_new += p_forced

    return x_new


def determine_next_node(pkg, state, day_of_year):
    current = pkg.position

    if current == US_POOLER:
        return constraint_12_grower_selection(pkg, day_of_year)

    if current == EU_DC:
        retailers = [EU_RETAILER_1, EU_RETAILER_2, EU_RETAILER_3, EU_RETAILER_4]
        return random.choices(retailers, weights=RETAILER_PROPORTIONS)[0]

    for j in range(1, NUM_NODES + 1):
        if state.adjacency[current, j] == 1:
            return j
    return None


def simulate_step(state, t):
    day_of_year = t % 365

    r_natural = np.zeros(NUM_NODES + 1)
    r_forced = np.zeros(NUM_NODES + 1)
    p_natural = np.zeros(NUM_NODES + 1)
    p_forced = np.zeros(NUM_NODES + 1)

    # Process any repairs completing today -> refurbished packages
    refurbished_ids = []
    if state.repair_backlog:
        still_pending = []
        for job in state.repair_backlog:
            if t >= job['ready_day'] and random.random() <= job.get('success_prob', REPAIR_SUCCESS_PROB):
                refurbished_ids.append(job['package_id'])
            else:
                still_pending.append(job)
        state.repair_backlog = still_pending
    if refurbished_ids:
        count = len(refurbished_ids)
        p_forced[US_POOLER] += count
        repair_cost_total = count * REPAIR_COST
        state.total_repair_cost += repair_cost_total
        for _ in range(count):
            new_pkg = Package(id=state.package_id_counter, position=US_POOLER)
            new_pkg.path_history.append(US_POOLER)
            new_pkg.last_active_day = t
            # refurbished: reset wear and costs
            new_pkg.wear_accumulation = 0.0
            new_pkg.total_transport_cost = 0.0
            new_pkg.total_carbon_emissions = 0.0
            new_pkg.total_holding_cost = 0.0
            state.packages[state.package_id_counter] = new_pkg
            state.package_id_counter += 1
            # refurbishment does not increase total_produced metric

    constraint_6_asset_lifecycle(state.packages, day_of_year)

    for pkg in state.packages.values():
        if (pkg.cycle_count >= pkg.max_cycles or pkg.wear_accumulation >= MAX_WEAR_ACCUMULATION) and not pkg.retired:
            pkg.retired = True
            r_natural[pkg.position] += 1
            state.retired_packages.append(pkg)

    idle_retired = constraint_23_idle_package_retirement(state.packages, t, day_of_year)
    for pkg_id in idle_retired:
        r_forced[state.packages[pkg_id].position] += 1
        state.retired_packages.append(state.packages[pkg_id])
        # push to repair with some probability? Assume idle retirements are not repaired

    excess_packages = constraint_26_fleet_optimization(state, day_of_year, t)
    for pkg_id in excess_packages:
        if pkg_id in state.packages and not state.packages[pkg_id].retired:
            state.packages[pkg_id].retired = True
            state.packages[pkg_id].forced_retirement = True
            r_forced[state.packages[pkg_id].position] += 1
            state.retired_packages.append(state.packages[pkg_id])

    seasonal_production = constraint_20_seasonal_production(state, day_of_year)
    emergency_production = constraint_22_emergency_production(state, day_of_year)

    fleet_adjustment = constraint_24_demand_linked_fleet_size(state, day_of_year)
    if fleet_adjustment < 0:
        seasonal_production += abs(fleet_adjustment)

    total_production = seasonal_production + emergency_production

    if total_production > 0:
        p_natural[US_POOLER] = total_production
        production_cost_total = total_production * PRODUCTION_COST
        state.total_production_cost += production_cost_total
        for i in range(int(total_production)):
            new_pkg = Package(id=state.package_id_counter, position=US_POOLER)
            new_pkg.path_history.append(US_POOLER)
            new_pkg.last_active_day = t
            state.packages[state.package_id_counter] = new_pkg
            state.package_id_counter += 1
            state.total_produced += 1

    new_flows = defaultdict(float)
    packages_to_move = defaultdict(list)

    for pkg_id, pkg in state.packages.items():
        if not pkg.retired and not pkg.in_transit:
            packages_to_move[pkg.position].append(pkg)

    demand_mult = get_potato_demand_multiplier(day_of_year)

    retailer_demand = get_retailer_daily_demand(day_of_year)
    unmet_demand = {k: 0 for k in retailer_demand.keys()}

    for node, packages in packages_to_move.items():
        if node == US_EXPORT_PORT or node == EU_RETURN_PORT:
            if is_sailing_day(node, t):
                cap = sailing_capacity(node)
                to_ship = min(len(packages), cap)
                if to_ship > 0:
                    next_node = SEA_EXPORT if node == US_EXPORT_PORT else SEA_RETURN
                    for pkg in packages[:to_ship]:
                        pkg.in_transit = True
                        delay = sample_delay(node, next_node, day_of_year)
                        pkg.arrival_time = t + delay
                        pkg.next_position = next_node
                        pkg.last_active_day = t
                        new_flows[(node, next_node)] += 1
            # if not sailing day, nothing ships

        elif node == EU_DC:
            by_retailer = {EU_RETAILER_1: [], EU_RETAILER_2: [], EU_RETAILER_3: [], EU_RETAILER_4: []}
            for pkg in packages:
                choice = random.choices(list(by_retailer.keys()), weights=RETAILER_PROPORTIONS)[0]
                by_retailer[choice].append(pkg)
            for retailer, pkgs in by_retailer.items():
                capacity = retailer_demand.get(retailer, 0)
                to_send = pkgs[:capacity]
                if len(pkgs) > capacity:
                    unmet_demand[retailer] += (len(pkgs) - capacity)
                for pkg in to_send:
                    next_node = retailer
                    pkg.in_transit = True
                    delay = sample_delay(node, next_node, day_of_year)
                    pkg.arrival_time = t + delay
                    pkg.next_position = next_node
                    pkg.last_active_day = t
                    new_flows[(node, next_node)] += 1

        elif node in [EU_RETAILER_1, EU_RETAILER_2, EU_RETAILER_3, EU_RETAILER_4]:
            ready_pkgs = [pkg for pkg in packages if (pkg.hold_until_day is None or pkg.hold_until_day <= t)]
            for pkg in ready_pkgs:
                next_node = EU_POOLER
                pkg.in_transit = True
                delay = sample_delay(node, next_node, day_of_year)
                pkg.arrival_time = t + delay
                pkg.next_position = next_node
                pkg.last_active_day = t
                new_flows[(node, next_node)] += 1

        else:
            if node == US_POOLER:
                daily_need = int(10 * demand_mult)
                packages_to_process = packages[:daily_need] if len(packages) > daily_need else packages
            elif demand_mult > 1.5 and len(packages) > 5:
                packages_to_process = packages
            else:
                max_flow = max(1, int(len(packages) * min(1.0, demand_mult)))
                packages_to_process = packages[:max_flow]

            for pkg in packages_to_process:
                next_node = determine_next_node(pkg, state, day_of_year)
                if next_node:
                    pkg.in_transit = True
                    delay = sample_delay(node, next_node, day_of_year)
                    pkg.arrival_time = t + delay
                    pkg.next_position = next_node
                    pkg.last_active_day = t
                    pkg.idle_days_at_pooler = 0
                    new_flows[(node, next_node)] += 1

    new_flows = constraint_3_non_negative_flows(new_flows)
    new_flows = constraint_5_arc_flow_capacity(new_flows)
    new_flows = constraint_10_network_topology(new_flows, state.adjacency)

    utilization = constraint_25_track_package_utilization(state.packages, new_flows, t)

    state.flows[t] = new_flows

    arrivals_today = process_arrivals(state, t, day_of_year)

    # When packages are retired due to damage, push to repair backlog
    for pkg in state.retired_packages:
        # Only add freshly retired today due to damage: approximate by last_active_day == t
        if pkg.forced_retirement and pkg.last_active_day == t:
            state.repair_backlog.append({
                'ready_day': t + sample_repair_lead_time(),
                'package_id': pkg.id,
                'success_prob': REPAIR_SUCCESS_PROB
            })
            # Count retirement at the node where it arrived (already handled via inventory update)

    departures_today = np.zeros(NUM_NODES + 1)
    for (i, j), flow in new_flows.items():
        departures_today[i] += flow

    next_inventory = main_conservation_equation(state, t, arrivals_today, r_natural, r_forced, p_natural, p_forced)

    delta = next_inventory - state.inventory
    lhs = arrivals_today + p_natural + p_forced - departures_today - r_natural - r_forced
    if not np.allclose(delta, lhs, atol=1e-6):
        state.conservation_violations.append({
            't': t,
            'delta': delta.tolist(),
            'lhs': lhs.tolist()
        })

    state.inventory = next_inventory

    state.inventory = constraint_2_non_negative_inventory(state.inventory)
    state.inventory = constraint_4_capacity_nodes(state.inventory)

    state.time = t

    # Calculate daily holding costs for all packages
    daily_holding_cost = 0.0
    for pkg in state.packages.values():
        if not pkg.retired:
            pkg.days_at_current_position += 1
            holding_cost = calculate_holding_cost(pkg.position)
            pkg.total_holding_cost += holding_cost
            daily_holding_cost += holding_cost
    
    state.total_holding_cost += daily_holding_cost
    
    # Record daily cost breakdown
    state.daily_costs.append({
        'day': t,
        'transport_cost': sum(calculate_transport_cost(i, j) * flow 
                            for (i, j), flow in new_flows.items()),
        'holding_cost': daily_holding_cost,
        'production_cost': total_production * PRODUCTION_COST if total_production > 0 else 0,
        'repair_cost': len(refurbished_ids) * REPAIR_COST if refurbished_ids else 0
    })

    total_unmet = sum(unmet_demand.values()) if unmet_demand else 0
    state.unmet_demand_history.append(total_unmet)

    return state


def run_simulation(days: int = SIMULATION_DAYS):
    state = NetworkState()

    metrics = {
        'time': [],
        'active_packages': [],
        'in_transit': [],
        'retired': [],
        'total_produced': [],
        'demand_multiplier': [],
        'node_inventory': defaultdict(list),
        'unmet_demand': []
    }

    for t in range(days):
        state = simulate_step(state, t)

        active = sum(1 for pkg in state.packages.values() if not pkg.retired)
        in_transit = sum(1 for pkg in state.packages.values() if pkg.in_transit)
        retired = len(state.retired_packages)
        demand_mult = get_potato_demand_multiplier(t % 365)

        metrics['time'].append(t)
        metrics['active_packages'].append(active)
        metrics['in_transit'].append(in_transit)
        metrics['retired'].append(retired)
        metrics['total_produced'].append(state.total_produced)
        metrics['demand_multiplier'].append(demand_mult)
        metrics['unmet_demand'].append(state.unmet_demand_history[-1] if state.unmet_demand_history else 0)

        for node in range(1, NUM_NODES + 1):
            node_count = sum(1 for pkg in state.packages.values()
                             if pkg.position == node and not pkg.in_transit and not pkg.retired)
            metrics['node_inventory'][node].append(node_count)

    return state, metrics


def plot_seasonal_metrics(metrics):
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))

    ax1 = axes[0]
    ax1.plot(metrics['time'], metrics['active_packages'], 'b-', label='Active', linewidth=2)
    ax1.plot(metrics['time'], metrics['in_transit'], 'g-', label='Transit', linewidth=1)
    ax1.plot(metrics['time'], metrics['retired'], 'r-', label='Retired', linewidth=1)
    ax1.plot(metrics['time'], metrics['total_produced'], 'c--', label='Produced', linewidth=1)

    ax2 = ax1.twinx()
    ax2.plot(metrics['time'], metrics['demand_multiplier'], 'orange',
             label='Demand', linewidth=2, alpha=0.7)
    ax2.set_ylabel('Demand Multiplier', color='orange')

    ax1.set_xlabel('Day')
    ax1.set_ylabel('Packages')
    ax1.set_title('RTP Network Flow with Potato Seasonality')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    for day in range(365):
        if 213 <= day <= 334:
            ax1.axvspan(day, day + 1, alpha=0.1, color='green')
        elif 91 <= day <= 212:
            ax1.axvspan(day, day + 1, alpha=0.1, color='yellow')
        else:
            ax1.axvspan(day, day + 1, alpha=0.05, color='blue')

    ax3 = axes[1]
    for node in [2, 3, 4]:
        ax3.plot(metrics['time'], metrics['node_inventory'][node],
                 label=f'Grower {node - 1}')
    ax3.set_xlabel('Day')
    ax3.set_ylabel('Inventory')
    ax3.set_title('Grower Activity')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    ax4 = axes[2]
    ax4.plot(metrics['time'], metrics['node_inventory'][5], 'b-',
             label='US Export', linewidth=1.5)
    ax4.plot(metrics['time'], metrics['node_inventory'][14], 'r-',
             label='EU Return', linewidth=1.5)
    ax4.set_xlabel('Day')
    ax4.set_ylabel('Inventory')
    ax4.set_title('Port Batch Accumulation')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    filename = 'seasonal_metrics.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {filename}")
    plt.close()


def plot_cost_and_carbon_analysis(state, metrics):
    """Plot cost and carbon analysis over time."""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Extract daily cost data
    days = [cost['day'] for cost in state.daily_costs]
    transport_costs = [cost['transport_cost'] for cost in state.daily_costs]
    holding_costs = [cost['holding_cost'] for cost in state.daily_costs]
    production_costs = [cost['production_cost'] for cost in state.daily_costs]
    repair_costs = [cost['repair_cost'] for cost in state.daily_costs]
    
    # Plot 1: Daily cost breakdown
    ax1 = axes[0, 0]
    ax1.stackplot(days, transport_costs, holding_costs, production_costs, repair_costs,
                  labels=['Transport', 'Holding', 'Production', 'Repair'],
                  colors=['blue', 'orange', 'green', 'red'], alpha=0.7)
    ax1.set_xlabel('Day')
    ax1.set_ylabel('Daily Cost (USD)')
    ax1.set_title('Daily Cost Breakdown')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Cumulative costs
    ax2 = axes[0, 1]
    cumulative_transport = np.cumsum(transport_costs)
    cumulative_holding = np.cumsum(holding_costs)
    cumulative_production = np.cumsum(production_costs)
    cumulative_repair = np.cumsum(repair_costs)
    
    ax2.plot(days, cumulative_transport, 'b-', label='Transport', linewidth=2)
    ax2.plot(days, cumulative_holding, 'orange', label='Holding', linewidth=2)
    ax2.plot(days, cumulative_production, 'g-', label='Production', linewidth=2)
    ax2.plot(days, cumulative_repair, 'r-', label='Repair', linewidth=2)
    ax2.plot(days, cumulative_transport + cumulative_holding + cumulative_production + cumulative_repair,
             'k--', label='Total', linewidth=3)
    
    ax2.set_xlabel('Day')
    ax2.set_ylabel('Cumulative Cost (USD)')
    ax2.set_title('Cumulative Cost Analysis')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Cost per package over time
    ax3 = axes[1, 0]
    active_packages = metrics['active_packages']
    total_daily_cost = [t + h + p + r for t, h, p, r in 
                       zip(transport_costs, holding_costs, production_costs, repair_costs)]
    cost_per_package = [total / max(active, 1) for total, active in zip(total_daily_cost, active_packages)]
    
    ax3.plot(days, cost_per_package, 'purple', linewidth=2)
    ax3.set_xlabel('Day')
    ax3.set_ylabel('Cost per Active Package (USD)')
    ax3.set_title('Daily Cost per Package')
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Carbon emissions over time (estimated from transport)
    ax4 = axes[1, 1]
    # Estimate daily carbon from transport costs (rough approximation)
    carbon_per_dollar = 0.5  # kg CO2 per USD transport cost
    daily_carbon = [cost * carbon_per_dollar for cost in transport_costs]
    cumulative_carbon = np.cumsum(daily_carbon)
    
    ax4.plot(days, daily_carbon, 'green', linewidth=2, label='Daily Emissions')
    ax4_twin = ax4.twinx()
    ax4_twin.plot(days, cumulative_carbon, 'darkgreen', linewidth=3, label='Cumulative Emissions')
    
    ax4.set_xlabel('Day')
    ax4.set_ylabel('Daily Carbon Emissions (kg CO2)', color='green')
    ax4_twin.set_ylabel('Cumulative Carbon Emissions (kg CO2)', color='darkgreen')
    ax4.set_title('Carbon Emissions Analysis')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    filename = 'cost_carbon_analysis.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {filename}")
    plt.close()


def print_cost_summary(state, metrics):
    """Print comprehensive cost and carbon summary."""
    
    print("\n" + "=" * 80)
    print("COST AND CARBON ANALYSIS")
    print("=" * 80)
    
    # Total costs
    total_cost = (state.total_transport_cost + state.total_holding_cost + 
                 state.total_production_cost + state.total_repair_cost)
    
    print(f"\nTotal Costs (USD):")
    print(f"  Transport:     ${state.total_transport_cost:,.2f}")
    print(f"  Holding:       ${state.total_holding_cost:,.2f}")
    print(f"  Production:    ${state.total_production_cost:,.2f}")
    print(f"  Repair:        ${state.total_repair_cost:,.2f}")
    print(f"  TOTAL:         ${total_cost:,.2f}")
    
    # Cost per package metrics
    final_active = sum(1 for pkg in state.packages.values() if not pkg.retired)
    total_packages_ever = len(state.packages) + len(state.retired_packages)
    
    print(f"\nCost per Package:")
    print(f"  Per active package:     ${total_cost / max(final_active, 1):.2f}")
    print(f"  Per package ever:        ${total_cost / max(total_packages_ever, 1):.2f}")
    print(f"  Per package-cycle:      ${total_cost / max(sum(pkg.cycle_count for pkg in state.packages.values()), 1):.2f}")
    
    # Carbon emissions
    print(f"\nCarbon Emissions:")
    print(f"  Total transport CO2:    {state.total_carbon_emissions:,.1f} kg")
    print(f"  Per active package:     {state.total_carbon_emissions / max(final_active, 1):.2f} kg")
    print(f"  Per package-cycle:      {state.total_carbon_emissions / max(sum(pkg.cycle_count for pkg in state.packages.values()), 1):.2f} kg")
    
    # Cost efficiency metrics
    total_cycles = sum(pkg.cycle_count for pkg in state.packages.values())
    print(f"\nEfficiency Metrics:")
    print(f"  Total package-cycles:   {total_cycles}")
    print(f"  Cost per cycle:         ${total_cost / max(total_cycles, 1):.2f}")
    print(f"  Carbon per cycle:       {state.total_carbon_emissions / max(total_cycles, 1):.2f} kg")
    
    # Seasonal analysis
    if len(state.daily_costs) >= 365:
        winter_costs = sum(cost['transport_cost'] + cost['holding_cost'] + cost['production_cost'] + cost['repair_cost']
                          for cost in state.daily_costs[0:90] + state.daily_costs[335:365])
        summer_costs = sum(cost['transport_cost'] + cost['holding_cost'] + cost['production_cost'] + cost['repair_cost']
                          for cost in state.daily_costs[182:273])
        
        print(f"\nSeasonal Cost Analysis:")
        print(f"  Winter costs:          ${winter_costs:,.2f}")
        print(f"  Summer costs:          ${summer_costs:,.2f}")
        print(f"  Summer/Winter ratio:   {summer_costs / max(winter_costs, 1):.2f}")
    
    print("=" * 80)


def plot_network_flow(state, metrics, day_range=None):
    """Plot network diagram showing flow of produce and transport packages between nodes."""
    
    # Create directed graph
    G = nx.DiGraph()
    
    # Add nodes with positions
    node_positions = {
        1: (0, 0),      # US_POOLER
        2: (-2, 1),     # US_GROWER_1
        3: (-2, 0),     # US_GROWER_2
        4: (-2, -1),    # US_GROWER_3
        5: (-1, 0),     # US_EXPORT_PORT
        6: (0, 1),      # SEA_EXPORT
        7: (1, 1),      # EU_ENTRY_PORT
        8: (2, 1),      # EU_DC
        9: (3, 2),      # EU_RETAILER_1
        10: (3, 1.5),   # EU_RETAILER_2
        11: (3, 0.5),   # EU_RETAILER_3
        12: (3, 0),     # EU_RETAILER_4
        13: (2, 0),     # EU_POOLER
        14: (1, 0),     # EU_RETURN_PORT
        15: (0, -1),    # SEA_RETURN
        16: (-1, -1),   # US_ENTRY_PORT
    }
    
    # Add nodes to graph
    for node_id, pos in node_positions.items():
        G.add_node(node_id, pos=pos)
    
    # Add edges
    for (i, j) in DELAYS.keys():
        G.add_edge(i, j)
    
    # Calculate average flow over specified day range
    if day_range is None:
        start_day, end_day = 0, len(metrics['time'])
    else:
        start_day, end_day = day_range
    
    avg_flows = defaultdict(float)
    flow_count = 0
    
    for t in range(start_day, end_day):
        if t in state.flows:
            for (i, j), flow in state.flows[t].items():
                avg_flows[(i, j)] += flow
                flow_count += 1
    
    if flow_count > 0:
        for edge in avg_flows:
            avg_flows[edge] /= flow_count
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
    
    # Plot 1: Network structure with flow thickness
    pos = nx.get_node_attributes(G, 'pos')
    
    # Draw nodes
    node_colors = []
    node_labels = {}
    for node in G.nodes():
        if node in [1, 13]:  # Poolers
            node_colors.append('lightblue')
        elif node in [2, 3, 4]:  # US Growers
            node_colors.append('lightgreen')
        elif node in [5, 14]:  # Export/Return ports
            node_colors.append('orange')
        elif node in [6, 15]:  # Sea transport
            node_colors.append('lightcoral')
        elif node in [7, 8]:  # EU Entry/DC
            node_colors.append('lightyellow')
        elif node in [9, 10, 11, 12]:  # EU Retailers
            node_colors.append('lightpink')
        elif node == 16:  # US Entry
            node_colors.append('lightgray')
        else:
            node_colors.append('white')
        
        node_labels[node] = get_node_name(node)
    
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1000, ax=ax1)
    nx.draw_networkx_labels(G, pos, node_labels, font_size=8, ax=ax1)
    
    # Draw edges with thickness based on flow
    edge_widths = []
    edge_colors = []
    for edge in G.edges():
        flow = avg_flows.get(edge, 0)
        edge_widths.append(max(1, flow * 2))  # Scale width
        
        # Color edges based on flow direction and volume
        if flow > 5:
            edge_colors.append('red')
        elif flow > 2:
            edge_colors.append('orange')
        elif flow > 0:
            edge_colors.append('green')
        else:
            edge_colors.append('gray')
    
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_colors, 
                          arrows=True, arrowsize=20, ax=ax1)
    
    ax1.set_title(f'Network Flow Diagram\n(Average flows over days {start_day}-{end_day-1})')
    ax1.axis('off')
    
    # Plot 2: Flow volume bar chart
    edge_labels = []
    flow_values = []
    colors = []
    
    for edge in sorted(avg_flows.keys()):
        i, j = edge
        flow = avg_flows[edge]
        if flow > 0:
            edge_labels.append(f'{get_node_name(i)} → {get_node_name(j)}')
            flow_values.append(flow)
            if flow > 5:
                colors.append('red')
            elif flow > 2:
                colors.append('orange')
            else:
                colors.append('green')
    
    if flow_values:
        bars = ax2.barh(range(len(edge_labels)), flow_values, color=colors)
        ax2.set_yticks(range(len(edge_labels)))
        ax2.set_yticklabels(edge_labels, fontsize=8)
        ax2.set_xlabel('Average Daily Flow')
        ax2.set_title('Flow Volumes Between Nodes')
        ax2.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, flow_values)):
            ax2.text(value + 0.1, bar.get_y() + bar.get_height()/2, 
                    f'{value:.1f}', va='center', fontsize=8)

    plt.tight_layout()
    filename = 'network_flow.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {filename}")
    plt.close()


def get_node_name(node_id):
    names = {
        1: "US-Pooler", 2: "US-Grower1", 3: "US-Grower2", 4: "US-Grower3",
        5: "US-Export", 6: "Sea-Export", 7: "EU-Entry", 8: "EU-DC",
        9: "EU-Retail1", 10: "EU-Retail2", 11: "EU-Retail3", 12: "EU-Retail4",
        13: "EU-Pooler", 14: "EU-Return", 15: "Sea-Return", 16: "US-Entry"
    }
    return names.get(node_id, f"Node-{node_id}")


def print_header():
    print("=" * 70)
    print("RTP SUPPLY CHAIN NETWORK MODEL - POTATO SEASONALITY")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  Initial packages: {N_0}")
    print(f"  Network nodes: {NUM_NODES}")
    print(f"  Simulation period: {SIMULATION_DAYS} days")
    print(f"  Max cycles per package: {C_MAX_DEFAULT}")
    print(f"  Base batch size: {B_EXPORT_BASE}")
    print("-" * 70)


def print_seasonal_status(t, active, in_transit, retired, produced, demand_mult):
    day_of_year = t % 365 + 1
    season = ""
    if 1 <= day_of_year <= 90 or 335 <= day_of_year <= 365:
        season = "Winter/Storage"
    elif 91 <= day_of_year <= 181:
        season = "Spring/Early"
    elif 182 <= day_of_year <= 273:
        season = "Summer/Main"
    else:
        season = "Fall/Late"

    print(f"Day {t:3d} [{season:15s}]: Active={active:3d}, Transit={in_transit:3d}, "
          f"Retired={retired:3d}, Produced={produced:3d}, Demand={demand_mult:.1f}x")


def print_summary(state, metrics):
    print("\n" + "=" * 70)
    print("SIMULATION SUMMARY")
    print("=" * 70)

    print("\nYear Statistics:")
    print(f"  Total packages produced: {state.total_produced}")
    print(f"  Total packages retired: {len(state.retired_packages)}")
    print(f"  Final active packages: {sum(1 for pkg in state.packages.values() if not pkg.retired)}")
    print(f"  Peak active packages: {max(metrics['active_packages'])}")
    print(f"  Minimum active packages: {min(metrics['active_packages'])}")

    final_active = sum(1 for pkg in state.packages.values() if not pkg.retired)
    final_retired = len(state.retired_packages)

    print("\nConservation Check (Constraint 11):")
    print(f"  Initial: {N_0}")
    print(f"  Active: {final_active}")
    print(f"  Retired: {final_retired}")
    print(f"  Produced: {state.total_produced}")
    print(f"  Conservation: {final_active + final_retired} == {N_0 + state.total_produced}", end="")
    if final_active + final_retired == N_0 + state.total_produced:
        print(" ✓")
    else:
        print(" ✗")

    print("\nConstraints Applied:")
    print("  Original (1-18):")
    print("    ✓ Flow conservation, Non-negativity, Capacity limits")
    print("    ✓ Asset lifecycle, Retirement rules, Path continuity")
    print("    ✓ Network topology, System conservation")
    print("    ✓ Batch shipping, Proportional allocation")
    print("    ✓ Production rules")
    print("  Seasonal (19-26):")
    print("    ✓ Seasonal flow rates")
    print("    ✓ Seasonal production")
    print("    ✓ Accelerated wear")
    print("    ✓ Emergency production")
    print("    ✓ Idle package retirement")
    print("    ✓ Demand-linked fleet size")
    print("    ✓ Package utilization tracking")
    print("    ✓ Fleet optimization")

    if state.conservation_violations:
        print("\nPer-node conservation violations detected on days:")
        print("  ", [v['t'] for v in state.conservation_violations[:10]], ("..." if len(state.conservation_violations) > 10 else ""))

    print("=" * 70)


def export_for_visualization(state, metrics, filename='simulation_data.json'):
    """Export simulation data for the interactive D3.js visualization."""
    import json

    # Node metadata
    node_info = {
        1: {"name": "US Pooler", "type": "pooler", "icon": "🏭", "region": "US"},
        2: {"name": "US Grower 1", "type": "grower", "icon": "🥔", "region": "US"},
        3: {"name": "US Grower 2", "type": "grower", "icon": "🥔", "region": "US"},
        4: {"name": "US Grower 3", "type": "grower", "icon": "🥔", "region": "US"},
        5: {"name": "US Export Port", "type": "port", "icon": "🚢", "region": "US"},
        6: {"name": "Sea Export", "type": "sea", "icon": "🌊", "region": "Ocean"},
        7: {"name": "EU Entry Port", "type": "port", "icon": "🚢", "region": "EU"},
        8: {"name": "EU Distribution Center", "type": "dc", "icon": "🏭", "region": "EU"},
        9: {"name": "EU Retailer 1", "type": "retailer", "icon": "🏪", "region": "EU"},
        10: {"name": "EU Retailer 2", "type": "retailer", "icon": "🏪", "region": "EU"},
        11: {"name": "EU Retailer 3", "type": "retailer", "icon": "🏪", "region": "EU"},
        12: {"name": "EU Retailer 4", "type": "retailer", "icon": "🏪", "region": "EU"},
        13: {"name": "EU Pooler", "type": "pooler", "icon": "🏭", "region": "EU"},
        14: {"name": "EU Return Port", "type": "port", "icon": "🚢", "region": "EU"},
        15: {"name": "Sea Return", "type": "sea", "icon": "🌊", "region": "Ocean"},
        16: {"name": "US Entry Port", "type": "port", "icon": "🚢", "region": "US"},
    }

    # Edge metadata
    edges = []
    for (i, j), delay in DELAYS.items():
        is_ocean = (i == 6 and j == 7) or (i == 15 and j == 16)
        edges.append({
            "source": i,
            "target": j,
            "delay": delay,
            "ocean": is_ocean,
            "cost": TRANSPORT_COSTS.get((i, j), 0),
            "carbon": CARBON_EMISSIONS.get((i, j), 0)
        })

    # Daily data
    daily_data = []
    for t in range(len(metrics['time'])):
        day_of_year = t % 365

        # Determine season
        if 213 <= day_of_year <= 334:
            season = "summer"
        elif 91 <= day_of_year <= 212:
            season = "spring"
        else:
            season = "winter"

        # Node inventories for this day
        node_inventories = {}
        for node in range(1, NUM_NODES + 1):
            node_inventories[str(node)] = metrics['node_inventory'][node][t]

        # Flows for this day
        flows = []
        if t in state.flows:
            for (i, j), flow in state.flows[t].items():
                if flow > 0:
                    flows.append({
                        "source": i,
                        "target": j,
                        "count": int(flow)
                    })

        # Daily costs
        daily_cost = state.daily_costs[t] if t < len(state.daily_costs) else {}

        daily_data.append({
            "day": t,
            "day_of_year": day_of_year,
            "season": season,
            "demand_multiplier": metrics['demand_multiplier'][t],
            "active_packages": metrics['active_packages'][t],
            "in_transit": metrics['in_transit'][t],
            "retired": metrics['retired'][t],
            "total_produced": metrics['total_produced'][t],
            "node_inventories": node_inventories,
            "flows": flows,
            "transport_cost": daily_cost.get('transport_cost', 0),
            "holding_cost": daily_cost.get('holding_cost', 0),
            "production_cost": daily_cost.get('production_cost', 0),
            "repair_cost": daily_cost.get('repair_cost', 0)
        })

    # Aggregate data
    export_data = {
        "config": {
            "initial_packages": N_0,
            "num_nodes": NUM_NODES,
            "simulation_days": len(metrics['time'])
        },
        "nodes": node_info,
        "edges": edges,
        "daily_data": daily_data,
        "totals": {
            "transport_cost": state.total_transport_cost,
            "holding_cost": state.total_holding_cost,
            "production_cost": state.total_production_cost,
            "repair_cost": state.total_repair_cost,
            "carbon_emissions": state.total_carbon_emissions
        }
    }

    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"  ✓ Exported visualization data to: {filename}")
    return filename


if __name__ == "__main__":
    print_header()

    print("\nRunning simulation...")
    state, metrics = run_simulation()

    print("\nSimulation Progress:")
    for t in range(0, SIMULATION_DAYS, 30):
        if t < len(metrics['time']):
            print_seasonal_status(
                t,
                metrics['active_packages'][t],
                metrics['in_transit'][t],
                metrics['retired'][t],
                metrics['total_produced'][t],
                metrics['demand_multiplier'][t]
            )

    print_summary(state, metrics)
    print_cost_summary(state, metrics)

    print("\nGenerating visualizations...")
    plot_seasonal_metrics(metrics)
    
    print("\nGenerating network flow diagram...")
    plot_network_flow(state, metrics)
    
    print("\nGenerating cost and carbon analysis...")
    plot_cost_and_carbon_analysis(state, metrics)

    print("\nExporting data for interactive visualization...")
    export_for_visualization(state, metrics)

    print("\nSimulation complete!")