// 전략 관리: 목록, 등록, 수정, 종료, 백테스트
import { api } from "../api.js";
import { badges, stateLine } from "../slip.js";
import { $, $$, errorHtml, esc, formValues, loading, openModal, toast } from "../util.js";

export async function render(view, _id, params) {
  view.innerHTML = `
    <div class="page-head">
      <div><h1>전략</h1><p class="sub">무한매수법과 VR 전략을 종목·계좌별로 등록해 동시에 관리합니다.</p></div>
      <div class="row">
        <label class="check small"><input type="checkbox" id="showEnded"> 종료된 전략도 보기</label>
        <button class="btn primary" id="newBtn" type="button">새 전략 등록</button>
      </div>
    </div>
    <div id="list">${loading()}</div>`;
  $("#newBtn").addEventListener("click", () => newStrategyModal(view));
  $("#showEnded").addEventListener("change", () => load(view));
  await load(view);
  if (params.get("new")) newStrategyModal(view);
}

async function load(view) {
  const box = $("#list", view);
  try {
    const list = await api.strategies($("#showEnded").checked);
    if (!list.length) {
      box.innerHTML = `<div class="empty"><p>등록된 전략이 없습니다. 실전 전략이나 연습용 시뮬레이션 전략을 등록해 보세요.</p></div>`;
      return;
    }
    const group = (title, items) => items.length ? `<section class="section"><h2>${title} <span class="muted small">${items.length}개</span></h2>
      <div class="table-wrap"><table><thead><tr><th>전략</th><th>상태</th><th>현재</th><th>계좌</th><th></th></tr></thead><tbody>
      ${items.map(s => `<tr>
        <td><a href="#/strategy/${esc(s.id)}"><b>${esc(s.name)}</b></a></td>
        <td><div class="row">${badges(s.status_summary, { sim: s.is_simulation })}${s.status === "ended" ? `<span class="badge">종료됨</span>` : ""}</div></td>
        <td class="small"><div class="slip-state">${s.status_summary?.error ? esc(s.status_summary.error) : stateLine(s.status_summary)}</div></td>
        <td class="muted small">${esc(s.account_memo || "–")}</td>
        <td class="r"><a class="btn small" href="#/strategy/${esc(s.id)}">상세</a></td>
      </tr>`).join("")}</tbody></table></div></section>` : "";
    box.innerHTML = group("무한매수법", list.filter(s => s.type === "infinite")) + group("VR", list.filter(s => s.type === "vr"));
  } catch (err) {
    box.innerHTML = errorHtml(err);
  }
}

const today = () => new Date().toISOString().slice(0, 10);

async function newStrategyModal(view) {
  const html = `<form id="newForm">
    <h2>새 전략 등록</h2>
    <div class="stack">
      <div class="row">
        <div class="seg" role="radiogroup" aria-label="전략 종류">
          <label><input type="radio" name="type" value="infinite" checked>무한매수법</label>
          <label><input type="radio" name="type" value="vr">VR</label>
        </div>
        <div class="seg" role="radiogroup" aria-label="종목">
          <label><input type="radio" name="ticker" value="TQQQ" checked>TQQQ</label>
          <label><input type="radio" name="ticker" value="SOXL">SOXL</label>
        </div>
      </div>
      <div class="form">
        <label class="field"><span>이름 (비우면 자동)</span><input name="name" maxlength="40" placeholder="예: TQQQ V4.0 1호"></label>
        <label class="field"><span>계좌 메모</span><input name="account_memo" maxlength="50" placeholder="예: 키움 1"></label>
        <label class="field"><span>시작일</span><input type="date" name="start_date" value="${today()}"></label>
      </div>
      <fieldset data-for="infinite" class="form">
        <label class="field"><span>버전</span><select name="rule_version"><option value="v4.0">V4.0</option><option value="v2.2">V2.2</option></select></label>
        <label class="field"><span>분할 수</span><select name="splits"><option value="40">40분할</option><option value="20">20분할</option></select></label>
        <label class="field"><span>원금 ($)</span><input type="number" name="principal" min="1" step="1" placeholder="20000"></label>
        <label class="field"><span>큰수 % (선택)</span><input type="number" name="big_pct" min="0.05" max="0.2" step="0.01" placeholder="0.10"></label>
        <label class="field"><span>사다리 줄 수</span><input type="number" name="ladder_count" min="0" max="20" value="8"></label>
        <label class="check"><input type="checkbox" name="compounding"> 사이클마다 수익 복리</label>
      </fieldset>
      <fieldset data-for="vr" class="form" hidden>
        <label class="field"><span>유형</span><select name="vr_type"><option value="installment">적립식</option><option value="lump_sum">거치식</option><option value="withdrawal">인출식</option></select></label>
        <label class="field"><span>시작 V ($)</span><input type="number" name="start_v" min="1" step="1" placeholder="8000"></label>
        <label class="field"><span>시작 Pool ($)</span><input type="number" name="start_pool" min="0" step="1" placeholder="2000"></label>
        <label class="field"><span>2주 적립/인출금 ($)</span><input type="number" name="cycle_amount" min="0" step="1" value="0"></label>
        <label class="field"><span>G</span><input type="number" name="g" min="1" step="1" value="10"></label>
        <label class="field"><span>밴드</span><input type="number" name="band" min="0.05" max="0.45" step="0.01" value="0.15"></label>
        <label class="field"><span>이미 가진 수량</span><input type="number" name="initial_qty" min="0" step="1" value="0"></label>
      </fieldset>
      <div class="form">
        <label class="check field wide"><input type="checkbox" name="is_simulation"> 시뮬레이션 전략 (실제 돈 없이 과거 시세로 백테스트)</label>
        <label class="field" data-for="sim" hidden><span>백테스트 시작일</span><input type="date" name="bt_start" value="2024-01-02"></label>
      </div>
    </div>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">등록</button></div>
  </form>`;
  const p = openModal(html, async form => {
    const v = formValues(form);
    const body = { type: v.type, ticker: v.ticker, name: v.name, account_memo: v.account_memo || "", is_simulation: v.is_simulation, start_date: v.start_date };
    if (v.type === "infinite") {
      Object.assign(body, { rule_version: v.rule_version, splits: v.rule_version === "v2.2" ? 40 : Number(v.splits), principal: v.principal, compounding: v.compounding, ladder_count: v.ladder_count, big_pct: v.big_pct });
      if (!body.principal) throw new Error("원금을 입력하세요.");
    } else {
      Object.assign(body, { vr_type: v.vr_type, start_v: v.start_v, start_pool: v.start_pool, cycle_amount: v.cycle_amount || 0, g: v.g, band: v.band, initial_qty: v.initial_qty || 0 });
      if (!body.start_v || body.start_pool === undefined) throw new Error("시작 V와 시작 Pool을 입력하세요.");
    }
    if (body.is_simulation) delete body.start_date;
    Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);
    const s = await api.createStrategy(body);
    if (s.warnings?.length) toast(s.warnings.join(" "), true);
    if (body.is_simulation) {
      toast("백테스트를 실행하는 중입니다. 1~2분 걸릴 수 있습니다.");
      try {
        const r = await api.backtest(s.id, v.bt_start);
        toast(`백테스트 완료: 가상 체결 ${r.fills_created}건`);
      } catch (err) {
        toast(`전략은 등록했지만 백테스트가 실패했습니다: ${err.message}`, true);
      }
    } else if (!s.warnings?.length) {
      toast("전략을 등록했습니다.");
    }
    location.hash = `#/strategy/${s.id}`;
    return s;
  });
  const form = $("#newForm");
  const sync = () => {
    const type = form.querySelector("[name=type]:checked").value;
    $$("fieldset[data-for]", form).forEach(f => {
      const on = f.dataset.for === type;
      f.hidden = !on;
      $$("input,select", f).forEach(el => (el.disabled = !on));
    });
    const v22 = form.rule_version.value === "v2.2";
    form.splits.value = v22 ? "40" : form.splits.value;
    form.splits.disabled = v22 || type !== "infinite";
    const sim = form.is_simulation.checked;
    $("[data-for=sim]", form).hidden = !sim;
    form.start_date.disabled = sim;
  };
  form.addEventListener("change", sync);
  sync();
  await p;
  // 등록 후에는 해시가 바뀌어 상세 화면으로 이동한다. 취소했으면 목록 유지
  if (location.hash.startsWith("#/strategies")) load(view);
}

