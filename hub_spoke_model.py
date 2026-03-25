"""
Domestic US Hub-and-Spoke Cold Chain Network Model
for Reusable Transport Packaging (RTP) of Potatoes

Inspired by:
  - "Optimizing Cold Food Supply Chains for Enhanced Food Availability
     Under Climate Variability" (MDPI Foods, 2025)
  - Multi-echelon cold chain design literature
  - Stochastic hub-and-spoke network optimization models

Network topology:
  5 Farm regions → 3 Regional Hubs → 1 National DC → 4 Regional DCs → 6 Retail Clusters
  Return: Retail Clusters → Regional DCs → National DC → Regional Hubs → Farm regions

20-node directed graph with hub consolidation and cold chain quality tracking.
"""

import numpy as np
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import json
import math

# ── Node IDs ──────────────────────────────────────────────────────────────────
# Farms (potato growing regions)
FARM_IDAHO      = 1
FARM_WASHINGTON = 2
FARM_WISCONSIN  = 3
FARM_MAINE      = 4
FARM_COLORADO   = 5

# Regional consolidation hubs
HUB_WEST   = 6   # Boise, ID area
HUB_CENTRAL = 7  # Omaha, NE area
HUB_EAST    = 8  # Albany, NY area

# National distribution center
NATIONAL_DC = 9   # Kansas City, MO area

# Regional distribution centers
RDC_WEST      = 10  # Los Angeles
RDC_SOUTH     = 11  # Atlanta
RDC_NORTHEAST = 12  # Philadelphia
RDC_MIDWEST   = 13  # Chicago

# Retail clusters
RETAIL_PACIFIC    = 14  # West Coast
RETAIL_SOUTHWEST  = 15  # TX/AZ
RETAIL_SOUTHEAST  = 16  # FL/GA
RETAIL_MIDATLANTIC = 17 # DC/MD/VA
RETAIL_NEWENGLAND = 18  # Boston/NY
RETAIL_HEARTLAND  = 19  # OH/IN/IL

# Collection / Return pooler
RETURN_POOLER = 20  # National return pooler

NUM_NODES = 20
N_0 = 80  # Initial fleet
SIMULATION_DAYS = 365

# ── Network arcs with base delays (days) ─────────────────────────────────────
DELAYS = {
    # Farms → Regional Hubs (consolidation)
    (1, 6): 1, (2, 6): 2, (5, 7): 2,
    (3, 7): 1, (4, 8): 1, (3, 8): 2,
    # Regional Hubs → National DC
    (6, 9): 3, (7, 9): 2, (8, 9): 3,
    # National DC → Regional DCs (distribution)
    (9, 10): 4, (9, 11): 3, (9, 12): 3, (9, 13): 2,
    # Regional DCs → Retail Clusters
    (10, 14): 2, (10, 15): 3,
    (11, 15): 2, (11, 16): 2,
    (12, 17): 1, (12, 18): 2,
    (13, 19): 1, (13, 18): 3,
    # Retail Clusters → Return Pooler (reverse logistics)
    (14, 20): 2, (15, 20): 3, (16, 20): 2,
    (17, 20): 2, (18, 20): 2, (19, 20): 1,
    # Return Pooler → Regional Hubs (redistribution)
    (20, 6): 3, (20, 7): 2, (20, 8): 3,
}

# ── Transport costs per package per leg (USD) ────────────────────────────────
TRANSPORT_COSTS = {
    (1, 6): 1.50, (2, 6): 2.50, (5, 7): 3.00,
    (3, 7): 2.00, (4, 8): 2.00, (3, 8): 3.50,
    (6, 9): 4.00, (7, 9): 3.00, (8, 9): 4.00,
    (9, 10): 6.00, (9, 11): 5.00, (9, 12): 5.00, (9, 13): 3.50,
    (10, 14): 2.50, (10, 15): 4.00,
    (11, 15): 3.00, (11, 16): 2.50,
    (12, 17): 1.50, (12, 18): 3.00,
    (13, 19): 1.50, (13, 18): 4.50,
    (14, 20): 3.00, (15, 20): 4.00, (16, 20): 3.00,
    (17, 20): 3.00, (18, 20): 3.00, (19, 20): 2.00,
    (20, 6): 5.00, (20, 7): 3.50, (20, 8): 5.00,
}

