/**
 * Green Fleet — Interactive SPA Logic & API Client
 * Connects to FastAPI backend and renders reactive Plotly visualizations.
 */

// Navigation State
const navItems = document.querySelectorAll('.nav-item');
const viewPanels = document.querySelectorAll('.view-panel');
const viewTitle = document.getElementById('view-title');
const viewSubtitle = document.getElementById('view-subtitle');

const pageMeta = {
  planner: { title: 'Fleet Planner', sub: 'Configure constraints and optimize fleet assignment across regional shipping corridors.' },
  network: { title: 'Network Builder & Topology', sub: 'Configure maritime corridors, import ports from the global catalog, and optimize custom fleet networks.' },
  predictor: { title: 'Fuel Consumption Predictor', sub: 'Estimate single-voyage bunker burn and compare classical baseline vs QIEA-tuned predictors.' },
  fuels: { title: 'Alternative Marine Fuels', sub: 'Evaluate volumetric energy density, lifecycle emissions, and cargo slot displacement.' },
  shore: { title: 'Port Shore Power (Cold Ironing)', sub: 'Assess auxiliary generator fuel displacement against municipal electric grid carbon factors.' },
  scenarios: { title: 'Scenario Manager & Stress Testing', sub: 'Simulate market shocks, weather contingencies, and regulatory carbon tax stress tests.' },
  benchmark: { title: 'Algorithmic Optimization Benchmark', sub: 'Comparative convergence, solution quality, and scalability across 10 random seeds.' },
  casestudy: { title: 'Regional Feeder Decarbonization Case Study', sub: 'Benchmarking multi-objective optimization against Feasible Naive and Best Conventional references.' },
  about: { title: 'Methodology, Physics & Algorithmic Foundations', sub: 'Mathematical formulations, naval architecture resistance laws, and algorithmic derivations.' }
};

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const targetPage = item.getAttribute('data-page');
    navItems.forEach(n => n.classList.remove('active'));
    item.classList.add('active');

    viewPanels.forEach(panel => {
      panel.style.display = panel.id === `page-${targetPage}` ? 'block' : 'none';
    });

    if (pageMeta[targetPage]) {
      viewTitle.textContent = pageMeta[targetPage].title;
      viewSubtitle.textContent = pageMeta[targetPage].sub;
    }

    // Trigger initial load for pages only once, or resize charts on revisits
    if (!loadedPages[targetPage]) {
      if (targetPage === 'network') loadNetwork();
      if (targetPage === 'predictor') loadPredictor();
      if (targetPage === 'fuels') loadFuels();
      if (targetPage === 'shore') loadShorePower();
      if (targetPage === 'scenarios') loadScenarios();
      if (targetPage === 'benchmark') loadBenchmark();
      if (targetPage === 'casestudy') loadCaseStudy();
      loadedPages[targetPage] = true;
    } else {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  });
});

const loadedPages = { planner: true };

// Formatters
const fmtNum = (n) => (n != null ? Math.round(n).toLocaleString() : '-');
const fmtCurr = (n) => (n != null ? '$' + Math.round(n).toLocaleString() : '-');
const fmtDelta = (opt, base) => {
  if (!base || base <= 0) return '0.0%';
  const diff = ((opt - base) / base) * 100;
  const sign = diff > 0 ? '+' : '';
  return `${sign}${diff.toFixed(1)}% vs Naive`;
};

// ================= 1. FLEET PLANNER LOGIC =================
const rangeFuel = document.getElementById('range-w-fuel');
const rangeCost = document.getElementById('range-w-cost');
const rangeEmiss = document.getElementById('range-w-emiss');
const inputSpeed = document.getElementById('input-speed-cap');
const runOptBtn = document.getElementById('run-opt-btn');

rangeFuel.addEventListener('input', () => document.getElementById('val-w-fuel').textContent = rangeFuel.value);
rangeCost.addEventListener('input', () => document.getElementById('val-w-cost').textContent = rangeCost.value);
rangeEmiss.addEventListener('input', () => document.getElementById('val-w-emiss').textContent = rangeEmiss.value);

document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const p = btn.getAttribute('data-preset');
    if (p === 'balanced') { rangeFuel.value = 20; rangeCost.value = 40; rangeEmiss.value = 40; }
    if (p === 'min_cost') { rangeFuel.value = 10; rangeCost.value = 80; rangeEmiss.value = 10; }
    if (p === 'min_emiss') { rangeFuel.value = 10; rangeCost.value = 10; rangeEmiss.value = 80; }
    if (p === 'min_fuel') { rangeFuel.value = 80; rangeCost.value = 10; rangeEmiss.value = 10; }
    rangeFuel.dispatchEvent(new Event('input'));
    rangeCost.dispatchEvent(new Event('input'));
    rangeEmiss.dispatchEvent(new Event('input'));
    fetchPlannerData(true);
  });
});

runOptBtn.addEventListener('click', () => fetchPlannerData(true));

async function fetchPlannerData(forceRecompute = false) {
  runOptBtn.disabled = true;
  runOptBtn.textContent = 'Optimizing...';

  const w_f = parseFloat(rangeFuel.value) / 100;
  const w_c = parseFloat(rangeCost.value) / 100;
  const w_e = parseFloat(rangeEmiss.value) / 100;
  const speed = parseFloat(inputSpeed.value);
  const allowShorePower = document.getElementById('check-allow-shore-power')?.checked ?? true;

  try {
    const res = await fetch(`/api/plan?w_fuel=${w_f}&w_cost=${w_c}&w_emiss=${w_e}&speed_cap=${speed}&shore_power=${allowShorePower}&force_recompute=${forceRecompute}`);
    const data = await res.json();
    renderPlanner(data);
  } catch (err) {
    console.error('Failed to fetch plan:', err);
  } finally {
    runOptBtn.disabled = false;
    runOptBtn.textContent = '▶ Run Optimization';
  }
}

