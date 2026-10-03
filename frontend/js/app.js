// 화면 전환(해시 라우터), 테마, 연결 설정, 서버 깨우기 안내
import { api, conn } from "./api.js";
import { $, $$, esc, openModal, toast } from "./util.js";
import * as dashboard from "./views/dashboard.js";
import * as strategies from "./views/strategies.js";
import * as strategy from "./views/strategy.js";
import * as data from "./views/data.js";
import * as summary from "./views/summary.js";
import * as chat from "./views/chat.js";

const ROUTES = [
  [/^\/?$/, dashboard, "dashboard", "오늘 주문"],
  [/^\/strategies$/, strategies, "strategies", "전략"],
  [/^\/strategy\/([\w-]+)$/, strategy, "strategies", "전략 상세"],
  [/^\/data$/, data, "data", "체결 기록"],
  [/^\/summary$/, summary, "summary", "요약·통계"],
  [/^\/chat$/, chat, "chat", "AI 비서"],
];

let renderSeq = 0;

async function route() {
  const raw = location.hash.slice(1) || "/";
  const [path, query = ""] = raw.split("?");
  const params = new URLSearchParams(query);
  const view = $("#view");
  const hit = ROUTES.map(([re, mod, nav, title]) => ({ m: path.match(re), mod, nav, title })).find(x => x.m);
  $$(".nav a").forEach(a => a.toggleAttribute("aria-current", false));
  if (!hit) {
    view.innerHTML = `<div class="empty"><p>없는 화면입니다.</p><a class="btn" href="#/">오늘 주문으로</a></div>`;
    return;
  }
  $(`.nav a[data-nav="${hit.nav}"]`)?.setAttribute("aria-current", "page");
  document.title = `${hit.title} · Rule_Keeper`;
  const seq = ++renderSeq;
  view.dataset.seq = seq;
  try {
    await hit.mod.render(view, hit.m[1], params);
  } catch (err) {
    if (view.dataset.seq == seq) view.innerHTML = `<p class="error-box">${esc(err.message)}</p>`;
  }
}

// ---- 테마 ----
function currentTheme() {
  const t = document.documentElement.dataset.theme;
  if (t) return t;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
$("#themeBtn").addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("rk_theme", next); } catch (e) { /* 무시 */ }
  route();   // 그래프 색을 새 테마로 다시 그린다
});

// ---- 연결 설정 ----
$("#settingsBtn").addEventListener("click", async () => {
  const p = openModal(`<form id="connForm">
    <h2>연결 설정</h2>
    <p class="muted small" style="margin-bottom:14px">이 브라우저에만 저장됩니다. API 키는 서버 .env의 APP_API_KEY와 같은 값이며, 체결 확정·전략 등록·채팅처럼 데이터를 바꾸는 요청에 필요합니다.</p>
    <div class="stack">
      <label class="field"><span>서버 주소</span><input name="base" value="${esc(conn.base)}" placeholder="http://127.0.0.1:8000"></label>
      <label class="field"><span>API 키</span><input name="key" type="password" autocomplete="off" value="${esc(conn.key)}" placeholder="비워 두면 키 없이 요청"></label>
      <p id="connResult" class="small muted"></p>
    </div>
    <div class="actions"><button class="btn" type="button" id="connTest">연결 확인</button><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">저장</button></div>
  </form>`, async form => {
    conn.base = form.base.value;
    conn.key = form.key.value;
    toast("연결 설정을 저장했습니다.");
    return true;
  });
  $("#connTest").addEventListener("click", async () => {
    const form = $("#connForm"), out = $("#connResult");
    const old = conn.base;
    conn.base = form.base.value;
    out.textContent = "확인하는 중…";
    try {
      const h = await api.health();
      out.textContent = `연결됨 · 저장소 ${h.storage}`;
    } catch (err) {
      out.textContent = err.message;
    } finally {
      conn.base = old;
    }
  });
  if (await p) route();
});

// ---- 서버 깨우기 (Render 무료 서버는 쉬다가 첫 요청에 30~60초 걸린다) ----
async function wake() {
  const banner = $("#banner");
  const slow = setTimeout(() => { banner.hidden = false; banner.textContent = "서버를 깨우는 중입니다. 무료 서버라 처음 한 번은 최대 1분쯤 걸립니다."; }, 2500);
  try {
    await api.health();
    banner.hidden = true;
  } catch (err) {
    banner.hidden = false;
    banner.textContent = `${err.message}`;
  } finally {
    clearTimeout(slow);
  }
}

window.addEventListener("hashchange", route);
wake().then(route);