# ── Carbon emissions per package per leg (kg CO2) ────────────────────────────
CARBON_EMISSIONS = {
    (1, 6): 0.5, (2, 6): 0.8, (5, 7): 1.0,
    (3, 7): 0.6, (4, 8): 0.6, (3, 8): 1.2,
    (6, 9): 1.5, (7, 9): 1.0, (8, 9): 1.5,
    (9, 10): 2.5, (9, 11): 2.0, (9, 12): 2.0, (9, 13): 1.5,
    (10, 14): 0.8, (10, 15): 1.5,
    (11, 15): 1.0, (11, 16): 0.8,
    (12, 17): 0.5, (12, 18): 1.0,
    (13, 19): 0.5, (13, 18): 1.5,
    (14, 20): 1.0, (15, 20): 1.5, (16, 20): 1.0,
    (17, 20): 1.0, (18, 20): 1.0, (19, 20): 0.7,
    (20, 6): 2.0, (20, 7): 1.5, (20, 8): 2.0,
}

# ── Holding costs per package per day (USD) ───────────────────────────────────
HOLDING_COSTS = {
    1: 0.12, 2: 0.12, 3: 0.12, 4: 0.12, 5: 0.12,  # Farms (cold storage)
    6: 0.18, 7: 0.18, 8: 0.18,                       # Hubs (refrigerated)
    9: 0.20,                                           # National DC
    10: 0.15, 11: 0.15, 12: 0.15, 13: 0.15,          # Regional DCs
    14: 0.08, 15: 0.08, 16: 0.08, 17: 0.08, 18: 0.08, 19: 0.08,  # Retail
    20: 0.10,                                          # Return Pooler
}

NODE_CAPACITY = {i: 200 for i in range(1, NUM_NODES + 1)}
NODE_CAPACITY[9] = 400  # National DC higher cap
ARC_CAPACITY = {edge: 80 for edge in DELAYS.keys()}

PRODUCTION_COST = 25.00
REPAIR_COST = 8.00
C_MAX_DEFAULT = 15
MAX_WEAR = 250
MAX_IDLE_DAYS = 25

# Temperature / quality parameters
BASE_TEMP_TARGET = 4.0   # °C for potatoes
TEMP_DEVIATION_STD = 1.5
QUALITY_DECAY_RATE = 0.002  # per day base

P_DAMAGE_IN_TRANSIT = 0.008
P_DAMAGE_AT_NODE = 0.001
REPAIR_LEAD_TIME_MEAN = 8
REPAIR_LEAD_TIME_STD = 2
REPAIR_SUCCESS_PROB = 0.92

# Seasonal potato harvest: Idaho/WA peak Aug-Oct, Maine Sep-Oct, etc.
def get_potato_harvest_multiplier(day_of_year):
    """US domestic potato availability / demand multiplier."""
    if 213 <= day_of_year <= 304:   # Aug-Oct: main harvest
        return 2.5
    elif 121 <= day_of_year <= 212:  # May-Jul: early/new potatoes
        return 1.5
    elif 305 <= day_of_year <= 365:  # Nov-Dec: storage drawdown
        return 1.2
    else:                            # Jan-Apr: storage season
        return 0.6

def get_farm_proportions(day_of_year):
    """Which farms supply how much by season."""
    if 213 <= day_of_year <= 304:
        return {1: 0.35, 2: 0.25, 3: 0.15, 4: 0.10, 5: 0.15}
    elif 121 <= day_of_year <= 212:
        return {1: 0.20, 2: 0.20, 3: 0.25, 4: 0.15, 5: 0.20}
    else:
        return {1: 0.30, 2: 0.15, 3: 0.20, 4: 0.20, 5: 0.15}

def get_hub_for_farm(farm):
    return {1: HUB_WEST, 2: HUB_WEST, 3: HUB_CENTRAL,
            4: HUB_EAST, 5: HUB_CENTRAL}[farm]

def get_rdc_retail_mapping():
    return {
        RDC_WEST: [RETAIL_PACIFIC, RETAIL_SOUTHWEST],
        RDC_SOUTH: [RETAIL_SOUTHWEST, RETAIL_SOUTHEAST],
        RDC_NORTHEAST: [RETAIL_MIDATLANTIC, RETAIL_NEWENGLAND],
        RDC_MIDWEST: [RETAIL_HEARTLAND, RETAIL_NEWENGLAND],
    }

