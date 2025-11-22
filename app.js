const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0
});

const hasDocument = typeof document !== 'undefined';
const hasWindow = typeof window !== 'undefined';
const form = hasDocument ? document.getElementById('inputs') : null;
const summaryEl = hasDocument ? document.getElementById('summary') : null;
const tableContainer = hasDocument ? document.getElementById('table-container') : null;
const chartCanvas = hasDocument ? document.getElementById('comparison-chart') : null;
let comparisonChart = null;

if (form) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    updateOutputs();
  });

  // Run a first calculation so the page is populated immediately.
  updateOutputs();
}

function updateOutputs() {
  if (!form) {
    return;
  }

  const data = new FormData(form);
  const values = parseValues(data);
  const results = runProjection(values);
  renderSummary(results, values.analysisYears);
  renderTable(results);
  renderChart(results);
}

function parseValues(data) {
  const getNumber = (name, fallback = 0) => {
    const value = parseFloat(data.get(name));
    return Number.isFinite(value) ? value : fallback;
  };

  return {
    homePrice: getNumber('homePrice', 0),
    downPercent: getNumber('downPercent', 0) / 100,
    closingCostPercent: getNumber('closingCostPercent', 0) / 100,
    loanTermYears: getNumber('loanTermYears', 30),
    interestRate: getNumber('interestRate', 0) / 100,
    analysisYears: Math.max(1, Math.min(40, getNumber('analysisYears', 10))),
    propertyTaxRate: getNumber('propertyTaxRate', 0) / 100,
    insuranceAnnual: getNumber('insuranceAnnual', 0),
    maintenanceRate: getNumber('maintenanceRate', 0) / 100,
    hoaMonthly: getNumber('hoaMonthly', 0),
    appreciationRate: getNumber('appreciationRate', 0) / 100,
    monthlyRent: getNumber('monthlyRent', 0),
    rentGrowthRate: getNumber('rentGrowthRate', 0) / 100
  };
}

function runProjection(values) {
  const {
    homePrice,
    downPercent,
    closingCostPercent,
    loanTermYears,
    interestRate,
    analysisYears,
    propertyTaxRate,
    insuranceAnnual,
    maintenanceRate,
    hoaMonthly,
    appreciationRate,
    monthlyRent,
    rentGrowthRate
  } = values;

  const downPayment = homePrice * downPercent;
  const closingCosts = homePrice * closingCostPercent;
  const loanAmount = Math.max(homePrice - downPayment, 0);
  const monthsTerm = Math.max(loanTermYears * 12, 1);
  const monthlyRate = interestRate / 12;
  let monthlyPayment = 0;

  if (loanAmount > 0 && loanTermYears > 0) {
    if (monthlyRate === 0) {
      monthlyPayment = loanAmount / monthsTerm;
    } else {
      monthlyPayment =
        (loanAmount * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -monthsTerm));
    }
  }

  let balance = loanAmount;
  let ownerCashOut = downPayment + closingCosts;
  let rentCumulative = 0;
  let monthsElapsed = 0;
  const rows = [];

  for (let year = 1; year <= analysisYears; year++) {
    let yearInterest = 0;
    let yearPrincipal = 0;
    let yearMortgagePayment = 0;

    for (let month = 0; month < 12; month++) {
      if (monthsElapsed < monthsTerm && balance > 0) {
        const interestComponent = monthlyRate === 0 ? 0 : balance * monthlyRate;
        let payment = monthlyPayment;
        let principalComponent = payment - interestComponent;

        if (principalComponent > balance) {
          principalComponent = balance;
          payment = principalComponent + interestComponent;
        }

        balance = Math.max(balance - principalComponent, 0);
        yearInterest += interestComponent;
        yearPrincipal += principalComponent;
        yearMortgagePayment += payment;
        monthsElapsed += 1;
      }
    }

    const homeValue = homePrice * Math.pow(1 + appreciationRate, year);
    const propertyTax = homeValue * propertyTaxRate;
    const maintenance = homeValue * maintenanceRate;
    const hoaAnnual = hoaMonthly * 12;
    const ownershipCost = yearMortgagePayment + propertyTax + maintenance + hoaAnnual + insuranceAnnual;
    ownerCashOut += ownershipCost;

    const equity = Math.max(homeValue - balance, 0);
    const ownerNetCost = ownerCashOut - equity;

    const rentThisYear = monthlyRent * 12 * Math.pow(1 + rentGrowthRate, year - 1);
    rentCumulative += rentThisYear;
    const rentVsOwn = rentCumulative - ownerNetCost;

    rows.push({
      year,
      homeValue,
      balance,
      equity,
      ownerCash: ownerCashOut,
      ownerNetCost,
      rentPaid: rentCumulative,
      rentVsOwn
    });
  }

  return {
    downPayment,
    closingCosts,
    rows,
    totals: rows[rows.length - 1]
  };
}

