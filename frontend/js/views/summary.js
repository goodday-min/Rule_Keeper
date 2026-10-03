// 요약·통계: 종목별 시세 통계와 그래프, 전략별 성과, AI에게 들어가는 요약 원문
import { api } from "../api.js";
import { colors, lineChart } from "../chart.js";
import { $, $$, errorHtml, esc, loading, money, pct, usd, whole } from "../util.js";

let cache = {};

export async function render(view) {
  cache = {};
  view.innerHTML = `
    <div class="page-head">
      <div><h1>요약·통계</h1><p class="sub">일별 시세(시계열 데이터)와 전략 성과를 한눈에 봅니다. AI 비서는 아래 요약을 보고 답합니다.</p></div>
    </div>
    <section class="panel">
      <div class="row" style="justify-content:space-between;margin-bottom:14px">
        <div class="seg" role="radiogroup" aria-label="종목">
          <label><input type="radio" name="tk" value="TQQQ" checked>TQQQ</label>
          <label><input type="radio" name="tk" value="SOXL">SOXL</label>
        </div>
        <div class="seg" role="radiogroup" aria-label="기간">
          <label><input type="radio" name="rg" value="126">6개월</label>
          <label><input type="radio" name="rg" value="252" checked>1년</label>
          <label><input type="radio" name="rg" value="0">전체</label>
        </div>
      </div>
      <div id="priceChart">${loading()}</div>
    </section>
    <div id="stats" class="section">${loading()}</div>
    <section class="section"><h2>AI에게 들어가는 요약</h2>
      <p class="muted small" style="margin-bottom:10px">채팅을 보낼 때마다 이 글이 시스템 프롬프트에 들어갑니다 (GET /api/data/summary).</p>
      <div id="sumText">${loading()}</div></section>`;

  $$("input[name=tk], input[name=rg]", view).forEach(el => el.addEventListener("change", drawPrice));
  const [stats, sum] = await Promise.allSettled([api.statistics(), api.summary()]);
  $("#stats").innerHTML = stats.status === "fulfilled" ? statsHtml(stats.value) : errorHtml(stats.reason);
  $("#sumText").innerHTML = sum.status === "fulfilled" ? `<pre class="panel flat" style="white-space:pre-wrap;font:inherit;font-size:.88rem;margin:0">${esc(sum.value.text)}</pre>` : errorHtml(sum.reason);
  drawPrice();
}

async function drawPrice() {
  const tk = $("input[name=tk]:checked").value, rg = Number($("input[name=rg]:checked").value);
  const box = $("#priceChart");
  try {
    cache[tk] = cache[tk] || await api.prices(tk);
    const rows = rg ? cache[tk].slice(-rg) : cache[tk];
    // 20일 이동평균을 같이 그려 추세를 본다
    const all = cache[tk], start = all.length - rows.length;
    const ma = rows.map((r, i) => {
      const j = start + i;
      if (j < 19) return { x: r.date, y: null };
      const w = all.slice(j - 19, j + 1);
      return { x: r.date, y: w.reduce((a, b) => a + b.close, 0) / 20 };
    });
    const c = colors();
    lineChart(box, {
      series: [{ name: `${tk} 종가`, color: c.ink, points: rows.map(r => ({ x: r.date, y: r.close })) },
        { name: "20일 이동평균", color: c.warn, points: ma, width: 1.3 }],
      height: 280,
    });
  } catch (err) {
    box.innerHTML = errorHtml(err);
  }
}

function statsHtml(st) {
  const tickers = Object.entries(st.prices || {});
  const priceRows = tickers.map(([t, p]) => `<tr>
    <td><b>${esc(t)}</b></td><td>${esc(p.period_start)} ~ ${esc(p.period_end)}</td>
    <td class="r num">${whole(p.count)}</td><td class="r num">${money(p.mean)}</td><td class="r num">${money(p.max)}</td>
    <td class="r num">${money(p.min)}</td><td class="r num">${money(p.last)}</td>
    <td class="r num">${pct(p.change_30d_pct)} <span class="muted">${esc(p.trend_30d || "")}</span></td>
    <td class="r num">${pct(p.volatility_annual_pct, 1, false)}</td><td class="r num">${pct(p.max_drawdown_pct, 1, false)}</td></tr>`).join("");
  const inf = (st.strategies || []).filter(s => s.realized_profit !== undefined);
  const vr = (st.strategies || []).filter(s => s.v !== undefined);
  return `
    <h2>시세 통계</h2>
    <div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>종목</th><th>기간</th><th class="r">개수</th><th class="r">평균</th><th class="r">최대</th><th class="r">최소</th><th class="r">최근</th><th class="r">30일 추세</th><th class="r">연 변동성</th><th class="r">최대 낙폭</th></tr></thead><tbody>${priceRows}</tbody></table></div>
    <div class="grid-2 section">
      <section><h2 style="margin-bottom:12px">무한매수법 성과</h2>${inf.length ? `<div class="table-wrap"><table><thead><tr><th>전략</th><th class="r">완료 사이클</th><th class="r">실현 수익</th><th class="r">평가손익</th></tr></thead><tbody>
        ${inf.map(s => `<tr><td><a href="#/strategy/${esc(s.strategy_id)}">${esc(s.name)}</a></td><td class="r num">${s.cycles_done}</td><td class="r num">${usd(s.realized_profit)}</td><td class="r num">${usd(s.unrealized)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="muted">무한매수법 전략이 없습니다.</p>`}</section>
      <section><h2 style="margin-bottom:12px">VR 현황</h2>${vr.length ? `<div class="table-wrap"><table><thead><tr><th>전략</th><th class="r">V</th><th class="r">평가금</th><th class="r">Pool</th></tr></thead><tbody>
        ${vr.map(s => `<tr><td><a href="#/strategy/${esc(s.strategy_id)}">${esc(s.name)}</a></td><td class="r num">${whole(s.v)}</td><td class="r num">${whole(s.e)}</td><td class="r num">${whole(s.pool)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="muted">VR 전략이 없습니다.</p>`}</section>
    </div>`;
}
