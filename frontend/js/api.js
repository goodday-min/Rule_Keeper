// 백엔드 호출. 주소와 API 키는 config.js 또는 '연결 설정'(브라우저 localStorage)에서 가져온다.

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key) || "";
    if (value) localStorage.setItem(key, value); else localStorage.removeItem(key);
  } catch (e) { /* 저장소를 못 쓰는 브라우저 */ }
  return value;
}

export const conn = {
  get base() { return (store("rk_api_base") || window.RK_CONFIG?.API_BASE || "").replace(/\/+$/, ""); },
  set base(v) { store("rk_api_base", (v || "").trim()); },
  get key() { return store("rk_api_key"); },
  set key(v) { store("rk_api_key", (v || "").trim()); },
};

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function detailText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {          // FastAPI 검증 오류 목록
    return detail.map(d => {
      const where = (d.loc || []).filter(x => x !== "body").join(".");
      return where ? `${where}: ${d.msg}` : d.msg;
    }).join(" / ");
  }
  return JSON.stringify(detail);
}

async function request(method, path, body) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (conn.key) headers["X-API-Key"] = conn.key;
  let res;
  try {
    res = await fetch(conn.base + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (e) {
    throw new ApiError(0, "서버에 연결하지 못했습니다. 서버가 켜져 있는지, 연결 설정의 주소가 맞는지 확인하세요.");
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
  if (!res.ok) {
    let msg = detailText(data && data.detail) || `요청이 실패했습니다 (${res.status})`;
    if (res.status === 401) msg = "API 키가 필요합니다. 왼쪽 아래 '연결 설정'에서 키를 입력하세요.";
    throw new ApiError(res.status, msg);
  }
  return data;
}

const qs = params => {
  const p = Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return p.length ? "?" + new URLSearchParams(p).toString() : "";
};

export const api = {
  health: () => request("GET", "/health"),
  // 전략·주문표
  strategies: (includeEnded = false) => request("GET", "/api/strategies" + qs({ include_ended: includeEnded })),
  createStrategy: body => request("POST", "/api/strategies", body),
  updateStrategy: (id, body) => request("PUT", `/api/strategies/${id}`, body),
  endStrategy: id => request("DELETE", `/api/strategies/${id}`),
  status: id => request("GET", `/api/strategies/${id}/status`),
  ordersToday: () => request("GET", "/api/orders/today"),
  nextOrders: id => request("GET", `/api/strategies/${id}/orders/next`),
  confirm: (id, date, overrides) => request("POST", `/api/strategies/${id}/orders/${date}/confirm`, { overrides }),
  vrSnapshots: id => request("GET", `/api/strategies/${id}/vr-snapshots`),
  vrRebalance: (id, body) => request("POST", `/api/strategies/${id}/vr/rebalance`, body),
  backtest: (id, startDate) => request("POST", `/api/strategies/${id}/backtest`, { start_date: startDate }),
  // 시세
  prices: (ticker, dateFrom) => request("GET", "/api/prices" + qs({ ticker, date_from: dateFrom })),
  syncPrices: () => request("POST", "/api/prices/sync"),
  // 체결 기록
  data: params => request("GET", "/api/data" + qs(params)),
  addData: body => request("POST", "/api/data", body),
  updateData: (id, body) => request("PUT", `/api/data/${id}`, body),
  deleteData: id => request("DELETE", `/api/data/${id}`),
  exportUrl: params => conn.base + "/api/data/export" + qs(params),
  summary: strategyId => request("GET", "/api/data/summary" + qs({ strategy_id: strategyId })),
  statistics: () => request("GET", "/api/data/statistics"),
  // 대화
  conversations: () => request("GET", "/api/conversations"),
  conversation: id => request("GET", `/api/conversations/${id}`),
  deleteConversation: id => request("DELETE", `/api/conversations/${id}`),
  chat: body => request("POST", "/api/chat", body),
};
