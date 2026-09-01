"""상품 상세 글을 조각으로 나눌 때 사용하는 설정값을 모아 둔다."""

from app.core.config import EMBED_MAX_TOKENS

CHUNK_SIZE = 384
CHUNK_OVERLAP = 48
PREFIX_BUDGET = 32
RESPLIT_OVER = EMBED_MAX_TOKENS - PREFIX_BUDGET

HEADERS = [("##", "section")]

SEPARATORS = ["\n\n", "\n", "다. ", "요. ", ". ", " ", ""]
