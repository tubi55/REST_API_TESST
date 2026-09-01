# 작업 규칙

화장품 회사 관리자용 AI 대시보드.

```
Python (FastAPI)   AI 서버. 검색 · 추천 · 질의응답 · 임베딩 파이프라인
SQLite             DB. 정형 데이터와 벡터를 같이 담는다
web/index.html     화면 한 장. 이 서버가 같이 준다
```

나중에 갈 곳은 두 갈래다. 어느 쪽인지는 아직 안 골랐다.

```
단독형   FastAPI + Postgres/Supabase          FastAPI 가 업무 데이터를 소유한다
분리형   Spring Boot + MySQL 이 업무 데이터    FastAPI 는 AI 만 맡는다
```

지금 고르지 않는다. 고르지 않은 채로 진도가 나가게 경계만 잡아 둔다.
자세한 것은 `ARCHITECTURE.md` 를 본다.

## 유일한 판단 기준

실무자가 봤을 때 최적화돼 있는가. 중복이 없고, 재사용 가능하고, 갈아끼우기 쉬운가.

지금 규모에 안 맞는 구조를 미리 넣지 않는다. 필요해지는 조건을 적어 두고 기다린다.

## 문서

| 파일 | 무엇 |
| --- | --- |
| `ARCHITECTURE.md` | 현재 설계. 작업 전 읽는다 |
| `docs/measurements.md` | 실측값. 잰 날짜 · 표본 · 조건과 함께 |
| `docs/deck/` | 이 저장소의 구조를 설명하는 슬라이드 |

---

## 1. 주석

함수 위에 `#` 한 줄로 무엇을 하는 함수인지 적는다.

```python
# 고객 벡터로 상품 후보를 뽑고 안전 필터에 걸린 것을 뺀다
def candidates(customer_id, n=N_CANDIDATES, use_filter=True):
```

docstring 은 파일 맨 위에 한 줄만 쓴다. 그 파일이 무엇을 하는지다.

```python
"""문장에서 전화번호와 이메일 같은 개인정보를 가린다."""
```

함수와 클래스에는 docstring 을 안 쓴다. 선언 위의 `#` 한 줄이 그 자리다.
포트(Protocol)와 Pydantic 모델도 같다. 여러 줄짜리 설명문은 코드가 아니라
`ARCHITECTURE.md` 에 적는다.

### 쓰지 않는 것

- 이모지와 특수 기호. `🔴` `⚠️` `★` `―` `—` 전부 안 쓴다
- 주석 안의 마크다운 강조 (`**...**`)
- 큰 구분선 (`# ====...`, `# ----...`). 필요하면 빈 줄로 나눈다
- 바깥 문서의 위치 참조 (`계획서 3절`). 실측값이 붙어 있으면 라벨만 떼고 숫자는 남긴다

```python
# 나쁜 예
# 🔴 계획서 4절에서 잰 값 ― 이력 카테고리 필터로 천장이 @5 13.0% 다

# 좋은 예
# 이력 카테고리 필터의 천장은 hit@5 13.0% (docs/measurements.md)
```

## 2. print

| 대상 | 규칙 |
| --- | --- |
| `app/` 전체 | print 금지. 필요하면 `logging` |
| `app/**` 의 `if __name__ == "__main__"` 자가진단 블록 | 두지 않는다. 검증은 `tests/` 로 |
| `pipeline/*.py` (prep 제외) | 스크립트다. 출력이 곧 제품이므로 print 를 쓴다 |
| `pipeline/prep/*.py` | 라이브러리다. print 금지. 값을 돌려주고 스크립트가 찍는다 |
| `eval/` | CLI 도구다. print 를 쓴다 |

구동에 필요 없는 검증 코드는 남기지 않는다. 한 번 확인하고 지운다.
계속 지켜야 하는 검증이면 테스트로 옮긴다.

## 3. 타입

전부 붙이지 않는다. 세 자리에만 붙인다.

