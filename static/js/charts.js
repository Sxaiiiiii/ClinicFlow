/* Chart.js helpers. All numbers come from the server (MySQL), never hard-coded. */
const CF = { teal: "#0B9C9A", tealDark: "#087E8B", navy: "#12344B", light: "#6FD3D1",
             palette: ["#0B9C9A", "#F5A524", "#1B7FC4", "#12A150", "#E5484D", "#6F4BD8"] };
Chart.defaults.font.family = '"Segoe UI", system-ui, sans-serif';
Chart.defaults.color = "#68839A";

function barChart(canvasId, labels, values, label) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  return new Chart(el, {
    type: "bar",
    data: { labels, datasets: [{ label: label || "Visits", data: values, backgroundColor: CF.light,
                                 hoverBackgroundColor: CF.teal, borderRadius: 8, maxBarThickness: 46 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
               scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#E7EFF3" } }, x: { grid: { display: false } } } },
  });
}
function lineChart(canvasId, labels, values, label) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  return new Chart(el, {
    type: "line",
    data: { labels, datasets: [{ label, data: values, borderColor: CF.teal, backgroundColor: "rgba(11,156,154,.12)", fill: true, tension: .35, pointRadius: 3 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
               scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#E7EFF3" } }, x: { grid: { display: false } } } },
  });
}
function doughnutChart(canvasId, labels, values) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  return new Chart(el, {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: CF.palette, borderWidth: 2 }] },
    options: { maintainAspectRatio: false, cutout: "62%", plugins: { legend: { position: "bottom" } } },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  // Dashboard "Patient Visits Overview" with a range selector
  const dash = document.getElementById("visitsChart");
  if (dash) {
    let chart = null;
    const load = async (days) => {
      const data = await (await fetch("/api/visits?days=" + days, { credentials: "same-origin" })).json();
      if (chart) chart.destroy();
      chart = barChart("visitsChart", data.labels, data.values, "Patient visits");
    };
    const select = document.getElementById("visitsRange");
    select && select.addEventListener("change", () => load(select.value));
    load(select ? select.value : 7);
  }

  // Reports page
  if (window.REPORT) {
    const r = window.REPORT;
    barChart("chartDaily", r.daily.labels, r.daily.values, "Daily visits");
    barChart("chartWeekly", r.weekly.labels, r.weekly.values, "Weekly visits");
    barChart("chartMonthly", r.monthly.labels, r.monthly.values, "Monthly visits");
    doughnutChart("chartAppt", r.appointment_status.labels, r.appointment_status.values);
    doughnutChart("chartQueue", r.queue_status.labels, r.queue_status.values);
    lineChart("chartReg", r.registrations.labels, r.registrations.values, "New patients");
  }
});