# ── Package and State ────────────────────────────────────────────────────────

@dataclass
class Package:
    id: int
    position: int
    cycle_count: int = 0
    max_cycles: int = C_MAX_DEFAULT
    in_transit: bool = False
    arrival_time: Optional[int] = None
    next_position: Optional[int] = None
    retired: bool = False
    forced_retirement: bool = False
    path_history: List[int] = field(default_factory=list)
    wear_accumulation: float = 0.0
    idle_days: int = 0
    last_active_day: int = 0
    hold_until_day: Optional[int] = None
    quality_level: float = 1.0
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
        self.total_produced = 0
        self.package_id_counter = N_0
        self.repair_backlog: List[Dict] = []

        self.adjacency = np.zeros((NUM_NODES + 1, NUM_NODES + 1))
        for (i, j) in DELAYS:
            self.adjacency[i, j] = 1

        # Place initial fleet at return pooler (ready to distribute)
        for i in range(N_0):
            pkg = Package(id=i, position=RETURN_POOLER)
            pkg.path_history.append(RETURN_POOLER)
            self.packages[i] = pkg
            self.inventory[RETURN_POOLER] += 1

        self.unmet_demand_history = []
        self.conservation_violations = []

        self.total_transport_cost = 0.0
        self.total_carbon_emissions = 0.0
        self.total_holding_cost = 0.0
        self.total_production_cost = 0.0
        self.total_repair_cost = 0.0
        self.daily_costs: List[Dict] = []


def sample_delay(i, j, day_of_year):
    base = DELAYS.get((i, j), 1)
    mult = get_potato_harvest_multiplier(day_of_year)
    mean = base * (1.15 if mult > 1.5 else 1.0)
    std = max(0.5, 0.25 * base)
    sampled = int(max(1, round(np.random.normal(mean, std))))
    # Disruption spike (weather/traffic)
    if random.random() < 0.03:
        sampled += random.randint(2, 7)
    return sampled


def determine_next_node(pkg, state, day_of_year):
    pos = pkg.position
    # Farms → their hub
    if pos in [1, 2, 3, 4, 5]:
        return get_hub_for_farm(pos)
    # Hubs → National DC
    if pos in [HUB_WEST, HUB_CENTRAL, HUB_EAST]:
        return NATIONAL_DC
    # National DC → Regional DCs (proportional)
    if pos == NATIONAL_DC:
        rdcs = [RDC_WEST, RDC_SOUTH, RDC_NORTHEAST, RDC_MIDWEST]
        weights = [0.25, 0.25, 0.30, 0.20]
        return random.choices(rdcs, weights=weights)[0]
    # Regional DCs → Retail clusters
    mapping = get_rdc_retail_mapping()
    if pos in mapping:
        return random.choice(mapping[pos])
    # Retail → Return Pooler
    if 14 <= pos <= 19:
        return RETURN_POOLER
    # Return Pooler → Hubs
    if pos == RETURN_POOLER:
        hubs = [HUB_WEST, HUB_CENTRAL, HUB_EAST]
        props = get_farm_proportions(day_of_year)
        hw = props.get(1, 0.3) + props.get(2, 0.2)
        hc = props.get(3, 0.2) + props.get(5, 0.15)
        he = props.get(4, 0.15)
        total = hw + hc + he
        return random.choices(hubs, weights=[hw/total, hc/total, he/total])[0]
    return None


