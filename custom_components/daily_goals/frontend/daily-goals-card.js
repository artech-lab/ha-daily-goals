/*
 * Daily Goals Card for Home Assistant
 * https://github.com/artech-lab/ha-daily-goals
 *
 * Dashboard card bundled with the Daily Goals integration, which serves and
 * loads it automatically (no dashboard resource needed). It only displays what
 * the integration computes: one progress ring per goal with its value, a badge
 * when the goal is achieved, the reward, the goals achieved today, the
 * completion of the day, the perfect-day streak and the points.
 * Goals are read from the "goals achieved" sensor; streak and points are
 * discovered from the same device.
 *
 * One dependency-free file, no build step. Localized: English and Italian.
 *
 * Copyright (C) 2026 The ha-daily-goals contributors
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version. This program is distributed in the hope that it will be
 * useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 * Public License for more details: <https://www.gnu.org/licenses/>.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// The integration appends its manifest version to the URL of this module.
const CARD_VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const CARD_TAG = "daily-goals-card";
const EDITOR_TAG = "daily-goals-card-editor";
const INTEGRATION = "daily_goals";

const STRINGS = {
  en: {
    card_name: "Daily Goals",
    card_description: "Gamified daily goals: progress rings, completion badges, rewards, streak and points.",
    default_title: "Today's goals",
    completed: "Completed!",
    waiting: "Waiting for today's value",
    unavailable: "not available",
    of: "{p}% · of {t}",
    max: "{p}% · max {t}",
    day: "Day completion: {p}%",
    perfect: "Perfect day, all goals achieved!",
    streak: "{n} d",
    streak_title: "Perfect days in a row (best: {b})",
    points: "{n} pts",
    points_title: "Points today (total: {t})",
    reward: "Reward: {r}",
    no_goals: "No goals yet: add them in Settings → Devices & services → Daily Goals → Add goal.",
    no_entity: "Select the \"Goals achieved\" sensor of a Daily Goals device.",
    // editor
    e_entity: "Goals achieved sensor",
    e_title: "Title",
    e_icon: "Icon",
    e_columns: "Columns (2-4)",
    e_show_rewards: "Show rewards",
    e_show_stats: "Show streak and points"
  },
  it: {
    card_name: "Daily Goals",
    card_description: "Obiettivi giornalieri gamificati: anelli di avanzamento, badge di completamento, premi, serie e punti.",
    default_title: "Obiettivi di oggi",
    completed: "Completato!",
    waiting: "In attesa del valore di oggi",
    unavailable: "non disponibile",
    of: "{p}% · su {t}",
    max: "{p}% · max {t}",
    day: "Completamento della giornata: {p}%",
    perfect: "Giornata perfetta, tutti gli obiettivi raggiunti!",
    streak: "{n} g",
    streak_title: "Giornate perfette di fila (record: {b})",
    points: "{n} punti",
    points_title: "Punti di oggi (totale: {t})",
    reward: "Premio: {r}",
    no_goals: "Nessun obiettivo: aggiungili da Impostazioni → Dispositivi e servizi → Daily Goals → Aggiungi obiettivo.",
    no_entity: "Seleziona il sensore \"Obiettivi raggiunti\" di un dispositivo Daily Goals.",
    e_entity: "Sensore obiettivi raggiunti",
    e_title: "Titolo",
    e_icon: "Icona",
    e_columns: "Colonne (2-4)",
    e_show_rewards: "Mostra i premi",
    e_show_stats: "Mostra serie e punti"
  }
};

function langOf(hass) {
  const l = (hass && ((hass.locale && hass.locale.language) || hass.language)) ||
    (typeof navigator !== "undefined" ? navigator.language : "en");
  return String(l || "en").toLowerCase().split("-")[0];
}

function t(hass, key, vars) {
  const table = STRINGS[langOf(hass)] || STRINGS.en;
  let s = table[key] != null ? table[key] : (STRINGS.en[key] != null ? STRINGS.en[key] : key);
  if (vars) for (const k of Object.keys(vars)) s = s.replace("{" + k + "}", vars[k]);
  return s;
}

/* Maps the integration's translation keys to the card's internal roles. */
const SIBLINGS = {
  completion: "completion",
  streak: "streak",
  best_streak: "best",
  points_today: "points",
  total_points: "total"
};

