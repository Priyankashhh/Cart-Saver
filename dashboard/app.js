// CartSaver Dashboard Core Logic

document.addEventListener('DOMContentLoaded', () => {
  // Try to load initial data
  loadDashboardData();
  
  // Bind refresh button
  const refreshBtn = document.getElementById('refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', handleRefresh);
  }
});

// Fallback Mock Data in case of network or CORS issues
const fallbackData = {
  "generated_at": new Date().toISOString(),
  "kpis": {
    "revenue": 34566.0,
    "revenue_target": 50000,
    "revenue_achievement": 69.13,
    "revenue_gap": -15434.0,
    "revenue_at_risk": 1099.0,
    "recovery_low": 329.7,
    "recovery_high": 549.5,
    "cvr": 93.33,
    "retention_rate": 93.33,
    "abandonment_rate": 6.67,
    "roas": 46459.68,
    "total_users": 15,
    "purchasers": 14,
    "abandoners": 1,
    "total_conversions": 21,
    "total_offers_sent": 72,
    "notification_cost": 0.744,
    "emails_sent": 24,
    "sms_sent": 24,
    "whatsapp_sent": 24
  },
  "funnel": [
    { "stage": "product_view", "users": 15 },
    { "stage": "add_to_cart", "users": 15 },
    { "stage": "checkout_started", "users": 13 },
    { "stage": "purchase", "users": 14 }
  ],
  "dropoffs": [
    { "from": "product_view", "to": "add_to_cart", "from_users": 15, "to_users": 15, "dropoff_pct": 0.0 },
    { "from": "add_to_cart", "to": "checkout_started", "from_users": 15, "to_users": 13, "dropoff_pct": 13.33 },
    { "from": "checkout_started", "to": "purchase", "from_users": 13, "to_users": 14, "dropoff_pct": -7.69 }
  ],
  "offer_performance": [
    { "tier": "10% Discount", "sent": 36, "conversions": 13, "conversion_rate": 36.11 },
    { "tier": "15% Discount", "sent": 9, "conversions": 3, "conversion_rate": 33.33 },
    { "tier": "5% Discount", "sent": 27, "conversions": 5, "conversion_rate": 18.52 }
  ],
  "segments": {
    "Very High Intent": 0,
    "High Intent": 1,
    "Low Intent": 0,
    "Converted": 14
  },
  "revenue_by_category": [
    { "category": "Footwear", "revenue": 9995.0 },
    { "category": "Electronics", "revenue": 8994.0 },
    { "category": "Fitness", "revenue": 3495.0 },
    { "category": "Clothing", "revenue": 3196.0 },
    { "category": "Home", "revenue": 2997.0 },
    { "category": "Accessories", "revenue": 2996.0 },
    { "category": "Kitchen", "revenue": 1497.0 },
    { "category": "Grocery", "revenue": 1396.0 }
  ],
  "top_abandoned_products": [
    { "product": "Running Shoes X200", "count": 1 },
    { "product": "Leather Wallet Classic", "count": 1 },
    { "product": "Bluetooth Speaker Mini", "count": 1 },
    { "product": "Bamboo Sunglasses", "count": 1 }
  ],
  "executive_briefing": [
    {
      "icon": "$",
      "title": "Revenue Performance",
      "description": "Revenue is currently at $34,566, which is 69.13% of the target. This indicates a significant shortfall. The company needs to focus on increasing revenue to meet the target.",
      "impact": "HIGH IMPACT",
      "confidence": "90%",
      "priority": 1,
      "action": "Analyze and optimize pricing strategy to increase revenue"
    },
    {
      "icon": "funnel",
      "title": "Checkout Funnel Drop-off",
      "description": "There is a 13.33% drop-off from the 'add_to_cart' stage to the 'checkout_started' stage. This indicates a potential issue with the checkout process. The company needs to investigate and address the cause of this drop-off.",
      "impact": "MEDIUM IMPACT",
      "confidence": "80%",
      "priority": 2,
      "action": "Conduct user testing to identify and fix checkout process issues"
    },
    {
      "icon": "chart",
      "title": "Offer Conversion Performance",
      "description": "The conversion rate from offers is 29.17% (21 conversions from 72 offers). This indicates a relatively low conversion rate. The company needs to optimize the offer strategy to increase conversions.",
      "impact": "MEDIUM IMPACT",
      "confidence": "85%",
      "priority": 3,
      "action": "Analyze offer performance and optimize offer targeting and content"
    },
    {
      "icon": "target",
      "title": "Abandoned Products",
      "description": "There are four products with one abandonment each, indicating a potential issue with these products. The company needs to investigate and address the cause of these abandonments.",
      "impact": "MEDIUM IMPACT",
      "confidence": "75%",
      "priority": 4,
      "action": "Analyze product performance and optimize product pages for the abandoned products"
    }
  ]
};

