# ODD: Reusable Transport Packaging (RTP) Supply Chain Model

## Purpose

The model simulates a closed-loop reusable transport packaging (RTP) supply chain for agricultural produce (specifically potatoes) between US production and EU retail markets. The model explores how seasonal demand patterns, stochastic delays, scheduled departures, damage/repair cycles, and economic factors affect fleet sizing, utilization, costs, and carbon emissions over a full year.

## Entities, State Variables, and Scales

### Entities
- **Packages**: Discrete reusable transport containers that circulate through the network
- **Nodes**: 16 fixed locations representing different stages of the supply chain
- **Arcs**: Directed connections between nodes with associated delays and costs

### Package State Variables
- `id`: Unique identifier
- `position`: Current node location (1-16)
- `cycle_count`: Number of complete loops through the network
- `max_cycles`: Maximum cycles before natural retirement (default: 12)
- `in_transit`: Boolean indicating if package is currently moving
- `arrival_time`: Day when package will arrive at destination
- `next_position`: Destination node for packages in transit
- `retired`: Boolean indicating if package is out of service
- `forced_retirement`: Boolean distinguishing policy-driven retirements
- `path_history`: List of all nodes visited
- `wear_accumulation`: Cumulative wear from seasonal usage
- `idle_days_at_pooler`: Days spent idle at US pooler
- `last_active_day`: Most recent day of activity
- `hold_until_day`: Day when package can leave retailer (dwell time)
- **Cost tracking**: `total_transport_cost`, `total_carbon_emissions`, `total_holding_cost`
- `days_at_current_position`: Counter for holding cost calculation

### Network State Variables
- `inventory`: Array of package counts per node
- `flows`: Dictionary of daily flows between node pairs
- `packages`: Dictionary of all active packages
- `retired_packages`: List of retired packages
- `time`: Current simulation day
- `total_produced`: Count of new packages created
- `package_id_counter`: Next available package ID
- `unmet_demand_history`: Daily unmet retailer demand
- `conservation_violations`: List of per-node conservation violations
- `repair_backlog`: List of packages undergoing repair
- **Cost tracking**: `total_transport_cost`, `total_carbon_emissions`, `total_holding_cost`, `total_production_cost`, `total_repair_cost`
- `daily_costs`: List of daily cost breakdowns

### Scales
- **Time**: 1 day per time step
- **Horizon**: 365 days (configurable)
- **Space**: 16-node directed graph network
- **Initial fleet**: 50 packages (configurable)

## Process Overview and Scheduling

### Daily Process Sequence (per time step t):

1. **Repair Processing**
   - Check repair backlog for completed repairs
   - Successful repairs create refurbished packages at US pooler
   - Reset wear and cost accumulations for refurbished packages

2. **Asset Lifecycle Management**
   - Update wear accumulation based on seasonal rates
   - Natural retirement if cycles or wear exceed limits
   - Forced retirement for idle packages at US pooler
   - Fleet optimization retirement during low demand

3. **Production Decisions**
   - Seasonal production: Top up US pooler to threshold
   - Emergency production: Ensure minimum fleet size
   - Demand-linked production: Adjust for seasonal requirements

4. **Movement Planning**
   - Build lists of packages available to move from each node
   - Apply node-specific movement rules:
     - **Export/Return ports**: Scheduled weekly departures with capacity limits
     - **EU DC**: Allocate to retailers based on daily demand caps
     - **Retailers**: Release to EU pooler after dwell time
     - **US Pooler**: Allocate to growers by seasonal proportions
     - **Other nodes**: Heuristic throughput based on demand multiplier
   - Sample stochastic delays for each movement
   - Set arrival times and next positions

5. **Arrival Processing**
   - Process packages arriving today
   - Track transport costs and carbon emissions
   - Apply damage checks (in-transit and at-node)
   - Update package positions and histories
   - Increment cycle counts at US entry port

6. **Cost Accumulation**
   - Calculate daily holding costs for all packages
   - Record daily cost breakdown (transport, holding, production, repair)
   - Update cumulative cost and emission totals

7. **Inventory Update**
   - Apply conservation equation: arrivals + production - departures - retirements = Δinventory
   - Enforce non-negativity and capacity constraints
   - Check per-node conservation balance

8. **Metrics Collection**
   - Update active, in-transit, retired counts
   - Record unmet demand
   - Track per-node inventories

## Design Concepts

### Basic Principles
- **Closed-loop circulation**: Packages continuously cycle through the network
- **Seasonal demand**: Potato seasonality drives production and movement patterns
- **Economic optimization**: Cost and carbon tracking enable policy evaluation
- **Conservation**: Package count conservation maintained throughout simulation

### Emergence
- **Fleet dynamics**: Active package counts vary seasonally
- **Port congestion**: Scheduled departures create accumulation patterns
- **Cost patterns**: Seasonal cost variations emerge from demand fluctuations
- **Carbon intensity**: Ocean freight dominates emissions profile

