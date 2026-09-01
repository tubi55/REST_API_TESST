"""긴 글을 제목과 토큰 수를 기준으로 작은 조각으로 나눈다."""

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from transformers import AutoTokenizer

from app.core.config import EMBED_TOKENIZER
from pipeline.prep.options import CHUNK_OVERLAP, CHUNK_SIZE, HEADERS, RESPLIT_OVER, SEPARATORS

_tokenizer = None


# 토큰을 세는 자. 무거우니 한 번만 올리고 계속 쓴다
def get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(EMBED_TOKENIZER)
    return _tokenizer


# 토큰 수. 특수토큰 2개가 포함된, 실제로 모델에 들어가는 수다
def count_tokens(text):
    return len(get_tokenizer().encode(text))


# 조각 앞에 [상품명 > 섹션] 을 붙인다. 임베딩은 글자만 보므로 출처를 글자로 적는다
def with_context(product_name, section, body):
    return f"[{product_name} > {section}] {body}"


# 1단. 글자 수가 아니라 '## 주의사항' 이라는 사람의 경계로 자른다
def split_sections(details):
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS)

    sections = []
    for product_id, product_name, detail in details:
        for doc in splitter.split_text(detail):
            text = doc.page_content.strip()
            if not text:
                continue
            sections.append({
                "product_id": product_id,
                "product_name": product_name,
                "section": doc.metadata.get("section", "(머리말)"),
                "text": text,
                "n_tokens": count_tokens(text),
            })
    return sections


# 2단. 상한을 넘는 섹션만 다시 자르고 접두어를 붙인다. (조각 목록, 다시 자른 수)
def split_chunks(sections):
    resplitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        get_tokenizer(), chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS, keep_separator="end")

    chunks, n_resplit = [], 0
    for section in sections:
        if section["n_tokens"] > RESPLIT_OVER:
            n_resplit += 1
            parts = resplitter.split_text(section["text"])
        else:
            parts = [section["text"]]

        for chunk_index, body in enumerate(parts):
            text = with_context(section["product_name"], section["section"], body)
            chunks.append({
                "product_id": section["product_id"],
                "product_name": section["product_name"],
                "section": section["section"],
                "chunk_index": chunk_index,
                "body": body,
                "text": text,
                "n_tokens": count_tokens(text),
            })
    return chunks, n_resplit


# 1단과 2단을 순서대로. 부르는 쪽은 이 하나만 알면 된다
def split_details(details):
    sections = split_sections(details)
    chunks, n_resplit = split_chunks(sections)
    return sections, chunks, n_resplit
