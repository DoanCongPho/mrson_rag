# Quy ước đánh Heading cho file Word (word_files)

Mục đích: đánh dấu lại các file `.docx` bằng Style Heading thật của Word, để chương trình đọc được cấu trúc bài học một cách chính xác (thay vì phải đoán qua màu/bold).

## Cách áp Heading trong Word
1. Bôi đen (chọn) dòng cần đánh dấu.
2. Vào tab **Home** → chọn **Heading 1** hoặc **Heading 2** trong khung Styles (thanh ribbon phía trên).
3. Không cần lo font/màu bị đổi sau khi áp — chương trình chỉ đọc **tên style**, không quan tâm hiển thị. Nếu muốn giữ màu/bold như cũ, bôi đen lại chữ và chỉnh font/màu thủ công sau khi áp Heading, không sao cả.

## Quy tắc 1 — Mục lớn → Heading 1
Chỉ dùng **một cấp Heading duy nhất: Heading 1**. Áp dụng cho các dòng đánh số thứ tự mục lớn, đứng riêng một đoạn, ví dụ:
- "1. MỞ BÀI"
- "2. VALUE LINE là gì?"
- "PART 2 – 3 STORY EXPANSION TRICKS"

→ Chọn dòng này, áp **Heading 1**. Không dùng Heading 2 hay các cấp khác.

## Quy tắc 2 — KHÔNG sửa các phần này
Giữ nguyên, không áp Heading, không sửa gì — kể cả khi chúng có bold hoặc màu chữ:
- Các nhãn/tiểu mục nằm bên trong một mục lớn, ví dụ "TRICK 1: ZOOM IN", "Mức 1: Safe VALUE LINE", "Opening", "Ví dụ:". Những dòng này chỉ là chữ đậm/có màu trong đoạn, KHÔNG phải heading.
- Các ô có màu nền (cam, xanh lá...) chứa ví dụ đúng/sai.
- Các câu được highlight màu vàng.
- Bullet list, đoạn văn thường.
- 1-2 dòng tiêu đề/tên bài ở đầu file (ví dụ "IELTS SPEAKING PART 2", tên bài học) — đây là tiêu đề của cả file, không phải một mục, không cần áp Heading.

Những phần này chương trình đã có cách đọc riêng (qua màu/tô nền/highlight), sửa vào sẽ không có lợi và tốn thời gian của bạn. Nếu phân vân, cứ để nguyên — chỉ áp Heading 1 cho đúng các mục lớn đánh số ở Quy tắc 1.

## Cách tự kiểm tra sau khi sửa
Word: vào tab **View** → tick **Navigation Pane** (hoặc **Sidebar** trên Mac). Nếu áp Heading đúng, các mục lớn/nhỏ sẽ hiện ra thành danh sách outline ở khung bên trái. Nếu không thấy dòng nào xuất hiện ở đó, nghĩa là Heading chưa được áp đúng.

## Sau khi sửa xong
Lưu file với **cùng tên file gốc**, không đổi định dạng (giữ `.docx`), không đổi vị trí nội dung khác.