/* Ring colors of goals without their own color. */
const PALETTE = [
  "#29b6f6", "#ff7043", "#66bb6a", "#7e57c2", "#26c6da", "#9ccc65", "#ef5350", "#f06292",
  "#8d6e63", "#ec407a", "#ab47bc", "#ffa726", "#ffca28", "#26a69a", "#5c6bc0", "#d4e157"
];
const DASH = "--";
const R = 30;
const CIRC = 2 * Math.PI * R;

function findAchievedEntity(hass) {
  const reg = (hass && hass.entities) || {};
  for (const id of Object.keys(reg)) {
    const e = reg[id];
    if (e && e.platform === INTEGRATION && e.translation_key === "achieved" && id.startsWith("sensor.")) return id;
  }
  return null;
}

function discoverSiblings(hass, entity) {
  const out = {};
  const reg = (hass && hass.entities) || {};
  const me = reg[entity];
  if (!me || !me.device_id) return out;
  for (const id of Object.keys(reg)) {
    const e = reg[id];
    if (!e || e.device_id !== me.device_id || e.platform !== INTEGRATION || !id.startsWith("sensor.")) continue;
    const role = SIBLINGS[e.translation_key];
    if (role) out[role] = id;
  }
  return out;
}

async function ensureHaForm() {
  if (customElements.get("ha-form")) return;
  try {
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: "entities", entities: [] });
    if (card && card.constructor && card.constructor.getConfigElement) await card.constructor.getConfigElement();
  } catch (e) {
    /* ha-form will be loaded by the edit dialog */
  }
}

function esc(v) {
  return String(v == null ? "" : v).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" })[c]);
}

function colorOf(goal, index) {
  const c = goal.color;
  if (Array.isArray(c) && c.length >= 3) return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
  return PALETTE[index % PALETTE.length];
}

const DEFAULTS = { icon: "mdi:trophy", columns: 3, show_rewards: true, show_stats: true };

