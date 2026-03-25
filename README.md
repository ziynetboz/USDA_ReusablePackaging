# USDA_ReusablePackaging
Models and datasets generated as part of the USDA FAS Reusable Transport Packaging Digital Twins

# RTP Supply Chain Network Models

A simulation and visualization system for **Reusable Transport Packaging (RTP)** in agricultural supply chains, featuring three complementary network models.

## Overview

This project models closed-loop reusable transport packaging systems for agricultural produce (potatoes) with:
- **Three network models:** US-EU international (16 nodes), US domestic hub-and-spoke (20 nodes), and EU regional distribution with washing (18 nodes)
- **Seasonal demand patterns** reflecting potato harvest cycles and EU import seasonality
- **Cost and carbon tracking** for economic and sustainability analysis
- **Interactive web visualizations** with real-time KPI dashboards for each model
- **Cold chain quality tracking** (US hub-and-spoke) and **hygiene/washing management** (EU regional)

![RTP Supply Chain Simulation Demo](simulation_demo.gif)

## Project Structure

```
.
├── README.md                               # This file
├── ODD_RTP_Supply_Chain_Model.md           # Detailed model documentation (ODD protocol)
│
├── networkmodel.py                         # Model 1: US-EU International (16 nodes)
├── rtp_visualization.html                  # Interactive visualization for Model 1
├── simulation_data.json                    # Generated simulation output for Model 1
│
├── hub_spoke_model.py                      # Model 2: US Domestic Hub-and-Spoke (20 nodes)
├── hub_spoke_visualization.html            # Interactive visualization for Model 2
├── hub_spoke_simulation_data.json          # Generated simulation output for Model 2
│
├── eu_regional_model.py                    # Model 3: EU Regional Distribution with Washing (18 nodes)
├── eu_regional_visualization.html          # Interactive visualization for Model 3
├── eu_regional_simulation_data.json        # Generated simulation output for Model 3
│
├── test_networkmodel.py                    # Unit tests for core model
├── test_network_viz.py                     # Tests for visualization data export
└── [output files]                          # Generated charts and visualizations
    ├── seasonal_metrics.png
    ├── network_flow.png
    ├── cost_carbon_analysis.png
    └── rpa_kpis.png
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ziynetboz/USDA_ReusablePackaging.git
cd USDA_ReusablePackaging
```

### 2. Set Up Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install numpy matplotlib networkx
```

### 3. Run the Simulations

```bash
# Model 1: US-EU International Network (16 nodes)
python networkmodel.py

# Model 2: US Domestic Hub-and-Spoke Cold Chain (20 nodes)
python hub_spoke_model.py

