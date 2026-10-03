// 오늘 주문: 전략별 다음 거래일 주문 전표 + 체결 확인 대기
import { api, conn } from "../api.js";
import { bindConfirm, slipHtml } from "../slip.js";
import { $, errorHtml, loading, toast } from "../util.js";

let syncedThisSession = false;

export async function render(view) {
  view.innerHTML = `
    <div class="page-head">
      <div>
        <h1>오늘 밤 걸 주문</h1>
        <p class="sub" id="dashSub">전략마다 다음 거래일에 넣을 주문을 계산했습니다.</p>
      </div>
      <div class="row">
        <span class="muted small" id="syncState"></span>
        <button class="btn" id="syncBtn" type="button">시세 갱신</button>
      </div>
    </div>
    <div id="tally" class="tally"></div>
    <div id="slips" class="section">${loading("주문표를 계산하는 중")}</div>`;

  $("#syncBtn").addEventListener("click", () => sync(view, true));
  // 접속할 때 한 번 자동으로 시세를 채운다 (키가 있을 때만)
  if (!syncedThisSession && conn.key) await sync(view, false);
  else await load(view);
}

async function sync(view, manual) {
  const btn = $("#syncBtn"), state = $("#syncState");
  btn.disabled = true;
  state.textContent = "시세를 받는 중…";
  try {
    const r = await api.syncPrices();
    syncedThisSession = true;
    const added = Object.values(r).reduce((a, x) => a + (x.added || 0), 0);
    const last = Object.values(r).map(x => x.last_date).filter(Boolean).sort().pop();
    state.textContent = last ? `${last} 종가까지 반영` : "";
    if (manual) toast(added ? `새 시세 ${added}건을 받았습니다.` : "이미 최신 시세입니다.");
  } catch (err) {
    state.textContent = "";
    if (manual) toast(err.message, true);
  } finally {
    btn.disabled = false;
  }
  await load(view);
}

async function load(view) {
  const box = $("#slips", view);
  try {
    const items = await api.ordersToday();
    renderItems(view, items);
  } catch (err) {
    box.innerHTML = errorHtml(err);
  }
}

function renderItems(view, items) {
  const box = $("#slips", view);
  if (!items.length) {
    $("#tally").innerHTML = "";
    box.innerHTML = `<div class="empty"><p>아직 운용 중인 전략이 없습니다.</p>
      <a class="btn primary" href="#/strategies?new=1">첫 전략 등록하기</a></div>`;
    return;
  }
  const inf = items.filter(x => x.status?.type === "infinite").length;
  const vr = items.filter(x => x.status?.type === "vr").length;
  const pending = items.reduce((a, x) => a + (x.to_confirm?.length || 0), 0);
  const attention = items.filter(x => ["reverse", "quarter_stop"].includes(x.status?.mode) || x.status?.rebalance_due).length;
  const dates = items.map(x => x.today?.date).filter(Boolean).sort();
  if (dates.length) $("#dashSub").textContent = `${dates[0]} 장에 넣을 주문입니다. 매수는 빨강, 매도는 파랑으로 표시합니다.`;
  $("#tally").innerHTML = `
    <span><b>${items.length}</b>개 전략 (무한매수 ${inf} · VR ${vr})</span>
    <span class="${pending ? "warn" : ""}"><b>${pending}</b>건 체결 확인 대기</span>
    <span class="${attention ? "warn" : ""}"><b>${attention}</b>개 주의 (리버스·쿼터손절·V 갱신일)</span>`;
  box.innerHTML = `<div class="slips">${items.map(slipHtml).join("")}</div>`;
  bindConfirm(box, () => load(view));
}

