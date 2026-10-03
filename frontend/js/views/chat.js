// AI 비서: 대화 목록 · 채팅 · 이번 답변에 들어간 요약 (3단)
import { api } from "../api.js";
import { $, errorHtml, esc, localTime, miniMarkdown, openModal, toast, TOOL_KO } from "../util.js";

const QUICK = ["오늘 뭐 걸어야 해?", "지금 소진에 가까운 전략 있어?", "별지점이 왜 이 가격이야?", "VR 전략은 밴드 안에 있어?", "최근 30일 TQQQ 추세 어때?"];

let state = { id: null, strategyId: "", messages: [], busy: false, list: [], strategies: [] };

export async function render(view, _id, params) {
  state = { id: params.get("c") || null, strategyId: params.get("strategy") || "", messages: [], busy: false, list: [], strategies: [] };
  view.innerHTML = `
    <div class="chat" id="chat">
      <aside class="chat-list" aria-label="대화 기록">
        <header class="row" style="justify-content:space-between"><b>대화 기록</b><button class="btn small" id="newChat" type="button">새 대화</button></header>
        <ul id="convList"><li class="muted small" style="padding:10px">불러오는 중</li></ul>
      </aside>
      <section class="chat-main">
        <div class="chat-top">
          <button class="btn small chat-toggle" id="listToggle" type="button">기록</button>
          <label class="row small"><span class="muted">대상</span>
            <select id="target"><option value="">전체 전략</option></select></label>
          <span class="spacer" style="flex:1"></span>
          <button class="btn small danger" id="delChat" type="button" hidden>이 대화 삭제</button>
        </div>
        <div class="msgs" id="msgs" aria-live="polite"></div>
        <form class="composer" id="composer">
          <label class="skip" for="input">질문</label>
          <textarea id="input" rows="1" maxlength="2000" placeholder="질문을 입력하세요. Enter로 보내고 Shift+Enter로 줄을 바꿉니다."></textarea>
          <button class="btn primary" type="submit" id="send">보내기</button>
        </form>
      </section>
      <aside class="chat-ctx" aria-label="AI에게 들어간 요약">
        <b>AI가 보는 요약</b>
        <p class="muted">질문할 때마다 이 요약이 함께 들어가고, 더 필요한 숫자는 AI가 도구로 직접 조회합니다. AI는 계산하지 않고 서버가 계산한 값만 인용합니다.</p>
        <pre id="ctx">불러오는 중</pre>
      </aside>
    </div>`;

  $("#newChat").addEventListener("click", () => { state.id = null; state.messages = []; drawMsgs(); drawList(); setHash(); $("#input").focus(); });
  $("#listToggle").addEventListener("click", () => $("#chat").classList.toggle("show-list"));
  $("#delChat").addEventListener("click", deleteCurrent);
  $("#target").addEventListener("change", e => { state.strategyId = e.target.value; loadCtx(); setHash(); });
  $("#composer").addEventListener("submit", e => { e.preventDefault(); send($("#input").value); });
  const input = $("#input");
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
  });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; });
  $("#msgs").addEventListener("click", e => { const c = e.target.closest(".chip"); if (c) send(c.textContent); });

  const [convs, strategies] = await Promise.allSettled([api.conversations(), api.strategies()]);
  state.list = convs.status === "fulfilled" ? convs.value : [];
  if (convs.status === "rejected") $("#convList").innerHTML = `<li>${errorHtml(convs.reason)}</li>`;
  else drawList();
  state.strategies = strategies.status === "fulfilled" ? strategies.value : [];
  $("#target").insertAdjacentHTML("beforeend", state.strategies.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join(""));
  $("#target").value = state.strategyId;

  if (state.id) await openConversation(state.id);
  else { drawMsgs(); loadCtx(); }
}

function setHash() {
  const p = new URLSearchParams();
  if (state.id) p.set("c", state.id);
  if (state.strategyId) p.set("strategy", state.strategyId);
  const h = "#/chat" + (p.toString() ? "?" + p : "");
  if (location.hash !== h) history.replaceState(null, "", h);
}

async function loadCtx(text) {
  const box = $("#ctx");
  if (text) { box.textContent = text; return; }
  try {
    box.textContent = (await api.summary(state.strategyId || undefined)).text;
  } catch (err) { box.textContent = err.message; }
}