const STYLE = `
:host{display:block}
ha-card{padding:12px 16px 14px;box-sizing:border-box;height:100%}
.head{display:flex;align-items:center;gap:10px;padding:2px 0 8px}
.hic{width:38px;height:38px;min-width:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  color:var(--amber-color,#ffc107);background:color-mix(in srgb,var(--amber-color,#ffc107) 20%,transparent)}
.hic ha-icon{--mdc-icon-size:21px}
.htitle{flex:1;min-width:0;font-size:16px;font-weight:600;color:var(--primary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip{font-size:12px;font-weight:600;border-radius:12px;padding:4px 9px;white-space:nowrap;display:flex;align-items:center;gap:3px;
  color:var(--primary-text-color);background:color-mix(in srgb,var(--primary-text-color) 8%,transparent);cursor:pointer}
.chip ha-icon{--mdc-icon-size:14px}
.chip.streak ha-icon{color:var(--deep-orange-color,#ff5722)}
.chip.points ha-icon{color:var(--amber-color,#ffc107)}
.count{font-size:13px;font-weight:700;padding:4px 12px}
.count.alldone{color:#fff;background:linear-gradient(135deg,var(--amber-color,#ffc107),var(--orange-color,#ff9800))}
.totbar{height:8px;border-radius:4px;background:color-mix(in srgb,var(--primary-text-color) 10%,transparent);overflow:hidden;margin:2px 0 4px}
.totfill{height:100%;border-radius:4px;transition:width .5s ease}
.totcap{font-size:11px;color:var(--secondary-text-color);text-align:right;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.totcap.perfect{color:var(--amber-color,#ffb300);font-weight:700}
.grid{display:grid;gap:10px 6px}
.goal{display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 2px 6px;border-radius:14px;cursor:pointer;min-width:0}
.goal:hover{background:color-mix(in srgb,var(--primary-text-color) 6%,transparent)}
.goal.done{background:color-mix(in srgb,var(--success-color,#4caf50) 9%,transparent)}
.ringwrap{position:relative;width:68px;height:68px}
.ringwrap svg{width:68px;height:68px;display:block}
.track{fill:none;stroke:color-mix(in srgb,var(--primary-text-color) 12%,transparent);stroke-width:6}
.prog{fill:none;stroke-width:6;stroke-linecap:round;transition:stroke-dasharray .6s ease}
.goal.done .prog{filter:drop-shadow(0 0 4px color-mix(in srgb,var(--success-color,#4caf50) 70%,transparent))}
.rv{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.rval{font-size:14px;font-weight:700;color:var(--primary-text-color);line-height:1.1;font-variant-numeric:tabular-nums}
.runit{font-size:9px;color:var(--secondary-text-color);line-height:1.2;max-width:52px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badge{position:absolute;top:-3px;right:-3px;width:20px;height:20px;border-radius:50%;background:var(--success-color,#4caf50);
  display:flex;align-items:center;justify-content:center;border:2px solid var(--card-background-color,#1c1c1c);animation:dgpop .35s ease}
.badge ha-icon{--mdc-icon-size:11px;color:#fff;display:flex}
@keyframes dgpop{0%{transform:scale(0)}70%{transform:scale(1.25)}100%{transform:scale(1)}}
.gname{display:flex;align-items:center;gap:4px;max-width:100%;min-width:0}
.gname ha-icon{--mdc-icon-size:14px;flex:none}
.gname span{font-size:12px;font-weight:500;color:var(--primary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gcap{font-size:10.5px;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.gcap.done{color:var(--success-color,#4caf50);font-weight:700}
.gcap.waiting{color:var(--warning-color,#ff9800);font-weight:600}
.empty{font-size:13px;color:var(--secondary-text-color);padding:4px 0 8px}
[hidden]{display:none!important}
`;

class DailyGoalsCard extends HTMLElement {
  static getStubConfig(hass) {
    return { entity: findAchievedEntity(hass) || "" };
  }

