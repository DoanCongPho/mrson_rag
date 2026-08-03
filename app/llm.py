from db.models import Chunk
from app.retrieval import retrieve
from openai import OpenAI
from config import settings

client = OpenAI(api_key=settings.openai_api_key)


def build_prompt(chunks: list[Chunk]) -> str:
    context = "\n\n".join(
        f"[Nguồn {i+1}] {chunk.source_file} > {chunk.section_title}\n{chunk.text}"
        for i, chunk in enumerate(chunks)
    )

    system_prompt = f"""Bạn là trợ lý IELTS Speaking. CHỈ dùng thông tin trong CONTEXT dưới đây để trả lời.
Nếu CONTEXT không đủ thông tin, nói rõ là không có thông tin, đừng bịa.

QUY TẮC TRÌNH BÀY:
- Khi cho ví dụ nên ghi song ngữ
QUY TẮC TRÍCH NGUỒN:
- Sau mỗi ý lấy từ tài liệu, ghi số nguồn dạng [1], [2].
- Một ý dùng nhiều nguồn thì ghi [1][3].
- Cuối câu trả lời, thêm mục "Nguồn tham khảo:" liệt kê các nguồn đã dùng theo dạng: [N] tên file > tên mục.
- KHÔNG liệt kê nguồn không dùng đến.


[Context]
{context}
"""
    return system_prompt


def single_turn():
    print("Hỏi bất cứ gì về bài học của thầy Sơn")
    while True:
        user_query = input("Ask ('end' để thoát): ").strip()
        if user_query.lower() == "end":
            break
        if not user_query:
            continue

        results = retrieve(user_query)
        chunks = [chunk for chunk, _ in results]
        prompt = build_prompt(chunks=chunks)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt},
                      {"role": "user", "content": user_query}],
            temperature=0.8,
        )
        answer = response.choices[0].message.content
        print(f"\nBot: {answer}\n")


if __name__ == "__main__":
    single_turn()