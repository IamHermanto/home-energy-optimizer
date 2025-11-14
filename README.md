# Home Energy Optimizer

**Live Demo:** https://home-energy-optimizer.onrender.com

A prototype system for optimizing residential energy usage across solar panels, battery storage, and EV charging - built to explore technical viability of VPP (Virtual Power Plant) concepts.

## The Challenge
How can households optimize energy costs and carbon footprint when combining solar panels, battery storage, and EV charging?

## Technical Solution
- Real-time energy flow simulation
- Predictive optimization using weather and pricing data
- REST API for third-party integration
- Data pipeline for analysis and reporting

## Key Findings
- **Optimal battery sizing:** 13.5kWh for typical home
- **Cost savings:** $800-1200/year with smart scheduling
- **Grid export benefit:** $300-500/year
- **EV integration:** Reduces payback period by 30%

## Tech Stack
- **Backend:** Python, Flask, SQLite
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **Infrastructure:** Render, Gunicorn
- **Data:** Pandas, NumPy, SQL

## API Endpoints
```
GET  /api/energy/current-status     - Latest energy readings
GET  /api/energy/daily-summary      - Daily energy summary
GET  /api/energy/hourly             - Hourly data for date range
GET  /api/energy/stats              - Overall statistics
GET  /api/energy/cost-analysis      - Cost comparison & savings
GET  /api/energy/recommendations    - 24hr optimization plan
```

## Business Insight
This prototype demonstrates technical viability of household-scale VPPs. Key commercial considerations:
- **Hardware cost vs savings ROI:** 7-9 years
- **Software integration complexity:** Medium
- **Customer value proposition:** Strong in high-tariff areas

## Local Development
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Generate sample data
python backend/energy_simulator.py

# Run server
python backend/api.py
```

Visit `http://localhost:5000`

## Project Structure
```
home-energy-optimizer/
├── backend/
│   ├── api.py              # Flask REST API
│   ├── optimizer.py        # Energy optimization logic
│   ├── energy_simulator.py # Data generation
│   └── templates/
│       └── dashboard.html  # Frontend dashboard
├── requirements.txt
├── Procfile
└── README.md
```

## Features
-  Real-time energy flow visualization
-  Cost analysis (grid-only vs battery system)
-  24-hour optimization recommendations
-  Battery state tracking
-  Grid independence metrics

---

Built to demonstrate technical assessment capabilities for energy technology roles.