| 우선순위 | 대상 | 이유 |
| --- | --- | --- |
| 1 | FastAPI 의 `response_model` (전 엔드포인트) | OpenAPI 스키마에서 TS 타입을 자동 생성한다 |
| 2 | 포트(Protocol) | 계약이라 타입이 곧 문서다 |
| 3 | `app/domain/` 순수 함수 | 설계 결함이 시그니처에 드러난다 |

`features/` 조립 코드와 `pipeline/` 스크립트에는 안 붙여도 된다.

Pydantic 은 v2 문법만 쓴다. `@field_validator` · `model_dump()` · `model_validate`.

새로 만드는 API 응답은 camelCase 로 낸다 (`alias_generator=to_camel`).
나중에 앞단이 Spring 으로 바뀌어도 화면이 안 바뀌게 하려는 것이다.

## 4. 지어낸 숫자를 쓰지 않는다

측정값을 코드 주석이나 문서에 적을 때는 실제로 돌려서 나온 값만 쓴다.
못 쟀으면 안 쟀다고 적는다.

실측값은 `docs/measurements.md` 에 잰 날짜 · 표본 · 조건과 함께 모으고,
코드에서는 그 파일을 가리킨다.

## 5. 구조

### 계층

```
app/domain/       순수. DB · 네트워크 · LLM 을 모른다. 테스트가 여기 붙는다
app/api/          HTTP. 라우터 · 의존성 · 오류 변환. main.py 는 조립만 한다
app/features/     조립. domain 에 저장소를 붙인다
app/repositories/ 정형 데이터의 SQL. 이름 붙은 질의만 낸다
app/adapters/     바깥. LLM · 벡터 저장소
app/core/         아래층. 설정 · DB 게이트웨이 · 임베딩기 · 인증 · 관측
```

`app/` 이 `pipeline/` 을 import 하지 않는다. 배포할 때 `pipeline/` 은 안 따라간다.
둘이 같이 쓰는 순수 함수는 `app/domain/` 에 둔다.

### 저장소는 포트 뒤에 있다

벡터 저장소는 `app/domain/ports.py` 의 `VectorStore` Protocol 로만 접근한다.
읽기(`search`)와 쓰기(`recreate` · `upsert`) 둘 다 포트에 있다.
같은 파일에 `ProductRepository` 도 있다. 경계는 이 둘이다.

포트는 `domain/` 에 둔다. 구현이 포트를 향하지 포트가 구현 옆에 있으면 안 된다.

`app/` 과 `pipeline/` 어디에도 `sqlite` 나 `pgvector` 라는 글자가 없어야 한다.
저장소 구현 파일만 예외다.

포트에 쿼리 빌더를 노출하지 않는다. 이름 붙은 질의만 노출한다.

정형 데이터의 SQL 은 `app/repositories/` 에만 있다. `app/features/` 와 `app/api/`
에는 SQL 도 표 이름도 없다. 여기도 이름 붙은 질의만 낸다. WHERE 절이나 SQL 조각을
인자로 받는 함수를 만들지 않는다.

### 파일 하나가 한 가지 일만 한다

순수 변환과 I/O 와 조립을 파일로 가른다.

## 6. 파이썬 환경

`.venv` 를 쓴다. 전역 파이썬에 설치하지 않는다.

```
python -m venv .venv
.venv/Scripts/activate          윈도. 그 외는 source .venv/bin/activate
pip install -e ".[dev,trace,local]"
```

`-e` 로 넣으므로 `app` 은 어디서든 import 된다. `pipeline` 과 `eval` 은 배포에
안 따라가서 설치되지 않는다. 그래서 저장소 뿌리에서 `-m` 으로 부른다 (7번).

### 엑스트라

| 이름 | 무엇 | 언제 |
| --- | --- | --- |
| (없음) | 서버가 도는 데 필요한 것 | 늘 |
| `dev` | pytest · httpx · ruff | 늘 |
| `local` | sentence-transformers · torch. 449MB 가중치를 받는다 | `USE_API=0` 일 때 |
| `trace` | langsmith | 관측을 켤 때 |
| `eval` | ragas. pandas 와 datasets 를 끌고 와서 무겁다 | 답변 품질을 잴 때 |

