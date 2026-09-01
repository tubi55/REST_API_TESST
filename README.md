# cosmetic-admin

화장품 회사 관리자용 AI 대시보드. 고객 이력을 보고 상품을 추천하고, 상품 문서에서
근거를 찾아 답한다.

```
FastAPI (:8000)   AI 서버 + 화면. 검색 · 추천 · 질의응답 · 임베딩
SQLite            정형 데이터와 벡터를 같이 담는다
web/index.html    화면 한 장. 이 서버가 같이 준다
```

LLM 을 한 번 불러 보는 데모가 아니라, 데이터가 바뀔 때 생기는 문제를 다룬 백엔드다.
상품을 고치면 검색용 문장이 바뀌고, 벡터를 안 맞추면 화면과 검색 결과가 갈린다.
그 자리를 어떻게 다루는지가 이 저장소의 요점이다.

## 무엇이 들어 있나

| | |
| --- | --- |
| 검색 | 조각으로 찾고 원문 섹션을 LLM 에 준다 (small-to-big) |
| 추천 | SQL 로 후보를 좁히고 벡터로 순위를 매긴다. LLM 이 그중에서 고른다 |
| 질의응답 | 근거를 답보다 먼저 스트리밍으로 보낸다 |
| 개인정보 | 전화 · 메일은 아예 안 꺼내고, 후기는 나갈 때 가린다 |
| 안전 필터 | 주의사항 글을 읽고 민감성 고객에게 못 파는 상품을 뺀다 |
| 구조화 출력 | LLM 이 후보 번호로 답하게 하고, 범위와 중복을 코드가 검사한다 |
| 증분 임베딩 | 글의 지문이 바뀐 것만 다시 만든다 |
| 비용 | 요청마다 토큰과 원가를 남기고 사용자별 쿼터로 막는다 |

## 내려받아 처음 돌리기

**폴더 안에 없는 것이 둘 있다.** 각자 PC 에서 만든다.

```
.venv/         가상환경. 파이썬 패키지가 여기 깔린다
cosmetic.db    DB. data/*.csv 에서 만든다
```

둘 다 저장소에 안 올린다 (`.gitignore`). 받자마자 실행하면
`ModuleNotFoundError: fastapi` 가 난다. **아래 넷을 먼저 한다.**

**1. 파이썬 3.11 이상**

```bash
python --version
```

**2. 가상환경과 패키지**

전역 파이썬에 설치하지 않는다. 저장소 뿌리에서 한다.

```bash
python -m venv .venv
.venv\Scripts\activate                    윈도. 그 외는 source .venv/bin/activate
pip install -e ".[dev,local]"
```

`local` 은 로컬 임베딩용이라 torch 와 449MB 가중치를 끌고 온다. 3~5분 걸린다.
`USE_API=1` 로만 쓸 거면 빼도 된다.

**3. Ollama 와 모델** (로컬 백엔드로 돌릴 때만)

`qwen-cpu` 는 **직접 만드는 이름**이다. `ollama pull qwen-cpu` 로는 안 받아진다.
`qwen2.5:3b` 를 받아서 GPU 를 안 쓰게 다시 찍는다.

```bash
ollama pull qwen2.5:3b
ollama create qwen-cpu -f Modelfile       Modelfile 은 저장소 뿌리에 있다
ollama list                               qwen-cpu 가 보이면 된다
```

`Modelfile` 은 두 줄이다. `num_gpu 0` 이 빠지면 Ollama 가 GPU 를 잡으려 든다.
**그 한 줄이 CPU 고정이다.**

**4. 돌린다**

```bash
run.bat
```

`cosmetic.db` 가 없으면 CSV 에서 먼저 만들고(1분쯤) 서버를 띄운다.
윈도가 아니면 아래 `DB 가 없다면` 의 네 줄을 손으로 돌리고 uvicorn 을 부른다.

```bash
python -m uvicorn app.main:app --reload
```

http://127.0.0.1:8000 을 연다. 화면은 `/`, API 문서는 `/docs` 다.
`localhost` 말고 `127.0.0.1` 을 쓴다. 윈도에서 IPv6 를 먼저 물어보느라 요청마다 2초쯤 샌다.