def simulate_step(state, t):
    day_of_year = t % 365
    mult = get_potato_harvest_multiplier(day_of_year)

    r_natural = np.zeros(NUM_NODES + 1)
    r_forced = np.zeros(NUM_NODES + 1)
    p_natural = np.zeros(NUM_NODES + 1)

    # ── Repair processing ─────────────────────────────────────────────────
    refurbished = 0
    if state.repair_backlog:
        still_pending = []
        for job in state.repair_backlog:
            if t >= job['ready_day'] and random.random() <= REPAIR_SUCCESS_PROB:
                new_pkg = Package(id=state.package_id_counter, position=RETURN_POOLER)
                new_pkg.path_history.append(RETURN_POOLER)
                new_pkg.last_active_day = t
                state.packages[state.package_id_counter] = new_pkg
                state.package_id_counter += 1
                refurbished += 1
            else:
                still_pending.append(job)
        state.repair_backlog = still_pending
    if refurbished:
        p_natural[RETURN_POOLER] += refurbished
        state.total_repair_cost += refurbished * REPAIR_COST

    # ── Lifecycle / retirement ────────────────────────────────────────────
    for pkg in list(state.packages.values()):
        if pkg.retired:
            continue
        wear_rate = 2.5 if mult > 1.5 else (1.5 if mult > 1.0 else 0.5)
        pkg.wear_accumulation += wear_rate

        if pkg.cycle_count >= pkg.max_cycles or pkg.wear_accumulation >= MAX_WEAR:
            pkg.retired = True
            r_natural[pkg.position] += 1
            state.retired_packages.append(pkg)
            continue

        # Idle retirement
        if not pkg.in_transit and pkg.position == RETURN_POOLER:
            if pkg.last_active_day < t - 1:
                pkg.idle_days += 1
            if pkg.idle_days > MAX_IDLE_DAYS:
                pkg.retired = True
                pkg.forced_retirement = True
                r_forced[pkg.position] += 1
                state.retired_packages.append(pkg)

    # ── Production ────────────────────────────────────────────────────────
    active_count = sum(1 for p in state.packages.values() if not p.retired)
    target_fleet = int(N_0 * mult * 0.9)
    available_at_pooler = sum(1 for p in state.packages.values()
                              if p.position == RETURN_POOLER and not p.retired and not p.in_transit)
    production = 0
    if active_count < target_fleet:
        production += target_fleet - active_count
    threshold = int(20 * mult)
    if available_at_pooler < threshold:
        production += max(0, threshold - available_at_pooler)
    production = min(production, 30)  # cap daily production

    if production > 0:
        p_natural[RETURN_POOLER] += production
        state.total_production_cost += production * PRODUCTION_COST
        for _ in range(production):
            pkg = Package(id=state.package_id_counter, position=RETURN_POOLER)
            pkg.path_history.append(RETURN_POOLER)
            pkg.last_active_day = t
            state.packages[state.package_id_counter] = pkg
            state.package_id_counter += 1
            state.total_produced += 1

    # ── Movement planning ─────────────────────────────────────────────────
    new_flows = defaultdict(float)
    packages_by_node = defaultdict(list)
    for pkg in state.packages.values():
        if not pkg.retired and not pkg.in_transit:
            packages_by_node[pkg.position].append(pkg)

    def _dispatch(pkg, node, nxt):
        """Dispatch pkg from node to nxt, respecting arc capacity. Returns True if dispatched."""
        arc = (node, nxt)
        if arc in ARC_CAPACITY and new_flows[arc] >= ARC_CAPACITY[arc]:
            return False
        pkg.in_transit = True
        pkg.arrival_time = t + sample_delay(node, nxt, day_of_year)
        pkg.next_position = nxt
        pkg.last_active_day = t
        new_flows[arc] += 1
        return True

    retail_demand = {}
    for r in range(14, 20):
        base = 4
        retail_demand[r] = max(0, int(round(base * mult + np.random.normal(0, 0.8))))

    for node, pkgs in packages_by_node.items():
        # Retail nodes: hold then release
        if 14 <= node <= 19:
            ready = [p for p in pkgs if p.hold_until_day is None or p.hold_until_day <= t]
            for pkg in ready:
                nxt = determine_next_node(pkg, state, day_of_year)
                if nxt:
                    _dispatch(pkg, node, nxt)
            continue

        # Hub consolidation: batch when enough accumulated
        if node in [HUB_WEST, HUB_CENTRAL, HUB_EAST]:
            batch_size = max(5, int(8 * mult))
            if len(pkgs) >= batch_size:
                to_ship = pkgs[:min(len(pkgs), batch_size * 2)]
                for pkg in to_ship:
                    _dispatch(pkg, node, NATIONAL_DC)
            continue

        # National DC: distribute to RDCs
        if node == NATIONAL_DC:
            daily_cap = int(15 * mult)
            to_process = pkgs[:daily_cap]
            for pkg in to_process:
                nxt = determine_next_node(pkg, state, day_of_year)
                if nxt:
                    _dispatch(pkg, node, nxt)
            continue

        # Regional DCs: distribute to retail clusters based on demand
        if node in [RDC_WEST, RDC_SOUTH, RDC_NORTHEAST, RDC_MIDWEST]:
            mapping = get_rdc_retail_mapping()
            retailers = mapping.get(node, [])
            cap = sum(retail_demand.get(r, 0) for r in retailers)
            to_process = pkgs[:max(1, cap)]
            for pkg in to_process:
                nxt = determine_next_node(pkg, state, day_of_year)
                if nxt:
                    _dispatch(pkg, node, nxt)
            continue

        # Default: farms and return pooler
        daily_need = max(1, int(8 * mult))
        to_process = pkgs[:daily_need]
        for pkg in to_process:
            nxt = determine_next_node(pkg, state, day_of_year)
            if nxt:
                if _dispatch(pkg, node, nxt):
                    pkg.idle_days = 0

    state.flows[t] = dict(new_flows)

    # ── Arrival processing ────────────────────────────────────────────────
    arrivals = np.zeros(NUM_NODES + 1)
    arrival_retirements = np.zeros(NUM_NODES + 1)  # packages damaged on arrival at node
    for pkg in list(state.packages.values()):
        if pkg.in_transit and not pkg.retired and pkg.arrival_time == t and pkg.next_position:
            dest = pkg.next_position
            old_pos = pkg.position

            if random.random() < P_DAMAGE_IN_TRANSIT:
                pkg.retired = True
                pkg.forced_retirement = True
                state.retired_packages.append(pkg)
                state.repair_backlog.append({
                    'ready_day': t + int(max(1, round(np.random.normal(REPAIR_LEAD_TIME_MEAN, REPAIR_LEAD_TIME_STD)))),
                    'package_id': pkg.id,
                })
                # Damaged in transit: does NOT arrive at destination
                pkg.in_transit = False
                pkg.arrival_time = None
                pkg.next_position = None
                continue

            tc = TRANSPORT_COSTS.get((old_pos, dest), 0)
            ce = CARBON_EMISSIONS.get((old_pos, dest), 0)
            pkg.total_transport_cost += tc
            pkg.total_carbon_emissions += ce
            state.total_transport_cost += tc
            state.total_carbon_emissions += ce

            arrivals[dest] += 1
            pkg.position = dest
            pkg.in_transit = False
            pkg.arrival_time = None
            pkg.next_position = None
            pkg.path_history.append(dest)
            pkg.days_at_current_position = 0

            # Cycle increment at return pooler
            if dest == RETURN_POOLER:
                pkg.cycle_count += 1

            # Retail dwell time
            if 14 <= dest <= 19:
                dwell = int(max(1, round(np.random.normal(3 if mult > 1.5 else 2, 1))))
                pkg.hold_until_day = t + dwell

            # Quality degradation
            travel_days = DELAYS.get((old_pos, dest), 1)
            temp_dev = abs(np.random.normal(0, TEMP_DEVIATION_STD))
            pkg.quality_level *= (1 - QUALITY_DECAY_RATE * travel_days * (1 + temp_dev / 5))
            pkg.quality_level = max(0.0, pkg.quality_level)

            if not pkg.retired and random.random() < P_DAMAGE_AT_NODE:
                pkg.retired = True
                pkg.forced_retirement = True
                state.retired_packages.append(pkg)
                arrival_retirements[dest] += 1

    # ── Conservation ──────────────────────────────────────────────────────
    departures = np.zeros(NUM_NODES + 1)
    for (i, j), flow in new_flows.items():
        departures[i] += flow

    next_inv = np.copy(state.inventory) + arrivals + p_natural - departures - r_natural - r_forced - arrival_retirements
    next_inv = np.maximum(next_inv, 0)
    for i in range(1, NUM_NODES + 1):
        next_inv[i] = min(next_inv[i], NODE_CAPACITY.get(i, 200))

    state.inventory = next_inv

    # ── Holding costs ─────────────────────────────────────────────────────
    daily_holding = 0.0
    for pkg in state.packages.values():
        if not pkg.retired:
            pkg.days_at_current_position += 1
            hc = HOLDING_COSTS.get(pkg.position, 0.10)
            pkg.total_holding_cost += hc
            daily_holding += hc
    state.total_holding_cost += daily_holding

    state.daily_costs.append({
        'day': t,
        'transport_cost': sum(TRANSPORT_COSTS.get(e, 0) * f for e, f in new_flows.items()),
        'holding_cost': daily_holding,
        'production_cost': production * PRODUCTION_COST if production > 0 else 0,
        'repair_cost': refurbished * REPAIR_COST,
    })

    state.time = t
    return state