`eval` 은 따로 깐다. 105개쯤 되고 `USE_API=1` 로만 쓸모가 있다.

```
pip install -e ".[eval]"
```

### 왜 전역을 안 쓰나

전역을 쓰던 때 이 문서에 이런 줄이 있었다.

```
langchain-community 는 0.3.31 로 고정한다. 0.4.2 에서 import ragas 가 깨진다
```

`ragas` 도 `langchain-community` 도 이 프로젝트가 안 쓰던 때였다. 다른 작업 때문에
생긴 기계 차원의 제약이 프로젝트 문서 안으로 들어와 앉아 있었다. 반대 방향이 더
위험하다. 다른 작업 때문에 `langchain-core` 를 올리면 이 프로젝트가 조용히 깨진다.

그 고장 자체는 진짜다. 지금은 `eval` 엑스트라 안에 핀으로 적혀 있고, `.venv` 안이라
다른 작업에 안 번진다. 제약이 있어야 할 자리로 옮겨 간 것이다.

### 잠금

`requirements.lock.txt` 는 이제 **설치용**이다. 전역이 아니라 `.venv` 안에 넣으므로
다른 작업의 패키지가 끌려 내려갈 일이 없다.

```
pip install -r requirements.lock.txt     실제로 돌려 본 그 조합 그대로
pip freeze > requirements.lock.txt       버전을 올린 뒤 다시 적는다
```

`pyproject.toml` 은 "무엇이 필요한가"(범위)를, 잠금 파일은 "무엇으로 돌려 봤나"
(정확한 버전)를 적는다. 둘 다 있어야 한다.

### 설치

패키지를 함부로 설치하지 않는다. `.venv` 안이라 전역보다 안전해졌지만, 무엇이
왜 필요한지는 여전히 말하고 넣는다. `pyproject.toml` 에 안 적힌 것을 깔지 않는다.

`pandas` 는 우리 코드에서 쓰지 않는다. 표준 `csv` 모듈로 처리한다.
(`eval` 엑스트라가 ragas 때문에 끌고 오는 것은 우리 코드가 쓰는 게 아니다.)

## 7. 실행

```
python -m pipeline schema        CSV -> DB
python -m pipeline chunk         상세 청킹
python -m pipeline embed         임베딩 (--full 로 전량)
python -m pipeline verify        점검
python -m pipeline               단계 목록

uvicorn app.main:app --reload    AI 서버 + 화면
pytest -q                        시험 (tests/ · tests/contract/ · tests/api/)
```

**저장소 뿌리에서 `-m` 으로 부른다.** 파일을 직접 실행하지 않는다.
`-m` 이 뿌리를 `sys.path` 에 올려서 `app` 도 `pipeline` 도 그냥 import 된다.
전에는 파일마다 `sys.path.insert` 를 두고 있었는데 그건 이 우회였다.

파일 이름에 번호를 안 붙인다. `01_schema` 는 모듈 이름이 될 수 없다
(`import pipeline.01_schema` 는 문법 오류다). 순서는 `pipeline/__main__.py` 의
`STEPS` 가 들고 있다.

채점 도구도 같은 방식이다.

```
python -m eval.qa_check          검색이 정답 섹션을 찾아오나 (hit@k)
python -m eval.golden            추천 품질
python -m eval.format_check      LLM 형식 준수

USE_API=1 python -m eval.ragas_check    답변이 근거에 충실한가
```

`ragas_check` 는 호출이 돈이 된다. 그리고 `USE_API=1` 로만 돈다. ragas 가 LLM 을
심판으로 쓰는데 로컬 3B 는 심판으로 못 쓴다 (`docs/measurements.md`).

`*.db` 는 git 에 넣지 않는다. CSV 에서 다시 만든다.
