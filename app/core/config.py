"""환경변수를 읽어 DB와 모델 등 프로젝트 설정을 결정한다."""

# 설정에 문제가 있을 때 경고를 남기기 위해 사용한다.
import logging

# 환경변수를 읽고 쓰기 위해 사용한다.
import os

# 파일 경로를 운영체제와 상관없이 다루기 위해 사용한다.
from pathlib import Path

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# 이 파일 위치에서 폴더를 세 번 거슬러 올라간 저장소 최상위 폴더다.
ROOT = Path(__file__).resolve().parent.parent.parent

# 원본 CSV 같은 자료가 들어 있는 폴더다.
DATA_DIR = ROOT / "data"


# .env 를 환경변수로 올린다. 이미 들어 있는 값은 덮어쓰지 않는다
def load_env(path=ROOT / ".env"):
    # 파일이 없으면 아무것도 하지 않고 끝낸다.
    if not Path(path).exists():
        # .env 없이도 기본값으로 돌아가야 하므로 오류를 내지 않는다.
        return
    # 파일을 한 줄씩 읽는다.
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        # 앞뒤 공백을 떼어 낸다.
        line = line.strip()
        # 빈 줄, 주석 줄, 등호가 없는 줄은 설정이 아니므로 건너뛴다.
        if not line or line.startswith("#") or "=" not in line:
            # 다음 줄로 넘어간다.
            continue
        # 맨 앞 등호 하나만 기준으로 이름과 값을 가른다. 값 안의 등호는 그대로 둔다.
        key, value = line.split("=", 1)
        # setdefault 는 이미 있는 환경변수를 덮어쓰지 않는다. 바깥에서 준 값이 우선한다.
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# 아래 설정값들을 읽기 전에 .env 를 먼저 올려 둔다.
load_env()


# 환경변수를 읽되 빈 값은 없는 것으로 친다
def env(name, default):
    # 없으면 빈 문자열로 받고 앞뒤 공백을 떼어 낸다.
    value = os.environ.get(name, "").strip()
    # 빈 문자열은 거짓이므로 이럴 때 기본값이 쓰인다.
    return value or default


# 참으로 읽을 낱말들이다.
TRUE_WORDS = {"1", "true", "yes", "on", "y"}

# 거짓으로 읽을 낱말들이다.
FALSE_WORDS = {"0", "false", "no", "off", "n"}


# 참거짓 환경변수. 모르는 값은 조용히 넘기지 않고 뜰 때 거절한다
def env_bool(name, default):
    # 대소문자를 가리지 않도록 소문자로 맞춘다.
    value = env(name, default).lower()
    # 참으로 읽을 낱말이면 True 다.
    if value in TRUE_WORDS:
        # 여기서 바로 답을 준다.
        return True
    # 거짓으로 읽을 낱말이면 False 다.
    if value in FALSE_WORDS:
        # 여기서 바로 답을 준다.
        return False
    # 둘 다 아니면 오타일 가능성이 높으므로 서버가 뜨기 전에 멈춘다.
    raise RuntimeError(
        # 어떤 값이 들어왔는지 먼저 알려 준다.
        f"{name} 값이 '{value}' 다. "
        # 그리고 쓸 수 있는 값을 모두 보여 준다.
        f"{sorted(TRUE_WORDS)} 또는 {sorted(FALSE_WORDS)} 중 하나여야 한다")


# 허용하는 실행 환경 이름들이다.
ENVIRONMENTS = ("dev", "test", "prod")

# 지금 어느 환경으로 도는지 읽는다. 안 주면 개발용이다.
APP_ENV = env("APP_ENV", "dev").lower()

# 모르는 이름이면 잘못된 환경으로 도는 것보다 안 뜨는 편이 낫다.
if APP_ENV not in ENVIRONMENTS:
    # 무엇이 들어왔는지 같이 알려 준다.
    raise RuntimeError(f"APP_ENV 는 {', '.join(ENVIRONMENTS)} 중 하나여야 한다 (지금 '{APP_ENV}')")

# 운영 환경인지를 곳곳에서 묻기 좋게 참거짓으로 만들어 둔다.
IS_PROD = APP_ENV == "prod"

# 상용 API 를 쓸지 내 컴퓨터의 모델을 쓸지 고르는 스위치다.
USE_API = env_bool("USE_API", "0")

# 상용 API 를 쓰는 경우다.
if USE_API:
    # OpenAI 서버 주소다.
    LLM_BASE_URL = "https://api.openai.com/v1"
    # 그 서버에 자기를 밝히는 열쇠다.
    LLM_API_KEY = env("OPENAI_API_KEY", "")
    # 대화에 쓸 모델 이름이다.
    LLM_MODEL = env("API_MODEL", "gpt-4o-mini")

    # 임베딩도 API 쪽을 쓴다는 표시다.
    EMBED_BACKEND = "api"
    # 글을 벡터로 바꿀 모델 이름이다.
    EMBED_MODEL = "text-embedding-3-small"
    # 이 모델이 만드는 벡터의 숫자 개수다.
    EMBED_DIM = 1536
    # 한 번에 넣을 수 있는 최대 토큰 수다.
    EMBED_MAX_TOKENS = 8191