### Adaptation
- **Production policies**: Seasonal and emergency production adapt to demand
- **Retirement policies**: Idle and fleet optimization retirement adapt to utilization
- **No agent learning**: Packages and nodes follow fixed rules

### Objectives
- **Implicit optimization**: Minimize costs while meeting demand
- **Service level**: Satisfy retailer demand within capacity constraints
- **Sustainability**: Track carbon emissions per package-cycle

### Prediction
- **Anticipatory production**: Production threshold uses 30-day demand forecast
- **No other predictions**: Movement decisions based on current state

### Sensing
- **Package-level**: Packages track their own costs and emissions
- **System-level**: Controller uses inventory counts and demand multipliers

### Interaction
- **Shared resources**: Node capacities and arc capacities constrain flows
- **Scheduled constraints**: Weekly sailing schedules limit port departures
- **Economic feedback**: Costs influence policy decisions

### Stochasticity
- **Transport delays**: Normal distribution around base delays with disruption spikes
- **Retailer demand**: Daily demand sampling with seasonal scaling
- **Damage events**: Small probabilities of in-transit and at-node damage
- **Repair outcomes**: Stochastic repair lead times and success rates

### Collectives
- **Fleet management**: Packages managed as collective resource
- **Cost pools**: Aggregated cost and emission tracking

### Observation
- **Daily metrics**: Active, in-transit, retired counts
- **Cost analysis**: Transport, holding, production, repair costs
- **Carbon tracking**: Emissions per movement and cumulative totals
- **Conservation monitoring**: Per-node balance verification

## Initialization

- Create 50 packages at US pooler (node 1)
- Initialize empty inventories at all other nodes
- Set up adjacency matrix from defined arcs
- Initialize cost and emission totals to zero
- Set time to 0

## Input Data

### Embedded Parameters
- **Network topology**: 16 nodes with directed arcs and base delays
- **Seasonality**: Demand multipliers by day-of-year (winter: 0.5x, spring: 1.5x, summer/fall: 2.5x)
- **Costs**: Transport costs per leg ($0.50-$15.00), holding costs per node ($0.10-$0.25/day)
- **Carbon factors**: Emissions per leg (0.2-12.0 kg CO2 per package)
- **Production costs**: $25 per new package, $8 per repair
- **Scheduling**: Weekly sailing days and capacities for ports
- **Damage rates**: 1% in-transit, 0.2% at-node damage probabilities

### No External Data Required
All parameters and functions are embedded in the model code.

## Submodels

### Seasonality
- `get_potato_demand_multiplier(day)`: Returns seasonal demand multiplier
- `get_production_threshold(day)`: Calculates anticipatory production threshold
- `get_batch_size(day)`: Returns seasonal batch sizes for shipping

### Production Control
- `constraint_20_seasonal_production()`: Seasonal top-up production
- `constraint_22_emergency_production()`: Emergency production for minimum fleet
- `constraint_24_demand_linked_fleet_size()`: Fleet size adjustment

### Retirement Management
- `constraint_6_asset_lifecycle()`: Natural retirement from wear/cycles
- `constraint_23_idle_package_retirement()`: Idle-based retirement
- `constraint_26_fleet_optimization()`: Fleet optimization retirement

### Movement and Routing
- `determine_next_node()`: Route packages through network
- `is_sailing_day()`: Check if port departure is scheduled
- `sailing_capacity()`: Get port departure capacity

### Stochastic Components
- `sample_delay()`: Sample transport delays with disruptions
- `sample_retailer_dwell()`: Sample retailer dwell times
- `get_retailer_daily_demand()`: Sample daily retailer demand
- `maybe_damage_in_transit()`: Check for in-transit damage
- `maybe_damage_at_node()`: Check for at-node damage

### Cost and Carbon Tracking
- `calculate_transport_cost()`: Get transport cost for movement
- `calculate_carbon_emissions()`: Get carbon emissions for movement
- `calculate_holding_cost()`: Get daily holding cost for node
- `process_arrivals()`: Track costs and emissions for arrivals

### Conservation and Validation
- `main_conservation_equation()`: Apply conservation with arrivals/production/retirement
- `constraint_2_non_negative_inventory()`: Enforce non-negative inventories
- `constraint_4_capacity_nodes()`: Enforce node capacity limits

## Scheduling Details

### Within-Day Order
1. Process repair completions
2. Apply asset lifecycle and retirement rules
3. Calculate production needs
4. Plan departures and movements
5. Process arrivals and track costs
6. Update inventories and check conservation
7. Calculate holding costs
8. Record metrics

### Time Dependencies
- Arrivals processed after departures are planned
- No same-day arrival-departure for same leg
- Repair backlog processed before new damage events

## Outputs

### Time Series Metrics
- Active, in-transit, retired package counts
- Total produced packages
- Unmet demand per day
- Demand multiplier
- Per-node inventories

