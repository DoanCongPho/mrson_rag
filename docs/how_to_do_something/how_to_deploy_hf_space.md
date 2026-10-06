# How to deploy free: Hugging Face Spaces + Neon

Toàn bộ app (API + frontend + reranker) chạy trong **1 container** trên Hugging Face Space (Docker), database ở **Neon** (Postgres có pgvector). Không cần thẻ tín dụng.

- App phục vụ frontend ở `/` và API ở `/api` trên cùng 1 domain `https://<owner>-<space>.hf.space`, nên cookie đăng nhập hoạt động mà không cần CORS (`app/space.py`).
- Model reranker được tải sẵn lúc build image (`deploy/hf-space/Dockerfile`), Space thức dậy không phải tải lại ~2 GB.
- Space free **tự ngủ** khi không ai dùng một thời gian; lần mở lại chờ ~1–2 phút (build sẵn, chỉ khởi động + load model).
- Chi phí duy nhất: **OpenAI** (giới hạn `DAILY_MESSAGE_LIMIT=50` câu/người/ngày; nên đặt usage limit trong billing OpenAI).

## 0. Yêu cầu 1 lần

- Tài khoản **Hugging Face** + token quyền *Write*: https://huggingface.co/settings/tokens, rồi `uv run hf auth login`.
- Tài khoản **Neon**: https://neon.tech (đăng nhập bằng GitHub được).
- Google OAuth client đã có (xem phần đăng nhập) — sẽ thêm origin của Space ở bước 4.
- Postgres local đang chạy (`docker compose up -d db`) và đã ở migration mới nhất (`uv run alembic upgrade head`).

## 1. Tạo database Neon và copy dữ liệu

1. Neon → **New project**, region **AWS Asia Pacific (Singapore)**, Postgres 16 hoặc 17.
2. **Connect** → copy connection string dạng
   `postgresql://<user>:<pass>@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
3. Copy toàn bộ dữ liệu local (chunks, documents, users, chats) sang Neon. Script chỉ chạy khi database Neon **còn trống**:

```bash
export NEON_DATABASE_URL='postgresql://...neon.tech/neondb?sslmode=require'
bash scripts/copy_db_to_neon.sh
```

Script tự tạo extension `vector`, cuối cùng in số dòng (active chunks, documents, users...) để đối chiếu.

## 2. Đặt Google Client ID cho frontend

`frontend/config.js` phải có `GOOGLE_CLIENT_ID` (không phải bí mật). Nên commit giá trị này; script deploy dùng file trong working tree nên dù chưa commit vẫn upload được (sẽ in cảnh báo).

## 3. Deploy lên Space

```bash
# lần đầu: tạo Space, upload code, set secrets/variables
uv run python scripts/deploy_hf_space.py <hf-username>/learn-with-heart --set-config

# các lần sau (chỉ cập nhật code)
uv run python scripts/deploy_hf_space.py <hf-username>/learn-with-heart
```

- Upload các file git-tracked cần để chạy (`app/`, `db/`, `alembic/`, `frontend/`, `pyproject.toml`, `uv.lock`, ...) **theo working tree hiện tại**, kèm `deploy/hf-space/{Dockerfile,README.md,.dockerignore}` ở gốc Space. Không upload `.env`, `tests/`, `eval/`, `word_files/`.
- `--set-config` đặt:
  - **Secrets**: `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID` (đọc từ `.env`), `DATABASE_URL` (từ biến môi trường `NEON_DATABASE_URL`, **không bao giờ** lấy DB local), `SESSION_SECRET` (tạo mới cho production).
  - **Variables**: `COOKIE_SECURE=true`, `PHOENIX_ENABLED=false`, `RERANKER_ENABLED=true`, `RERANK_CANDIDATE_K=10`, `DAILY_MESSAGE_LIMIT=50`.
  - Chạy lại `--set-config` sẽ tạo `SESSION_SECRET` mới → mọi người phải đăng nhập lại.
- Xem build log ở `https://huggingface.co/spaces/<hf-username>/learn-with-heart?logs=build`. Build lần đầu ~10–15 phút (torch + model). Container khởi động sẽ tự chạy `alembic upgrade head`.

## 4. Cho phép đăng nhập Google trên domain của Space

Google Cloud Console → **APIs & Services → Credentials** → OAuth client → **Authorized JavaScript origins** → thêm:

```
https://<hf-username>-learn-with-heart.hf.space
```

(script in sẵn URL này ở cuối). Trước khi chia sẻ cho cả lớp: **OAuth consent screen → Publish app**.

## 5. Chia sẻ đúng link

Gửi link **trực tiếp** `https://<hf-username>-learn-with-heart.hf.space`, **không** gửi link `huggingface.co/spaces/...`: trang đó nhúng app trong iframe, trình duyệt chặn cookie trong iframe nên đăng nhập sẽ không giữ được.

## Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách sửa |
|---|---|
| Build log báo lỗi ở bước tải model | Mạng của Space lúc build; bấm **Factory rebuild** trong Settings của Space. |
| App báo lỗi kết nối DB khi khởi động | `DATABASE_URL` sai hoặc thiếu `?sslmode=require`; kiểm tra secret trên Space. |
| Đăng nhập Google: "origin not allowed" | Chưa thêm domain `*.hf.space` ở bước 4 (đợi vài phút sau khi lưu). |
| Đăng nhập xong vẫn bị đẩy ra màn hình login | Đang mở qua `huggingface.co/spaces/...` (iframe) — dùng link trực tiếp ở bước 5. |
| Trả lời chậm | 2 vCPU dùng chung; giảm `RERANK_CANDIDATE_K` hoặc đặt `RERANKER_ENABLED=false` trong Variables của Space. |
