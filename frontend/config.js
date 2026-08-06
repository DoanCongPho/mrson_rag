// Tự nhận diện môi trường: chạy local thì gọi thẳng localhost:8000,
// còn lại (domain thật, sau reverse proxy) thì gọi qua subpath /api cùng domain.
// Nếu domain thật của bạn khác "yourdomain.com" trong Caddyfile, sửa luôn dòng dưới cho khớp.
const API_BASE_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : `${window.location.origin}/api`;
