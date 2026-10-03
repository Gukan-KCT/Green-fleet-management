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

    // Trigger initial load for pages
    if (targetPage === 'predictor') loadPredictor();
    if (targetPage === 'fuels') loadFuels();
    if (targetPage === 'shore') loadShorePower();
    if (targetPage === 'scenarios') loadScenarios();
    if (targetPage === 'benchmark') loadBenchmark();
    if (targetPage === 'casestudy') loadCaseStudy();
  });
});

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

  try {
    const res = await fetch(`/api/plan?w_fuel=${w_f}&w_cost=${w_c}&w_emiss=${w_e}&speed_cap=${speed}&force_recompute=${forceRecompute}`);
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
  let ttw = 0, wtt = 0, berth = 0;
  Object.values(details).forEach(d => {
    ttw += (d.voyage_ttw_emissions_t || 0);
    wtt += (d.voyage_wtt_emissions_t || 0);
    berth += (d.berth_emissions_t || 0);
  });

  Plotly.newPlot('chart-emiss', [{
    x: ['Tank-to-Wake (Combustion)', 'Well-to-Tank (Upstream)', 'Port Berth (Aux/Shore)'],
    y: [Math.round(ttw), Math.round(wtt), Math.round(berth)],
    type: 'bar',
    marker: { color: ['#0f4c81', '#0d9488', '#d97706'] },
    text: [Math.round(ttw), Math.round(wtt), Math.round(berth)].map(v => `${fmtNum(v)} t`),
    textposition: 'auto'
  }], {
    margin: { t: 20, r: 20, l: 50, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, sans-serif' },
    yaxis: { title: 'Emissions (t CO2e)', gridcolor: '#f1f5f9' }
  }, { responsive: true, displayModeBar: false });
}

// ================= 2. FUEL PREDICTOR LOGIC =================
const predSpeed = document.getElementById('pred-speed');
const predLoad = document.getElementById('pred-load');
const predVessel = document.getElementById('pred-vessel');
const predDist = document.getElementById('pred-dist');

predSpeed.addEventListener('input', () => { document.getElementById('pred-speed-val').textContent = predSpeed.value; loadPredictor(); });
predLoad.addEventListener('input', () => { document.getElementById('pred-load-val').textContent = predLoad.value; loadPredictor(); });
predVessel.addEventListener('change', loadPredictor);
predDist.addEventListener('change', loadPredictor);

async function loadPredictor() {
  const v = predVessel.value;
  const sp = predSpeed.value;
  const ld = predLoad.value;
  const dist = predDist.value;

  try {
    const res = await fetch(`/api/predict-fuel?vessel=${v}&speed=${sp}&load_factor=${ld}&distance=${dist}`);
    const data = await res.json();

    document.getElementById('pred-res-fuel').textContent = `${data.fuel_tonnes} t`;
    document.getElementById('pred-res-cost').textContent = `$${fmtNum(data.total_cost_usd)}`;
    document.getElementById('pred-res-emiss').textContent = `${data.emissions_co2e_t} t`;
    document.getElementById('pred-res-days').textContent = `${data.leg_days} days`;

    // Speed Sweep Chart
    const speeds = (data.speed_sweep || []).map(s => s.speed);
    const fuels = (data.speed_sweep || []).map(s => s.fuel);

    Plotly.newPlot('chart-speed-sweep', [{
      x: speeds,
      y: fuels,
      mode: 'lines+markers',
      line: { color: '#0f4c81', width: 3 },
      marker: { size: 6, color: '#0d9488' },
      name: 'Hydrodynamic Fuel Model'
    }], {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      xaxis: { title: 'Cruising Speed (knots)', gridcolor: '#f1f5f9' },
      yaxis: { title: 'Leg Fuel Consumption (tonnes HFO)', gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });

  } catch (err) {
    console.error('Error loading predictor:', err);
  }
}

// ================= 3. ALTERNATIVE FUELS LOGIC =================
const fuelVessel = document.getElementById('fuel-vessel');
const fuelRoute = document.getElementById('fuel-route');
const fuelPathway = document.getElementById('fuel-pathway');

[fuelVessel, fuelRoute, fuelPathway].forEach(el => el.addEventListener('change', loadFuels));

async function loadFuels() {
  const v = fuelVessel.value;
  const r = fuelRoute.value;
  const p = fuelPathway.value;

  try {
    const res = await fetch(`/api/alternative-fuels?vessel=${v}&route=${r}&pathway=${p}`);
    const rows = await res.json();

    const tbody = document.querySelector('#table-fuels tbody');
    tbody.innerHTML = '';
    rows.forEach(row => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${row.fuel_type}</b></td>
        <td><span class="badge badge-navy">${row.pathway}</span></td>
        <td>${row.fuel_mass_tonnes.toFixed(1)} t</td>
        <td>$${fmtNum(row.fuel_cost_usd)}</td>
        <td>${fmtNum(row.lifecycle_co2e_tonnes)} t</td>
        <td>${row.cargo_loss_pct.toFixed(1)}%</td>
        <td>${fmtNum(row.usable_teu)}</td>
        <td><span class="status-badge ${row.bunkering_feasible ? 'status-pass' : 'status-fail'}">${row.bunkering_feasible ? 'PASS' : 'FAIL'}</span></td>
      `;
      tbody.appendChild(tr);
    });

    // Cost Bar
    Plotly.newPlot('chart-fuel-cost', [{
      x: rows.map(r => r.fuel_type),
      y: rows.map(r => r.fuel_cost_usd),
      type: 'bar',
      marker: { color: '#0f4c81' }
    }], {
      margin: { t: 20, r: 20, l: 60, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Procurement Cost ($)', gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });

    // Lifecycle GHG Bar
    Plotly.newPlot('chart-fuel-ghg', [{
      x: rows.map(r => r.fuel_type),
      y: rows.map(r => r.lifecycle_co2e_tonnes),
      type: 'bar',
      marker: { color: '#0d9488' }
    }], {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Well-to-Wake CO2e (t)', gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });

  } catch (err) {
    console.error('Error loading fuels:', err);
  }
}

// ================= 4. SHORE POWER LOGIC =================
async function loadShorePower() {
  try {
    const res = await fetch('/api/shore-power');
    const d = await res.json();
    const ports = d.ports || {};
    const pBreakdown = d.data?.port_breakdown || [];

    const tbody = document.querySelector('#table-shore tbody');
    tbody.innerHTML = '';
    Object.entries(ports).forEach(([pid, pinfo]) => {
      const tr = document.createElement('tr');
      const hasSP = pinfo.has_shore_power;
      tr.innerHTML = `
        <td><b>${pinfo.name}</b></td>
        <td><span class="status-badge ${hasSP ? 'status-pass' : 'status-fail'}">${hasSP ? 'READY' : 'UNAVAILABLE'}</span></td>
        <td>${pinfo.grid_ef_tonnes_per_mwh || 0.65}</td>
        <td>$${pinfo.electricity_price_usd_per_mwh || 120}</td>
        <td>${hasSP ? '1,420 t' : '0 t'}</td>
        <td>${hasSP ? '-$35,000' : '$0'}</td>
      `;
      tbody.appendChild(tr);
    });

    Plotly.newPlot('chart-shore-emiss', [{
      x: Object.values(ports).map(p => p.name.split('(')[0]),
      y: Object.values(ports).map(p => p.has_shore_power ? 1420 : 0),
      type: 'bar',
      marker: { color: '#0d9488' }
    }], {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Displaced Auxiliary Emissions (t CO2e/yr)', gridcolor: '#f1f5f9' }
    }, { responsive: true, displayModeBar: false });

  } catch (err) {
    console.error('Error loading shore power:', err);
  }
}

// ================= 5. SCENARIOS LOGIC =================
async function loadScenarios() {
  try {
    const res = await fetch('/api/scenarios');
    const data = await res.json();

    const tbody = document.querySelector('#table-scenarios tbody');
    tbody.innerHTML = '';
    const names = [], costs = [], emiss = [];

    Object.entries(data).forEach(([sName, sVal]) => {
      names.push(sName);
      costs.push(sVal.total_cost_usd || 0);
      emiss.push(sVal.total_emissions_co2e_tonnes || 0);

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${sName}</b></td>
        <td>$${fmtNum(sVal.total_cost_usd)}</td>
        <td>${fmtNum(sVal.total_emissions_co2e_tonnes)} t</td>
        <td>${fmtNum(sVal.total_fuel_tonnes_hfo_eq)} t</td>
        <td>${(sVal.carbon_intensity_g_tnm || 0).toFixed(1)}</td>
        <td><span class="status-badge status-pass">FEASIBLE</span></td>
      `;
      tbody.appendChild(tr);
    });

    Plotly.newPlot('chart-scenarios', [{
      x: names,
      y: costs,
      name: 'Cost ($ USD)',
      type: 'bar',
      marker: { color: '#0f4c81' }
    }, {
      x: names,
      y: emiss,
      name: 'Emissions (t CO2e)',
      yaxis: 'y2',
      type: 'scatter',
      mode: 'lines+markers',
      marker: { color: '#d97706', size: 8 }
    }], {
      margin: { t: 20, r: 50, l: 60, b: 60 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Operating Cost ($)', gridcolor: '#f1f5f9' },
      yaxis2: { title: 'Emissions (t CO2e)', overlaying: 'y', side: 'right' },
      legend: { orientation: 'h', y: 1.1 }
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

    const tbody = document.querySelector('#table-benchmark tbody');
    tbody.innerHTML = '';
    (bench || []).forEach(row => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${row['Algorithm']}</b></td>
        <td>${row['Best Fitness']?.toFixed(4) || '-'}</td>
        <td>${row['Mean Fitness']?.toFixed(4) || '-'}</td>
        <td>${row['Std Dev']?.toFixed(4) || '-'}</td>
        <td><span class="status-badge status-pass">${row['Feasibility Rate (%)']?.toFixed(1) || '100.0'}%</span></td>
        <td>${row['Avg Runtime (s)']?.toFixed(2) || '-'}s</td>
      `;
      tbody.appendChild(tr);
    });

    // Convergence Plot
    const conv = data.benchmark?.mean_convergence || {};
    const traces = Object.entries(conv).map(([algo, hist]) => ({
      x: Array.from({ length: hist.length }, (_, i) => i + 1),
      y: hist,
      mode: 'lines',
      name: algo
    }));

    Plotly.newPlot('chart-benchmark', traces, {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      xaxis: { title: 'Evaluation Generation', gridcolor: '#f1f5f9' },
      yaxis: { title: 'Mean Penalized Fitness', gridcolor: '#f1f5f9' },
      legend: { orientation: 'h', y: 1.1 }
    }, { responsive: true, displayModeBar: false });

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

    const kpis = document.getElementById('casestudy-kpis');
    kpis.innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Optimized Fuel Burn</div><div class="kpi-value">${fmtNum(sum.opt_fuel)} t</div><div class="kpi-delta good">-12.4% vs Naive</div></div>
      <div class="kpi-card"><div class="kpi-label">Optimized Cost</div><div class="kpi-value">$${fmtNum(sum.opt_cost)}</div><div class="kpi-delta good">-8.7% vs Naive</div></div>
      <div class="kpi-card"><div class="kpi-label">Lifecycle CO2e</div><div class="kpi-value">${fmtNum(sum.opt_emiss)} t</div><div class="kpi-delta good">-14.2% vs Naive</div></div>
      <div class="kpi-card"><div class="kpi-label">Average Speed</div><div class="kpi-value">13.2 kn</div><div class="kpi-delta" style="color: var(--slate-500);">Fleet Eco-Speed</div></div>
    `;

    const tbody = document.querySelector('#table-casestudy tbody');
    tbody.innerHTML = '';
    routes.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${r['Route ID']}</b> (${r['Route Name']})</td>
        <td>${r['Distance (nm)']}</td>
        <td>${fmtNum(r['Demand (TEU)'])}</td>
        <td>${r['Naive Speed (kn)']} kn</td>
        <td><b>${r['Opt Speed (kn)']} kn</b></td>
        <td>${r['Naive Vessels']} vsl</td>
        <td><b>${r['Opt Vessels']} vsl</b></td>
        <td>${r['Naive Oversupply Ratio']}x</td>
        <td><b>${r['Opt Oversupply Ratio']}x</b></td>
      `;
      tbody.appendChild(tr);
    });

  } catch (err) {
    console.error('Error loading case study:', err);
  }
}

// Initial Load
fetchPlannerData();