function renderSummary(results, analysisYears) {
  if (!summaryEl) {
    return;
  }

  if (!results.rows.length) {
    summaryEl.innerHTML = '<p>No projection available.</p>';
    return;
  }

  const final = results.totals;
  const diff = final.rentVsOwn;
  const owningAhead = diff > 0;
  const message = owningAhead
    ? `Owning is projected to be ${currency.format(diff)} ahead of renting after ${analysisYears} years.`
    : `Renting is projected to be ${currency.format(Math.abs(diff))} ahead of owning after ${analysisYears} years.`;

  summaryEl.innerHTML = `
    <div class="summary-grid">
      <article class="summary-card">
        <h3>Cash paid by homeowner</h3>
        <p>${currency.format(final.ownerCash)}</p>
      </article>
      <article class="summary-card">
        <h3>Estimated equity</h3>
        <p>${currency.format(final.equity)}</p>
      </article>
      <article class="summary-card">
        <h3>Net cost of owning</h3>
        <p>${currency.format(final.ownerNetCost)}</p>
      </article>
      <article class="summary-card">
        <h3>Rent paid</h3>
        <p>${currency.format(final.rentPaid)}</p>
      </article>
      <article class="summary-card trend-card ${owningAhead ? 'trend-positive' : 'trend-negative'}">
        <h3>Owning vs Renting</h3>
        <p>${owningAhead ? '+' : '-'}${currency.format(Math.abs(diff))}</p>
      </article>
    </div>
    <p>${message}</p>
  `;
}

function renderTable(results) {
  if (!tableContainer) {
    return;
  }

  if (!results.rows.length) {
    tableContainer.innerHTML = '';
    if (comparisonChart) {
      comparisonChart.destroy();
      comparisonChart = null;
    }
    return;
  }

  const header = `
    <thead>
      <tr>
        <th>Year</th>
        <th>Home value</th>
        <th>Mortgage balance</th>
        <th>Equity</th>
        <th>Owner cash paid</th>
        <th>Owner net cost</th>
        <th>Rent paid</th>
        <th>Rent vs Own</th>
      </tr>
    </thead>
  `;

  const rows = results.rows
    .map((row) => {
      return `
        <tr>
          <td>${row.year}</td>
          <td>${currency.format(row.homeValue)}</td>
          <td>${currency.format(row.balance)}</td>
          <td>${currency.format(row.equity)}</td>
          <td>${currency.format(row.ownerCash)}</td>
          <td>${currency.format(row.ownerNetCost)}</td>
          <td>${currency.format(row.rentPaid)}</td>
          <td class="${row.rentVsOwn >= 0 ? 'positive' : 'negative'}">${row.rentVsOwn >= 0 ? '+' : '-'}${currency.format(Math.abs(row.rentVsOwn))}</td>
        </tr>
      `;
    })
    .join('');

  tableContainer.innerHTML = `
    <div class="table-wrapper">
      <table>
        ${header}
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
  }

function renderChart(results) {
  if (!chartCanvas || !hasWindow || !window.Chart) {
    return;
  }

  if (!results.rows.length) {
    if (comparisonChart) {
      comparisonChart.destroy();
      comparisonChart = null;
    }
    return;
  }

  const labels = results.rows.map((row) => `Year ${row.year}`);
  const rentSeries = results.rows.map((row) => row.rentPaid);
  const equitySeries = results.rows.map((row) => row.equity);

  if (comparisonChart) {
    comparisonChart.destroy();
  }

  comparisonChart = new window.Chart(chartCanvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Rent paid (cumulative)',
          data: rentSeries,
          borderColor: '#94a3b8',
          backgroundColor: 'rgba(148, 163, 184, 0.15)',
          borderWidth: 3,
          tension: 0.3,
          fill: true
        },
        {
          label: 'Home equity',
          data: equitySeries,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.15)',
          borderWidth: 3,
          tension: 0.3,
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'bottom'
        },
        tooltip: {
          callbacks: {
            label(context) {
              return `${context.dataset.label}: ${currency.format(context.parsed.y)}`;
            }
          }
        }
      },
      scales: {
        y: {
          ticks: {
            callback: (value) => currency.format(value)
          }
        }
      }
    }
  });
}

if (typeof module !== 'undefined') {
  module.exports = { runProjection };
}
