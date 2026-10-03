// 전략 상세: 현재 상태, 그래프, 다음 주문표, 사이클/VR 이력, 최근 체결
import { api } from "../api.js";
import { colors, lineChart } from "../chart.js";
import { badges, bindConfirm, linesHtml } from "../slip.js";
import { $, BAND_POS_KO, errorHtml, esc, formValues, loading, money, pct, ROLE_KO, SIDE_KO, SOURCE_KO, toast, usd, VR_TYPE_KO, whole } from "../util.js";
import { backtestModal, editStrategyModal, endStrategyModal } from "./strategies.js";

export async function render(view, id) {
  view.innerHTML = loading("전략을 불러오는 중");
  let s;
  try {
    const all = await api.strategies(true);
    s = all.find(x => x.id === id);
    if (!s) throw new Error("전략을 찾을 수 없습니다. 목록에서 다시 골라 주세요.");
  } catch (err) {
    view.innerHTML = errorHtml(err);
    return;
  }
  const st = s.status_summary || {};
  const ended = s.status === "ended";
  const isVr = s.type === "vr";

  view.innerHTML = `
    <div class="page-head">
      <div>
        <p class="muted small"><a href="#/strategies">전략</a> / ${esc(s.ticker)}</p>
        <h1>${esc(s.name)}</h1>
        <div class="row" style="margin-top:8px">${badges(st, { sim: s.is_simulation })}${ended ? `<span class="badge">종료됨</span>` : ""}
          ${s.account_memo ? `<span class="muted small">계좌 ${esc(s.account_memo)}</span>` : ""}
          <span class="muted small">${esc(st.last_date || "")} 종가 ${money(st.last_close)}</span></div>
      </div>
      <div class="row">
        <a class="btn" href="#/chat?strategy=${esc(id)}">AI에게 묻기</a>
        ${!ended ? `<button class="btn" id="editBtn" type="button">설정 수정</button>` : ""}
        ${s.is_simulation && !ended ? `<button class="btn" id="btBtn" type="button">백테스트 다시</button>` : ""}
        ${!ended ? `<button class="btn danger" id="endBtn" type="button">전략 종료</button>` : ""}
      </div>
    </div>
    ${st.error ? errorHtml(st.error) : `<dl class="facts">${isVr ? vrFacts(st, s) : infFacts(st)}</dl>`}
    <div class="grid-2 section">
      <section class="panel"><h2 style="margin-bottom:12px">${isVr ? "평가금과 밴드" : "종가와 평단·별지점"} <span class="muted small">최근 6개월</span></h2><div id="chart">${loading()}</div></section>
      <section class="slip" id="sheet"><div class="slip-head"><h3>다음 거래일 주문</h3></div>${loading()}</section>
    </div>
    ${isVr && !ended ? rebalancePanel(s) : ""}
    <section class="section" id="history"><h2>${isVr ? "V 갱신 이력" : "사이클 이력"}</h2>${loading()}</section>
    <section class="section"><div class="row" style="justify-content:space-between;margin-bottom:12px"><h2>최근 체결</h2>
      <a class="btn small" href="#/data?strategy=${esc(id)}">체결 기록 전체 보기</a></div><div id="fills">${loading()}</div></section>`;

  $("#editBtn")?.addEventListener("click", async () => { if (await editStrategyModal(s)) render(view, id); });
  $("#endBtn")?.addEventListener("click", async () => { if (await endStrategyModal(s)) location.hash = "#/strategies"; });
  $("#btBtn")?.addEventListener("click", async () => { if (await backtestModal(s)) render(view, id); });

  // 나머지는 동시에 불러온다
  const from = sixMonthsBefore(st.last_date);
  const [prices, fills, sheet, snaps] = await Promise.allSettled([
    api.prices(s.ticker, isVr ? undefined : from),
    api.data({ strategy_id: id, limit: 5000 }),
    ended ? Promise.resolve(null) : api.nextOrders(id),
    isVr ? api.vrSnapshots(id) : Promise.resolve(null),
  ]);

  renderSheet(view, id, sheet, ended);
  if (prices.status === "fulfilled" && fills.status === "fulfilled") {
    if (isVr) vrChart($("#chart"), s, prices.value, fills.value, snaps.value || [], from);
    else infChart($("#chart"), st, prices.value, fills.value, from);
  } else {
    $("#chart").innerHTML = errorHtml(prices.reason || fills.reason);
  }
  $("#history").innerHTML = `<h2 style="margin-bottom:12px">${isVr ? "V 갱신 이력" : "사이클 이력"}</h2>` +
    (isVr ? snapTable(snaps.value || []) : cycleTable(st.cycles || []));
  $("#history .table-wrap")?.classList.add("scroll");
  $("#fills").innerHTML = fills.status === "fulfilled" ? fillTable(fills.value.slice(0, 20)) : errorHtml(fills.reason);
  if (isVr && !ended) bindRebalance(view, s);
}