`.env` 는 없어도 된다. 없으면 `APP_ENV=dev` · `USE_API=0` 으로 돈다.
상용 백엔드로 갈 때만 `.env.example` 을 `.env` 로 복사해 키를 채운다.

상태는 둘로 갈려 있다. `/health` 는 프로세스가 살아 있나만 보고,
`/ready` 는 DB · 벡터 표 · 임베딩기가 섰나를 실제로 물어서 아니면 503 을 준다.

### GPU 없이 돈다

두 자리에서 CPU 로 못 박혀 있다. 그래픽 카드가 없어도, 드라이버가 안 맞아도 돈다.

| 무엇 | 어디 |
| --- | --- |
| 임베딩 (multilingual-e5-small) | `app/core/embedder.py` 의 `model_kwargs={"device": "cpu"}` |
| LLM (qwen2.5 3B) | 저장소 뿌리 `Modelfile` 의 `PARAMETER num_gpu 0` |

앞의 것은 코드에 있어서 따라온다. **뒤의 것은 각자 PC 의 Ollama 에 있다.**
3번을 건너뛰고 `qwen2.5:3b` 를 그냥 `qwen-cpu` 로 이름만 바꾸면 GPU 를 쓰게 된다.

`requirements.lock.txt` 의 `torch==2.13.0` 은 PyPI 기본 휠이라 CPU 판이다.
`nvidia-*` 패키지가 하나도 안 딸려 온다.

### DB 가 없다면

CSV 에서 다시 만든다. 로컬 모델이라 비용이 없고 1분쯤 걸린다.

```bash
python -m pipeline schema        CSV -> DB (스키마를 값에서 추론한다)
python -m pipeline chunk         상세를 조각으로
python -m pipeline embed         조각 · 상품 · 고객 · 후기를 벡터로
python -m pipeline verify        점검
```

저장소 뿌리에서 `-m` 으로 부른다. 단계 목록은 `python -m pipeline` 이 보여 준다.

두 번째부터 `embed` 는 글이 바뀐 것만 다시 만든다. 전량은 `--full` 이다.

### 로컬과 상용

`.env` 의 한 글자로 갈린다. 코드는 안 바뀐다.

```
USE_API=0   로컬  Ollama qwen-cpu + multilingual-e5-small
USE_API=1   상용  OpenAI gpt-4o-mini + text-embedding-3-small
```

DB 는 백엔드마다 따로 만들어진다 (`cosmetic.db` / `cosmetic-api.db`).
로컬 벡터는 384차원, 상용은 1536차원이라 한 표에 못 섞기 때문이다.

로컬로 돌리려면 Ollama 가 떠 있어야 한다.

```bash
ollama serve
ollama list        qwen-cpu 가 보여야 한다
```

### 재기

```bash
pytest -q                        시험 (순수 로직 · 포트 계약 · API)
python -m pipeline verify        파이프라인 점검
python -m eval.golden            추천 품질 (hit@k)
python -m eval.qa_check          검색이 정답 섹션을 찾아오나
python -m eval.format_check      LLM 형식 준수
```

답변이 근거에 충실한지는 따로 잰다. ragas 가 필요하고 상용 백엔드로만 돈다.

```bash
pip install -e ".[eval]"
USE_API=1 python -m eval.ragas_check
```

호출이 실제로 돈이 된다. 로컬 3B 는 심판으로 못 써서 막아 뒀다.

## 부를 때

앞단 서버가 부르는 것을 전제로 한다. 헤더 두 개가 필요하다.

```
Authorization: Bearer <서비스 토큰>   이 서버를 부를 자격
X-User-Id: <사용자 id>               누구를 대신해 부르나
```

**이 서버는 끝 사용자를 인증하지 않는다.** 로그인은 앞단의 일이고, 이 서버는
그 결과를 헤더로 전해 받는다. 그래서 로그인 방식이 Supabase Auth 든 Spring JWT 든
`app/core/auth.py` 는 안 바뀐다. 쿼터와 비용 기록이 `X-User-Id` 를 열쇠로 쓴다.

