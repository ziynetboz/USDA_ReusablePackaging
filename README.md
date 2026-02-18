# USDA_ReusablePackaging
Models and datasets generated as part of the USDA FAS Reusable Transport Packaging Digital Twins

# RTP Supply Chain Network Model

A simulation and visualization system for **Reusable Transport Packaging (RTP)** in agricultural supply chains between US production and EU retail markets.

## Overview

This project models a closed-loop reusable transport packaging system for agricultural produce (potatoes) with:
- **16-node supply chain network** spanning US growers, ports, ocean transport, EU distribution, and retailers
- **Seasonal demand patterns** reflecting potato harvest cycles
- **Cost and carbon tracking** for economic and sustainability analysis
- **Interactive web visualization** with real-time KPI dashboards

![RTP Supply Chain Simulation Demo](simulation_demo.gif)

## Project Structure

```
.
├── README.md                           # This file
├── ODD_RTP_Supply_Chain_Model.md       # Detailed model documentation (ODD protocol)
├── networkmodel.py                     # Core simulation model
├── rtp_visualization.html              # Interactive web visualization
├── simulation_data.json                # Generated simulation output
├── test_networkmodel.py                # Unit tests for core model
├── test_network_viz.py                 # Tests for visualization data export
└── [output files]                      # Generated charts and visualizations
    ├── seasonal_metrics.png
    ├── network_flow.png
    └── cost_carbon_analysis.png
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

### 3. Run the Simulation

```bash
python networkmodel.py
```

This generates:
- `simulation_data.json` - Data for the interactive visualization
- `seasonal_metrics.png` - Package counts over time with seasonal overlay
- `network_flow.png` - Network diagram with flow volumes
- `cost_carbon_analysis.png` - Cost and carbon breakdown charts

### 4. View the Interactive Visualization

Start a local web server and open the visualization in your browser:

```bash
python -m http.server 8000
```

Then open **http://localhost:8000/rtp_visualization.html** in your browser.

**Features:**
- **Animated network flow** showing packages moving between nodes
- **Real-time KPI dashboards** with sparkline trend charts
- **Playback controls** (play/pause, speed, day slider)
- **Interactive charts** for costs, carbon, utilization, and quality metrics

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

### Network Nodes (16 total)

**US Region:**
- US Pooler (central hub)
- 3 US Growers
- US Export Port

**Ocean Transit:**
- Sea Export
- Sea Return

**EU Region:**
- EU Entry Port
- EU Distribution Center
- 4 EU Retailers
- EU Pooler
- EU Return Port
- US Entry Port

### Seasonality

The model captures potato harvest seasonality:
- **Winter (Dec-Mar):** 0.5x demand - storage/off-season
- **Spring (Apr-Jul):** 1.5x demand - early harvest
- **Summer/Fall (Aug-Nov):** 2.5x demand - main harvest

### Constraints Implemented

The model enforces 26 constraints including:
- Flow conservation and non-negativity
- Node and arc capacity limits
- Asset lifecycle management (12-cycle max)
- Scheduled port departures (weekly sailings)
- Seasonal production and retirement policies
- Damage/repair cycles with stochastic delays

## Cost Structure

| Cost Type | Range | Description |
|-----------|-------|-------------|
| Transport | $0.50-$15.00/leg | Per package movement |
| Holding | $0.10-$0.25/day | Storage at nodes |
| Production | $25.00/package | New package creation |
| Repair | $8.00/package | Refurbishment |

## Carbon Emissions

| Transport Mode | Emissions |
|---------------|-----------|
| Truck (local) | 0.6-1.0 kg CO2 |
| Ocean freight | 12.0 kg CO2 |
| Port handling | 0.2-0.3 kg CO2 |

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