export function editStrategyModal(s) {
  const inf = s.type === "infinite";
  return openModal(`<form>
    <h2>설정 수정</h2>
    <p class="muted small" style="margin-bottom:12px">원금·분할·유형처럼 계산의 바탕이 되는 값은 바꿀 수 없습니다. 바꾸려면 새 전략으로 등록하세요.</p>
    <div class="form">
      <label class="field"><span>이름</span><input name="name" maxlength="40" value="${esc(s.name)}"></label>
      <label class="field"><span>계좌 메모</span><input name="account_memo" maxlength="50" value="${esc(s.account_memo || "")}"></label>
      ${inf ? `
        <label class="field"><span>큰수 %</span><input type="number" name="big_pct" min="0.05" max="0.2" step="0.01" value="${s.big_pct ?? ""}" placeholder="기본값"></label>
        <label class="field"><span>사다리 줄 수</span><input type="number" name="ladder_count" min="0" max="20" value="${s.ladder_count ?? 8}"></label>
        <label class="check"><input type="checkbox" name="compounding" ${s.compounding ? "checked" : ""}> 수익 복리</label>` : `
        <label class="field"><span>2주 적립/인출금 ($)</span><input type="number" name="cycle_amount" min="0" step="1" value="${s.cycle_amount ?? 0}"></label>
        <label class="field"><span>G</span><input type="number" name="g" min="1" step="1" value="${s.g ?? 10}"></label>
        <label class="field"><span>밴드</span><input type="number" name="band" min="0.05" max="0.45" step="0.01" value="${s.band ?? 0.15}"></label>`}
    </div>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">저장</button></div>
  </form>`, async form => {
    await api.updateStrategy(s.id, formValues(form));
    toast("설정을 저장했습니다.");
    return true;
  });
}

export function endStrategyModal(s) {
  return openModal(`<form>
    <h2>전략 종료</h2>
    <p>${esc(s.name)} 전략을 종료합니다. 체결 기록은 그대로 남고, 오늘 주문 화면에서만 빠집니다.</p>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">종료</button></div>
  </form>`, async () => {
    await api.endStrategy(s.id);
    toast("전략을 종료했습니다.");
    return true;
  });
}

export function backtestModal(s) {
  return openModal(`<form>
    <h2>백테스트 다시 실행</h2>
    <p class="muted small" style="margin-bottom:12px">이 시뮬레이션 전략의 가상 체결을 모두 지우고 시작일부터 다시 계산합니다.</p>
    <label class="field"><span>시작일</span><input type="date" name="start_date" value="${esc(s.start_date || "2024-01-02")}" required></label>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">실행</button></div>
  </form>`, async form => {
    const r = await api.backtest(s.id, formValues(form).start_date);
    toast(`백테스트 완료: 가상 체결 ${r.fills_created}건`);
    return true;
  });
}

