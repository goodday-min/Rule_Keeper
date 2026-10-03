// 주문 전표: 전략 하나의 다음 거래일 주문표 + 체결 확인 대기
import { api } from "./api.js";
import { $$, BAND_POS_KO, esc, money, pct, ROLE_KO, SIDE_KO, toast, usd, whole } from "./util.js";

export function stateLine(st) {
  if (!st) return "";
  if (st.type === "vr") {
    return `<span>V <b class="num">${whole(st.v)}</b></span>
      <span>평가금 <b class="num">${whole(st.e)}</b></span>
      <span>밴드 <b class="num">${whole(st.band_low)}~${whole(st.band_high)}</b></span>
      <span>Pool <b class="num">${whole(st.pool)}</b></span>
      <span>보유 <b class="num">${st.qty}주</b></span>`;
  }
  const parts = [`<span>T <b class="num">${money(st.t, 2)}/${st.splits}</b></span>`];
  if (st.qty) {
    parts.push(`<span>평단 <b class="num">${money(st.avg)}</b></span>`, `<span>별지점 <b class="num">${money(st.star)}</b></span>`,
      `<span>보유 <b class="num">${st.qty}주</b></span>`);
    if (st.pnl_pct !== undefined) parts.push(`<span>평가손익 <b class="num">${pct(st.pnl_pct)}</b></span>`);
  }
  parts.push(`<span>잔금 <b class="num">${usd(st.cash, 0)}</b></span>`);
  return parts.join("");
}

export function badges(st, { sim, sheet } = {}) {
  const b = [];
  if (sim) b.push(`<span class="badge sim">시뮬레이션</span>`);
  if (st) {
    if (st.type === "vr") {
      b.push(`<span class="badge">VR ${esc({ installment: "적립식", lump_sum: "거치식", withdrawal: "인출식" }[st.vr_type] || "")}</span>`);
      if (st.band_position) b.push(`<span class="badge ${st.band_position === "below" ? "buy" : st.band_position === "above" ? "sell" : ""}">${esc(BAND_POS_KO[st.band_position])}</span>`);
      if (st.rebalance_due) b.push(`<span class="badge warn">V 갱신일</span>`);
    } else {
      b.push(`<span class="badge">${esc(st.version?.toUpperCase())}</span>`);
      b.push(`<span class="badge ${st.mode === "normal" ? "" : "warn"}">${esc(st.mode === "normal" ? st.phase_ko : st.mode_ko + " 모드")}</span>`);
    }
  }
  if (sheet?.provisional) b.push(`<span class="badge warn" title="이전 주문표의 체결이 아직 확정되지 않았습니다">임시 주문표</span>`);
  return b.join("");
}

function lineHtml(l, minor = false) {
  return `<li class="line ${l.side}${minor ? " minor" : ""}">
    <span class="l-side">${SIDE_KO[l.side]}</span>
    <span class="what">${esc(ROLE_KO[l.role] || l.role)} <span class="muted small">${esc(l.order_type)}</span>${l.note ? `<small>${esc(l.note)}</small>` : ""}</span>
    <span class="price num">${l.order_type === "MOC" ? "시장가" : money(l.price)}</span>
    <span class="qty num">× <b>${l.qty}</b>주</span>
  </li>`;
}

// 사다리처럼 1주씩 촘촘한 줄은 접어 둔다
export function linesHtml(lines) {
  if (!lines?.length) return `<p class="muted small" style="padding:12px 20px">오늘은 걸 주문이 없습니다.</p>`;
  const isMinor = (l, i, arr) => {
    if (l.role === "ladder") return arr.filter(x => x.role === "ladder").indexOf(l) >= 2;
    if (l.role === "vr_buy" || l.role === "vr_sell") return arr.filter(x => x.role === l.role).indexOf(l) >= 3;
    return false;
  };
  const main = [], folded = [];
  lines.forEach((l, i, arr) => (isMinor(l, i, arr) ? folded : main).push(l));
  return `<ul class="lines">${main.map(l => lineHtml(l)).join("")}</ul>` +
    (folded.length ? `<details class="lines-more"><summary>촘촘한 주문 ${folded.length}줄 더 보기</summary><ul class="lines">${folded.map(l => lineHtml(l, true)).join("")}</ul></details>` : "");
}