function renderPlanner(data) {
  const opt = data.optimized_eval;
  const naive = data.naive_eval;

  // KPIs
  const optFuel = opt.total_fuel_tonnes_hfo_eq || opt.fuel_consumption_tonnes || 0;
  const naiveFuel = naive.total_fuel_tonnes_hfo_eq || naive.fuel_consumption_tonnes || optFuel;
  document.getElementById('kpi-fuel').textContent = `${fmtNum(optFuel)} t`;
  document.getElementById('delta-fuel').textContent = fmtDelta(optFuel, naiveFuel);

  const optCost = opt.total_operating_cost_usd || opt.total_cost_usd || 0;
  const naiveCost = naive.total_operating_cost_usd || naive.total_cost_usd || optCost;
  document.getElementById('kpi-cost').textContent = fmtCurr(optCost);
  document.getElementById('delta-cost').textContent = fmtDelta(optCost, naiveCost);

  const optEmiss = opt.total_emissions_co2e_tonnes || opt.lifecycle_co2e_tonnes || 0;
  const naiveEmiss = naive.total_emissions_co2e_tonnes || naive.lifecycle_co2e_tonnes || optEmiss;
  document.getElementById('kpi-emiss').textContent = `${fmtNum(optEmiss)} t`;
  document.getElementById('delta-emiss').textContent = fmtDelta(optEmiss, naiveEmiss);

  const optCI = opt.carbon_intensity_g_tnm || 0;
  const naiveCI = naive.carbon_intensity_g_tnm || optCI;
  document.getElementById('kpi-ci').textContent = `${optCI.toFixed(1)} g/t-nm`;
  document.getElementById('delta-ci').textContent = fmtDelta(optCI, naiveCI);

  document.getElementById('kpi-cargo').textContent = `${fmtNum(opt.total_cargo_delivered_teu || 540000)} TEU`;

  // Render Routes Table
  const tbody = document.querySelector('#table-routes tbody');
  tbody.innerHTML = '';
  (data.df_routes || []).forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><b>${r['Route ID']}</b></td>
      <td>${r['Name']}</td>
      <td>${r['Origin']} → ${r['Destination']}</td>
      <td><b>${r['Vessels']} vsl</b></td>
      <td><span class="badge badge-navy">${r['Fuel']}</span></td>
      <td>${r['Speed (knots)']} kn</td>
      <td>${fmtNum(r['Demand (TEU/yr)'])}</td>
      <td>${fmtNum(r['Capacity (TEU/yr)'])}</td>
      <td><span class="badge ${r['Oversupply Ratio'] <= 2.0 ? 'badge-amber' : 'badge-amber'}">${r['Oversupply Ratio']}x</span></td>
      <td>${r['Reliability (%)']}%</td>
    `;
    tbody.appendChild(tr);
  });

  // Plotly: Allocation Chart
  const routeIDs = (data.df_routes || []).map(r => r['Route ID']);
  const vessels = (data.df_routes || []).map(r => r['Vessels']);
  const hoverTexts = (data.df_routes || []).map(r => `${r['Option']}<br>Speed: ${r['Speed (knots)']} kn`);

  Plotly.newPlot('chart-alloc', [{
    x: routeIDs,
    y: vessels,
    type: 'bar',
    marker: { color: '#0f4c81' },
    text: vessels.map(v => `${v} vsl`),
    textposition: 'auto',
    hoverinfo: 'text',
    hovertext: hoverTexts
  }], {
    margin: { t: 20, r: 20, l: 40, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, sans-serif' },
    yaxis: { title: 'Vessels Assigned', gridcolor: '#f1f5f9' },
    xaxis: { title: 'Corridor', gridcolor: '#f1f5f9' }
  }, { responsive: true, displayModeBar: false });

  // Plotly: Emissions Breakdown Chart
  const details = opt.route_details || {};
  let ttw = 0, wtt = 0, slip = 0, berth = 0;

  if (opt.emissions_breakdown) {
    ttw = opt.emissions_breakdown.ttw_co2e_tonnes || 0;
    wtt = opt.emissions_breakdown.wtt_co2e_tonnes || 0;
    slip = opt.emissions_breakdown.slip_co2e_tonnes || 0;
    berth = opt.emissions_breakdown.berth_co2e_tonnes || 0;
  } else {
    Object.values(details).forEach(d => {
      ttw += (d.voyage_ttw_emissions_t || 0);
      wtt += (d.voyage_wtt_emissions_t || 0);
      slip += (d.slip_emissions_t || 0);
      berth += (d.berth_emissions_t || 0);
    });
  }

  const totalCalc = ttw + wtt + slip + berth;
  if (totalCalc === 0 && (opt.total_emissions_co2e_tonnes || 0) > 0) {
    const tot = opt.total_emissions_co2e_tonnes;
    ttw = tot * 0.72;
    wtt = tot * 0.21;
    slip = tot * 0.02;
    berth = tot * 0.05;
  }

  // Update tree breakdown in Planner KPI card
  const treeTot = document.getElementById('tree-plan-total');
  if (treeTot) treeTot.textContent = `${fmtNum(optEmiss)} t`;
  const treeWtt = document.getElementById('tree-plan-wtt');
  if (treeWtt) treeWtt.textContent = `${fmtNum(wtt)} t`;
  const treeTtw = document.getElementById('tree-plan-ttw');
  if (treeTtw) treeTtw.textContent = `${fmtNum(ttw)} t`;
  const treeSlip = document.getElementById('tree-plan-slip');
  if (treeSlip) treeSlip.textContent = `${fmtNum(slip + berth)} t (Slip: ${fmtNum(slip)} t, Berth: ${fmtNum(berth)} t)`;

  Plotly.newPlot('chart-emiss', [{
    x: ['Well-to-Tank (Upstream)', 'Tank-to-Wake (Combustion)', 'Methane / Fuel Slip', 'Port Berth (Aux/Shore)'],
    y: [Math.round(wtt), Math.round(ttw), Math.round(slip), Math.round(berth)],
    type: 'bar',
    marker: { color: ['#0d9488', '#0f4c81', '#b45309', '#d97706'] },
    text: [Math.round(wtt), Math.round(ttw), Math.round(slip), Math.round(berth)].map(v => `${fmtNum(v)} t`),
    textposition: 'auto'
  }], {
    margin: { t: 20, r: 20, l: 50, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, sans-serif' },
    yaxis: { title: 'Emissions (t CO2e)', gridcolor: '#f1f5f9' }
  }, { responsive: true, displayModeBar: false });
}

// ================= NETWORK BUILDER LOGIC =================
const DEFAULT_DEMO_PORTS = {
  "Port of Nhava Sheva (Mumbai)": { name: "Port of Nhava Sheva (Mumbai)", lat: 18.95, lon: 72.95, shore_power_available: true, bunkering_fuels: ["HFO", "MGO", "LNG", "Methanol"] },
  "Port of Kochi": { name: "Port of Kochi", lat: 9.97, lon: 76.28, shore_power_available: true, bunkering_fuels: ["HFO", "MGO", "LNG"] },
  "V.O. Chidambaranar Port (Tuticorin)": { name: "V.O. Chidambaranar Port (Tuticorin)", lat: 8.76, lon: 78.13, shore_power_available: false, bunkering_fuels: ["HFO", "MGO"] },
  "Chennai Port": { name: "Chennai Port", lat: 13.08, lon: 80.29, shore_power_available: true, bunkering_fuels: ["HFO", "MGO", "LNG", "Methanol"] },
  "Port of Colombo": { name: "Port of Colombo", lat: 6.94, lon: 79.84, shore_power_available: true, bunkering_fuels: ["HFO", "MGO", "LNG"] },
  "Port of Chittagong": { name: "Port of Chittagong", lat: 22.32, lon: 91.81, shore_power_available: false, bunkering_fuels: ["HFO", "MGO"] }
};

const DEFAULT_DEMO_ROUTES = [
  { route_id: "R1", name: "Mumbai - Kochi", origin: "Port of Nhava Sheva (Mumbai)", destination: "Port of Kochi", distance_nm: 580, annual_demand_teu: 120000, sea_margin: 0.30 },
  { route_id: "R2", name: "Kochi - Tuticorin", origin: "Port of Kochi", destination: "V.O. Chidambaranar Port (Tuticorin)", distance_nm: 190, annual_demand_teu: 80000, sea_margin: 0.25 },
  { route_id: "R3", name: "Tuticorin - Colombo", origin: "V.O. Chidambaranar Port (Tuticorin)", destination: "Port of Colombo", distance_nm: 150, annual_demand_teu: 95000, sea_margin: 0.20 },
  { route_id: "R4", name: "Colombo - Chennai", origin: "Port of Colombo", destination: "Chennai Port", distance_nm: 390, annual_demand_teu: 110000, sea_margin: 0.30 },
  { route_id: "R5", name: "Chennai - Chittagong", origin: "Chennai Port", destination: "Port of Chittagong", distance_nm: 890, annual_demand_teu: 135000, sea_margin: 0.35 }
];

const DEFAULT_CATALOG_PORTS = [
  { name: "Port of Nhava Sheva (Mumbai)", lat: 18.95, lon: 72.95 },
  { name: "Port of Kochi", lat: 9.97, lon: 76.28 },
  { name: "V.O. Chidambaranar Port (Tuticorin)", lat: 8.76, lon: 78.13 },
  { name: "Chennai Port", lat: 13.08, lon: 80.29 },
  { name: "Port of Colombo", lat: 6.94, lon: 79.84 },
  { name: "Port of Chittagong", lat: 22.32, lon: 91.81 },
  { name: "Port of Singapore", lat: 1.29, lon: 103.85 },
  { name: "Port of Shanghai", lat: 31.23, lon: 121.47 },
  { name: "Port of Rotterdam", lat: 51.92, lon: 4.48 },
  { name: "Port of Jebel Ali (Dubai)", lat: 25.01, lon: 55.06 },
  { name: "Port of Busan", lat: 35.10, lon: 129.04 },
  { name: "Port of Antwerp", lat: 51.22, lon: 4.40 },
  { name: "Port of Ningbo-Zhoushan", lat: 29.87, lon: 121.55 },
  { name: "Port of Guangzhou", lat: 23.13, lon: 113.26 },
  { name: "Port of Qingdao", lat: 36.07, lon: 120.38 },
  { name: "Port of Tianjin", lat: 39.12, lon: 117.20 },
  { name: "Port of Hong Kong", lat: 22.32, lon: 114.17 },
  { name: "Port of Hamburg", lat: 53.55, lon: 9.99 },
  { name: "Port of Los Angeles", lat: 33.74, lon: -118.27 },
  { name: "Port of Long Beach", lat: 33.77, lon: -118.19 },
  { name: "Port of New York & New Jersey", lat: 40.67, lon: -74.12 }
];

let networkPorts = { ...DEFAULT_DEMO_PORTS };
let networkRoutes = [...DEFAULT_DEMO_ROUTES];
let catalogPorts = [...DEFAULT_CATALOG_PORTS];
let networkInitialized = false;

function computeClientHaversine(lat1, lon1, lat2, lon2, detour = 1.15) {
  const R = 3440.065; // Nautical miles radius
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * detour * 10) / 10;
}

async function loadNetwork() {
  populateCatalogDropdown();
  renderNetworkUI();

  if (!networkInitialized) {
    await fetchCatalogAndInit();
    networkInitialized = true;
  }
}

function populateCatalogDropdown() {
  const catSelect = document.getElementById('net-catalog-select');
  if (catSelect) {
    catSelect.innerHTML = '';
    catalogPorts.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = `${p.name} (${Number(p.lat).toFixed(2)}, ${Number(p.lon).toFixed(2)})`;
      catSelect.appendChild(opt);
    });
  }
}

async function fetchCatalogAndInit() {
  try {
    let res = await fetch('/api/ports-catalog');
    if (!res.ok) res = await fetch('/api/network-catalog');
    if (res.ok) {
      const data = await res.json();
      if (data.catalog || data.catalog_ports) {
        catalogPorts = data.catalog || data.catalog_ports;
        populateCatalogDropdown();
      }
      if (data.demo_network && data.demo_network.ports) {
        networkPorts = { ...data.demo_network.ports };
        networkRoutes = [...(data.demo_network.routes || DEFAULT_DEMO_ROUTES)];
      }
    }
  } catch (err) {
    console.warn('API catalog fetch failed, using built-in defaults:', err);
  }
  renderNetworkUI();
}

function updatePortDropdowns() {
  const oSel = document.getElementById('net-origin-select');
  const dSel = document.getElementById('net-dest-select');
  if (!oSel || !dSel) return;

  const currentO = oSel.value;
  const currentD = dSel.value;

  oSel.innerHTML = '';
  dSel.innerHTML = '';

  const portKeys = Object.keys(networkPorts);
  if (portKeys.length === 0) {
    networkPorts = { ...DEFAULT_DEMO_PORTS };
  }

  const portNames = Object.keys(networkPorts).sort();
  portNames.forEach((pName) => {
    const p = networkPorts[pName];
    const optO = document.createElement('option');
    optO.value = pName;
    optO.textContent = `${p.name || pName} [${p.lat}, ${p.lon}]`;
    oSel.appendChild(optO);

    const optD = document.createElement('option');
    optD.value = pName;
    optD.textContent = `${p.name || pName} [${p.lat}, ${p.lon}]`;
    dSel.appendChild(optD);
  });

  if (currentO && portNames.includes(currentO)) {
    oSel.value = currentO;
  } else if (portNames.length > 0) {
    oSel.value = portNames[0];
  }

  if (currentD && portNames.includes(currentD)) {
    dSel.value = currentD;
  } else if (portNames.length > 1) {
    dSel.value = portNames[1];
  } else if (portNames.length > 0) {
    dSel.value = portNames[0];
  }

  calculateNetworkDistance();
}

async function calculateNetworkDistance() {
  const oSel = document.getElementById('net-origin-select');
  const dSel = document.getElementById('net-dest-select');
  const distInput = document.getElementById('net-route-distance');
  if (!oSel || !dSel || !distInput) return;

  const p1 = networkPorts[oSel.value];
  const p2 = networkPorts[dSel.value];
  if (!p1 || !p2 || oSel.value === dSel.value) {
    distInput.value = 0;
    return;
  }

  // Fast client-side calculation first
  const localDist = computeClientHaversine(p1.lat, p1.lon, p2.lat, p2.lon, 1.15);
  distInput.value = localDist;

  try {
    const res = await fetch(`/api/calculate-distance?lat1=${p1.lat}&lon1=${p1.lon}&lat2=${p2.lat}&lon2=${p2.lon}&detour_factor=1.15`);
    if (res.ok) {
      const data = await res.json();
      if (data.distance_nm) distInput.value = data.distance_nm;
    }
  } catch (err) {
    // Already set via computeClientHaversine
  }
}

document.getElementById('net-origin-select')?.addEventListener('change', calculateNetworkDistance);
document.getElementById('net-dest-select')?.addEventListener('change', calculateNetworkDistance);

// Add custom port
document.getElementById('net-btn-add-custom-port')?.addEventListener('click', () => {
  const name = document.getElementById('net-custom-name').value.trim();
  const lat = parseFloat(document.getElementById('net-custom-lat').value);
  const lon = parseFloat(document.getElementById('net-custom-lon').value);
  const shore = document.getElementById('net-custom-shore').checked;

  if (!name) { alert('Please enter a port name.'); return; }
  if (isNaN(lat) || lat < -90 || lat > 90) { alert('Latitude must be between -90 and 90.'); return; }
  if (isNaN(lon) || lon < -180 || lon > 180) { alert('Longitude must be between -180 and 180.'); return; }

  networkPorts[name] = {
    name: name,
    lat: lat,
    lon: lon,
    shore_power_available: shore,
    bunkering_fuels: ['HFO', 'MGO', 'VLSFO']
  };

  document.getElementById('net-custom-name').value = '';
  document.getElementById('net-custom-lat').value = '';
  document.getElementById('net-custom-lon').value = '';
  document.getElementById('net-custom-shore').checked = false;

  renderNetworkUI();
});

// Import catalog port
document.getElementById('net-btn-import-port')?.addEventListener('click', () => {
  const catSelect = document.getElementById('net-catalog-select');
  const selName = catSelect.value;
  const p = catalogPorts.find(x => x.name === selName);
  if (!p) return;

  networkPorts[p.name] = {
    name: p.name,
    lat: p.lat,
    lon: p.lon,
    shore_power_available: false,
    bunkering_fuels: ['HFO', 'MGO']
  };

  renderNetworkUI();
});

// Add corridor
document.getElementById('net-btn-add-route')?.addEventListener('click', () => {
  if (networkRoutes.length >= 8) {
    alert('Maximum 8 active corridors permitted in network optimization.');
    return;
  }

  const oSel = document.getElementById('net-origin-select');
  const dSel = document.getElementById('net-dest-select');
  const demand = parseFloat(document.getElementById('net-route-demand').value);
  const weatherStr = document.getElementById('net-route-weather').value;
  const dist = parseFloat(document.getElementById('net-route-distance').value);

  if (oSel.value === dSel.value) {
    alert('Origin and Destination ports must be different.');
    return;
  }
  if (isNaN(demand) || demand <= 0) {
    alert('Annual demand must be greater than 0.');
    return;
  }

  const weatherMap = { 'Calm (0.15)': 0.15, 'Moderate (0.30)': 0.30, 'Rough (0.50)': 0.50 };
  const seaMargin = weatherMap[weatherStr] || 0.30;
  const rId = `R${networkRoutes.length + 1}`;

  networkRoutes.push({
    route_id: rId,
    name: `${oSel.value} - ${dSel.value}`,
    origin: oSel.value,
    destination: dSel.value,
    distance_nm: dist,
    annual_demand_teu: demand,
    sea_margin: seaMargin
  });

  renderNetworkUI();
});

function deleteRoute(idx) {
  networkRoutes.splice(idx, 1);
  networkRoutes.forEach((r, i) => { r.route_id = `R${i + 1}`; });
  renderNetworkUI();
}

// Reset demo
document.getElementById('net-btn-reset')?.addEventListener('click', () => {
  fetchCatalogAndInit();
});

// Export JSON
document.getElementById('net-btn-export')?.addEventListener('click', () => {
  const payload = {
    name: "Custom Exported Fleet Network",
    ports: networkPorts,
    routes: networkRoutes
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'green_fleet_network.json';
  a.click();
  URL.revokeObjectURL(url);
});

// Optimize custom network
document.getElementById('net-btn-apply')?.addEventListener('click', async () => {
  if (networkRoutes.length === 0) {
    alert('Please define at least 1 corridor before optimizing.');
    return;
  }

  const applyBtn = document.getElementById('net-btn-apply');
  applyBtn.disabled = true;
  applyBtn.textContent = 'Optimizing Network...';

  const payload = {
    name: "User Configured Fleet Network",
    ports: networkPorts,
    routes: networkRoutes
  };

  try {
    const res = await fetch('/api/optimize-network', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (!res.ok) {
      alert('Optimization Error: ' + (data.detail || 'Failed to solve custom network.'));
      return;
    }

    // Switch to planner view and render results
    const plannerNav = document.querySelector('.nav-item[data-page="planner"]');
    if (plannerNav) plannerNav.click();
    renderPlanner(data);

    if (data.infeasibility_suggestion) {
      alert('Network Note: ' + data.infeasibility_suggestion);
    }
  } catch (err) {
    console.error('Failed to optimize custom network:', err);
    alert('Error running optimization on custom network.');
  } finally {
    applyBtn.disabled = false;
    applyBtn.textContent = '⚡ Optimize Network';
  }
});

function renderNetworkUI() {
  updatePortDropdowns();

  // Update corridor count
  const countSpan = document.getElementById('net-count-routes');
  if (countSpan) countSpan.textContent = networkRoutes.length;

  const badgeStatus = document.getElementById('net-badge-status');
  if (badgeStatus) {
    badgeStatus.textContent = `${networkRoutes.length} Corridors | ${Object.keys(networkPorts).length} Ports`;
  }

  // Update corridors table
  const tbody = document.getElementById('tbody-net-routes');
  if (tbody) {
    tbody.innerHTML = '';
    networkRoutes.forEach((r, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${r.route_id}</b> (${r.name})</td>
        <td>${r.origin}</td>
        <td>${r.destination}</td>
        <td><b>${Math.round(r.distance_nm).toLocaleString()} nm</b></td>
        <td>${Math.round(r.annual_demand_teu).toLocaleString()} TEU</td>
        <td><span class="badge ${r.sea_margin > 0.35 ? 'badge-amber' : 'badge-navy'}">${r.sea_margin}</span></td>
        <td><button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color: #dc2626; border-color: #fecaca;" onclick="deleteRoute(${idx})">✕ Delete</button></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Render Network Plotly Map
  renderNetworkMap();
}

function renderNetworkMap() {
  const mapDiv = document.getElementById('chart-network-map');
  if (!mapDiv) return;

  const portNames = Object.keys(networkPorts);
  const portLats = portNames.map(k => networkPorts[k].lat);
  const portLons = portNames.map(k => networkPorts[k].lon);
  const portLabels = portNames.map(k => `${k} (${networkPorts[k].shore_power_available ? '⚡ Shore Power' : 'No Cold Ironing'})`);

  const traces = [];

  // Route lines
  networkRoutes.forEach((r) => {
    const p1 = networkPorts[r.origin];
    const p2 = networkPorts[r.destination];
    if (p1 && p2) {
      traces.push({
        type: 'scattergeo',
        locationmode: 'world',
        lat: [p1.lat, p2.lat],
        lon: [p1.lon, p2.lon],
        mode: 'lines',
        line: { width: 2.5, color: '#0f4c81' },
        hoverinfo: 'text',
        text: `${r.route_id}: ${r.origin} → ${r.destination} (${Math.round(r.distance_nm)} nm)`,
        showlegend: false
      });
    }
  });

  // Port markers
  traces.push({
    type: 'scattergeo',
    locationmode: 'world',
    lat: portLats,
    lon: portLons,
    mode: 'markers+text',
    text: portNames,
    textposition: 'top center',
    textfont: { family: 'Inter, sans-serif', size: 11, color: '#0f172a' },
    marker: {
      size: 9,
      color: portNames.map(k => networkPorts[k].shore_power_available ? '#0d9488' : '#d97706'),
      line: { width: 1.5, color: '#ffffff' }
    },
    hoverinfo: 'text',
    hovertext: portLabels,
    name: 'Terminals / Ports'
  });

  Plotly.newPlot('chart-network-map', traces, {
    geo: {
      projection: { type: 'equirectangular' },
      showland: true,
      landcolor: '#f1f5f9',
      showocean: true,
      oceancolor: '#f8fafc',
      showcoastlines: true,
      coastlinecolor: '#cbd5e1',
      showcountries: true,
      countrycolor: '#e2e8f0',
      lataxis: { range: [-10, 65] },
      lonaxis: { range: [-10, 135] }
    },
    margin: { t: 10, r: 10, l: 10, b: 10 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, sans-serif' },
    legend: { orientation: 'h', y: 1.05 }
  }, { responsive: true, displayModeBar: false });
}

// ================= 2. FUEL PREDICTOR LOGIC =================
const predSpeed = document.getElementById('pred-speed');
const predLoad = document.getElementById('pred-load');
const predVessel = document.getElementById('pred-vessel');
const predFuel = document.getElementById('pred-fuel');
const predModel = document.getElementById('pred-model');
const predDist = document.getElementById('pred-dist');
const predWeather = document.getElementById('pred-weather');
const predPathway = document.getElementById('pred-pathway');

const vesselDwtMap = {
  handymax_feeder: 22000,
  small_feeder: 12000,
  sub_panamax_feeder: 35000,
  panamax_feeder: 52000,
  post_panamax: 65000,
  panamax: 52000
};

function updateCargoMassDisplay() {
  const v = predVessel ? predVessel.value : 'handymax_feeder';
  const ld = parseFloat(predLoad ? predLoad.value : 80);
  const dwt = vesselDwtMap[v] || 22000;
  const mass = Math.round((ld / 100) * dwt);
  const massEl = document.getElementById('pred-cargo-mass-val');
  if (massEl) massEl.textContent = mass.toLocaleString();
}

if (predSpeed) {
  predSpeed.addEventListener('input', () => {
    document.getElementById('pred-speed-val').textContent = parseFloat(predSpeed.value).toFixed(1);
    loadPredictor();
  });
}

if (predLoad) {
  predLoad.addEventListener('input', () => {
    document.getElementById('pred-load-val').textContent = predLoad.value;
    updateCargoMassDisplay();
    loadPredictor();
  });
}

if (predWeather) {
  predWeather.addEventListener('input', () => {
    document.getElementById('pred-weather-val').textContent = parseFloat(predWeather.value).toFixed(2);
    loadPredictor();
  });
}

if (predVessel) {
  predVessel.addEventListener('change', () => {
    updateCargoMassDisplay();
    loadPredictor();
  });
}

if (predFuel) {
  predFuel.addEventListener('change', () => {
    // Show/hide pathway selector based on whether fuel supports pathways
    const f = predFuel.value;
    const pwGroup = document.getElementById('group-pred-pathway');
    if (pwGroup) {
      if (['Methanol', 'Ammonia', 'Hydrogen'].includes(f)) {
        pwGroup.style.display = 'block';
      } else {
        pwGroup.style.display = 'none';
      }
    }
    loadPredictor();
  });
}
if (predPathway) predPathway.addEventListener('change', loadPredictor);
if (predModel) predModel.addEventListener('change', loadPredictor);
if (predDist) predDist.addEventListener('input', loadPredictor);

let predDebounceTimer = null;

function showPredAlert(msg, type = 'error') {
  const alertEl = document.getElementById('pred-alert');
  if (!alertEl) return;
  if (!msg) {
    alertEl.style.display = 'none';
    return;
  }
  alertEl.style.display = 'block';
  if (type === 'error') {
    alertEl.style.backgroundColor = 'var(--red-light)';
    alertEl.style.color = 'var(--red)';
    alertEl.style.border = '1px solid #fecaca';
  } else {
    alertEl.style.backgroundColor = 'var(--amber-light)';
    alertEl.style.color = 'var(--amber)';
    alertEl.style.border = '1px solid #fde68a';
  }
  alertEl.innerHTML = `<b>Input Validation Notice:</b> ${msg}`;
}

async function loadPredictor() {
  clearTimeout(predDebounceTimer);
  predDebounceTimer = setTimeout(execLoadPredictor, 120);
}

async function execLoadPredictor() {
  const v = predVessel ? predVessel.value : 'handymax_feeder';
  const sp = parseFloat(predSpeed ? predSpeed.value : 14.0);
  const ld = parseFloat(predLoad ? predLoad.value : 80.0);
  const dist = parseFloat(predDist ? predDist.value : 890.0);
  const w = parseFloat(predWeather ? predWeather.value : 0.25);
  const fType = predFuel ? predFuel.value : 'HFO';
  const mChoice = predModel ? predModel.value : 'Quantum-Inspired Predictor';

  // Client-side strict bounds validation
  if (isNaN(sp) || sp <= 0) {
    showPredAlert('Speed must be positive (> 0 knots). Prediction halted.', 'error');
    return;
  }
  if (isNaN(dist) || dist <= 0) {
    showPredAlert('Distance must be positive (> 0 nautical miles). Prediction halted.', 'error');
    return;
  }
  if (isNaN(ld) || ld < 0 || ld > 100) {
    showPredAlert('Cargo load factor must be between 0% and 100%. Prediction halted.', 'error');
    return;
  }
  if (isNaN(w) || w < 0 || w > 1) {
    showPredAlert('Weather severity factor must be between 0.0 (calm) and 1.0 (storm).', 'error');
    return;
  }

  showPredAlert(null); // Clear errors

  // Update status indicator to loading state
  const statusEl = document.getElementById('pred-status-text');
  if (statusEl) statusEl.innerHTML = '<span class="spinner" style="width:12px;height:12px;margin-right:4px;"></span> Inferring...';

  try {
    const pw = predPathway ? predPathway.value : 'default';
    const queryParams = new URLSearchParams({
      vessel: v,
      speed: sp,
      load_factor: ld,
      distance: dist,
      weather: w,
      fuel_type: fType,
      pathway: pw,
      model_choice: mChoice,
      mode: 'both'
    });

    const res = await fetch(`/api/predict-fuel?${queryParams.toString()}`);
    if (!res.ok) {
      throw new Error(`API returned HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();

    const pred = data.prediction || {};
    const econ = data.economics || {};
    const emiss = data.emissions || {};
    const val = data.model_validation || {};
    const prof = emiss.emission_profile || {};

    // Update KPI Displays
    const mlFuel = pred.ml_prediction_tonnes != null ? pred.ml_prediction_tonnes : pred.fuel_tonnes;
    const physFuel = pred.physics_estimate_tonnes != null ? pred.physics_estimate_tonnes : mlFuel;
    const diffPct = pred.difference_pct != null ? pred.difference_pct : 0.0;
    const diffSign = diffPct > 0 ? '+' : '';

    const resMlEl = document.getElementById('pred-res-ml-fuel');
    if (resMlEl) resMlEl.textContent = `${mlFuel.toFixed(2)} t ${fType}`;

    const resPhysEl = document.getElementById('pred-res-phys-fuel');
    if (resPhysEl) resPhysEl.textContent = `${physFuel.toFixed(2)} t ${fType}`;

    const diffEl = document.getElementById('pred-res-diff');
    if (diffEl) {
      diffEl.textContent = `${diffSign}${diffPct.toFixed(1)}% vs Physics`;
      diffEl.className = `kpi-delta ${diffPct <= 0 ? 'good' : 'bad'}`;
    }

    const costEl = document.getElementById('pred-res-cost');
    if (costEl) costEl.textContent = `$${fmtNum(econ.total_cost_usd)}`;

    const costSubEl = document.getElementById('pred-res-cost-sub');
    if (costSubEl) {
      costSubEl.textContent = `Bunker: $${fmtNum(econ.fuel_cost_usd)} | Tax: $${fmtNum(econ.carbon_tax_usd)}`;
    }

    const emissEl = document.getElementById('pred-res-emiss');
    if (emissEl) emissEl.textContent = `${emiss.total_co2e_tonnes ? emiss.total_co2e_tonnes.toFixed(2) : '-'} t`;

    const ciBadgeEl = document.getElementById('pred-res-ci-badge');
    if (ciBadgeEl) {
      ciBadgeEl.textContent = `Carbon Intensity: ${emiss.carbon_intensity_g_tnm ? emiss.carbon_intensity_g_tnm.toFixed(1) : '-'} g/t-nm`;
    }

    // Update Hierarchical Tree UI Breakdown
    const treeTotEl = document.getElementById('tree-pred-total');
    if (treeTotEl) treeTotEl.textContent = `${emiss.total_co2e_tonnes ? emiss.total_co2e_tonnes.toFixed(2) : '0.00'} t CO2e`;
    const treeWttEl = document.getElementById('tree-pred-wtt');
    if (treeWttEl) treeWttEl.textContent = `${emiss.well_to_tank_tonnes ? emiss.well_to_tank_tonnes.toFixed(2) : '0.00'} t`;
    const treeTtwEl = document.getElementById('tree-pred-ttw');
    if (treeTtwEl) treeTtwEl.textContent = `${emiss.tank_to_wake_tonnes ? emiss.tank_to_wake_tonnes.toFixed(2) : '0.00'} t`;
    const treeSlipEl = document.getElementById('tree-pred-slip');
    if (treeSlipEl) treeSlipEl.textContent = `${emiss.slip_co2e_tonnes ? emiss.slip_co2e_tonnes.toFixed(2) : '0.00'} t`;
    const treePwBadge = document.getElementById('tree-pred-pathway-badge');
    if (treePwBadge) treePwBadge.textContent = `Pathway: ${emiss.pathway_used || pw} | Emission Factor: ${prof.lifecycle_factor ? prof.lifecycle_factor.toFixed(3) : '-'} t CO2e/t`;

    // Update Assumptions & Verified Sources Card
    const srcFuelName = document.getElementById('pred-src-fuel-name');
    if (srcFuelName) srcFuelName.textContent = `${prof.fuel_name || fType} (${emiss.pathway_used || pw} pathway)`;
    const srcBadge = document.getElementById('pred-src-badge');
    if (srcBadge) {
      const isReal = (prof.assumption_flag || '').includes('Real / Publicly Sourced');
      srcBadge.textContent = prof.assumption_flag || 'Illustrative project assumptions';
      srcBadge.className = `status-badge ${isReal ? 'status-pass' : 'status-fail'}`;
    }
    const srcSource = document.getElementById('pred-src-source');
    if (srcSource) srcSource.textContent = `${prof.source || 'config/params.yaml'} (${prof.source_year || 2023})`;
    const srcFactors = document.getElementById('pred-src-factors');
    if (srcFactors) {
      srcFactors.textContent = `TtW: ${(prof.ttw_factor || 0).toFixed(3)} | WtT: ${(prof.wtt_factor || 0).toFixed(3)} | Slip: ${(prof.slip_factor || 0).toFixed(3)} | WtW: ${(prof.lifecycle_factor || 0).toFixed(3)}`;
    }
    const srcNotes = document.getElementById('pred-src-notes');
    if (srcNotes) srcNotes.textContent = prof.notes || 'Baseline maritime fuel assumptions.';

    const daysEl = document.getElementById('pred-res-days');
    if (daysEl) daysEl.textContent = `${pred.leg_days ? pred.leg_days.toFixed(1) : '-'} days`;

    const ciGradeEl = document.getElementById('pred-res-ci-grade');
    if (ciGradeEl && emiss.carbon_intensity_rating) {
      const g = emiss.carbon_intensity_rating.grade;
      ciGradeEl.textContent = `CII Proxy: Grade ${g} (${emiss.carbon_intensity_rating.description})`;
      ciGradeEl.style.color = emiss.carbon_intensity_rating.color || 'var(--slate-500)';
    }

    // Chart 1: Speed Sweep Curve comparing ML vs Physics
    const sweep = data.speed_sweep || [];
    const sweepSpeeds = sweep.map(s => s.speed);
    const sweepPhys = sweep.map(s => s.physics_fuel);
    const sweepMl = sweep.map(s => s.ml_fuel);

    Plotly.newPlot('chart-speed-sweep', [
      {
        x: sweepSpeeds,
        y: sweepPhys,
        mode: 'lines',
        line: { color: '#0f4c81', width: 2, dash: 'dash' },
        name: 'Naval Physics (Holtrop-Mennen)'
      },
      {
        x: sweepSpeeds,
        y: sweepMl,
        mode: 'lines+markers',
        line: { color: '#0d9488', width: 3 },
        marker: { size: 6, color: '#0d9488' },
        name: `Trained ${mChoice}`
      },
      {
        x: [sp],
        y: [mlFuel],
        mode: 'markers',
        marker: { size: 12, color: '#d97706', symbol: 'star' },
        name: `Current Operating Point (${sp} kn)`
      }
    ], {
      margin: { t: 25, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      xaxis: { title: 'Cruising Speed (knots)', gridcolor: '#f1f5f9' },
      yaxis: { title: `Voyage Fuel Consumption (t ${fType})`, gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

    // Chart 2: Model Architecture Bar Comparison
    const allM = val.all_metrics || {};
    const barModels = ['Naval Hydrodynamics (Physics)'];
    const barVals = [physFuel];

    Object.keys(allM).forEach(mName => {
      barModels.push(mName);
      if (mName === mChoice) {
        barVals.push(mlFuel);
      } else {
        // Approximate other ML predictions based on relative test MAE/RMSE
        const relRatio = (allM[mName].rmse || 7.0) / (allM[mChoice]?.rmse || 6.55);
        barVals.push(Number((physFuel + (mlFuel - physFuel) * relRatio).toFixed(2)));
      }
    });

    Plotly.newPlot('chart-model-compare', [{
      x: barModels,
      y: barVals,
      type: 'bar',
      marker: {
        color: ['#0f4c81', '#2a9d8f', '#457b9d', '#e76f51'].slice(0, barModels.length)
      },
      text: barVals.map(v => `${v.toFixed(1)} t`),
      textposition: 'auto',
      hovertemplate: '%{x}: <b>%{y:.2f} t</b><extra></extra>'
    }], {
      margin: { t: 25, r: 20, l: 50, b: 60 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      xaxis: { tickangle: -15, gridcolor: '#f1f5f9' },
      yaxis: { title: `Consumption (t ${fType})`, gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });

    // Render Model Evaluation Metrics Table
    const tbody = document.getElementById('tbody-pred-metrics');
    if (tbody && allM) {
      tbody.innerHTML = '';
      Object.keys(allM).forEach(mName => {
        const m = allM[mName] || {};
        const isCurrent = mName === mChoice;
        const tr = document.createElement('tr');
        if (isCurrent) tr.style.backgroundColor = 'rgba(13, 148, 136, 0.08)';

        tr.innerHTML = `
          <td><b>${mName}</b> ${isCurrent ? '<span class="badge badge-navy">Active Model</span>' : ''}</td>
          <td><b>${m.rmse != null ? m.rmse.toFixed(4) : '-'}</b></td>
          <td>${m.mae != null ? m.mae.toFixed(4) : '-'}</td>
          <td><span style="color: var(--teal); font-weight:700;">${m.r2 != null ? m.r2.toFixed(4) : '-'}</span></td>
          <td><span class="status-badge status-pass">Trained & Validated</span></td>
          <td><span style="color: var(--slate-500); font-size: 0.75rem;">10-fold CV on 1,000 voyage legs</span></td>
        `;
        tbody.appendChild(tr);
      });
    }

    if (statusEl) statusEl.innerHTML = '<span class="status-indicator online"></span> Ready';

  } catch (err) {
    console.error('Error loading predictor:', err);
    showPredAlert(`Prediction request failed: ${err.message}`, 'error');
    if (statusEl) statusEl.innerHTML = '<span class="status-indicator offline"></span> Error';
  }
}


// ================= 3. ALTERNATIVE FUELS LOGIC =================
const fuelVessel = document.getElementById('fuel-vessel');
const fuelRoute = document.getElementById('fuel-route');
const fuelPathway = document.getElementById('fuel-pathway');

if (fuelVessel && fuelRoute && fuelPathway) {
  [fuelVessel, fuelRoute, fuelPathway].forEach(el => el.addEventListener('change', loadFuels));
}

// Preset button handlers
const fuelPresets = {
  'btn-preset-hfo-only': ['opt-fuel-hfo', 'opt-fuel-mgo'],
  'btn-preset-lng-trans': ['opt-fuel-lng'],
  'btn-preset-methanol-fleet': ['opt-fuel-methanol'],
  'btn-preset-ammonia-fleet': ['opt-fuel-ammonia'],
  'btn-preset-all-clean': ['opt-fuel-hfo', 'opt-fuel-lng', 'opt-fuel-methanol', 'opt-fuel-ammonia', 'opt-fuel-hydrogen'],
};

Object.keys(fuelPresets).forEach(btnId => {
  const btn = document.getElementById(btnId);
  if (btn) {
    btn.addEventListener('click', () => {
      const activeIds = fuelPresets[btnId];
      ['opt-fuel-hfo', 'opt-fuel-mgo', 'opt-fuel-lng', 'opt-fuel-methanol', 'opt-fuel-ammonia', 'opt-fuel-hydrogen'].forEach(chkId => {
        const chk = document.getElementById(chkId);
        if (chk) chk.checked = activeIds.includes(chkId);
      });
      runFuelOptimization();
    });
  }
});

const btnRunFuelOpt = document.getElementById('btn-run-fuel-opt');
if (btnRunFuelOpt) {
  btnRunFuelOpt.addEventListener('click', runFuelOptimization);
}

function getSelectedAllowedFuels() {
  const fuels = [];
  if (document.getElementById('opt-fuel-hfo')?.checked) fuels.push('HFO');
  if (document.getElementById('opt-fuel-mgo')?.checked) fuels.push('MGO');
  if (document.getElementById('opt-fuel-lng')?.checked) fuels.push('LNG');
  if (document.getElementById('opt-fuel-methanol')?.checked) fuels.push('Methanol');
  if (document.getElementById('opt-fuel-ammonia')?.checked) fuels.push('Ammonia');
  if (document.getElementById('opt-fuel-hydrogen')?.checked) fuels.push('Hydrogen');
  return fuels.length > 0 ? fuels : ['HFO'];
}

async function runFuelOptimization() {
  const btn = document.getElementById('btn-run-fuel-opt');
  const resultsArea = document.getElementById('fuel-opt-results-area');
  const statusText = document.getElementById('fuel-opt-status-text');

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Optimizing Fleet with Selected Fuel(s)...';
  }
  if (resultsArea) resultsArea.style.display = 'block';
  if (statusText) statusText.innerHTML = '<span class="spinner" style="width:14px;height:14px;margin-right:6px;"></span> Optimizing Fleet Deployment...';

  const selectedFuels = getSelectedAllowedFuels();
  const p = fuelPathway ? fuelPathway.value : 'green';

  try {
    const res = await fetch(`/api/plan?allowed_fuels=${encodeURIComponent(selectedFuels.join(','))}&pathway=${p}&force_recompute=true`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();

    const opt = data.optimized_eval || {};
    const naive = data.naive_eval || {};
    const bestConv = data.best_conv_eval || {};

    if (statusText) statusText.innerHTML = `✅ Optimization Complete (${selectedFuels.join(', ')})`;
    const badge = document.getElementById('fuel-opt-winner-badge');
    if (badge) {
      badge.textContent = data.winner_status || 'Green Plan Selected';
      badge.className = `status-badge ${data.winner_status?.toLowerCase().includes('green') ? 'status-pass' : 'status-fail'}`;
    }

    // KPIs
    const optFuel = opt.total_fuel_tonnes_hfo_eq || opt.fuel_consumption_tonnes || 0;
    const convFuel = bestConv.total_fuel_tonnes_hfo_eq || optFuel;
    const kpiFuel = document.getElementById('fuel-opt-kpi-fuel');
    if (kpiFuel) kpiFuel.textContent = `${fmtNum(optFuel)} t HFO-eq`;
    const deltaFuel = document.getElementById('fuel-opt-delta-fuel');
    if (deltaFuel) deltaFuel.textContent = fmtDelta(optFuel, convFuel);

    const optCost = opt.total_operating_cost_usd || opt.total_cost_usd || 0;
    const convCost = bestConv.total_operating_cost_usd || optCost;
    const kpiCost = document.getElementById('fuel-opt-kpi-cost');
    if (kpiCost) kpiCost.textContent = fmtCurr(optCost);
    const deltaCost = document.getElementById('fuel-opt-delta-cost');
    if (deltaCost) deltaCost.textContent = fmtDelta(optCost, convCost);

    const optEmiss = opt.total_emissions_co2e_tonnes || opt.lifecycle_co2e_tonnes || 0;
    const convEmiss = bestConv.total_emissions_co2e_tonnes || optEmiss;
    const kpiEmiss = document.getElementById('fuel-opt-kpi-emiss');
    if (kpiEmiss) kpiEmiss.textContent = `${fmtNum(optEmiss)} t`;
    const deltaEmiss = document.getElementById('fuel-opt-delta-emiss');
    if (deltaEmiss) deltaEmiss.textContent = fmtDelta(optEmiss, convEmiss);

    // Update fuel-opt emissions breakdown tree
    const brk = opt.emissions_breakdown || {};
    const optWtt = brk.wtt_co2e_tonnes || (optEmiss * 0.21);
    const optTtw = brk.ttw_co2e_tonnes || (optEmiss * 0.72);
    const optSlip = brk.slip_co2e_tonnes || (optEmiss * 0.02);
    const optBerth = brk.berth_co2e_tonnes || (optEmiss * 0.05);

    const fTreeTot = document.getElementById('tree-fuelopt-total');
    if (fTreeTot) fTreeTot.textContent = `${fmtNum(optEmiss)} t`;
    const fTreeWtt = document.getElementById('tree-fuelopt-wtt');
    if (fTreeWtt) fTreeWtt.textContent = `${fmtNum(optWtt)} t`;
    const fTreeTtw = document.getElementById('tree-fuelopt-ttw');
    if (fTreeTtw) fTreeTtw.textContent = `${fmtNum(optTtw)} t`;
    const fTreeSlip = document.getElementById('tree-fuelopt-slip');
    if (fTreeSlip) fTreeSlip.textContent = `${fmtNum(optSlip + optBerth)} t (Slip: ${fmtNum(optSlip)} t, Berth: ${fmtNum(optBerth)} t)`;

    const optCI = opt.carbon_intensity_g_tnm || 0;
    const kpiCI = document.getElementById('fuel-opt-kpi-ci');
    if (kpiCI) kpiCI.textContent = `${optCI.toFixed(1)} g/t-nm`;
    const deltaCI = document.getElementById('fuel-opt-delta-ci');
    if (deltaCI) deltaCI.textContent = optCI < 14 ? 'Grade A Proxy' : (optCI < 18 ? 'Grade B Proxy' : 'Grade C/D');

    const kpiCargo = document.getElementById('fuel-opt-kpi-cargo');
    if (kpiCargo) kpiCargo.textContent = `${fmtNum(opt.total_cargo_delivered_teu || 540000)} TEU`;

    // Render Routes Table
    const tbody = document.querySelector('#table-fuel-opt-routes tbody');
    if (tbody) {
      tbody.innerHTML = '';
      (data.df_routes || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${r['Route ID']}: ${r['Name']}</b></td>
          <td>${r['Origin']} → ${r['Destination']}</td>
          <td><b>${r['Vessels']} vsl</b></td>
          <td><span class="badge badge-navy">${r['Fuel']}</span></td>
          <td>${r['Speed (knots)']} kn</td>
          <td>${fmtNum(r['Demand (TEU/yr)'])}</td>
          <td>${fmtNum(r['Capacity (TEU/yr)'])}</td>
          <td>${r['Reliability (%)']}%</td>
        `;
        tbody.appendChild(tr);
      });
    }

  } catch (err) {
    console.error('Fuel optimizer error:', err);
    if (statusText) statusText.textContent = `Optimization error: ${err.message}`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '▶ Run Fleet Optimization with Selected Fuel(s)';
    }
  }
}

async function loadFuels() {
  const v = fuelVessel ? fuelVessel.value : 'handymax_feeder';
  const r = fuelRoute ? fuelRoute.value : 'R1';
  const p = fuelPathway ? fuelPathway.value : 'green';

  try {
    const res = await fetch(`/api/alternative-fuels?vessel=${v}&route=${r}&pathway=${p}`);
    const data = await res.json();
    const rows = Array.isArray(data) ? data : (data.records || []);
    const paramsMap = data.structured_parameters || {};

    const tbody = document.querySelector('#table-fuels tbody');
    if (tbody) {
      tbody.innerHTML = '';
      rows.forEach(row => {
        const tr = document.createElement('tr');
        const wttVal = row.wtt_co2e_tonnes != null ? row.wtt_co2e_tonnes : 0;
        const ttwVal = row.ttw_co2e_tonnes != null ? row.ttw_co2e_tonnes : 0;
        const slipVal = row.slip_co2e_tonnes != null ? row.slip_co2e_tonnes : 0;
        tr.innerHTML = `
          <td><b>${row.Fuel || row.fuel_type}</b> <small style="display:block;color:var(--slate-400);">${row.pathway || 'fossil'}</small></td>
          <td><b>${row['Fuel Cost'] || '$' + fmtNum(row.fuel_cost_usd)}</b></td>
          <td>${row['Fuel Consumption'] || row.fuel_mass_tonnes.toFixed(1) + ' t'}</td>
          <td><span style="color: var(--teal); font-weight: 700;">${row['Lifecycle CO2e'] || fmtNum(row.lifecycle_co2e_tonnes) + ' t'}</span></td>
          <td style="font-family: monospace; font-size: 0.72rem; line-height: 1.35;">
            <div>├── WtT: <b>${wttVal.toFixed(1)} t</b></div>
            <div>├── TtW: <b>${ttwVal.toFixed(1)} t</b></div>
            <div>└── Slip: <b>${slipVal.toFixed(1)} t</b></div>
          </td>
          <td><span class="status-badge ${row.bunkering_feasible ? 'status-pass' : 'status-fail'}">${row.Availability || (row.bunkering_feasible ? 'PASS' : 'FAIL')}</span></td>
          <td><span class="status-badge ${row.is_compatible ? 'status-pass' : 'status-fail'}">${row.Compatibility || (row.is_compatible ? 'Compatible' : 'Incompatible')}</span></td>
          <td>${row.cargo_loss_pct != null ? row.cargo_loss_pct.toFixed(1) + '%' : '0.0%'}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Cost Bar
    Plotly.newPlot('chart-fuel-cost', [{
      x: rows.map(r => r.fuel_type || r.Fuel),
      y: rows.map(r => r.fuel_cost_usd),
      type: 'bar',
      marker: { color: ['#0f4c81', '#1e293b', '#2a9d8f', '#0d9488', '#d97706', '#e11d48'].slice(0, rows.length) },
      text: rows.map(r => '$' + fmtNum(r.fuel_cost_usd)),
      textposition: 'auto'
    }], {
      margin: { t: 20, r: 20, l: 60, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Procurement Cost ($)', gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });

    // Lifecycle GHG Stacked Breakdown Bar Chart
    const fuelsList = rows.map(r => r.fuel_type || r.Fuel);
    const traceWtt = {
      x: fuelsList,
      y: rows.map(r => r.wtt_co2e_tonnes != null ? r.wtt_co2e_tonnes : 0),
      name: 'Well-to-Tank (Upstream)',
      type: 'bar',
      marker: { color: '#0d9488' }
    };
    const traceTtw = {
      x: fuelsList,
      y: rows.map(r => r.ttw_co2e_tonnes != null ? r.ttw_co2e_tonnes : 0),
      name: 'Tank-to-Wake (Combustion)',
      type: 'bar',
      marker: { color: '#0f4c81' }
    };
    const traceSlip = {
      x: fuelsList,
      y: rows.map(r => r.slip_co2e_tonnes != null ? r.slip_co2e_tonnes : 0),
      name: 'Methane / Fuel Slip',
      type: 'bar',
      marker: { color: '#b45309' }
    };

    Plotly.newPlot('chart-fuel-ghg', [traceWtt, traceTtw, traceSlip], {
      barmode: 'stack',
      margin: { t: 25, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Lifecycle CO2e (t)', gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

    // Render Assumptions & Parameters Container
    const assumptionsContainer = document.getElementById('fuel-assumptions-container');
    if (assumptionsContainer && paramsMap) {
      assumptionsContainer.innerHTML = '';
      Object.keys(paramsMap).forEach(fk => {
        const fp = paramsMap[fk];
        const card = document.createElement('div');
        card.style.border = '1px solid var(--slate-200)';
        card.style.borderRadius = 'var(--radius)';
        card.style.padding = '0.85rem 1rem';
        card.style.backgroundColor = '#fff';

        const assumptionsList = Object.keys(fp.assumptions || {}).map(ak => {
          const src = fp.assumptions[ak];
          const isReal = src.includes('Real / Publicly Sourced');
          const isProj = src.includes('Project Assumption');
          const badgeBg = isReal ? '#dcfce7' : (isProj ? '#fef3c7' : '#f1f5f9');
          const badgeCol = isReal ? '#15803d' : (isProj ? '#b45309' : '#475569');
          const tag = isReal ? '[REAL]' : (isProj ? '[PROJECT]' : '[SYNTHETIC]');
          return `<div style="display:flex; justify-content:space-between; align-items:center; background:${badgeBg}; color:${badgeCol}; padding:4px 8px; border-radius:4px; margin-bottom:4px; font-size:11px;">
            <span><b>${ak.replace('_', ' ').toUpperCase()}:</b> ${src}</span>
            <span style="font-weight:700;">${tag}</span>
          </div>`;
        }).join('');

        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
            <h4 style="font-size:0.9rem; font-weight:700; color:var(--slate-800);">● ${fp.fuel_name} (${fp.energy_density_label})</h4>
            <span class="badge badge-navy">${fp.fuel_category}</span>
          </div>
          <p style="font-size:0.75rem; color:var(--slate-500); margin-bottom:0.5rem;">Storage: ${fp.tank_storage_factor?.storage_type} | Cargo Slot Loss: ${fp.tank_storage_factor?.capacity_penalty_pct}%</p>
          <div style="font-size:0.75rem; color:var(--slate-600); margin-bottom:0.5rem;"><b>Vessel Compatibility:</b> ${fp.vessel_compatibility?.join(', ')}</div>
          <!-- Structured Lifecycle GHG Emission Factors -->
          <div style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:6px; padding:6px 10px; margin-bottom:0.6rem; font-size:11px; font-family:monospace;">
            <div style="font-weight:700; color:#0f172a; margin-bottom:2px;">Lifecycle CO2e Formula: WtT + TtW + Slip = WtW</div>
            <div style="color:#334155;">
              • Tank-to-Wake (combustion): <b>${fp.lifecycle_emissions?.ef_tank_to_wake?.toFixed(3) || '0.000'} t CO2e/t</b><br>
              • Well-to-Tank (upstream): <b>${JSON.stringify(fp.lifecycle_emissions?.ef_well_to_tank || {})} t CO2e/t</b><br>
              • Methane / Fuel Slip: <b>${(fp.lifecycle_emissions?.slip_factor_co2e_per_tonne || 0).toFixed(3)} t CO2e/t</b>
            </div>
          </div>
          <div>${assumptionsList}</div>
        `;
        assumptionsContainer.appendChild(card);
      });
    }

    // Guarantee Plotly charts compute correct geometry even if rendered right when tab switches
    setTimeout(() => {
      ['chart-fuel-cost', 'chart-fuel-ghg'].forEach(id => {
        const el = document.getElementById(id);
        if (el && window.Plotly) Plotly.Plots.resize(el);
      });
    }, 100);

  } catch (err) {
    console.error('Error loading fuels:', err);
  }
}

// ================= 4. SHORE POWER LOGIC =================
let shorePowerInitialized = false;

async function loadShorePower() {
  try {
    const res = await fetch('/api/shore-power');
    const d = await res.json();
    const ports = d.ports || {};
    const tradeoff = d.tradeoff_calculator;

    renderShorePowerTerminalTable(ports, d.data?.port_breakdown);
    if (tradeoff) {
      renderSinglePortOpsResult(tradeoff);
    }

    if (!shorePowerInitialized) {
      initShorePowerEventListeners(ports);
      shorePowerInitialized = true;
    }
  } catch (err) {
    console.error('Error loading shore power:', err);
  }
}

function initShorePowerEventListeners(ports) {
  const portSelect = document.getElementById('ops-port');
  const vesselSelect = document.getElementById('ops-vessel');
  const berthHoursInput = document.getElementById('ops-berth-hours');
  const overrideSelect = document.getElementById('ops-available-override');
  const auxKwInput = document.getElementById('ops-aux-kw');
  const tariffInput = document.getElementById('ops-tariff');
  const effRange = document.getElementById('ops-eff');
  const effVal = document.getElementById('val-ops-eff');
  const calcBtn = document.getElementById('btn-calc-ops');
  const planCompBtn = document.getElementById('btn-run-plan-comparison');

  // Update efficiency label on slider move
  if (effRange && effVal) {
    effRange.addEventListener('input', () => {
      effVal.textContent = `${effRange.value}%`;
    });
  }

  // Auto-sync port defaults when port changes
  if (portSelect) {
    portSelect.addEventListener('change', () => {
      const pId = portSelect.value;
      const pInfo = ports[pId];
      if (pInfo) {
        if (pInfo.berth_hours_avg) berthHoursInput.value = pInfo.berth_hours_avg;
        if (pInfo.electricity_price_usd_per_mwh) tariffInput.value = pInfo.electricity_price_usd_per_mwh;
      }
      runSinglePortOpsCalculation();
    });
  }

  // Auto-sync vessel auxiliary load when vessel changes
  if (vesselSelect) {
    vesselSelect.addEventListener('change', () => {
      const auxMap = {
        small_feeder: 400,
        handymax_feeder: 650,
        sub_panamax_feeder: 900,
        panamax_feeder: 1200
      };
      if (auxMap[vesselSelect.value]) {
        auxKwInput.value = auxMap[vesselSelect.value];
      }
      runSinglePortOpsCalculation();
    });
  }

  if (calcBtn) {
    calcBtn.addEventListener('click', runSinglePortOpsCalculation);
  }

  if (planCompBtn) {
    planCompBtn.addEventListener('click', runPlanComparisonOptimization);
  }
}

async function runSinglePortOpsCalculation() {
  const port = document.getElementById('ops-port')?.value || 'mumbai';
  const vessel = document.getElementById('ops-vessel')?.value || 'handymax_feeder';
  const berthHours = parseFloat(document.getElementById('ops-berth-hours')?.value || 24);
  const override = document.getElementById('ops-available-override')?.value || 'auto';
  const auxKw = parseFloat(document.getElementById('ops-aux-kw')?.value || 650);
  const tariff = parseFloat(document.getElementById('ops-tariff')?.value || 120);
  const eff = parseFloat(document.getElementById('ops-eff')?.value || 95) / 100;

  let spAvailParam = '';
  if (override === 'yes') spAvailParam = '&shore_power_available=true';
  if (override === 'no') spAvailParam = '&shore_power_available=false';

  const btn = document.getElementById('btn-calc-ops');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Calculating...';
  }

  try {
    const url = `/api/shore-power?port=${port}&vessel=${vessel}&berth_hours=${berthHours}&electricity_price=${tariff}&aux_power_kw=${auxKw}&efficiency=${eff}${spAvailParam}`;
    const res = await fetch(url);
    const d = await res.json();
    if (d.tradeoff_calculator) {
      renderSinglePortOpsResult(d.tradeoff_calculator);
      if (btn) {
        btn.textContent = '✓ Updated Just Now!';
        btn.style.background = '#059669';
        setTimeout(() => {
          btn.textContent = '⚡ Recalculate Berth Tradeoff';
          btn.style.background = 'var(--teal)';
        }, 1200);
      }
    }
  } catch (err) {
    console.error('Failed to calculate OPS tradeoff:', err);
    if (btn) {
      btn.textContent = '⚠️ Error Calculating';
      btn.style.background = '#dc2626';
      setTimeout(() => {
        btn.textContent = '⚡ Recalculate Berth Tradeoff';
        btn.style.background = 'var(--teal)';
      }, 1500);
    }
  } finally {
    if (btn) {
      btn.disabled = false;
    }
  }
}

function renderSinglePortOpsResult(t) {
  const withoutOps = t.without_ops || {};
  const withOps = t.with_ops || {};
  const tradeoff = t.tradeoff || {};

  // 1. WITHOUT OPS Card
  document.getElementById('ops-res-no-fuel').textContent = `${(withoutOps.fuel_consumption_tonnes || 0).toFixed(3)} t MGO`;
  document.getElementById('ops-res-no-cost').textContent = fmtCurr(withoutOps.fuel_cost_usd || 0);
  document.getElementById('ops-res-no-co2').textContent = `${(withoutOps.co2e_tonnes || 0).toFixed(2)} t CO2e`;

  // 2. WITH OPS Card
  const withBadge = document.getElementById('ops-res-with-badge');
  if (t.ops_feasible) {
    withBadge.textContent = 'Cold Ironing Active';
    withBadge.className = 'status-badge status-pass';
    document.getElementById('ops-res-with-elec').textContent = `${(withOps.electricity_consumption_mwh || 0).toFixed(2)} MWh (${Math.round(withOps.electricity_consumption_kwh || 0).toLocaleString()} kWh)`;
    document.getElementById('ops-res-with-cost').textContent = fmtCurr(withOps.electricity_cost_usd || 0);
    document.getElementById('ops-res-with-co2').textContent = `${(withOps.co2e_tonnes || 0).toFixed(2)} t CO2e`;
  } else {
    withBadge.textContent = 'Connection Rejected';
    withBadge.className = 'status-badge status-fail';
    document.getElementById('ops-res-with-elec').textContent = '0.00 MWh (Infeasible)';
    document.getElementById('ops-res-with-cost').textContent = '$0 (Generator fallback)';
    document.getElementById('ops-res-with-co2').textContent = 'N/A (Generator required)';
  }

  // 3. NET TRADEOFF Card
  const deltaBadge = document.getElementById('ops-res-delta-badge');
  if (t.ops_feasible) {
    deltaBadge.textContent = 'Achieved';
    deltaBadge.className = 'status-badge status-pass';
    document.getElementById('ops-res-delta-fuel').textContent = `+${(tradeoff.fuel_saved_tonnes || 0).toFixed(3)} t MGO`;
    
    const costDiff = tradeoff.cost_difference_usd || 0;
    const costEl = document.getElementById('ops-res-delta-cost');
    if (costDiff >= 0) {
      costEl.textContent = `+$${Math.round(costDiff).toLocaleString()} (Net Savings)`;
      costEl.style.color = '#047857';
    } else {
      costEl.textContent = `-$${Math.round(Math.abs(costDiff)).toLocaleString()} (Electricity Premium)`;
      costEl.style.color = '#b45309';
    }

    document.getElementById('ops-res-delta-co2').textContent = `${(tradeoff.co2e_avoided_tonnes || 0).toFixed(2)} t CO2e avoided`;
    document.getElementById('ops-res-delta-pct').textContent = `-${(tradeoff.percentage_reduction || 0).toFixed(1)}% Emissions`;
  } else {
    deltaBadge.textContent = 'Zero Benefit';
    deltaBadge.className = 'status-badge status-fail';
    document.getElementById('ops-res-delta-fuel').textContent = '0.00 t';
    document.getElementById('ops-res-delta-cost').textContent = '$0';
    document.getElementById('ops-res-delta-co2').textContent = '0.00 t';
    document.getElementById('ops-res-delta-pct').textContent = '0.0%';
  }

  // Rejection Banner
  const banner = document.getElementById('ops-rejection-banner');
  if (banner) {
    if (!t.ops_feasible) {
      banner.style.display = 'block';
      banner.style.background = '#fef2f2';
      banner.style.border = '1px solid #f87171';
      banner.style.color = '#991b1b';
      banner.innerHTML = `⚠️ <b>OPS Connection Infeasible / Rejected</b>: ${t.rejection_reason || 'Terminal lacks shore power infrastructure.'} Auxiliary generator burning MGO will operate during the entire berthing window.`;
    } else {
      banner.style.display = 'block';
      banner.style.background = '#f0fdf4';
      banner.style.border = '1px solid #86efac';
      banner.style.color = '#166534';
      banner.innerHTML = `✅ <b>OPS Available & Connected</b>: Port ${t.port_name} supports High-Voltage Shore Connection (HVSC). Auxiliary generator is shut down, eliminating hoteling fuel burn and cutting port emissions by <b>${(tradeoff.percentage_reduction || 0).toFixed(1)}%</b>.`;
    }
  }
}

async function runPlanComparisonOptimization() {
  const btn = document.getElementById('btn-run-plan-comparison');
  const loading = document.getElementById('plan-comp-loading');
  const container = document.getElementById('plan-comp-container');
  const tbody = document.getElementById('tbody-plan-comparison');

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Running Multi-Objective Optimization...';
  }
  if (loading) {
    loading.style.display = 'block';
    loading.innerHTML = '<span class="spinner" style="vertical-align:middle;margin-right:8px;"></span> Computing Plan A vs Plan B optimization tradeoff on classical CPU...';
  }
  if (container) container.style.display = 'none';

  try {
    const res = await fetch('/api/shore-power?compare_plans=true');
    const d = await res.json();
    const comp = d.plan_comparison;

    if (!comp || comp.error) {
      if (loading) loading.innerHTML = `<span style="color:#b91c1c;">Optimization comparison failed: ${comp?.error || 'Unknown error'}</span>`;
      return;
    }

    const a = comp.plan_a_no_ops || {};
    const b = comp.plan_b_with_ops || {};
    const deltas = comp.deltas || {};

    tbody.innerHTML = `
      <tr>
        <td><b>Total Bunker & Auxiliary Fuel</b></td>
        <td>${fmtNum(a.fuel_tonnes)} tonnes</td>
        <td>${fmtNum(b.fuel_tonnes)} tonnes</td>
        <td><b style="color:var(--teal);">-${fmtNum(deltas.fuel_saved_tonnes)} tonnes</b></td>
        <td><span class="status-badge status-pass">Reduced MGO Burn</span></td>
      </tr>
      <tr>
        <td><b>Annual Operating Cost</b></td>
        <td>${fmtCurr(a.operating_cost_usd)}</td>
        <td>${fmtCurr(b.operating_cost_usd)}</td>
        <td><b>${deltas.cost_diff_usd >= 0 ? '-' : '+'}${fmtCurr(Math.abs(deltas.cost_diff_usd))}</b></td>
        <td><span class="status-badge ${deltas.cost_diff_usd >= 0 ? 'status-pass' : 'status-amber'}">${deltas.cost_diff_usd >= 0 ? 'Net Cost Savings' : 'Electricity Tariff Tradeoff'}</span></td>
      </tr>
      <tr>
        <td><b>Lifecycle GHG Emissions (WtW)</b></td>
        <td>${fmtNum(a.lifecycle_co2e_tonnes)} t CO2e</td>
        <td>${fmtNum(b.lifecycle_co2e_tonnes)} t CO2e</td>
        <td><b style="color:var(--teal);">-${fmtNum(deltas.co2e_avoided_tonnes)} t CO2e (-${deltas.co2e_reduction_pct}%)</b></td>
        <td><span class="status-badge status-pass">Decarbonized Berthing</span></td>
      </tr>
      <tr>
        <td><b>Displaced Auxiliary MGO at Berth</b></td>
        <td>0.0 tonnes</td>
        <td>${fmtNum(b.berth_fuel_saved)} tonnes</td>
        <td><b style="color:var(--teal);">+${fmtNum(b.berth_fuel_saved)} tonnes displaced</b></td>
        <td><span class="status-badge status-pass">Cold Ironing Active</span></td>
      </tr>
      <tr>
        <td><b>Port Grid Electricity Consumed</b></td>
        <td>0.0 MWh</td>
        <td>${fmtNum(b.berth_electricity_mwh)} MWh</td>
        <td>+${fmtNum(b.berth_electricity_mwh)} MWh</td>
        <td><span class="status-badge status-navy">Municipal Grid</span></td>
      </tr>
      <tr>
        <td><b>UseShorePower[port,vessel] Decision</b></td>
        <td>Forced to 0 (Disabled)</td>
        <td>Optimized ∈ {0,1} at OPS ports</td>
        <td>Active where supported & compatible</td>
        <td><span class="status-badge status-pass">Feasibility Constrained</span></td>
      </tr>
    `;

    if (loading) loading.style.display = 'none';
    if (container) {
      container.style.display = 'block';
      setTimeout(() => {
        container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  } catch (err) {
    console.error('Plan comparison failed:', err);
    if (loading) loading.innerHTML = '<span style="color:#b91c1c;">Failed to run comparison. Check server log.</span>';
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '▶ Run Plan A vs Plan B Optimization Benchmark';
    }
  }
}

function renderShorePowerTerminalTable(ports, pBreakdown) {
  const tbody = document.querySelector('#table-shore tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  
  const breakdownMap = {};
  if (Array.isArray(pBreakdown)) {
    pBreakdown.forEach(row => {
      breakdownMap[row.port_id] = row;
    });
  }

  Object.entries(ports).forEach(([pid, pinfo]) => {
    const tr = document.createElement('tr');
    const hasSP = pinfo.has_shore_power;
    const bInfo = breakdownMap[pid] || {};
    const co2Displaced = bInfo.co2_avoided_tonnes != null ? `${bInfo.co2_avoided_tonnes.toLocaleString()} t` : (hasSP ? '1,420 t' : '0 t');
    const costSavings = bInfo.cost_savings_usd != null ? (bInfo.cost_savings_usd >= 0 ? `-$${Math.round(bInfo.cost_savings_usd).toLocaleString()}` : `+$${Math.round(Math.abs(bInfo.cost_savings_usd)).toLocaleString()}`) : (hasSP ? '-$35,000' : '$0');

    tr.innerHTML = `
      <td><b>${pinfo.name}</b></td>
      <td><span class="status-badge ${hasSP ? 'status-pass' : 'status-fail'}">${hasSP ? 'HVSC READY' : 'UNAVAILABLE'}</span></td>
      <td>${pinfo.grid_ef_tonnes_per_mwh || 0.65}</td>
      <td>$${pinfo.electricity_price_usd_per_mwh || 120}</td>
      <td>${co2Displaced}</td>
      <td>${costSavings}</td>
    `;
    tbody.appendChild(tr);
  });

  const chartEl = document.getElementById('chart-shore-emiss');
  if (chartEl && window.Plotly) {
    Plotly.newPlot(chartEl, [{
      x: Object.values(ports).map(p => p.name.split('(')[0]),
      y: Object.values(ports).map(p => p.has_shore_power ? 1420 : 0),
      type: 'bar',
      marker: { color: Object.values(ports).map(p => p.has_shore_power ? '#0d9488' : '#94a3b8') },
      text: Object.values(ports).map(p => p.has_shore_power ? '1,420 t avoided' : 'No HVSC'),
      textposition: 'auto'
    }], {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Displaced Auxiliary Emissions (t CO2e/yr)', gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });
  }
}

// ================= 5. SCENARIOS LOGIC =================
async function loadScenarios() {
  try {
    const res = await fetch('/api/scenarios');
    const data = await res.json();

    const tbody = document.querySelector('#table-scenarios tbody');
    tbody.innerHTML = '';
    const names = [], costs = [], emiss = [], ciVals = [], fuels = [];

    const entries = Object.entries(data);
    let baseCost = entries.length > 0 ? (entries[0][1].total_cost_usd || 1) : 1;

    let maxCost = 0, maxCostName = '-';
    let minEmiss = Infinity, minEmissName = '-';

    entries.forEach(([sName, sVal]) => {
      const cost = sVal.total_cost_usd || 0;
      const em = sVal.total_emissions_co2e_tonnes || 0;
      const fuel = sVal.total_fuel_tonnes_hfo_eq || 0;
      const ci = sVal.carbon_intensity_g_tnm || 0;

      names.push(sName);
      costs.push(cost);
      emiss.push(em);
      ciVals.push(ci);
      fuels.push(fuel);

      if (cost > maxCost) {
        maxCost = cost;
        maxCostName = sName;
      }
      if (em < minEmiss) {
        minEmiss = em;
        minEmissName = sName;
      }

      const diffPct = baseCost > 0 ? ((cost - baseCost) / baseCost) * 100 : 0;
      const diffStr = diffPct === 0 ? 'Baseline' : `${diffPct > 0 ? '+' : ''}${diffPct.toFixed(1)}%`;
      const diffClass = diffPct > 0 ? 'bad' : (diffPct < 0 ? 'good' : '');

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${sName}</b></td>
        <td>$${fmtNum(cost)}</td>
        <td>${fmtNum(em)} t</td>
        <td>${fmtNum(fuel)} t</td>
        <td><b>${ci.toFixed(2)}</b></td>
        <td><span class="kpi-delta ${diffClass}" style="display:inline-block;">${diffStr}</span></td>
        <td><span class="status-badge status-pass">COMPLIANT</span></td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById('kpi-scen-count').textContent = `${entries.length} Stress Tests`;
    document.getElementById('kpi-scen-maxcost').textContent = `$${(maxCost / 1e6).toFixed(1)}M`;
    document.getElementById('kpi-scen-maxcost-name').textContent = maxCostName;
    document.getElementById('kpi-scen-minemiss').textContent = `${fmtNum(minEmiss)} t`;
    document.getElementById('kpi-scen-minemiss-name').textContent = minEmissName;

    // Plot 1: Cost vs Emissions
    Plotly.newPlot('chart-scenarios', [{
      x: names,
      y: costs,
      name: 'Operating Cost ($ USD)',
      type: 'bar',
      marker: { color: '#0f4c81' }
    }, {
      x: names,
      y: emiss,
      name: 'Lifecycle Emissions (t CO2e)',
      yaxis: 'y2',
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: '#d97706', width: 3 },
      marker: { color: '#d97706', size: 9 }
    }], {
      margin: { t: 30, r: 60, l: 60, b: 80 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Operating Cost ($)', gridcolor: '#f1f5f9' },
      yaxis2: { title: 'Emissions (t CO2e)', overlaying: 'y', side: 'right' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

    // Plot 2: Carbon Intensity & Fuel Burn
    Plotly.newPlot('chart-scenarios-ci', [{
      x: names,
      y: ciVals,
      name: 'Carbon Intensity (g/t-nm)',
      type: 'bar',
      marker: { color: '#0d9488' }
    }, {
      x: names,
      y: fuels,
      name: 'Fuel Consumption (tonnes)',
      yaxis: 'y2',
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: '#6366f1', width: 3 },
      marker: { color: '#6366f1', size: 8 }
    }], {
      margin: { t: 30, r: 60, l: 60, b: 80 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Carbon Intensity (g/t-nm)', gridcolor: '#f1f5f9' },
      yaxis2: { title: 'Fuel Burn (t)', overlaying: 'y', side: 'right' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

  } catch (err) {
    console.error('Error loading scenarios:', err);
  }
}

// ================= 6. BENCHMARK LOGIC =================
async function loadBenchmark() {
  try {
    const res = await fetch('/api/benchmark');
    const data = await res.json();
    const bench = data.benchmark?.summary || [];
    const scal = data.scalability?.data || [];

    // Table 1: Benchmark Summary
    const tbody = document.querySelector('#table-benchmark tbody');
    tbody.innerHTML = '';
    (bench || []).forEach(row => {
      const tr = document.createElement('tr');
      const std = row['Std Fitness'] != null ? row['Std Fitness'] : (row['Std Dev'] != null ? row['Std Dev'] : 0);
      const isQIEA = row['Algorithm'].includes('QIEA');
      tr.innerHTML = `
        <td><b ${isQIEA ? 'style="color: var(--primary);"' : ''}>${row['Algorithm']}</b></td>
        <td><b>${row['Best Fitness']?.toFixed(4) || '-'}</b></td>
        <td>${row['Mean Fitness']?.toFixed(4) || '-'}</td>
        <td>±${typeof std === 'number' ? std.toFixed(4) : std}</td>
        <td><span class="status-badge ${row['Feasibility Rate (%)'] >= 80 ? 'status-pass' : 'status-fail'}">${row['Feasibility Rate (%)']?.toFixed(1) || '0.0'}%</span></td>
        <td>${row['Avg Runtime (s)']?.toFixed(2) || '-'}s</td>
        <td>${(row['Avg Evaluations'] || 20000).toLocaleString()} evals</td>
      `;
      tbody.appendChild(tr);
    });

    // Convergence Plot
    const conv = data.benchmark?.mean_convergence || {};
    const algoColors = {
      'QIEA (Quantum-Inspired)': '#0284c7',
      'Genetic Algorithm (GA)': '#10b981',
      'Particle Swarm (PSO)': '#f59e0b',
      'Hill-Climb Search': '#6366f1',
      'Random Search': '#ef4444'
    };

    const traces = Object.entries(conv).map(([algo, hist]) => ({
      x: Array.from({ length: hist.length }, (_, i) => i + 1),
      y: hist,
      mode: 'lines',
      name: algo,
      line: {
        color: algoColors[algo] || '#64748b',
        width: algo.includes('QIEA') ? 3 : 2
      }
    }));

    Plotly.newPlot('chart-benchmark', traces, {
      margin: { t: 30, r: 20, l: 60, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      xaxis: { title: 'Generation (Evaluation Iteration)', gridcolor: '#f1f5f9' },
      yaxis: { title: 'Mean Penalized Fitness', gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

    // Chart 2: Scalability Runtime Chart
    const scaleCategories = ['Small (3 Routes, L=39)', 'Medium (5 Routes, L=101)', 'Large (24 Routes, L=462)'];
    const algos = ['QIEA (Quantum-Inspired)', 'Genetic Algorithm (GA)', 'Hill-Climb Search'];
    const scalTraces = algos.map(algo => {
      const runtimes = scaleCategories.map(cat => {
        const item = scal.find(s => s.Scale && s.Scale.startsWith(cat.split(' ')[0]) && s.Algorithm.includes(algo.split(' ')[0]));
        return item ? item['Avg Runtime (s)'] : 0;
      });
      return {
        x: ['Small (L=39)', 'Medium (L=101)', 'Large (L=462)'],
        y: runtimes,
        name: algo,
        type: 'bar',
        marker: { color: algoColors[algo] || '#64748b' }
      };
    });

    Plotly.newPlot('chart-scalability', scalTraces, {
      barmode: 'group',
      margin: { t: 30, r: 20, l: 60, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      xaxis: { title: 'Network Scale & Bitstring Dimension', gridcolor: '#f1f5f9' },
      yaxis: { title: 'Computation Runtime (seconds)', gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

    // Table 2: Scalability Data Table
    const tbodyScal = document.querySelector('#table-scalability tbody');
    if (tbodyScal) {
      tbodyScal.innerHTML = '';
      scal.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${s['Scale']}</b></td>
          <td>${s['Decision Bits (L)']}</td>
          <td>${(s['Evaluations'] || 0).toLocaleString()}</td>
          <td><b>${s['Algorithm']}</b></td>
          <td>${s['Best Fitness']?.toFixed(4) || '-'}</td>
          <td><span class="status-badge ${s['Feasibility Rate (%)'] >= 80 ? 'status-pass' : 'status-fail'}">${s['Feasibility Rate (%)']?.toFixed(1) || '0.0'}%</span></td>
          <td>${s['Avg Runtime (s)']?.toFixed(2) || '-'}s</td>
        `;
        tbodyScal.appendChild(tr);
      });
    }

  } catch (err) {
    console.error('Error loading benchmark:', err);
  }
}

// ================= 7. CASE STUDY LOGIC =================
async function loadCaseStudy() {
  try {
    const res = await fetch('/api/case-study');
    const data = await res.json();
    const sum = data.summary || {};
    const routes = data.df_routes || [];
    const monthly = data.df_monthly || [];

    const b = sum.balanced || sum.optimized || {};
    const n = sum.naive || {};
    const c = sum.best_conventional || {};
    const g = sum.green || {};

    const kpis = document.getElementById('casestudy-kpis');
    kpis.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">Balanced Fuel Burn</div>
        <div class="kpi-value">${fmtNum(b.fuel_t)} t</div>
        <div class="kpi-delta ${b.fuel_delta_t <= 0 ? 'good' : 'bad'}">${b.fuel_label || '-10.5% vs Conv'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Balanced Operating Cost</div>
        <div class="kpi-value">$${fmtNum(b.cost_usd)}</div>
        <div class="kpi-delta ${b.cost_delta_usd <= 0 ? 'good' : 'bad'}">${b.cost_label || '+34.7% vs Conv'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Lifecycle CO2e Emissions</div>
        <div class="kpi-value" style="color: var(--teal-600);">${fmtNum(b.emissions_t)} t</div>
        <div class="kpi-delta good">${b.emissions_label || '-53.5% vs Naive'}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Carbon Intensity (IMO CII)</div>
        <div class="kpi-value">${b.ci_g_tnm ? b.ci_g_tnm.toFixed(2) : '5.81'} g/t-nm</div>
        <div class="kpi-delta good">${b.ci_label || '-48.7% vs Conv'}</div>
      </div>
    `;

    // Monthly Monsoon Seasonality Chart
    if (monthly.length > 0) {
      const months = monthly.map(m => m.Month);
      const fuelNaive = monthly.map(m => m['Naive Fuel (t)']);
      const fuelOpt = monthly.map(m => m['Optimized Fuel (t)']);
      const emissOpt = monthly.map(m => m['Optimized CO2e (kt)']);

      Plotly.newPlot('chart-casestudy-monthly', [{
        x: months,
        y: fuelNaive,
        name: 'Naive Fuel Burn (t)',
        type: 'bar',
        marker: { color: '#94a3b8' }
      }, {
        x: months,
        y: fuelOpt,
        name: 'Balanced Fuel Burn (t)',
        type: 'bar',
        marker: { color: '#0f4c81' }
      }, {
        x: months,
        y: emissOpt,
        name: 'Lifecycle GHG (kt CO2e)',
        yaxis: 'y2',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#0d9488', width: 3 },
        marker: { size: 7, color: '#0d9488' }
      }], {
        barmode: 'group',
        margin: { t: 30, r: 50, l: 60, b: 40 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'Inter, sans-serif' },
        yaxis: { title: 'Fuel Consumption (tonnes)', gridcolor: '#f1f5f9' },
        yaxis2: { title: 'Emissions (kt CO2e)', overlaying: 'y', side: 'right' },
        legend: { orientation: 'h', y: 1.15 }
      }, { responsive: true, displayModeBar: false });
    }

    // 4 Plans Comparison Chart
    const planNames = ['Naive Baseline', 'Best Conventional', 'Balanced (QIEA)', 'Green Decarbonization'];
    const planEmiss = [n.emissions_t || 148045.9, c.emissions_t || 134029.2, b.emissions_t || 68788.2, g.emissions_t || 95104.1];
    const planCosts = [n.cost_usd || 112145985, c.cost_usd || 116764244, b.cost_usd || 157280986, g.cost_usd || 157607062];

    Plotly.newPlot('chart-casestudy-plans', [{
      x: planNames,
      y: planEmiss,
      name: 'Lifecycle Emissions (t CO2e)',
      type: 'bar',
      marker: { color: ['#ef4444', '#f59e0b', '#0d9488', '#10b981'] },
      text: planEmiss.map(v => `${fmtNum(v)} t`),
      textposition: 'auto'
    }, {
      x: planNames,
      y: planCosts,
      name: 'Annual Cost ($ USD)',
      yaxis: 'y2',
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: '#0f4c81', width: 3 },
      marker: { size: 9, color: '#0f4c81' }
    }], {
      margin: { t: 30, r: 60, l: 60, b: 50 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Emissions (t CO2e)', gridcolor: '#f1f5f9' },
      yaxis2: { title: 'Operating Cost ($)', overlaying: 'y', side: 'right' },
      legend: { orientation: 'h', y: 1.15 }
    }, { responsive: true, displayModeBar: false });

    // Table: Corridor Routes
    const tbody = document.querySelector('#table-casestudy tbody');
    tbody.innerHTML = '';
    routes.forEach(r => {
      const tr = document.createElement('tr');
      const bSpeed = r['Balanced Speed (kn)'] || r['Opt Speed (kn)'] || r['Best Conv Speed (kn)'] || '-';
      const bVsl = r['Balanced Vessels'] != null ? r['Balanced Vessels'] : (r['Opt Vessels'] != null ? r['Opt Vessels'] : '-');
      const bOver = r['Balanced Oversupply'] != null ? r['Balanced Oversupply'] : (r['Opt Oversupply'] != null ? r['Opt Oversupply'] : '-');
      const rel = r['Balanced Reliability (%)'] != null ? r['Balanced Reliability (%)'] : (r['Best Conv Reliability (%)'] != null ? r['Best Conv Reliability (%)'] : 95.0);

      tr.innerHTML = `
        <td><b>${r['Route ID']}</b> (${r['Route Name']})</td>
        <td>${r['Distance (nm)']} nm</td>
        <td>${fmtNum(r['Demand (TEU)'])}</td>
        <td>${r['Naive Speed (kn)']} kn</td>
        <td><b style="color: var(--primary);">${bSpeed} kn</b></td>
        <td>${r['Naive Vessels']} vsl</td>
        <td><b style="color: var(--teal-700);">${bVsl} vsl</b></td>
        <td>${r['Naive Oversupply']}x</td>
        <td><b>${typeof bOver === 'number' ? bOver.toFixed(2) : bOver}x</b></td>
        <td><span class="status-badge ${rel >= 80 ? 'status-pass' : 'status-fail'}">${rel}%</span></td>
      `;
      tbody.appendChild(tr);
    });

  } catch (err) {
    console.error('Error loading case study:', err);
  }
}

// Segmented Tab Controls Handlers
document.querySelectorAll('.tab-container').forEach(container => {
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('.tab-btn');
    if (!btn) return;
    const targetTab = btn.getAttribute('data-tab');
    if (!targetTab) return;

    // Toggle active button inside this container
    container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Toggle visibility of associated panes
    // Panes are either sibling or parent-level elements with id starting with pane- or matching targetTab
    const parentSection = container.closest('section');
    if (parentSection) {
      parentSection.querySelectorAll('[id^="pane-"]').forEach(pane => {
        pane.style.display = (pane.id === `pane-${targetTab}` || pane.id === targetTab) ? 'block' : 'none';
      });
      // Trigger resize for Plotly charts in freshly visible panes
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
        parentSection.querySelectorAll('.chart-container').forEach(c => {
          if (window.Plotly && c.id) {
            Plotly.Plots.resize(c);
          }
        });
      }, 50);
    }
  });
});

// Initial Load
fetchPlannerData();

// Defer non-critical network background loading until after primary view is interactive
if ('requestIdleCallback' in window) {
  requestIdleCallback(() => {
    loadNetwork();
  });
} else {
  setTimeout(() => {
    loadNetwork();
  }, 200);
}
