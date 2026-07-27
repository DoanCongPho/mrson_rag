# Quy ước đánh Heading cho file Word (word_files)

Mục đích: đánh dấu lại các file `.docx` bằng Style Heading thật của Word, để chương trình đọc được cấu trúc bài học một cách chính xác (thay vì phải đoán qua màu/bold).

## Cách áp Heading trong Word
1. Bôi đen (chọn) dòng cần đánh dấu.
2. Vào tab **Home** → chọn **Heading 1** hoặc **Heading 2** trong khung Styles (thanh ribbon phía trên).
3. Không cần lo font/màu bị đổi sau khi áp — chương trình chỉ đọc **tên style**, không quan tâm hiển thị. Nếu muốn giữ màu/bold như cũ, bôi đen lại chữ và chỉnh font/màu thủ công sau khi áp Heading, không sao cả.

## Quy tắc 1 — Mục lớn → Heading 1
Áp dụng cho các dòng đánh số thứ tự mục lớn, đứng riêng một đoạn, ví dụ:
- "1. MỞ BÀI"
- "2. VALUE LINE là gì?"
- "PART 2 – 3 STORY EXPANSION TRICKS"

→ Chọn dòng này, áp **Heading 1**.

## Quy tắc 2 — Mục con trong 1 mục lớn → Heading 2
Áp dụng cho các dòng là tiểu mục nằm bên trong một mục lớn, ví dụ:
- "TRICK 1: ZOOM IN"
- "Mức 1: Safe VALUE LINE"
- "TƯ DUY CỐT LÕI" (nếu nó thuộc trong 1 mục lớn phía trên, không phải mục đứng riêng)

→ Chọn dòng này, áp **Heading 2**.

Nếu không chắc một dòng là Heading 1 hay Heading 2: nhìn xem nó có "thuộc về" một mục lớn phía trên nó không. Có → Heading 2. Đứng độc lập, ngang hàng với các mục số 1/2/3 khác → Heading 1.

## Quy tắc 3 — KHÔNG sửa các phần này
Giữ nguyên, không cần áp Heading, không cần sửa gì:
- Các ô có màu nền (cam, xanh lá...) chứa ví dụ đúng/sai.
- Các câu được highlight màu vàng.
- Bullet list, đoạn văn thường.

Những phần này chương trình đã có cách đọc riêng, sửa vào sẽ không có lợi và tốn thời gian của bạn.

## Cách tự kiểm tra sau khi sửa
Word: vào tab **View** → tick **Navigation Pane** (hoặc **Sidebar** trên Mac). Nếu áp Heading đúng, các mục lớn/nhỏ sẽ hiện ra thành danh sách outline ở khung bên trái. Nếu không thấy dòng nào xuất hiện ở đó, nghĩa là Heading chưa được áp đúng.

## Sau khi sửa xong
Lưu file với **cùng tên file gốc**, không đổi định dạng (giữ `.docx`), không đổi vị trí nội dung khác.
