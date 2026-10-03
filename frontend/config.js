// 백엔드 주소. 내 PC(127.0.0.1, localhost)에서 열면 로컬 서버를, 그 밖(Vercel 등)에서 열면 Render 서버를 쓴다.
// (화면 왼쪽 아래 '연결 설정'에서 브라우저별로 바꿀 수도 있습니다.)
// API 키는 여기에 적지 않습니다. '연결 설정'에서 입력하면 그 브라우저에만 저장됩니다.
(function () {
  const local = ["127.0.0.1", "localhost", ""].includes(location.hostname);
  window.RK_CONFIG = {
    API_BASE: local ? "http://127.0.0.1:8000" : "https://rule-keeper.onrender.com",
  };
})();
