import React, { useEffect, useState } from "react";
import axios from "axios";

import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from "chart.js";

import { Line } from "react-chartjs-2";

ChartJS.register(
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend
);

const API_URL = "http://localhost:8000";

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [readings, setReadings] = useState([]);
  const [history, setHistory] = useState([]);
  const [injections, setInjections] = useState([]);
  const [lastSync, setLastSync] = useState(null);

  const sitePositions = {
    ESP01: { top: "76%", left: "19%" },
    ESP02: { top: "56%", left: "36%" },
    ESP03: { top: "87%", left: "11%" },
    ESP04: { top: "30%", left: "49%" },
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [dashboardResponse, latestResponse, historyResponse] =
          await Promise.all([
            axios.get(`${API_URL}/dashboard`),
            axios.get(`${API_URL}/readings/latest`),
            axios.get(`${API_URL}/readings/history?refresh=${Date.now()}`),
          ]);

        setDashboard(dashboardResponse.data);
        setReadings(latestResponse.data.readings || []);
        setHistory(historyResponse.data.readings || []);
        setInjections(historyResponse.data.injections || []);
        setLastSync(new Date());
      } catch (error) {
        console.error("Erreur lors du rafraîchissement du dashboard :", error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!dashboard) {
    return <div className="loading">Chargement du dashboard...</div>;
  }

  const summary = dashboard.summary || {};

  const buildChart = (field, label) => {
    const deviceColors = {
      ESP01: "#ff9800",
      ESP02: "#00c8ff",
      ESP03: "#ef4444",
      ESP04: "#00e676",
    };

    const filtered = history
      .filter((reading) => reading.field === field)
      .sort((a, b) => new Date(a.time) - new Date(b.time));

    const devices = [
      ...new Set(filtered.map((reading) => reading.deviceId).filter(Boolean)),
    ];

    const timeline = [...new Set(filtered.map((reading) => reading.time))].slice(-12);

    const labels = timeline.map((time) =>
      new Date(time).toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    );

    const datasets = devices.map((deviceId) => {
      const deviceReadings = filtered.filter(
        (reading) => reading.deviceId === deviceId
      );

      const values = timeline.map((time) => {
        const reading = deviceReadings.find((item) => item.time === time);
        return reading ? Number(reading.value) : null;
      });

      const color = deviceColors[deviceId] || "#ffffff";

      return {
        label: `${label} - ${deviceId}`,
        data: values,
        borderColor: color,
        backgroundColor: `${color}33`,
        tension: 0.35,
        borderWidth: 3,
        pointRadius: 4,
        pointHoverRadius: 7,
        spanGaps: true,
        fill: false,
      };
    });

    const thresholdConfig = {
      temperature: [
        { label: "Seuil critique : 50 °C", value: 50, color: "#ef4444" },
      ],
      humidity: [
        { label: "Seuil bas : 20 %", value: 20, color: "#f59e0b" },
        { label: "Seuil haut : 85 %", value: 85, color: "#ef4444" },
      ],
      co2: [
        { label: "Seuil critique : 1500 ppm", value: 1500, color: "#ef4444" },
      ],
    };

    const thresholdDatasets = (thresholdConfig[field] || []).map((threshold) => ({
      label: threshold.label,
      data: labels.map(() => threshold.value),
      borderColor: threshold.color,
      backgroundColor: threshold.color,
      borderWidth: 2,
      borderDash: [8, 6],
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
      fill: false,
    }));

    return {
      labels,
      datasets: [...datasets, ...thresholdDatasets],
    };
  };

  const getDeviceStatus = (device) => {
    const temp = Number(device.values?.temperature);
    const humidity = Number(device.values?.humidity);
    const co2 = Number(device.values?.co2);
    const battery = Number(device.values?.battery);
    const signal = Number(device.values?.signal);
    const fraudScore = Number(device.values?.fraudScore) || 0;

    const isFraud =
      fraudScore > 50 ||
      temp > 50 ||
      humidity < 20 ||
      humidity > 85 ||
      co2 > 1500;

    const isMaintenance = !isFraud && (battery < 15 || signal < -85);

    if (isFraud) return { label: "Fraude", className: "critical" };
    if (isMaintenance) return { label: "Maintenance", className: "maintenance" };
    return { label: "Normal", className: "normal" };
  };

  const getStatusTooltip = (device) => {
    const temp = Number(device.values?.temperature);
    const humidity = Number(device.values?.humidity);
    const co2 = Number(device.values?.co2);
    const battery = Number(device.values?.battery);
    const signal = Number(device.values?.signal);
    const fraudScore = Number(device.values?.fraudScore) || 0;
    const details = [];

    if (fraudScore > 50) details.push(`Score fraude élevé : ${fraudScore}`);
    if (temp > 50) details.push(`Température critique : ${temp} °C`);
    if (humidity < 20) details.push(`Humidité trop basse : ${humidity} %`);
    if (humidity > 85) details.push(`Humidité trop élevée : ${humidity} %`);
    if (co2 > 1500) details.push(`CO₂ critique : ${co2} ppm`);
    if (battery < 15) details.push(`Batterie faible : ${battery} %`);
    if (signal < -85) details.push(`Signal faible : ${signal} dBm`);

    return details.length
      ? details.join(" | ")
      : "État normal — Température attendue : 34-40 °C | Humidité : 52-70 % | CO₂ : 480-850 ppm";
  };

  const getStatusReason = (device) => {
    const temp = Number(device.values?.temperature);
    const humidity = Number(device.values?.humidity);
    const co2 = Number(device.values?.co2);
    const battery = Number(device.values?.battery);
    const signal = Number(device.values?.signal);
    const fraudScore = Number(device.values?.fraudScore) || 0;
    const reasons = [];

    if (fraudScore > 50) reasons.push(`score de fraude ${fraudScore}`);
    if (temp > 50) reasons.push(`température ${temp} °C`);
    if (humidity < 20) reasons.push(`humidité basse ${humidity} %`);
    if (humidity > 85) reasons.push(`humidité élevée ${humidity} %`);
    if (co2 > 1500) reasons.push(`CO₂ élevé ${co2} ppm`);
    if (battery < 15) reasons.push(`batterie faible ${battery} %`);
    if (signal < -85) reasons.push(`signal faible ${signal} dBm`);

    return reasons.length
      ? reasons.join(" • ")
      : "Toutes les mesures sont dans les seuils normaux";
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#ffffff" } },
      tooltip: { mode: "index", intersect: false },
    },
    interaction: { mode: "nearest", axis: "x", intersect: false },
    scales: {
      x: {
        ticks: { color: "#cbd5e1" },
        grid: { color: "#334155" },
      },
      y: {
        beginAtZero: false,
        ticks: { color: "#cbd5e1" },
        grid: { color: "#334155" },
      },
    },
  };

  const buildDeviceCards = () => {
    const devices = {};

    readings.forEach((reading) => {
      if (!reading.deviceId) return;

      if (!devices[reading.deviceId]) {
        devices[reading.deviceId] = {
          deviceId: reading.deviceId,
          site: reading.site || "-",
          values: {},
          lastTime: reading.time,
        };
      }

      devices[reading.deviceId].values[reading.field] = reading.value;

      if (
        !devices[reading.deviceId].lastTime ||
        new Date(reading.time) > new Date(devices[reading.deviceId].lastTime)
      ) {
        devices[reading.deviceId].lastTime = reading.time;
      }

      if (reading.site) devices[reading.deviceId].site = reading.site;
    });

    return Object.values(devices).sort(
      (a, b) => new Date(b.lastTime) - new Date(a.lastTime)
    );
  };

  const deviceCards = buildDeviceCards();
  const uniqueLatestAlerts = [];
  const seenAlerts = new Set();

  for (const alert of dashboard.latestAlerts || []) {
    const alertType = (alert.type || "").trim().toUpperCase();
    if (alertType === "TEST_CLI") continue;

    const alertKey = [
      String(alert.deviceId || "device-inconnu").trim().toUpperCase(),
      String(alert.site || "site-inconnu").trim().toUpperCase(),
      alertType || "ALERTE",
    ].join("|");

    if (!seenAlerts.has(alertKey)) {
      seenAlerts.add(alertKey);
      uniqueLatestAlerts.push(alert);
    }

    if (uniqueLatestAlerts.length === 5) break;
  }

  return (
    <main className="dashboard">
      <header className="header">
        <div>
          <h1>CocoaSecure Dashboard</h1>
          <p>Supervision IoT du séchage du cacao</p>
        </div>

        <div className="header-status">
          <span className="status">API connectée</span>
          <small className="last-sync">
            Dernière synchronisation :{" "}
            <strong>
              {lastSync
                ? lastSync.toLocaleTimeString("fr-FR", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                : "--:--:--"}
            </strong>
          </small>
        </div>
      </header>

      <section className="cards">
        <div className="card" title="Nombre de paquets complets de mesures reçus pendant les dernières 24 heures.">
          <p>Injections sur 24 h</p>
          <h2>{summary.injections24h ?? 0}</h2>
        </div>
        <div className="card danger" title="Nombre de fraudes critiques détectées pendant les dernières 24 heures.">
          <p>Alertes critiques sur 24 h</p>
          <h2>{summary.criticalAlerts24h ?? 0}</h2>
        </div>
        <div className="card" title="Nombre de capteurs ayant transmis au moins une mesure pendant les dernières 24 heures.">
          <p>Capteurs actifs</p>
          <h2>{summary.activeSensors ?? 0}</h2>
        </div>
        <div className="card" title="Nombre de sites distincts ayant transmis des données pendant les dernières 24 heures.">
          <p>Sites supervisés</p>
          <h2>{summary.supervisedSites ?? 0}</h2>
        </div>
      </section>

      <section className="charts">
        <div className="panel">
          <h2>Température</h2>
          <div style={{ height: "280px" }}>
            <Line data={buildChart("temperature", "Température °C")} options={chartOptions} />
          </div>
        </div>
        <div className="panel">
          <h2>Humidité</h2>
          <div style={{ height: "280px" }}>
            <Line data={buildChart("humidity", "Humidité %")} options={chartOptions} />
          </div>
        </div>
        <div className="panel">
          <h2>CO₂</h2>
          <div style={{ height: "280px" }}>
            <Line data={buildChart("co2", "CO₂ ppm")} options={chartOptions} />
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Capteurs IoT en temps réel</h2>
        <div className="device-grid">
          {deviceCards.map((device) => {
            const status = getDeviceStatus(device);
            return (
              <div className="device-card" key={device.deviceId}>
                <div className="device-header">
                  <h3>{device.deviceId}</h3>
                  <span className="online">En ligne</span>
                </div>
                <p className="site">{device.site}</p>
                <div className="device-values">
                  <p>🌡 Température : <strong>{device.values.temperature ?? "-"} °C</strong></p>
                  <p>💧 Humidité : <strong>{device.values.humidity ?? "-"} %</strong></p>
                  <p>🫧 CO₂ : <strong>{device.values.co2 ?? "-"} ppm</strong></p>
                  <p>🔋 Batterie : <strong>{device.values.battery ?? "-"} %</strong></p>
                  <p>📶 Signal : <strong>{device.values.signal ?? "-"} dBm</strong></p>
                </div>

                <div className="device-status-block">
                  <p>
                    État :{" "}
                    <span className={`state ${status.className}`} title={getStatusTooltip(device)}>
                      {status.label}
                    </span>
                  </p>
                  <span className={`reason-badge ${status.className}`} title={getStatusTooltip(device)}>
                    {status.className === "critical" && "⚠ "}
                    {status.className === "maintenance" && "🔧 "}
                    {status.className === "normal" && "✓ "}
                    {getStatusReason(device)}
                  </span>
                </div>

                <small>
                  Dernière mesure :{" "}
                  {device.lastTime ? new Date(device.lastTime).toLocaleString("fr-FR") : "-"}
                </small>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <h2>Carte des sites de supervision</h2>
        <div className="sites-layout">
          <div className="sites-map">
            {deviceCards.map((device) => {
              const status = getDeviceStatus(device);
              const position = sitePositions[device.deviceId] || { top: "50%", left: "50%" };
              return (
                <div
                  key={device.deviceId}
                  className="site-marker"
                  style={{ top: position.top, left: position.left }}
                  title={`${device.deviceId} — ${device.site} — ${status.label}\n${getStatusTooltip(device)}`}
                >
                  <span className={`site-dot ${status.className}`} />
                  <strong>{device.site}</strong>
                </div>
              );
            })}
          </div>
          <div className="sites-legend">
            <h3>Légende</h3>
            <p><span className="legend-dot normal" />Site normal</p>
            <p><span className="legend-dot maintenance" />Site en maintenance</p>
            <p><span className="legend-dot critical" />Site avec fraude détectée</p>
            <p>📡 Capteurs IoT actifs</p>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Tableau de supervision des capteurs</h2>
        <div className="sensor-table">
          <div className="sensor-row sensor-head">
            <span>Device</span><span>Site</span><span>Température</span><span>Humidité</span>
            <span>CO₂</span><span>Batterie</span><span>Signal</span><span>État</span>
          </div>
          {deviceCards.map((device) => {
            const status = getDeviceStatus(device);
            return (
              <div className="sensor-row" key={device.deviceId}>
                <span>{device.deviceId}</span><span>{device.site}</span>
                <span>{device.values.temperature ?? "-"} °C</span>
                <span>{device.values.humidity ?? "-"} %</span>
                <span>{device.values.co2 ?? "-"} ppm</span>
                <span>{device.values.battery ?? "-"} %</span>
                <span>{device.values.signal ?? "-"} dBm</span>
                <span className={`state ${status.className}`} title={getStatusTooltip(device)}>{status.label}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <h2>Historique des dernières injections</h2>
        <div className="history-table">
          <div className="history-row history-head">
            <span>Heure</span><span>Device</span><span>Site</span><span>Température</span>
            <span>Humidité</span><span>CO₂</span><span>État</span>
          </div>
          {injections.length === 0 ? (
            <div className="empty-message">Aucune injection disponible.</div>
          ) : (
            [...injections]
              .sort((a, b) => new Date(b.time) - new Date(a.time))
              .slice(0, 10)
              .map((injection) => {
              const status = getDeviceStatus(injection);
              return (
                <div className="history-row" key={`${injection.deviceId}-${injection.time}`}>
                  <span>{injection.time ? new Date(injection.time).toLocaleTimeString("fr-FR") : "-"}</span>
                  <span>{injection.deviceId || "-"}</span><span>{injection.site || "-"}</span>
                  <span>{injection.values?.temperature ?? "-"} °C</span>
                  <span>{injection.values?.humidity ?? "-"} %</span>
                  <span>{injection.values?.co2 ?? "-"} ppm</span>
                  <span className={`state ${status.className}`} title={getStatusTooltip(injection)}>{status.label}</span>
                </div>
              );
            })
          )}
        </div>
      </section>

      <section className="panel">
        <h2>Dernières alertes</h2>
        <div className="alerts">
          {uniqueLatestAlerts.length === 0 ? (
            <div className="empty-message">Aucune alerte récente.</div>
          ) : (
            uniqueLatestAlerts.map((alert, index) => {
              const alertType = (alert.type || "ALERTE").trim().toUpperCase();

              const rawCauses = Array.isArray(alert.alerts)
                ? alert.alerts
                : [];

              const visibleCauses =
                rawCauses.length > 0
                  ? rawCauses.join(" • ")
                  : alert.fraudScore !== undefined
                    ? `Anomalie détectée — score de fraude : ${alert.fraudScore}`
                    : "Anomalie détectée sur les données du capteur";

              const tooltipParts = [
                `Type : ${alertType}`,
                `Capteur : ${alert.deviceId || "inconnu"}`,
                `Site : ${alert.site || "inconnu"}`,
                `Cause : ${visibleCauses}`,
              ];

              if (alert.fraudScore !== undefined) {
                tooltipParts.push(`Score fraude : ${alert.fraudScore}`);
              }

              return (
                <div
                  className="alert"
                  key={alert.createdAt || `${alert.deviceId}-${alert.site}-${index}`}
                  title={tooltipParts.join("\n")}
                >
                  <div>
                    <strong>{alertType}</strong>

                    <p>
                      {alert.deviceId || "Device inconnu"} —{" "}
                      {alert.site || "Site inconnu"}
                    </p>

                    <p>{visibleCauses}</p>

                    {alert.createdAt && (
                      <small>
                        {new Date(alert.createdAt).toLocaleString("fr-FR")}
                      </small>
                    )}
                  </div>

                  <span>{alert.niveau || "INFO"}</span>
                </div>
              );
            })
          )}
        </div>
      </section>
    </main>
  );
}

export default App;