function sixMonthsBefore(d) {
  const x = d ? new Date(d) : new Date();
  x.setMonth(x.getMonth() - 6);
  return x.toISOString().slice(0, 10);
}

function fact(label, value, small = "") {
  return `<div class="fact"><dt>${label}</dt><dd class="num">${value}${small ? ` <small>${small}</small>` : ""}</dd></div>`;
}

function infFacts(st) {
  return [
    fact("모드", esc(st.mode_ko), esc(st.mode === "normal" ? st.phase_ko : "")),
    fact("T", money(st.t, 2), `/ ${st.splits}`),
    fact("1회 매수금", usd(st.unit)),
    fact("별%", st.star_pct !== undefined ? pct(st.star_pct) : "–"),
    fact("별지점", money(st.star)),
    fact("평단", st.qty ? money(st.avg) : "–"),
    fact("보유", `${st.qty}`, "주"),
    fact("잔금", usd(st.cash)),
    fact("평가손익", st.pnl !== undefined ? usd(st.pnl) : "–", st.pnl_pct !== undefined ? pct(st.pnl_pct) : ""),
    fact("실현 수익", usd(st.profit_total), `${(st.cycles || []).length}사이클 완료`),
    st.reverse_star ? fact("리버스 별지점", money(st.reverse_star), `탈출 ${money(st.reverse_exit_price)}`) : "",
    st.quarter_stop ? fact("쿼터손절", `${st.quarter_stop.buys}/10회`, `1회 ${usd(st.quarter_stop.unit)}`) : "",
  ].join("");
}

function vrFacts(st, s) {
  return [
    fact("V", usd(st.v, 0)),
    fact("평가금", usd(st.e, 0), esc(BAND_POS_KO[st.band_position] || "")),
    fact("밴드 하단", usd(st.band_low, 0)),
    fact("밴드 상단", usd(st.band_high, 0)),
    fact("Pool", usd(st.pool, 0)),
    fact("이번 사이클 남은 매수 한도", usd(st.budget_left, 0)),
    fact("보유", `${st.qty}`, "주"),
    fact("유형", esc(VR_TYPE_KO[st.vr_type]), `G ${st.g} · 적립/인출 ${usd(s.cycle_amount || 0, 0)}`),
    fact("마지막 갱신 후", `${st.days_since_rebalance}`, st.rebalance_due ? "거래일 · 갱신일" : "거래일 (10일마다 갱신)"),
  ].join("");
}

function renderSheet(view, id, res, ended) {
  const box = $("#sheet");
  if (ended) { box.innerHTML = `<div class="slip-head"><h3>다음 거래일 주문</h3><p class="muted">종료된 전략입니다.</p></div>`; return; }
  if (res.status === "rejected") { box.innerHTML = `<div class="slip-head"><h3>다음 거래일 주문</h3>${errorHtml(res.reason)}</div>`; return; }
  const sh = res.value;
  box.innerHTML = `<div class="slip-head">
      <div class="slip-title"><h3>다음 거래일 주문</h3><span class="slip-date">${esc(sh.date)} 주문 · ${esc(sh.based_on)} 종가 기준</span></div>
      ${sh.provisional ? `<p class="note">이전 주문표의 체결이 확정되지 않아 임시로 계산했습니다. 오늘 주문 화면에서 체결을 먼저 확정하세요.</p>` : ""}
      ${sh.meta?.notice ? `<p class="note info">${esc(sh.meta.notice)}</p>` : ""}
    </div><div class="tear" aria-hidden="true"></div>${linesHtml(sh.lines)}`;
  bindConfirm(box, () => render(view, id));
}