// Global chart references so we can destroy them on reload
let funnelChart = null;
let categoryChart = null;
let offerChart = null;
let healthChart = null;

/**
 * Loads dashboard data from the json file.
 */
async function loadDashboardData() {
  try {
    // Fetch data.json with a timestamp to avoid caching
    const response = await fetch(`data.json?t=${new Date().getTime()}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    console.log("Loaded data.json successfully:", data);
    renderDashboard(data);
  } catch (error) {
    console.warn("Failed to fetch data.json, falling back to mock data:", error);
    renderDashboard(fallbackData);
    showNotification("Running in Offline/Fallback Mode. Start the server via 'run_dashboard.py' for live updates.", "warning");
  }
}

/**
 * Main render orchestrator
 */
function renderDashboard(data) {
  // Update timestamp
  const generatedAt = new Date(data.generated_at);
  document.getElementById('last-updated').textContent = `Last Refreshed: ${generatedAt.toLocaleString()}`;

  // Render elements
  renderKPIs(data.kpis);
  renderBusinessHealth(data.kpis);
  renderFunnelChart(data.funnel, data.dropoffs);
  renderCategorySalesChart(data.revenue_by_category);
  renderOfferPerformanceChart(data.offer_performance);
  renderIntentCohorts(data.segments, data.kpis.total_users);
  renderTopAbandoned(data.top_abandoned_products);
  renderCampaignChannels(data.kpis);
  renderAIExecutiveBriefing(data.executive_briefing);

  // Trigger Lucide icons replacing
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

/**
 * Population of Top KPIs
 */
function renderKPIs(kpis) {
  // Format currency helper
  const fmtCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
  
  // Total Revenue
  document.getElementById('kpi-revenue').innerHTML = fmtCurrency(kpis.revenue);
  document.getElementById('revenue-achievement').innerHTML = 
    `<span class="trend-up"><i data-lucide="trending-up"></i> ${kpis.revenue_achievement}%</span> of target ($${(kpis.revenue_target/1000)}k)`;

  // Conversion Rate (CVR)
  document.getElementById('kpi-cvr').textContent = `${kpis.cvr}%`;
  document.getElementById('cvr-details').innerHTML = 
    `<span class="trend-up"><i data-lucide="users"></i> ${kpis.purchasers}</span> buyers / ${kpis.total_users} visitors`;

  // Revenue At Risk
  document.getElementById('kpi-at-risk').textContent = fmtCurrency(kpis.revenue_at_risk);
  document.getElementById('risk-details').innerHTML = 
    `<span class="trend-down"><i data-lucide="alert-circle"></i> ${kpis.abandonment_rate}%</span> cart abandonment`;

  // Recovery Opportunity
  document.getElementById('kpi-recovery').textContent = `${fmtCurrency(kpis.recovery_low)} - ${fmtCurrency(kpis.recovery_high)}`;
  document.getElementById('recovery-details').innerHTML = 
    `<span class="trend-up"><i data-lucide="sparkles"></i> 30% - 50%</span> target recovery rate`;
}

/**
 * Business Health Score calculation and Gauge
 */
function renderBusinessHealth(kpis) {
  // Calculate health score (weighted combination of retention and target achievement)
  // Let's use: 0.6 * Retention Rate + 0.4 * Revenue Achievement (capped at 100)
  const retentionWeight = kpis.retention_rate || 0;
  const achievementWeight = Math.min(kpis.revenue_achievement, 100);
  const healthScore = Math.round(0.6 * retentionWeight + 0.4 * achievementWeight);

  let statusClass = "good";
  let statusText = "Good Health";
  if (healthScore >= 90) {
    statusClass = "excellent";
    statusText = "Excellent Health";
  } else if (healthScore < 75) {
    statusClass = "warning";
    statusText = "Risk Detected";
  }

  // Update status badge
  const badgeEl = document.getElementById('health-badge');
  badgeEl.className = `health-status-badge ${statusClass}`;
  badgeEl.textContent = statusText;

  document.getElementById('health-score-val').textContent = `${healthScore}`;

  // Gauge options
  const options = {
    series: [healthScore],
    chart: {
      type: 'radialBar',
      height: 180,
      sparkline: { enabled: true }
    },
    plotOptions: {
      radialBar: {
        startAngle: -90,
        endAngle: 90,
        track: {
          background: "rgba(255, 255, 255, 0.05)",
          strokeWidth: '97%',
          margin: 5,
        },
        dataLabels: {
          name: { show: false },
          value: {
            offsetY: -2,
            fontSize: '22px',
            fontFamily: 'Outfit, sans-serif',
            fontWeight: 'bold',
            color: '#fff',
            formatter: function(val) { return val + "%"; }
          }
        }
      }
    },
    fill: {
      type: 'gradient',
      gradient: {
        shade: 'dark',
        type: 'horizontal',
        gradientToColors: [statusClass === 'excellent' ? '#10b981' : (statusClass === 'good' ? '#3b82f6' : '#f59e0b')],
        stops: [0, 100]
      }
    },
    colors: ['#8b5cf6'],
    stroke: { lineCap: 'round' }
  };

  if (healthChart) {
    healthChart.destroy();
  }
  healthChart = new ApexCharts(document.querySelector("#health-gauge-chart"), options);
  healthChart.render();
}

/**
 * Funnel Chart (Horizontal Bar Chart)
 */
function renderFunnelChart(funnel, dropoffs) {
  // Sort stages
  const stagesMap = {
    "product_view": "1. Views",
    "add_to_cart": "2. Carts",
    "checkout_started": "3. Checkouts",
    "purchase": "4. Purchases"
  };

  const categories = funnel.map(f => stagesMap[f.stage] || f.stage);
  const data = funnel.map(f => f.users);

  const options = {
    series: [{
      name: 'Unique Users',
      data: data
    }],
    chart: {
      type: 'bar',
      height: 280,
      toolbar: { show: false }
    },
    plotOptions: {
      bar: {
        horizontal: true,
        barHeight: '55%',
        borderRadius: 4,
        distributed: true,
        dataLabels: {
          position: 'center'
        }
      }
    },
    colors: ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981'],
    dataLabels: {
      enabled: true,
      textAnchor: 'middle',
      style: {
        colors: ['#fff'],
        fontSize: '11px',
        fontFamily: 'Inter, sans-serif',
        fontWeight: 'bold'
      },
      formatter: function (val, opt) {
        return `${val} users`;
      }
    },
    xaxis: {
      categories: categories,
      labels: {
        style: { colors: '#6b7280', fontSize: '10px' }
      },
      axisBorder: { show: false },
      axisTicks: { show: false }
    },
    yaxis: {
      labels: {
        style: { colors: '#f3f4f6', fontSize: '11px', fontWeight: 600 }
      }
    },
    grid: {
      borderColor: 'rgba(255,255,255,0.04)',
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: false } }
    },
    legend: { show: false },
    tooltip: {
      theme: 'dark',
      y: {
        formatter: function(val, opt) {
          const index = opt.dataPointIndex;
          if (index === 0) return `${val} Users (Baseline)`;
          
          // Get dropoff rate
          const drop = dropoffs[index - 1];
          if (drop) {
            const label = drop.dropoff_pct < 0 
              ? `Reactivation Conversion: +${Math.abs(drop.dropoff_pct)}%` 
              : `Drop-off: -${drop.dropoff_pct}%`;
            return `${val} Users (${label})`;
          }
          return `${val} Users`;
        }
      }
    }
  };

  if (funnelChart) {
    funnelChart.destroy();
  }
  funnelChart = new ApexCharts(document.querySelector("#funnel-chart"), options);
  funnelChart.render();
}

/**
 * Category Sales Donut Chart
 */
function renderCategorySalesChart(categories) {
  // Sort and limit categories
  const sorted = [...categories].sort((a,b) => b.revenue - a.revenue);
  const labels = sorted.map(c => c.category);
  const series = sorted.map(c => c.revenue);

  const options = {
    series: series,
    labels: labels,
    chart: {
      type: 'donut',
      height: 250,
      foreColor: '#9ca3af'
    },
    stroke: { colors: ['#111827'], width: 2 },
    colors: ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#6b7280', '#1f2937'],
    legend: {
      position: 'bottom',
      fontSize: '11px',
      fontFamily: 'Inter, sans-serif',
      markers: { radius: 4 }
    },
    dataLabels: { enabled: false },
    plotOptions: {
      pie: {
        donut: {
          size: '70%',
          labels: {
            show: true,
            name: { show: true, fontSize: '12px', fontFamily: 'Outfit, sans-serif', fontWeight: 600, color: '#9ca3af' },
            value: {
              show: true,
              fontSize: '18px',
              fontFamily: 'Outfit, sans-serif',
              fontWeight: 800,
              color: '#fff',
              formatter: function(val) { return '$' + Number(val).toLocaleString(); }
            },
            total: {
              show: true,
              label: 'Total Revenue',
              color: '#9ca3af',
              formatter: function (w) {
                const sum = w.globals.seriesTotals.reduce((a, b) => a + b, 0);
                return '$' + Math.round(sum).toLocaleString();
              }
            }
          }
        }
      }
    },
    tooltip: {
      theme: 'dark',
      y: {
        formatter: function(val) { return '$' + Number(val).toLocaleString(); }
      }
    }
  };

  if (categoryChart) {
    categoryChart.destroy();
  }
  categoryChart = new ApexCharts(document.querySelector("#category-chart"), options);
  categoryChart.render();
}

/**
 * Offer Performance Chart
 */
function renderOfferPerformanceChart(offers) {
  const categories = offers.map(o => o.tier);
  const convRates = offers.map(o => o.conversion_rate);
  const sentCounts = offers.map(o => o.sent);

  const options = {
    series: [
      {
        name: 'Conversion Rate',
        type: 'column',
        data: convRates
      },
      {
        name: 'Offers Sent',
        type: 'line',
        data: sentCounts
      }
    ],
    chart: {
      height: 250,
      type: 'line',
      toolbar: { show: false },
      foreColor: '#9ca3af'
    },
    stroke: {
      width: [0, 3],
      curve: 'smooth'
    },
    plotOptions: {
      bar: {
        columnWidth: '40%',
        borderRadius: 4
      }
    },
    colors: ['#10b981', '#8b5cf6'],
    dataLabels: {
      enabled: true,
      enabledOnSeries: [0],
      formatter: function (val) { return val + "%"; },
      style: { fontSize: '10px', fontFamily: 'Inter' }
    },
    grid: {
      borderColor: 'rgba(255,255,255,0.04)'
    },
    xaxis: {
      categories: categories,
      axisBorder: { show: false },
      axisTicks: { show: false }
    },
    yaxis: [
      {
        title: {
          text: 'Conversion Rate (%)',
          style: { color: '#10b981', fontWeight: 600 }
        },
        labels: {
          formatter: function (val) { return val + "%"; }
        }
      },
      {
        opposite: true,
        title: {
          text: 'Offers Sent',
          style: { color: '#8b5cf6', fontWeight: 600 }
        }
      }
    ],
    tooltip: {
      theme: 'dark',
      shared: true,
      intersect: false
    },
    legend: {
      position: 'top',
      horizontalAlign: 'right'
    }
  };

  if (offerChart) {
    offerChart.destroy();
  }
  offerChart = new ApexCharts(document.querySelector("#offer-chart"), options);
  offerChart.render();
}

/**
 * Customer Segmentation (Rule Based)
 */
function renderIntentCohorts(segments, totalUsers) {
  const container = document.getElementById('intent-cohorts');
  container.innerHTML = '';

  const segmentKeys = [
    { key: "Very High Intent", class: "very-high", icon: "zap", desc: "Viewed 10+, Added Cart, Started Checkout, No Purchase" },
    { key: "High Intent", class: "high", icon: "activity", desc: "Viewed 5+, Added Cart, No Purchase" },
    { key: "Low Intent", class: "low", icon: "eye", desc: "Only viewed products, did not add to cart" },
    { key: "Converted", class: "converted", icon: "check-circle", desc: "Completed purchase successfully" }
  ];

  segmentKeys.forEach(s => {
    const val = segments[s.key] || 0;
    const pct = totalUsers > 0 ? Math.round((val / totalUsers) * 100) : 0;

    const itemHtml = `
      <div class="segment-item">
        <div class="segment-label">
          <span style="display: flex; align-items: center; gap: 0.35rem; font-weight: 600; color: #fff;">
            <i data-lucide="${s.icon}" style="width: 14px; height: 14px;" class="trend-up"></i>
            ${s.key}
          </span>
          <span><strong>${val}</strong> users (${pct}%)</span>
        </div>
        <div class="segment-bar-bg" title="${s.desc}">
          <div class="segment-bar-fill ${s.class}" style="width: ${pct}%"></div>
        </div>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', itemHtml);
  });
}