def run_simulation(days=SIMULATION_DAYS):
    state = NetworkState()
    metrics = {
        'time': [], 'active_packages': [], 'in_transit': [],
        'retired': [], 'total_produced': [], 'demand_multiplier': [],
        'node_inventory': defaultdict(list), 'unmet_demand': [],
        'avg_quality': [],
    }
    for t in range(days):
        state = simulate_step(state, t)
        active = sum(1 for p in state.packages.values() if not p.retired)
        in_transit = sum(1 for p in state.packages.values() if p.in_transit)
        retired = len(state.retired_packages)
        mult = get_potato_harvest_multiplier(t % 365)
        quals = [p.quality_level for p in state.packages.values() if not p.retired]
        avg_q = np.mean(quals) if quals else 0

        metrics['time'].append(t)
        metrics['active_packages'].append(active)
        metrics['in_transit'].append(in_transit)
        metrics['retired'].append(retired)
        metrics['total_produced'].append(state.total_produced)
        metrics['demand_multiplier'].append(mult)
        metrics['unmet_demand'].append(0)
        metrics['avg_quality'].append(avg_q)

        for node in range(1, NUM_NODES + 1):
            cnt = sum(1 for p in state.packages.values()
                      if p.position == node and not p.in_transit and not p.retired)
            metrics['node_inventory'][node].append(cnt)

    return state, metrics