function confirmHtml(sid, j) {
  const judged = new Map(j.judged.map(x => [x.line_id, x]));
  const filledCount = j.judged.filter(x => x.filled).length;
  const rows = j.lines.map(l => {
    const r = judged.get(l.line_id) || {};
    return `<tr data-line="${l.line_id}">
      <td><input type="checkbox" name="filled" ${r.filled ? "checked" : ""} aria-label="${esc(ROLE_KO[l.role])} 체결"></td>
      <td><span class="badge ${l.side}">${SIDE_KO[l.side]}</span> ${esc(ROLE_KO[l.role] || l.role)}</td>
      <td class="r num">${l.order_type === "MOC" ? "MOC" : money(l.price)} × ${l.qty}</td>
      <td class="r"><input type="number" name="price" step="0.01" min="0.01" value="${r.price ?? ""}" placeholder="체결가"></td>
      <td class="r"><input type="number" name="qty" step="1" min="0" value="${r.filled ? r.qty : ""}" placeholder="수량"></td>
    </tr>`;
  }).join("");
  return `<form class="confirm" data-sid="${esc(sid)}" data-date="${esc(j.date)}">
    <h4>${esc(j.date)} 체결 확인 <span class="muted small">종가 ${money(j.close)} · 고가 ${money(j.high)} 기준 자동 판정 ${filledCount}줄 체결</span></h4>
    <p class="small muted">증권사 체결 내역과 다르면 체크와 가격·수량을 고친 뒤 확정하세요.</p>
    <div class="table-wrap"><table>
      <thead><tr><th>체결</th><th>주문</th><th class="r">주문가</th><th class="r">체결가</th><th class="r">수량</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <div class="row"><button class="btn primary small" type="submit">체결 확정</button></div>
  </form>`;
}

export function slipHtml(item) {
  const st = item.status, sheet = item.today;
  const alert = st && (st.mode === "reverse" || st.mode === "quarter_stop" || st.rebalance_due);
  const sid = item.strategy_id;
  if (item.error) {
    return `<article class="slip"><div class="slip-head"><div class="slip-title"><h3><a href="#/strategy/${esc(sid)}">${esc(item.name)}</a></h3></div>
      <p class="error-box">${esc(item.error)}</p></div></article>`;
  }
  return `<article class="slip${alert ? " alert" : ""}">
    <div class="slip-head">
      <div class="slip-title">
        <h3><a href="#/strategy/${esc(sid)}">${esc(item.name)}</a></h3>
        <span class="slip-date">${esc(sheet?.date)} 주문</span>
      </div>
      <div class="row">${badges(st, { sim: item.is_simulation, sheet })}</div>
      <div class="slip-state">${stateLine(st)}</div>
      ${sheet?.meta?.notice ? `<p class="note info">${esc(sheet.meta.notice)}</p>` : ""}
    </div>
    <div class="tear" aria-hidden="true"></div>
    ${linesHtml(sheet?.lines)}
    ${(item.to_confirm || []).map(j => confirmHtml(sid, j)).join("")}
    <div class="slip-foot">
      <span class="muted small">${esc(sheet?.based_on)} 종가 기준</span>
      <span class="spacer"></span>
      <a class="btn small" href="#/chat?strategy=${esc(sid)}">AI에게 묻기</a>
      <a class="btn small" href="#/strategy/${esc(sid)}">상세 보기</a>
    </div>
  </article>`;
}

// 체결 확정 폼 연결. 확정 후 onDone() 호출
export function bindConfirm(root, onDone) {
  $$("form.confirm", root).forEach(form => {
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const btn = form.querySelector("[type=submit]");
      const overrides = $$("tr[data-line]", form).map(tr => {
        const filled = tr.querySelector("[name=filled]").checked;
        const price = parseFloat(tr.querySelector("[name=price]").value);
        const qty = parseInt(tr.querySelector("[name=qty]").value, 10);
        return { line_id: Number(tr.dataset.line), filled, price: filled && price > 0 ? price : null, qty: filled ? (qty || 0) : 0 };
      });
      if (overrides.some(o => o.filled && (!o.price || !o.qty))) {
        toast("체결로 표시한 줄은 체결가와 수량을 모두 입력하세요.", true);
        return;
      }
      btn.disabled = true;
      try {
        const r = await api.confirm(form.dataset.sid, form.dataset.date, overrides);
        toast(`${form.dataset.date} 체결 ${r.fills_created}건을 기록했습니다.`);
        onDone?.();
      } catch (err) {
        toast(err.message, true);
        btn.disabled = false;
      }
    });
  });
}
