// Vercel 빌드 때 실행: 환경 변수 API_BASE_URL 값으로 config.js를 새로 만든다.
// (바닐라 HTML은 브라우저에서 환경 변수를 읽을 수 없으므로, 배포 직전에 파일로 적어 둔다.)
// 환경 변수가 없으면 저장소의 config.js를 그대로 쓴다 (로컬은 127.0.0.1:8000, 배포는 Render 주소로 자동 선택).
const fs = require("fs");
const url = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (url) {
  fs.writeFileSync("config.js",
    "// Vercel 빌드 때 환경 변수 API_BASE_URL로 만든 파일입니다.\n" +
    `window.RK_CONFIG = { API_BASE: ${JSON.stringify(url)} };\n`);
  console.log(`config.js <- API_BASE_URL=${url}`);
} else {
  console.log("API_BASE_URL 환경 변수가 없어 config.js를 그대로 사용합니다.");
}