/**
 * Top Abandoned Products
 */
function renderTopAbandoned(products) {
  const container = document.getElementById('abandoned-products');
  container.innerHTML = '';

  if (!products || products.length === 0) {
    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 1rem;">No abandoned products detected.</div>';
    return;
  }

  products.forEach(p => {
    const itemHtml = `
      <div class="product-item">
        <span class="product-name">${p.product}</span>
        <span class="product-count">
          <i data-lucide="shopping-bag" style="width: 12px; height: 12px;"></i>
          ${p.count}
        </span>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', itemHtml);
  });
}

/**
 * Notification Channel table
 */
function renderCampaignChannels(kpis) {
  const container = document.getElementById('channel-body');
  container.innerHTML = '';

  // Costs
  const emailCost = 0.001;
  const smsCost = 0.01;
  const waCost = 0.02;

  const channels = [
    { name: "Email", count: kpis.emails_sent, cost: emailCost, tag: "email" },
    { name: "SMS", count: kpis.sms_sent, cost: smsCost, tag: "sms" },
    { name: "WhatsApp", count: kpis.whatsapp_sent, cost: waCost, tag: "whatsapp" }
  ];

  channels.forEach(ch => {
    const totalCost = ch.count * ch.cost;
    const rowHtml = `
      <tr>
        <td><span class="channel-tag ${ch.tag}">${ch.name}</span></td>
        <td><strong>${ch.count}</strong> messages</td>
        <td>$${ch.cost.toFixed(3)}</td>
        <td>$${totalCost.toFixed(2)}</td>
      </tr>
    `;
    container.insertAdjacentHTML('beforeend', rowHtml);
  });

  // ROAS footer summary
  document.getElementById('total-sent-label').textContent = `${kpis.total_offers_sent} sent`;
  document.getElementById('total-cost-label').textContent = `$${kpis.notification_cost.toFixed(2)}`;
  document.getElementById('total-conv-label').textContent = `${kpis.total_conversions} conv`;
  document.getElementById('roas-label').textContent = `${kpis.roas.toLocaleString()}x`;
}

/**
 * AI Executive Briefing insights rendering
 */
function renderAIExecutiveBriefing(briefing) {
  const container = document.getElementById('briefing-container');
  container.innerHTML = '';

  if (!briefing || briefing.length === 0) {
    container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; text-align: center; grid-column: span 4; padding: 2rem;">No insights generated. Ensure the database has records and run server.</div>';
    return;
  }

  // Icon mapping helper
  const getIconClass = (iconStr) => {
    switch (iconStr) {
      case "$": return "dollar-sign";
      case "funnel": return "filter";
      case "target": return "target";
      case "chart": return "trending-up";
      default: return "info";
    }
  };

  // Limit briefing to 4 items
  const items = briefing.slice(0, 4);

  items.forEach(item => {
    const iconName = getIconClass(item.icon);
    const impactClass = item.impact.toLowerCase().includes('high') ? 'high' : 'medium';
    
    const cardHtml = `
      <div class="card briefing-card">
        <div class="briefing-meta">
          <span class="impact-badge ${impactClass}">${item.impact}</span>
          <span class="briefing-confidence">
            <i data-lucide="gauge" style="width: 12px; height: 12px;"></i>
            Conf: ${item.confidence}
          </span>
        </div>
        <h3 class="briefing-title">
          <i data-lucide="${iconName}" style="width: 16px; height: 16px;"></i>
          ${item.title}
        </h3>
        <p class="briefing-description">${item.description}</p>
        <div class="briefing-action">
          <strong>Recommended Action:</strong><br/>
          ${item.action}
        </div>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', cardHtml);
  });
}