지금은 `web/index.html` 이 앞단 노릇을 하느라 토큰을 들고 있다. 그대로 공개
배포하면 안 된다. 앞단 서버를 세우거나 쓰기 API 를 닫아야 한다.

## 구조

```
app/domain/       순수. DB · 네트워크 · LLM 을 모른다. 포트와 시험이 여기 붙는다
app/api/          HTTP. 라우터 · 의존성 · 오류 변환
app/features/     조립. domain 에 저장소를 붙인다
app/repositories/ 정형 데이터의 SQL. 이름 붙은 질의만 낸다
app/adapters/     바깥. LLM · 벡터 저장소
app/core/         아래층. 설정 · DB · 임베딩기 · 인증 · 관측
pipeline/        CSV 에서 DB 와 벡터를 만든다. 배포에는 안 따라간다
pipeline/prep/   준비 과정에서 같이 쓰는 함수들
eval/            품질을 재는 CLI
```

`app/` 이 `pipeline/` 을 import 하지 않는다. 둘이 같이 쓰는 순수 함수는
`app/domain/` 에 둔다. 벡터 저장소와 상품 저장소는 `app/domain/ports.py` 의
Protocol 뒤에 있고, 읽기와 쓰기가 둘 다 포트에 있다. 그 약속을 지키는지는
`tests/contract/` 가 본다.

## 재 본 값

추측을 안 적는다. 실제로 돌려서 나온 값만 `docs/measurements.md` 에 날짜 · 표본 ·
조건과 함께 모으고, 코드는 그 파일을 가리킨다. 몇 가지만 옮기면 이렇다.

| 무엇 | 값 |
| --- | --- |
| 고객 벡터에 후기를 넣으면 | hit@5 가 11.3% 에서 7.7% 로 떨어진다 |
| 이력 카테고리 필터 | hit@5 는 제일 좋지만 정답 생존율이 58.0% 다 |
| 자의 흔들림 | 표본 30명에서 16.7%p. 1%p 차이는 못 믿는다 |
| 구조화 출력 | 로컬 3B 17/30, 상용 gpt-4o-mini 29~30/30 |
| 전화번호 정규식 | 하이픈만 잡으면 152건 중 42건만 잡힌다 |
| 이름 사전 방식 | 우리 명단에 없는 이름은 못 잡는다. 최소 31건이 남는다 |

## 아직 안 한 것

정직하게 적어 둔다. 무엇을 왜 안 하기로 했는지는
`ARCHITECTURE.md` 8절에 있다.

- **저장소를 실제로 갈아끼워 본 적이 없다.** SQL 을 `app/repositories/` 한 층에
  모았고 약속을 `app/domain/ports.py` 에 적었고 계약 시험이 그 약속을 본다.
  거기까지다. 두 번째 구현이 없으니 "구현만 교체하면 된다" 는 아직 주장이다
- 임베딩 호출의 토큰 수를 못 세서 그 행의 원가가 0 으로 남는다.
  임베딩기가 안 돌려준다. 추정해서 채우지 않는다
- `web/index.html` 이 서비스 토큰을 들고 있다. 그대로 공개 배포하면 안 된다.
  `APP_ENV=prod` 면 기본 토큰으로는 서버가 안 뜨지만, 앞단 서버를 세우거나
  `PRODUCT_WRITE_ENABLED=0` 으로 쓰기를 닫기 전까지는 여전히 공개하면 안 된다
- 배포 대상 플랫폼의 잠금이 없다. `requirements.lock.txt` 는 `.venv` 안에
  그대로 설치되지만 Windows / Python 3.13 에서 뜬 것이라 플랫폼 마커가 없다.
  배포 대상을 정하는 날 그 플랫폼에서 다시 뜬다
- 마이그레이션에 downgrade 가 없고, 앱의 DB 계정이 DDL 권한을 늘 들고 있어야 한다

## 문서

| 파일 | 무엇 |
| --- | --- |
| `ARCHITECTURE.md` | 왜 이렇게 짰나. 코드만 봐서는 알 수 없는 결정 |
| `docs/measurements.md` | 실측값 |
| `CONVENTIONS.md` | 코드 작성 규칙 |