function infChart(el, st, prices, fills, from) {
  const c = colors();
  const pts = prices.map(p => ({ x: p.date, y: p.close }));
  const recent = fills.filter(f => f.date >= from);
  lineChart(el, {
    series: [{ name: "종가", color: c.ink, points: pts }],
    hlines: st.qty ? [{ y: st.avg, name: "평단", color: c.muted }, { y: st.star, name: "별지점", color: c.warn }] : [],
    markers: recent.map(f => ({ x: f.date, y: f.value, color: f.side === "buy" ? c.buy : c.sell, label: f.side === "buy" ? "매수 체결" : "매도 체결" })),
  });
}

function vrChart(el, s, prices, fills, snaps, from) {
  const c = colors();
  // 체결로 날짜별 보유 수량을 다시 계산해 평가금 = 수량 × 종가
  const delta = new Map();
  for (const f of fills) delta.set(f.date, (delta.get(f.date) || 0) + (f.side === "buy" ? f.qty : -f.qty));
  let qty = Number(s.initial_qty || 0);
  const start = s.start_date || "";
  const snapList = [...snaps].sort((a, b) => a.date.localeCompare(b.date));
  let k = -1;
  const E = [], V = [], LO = [], HI = [];
  for (const p of prices) {
    if (p.date < start) continue;
    qty += delta.get(p.date) || 0;
    while (k + 1 < snapList.length && snapList[k + 1].date <= p.date) k++;
    if (p.date < from) continue;
    E.push({ x: p.date, y: qty * p.close });
    if (k >= 0) {
      V.push({ x: p.date, y: snapList[k].v });
      LO.push({ x: p.date, y: snapList[k].band_low });
      HI.push({ x: p.date, y: snapList[k].band_high });
    }
  }
  lineChart(el, {
    series: [
      { name: "평가금", color: c.ink, points: E },
      { name: "V", color: c.muted, points: V, width: 1.4 },
      { name: "밴드 하단", color: c.buy, points: LO, dash: true, width: 1.2 },
      { name: "밴드 상단", color: c.sell, points: HI, dash: true, width: 1.2 },
    ],
    yFormat: v => whole(v),
  });
}