### Cost Analysis
- Daily cost breakdown (transport, holding, production, repair)
- Cumulative costs over time
- Cost per package and per cycle
- Seasonal cost analysis

### Carbon Emissions
- Daily and cumulative carbon emissions
- Emissions per package and per cycle
- Carbon intensity by transport mode

### Static Visualizations (Matplotlib)
- **seasonal_metrics.png**: Package counts with seasonal demand overlay
- **network_flow.png**: Network diagram with flow volumes
- **cost_carbon_analysis.png**: Cost and carbon breakdown charts

### Interactive Web Visualization (D3.js + Chart.js)
The model exports data to `simulation_data.json` for an interactive HTML visualization (`rtp_visualization.html`) featuring:

**Network Animation:**
- Real-time package flow visualization between nodes
- Animated ocean crossings with ship icons
- Custom pallet icons for land transport
- Interactive node tooltips with inventory details

**KPI Dashboard with Sparkline Charts:**
Each KPI displays current value, trend sparkline, target, and change indicator:

| KPI | Description | Target | Data Source |
|-----|-------------|--------|-------------|
| Total Cost of Ownership | All-in cost per package cycle | $12.00 | Cumulative costs / cycles |
| Avg Cycles per Package | Lifetime reusability metric | 12 | Package cycle counts |
| CO2 Reduction vs Disposable | Savings vs single-use | 2.5 kg | Carbon tracking |
| Package Velocity | Annual turnover rate | 5.0 cycles/yr | Annualized cycle rate |
| Loss/Shrinkage Rate | Packages lost per cycle | <2% | Retired / total |
| Asset Utilization Rate | Time in productive use | 80% | In-transit / active |
| Damage Rate | Package integrity issues | <3% | Repair costs |
| Asset Tracking Success | Location accuracy | 98% | Simulated metric |

**Time Series Charts:**
- Package counts over time (active, in-transit, retired)
- Cumulative costs by category
- Carbon emissions trajectory
- Demand multiplier pattern
- Utilization and velocity trends
- Loss and damage rate evolution

**Playback Controls:**
- Play/pause animation
- Speed control (0.5x to 10x)
- Day slider for manual navigation
- Reset to beginning

### Conservation Reports
- Per-node conservation violations
- System-wide package conservation check
- Daily cost and emission summaries

## Verification, Validation, and Testing

### Internal Checks
- **Per-node conservation**: arrivals + production - departures - retirements = Δinventory
- **Non-negative inventories**: All node inventories ≥ 0
- **Capacity constraints**: Node and arc capacities enforced
- **Package conservation**: Active + Retired = Initial + Produced

### Unit Tests
- 60-day seeded simulation with conservation assertions
- Non-negative inventory verification
- Metric completeness checks
- Cost and emission tracking validation

### Sensitivity Analysis
- Parameter variations (damage rates, costs, capacities)
- Seasonal demand pattern changes
- Production and retirement policy modifications

## Assumptions and Limitations

### Modeling Assumptions
- **Fixed network topology**: No dynamic route changes
- **Heuristic routing**: No explicit cost-based path optimization
- **Simplified batching**: Threshold-based rather than calendar-based
- **Linear cost relationships**: No economies of scale
- **Perfect information**: All costs and delays known

### Limitations
- **No market mechanisms**: No dynamic pricing or package trading
- **No multi-modal optimization**: Single transport mode per arc
- **No capacity learning**: Fixed capacities throughout simulation
- **No regional variations**: Uniform parameters across similar node types
- **No external disruptions**: Only embedded stochasticity

### Data Limitations
- **Parameter estimates**: Costs and emissions based on industry averages
- **No calibration**: Parameters not fitted to historical data
- **Simplified seasonality**: Fixed seasonal patterns rather than data-driven

## Extensions and Future Work

### Potential Enhancements
- **Multi-commodity support**: Different produce types with varying requirements
- **Dynamic pricing**: Market-driven cost optimization
- **Multi-modal transport**: Multiple transport options per arc
- **Regional variations**: Location-specific parameters
- **Data calibration**: Fit parameters to historical data
- **Service level optimization**: Explicit service level targets
- **Inventory optimization**: Economic order quantity models

### Policy Analysis Capabilities
- **Fleet sizing**: Optimal fleet size for different demand scenarios
- **Production timing**: When to produce vs repair packages
- **Retirement policies**: Optimal retirement thresholds
- **Carbon reduction**: Impact of different transport modes
- **Cost optimization**: Trade-offs between different cost components

## Usage Instructions

### Running the Simulation

```bash
# Install dependencies
pip install numpy matplotlib networkx

# Run simulation (generates all outputs)
python networkmodel.py
```

### Viewing Interactive Visualization

1. Ensure `simulation_data.json` exists (generated by simulation)
2. Open `rtp_visualization.html` in a web browser
3. Use controls to play, pause, or scrub through the simulation
4. Hover over nodes to see inventory details

### Running Tests

```bash
python -m pytest test_networkmodel.py test_network_viz.py
```