# Model 3: EU Regional Distribution with Washing (18 nodes)
python eu_regional_model.py
```

Each model generates a JSON data file consumed by its corresponding visualization.

### 4. View the Interactive Visualizations

Start a local web server and open the visualizations in your browser:

```bash
python -m http.server 8000
```

Then open any of these in your browser:
- **http://localhost:8000/rtp_visualization.html** - US-EU International Network
- **http://localhost:8000/hub_spoke_visualization.html** - US Domestic Hub-and-Spoke
- **http://localhost:8000/eu_regional_visualization.html** - EU Regional Distribution

**Features:**
- **Animated network flow** showing packages moving between nodes
- **Real-time KPI dashboards** with sparkline trend charts
- **Playback controls** (play/pause, speed, day slider)
- **Interactive charts** for costs, carbon, utilization, and quality/hygiene metrics

Click **Play** to start the simulation and watch packages flow through the supply chain network!

## Key Performance Indicators (KPIs)

The visualization tracks 8 agri-food supply chain KPIs:

| KPI | Description | Target |
|-----|-------------|--------|
| Total Cost of Ownership | All-in cost per package cycle | $12.00 |
| Avg Cycles per Package | Lifetime reusability metric | 12 cycles |
| CO2 Reduction | Savings vs disposable packaging | 2.5 kg/cycle |
| Package Velocity | Annual turnover rate | 5.0 cycles/year |
| Loss/Shrinkage Rate | Packages lost per cycle | <2% |
| Asset Utilization | Time in productive use | 80% |
| Damage Rate | Package integrity issues | <3% |
| Asset Tracking | Real-time location accuracy | 98% |

## Model Details

### Model 1: US-EU International Network (16 nodes)

**US Region:** US Pooler, 3 US Growers, US Export Port
**Ocean Transit:** Sea Export, Sea Return
**EU Region:** EU Entry Port, EU Distribution Center, 4 EU Retailers, EU Pooler, EU Return Port, US Entry Port

**Seasonality:** Winter 0.5x, Spring 1.5x, Summer/Fall 2.5x demand

### Model 2: US Domestic Hub-and-Spoke Cold Chain (20 nodes)

**Topology:** 5 Farm regions -> 3 Regional Hubs -> 1 National DC -> 4 Regional DCs -> 6 Retail Clusters -> Return Pooler

| Layer | Nodes | Description |
|-------|-------|-------------|
| Farms (5) | Idaho, Washington, Wisconsin, Maine, Colorado | Potato growing regions |
| Regional Hubs (3) | West (Boise), Central (Omaha), East (Albany) | Consolidation hubs |
| National DC (1) | Kansas City | Central distribution |
| Regional DCs (4) | LA, Atlanta, Philadelphia, Chicago | Regional distribution |
| Retail Clusters (6) | Pacific, Southwest, Southeast, Mid-Atlantic, New England, Heartland | End markets |
| Return Pooler (1) | National | Reverse logistics hub |

**Seasonality (US potato harvest):**
- **Aug-Oct:** 2.5x (main harvest), **May-Jul:** 1.5x (early/new), **Nov-Dec:** 1.2x (drawdown), **Jan-Apr:** 0.6x (storage)

**Key features:** Cold chain quality tracking, hub consolidation batching, stochastic transit delays with disruption spikes, arc capacity enforcement via dispatch helper.

### Model 3: EU Regional Distribution with Washing (18 nodes)

**Topology:** EU Entry Ports -> Regional DCs -> Retail Regions -> Collection Points -> Washing Centers -> EU Pooler -> (recirculate or return to US)

| Layer | Nodes | Description |
|-------|-------|-------------|
| Entry Ports (2) | Rotterdam, Hamburg | Import points |
| Regional DCs (3) | North (NL/BE), Central (DE/FR), South (IT/ES) | Distribution |
| Retail Regions (5) | Benelux, Germany, France, Italy, Iberia | End markets |
| Collection Points (3) | North, Central, South | Reverse collection |
| Washing Centers (2) | North (cap: 30/day), South (cap: 25/day) | Hygiene reconditioning |
| Exit Ports (2) | Rotterdam, Hamburg | Return to US |
| EU Pooler (1) | Central | Recirculation hub |

**Seasonality (EU import demand):**
- **Nov-Mar:** 2.0x (high import), **Apr-Jun:** 1.2x (medium), **Jul-Aug:** 0.5x (low), **Sep-Oct:** 1.0x (rising)

**Key features:** Hygiene level tracking and decay, capacity-limited washing centers with lead time, duplicate wash prevention, 80/20 recirculation vs. return split, scheduled exit port departures.

### Constraints Implemented (all models)

- Flow conservation and non-negativity
- Node and arc capacity limits
- Asset lifecycle management (cycle and wear limits)
- Seasonal production and retirement policies
- Damage/repair cycles with stochastic delays
- Arc capacity enforcement via dispatch helpers (hub-spoke and EU models)

## Cost Structure

| Cost Type | US-EU Model | Hub-and-Spoke | EU Regional | Description |
|-----------|-------------|---------------|-------------|-------------|
| Transport | $0.50-$15.00/leg | $1.50-$6.00/leg | $0.50-$15.00/leg | Per package movement |
| Holding | $0.10-$0.25/day | $0.08-$0.20/day | $0.08-$0.20/day | Storage at nodes |
| Production | $25.00/pkg | $25.00/pkg | $25.00/pkg | New package creation |
| Repair | $8.00/pkg | $8.00/pkg | $8.00/pkg | Refurbishment |
| Washing | — | — | $1.50/wash | EU hygiene reconditioning |

## Carbon Emissions

| Transport Mode | Emissions |
|---------------|-----------|
| Truck (local) | 0.3-2.5 kg CO2 |
| Ocean freight | 12.0 kg CO2 |
| Port handling | 0.1-0.3 kg CO2 |

## Testing

```bash
# Run unit tests
python -m pytest test_networkmodel.py
python -m pytest test_network_viz.py
```

## Documentation

For detailed model documentation following the ODD (Overview, Design concepts, Details) protocol, see `ODD_RTP_Supply_Chain_Model.md`.

## Technologies Used

- **Python 3.8+** - Core simulation
- **NumPy** - Numerical computations
- **Matplotlib** - Static visualizations
- **NetworkX** - Graph operations
- **D3.js** - Interactive network visualization
- **Chart.js** - Dashboard charts

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions from the academic community. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this research project.

## Contact

- **Mert Canatan** - [mert.canatan@ufl.edu](mailto:mert.canatan@ufl.edu)
- **Ziynet Boz** - [ziynetboz@ufl.edu](mailto:ziynetboz@ufl.edu)

University of Florida

## Citation

If you use this model in your research, please cite our work. Citation information will be provided upon publication.