function cycleTable(cycles) {
  if (!cycles.length) return `<p class="muted">아직 끝난 사이클이 없습니다. 지정가 매도로 모두 팔리면 한 사이클이 끝납니다.</p>`;
  const rows = [...cycles].reverse().map(c => `<tr>
    <td>${c.cycle_no}회차</td><td>${esc(c.start)}</td><td>${esc(c.end)}</td>
    <td class="r num">${usd(c.principal, 0)}</td><td class="r num">${usd(c.profit)}</td>
    <td class="r num">${pct(c.principal ? c.profit / c.principal * 100 : null)}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th>회차</th><th>시작</th><th>종료</th><th class="r">원금</th><th class="r">수익</th><th class="r">수익률</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function snapTable(snaps) {
  if (!snaps.length) return `<p class="muted">아직 V 갱신 기록이 없습니다.</p>`;
  const rows = [...snaps].reverse().slice(0, 30).map(x => `<tr>
    <td>${esc(x.date)}</td><td class="r num">${whole(x.v)}</td><td class="r num">${whole(x.e)}</td>
    <td class="r num">${whole(x.band_low)}~${whole(x.band_high)}</td><td class="r num">${whole(x.pool)}</td>
    <td class="r num">${whole(x.cycle_amount)}</td><td class="r num">${whole(x.pool_limit)}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th>갱신일</th><th class="r">V</th><th class="r">평가금</th><th class="r">밴드</th><th class="r">Pool</th><th class="r">적립/인출</th><th class="r">매수 한도</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// 백테스트 메모의 역할 이름(star_buy 등)을 우리말로
const memoKo = m => (m || "").replace(/\b[a-z_]+\b/g, w => ROLE_KO[w] || w);

export function fillTable(rows, { names, actions = false } = {}) {
  if (!rows.length) return `<p class="muted">체결 기록이 없습니다.</p>`;
  const body = rows.map(f => `<tr data-id="${esc(f.id)}">
    <td>${esc(f.date)}</td>
    ${names ? `<td>${esc(names.get(f.strategy_id) || f.strategy_id)}</td>` : ""}
    <td><span class="badge ${f.side}">${SIDE_KO[f.side]}</span></td>
    <td>${esc(ROLE_KO[f.role] || f.role)}</td>
    <td class="r num">${money(f.value)}</td><td class="r num">${f.qty}</td>
    <td class="r num">${money(f.value * f.qty)}</td>
    <td class="memo">${esc(memoKo(f.memo))}</td>
    <td class="muted small">${esc(SOURCE_KO[f.source] || f.source || "")}</td>
    ${actions ? `<td class="r"><button class="btn small" data-act="edit" type="button">수정</button> <button class="btn small danger" data-act="del" type="button">삭제</button></td>` : ""}
  </tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th>날짜</th>${names ? "<th>전략</th>" : ""}<th>구분</th><th>역할</th><th class="r">단가</th><th class="r">수량</th><th class="r">금액</th><th>메모</th><th>출처</th>${actions ? "<th></th>" : ""}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function rebalancePanel(s) {
  const label = s.vr_type === "withdrawal" ? "이번 인출금" : s.vr_type === "installment" ? "이번 적립금" : "추가 입금";
  return `<section class="section panel">
    <h2>V 갱신</h2>
    <p class="muted small" style="margin:4px 0 12px">2주(10거래일)마다 V' = V + Pool/G ${s.vr_type === "withdrawal" ? "− 인출금" : "+ 적립금"}으로 새 V와 밴드를 정합니다. 먼저 미리보기로 확인하세요.</p>
    <form id="rbForm" class="form">
      <label class="field"><span>${label} ($)</span><input type="number" name="cycle_amount" min="0" step="1" value="${Number(s.cycle_amount || 0)}"></label>
      <div class="row"><button class="btn" type="submit">미리보기</button><button class="btn primary" type="button" id="rbApply" hidden>이 값으로 갱신</button></div>
    </form>
    <div id="rbOut" style="margin-top:12px"></div>
  </section>`;
}

function bindRebalance(view, s) {
  const form = $("#rbForm"), out = $("#rbOut"), apply = $("#rbApply");
  form.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      const v = formValues(form);
      const r = await api.vrRebalance(s.id, { cycle_amount: v.cycle_amount ?? 0, dry_run: true });
      const p = r.preview;
      out.innerHTML = `<dl class="facts">${fact("새 V", usd(p.v, 0))}${fact("밴드", `${whole(p.band_low)}~${whole(p.band_high)}`)}${fact("Pool", usd(p.pool, 0))}${fact("이번 매수 한도", usd(p.pool_limit, 0))}${fact("기준일", esc(p.date))}</dl>`;
      apply.hidden = false;
    } catch (err) { out.innerHTML = errorHtml(err); }
  });
  apply.addEventListener("click", async () => {
    apply.disabled = true;
    try {
      const v = formValues(form);
      await api.vrRebalance(s.id, { cycle_amount: v.cycle_amount ?? 0, dry_run: false });
      toast("V를 갱신했습니다. 주문표가 새 밴드로 바뀌었습니다.");
      render(view, s.id);
    } catch (err) { toast(err.message, true); apply.disabled = false; }
  });
}