# 내 컴퓨터에서 도는 모델을 쓰는 경우다.
else:
    # 컴퓨터 안에서 도는 Ollama 서버 주소다.
    LLM_BASE_URL = "http://localhost:11434/v1"
    # 로컬 서버는 열쇠를 확인하지 않지만 자리는 채워야 한다.
    LLM_API_KEY = "ollama"
    # 로컬에서 돌릴 대화 모델 이름이다.
    LLM_MODEL = "qwen-cpu"

    # 임베딩도 내 컴퓨터에서 만든다는 표시다.
    EMBED_BACKEND = "local"
    # 여러 나라 말을 다루는 작은 임베딩 모델이다.
    EMBED_MODEL = "intfloat/multilingual-e5-small"
    # 이 모델이 만드는 벡터는 숫자 384개다.
    EMBED_DIM = 384
    # 한 번에 넣을 수 있는 최대 토큰 수다.
    EMBED_MAX_TOKENS = 512

# 상용과 로컬은 벡터 차원이 달라 DB 를 섞으면 안 되므로 파일 이름을 갈라 둔다.
DEFAULT_DB_NAME = "cosmetic-api.db" if USE_API else "cosmetic.db"

# DB 파일 위치다. 환경변수로 지정하지 않으면 저장소 최상위에 둔다.
DB_PATH = env("DB_PATH", str(ROOT / DEFAULT_DB_NAME))

# 모델 호출 기록을 한 줄에 하나씩 쌓는 파일 위치다.
RUNS_PATH = env("RUNS_PATH", str(ROOT / "runs.jsonl"))

# 화면 파일이 들어 있는 폴더 위치다.
WEB_DIR = env("WEB_DIR", str(ROOT / "web"))

# 상품을 고치거나 지우는 기능을 열어 둘지 정하는 스위치다.
PRODUCT_WRITE_ENABLED = env_bool("PRODUCT_WRITE_ENABLED", "1")

# 벡터의 각 숫자를 소수점 몇 자리까지 저장할지 정한다.
EMBED_DECIMALS = 6

# 글 길이를 토큰으로 잴 때 기준으로 삼는 모델이다.
EMBED_TOKENIZER = "intfloat/multilingual-e5-small"

# 질문 한 개의 최대 글자 수다. 너무 긴 입력을 앞에서 막는다.
MAX_QUESTION_CHARS = 500

# 사용자 한 명이 하루에 쓸 수 있는 호출 횟수다.
DAILY_QUOTA = 50

# LangSmith 로 실행 과정을 내보낼지 정하는 스위치다.
LANGSMITH_TRACING = env_bool("LANGSMITH_TRACING", "false")

# 프롬프트와 답 전문까지 같이 보낼지 정하는 스위치다.
LANGSMITH_SEND_BODY = env_bool("LANGSMITH_SEND_BODY", "false")


# 운영에서만 거는 검사. 하나라도 걸리면 서버가 안 뜬다
def _check_prod():
    # 상용 API 를 쓰기로 해 놓고 열쇠가 비어 있으면 호출이 전부 실패한다.
    if USE_API and not LLM_API_KEY:
        # 뜨고 나서 실패하는 것보다 안 뜨는 편이 낫다.
        raise RuntimeError("APP_ENV=prod 이고 USE_API=1 인데 OPENAI_API_KEY 가 비어 있다")

    # 환경변수로 DB 위치를 직접 정했는지 확인한다.
    if not os.environ.get("DB_PATH", "").strip():
        # 기본 위치는 소스 폴더 안이라 배포할 때마다 사라진다.
        raise RuntimeError(
            # 무엇을 해야 하는지 먼저 말한다.
            "APP_ENV=prod 에서는 DB_PATH 를 명시해야 한다. "
            # 왜 그런지도 같이 적는다.
            "기본값은 소스 폴더 안이라 다시 배포하면 사라진다")


# 운영 환경이면 위 검사를 실제로 돌린다.
if IS_PROD:
    # 문제가 있으면 여기서 서버가 멈춘다.
    _check_prod()
# 개발 환경에서 열쇠가 비어 있는 것은 멈출 일까지는 아니다.
elif USE_API and not LLM_API_KEY:
    # 대신 알아차릴 수 있게 경고만 남긴다.
    log.warning("USE_API=1 인데 OPENAI_API_KEY 가 비어 있다. .env 를 확인할 것")

# 운영에서 본문까지 밖으로 내보내는 설정은 위험하다.
if IS_PROD and LANGSMITH_SEND_BODY:
    # 막지는 않고 무엇이 나가는지 알려 준다.
    log.warning("APP_ENV=prod 인데 LANGSMITH_SEND_BODY 가 켜져 있다. "
                # 무엇이 밖으로 나가는지 구체적으로 적는다.
                "프롬프트와 답 전문이 밖으로 나간다")

# DB 파일이 아직 없을 수도 있다.
if not Path(DB_PATH).exists():
    # 파이프라인을 안 돌린 상태면 정상이므로 경고만 남긴다.
    log.warning("DB 가 아직 없다: %s (pipeline schema 전이면 정상)", DB_PATH)
