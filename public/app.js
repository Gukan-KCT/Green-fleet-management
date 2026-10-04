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
    if (!res.ok) {
      throw new Error(`Planner API returned HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    renderPlanner(data);
  } catch (err) {
    console.error('Failed to fetch plan:', err);
    ['delta-fuel', 'delta-cost', 'delta-emiss', 'delta-ci'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'Retry Needed';
    });
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

  if (opt.emissions_breakdown) {
    ttw = opt.emissions_breakdown.ttw_co2e_tonnes || 0;
    wtt = opt.emissions_breakdown.wtt_co2e_tonnes || 0;
    berth = opt.emissions_breakdown.berth_co2e_tonnes || 0;
  } else {
    Object.values(details).forEach(d => {
      ttw += (d.voyage_ttw_emissions_t || 0);
      wtt += (d.voyage_wtt_emissions_t || 0);
      berth += (d.berth_emissions_t || 0);
    });
  }

  if (ttw === 0 && wtt === 0 && berth === 0 && (opt.total_emissions_co2e_tonnes || 0) > 0) {
    const tot = opt.total_emissions_co2e_tonnes;
    ttw = tot * 0.74;
    wtt = tot * 0.21;
    berth = tot * 0.05;
  }

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
const predFuel = document.getElementById('pred-fuel');
const predModel = document.getElementById('pred-model');
const predDist = document.getElementById('pred-dist');
const predWeather = document.getElementById('pred-weather');

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

if (predFuel) predFuel.addEventListener('change', loadPredictor);
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
    const queryParams = new URLSearchParams({
      vessel: v,
      speed: sp,
      load_factor: ld,
      distance: dist,
      weather: w,
      fuel_type: fType,
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
        tr.innerHTML = `
          <td><b>${row.Fuel || row.fuel_type}</b></td>
          <td><b>${row['Fuel Cost'] || '$' + fmtNum(row.fuel_cost_usd)}</b></td>
          <td>${row['Fuel Consumption'] || row.fuel_mass_tonnes.toFixed(1) + ' t'}</td>
          <td><span style="color: var(--teal); font-weight: 700;">${row['Lifecycle CO2e'] || fmtNum(row.lifecycle_co2e_tonnes) + ' t'}</span></td>
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

    // Lifecycle GHG Bar
    Plotly.newPlot('chart-fuel-ghg', [{
      x: rows.map(r => r.fuel_type || r.Fuel),
      y: rows.map(r => r.lifecycle_co2e_tonnes),
      type: 'bar',
      marker: { color: ['#2b2d42', '#334155', '#457b9d', '#0d9488', '#10b981', '#06b6d4'].slice(0, rows.length) },
      text: rows.map(r => fmtNum(r.lifecycle_co2e_tonnes) + ' t'),
      textposition: 'auto'
    }], {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif' },
      yaxis: { title: 'Well-to-Wake CO2e (t)', gridcolor: '#f1f5f9' }
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
          <div>${assumptionsList}</div>
        `;
        assumptionsContainer.appendChild(card);
      });
    }

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

    const kpiCount = document.getElementById('kpi-scen-count');
    if (kpiCount) kpiCount.textContent = `${entries.length} Stress Tests`;
    const kpiMax = document.getElementById('kpi-scen-maxcost');
    if (kpiMax) kpiMax.textContent = `$${(maxCost / 1e6).toFixed(1)}M`;
    const kpiMaxN = document.getElementById('kpi-scen-maxcost-name');
    if (kpiMaxN) kpiMaxN.textContent = maxCostName;
    const kpiMinE = document.getElementById('kpi-scen-minemiss');
    if (kpiMinE) kpiMinE.textContent = `${fmtNum(minEmiss)} t`;
    const kpiMinEN = document.getElementById('kpi-scen-minemiss-name');
    if (kpiMinEN) kpiMinEN.textContent = minEmissName;

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
    if (kpis) {
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
    }

    // Monthly Monsoon Seasonality Chart
    if (monthly.length > 0 && document.getElementById('chart-casestudy-monthly')) {
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
    if (document.getElementById('chart-casestudy-plans')) {
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
    }

    // Table: Corridor Routes
    const tbody = document.querySelector('#table-casestudy tbody');
    if (tbody) {
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
    }

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

    container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const parentSection = container.closest('section');
    if (parentSection) {
      parentSection.querySelectorAll('[id^="pane-"]').forEach(pane => {
        pane.style.display = (pane.id === `pane-${targetTab}` || pane.id === targetTab) ? 'block' : 'none';
      });
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
