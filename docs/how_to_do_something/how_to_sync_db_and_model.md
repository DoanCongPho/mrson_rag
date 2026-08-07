# How to sync DB and model (Alembic workflow)

Quy trình chuẩn khi đổi schema (sửa `db/models.py`) và cần đưa lên DB thật.

## 1. Sửa model trước

Thêm/sửa/xoá column, table, relationship... trong `db/models.py`.

## 2. Sinh migration

Có 2 cách:

**Autogenerate (ưu tiên dùng khi có thể):**

```bash
uv run alembic revision --autogenerate -m "mô tả ngắn gọn thay đổi"
```

Alembic sẽ **so sánh** `db/models.py` hiện tại với schema thực tế trong DB (kết nối qua `DATABASE_URL`), rồi tự sinh code migration cho phần khác biệt.

**Manual (khi autogenerate không detect được hoặc detect sai):**

```bash
uv run alembic revision -m "mô tả ngắn gọn thay đổi"
```

Rồi tự viết `upgrade()`/`downgrade()` tay.

> ⚠️ Autogenerate **không hoàn hảo** — nó không tự phát hiện được: đổi tên column (hiểu nhầm thành drop + add), thay đổi cần migrate dữ liệu (data migration), một số kiểu đổi index/constraint phức tạp. Nên **luôn luôn** làm bước 3.

## 3. Review lại file migration vừa sinh ra

Mở file trong `alembic/versions/`, đọc kỹ `upgrade()`/`downgrade()` xem đúng ý chưa trước khi apply — đây là bước hay bị bỏ qua nhưng quan trọng nhất, tránh mất data ngoài ý muốn (ví dụ autogenerate drop nhầm cột do tưởng là rename).

## 4. Apply migration lên DB

```bash
uv run alembic upgrade head
```

Lệnh này chạy tất cả migration chưa được apply, theo đúng thứ tự (`down_revision` chain).

## 5. Verify

Check lại bằng psql/DBeaver, hoặc chạy thử app xem query có lỗi không.

## 6. Commit cùng lúc

Commit `db/models.py` + file migration mới trong **cùng 1 commit** — 2 thứ này phải đi cùng nhau, tách rời ra dễ gây lệch schema giữa các máy/môi trường.

---

## Rollback nếu cần

```bash
uv run alembic downgrade -1   # lùi lại 1 bước gần nhất
```

## Lưu ý riêng cho project này

Service `backend` trong `docker-compose.yml` đã tự chạy `alembic upgrade head` mỗi lần container start:

```yaml
command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

Nên khi deploy qua Docker, bước 4 tự động xảy ra, chỉ cần đảm bảo migration file đã commit vào code trước khi build/deploy. Còn chạy local (không qua Docker) thì phải tự chạy `uv run alembic upgrade head` tay.