/**
 * Handler for refresh button clicking
 */
async function handleRefresh() {
  const overlay = document.getElementById('loading-overlay');
  const refreshBtn = document.getElementById('refresh-btn');

  // Activate loading
  overlay.classList.add('active');
  refreshBtn.disabled = true;

  try {
    const response = await fetch('/api/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`API error! status: ${response.status}`);
    }

    const resJson = await response.json();
    console.log("Database & AI Refresh completed:", resJson);
    
    // Reload dashboard data
    await loadDashboardData();
    showNotification("Dashboard data refreshed successfully with live db stats & AI Insights!", "success");
  } catch (err) {
    console.error("Refresh request failed:", err);
    showNotification("API Refresh failed. Ensure run_dashboard.py server is running locally.", "danger");
  } finally {
    // Hide overlay
    setTimeout(() => {
      overlay.classList.remove('active');
      refreshBtn.disabled = false;
    }, 4000); // Give enough visual feedback time
  }
}

/**
 * Show a floating temporary alert toast
 */
function showNotification(message, type = "success") {
  const existing = document.getElementById('dashboard-toast');
  if (existing) {
    existing.remove();
  }

  const toast = document.createElement('div');
  toast.id = 'dashboard-toast';
  
  let bg = 'var(--color-success)';
  if (type === 'danger') bg = 'var(--color-danger)';
  if (type === 'warning') bg = 'var(--color-warning)';
  
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: ${bg};
    color: white;
    padding: 0.75rem 1.25rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    font-size: 0.85rem;
    font-weight: 600;
    z-index: 1100;
    transition: opacity 0.3s ease;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  `;
  
  let icon = 'check';
  if (type === 'danger') icon = 'x-circle';
  if (type === 'warning') icon = 'alert-triangle';
  
  toast.innerHTML = `<i data-lucide="${icon}" style="width: 16px; height: 16px;"></i> ${message}`;
  document.body.appendChild(toast);

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Remove toast
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}