function drawList() {
  const ul = $("#convList");
  if (!state.list.length) { ul.innerHTML = `<li class="muted small" style="padding:10px">아직 대화가 없습니다. 첫 질문을 보내면 여기에 저장됩니다.</li>`; return; }
  ul.innerHTML = state.list.map(c => `<li><button type="button" data-id="${esc(c.id)}" aria-current="${c.id === state.id}">
    <span class="t">${esc(c.title)}</span>
    <span class="m">${esc(localTime(c.updated_at))} · ${c.message_count}개 메시지${c.strategy_id ? " · " + esc(nameOf(c.strategy_id)) : ""}</span></button></li>`).join("");
  ul.querySelectorAll("button[data-id]").forEach(b => b.addEventListener("click", () => {
    $("#chat").classList.remove("show-list");
    openConversation(b.dataset.id);
  }));
}

const nameOf = id => state.strategies.find(s => s.id === id)?.name || "전략";

async function openConversation(id) {
  $("#msgs").innerHTML = `<div class="loading">대화를 불러오는 중</div>`;
  try {
    const c = await api.conversation(id);
    state.id = c.id;
    state.messages = c.messages || [];
    state.strategyId = c.strategy_id || "";
    $("#target").value = state.strategyId;
    drawMsgs();
    drawList();
    setHash();
    loadCtx();
  } catch (err) {
    state.id = null;
    $("#msgs").innerHTML = errorHtml(err);
    setHash();
  }
}

function msgHtml(m) {
  if (m.role === "user") return `<div class="msg user">${esc(m.content)}</div>`;
  const tools = (m.tools_used || []).map(t => `<span class="badge${t.ok ? "" : " warn"}" title="${esc(JSON.stringify(t.args))}">${esc(TOOL_KO[t.name] || t.name)}</span>`).join("");
  return `<div class="msg assistant">${miniMarkdown(m.content)}${tools ? `<div class="tools">${tools}</div>` : ""}</div>`;
}

function drawMsgs() {
  const box = $("#msgs");
  $("#delChat").hidden = !state.id;
  if (!state.messages.length) {
    box.innerHTML = `<div class="chat-start">
      <h2>무엇이든 물어보세요</h2>
      <p>주문표, T와 평단, VR 밴드, 시세 추세를 규칙 근거와 함께 설명해 드립니다. 위 '대상'에서 전략을 고르면 그 전략에 맞춰 답합니다.</p>
      <div class="chips">${QUICK.map(q => `<button class="chip" type="button">${esc(q)}</button>`).join("")}</div>
    </div>`;
    return;
  }
  box.innerHTML = state.messages.map(msgHtml).join("");
  box.scrollTop = box.scrollHeight;
}

async function send(text) {
  text = (text || "").trim();
  if (!text || state.busy) return;
  state.busy = true;
  const input = $("#input"), btn = $("#send");
  input.value = ""; input.style.height = "auto";
  btn.disabled = true;
  state.messages.push({ role: "user", content: text });
  drawMsgs();
  const box = $("#msgs");
  box.insertAdjacentHTML("beforeend", `<div class="msg assistant pending" id="pending">숫자를 조회하며 답을 쓰는 중… (10~30초)</div>`);
  box.scrollTop = box.scrollHeight;
  try {
    const body = { message: text };
    if (state.id) body.conversation_id = state.id;
    if (state.strategyId) body.strategy_id = state.strategyId;
    const r = await api.chat(body);
    const isNew = !state.id;
    state.id = r.conversation_id;
    state.messages.push({ role: "assistant", content: r.reply, tools_used: r.tools_used });
    drawMsgs();
    loadCtx(r.summary_used);
    setHash();
    // 목록 갱신 (새 대화면 맨 위에 생김)
    try { state.list = await api.conversations(); } catch (e) { /* 목록 실패는 무시 */ }
    drawList();
    if (isNew) toast("새 대화를 저장했습니다.");
  } catch (err) {
    $("#pending")?.remove();
    state.messages.pop();
    drawMsgs();
    input.value = text;
    toast(err.message, true);
  } finally {
    state.busy = false;
    btn.disabled = false;
    input.focus();
  }
}

async function deleteCurrent() {
  if (!state.id) return;
  const title = state.list.find(c => c.id === state.id)?.title || "이 대화";
  const ok = await openModal(`<form><h2>대화 삭제</h2><p>"${esc(title)}" 대화를 지웁니다. 되돌릴 수 없습니다.</p>
    <div class="actions"><button class="btn" type="button" data-close>취소</button><button class="btn primary" type="submit">삭제</button></div></form>`,
    async () => { await api.deleteConversation(state.id); return true; });
  if (!ok) return;
  toast("대화를 삭제했습니다.");
  state.list = state.list.filter(c => c.id !== state.id);
  state.id = null; state.messages = [];
  drawMsgs(); drawList(); setHash();
}