  static async getConfigElement() {
    await ensureHaForm();
    return document.createElement(EDITOR_TAG);
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._cfg = Object.assign({}, DEFAULTS, config, { entity: config.entity || "" });
    this._layout = null;
    this._lastSig = null;
    if (this._hass) this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._cfg) this._refresh();
  }

  getCardSize() {
    const st = this._hass && this._cfg && this._hass.states[this._cfg.entity];
    const n = st && Array.isArray(st.attributes.goals) ? st.attributes.goals.length : 3;
    return 2 + 2 * Math.ceil(n / this._columns());
  }

  getGridOptions() {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  _t(key, vars) {
    return t(this._hass, key, vars);
  }

  _columns() {
    return Math.min(4, Math.max(2, Number(this._cfg && this._cfg.columns) || 3));
  }

  _fmt(n, decimals) {
    const d = Math.max(0, Math.min(2, Math.round(Number(decimals) || 0)));
    return Number(n).toLocaleString(langOf(this._hass), { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }

  _num(id) {
    const st = id && this._hass.states[id];
    if (!st) return null;
    const n = Number(st.state);
    return st.state === "" || isNaN(n) ? null : n;
  }

  /* The skeleton depends only on the goals and their look: rebuilt when they change. */
  _build(goals, layout) {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const cells = goals.map((g, i) => `
      <div class="goal" data-i="${i}">
        <div class="ringwrap">
          <svg viewBox="0 0 68 68"><circle class="track" cx="34" cy="34" r="${R}"/>
            <circle class="prog" cx="34" cy="34" r="${R}" stroke-dasharray="0 ${CIRC.toFixed(2)}" transform="rotate(-90 34 34)"/></svg>
          <div class="rv"><div class="rval">${DASH}</div><div class="runit">${esc(g.unit)}</div></div>
          <div class="badge" hidden><ha-icon icon="mdi:check-bold"></ha-icon></div>
        </div>
        <div class="gname"><ha-icon icon="${esc(g.icon || "mdi:target")}" style="color:${colorOf(g, i)}"></ha-icon><span>${esc(g.name)}</span></div>
        <div class="gcap">${DASH}</div>
      </div>`).join("");
    const gradient = goals.length > 1 ? goals.map((g, i) => colorOf(g, i)).join(",") : "var(--primary-color),var(--primary-color)";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        <div class="head">
          <div class="hic"><ha-icon id="icon"></ha-icon></div>
          <div class="htitle" id="title"></div>
          <div class="chip streak" id="streak" hidden><ha-icon icon="mdi:fire"></ha-icon><span></span></div>
          <div class="chip points" id="points" hidden><ha-icon icon="mdi:star-circle"></ha-icon><span></span></div>
          <div class="chip count" id="count">${DASH}</div>
        </div>
        <div class="totbar"><div class="totfill" id="totfill" style="width:0%;background:linear-gradient(90deg,${gradient})"></div></div>
        <div class="totcap" id="totcap"></div>
        <div class="empty" id="empty" hidden></div>
        <div class="grid" style="grid-template-columns:repeat(${this._columns()},minmax(0,1fr))">${cells}</div>
      </ha-card>`;
    const r = this.shadowRoot;
    r.querySelectorAll(".goal").forEach((el) => {
      el.addEventListener("click", () => this._moreInfo(this._goals[Number(el.dataset.i)].source));
    });
    r.getElementById("count").addEventListener("click", () => this._moreInfo(this._cfg.entity));
    r.getElementById("totcap").addEventListener("click", () => this._moreInfo(this._siblings.completion));
    r.getElementById("streak").addEventListener("click", () => this._moreInfo(this._siblings.streak));
    r.getElementById("points").addEventListener("click", () => this._moreInfo(this._siblings.points));
    this._layout = layout;
  }

  _refresh() {
    const c = this._cfg;
    const st = c.entity && this._hass.states[c.entity];
    if (!st) {
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="empty">${esc(this._t("no_entity"))}</div></ha-card>`;
      this._layout = null;
      return;
    }
    const a = st.attributes || {};
    const goals = Array.isArray(a.goals) ? a.goals : [];
    this._goals = goals;
    this._siblings = discoverSiblings(this._hass, c.entity);
    const s = this._siblings;
    const lang = langOf(this._hass);
    const layout = JSON.stringify([goals.map((g) => [g.id, g.name, g.icon, g.color, g.unit]), this._columns(), lang]);
    const stats = [s.streak, s.best, s.points, s.total, s.completion].map((id) => (id && this._hass.states[id] ? this._hass.states[id].state : ""));
    const sig = [layout, JSON.stringify(goals), stats.join("|"), c.title, c.icon, c.show_rewards, c.show_stats, a.perfect_day,
      a.perfect_day_reward].join("§");
    if (sig === this._lastSig) return;
    this._lastSig = sig;
    if (layout !== this._layout) this._build(goals, layout);

    const r = this.shadowRoot;
    r.getElementById("title").textContent = c.title || this._t("default_title");
    r.getElementById("icon").setAttribute("icon", c.icon || DEFAULTS.icon);

    let done = 0;
    r.querySelectorAll(".goal").forEach((cell) => {
      const i = Number(cell.dataset.i);
      const g = goals[i];
      const achieved = !!g.achieved;
      if (achieved) done += 1;
      const has = g.value !== null && g.value !== undefined;
      const pct = achieved ? 1 : Math.max(0, Math.min(1, (Number(g.progress) || 0) / 100));
      const prog = cell.querySelector(".prog");
      prog.setAttribute("stroke-dasharray", `${(CIRC * pct).toFixed(2)} ${CIRC.toFixed(2)}`);
      prog.setAttribute("stroke", achieved ? "var(--success-color, #4caf50)" : colorOf(g, i));
      prog.style.opacity = pct > 0 ? "1" : "0"; // a round cap of length 0 would still draw a dot
      cell.querySelector(".rval").textContent = has ? this._fmt(g.value, g.decimals) : DASH;
      cell.querySelector(".badge").hidden = !achieved;
      cell.classList.toggle("done", achieved);
      const cap = cell.querySelector(".gcap");
      let text, cls = "gcap";
      if (achieved) {
        text = c.show_rewards && g.reward ? "🎁 " + g.reward : this._t("completed");
        cls += " done";
      } else if (!has) {
        text = g.waiting ? (g.waiting_text || this._t("waiting")) : this._t("unavailable");
        if (g.waiting) cls += " waiting";
      } else {
        const p = Math.round(Number(g.progress) || 0);
        text = this._t(g.direction === "below" ? "max" : "of", { p, t: this._fmt(g.target, g.decimals) });
      }
      cap.textContent = text;
      cap.className = cls;
      cell.title = g.reward ? this._t("reward", { r: g.reward }) : "";
    });

    const total = goals.length;
    const count = r.getElementById("count");
    count.textContent = `${done}/${total}`;
    count.classList.toggle("alldone", total > 0 && done === total);
    const completion = this._num(s.completion);
    const pct = completion === null ? 0 : Math.round(completion);
    r.getElementById("totfill").style.width = pct + "%";
    const cap = r.getElementById("totcap");
    const perfect = !!a.perfect_day;
    cap.classList.toggle("perfect", perfect);
    cap.textContent = perfect
      ? this._t("perfect") + (c.show_rewards && a.perfect_day_reward ? " 🎁 " + a.perfect_day_reward : "")
      : this._t("day", { p: pct });
    const empty = r.getElementById("empty");
    empty.hidden = total > 0;
    empty.textContent = this._t("no_goals");

    const streak = this._num(s.streak), best = this._num(s.best), points = this._num(s.points), tot = this._num(s.total);
    const sc = r.getElementById("streak"), pc = r.getElementById("points");
    sc.hidden = !(c.show_stats && streak !== null);
    pc.hidden = !(c.show_stats && points !== null);
    if (streak !== null) {
      sc.querySelector("span").textContent = this._t("streak", { n: this._fmt(streak, 0) });
      sc.title = this._t("streak_title", { b: best === null ? DASH : this._fmt(best, 0) });
    }
    if (points !== null) {
      pc.querySelector("span").textContent = this._t("points", { n: this._fmt(points, 0) });
      pc.title = this._t("points_title", { t: tot === null ? DASH : this._fmt(tot, 0) });
    }
  }
}

class DailyGoalsCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({}, config);
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  connectedCallback() {
    this._render();
  }

  _schema() {
    const flag = (name) => ({ name, selector: { boolean: {} } });
    return [
      { name: "entity", required: true, selector: { entity: { integration: INTEGRATION, domain: "sensor" } } },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "title", selector: { text: {} } },
          { name: "icon", selector: { icon: {} } },
          { name: "columns", selector: { number: { min: 2, max: 4, mode: "box" } } }
        ]
      },
      { type: "grid", name: "", schema: ["show_rewards", "show_stats"].map(flag) }
    ];
  }

  async _render() {
    if (!this._config || !this._hass) return;
    await ensureHaForm();
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        const config = Object.assign({}, this._config, ev.detail.value);
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] === undefined) delete config[k];
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = Object.assign({}, DEFAULTS, this._config);
    this._form.schema = this._schema();
    this._form.computeLabel = (s) => t(this._hass, "e_" + s.name);
  }
}

if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, DailyGoalsCardEditor);
if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, DailyGoalsCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TAG,
    name: t(null, "card_name"),
    description: t(null, "card_description"),
    preview: true,
    documentationURL: "https://github.com/artech-lab/ha-daily-goals"
  });
  console.info(`%c DAILY-GOALS-CARD %c ${CARD_VERSION} `, "color:#000;background:#ffb300;font-weight:700", "color:#ffb300;background:#424242");
}
