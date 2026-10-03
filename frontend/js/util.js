// 화면 공통 도구: HTML 이스케이프, 숫자 표기, 한국어 이름표, 토스트, 모달

export const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function money(n, digits = 2) {
  if (n === null || n === undefined || isNaN(n)) return "–";
  return Number(n).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
export const usd = (n, d = 2) => (n === null || n === undefined || isNaN(n)) ? "–" : "$" + money(n, d);
export const whole = n => money(n, 0);
export function pct(n, digits = 2, sign = true) {
  if (n === null || n === undefined || isNaN(n)) return "–";
  const s = Number(n).toFixed(digits);
  return (sign && n > 0 ? "+" : "") + s + "%";
}
export const signClass = n => (n > 0 ? "up" : n < 0 ? "down" : "");

export const ROLE_KO = {
  big: "큰수 매수", star_buy: "별지점 매수", avg_buy: "평단 매수", ladder: "사다리 매수",
  quarter_sell: "쿼터 매도", limit_sell: "지정가 매도",
  quarter_stop_moc: "쿼터손절 MOC", quarter_stop_buy: "쿼터손절 매수", quarter_stop_sell: "쿼터손절 매도",
  reverse_moc: "리버스 MOC 매도", reverse_sell: "리버스 매도", reverse_buy: "리버스 쿼터매수",
  vr_buy: "VR 매수", vr_sell: "VR 매도",
};
export const BUY_ROLES = ["big", "star_buy", "avg_buy", "ladder", "quarter_stop_buy", "reverse_buy", "vr_buy"];
export const SELL_ROLES = ["quarter_sell", "limit_sell", "quarter_stop_moc", "quarter_stop_sell", "reverse_moc", "reverse_sell", "vr_sell"];
export const SIDE_KO = { buy: "매수", sell: "매도" };
export const SOURCE_KO = { auto: "자동 확정", manual: "직접 입력", backtest: "백테스트" };
export const VR_TYPE_KO = { installment: "적립식", lump_sum: "거치식", withdrawal: "인출식" };
export const BAND_POS_KO = { below: "하단 아래 (매수 구간)", inside: "밴드 안", above: "상단 위 (매도 구간)" };
export const TOOL_KO = {
  get_portfolio_summary: "전체 현황 조회", get_strategy_status: "전략 상태 조회", get_today_orders: "주문표 조회",
  get_fill_history: "체결 기록 조회", get_price_stats: "시세 통계 조회",
};

export const shortDate = d => (d ? d.slice(5).replace("-", "/") : "");
export function localTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
export const todayStr = () => new Date().toISOString().slice(0, 10);

// ---- 토스트 ----
let toastTimer;
export function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("err", isError);
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), isError ? 5000 : 2600);
}

// ---- 모달 ----
// html을 넣고 열어 준다. 폼 submit 이벤트는 onSubmit(form)으로 받는다. 닫히면 resolve.
export function openModal(html, onSubmit) {
  const dlg = $("#modal");
  $("#modalBody").innerHTML = html;
  return new Promise(resolve => {
    const form = $("#modalBody form");
    if (form) {
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const btn = form.querySelector("[type=submit]");
        if (btn) btn.disabled = true;
        try {
          const r = await onSubmit?.(form);
          if (r !== false) { dlg.close(); resolve(r ?? true); }
        } catch (err) {
          showError(form, err);
        } finally {
          if (btn) btn.disabled = false;
        }
      });
    }
    $$("[data-close]", dlg).forEach(b => b.addEventListener("click", () => { dlg.close(); resolve(null); }));
    dlg.addEventListener("close", () => resolve(null), { once: true });
    dlg.showModal();
  });
}

export function showError(container, err) {
  let box = container.querySelector(":scope > .error-box");
  if (!box) {
    box = document.createElement("p");
    box.className = "error-box";
    container.prepend(box);
  }
  box.textContent = err?.message || String(err);
}

export const loading = (msg = "불러오는 중") => `<div class="loading">${esc(msg)}</div>`;
export const errorHtml = err => `<p class="error-box">${esc(err?.message || err)}</p>`;

// 폼 값을 객체로 (빈 칸은 뺀다, data-num은 숫자로)
export function formValues(form) {
  const out = {};
  for (const el of form.elements) {
    if (!el.name || el.disabled) continue;
    if (el.type === "checkbox") { out[el.name] = el.checked; continue; }
    if (el.type === "radio") { if (el.checked) out[el.name] = el.value; continue; }
    if (el.value === "") continue;
    out[el.name] = el.type === "number" ? Number(el.value) : el.value;
  }
  return out;
}

// 답변용 간단 마크다운: 굵게, 목록, 줄바꿈 (먼저 이스케이프)
export function miniMarkdown(text) {
  const blocks = esc(text || "").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split(/\n{2,}/);
  return blocks.map(b => {
    const lines = b.split("\n");
    if (lines.every(l => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
      return "<ul>" + lines.map(l => `<li>${l.replace(/^\s*([-*•]|\d+\.)\s+/, "")}</li>`).join("") + "</ul>";
    }
    const out = [];
    let list = [];
    const flush = () => { if (list.length) { out.push("<ul>" + list.map(x => `<li>${x}</li>`).join("") + "</ul>"); list = []; } };
    for (const l of lines) {
      if (/^\s*[-*•]\s+/.test(l)) list.push(l.replace(/^\s*[-*•]\s+/, ""));
      else { flush(); out.push(l); }
    }
    flush();
    return "<p>" + out.join("<br>").replace(/<br>(<ul>)/g, "$1").replace(/(<\/ul>)<br>/g, "$1") + "</p>";
  }).join("");
}
