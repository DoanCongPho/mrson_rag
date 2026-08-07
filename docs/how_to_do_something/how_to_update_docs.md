# How to sync tài liệu từ Google Drive

Quy trình khi có tài liệu mới/sửa trên Google Drive và cần đưa vào RAG.

## 0. Yêu cầu 1 lần (setup ban đầu)

- File `service_account.json` ở thư mục gốc project (đã gitignore, không commit).
  - Tạo ở Google Cloud Console → APIs & Services → Credentials → Create Credentials → Service account → tab Keys → Add Key → JSON.
  - Nếu bị chặn bởi org policy `iam.disableServiceAccountKeyCreation`: tạo project bằng 1 tài khoản Gmail cá nhân không thuộc Workspace/organization nào (tài khoản cá nhân không bị policy này).
- Folder Drive chứa tài liệu (id đang set ở `root_folder_id` trong `config.py`) phải share **"Anyone with the link" (Viewer)** — không cần share riêng cho email service account, vì service account cũng nằm trong "anyone". Lưu ý: phải share ở **chính folder gốc**, không chỉ từng file bên trong, vì `update_docs.py` cần quyền đọc folder cha để liệt kê file con.

## 1. Sync danh sách file Drive vào DB

```bash
uv run python -m update_docs.update_docs
```

Việc này gọi Drive API, liệt kê đệ quy toàn bộ file trong `root_folder_id`, rồi upsert (`name`, `url`) vào bảng `documents` trong Postgres. Chạy lại an toàn nhiều lần — file cũ được update, file mới được thêm.

## 2. Đảm bảo file local khớp tên với Drive

`ingestion/run_ingest.py` match `Chunk.doc_url` bằng cách so tên file local (trong `word_files/heading_already_files/`) với `Document.name` đã sync ở bước 1 — **so khớp tuyệt đối theo tên file, không theo nội dung**.

- Tên file local phải **giống hệt** tên file trên Drive (kể cả khoảng trắng, dấu chấm, số thứ tự).
- Không cần lo Unicode NFC/NFD (macOS lưu tên file ở dạng NFD, Drive trả NFC) — code đã tự normalize cả 2 bên về NFC trước khi so sánh.
- Nếu không khớp, ingest vẫn chạy bình thường nhưng `doc_url` của chunk đó sẽ là `NULL` (không bị lỗi/crash), kèm warning:
  ```
  WARNING: no Document record for <tên file> (run update_docs sync first, or filename differs from Drive), doc_url will be empty
  ```

## 3. Ingest lại

```bash
uv run python -m ingestion.run_ingest
```

Chunk cũ của file đó bị đánh `is_active=False` (soft-delete), chunk mới được tạo kèm `doc_url` lấy từ bảng `documents`.

## Thứ tự chuẩn khi có thay đổi trên Drive

1. Sửa/thêm file trên Google Drive.
2. Tải file mới về, đặt đúng tên (khớp Drive) vào `word_files/heading_already_files/`.
3. `uv run python -m update_docs.update_docs` (sync bảng `documents`).
4. `uv run python -m ingestion.run_ingest` (tạo chunk mới, gán `doc_url`).

Bước 3 nên chạy trước bước 4 nếu có file mới hoàn toàn (chưa từng có trong bảng `documents`), để `doc_url` được gán ngay lần ingest đầu thay vì phải ingest lại lần 2.
