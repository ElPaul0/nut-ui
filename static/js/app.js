(function () {
  const cfg = window.NUT_UI_CONFIG || {};
  const I18N = window.NUT_UI_I18N || {};
  const THEME_KEY = "nut-ui-theme";
  const LANG_KEY = "nut-ui-lang";
  const REFRESH_KEY = "nut-ui-refresh-sec";
  const REFRESH_OPTIONS = [5, 10, 30, 60];

  let theme = localStorage.getItem(THEME_KEY) || cfg.defaultTheme || "dark";
  let lang = localStorage.getItem(LANG_KEY) || cfg.defaultLang || "en";
  let refreshSec = parseInt(localStorage.getItem(REFRESH_KEY) || cfg.defaultRefreshSec || 10, 10);
  if (!REFRESH_OPTIONS.includes(refreshSec)) refreshSec = 10;
  if (!I18N[lang]) lang = "en";
  if (theme !== "light" && theme !== "dark") theme = "dark";

  let refreshTimer = null;
  let shellBuilt = false;
  let lastEventsSig = "";

  function t(key) {
    return (I18N[lang] && I18N[lang][key]) || (I18N.en && I18N.en[key]) || key;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const node = el(id);
    if (!node) return;
    const next = value == null ? "" : String(value);
    if (node.textContent !== next) node.textContent = next;
  }

  function setHtml(id, html) {
    const node = el(id);
    if (!node) return;
    if (node.innerHTML !== html) node.innerHTML = html;
  }

  function applyTheme() {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-theme-btn]").forEach((btn) => {
      btn.setAttribute("aria-pressed", btn.dataset.themeBtn === theme ? "true" : "false");
    });
  }

  function applyLangChrome() {
    document.documentElement.lang = lang;
    const testBtn = el("testBtn");
    if (testBtn && !testBtn.disabled) testBtn.textContent = "🧪 " + t("test_notify");
    document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      btn.setAttribute("aria-pressed", btn.dataset.langBtn === lang ? "true" : "false");
    });
    const darkBtn = document.querySelector('[data-theme-btn="dark"]');
    const lightBtn = document.querySelector('[data-theme-btn="light"]');
    if (darkBtn) darkBtn.textContent = t("theme_dark");
    if (lightBtn) lightBtn.textContent = t("theme_light");

    const refreshLabel = el("refreshLabel");
    if (refreshLabel) refreshLabel.textContent = t("refresh");

    if (shellBuilt) {
      setText("lbl-realtime", "📊 " + t("realtime"));
      setText("lbl-settings", "⚙️ " + t("settings"));
      setText("lbl-events", "📋 " + t("events"));
      setText("lbl-model", t("model"));
      setText("lbl-status", t("status"));
      setText("lbl-voltage", t("output_voltage"));
      setText("lbl-load", t("load"));
      setText("lbl-runtime", t("runtime"));
      setText("lbl-battery", t("battery"));
      setText("lbl-nom-power", t("nom_power"));
      setText("lbl-nom-voltage", t("nom_voltage"));
      setText("lbl-nom-freq", t("nom_freq"));
      setText("lbl-charge-low", t("charge_low"));
      setText("lbl-delay-shutdown", t("delay_shutdown"));
      setText("lbl-delay-start", t("delay_start"));
      setText("lbl-transfer", t("transfer_range"));
      setText("lbl-beeper", t("beeper"));
      setText("lbl-outlet1", t("outlet1"));
      setText("lbl-outlet2", t("outlet2"));
      setText("lbl-firmware", t("firmware"));
      setText("lbl-driver", t("driver"));
    }
  }

  function setTheme(next) {
    theme = next;
    localStorage.setItem(THEME_KEY, theme);
    applyTheme();
  }

  function setLang(next) {
    lang = next;
    localStorage.setItem(LANG_KEY, lang);
    applyLangChrome();
    lastEventsSig = "";
    refresh();
  }

  function scheduleRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refresh, refreshSec * 1000);
  }

  function setRefreshSec(sec) {
    refreshSec = sec;
    localStorage.setItem(REFRESH_KEY, String(refreshSec));
    const select = el("refreshSelect");
    if (select) select.value = String(refreshSec);
    scheduleRefresh();
  }

  function badge(on, onLabel, offLabel) {
    if (on === "on" || on === "enabled") {
      return `<span class="badge badge-on">${onLabel}</span>`;
    }
    return `<span class="badge badge-off">${offLabel}</span>`;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatTemplate(template, params) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) =>
      params[key] != null ? String(params[key]) : ""
    );
  }

  function inferLegacyEvent(message) {
    const m = String(message || "");
    const charge = (m.match(/(\d+|\?)%/) || [])[1] || "?";

    if (/Batterie faible|Low battery|Shutdown imminent/i.test(m)) {
      return { key: "low_battery", params: { charge } };
    }
    if (/Secteur rétabli|Mains restored/i.test(m)) {
      return { key: "power_restored", params: { charge } };
    }
    if (/Sur batterie|On battery/i.test(m)) {
      const runtime = (m.match(/(\d+)\s*min/i) || [])[1] || "?";
      return { key: "on_battery", params: { charge, runtime } };
    }
    if (/Coupure secteur|Power failure/i.test(m)) {
      return { key: "power_loss", params: { charge } };
    }
    if (/Test notification/i.test(m)) {
      const ts = (m.match(/(\d{2}\/\d{2}\s+\d{2}:\d{2}:\d{2})/) || [])[1] || "";
      return { key: "test", params: { ts } };
    }
    if (/démarré|started|monitoring actif|monitoring active/i.test(m)) {
      return { key: "started", params: {} };
    }
    return null;
  }

  function formatEventMessage(event) {
    let key = event.key;
    let params = event.params || {};
    if (!key) {
      const inferred = inferLegacyEvent(event.message);
      if (inferred) {
        key = inferred.key;
        params = inferred.params;
      }
    }
    if (!key) return event.message || "";
    const template = t("evt_" + key);
    if (!template || template === "evt_" + key) return event.message || key;
    return formatTemplate(template, params);
  }

  function ensureShell() {
    if (shellBuilt) return;
    const content = el("content");
    content.classList.remove("loading");
    content.innerHTML = `
      <div id="errorBanner" class="error-banner" hidden></div>
      <div id="dashboard" hidden>
        <div class="card">
          <h2 id="lbl-realtime"></h2>
          <table>
            <tr><td id="lbl-model"></td><td id="val-model"></td></tr>
            <tr><td id="lbl-status"></td><td><span id="val-status"></span></td></tr>
            <tr><td id="lbl-voltage"></td><td id="val-voltage"></td></tr>
            <tr><td id="lbl-load"></td><td id="val-load"></td></tr>
            <tr><td id="lbl-runtime"></td><td id="val-runtime"></td></tr>
            <tr><td id="lbl-battery"></td><td>
              <div class="bar-bg"><div class="bar-fill" id="val-battery-bar">0%</div></div>
            </td></tr>
          </table>
        </div>
        <div class="card">
          <h2 id="lbl-settings"></h2>
          <table>
            <tr><td id="lbl-nom-power"></td><td id="val-nom-power"></td></tr>
            <tr><td id="lbl-nom-voltage"></td><td id="val-nom-voltage"></td></tr>
            <tr><td id="lbl-nom-freq"></td><td id="val-nom-freq"></td></tr>
            <tr><td id="lbl-charge-low"></td><td id="val-charge-low"></td></tr>
            <tr><td id="lbl-delay-shutdown"></td><td id="val-delay-shutdown"></td></tr>
            <tr><td id="lbl-delay-start"></td><td id="val-delay-start"></td></tr>
            <tr><td id="lbl-transfer"></td><td id="val-transfer"></td></tr>
            <tr><td id="lbl-beeper"></td><td id="val-beeper"></td></tr>
            <tr><td id="lbl-outlet1"></td><td id="val-outlet1"></td></tr>
            <tr><td id="lbl-outlet2"></td><td id="val-outlet2"></td></tr>
            <tr><td id="lbl-firmware"></td><td id="val-firmware"></td></tr>
            <tr><td id="lbl-driver"></td><td id="val-driver"></td></tr>
          </table>
        </div>
        <div class="card">
          <h2 id="lbl-events"></h2>
          <div class="events" id="val-events"></div>
        </div>
      </div>
    `;
    shellBuilt = true;
    applyLangChrome();
  }

  function showError(message) {
    ensureShell();
    const banner = el("errorBanner");
    const dash = el("dashboard");
    banner.hidden = false;
    dash.hidden = true;
    banner.innerHTML = `<strong>${t("ups_error")}</strong><br>${escapeHtml(message)}`;
  }

  function showDashboard() {
    ensureShell();
    el("errorBanner").hidden = true;
    el("dashboard").hidden = false;
  }

  async function refresh() {
    try {
      const [status, events] = await Promise.all([
        fetch("/api/status").then((r) => r.json()),
        fetch("/api/events").then((r) => r.json()),
      ]);

      if (status._error) {
        showError(status._error);
        return;
      }

      showDashboard();

      const s = status["ups.status"] || "?";
      const charge = parseInt(status["battery.charge"] || 0, 10) || 0;
      const runtime = Math.floor(parseInt(status["battery.runtime"] || 0, 10) / 60) || 0;
      const power = status["ups.realpower"] || "?";
      const load = status["ups.load"] || "?";
      const voltage = status["output.voltage"] || "?";
      const model = status["ups.model"] || "?";

      let statusClass = "status-ol";
      let statusLabel = t("status_ol");
      if (s.includes("OB")) {
        statusClass = "status-ob";
        statusLabel = t("status_ob");
      }
      if (s.includes("LB")) {
        statusClass = "status-lb";
        statusLabel = t("status_lb");
      }
      if (s === "?") {
        statusClass = "status-ob";
        statusLabel = t("status_unknown");
      }

      const barColor = charge > 50 ? "var(--ok)" : charge > 20 ? "var(--warn)" : "var(--danger)";
      const chargeLow = status["battery.charge.low"] || "?";
      const delayShutdown = status["ups.delay.shutdown"] || "?";
      const delayStart = status["ups.delay.start"] || "?";
      const transferHigh = status["input.transfer.high"] || "?";
      const transferLow = status["input.transfer.low"] || "?";
      const nomPower = status["ups.power.nominal"] || "?";
      const nomVoltage = status["output.voltage.nominal"] || "?";
      const nomFreq = status["output.frequency.nominal"] || "?";
      const beeper = status["ups.beeper.status"] || "?";
      const firmware = status["ups.firmware"] || "?";
      const driver = status["driver.name"] || "?";
      const pollInterval = status["driver.parameter.pollinterval"] || "?";
      const outlet1 = status["outlet.1.status"] || "?";
      const outlet2 = status["outlet.2.status"] || "?";

      setText("val-model", model);
      const statusNode = el("val-status");
      if (statusNode) {
        statusNode.className = statusClass;
        if (statusNode.textContent !== statusLabel) statusNode.textContent = statusLabel;
      }
      setText("val-voltage", `${voltage} V`);
      setText("val-load", `${load}% — ${power} W`);
      setText("val-runtime", `${runtime} ${t("minutes")}`);

      const bar = el("val-battery-bar");
      if (bar) {
        const width = `${charge}%`;
        if (bar.style.width !== width) bar.style.width = width;
        if (bar.style.background !== barColor) bar.style.background = barColor;
        const label = `${charge}%`;
        if (bar.textContent !== label) bar.textContent = label;
      }

      setText("val-nom-power", `${nomPower} VA`);
      setText("val-nom-voltage", `${nomVoltage} V`);
      setText("val-nom-freq", `${nomFreq} Hz`);
      setText("val-charge-low", `${chargeLow}%`);
      setText("val-delay-shutdown", `${delayShutdown} ${t("seconds_unit")}`);
      setText("val-delay-start", `${delayStart} ${t("seconds_unit")}`);
      setText("val-transfer", `${transferLow} – ${transferHigh} V`);
      setHtml("val-beeper", badge(beeper, t("enabled"), t("disabled")));
      setHtml("val-outlet1", badge(outlet1, "ON", "OFF"));
      setHtml("val-outlet2", badge(outlet2, "ON", "OFF"));
      setText("val-firmware", firmware);
      setText("val-driver", `${driver} (${t("poll")}: ${pollInterval}${t("seconds_unit")})`);

      const eventsSig = lang + "|" + JSON.stringify(events);
      if (eventsSig !== lastEventsSig) {
        lastEventsSig = eventsSig;
        let eventsHtml = "";
        if (!events.length) {
          eventsHtml = `<div class="event-row" style="color:var(--text-muted)">${t("no_events")}</div>`;
        } else {
          for (const e of events) {
            eventsHtml += `<div class="event-row"><span class="event-ts">${escapeHtml(
              e.ts
            )}</span>${escapeHtml(formatEventMessage(e))}</div>`;
          }
        }
        setHtml("val-events", eventsHtml);
      }
    } catch (e) {
      showError(String(e));
    }
  }

  async function testNotify() {
    const btn = el("testBtn");
    const original = "🧪 " + t("test_notify");
    btn.textContent = "⏳ " + t("sending");
    btn.disabled = true;
    try {
      const res = await fetch("/api/test-notify");
      const data = await res.json();
      btn.textContent = data.sent ? "✅ " + t("sent") : "❌ " + t("failed");
    } catch {
      btn.textContent = "❌ " + t("error");
    }
    setTimeout(() => {
      btn.textContent = original;
      btn.disabled = false;
      lastEventsSig = "";
      refresh();
    }, 2000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme();
    applyLangChrome();

    document.querySelectorAll("[data-theme-btn]").forEach((btn) => {
      btn.addEventListener("click", () => setTheme(btn.dataset.themeBtn));
    });
    document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      btn.addEventListener("click", () => setLang(btn.dataset.langBtn));
    });
    el("testBtn").addEventListener("click", testNotify);

    const select = el("refreshSelect");
    if (select) {
      select.value = String(refreshSec);
      select.addEventListener("change", () => {
        setRefreshSec(parseInt(select.value, 10));
      });
    }

    refresh();
    scheduleRefresh();
  });
})();
