// 체결 기록 관리: 조회·추가·수정·삭제·내보내기 (과제 필수 data CRUD)
import { api } from "../api.js";
import { $, BUY_ROLES, errorHtml, esc, formValues, loading, openModal, ROLE_KO, SELL_ROLES, toast, todayStr } from "../util.js";
import { fillTable } from "./strategy.js";

let strategies = [];
let rows = [];

export async function render(view, _id, params) {
  view.innerHTML = `
    <div class="page-head">
      <div><h1>체결 기록</h1><p class="sub">증권사에서 실제로 체결된 내역입니다. 상태(T, 평단, V)는 이 기록을 처음부터 다시 따라가며 계산합니다.</p></div>
      <div class="row">
        <a class="btn" id="csvBtn" download>CSV 내려받기</a>
        <a class="btn" id="jsonBtn" download>JSON 내려받기</a>
        <button class="btn primary" id="addBtn" type="button">체결 직접 입력</button>
      </div>
    </div>
    <form id="filter" class="form panel flat">
      <label class="field"><span>전략</span><select name="strategy_id"><option value="">전체</option></select></label>
      <label class="field"><span>시작일</span><input type="date" name="date_from"></label>
      <label class="field"><span>종료일</span><input type="date" name="date_to"></label>
      <label class="field"><span>출처</span><select name="source"><option value="">전체</option><option value="auto">자동 확정</option><option value="manual">직접 입력</option><option value="backtest">백테스트</option></select></label>
      <div class="row"><button class="btn" type="submit">조회</button><button class="btn" type="reset">초기화</button></div>
    </form>
    <p class="muted small section" id="count" style="margin-top:20px"></p>
    <div id="table">${loading()}</div>`;

  try {
    strategies = await api.strategies(true);
  } catch (err) {
    $("#table").innerHTML = errorHtml(err);
    return;
  }
  const sel = $("#filter [name=strategy_id]");
  sel.insertAdjacentHTML("beforeend", strategies.map(s => `<option value="${esc(s.id)}">${esc(s.name)}${s.status === "ended" ? " (종료)" : ""}</option>`).join(""));
  if (params.get("strategy")) sel.value = params.get("strategy");

  $("#filter").addEventListener("submit", e => { e.preventDefault(); load(); });
  $("#filter").addEventListener("reset", () => setTimeout(load));
  $("#addBtn").addEventListener("click", () => editModal(null));
  $("#table").addEventListener("click", e => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const row = rows.find(r => r.id === btn.closest("tr").dataset.id);
    if (btn.dataset.act === "edit") editModal(row);
    else deleteModal(row);
  });
  await load();
}

function filters() {
  const v = formValues($("#filter"));
  return { strategy_id: v.strategy_id, date_from: v.date_from, date_to: v.date_to, source: v.source };
}

async function load() {
  const f = filters();
  $("#csvBtn").href = api.exportUrl({ ...f, source: undefined, format: "csv" });
  $("#jsonBtn").href = api.exportUrl({ ...f, source: undefined, format: "json" });
  const box = $("#table");
  box.innerHTML = loading();
  try {
    rows = await api.data({ ...f, limit: 500 });
    const names = new Map(strategies.map(s => [s.id, s.name]));
    $("#count").textContent = rows.length >= 500 ? "최근 500건만 보여 줍니다. 기간이나 전략으로 좁혀 보세요." : `${rows.length}건`;
    box.innerHTML = rows.length ? fillTable(rows, { names, actions: true })
      : `<div class="empty"><p>조건에 맞는 체결 기록이 없습니다.</p></div>`;
    box.querySelector(".table-wrap")?.classList.add("scroll");
  } catch (err) {
    box.innerHTML = errorHtml(err);
  }
}

function roleOptions(side, selected) {
  return (side === "sell" ? SELL_ROLES : BUY_ROLES).map(r => `<option value="${r}" ${r === selected ? "selected" : ""}>${esc(ROLE_KO[r])}</option>`).join("");
}

async function editModal(row) {
  const isNew = !row;
  const active = strategies.filter(s => s.status !== "ended");
  const html = `<form id="dataForm">
    <h2>${isNew ? "체결 직접 입력" : "체결 기록 수정"}</h2>
    ${isNew ? `<p class="muted small" style="margin-bottom:12px">주문표 확정을 쓰지 않고 증권사 체결 내역을 그대로 옮겨 적을 때 사용합니다.</p>` : `<p class="muted small" style="margin-bottom:12px">${esc(ROLE_KO[row.role])} 기록입니다. 전략이나 역할을 바꾸려면 삭제하고 다시 입력하세요.</p>`}
    <div class="form">
      ${isNew ? `
        <label class="field wide"><span>전략</span><select name="strategy_id" required>${active.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join("")}</select></label>
        <label class="field"><span>구분</span><select name="side"><option value="buy">매수</option><option value="sell">매도</option></select></label>
        <label class="field"><span>역할</span><select name="role">${roleOptions("buy", "star_buy")}</select></label>
        <label class="field"><span>주문 방식</span><select name="order_type"><option value="LOC">LOC</option><option value="LIMIT">지정가</option><option value="MOC">MOC</option><option value="">기타</option></select></label>` : ""}
      <label class="field"><span>날짜</span><input type="date" name="date" required value="${esc(row?.date || todayStr())}"></label>
      <label class="field"><span>체결 단가 ($)</span><input type="number" name="value" step="0.01" min="0.01" required value="${row?.value ?? ""}"></label>
      <label class="field"><span>체결 수량 (주)</span><input type="number" name="qty" step="1" min="1" required value="${row?.qty ?? ""}"></label>
      <label class="field wide"><span>메모</span><input name="memo" maxlength="200" value="${esc(row?.memo || "")}"></label>
    </div>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">${isNew ? "기록 추가" : "저장"}</button></div>
  </form>`;
  const p = openModal(html, async form => {
    const v = formValues(form);
    if (isNew) {
      await api.addData({ ...v, memo: v.memo || "", order_type: v.order_type || "" });
      toast("체결 기록을 추가했습니다.");
    } else {
      await api.updateData(row.id, { date: v.date, value: v.value, qty: v.qty, memo: v.memo ?? "" });
      toast("체결 기록을 수정했습니다.");
    }
    return true;
  });
  const form = $("#dataForm");
  form.side?.addEventListener("change", () => { form.role.innerHTML = roleOptions(form.side.value); });
  if (await p) load();
}

async function deleteModal(row) {
  const ok = await openModal(`<form>
    <h2>체결 기록 삭제</h2>
    <p>${esc(row.date)} ${esc(ROLE_KO[row.role])} ${row.value} × ${row.qty}주 기록을 지웁니다. 지우면 그 전략의 T와 평단이 다시 계산됩니다.</p>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">삭제</button></div>
  </form>`, async () => { await api.deleteData(row.id); toast("체결 기록을 삭제했습니다."); return true; });
  if (ok) load();
}