def get_node_name(node_id):
    names = {
        1: "Farm-Idaho", 2: "Farm-Washington", 3: "Farm-Wisconsin",
        4: "Farm-Maine", 5: "Farm-Colorado",
        6: "Hub-West", 7: "Hub-Central", 8: "Hub-East",
        9: "National-DC",
        10: "RDC-West", 11: "RDC-South", 12: "RDC-NorthEast", 13: "RDC-Midwest",
        14: "Retail-Pacific", 15: "Retail-Southwest", 16: "Retail-Southeast",
        17: "Retail-MidAtlantic", 18: "Retail-NewEngland", 19: "Retail-Heartland",
        20: "Return-Pooler",
    }
    return names.get(node_id, f"Node-{node_id}")


def export_for_visualization(state, metrics, filename='hub_spoke_simulation_data.json'):
    node_info = {
        1: {"name": "Idaho Farms", "type": "farm", "icon": "🥔", "region": "West"},
        2: {"name": "Washington Farms", "type": "farm", "icon": "🥔", "region": "West"},
        3: {"name": "Wisconsin Farms", "type": "farm", "icon": "🥔", "region": "Central"},
        4: {"name": "Maine Farms", "type": "farm", "icon": "🥔", "region": "East"},
        5: {"name": "Colorado Farms", "type": "farm", "icon": "🥔", "region": "Central"},
        6: {"name": "Hub West (Boise)", "type": "hub", "icon": "🏭", "region": "West"},
        7: {"name": "Hub Central (Omaha)", "type": "hub", "icon": "🏭", "region": "Central"},
        8: {"name": "Hub East (Albany)", "type": "hub", "icon": "🏭", "region": "East"},
        9: {"name": "National DC (Kansas City)", "type": "national_dc", "icon": "🏢", "region": "Central"},
        10: {"name": "RDC West (LA)", "type": "rdc", "icon": "📦", "region": "West"},
        11: {"name": "RDC South (Atlanta)", "type": "rdc", "icon": "📦", "region": "South"},
        12: {"name": "RDC NorthEast (Philly)", "type": "rdc", "icon": "📦", "region": "East"},
        13: {"name": "RDC Midwest (Chicago)", "type": "rdc", "icon": "📦", "region": "Central"},
        14: {"name": "Retail Pacific", "type": "retail", "icon": "🏪", "region": "West"},
        15: {"name": "Retail Southwest", "type": "retail", "icon": "🏪", "region": "South"},
        16: {"name": "Retail Southeast", "type": "retail", "icon": "🏪", "region": "South"},
        17: {"name": "Retail Mid-Atlantic", "type": "retail", "icon": "🏪", "region": "East"},
        18: {"name": "Retail New England", "type": "retail", "icon": "🏪", "region": "East"},
        19: {"name": "Retail Heartland", "type": "retail", "icon": "🏪", "region": "Central"},
        20: {"name": "Return Pooler", "type": "pooler", "icon": "♻️", "region": "Central"},
    }

    edges = []
    for (i, j), delay in DELAYS.items():
        edges.append({
            "source": i, "target": j, "delay": delay,
            "cost": TRANSPORT_COSTS.get((i, j), 0),
            "carbon": CARBON_EMISSIONS.get((i, j), 0),
            "is_return": i >= 14 and j == 20 or i == 20,
        })

    daily_data = []
    cumT = cumH = cumP = cumR = 0
    for t in range(len(metrics['time'])):
        doy = t % 365
        season = "harvest" if 213 <= doy <= 304 else ("early" if 121 <= doy <= 212 else ("drawdown" if 305 <= doy else "storage"))
        node_inv = {str(n): metrics['node_inventory'][n][t] for n in range(1, NUM_NODES + 1)}
        flows = []
        if t in state.flows:
            for (i, j), flow in state.flows[t].items():
                if flow > 0:
                    flows.append({"source": i, "target": j, "count": int(flow)})
        dc = state.daily_costs[t] if t < len(state.daily_costs) else {}
        cumT += dc.get('transport_cost', 0)
        cumH += dc.get('holding_cost', 0)
        cumP += dc.get('production_cost', 0)
        cumR += dc.get('repair_cost', 0)
        daily_data.append({
            "day": t, "day_of_year": doy, "season": season,
            "demand_multiplier": metrics['demand_multiplier'][t],
            "active_packages": metrics['active_packages'][t],
            "in_transit": metrics['in_transit'][t],
            "retired": metrics['retired'][t],
            "total_produced": metrics['total_produced'][t],
            "avg_quality": round(metrics['avg_quality'][t], 4),
            "node_inventories": node_inv, "flows": flows,
            "transport_cost": dc.get('transport_cost', 0),
            "holding_cost": dc.get('holding_cost', 0),
            "production_cost": dc.get('production_cost', 0),
            "repair_cost": dc.get('repair_cost', 0),
            "cum_transport": round(cumT, 2), "cum_holding": round(cumH, 2),
            "cum_production": round(cumP, 2), "cum_repair": round(cumR, 2),
        })

    export_data = {
        "config": {"initial_packages": N_0, "num_nodes": NUM_NODES,
                   "simulation_days": len(metrics['time']),
                   "model_name": "Domestic US Hub-and-Spoke Cold Chain"},
        "nodes": node_info, "edges": edges, "daily_data": daily_data,
        "totals": {
            "transport_cost": state.total_transport_cost,
            "holding_cost": state.total_holding_cost,
            "production_cost": state.total_production_cost,
            "repair_cost": state.total_repair_cost,
            "carbon_emissions": state.total_carbon_emissions,
        }
    }
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    print(f"  ✓ Exported: {filename}")
    return filename


if __name__ == "__main__":
    print("=" * 70)
    print("DOMESTIC US HUB-AND-SPOKE COLD CHAIN NETWORK MODEL")
    print("=" * 70)
    random.seed(42)
    np.random.seed(42)
    print("Running simulation...")
    state, metrics = run_simulation()
    print(f"  Active: {metrics['active_packages'][-1]}")
    print(f"  Retired: {metrics['retired'][-1]}")
    print(f"  Produced: {state.total_produced}")
    print(f"  Total Cost: ${state.total_transport_cost + state.total_holding_cost + state.total_production_cost + state.total_repair_cost:,.2f}")
    print(f"  Total CO2: {state.total_carbon_emissions:,.1f} kg")
    export_for_visualization(state, metrics)
    print("Done!")
