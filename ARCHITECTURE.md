# 설계

작업 전에 이 문서를 읽는다. 코드만 봐서는 알 수 없는 결정을 여기 적는다.

실측값은 `docs/measurements.md`, 작업 규칙은 `CONVENTIONS.md` 에 있다.

## 무엇을 만들고 있나

화장품 회사 관리자용 AI 대시보드. 지금은 프로세스가 하나다.

```
FastAPI (:8000)   AI 서버 + 화면. web/index.html 을 같이 준다
```

같은 주소에서 화면과 API 가 나오므로 CORS 설정이 필요 없다.
앞단 서버를 따로 세우는 날 이 마운트를 빼고 CORS 를 켠다.

## 지금 상태

| | |
| --- | --- |
| 백엔드 | 로컬 (Ollama qwen-cpu + multilingual-e5-small) |
| 상용 전환 | `.env` 의 `USE_API=1` 한 글자. 코드는 안 바뀐다 |
| DB | SQLite. 백엔드마다 파일이 따로다 |
| 환경 | `APP_ENV` 가 `dev` · `test` · `prod` 를 가른다. 운영 검사는 §10 |

### 나중에 갈 곳은 두 갈래다

지금 고르지 않는다. 고르지 않은 채로 진도가 나가게 경계만 잡아 둔다.

```
단독형   FastAPI -> ProductRepository -> Postgres / Supabase
분리형   FastAPI -> ProductRepository -> Spring Boot API -> MySQL
```

분리형에서는 상품과 고객의 원본을 Spring 이 소유한다. FastAPI 는 검색 · 추천 ·
질의응답 · 임베딩만 맡는다. FastAPI 와 Spring 이 같은 MySQL 표를 동시에 직접
고치면 서비스 경계와 데이터 책임이 불명확해지므로, FastAPI 는 MySQL 에 직접 안 닿는다.

**두 모델에서 상품 CRUD 의 운명이 다르다.** 단독형이면 지금처럼 이 서버에 있고,
분리형이면 쓰기 API 가 사라지고 "Spring 이 바뀌었다고 알려주면 임베딩을 맞춘다"
만 남는다. 지금 CRUD 를 만든 이유는 단독형이 기본값이기 때문이다.

DB 를 백엔드마다 나눈 이유는 차원이 다르기 때문이다. 로컬은 384, 상용은 1536 이라
한 표에 못 섞는다. 나눠 두면 각각 한 번씩만 만들고 `USE_API` 만 바꿔서 오간다.

---

## 1. 갈아끼울 자리를 어디에 그었나

### 벡터 저장소 (Python)

`app/domain/ports.py` 의 Protocol 뒤에 있다. 읽기와 쓰기가 둘 다 있다.

포트가 `domain/` 에 있는 이유는 포트가 안쪽 것이기 때문이다. 구현이 포트를 향해야
하는데 포트가 구현 옆에 있으면 그 방향이 안 보인다. `sqlite_store.py` 는 Protocol
을 상속하지 않는다. 상속하면 구현이 포트를 import 하게 된다.

```
읽기   search(kind, vector, k, only_ids=, reverse=) · get_vector · has
       hashes(kind, ids=) · chunk_ids_for_products(ids)
       fetch_payloads(kind, ids, columns)
쓰기   recreate(kind, dim, model, payload_columns) · upsert · delete · set_payload
```

`hashes` 의 `ids=` 는 `only_ids` 와 같은 종류의 인자다. 쓰임이 실제로 둘이다.
파이프라인은 무엇을 지우고 만들지 정하려고 전량을 묻고, 화면은 이 쪽에 실린
상품만 최신인지 묻는다. 안 가르면 상품 한 건을 읽을 때마다 벡터 표를 통째로
훑는다. 200행에서는 시간 차이가 안 잡히지만(`docs/measurements.md`) 저장소가
네트워크 너머로 가면 그 행 수가 그대로 왕복이 된다.

읽기 쪽 아래 두 줄은 검색이 벡터만으로 안 끝나기 때문에 있다. 상품으로 좁힐 때
어느 조각이 그 상품 것인지 알아야 하고, 찾은 다음에는 베껴 둔 값을 붙여야 한다.
표 이름을 물으면 그게 밖으로 새므로 질문 자체를 포트에 이름으로 적었다.

`set_payload` 는 벡터를 안 건드리고 베껴 둔 값 하나만 고친다. 상품 이름이 바뀌면
조각 글은 그대로인데 `chunk_vectors.product_name` 만 낡는데, 그 자리에 쓴다.
아이디를 명시해서 받는다. 조건을 받으면 그건 쿼리 빌더다.

검사는 이렇게 한다. 저장소 구현을 포트를 우회해 import 하는 곳이 없어야 한다.

```bash
grep -rn "from app.adapters.stores.sqlite_store import" --include=*.py app/ pipeline/ eval/
# stores/__init__.py 말고는 아무것도 안 나와야 한다
```

주석에서 pgvector 를 언급하는 것은 상관없다. 막는 것은 import 다.

**포트에 쿼리 빌더를 노출하지 않는다.** `only_ids` 처럼 이름 붙은 인자만 노출한다.
`load_all() -> 행렬` 로 적으면 pgvector 를 붙여도 이점이 없다. 벡터를 전부 앱으로
끌어온 다음 앱이 계산하게 되고, 인덱스도 못 쓴다.

읽기만 추상화하면 반쪽이다. 쓰기가 없으면 Supabase 로 옮기는 날 `pipeline/embed.py` 가
통째로 안 돈다.

### 살아 있나와 준비됐나는 다른 질문이다

```
GET /health   프로세스가 응답하나. 아무것도 확인하지 않는다
GET /ready    DB · 벡터 표 · 임베딩기가 섰나. 아니면 503
```

로드밸런서가 둘을 다르게 쓴다. liveness 가 실패하면 다시 띄우고, readiness 가
실패하면 트래픽만 안 보낸다. 하나로 두면 고를 수가 없다. DB 가 없어서 못 받는
서버를 죽었다고 보고 다시 띄우면, 다시 떠도 DB 는 여전히 없으니 재시작만 반복한다.

`/ready` 는 참거짓만 낸다. 왜 아닌지는 서버 로그에 남긴다. 준비 안 된 이유가
본문에 붙으면 그게 곧 내부 구조를 알려 주는 글이 된다.

### 스트리밍은 줄 단위 JSON 이다

`/api/ask` 는 NDJSON 을 줄 단위로 흘려보낸다. 화면은 줄이 올 때마다 받아 붙인다.

```
{"type": "route"}    어느 쪽으로 갈랐나
{"type": "sources"}  근거를 답보다 먼저 보낸다
{"type": "delta"}    글자
{"type": "done"}
```

앞단 서버를 세우는 날 이것만 값 하나를 돌려주는 방식으로 감싸면 안 된다.
중간에 모으면 스트리밍이 아니게 된다. 몸통을 그대로 흘려보내야 한다.

**오류가 나도 상태 코드는 200 이다.** 첫 줄을 보낸 순간 이미 굳었기 때문이다.
그래서 감시 도구는 이 요청을 성공으로 센다. 대신 서버 로그에 남긴다.
`{"type": "error"}` 의 글은 고정된 한 문장이다. 예외 글을 그대로 실으면
접속 문자열이나 내부 경로가 같이 나간다.

## 2. 데이터가 오가는 형식

| 자리 | 형식 | 왜 |
| --- | --- | --- |
| 새 API (`/api/products`) | camelCase | Spring 이 줄 모양과 같다 |
| 옛 API (`/api/customers` 등) | snake_case | 이미 굳었다. 앞단의 매퍼가 흡수한다 |

목록 응답은 Spring Data 의 `Page<T>` 와 같은 모양이다.

```
{ content, totalElements, number, size }
```

지금 이렇게 잡아 두면 Spring 으로 갈아끼우는 날 REST 어댑터가 변환 없이 그대로 쓴다.

앞단을 TypeScript 로 세우는 날 타입은 손으로 안 쓴다. FastAPI 의 OpenAPI 스키마에서
생성한다 (`openapi-typescript`). 그래서 `response_model` 이 곧 프런트의 타입 원본이다.

`response_model` 이 정확할수록 프런트가 안전해진다. 그래서 전 엔드포인트에 붙인다.
예외는 둘뿐이다.

| 엔드포인트 | 왜 없나 |
| --- | --- |
| `POST /api/ask` | StreamingResponse 라 붙일 수 없다 |
| `DELETE /api/products/{id}` | 204 라 돌려줄 몸통이 없다 |

---

## 3. 증분 임베딩

**판단 기준은 시각이 아니라 글의 지문이다.**

```
fingerprint = md5(모델이름 + "\n" + 임베딩에 넣을 글)[:16]
```

- 고쳤다가 되돌리면 시각은 바뀌지만 지문은 그대로다. 그래서 안 만든다
- 지문에 모델 이름이 들어간다. 모델을 바꾸면 전량 재생성이 저절로 따라오고
  차원이 달라지는 것도 같이 막힌다
- 벡터 표의 `source_hash` 컬럼에 저장한다

`app/features/embedding_sync.py` 한 곳에 있고 파이프라인과 앱이 같이 쓴다.

```
sync(kind, ids, texts, ...)   파이프라인. 전량을 맞춘다
sync_one(kind, id, text, ...) 앱. 상품 CRUD 와 reindex 가 부른다
```

`POST /api/products/{id}/reindex` 로 밖에서도 부를 수 있다. **두 갈래 어느 쪽으로
가든 살아남는 기능이 이것 하나다.** 단독형이면 CRUD 가 저장한 뒤 스스로 부르고,
분리형이면 쓰기 API 가 사라진 자리에서 Spring 이 부른다. 안에서만 부를 수 있게
두면 그날 이 서버를 다시 써야 한다.

멱등해서 재시도 로직이 따로 없다. 지문이 같으면 건너뛰므로 몇 번을 불러도 같다.

**상품을 고치면 그 자리에서 그 한 건만 다시 임베딩한다.** 안 그러면 화면에는
새 값이 보이는데 추천과 검색은 옛 값으로 돈다. 오류는 안 난다.

### 임베딩이 실패하면

상품 수정은 성공시킨다. 둘을 같이 실패시키면 사용자가 고친 내용을 잃는데,
벡터는 나중에 언제든 다시 만들 수 있기 때문이다.

**무엇이 아직 안 맞는지를 상태 컬럼에 저장하지 않는다.** 지문을 견주면 알 수 있다.

```
저장된 지문 == 지금 글의 지문    최신이다
다르다                          다시 만들어야 한다  (needs_embedding)
벡터가 없다                     한 번도 안 만들었다 (has_vector = false)
```

상태 컬럼은 갱신을 빠뜨리면 거짓말을 한다. 벡터를 넣고 상태를 적기 전에 죽으면
어긋나고, 어긋난 것을 알아낼 방법이 없다. 지문은 내용에서 나오므로 못 그런다.

재시도도 따로 안 만든다. 다시 저장하거나 `pipeline/embed.py` 를 돌리면 지문이 안 맞는
것만 다시 만들어진다. 멱등성이 곧 재시도다.

`pending / processing / completed / failed` 같은 상태 기계를 넣지 않은 이유가
이것이다. 그 상태를 옮길 워커가 없고, 있어도 지문보다 정확하지 않다.

`pipeline/chunk.py` 를 다시 돌리면 조각 벡터는 전량 다시 만들어진다. `chunk_id` 가
새로 붙는 자동 번호라 지문이 아니라 아이디부터 안 맞기 때문이다. 이건 조각이
파생물이라는 성질에서 오는 것이고, 상품·고객·후기는 영향을 안 받는다.

---

## 4. CSV 와 화면 수정이 충돌하는 자리

`pipeline/schema.py` 는 CSV 를 원본으로 보고 DB 를 다시 만든다. 그런데 CSV 가 원본이
아닌 것도 표 안에 있다.

- 화면에서 만든 상품
- `usage_log`

그래서 `products` 에 `source` 컬럼을 둔다.

```
csv   CSV 에서 온 행. 재적재 때 덮인다
app   화면에서 만들거나 고친 행. 안 덮인다
```

`pipeline/schema.py` 가 지우기 전에 `source='app'` 행과 `usage_log` 를 떠 두고
다시 만든 뒤에 되돌려 놓는다.

이건 코드가 아니라 설계 문제다. 원본이 무엇인지 먼저 정해야 지워도 되는지가 정해진다.

---

## 5. 마스킹

**나가는 글을 가리는 자리는 하나여야 한다.**

```
app/domain/masking.py     규칙. 사전을 인자로 받는다. 이름이 mask 다
app/features/privacy.py   조립. 사전(DB)을 붙인다. 앱이 부르는 mask_text 다
```

예전에 두 함수 이름이 둘 다 `mask_text` 였고, `llm.py` 가 사전 없이 domain 쪽을
불러서 **이름과 주소가 안 가려진 채로 프롬프트에 실렸다.** 이름을 갈라서 실수로
못 부르게 했다.

`profile.dashboard()` 가 `review_masked` 를 만들어 두고, 프롬프트 조립은 그것을
쓴다. 다시 가리지 않는다. 가리는 자리가 둘이면 하나는 반드시 약해진다.

### LangSmith 를 켤 때

LangSmith 가 받는 글은 OpenAI 가 받는 글과 **같다.** 둘 다 마스킹을 지난 뒤다.
"이미 OpenAI 로 나가니까 하나 더는 상관없다" 는 틀린 추론이지만, "LangSmith 는
더 많이 본다" 도 틀렸다. 실제 차이는 셋이다.

1. **마스킹이 완전하지 않다.** 우리 고객 명단에 없는 이름은 못 잡고 최소 31건이
   남는다 (`docs/measurements.md`). 받는 곳이 늘면 그 잔여분도 같이 는다
2. **목적이 다르다.** OpenAI 는 답을 만들려고 잠깐 받고, LangSmith 는 나중에
   사람이 읽으려고 저장한다. 보관 기간과 열람 범위가 다르다
3. **개인정보 처리위탁이 하나 더 생긴다.** 별개 사업자라 계약과 고지가 따로 필요하다

그래서 스위치를 둘로 나눴다.

```
LANGSMITH_TRACING     켤까 말까
LANGSMITH_SEND_BODY   본문을 보낼까 말까 (기본 false)
```

`SEND_BODY` 가 꺼져 있으면 `hide_inputs` · `hide_outputs` 를 건 클라이언트로
갈아끼워서 토큰 · 시간 · 실패 · 재시도만 간다. 관측의 값은 대부분 거기 있다.
본문이 필요한 것은 디버깅할 때고 그건 개발 환경에서 한다.

기본값이 꺼짐인 이유는 운영에 그대로 올라가도 본문이 안 나가야 하기 때문이다.

무료 등급은 1인 · 월 5,000 트레이스 · 보관 14일이고 SSO 나 RBAC 이 없다.
누가 트레이스를 볼 수 있는지를 정해야 하는 단계가 되면 유료 등급이 필요하다.

---

## 6. SQLite 를 여럿이 동시에 쓸 때

`app/core/db.py` 가 스레드마다 연결을 따로 만든다.

FastAPI 는 동기 엔드포인트를 스레드풀에서 돌리고, 프런트는 한 화면에서 여러
요청을 동시에 보낸다. 연결 하나를 여러 스레드가 같이 쓰면 이렇게 된다.

```
sqlite3.InterfaceError: bad parameter or other API misuse
```

`check_same_thread=False` 는 검사를 끌 뿐 동시 사용을 안전하게 만들지 않는다.
WAL 과 `busy_timeout` 도 같이 켠다.

**연결 객체를 이 파일 밖으로 내보내지 않는다.** 밖으로 새면 Postgres 로 옮기는 날
그걸 쥔 파일을 전부 뒤져야 한다.

---

## 7. 저장소를 갈아끼울 때

### 성공 판정

그날 바뀌는 파일 수로 잰다.

```
새로 만드는 것   app/adapters/stores/pgvector_store.py
                app/repositories/ 의 구현 한 벌
고치는 것        stores/__init__.py       분기 한 줄  (벡터)
                repositories/__init__.py 분기 한 줄  (정형)
                config.py 에 DATABASE_URL
안 바뀌는 것     app/features/  app/domain/  app/api/
                pipeline/embed.py
다시 쓰는 것     pipeline/verify.py
```

**고르는 자리가 두 경계에 다 있다.** 전에는 벡터에만 있었다. `features/` 가
`from app.repositories import products` 로 구현 모듈을 이름으로 불렀기 때문에,
두 번째 구현을 옆에 둘 수가 없고 그 파일의 내용을 그 자리에서 갈아치우는
수밖에 없었다. 지금은 `get_product_repo()` 를 부른다. `get_store()` 와 같은 모양이다.

`pipeline/embed.py` 가 한 글자도 안 바뀌고 도는가. 이게 시험이다.

`pipeline/verify.py` 는 예외로 둔다. 파일 크기와 `PRAGMA` 를 보는 SQLite 점검 도구라
저장소가 바뀌면 어차피 다시 쓴다. 지킬 수 없는 약속은 안 한다.

**판정을 세어 볼 수 있는 상태가 됐다.** `app/features/` 와 `app/api/` 에 SQL 도
벡터 표 이름도 없다. 두 줄로 확인한다.

```bash
grep -rn "SELECT\|INSERT\|UPDATE \|DELETE FROM\|PRAGMA" --include=*.py app/features/ app/api/
grep -rn "_vectors" --include=*.py app/features/
# 둘 다 아무것도 안 나와야 한다
```

방향은 grep 이 아니라 `tests/test_layers.py` 가 본다. import 그래프를 떠서
아래층이 위층을 가리키는 자리가 있나 센다. 파일 하나를 열어서는 그 import 가
위인지 아래인지 알 수 없어서 눈으로는 안 잡힌다. 실제로 `core/usage.py` 가
`app.repositories` 를 부르던 것을 이 검사가 잡았다.

**아직 갈아끼워 본 적은 없다.** 두 번째 구현이 없기 때문이다. 위의 파일 수는
그날 실제로 세어 볼 수 있게 됐다는 뜻이지 세어 봤다는 뜻이 아니다.
`app/repositories/` 를 한 벌 더 쓰는 날 센다.

### RLS 는 최후의 그물로만 쓴다

이게 제일 중요하다.

RLS 는 권한 로직을 DB 에 넣는 것이고 **MySQL 에는 RLS 가 없다.** 여기에 업무 규칙을
많이 실을수록 나중에 Spring + MySQL 로 옮기는 날 그 로직이 어댑터 교체가 아니라
**재작성**이 된다. 어댑터 패턴이 안 구해 준다.

- 정책은 단순하게. "로그인한 관리자면 읽는다" 수준
- "이 고객은 이 담당자만 본다" 같은 업무 규칙은 RLS 에 넣지 않는다
- 그 규칙은 순수 함수로 두면 Spring 으로 그대로 따라간다

`app/domain/safety.py` 를 순수하게 둔 것과 같은 판단이다.

### 정형 데이터의 플레이스홀더

Postgres 로 가면 SQL 의 `?` 가 `%s` 로 바뀌고, `INSERT OR REPLACE` 는
`ON CONFLICT DO UPDATE` 가 된다. MySQL 이면 `ON DUPLICATE KEY UPDATE` 다.

조건은 **SQL 이 한 층 안에 모여 있는 것**이다. 지금 그 상태다.
정형 데이터의 SQL 은 `app/repositories/` 의 여섯 파일에 있고, 벡터 표의 SQL 은
`app/adapters/stores/sqlite_store.py` 안에 있다. `db.py` 는 실행기다.

여러 표를 걸치는 변경은 `repositories.transaction()` 으로 묶는다. 없으면 문장마다
커밋이라 중간에 터졌을 때 반쯤 지워진 상태가 파일에 남는다. 묶이는 범위는 한
연결이라 SQLite 벡터 표까지는 같이 묶이고, 벡터를 다른 저장소로 옮기는 날에는
안 묶인다. 지킬 수 없는 약속은 안 한다.

`grep` 세 줄은 이제 CI 가 돌린다 (`.github/workflows/ci.yml`). 문서에만 적어 두면
사람이 기억해야 돌고, 기억은 언젠가 빠진다.

`app/repositories/` 는 이름 붙은 함수만 낸다. `find_page(...)` 는 되고
WHERE 절이나 SQL 조각을 인자로 받는 함수는 없다. 받는 순간 이 층이 쿼리 빌더가
되고, 갈아끼울 때 그 빌더까지 같이 옮겨야 한다.

### 인증

세 경계를 넘는다.

| 경계 | 지금 | 나중 |
| --- | --- | --- |
| 브라우저 → 앞단 | 없다. 화면이 앞단 노릇을 한다 | Supabase Auth 또는 Spring JWT |
| 앞단 → AI 서버 | 서비스 토큰 + `X-User-Id` | 그대로 |

**AI 서버는 끝 사용자를 인증하지 않는다.** 앞단이 인증하고 그 결과를 헤더로 전한다.
그래서 로그인 방식이 바뀌어도 `app/core/auth.py` 는 안 바뀐다.
쿼터와 비용 기록이 `X-User-Id` 를 열쇠로 쓴다.

이건 로그인이 아니라 **서비스 토큰**이다. 그렇게 부른다. 지금은 `web/index.html`
이 앞단 노릇을 하느라 토큰을 들고 있는데, 그 상태로 밖에 내보내면 안 된다.
공개 배포한다면 앞단 서버를 먼저 세우거나 쓰기 API 를 닫는다.

정직한 기대치는 **"90% 갈아끼워지고 인증은 다시 짠다"** 다. 인증까지 완전히
추상화하려는 시도는 실무에서도 대개 실패한다. 새는 범위를 좁게 가두는 것이 목표다.

---

## 8. 지금 안 넣은 것과 그 이유

먼저 표로 적어 둔다. 작업하다 흔들릴 때 여기를 본다.

| 안 넣는다 | 왜 |
| --- | --- |
| `LLMClient` 인터페이스 | `adapters/llm.py` 가 서른 줄이고 분기가 `base_url` 하나다. LangChain 의 Runnable 이 이미 인터페이스다. 그 위에 하나 더 씌우면 인터페이스 남발이다 |
| `features/` 를 `application/` 로 이름 갈이 | 의존 방향은 이미 맞다. 이름만 바꾸면 커밋만 지저분해진다 |
| Next.js 프런트 새로 만들기 | 어중간한 것이 하나 더 생긴다. `web/index.html` 한 장이 정직하다. 이건 AI 서버 프로젝트다 |
| Supabase 와 MySQL 동시 구현 | 확정 안 된 미래를 위한 과설계다. 교체 지점만 정의한다 |
| 로그인 UI · 회원가입 · 역할 구분 | 관리자 한 종류뿐인 서비스에 역할 모델을 미리 만드는 일이다 |
| 고객 CRUD | 상품 CRUD 만으로 쓰기 시나리오가 증명된다. 넓히면 게시판 CRUD 가 된다 |
| 상태 컬럼 (`pending`/`completed`/`failed`) | 그 상태를 굴릴 워커가 없다. 지문이 같은 일을 더 정확하게 한다. 자세한 것은 3절 |
| 마이그레이션 도구 (alembic) | 표가 열 개다. 뜰 때 한 번 도는 함수와 `schema_version` 표로 충분하다 |

**경계는 둘이면 된다.** `ProductRepository` 와 `VectorStore` 다.
사용처가 하나뿐인 함수마다 인터페이스를 만드는 것은 전문성이 아니다.

아래 셋은 조건이 구체적이라 따로 적는다.


### LangGraph

`app/features/answering.py` 의 `route()` 는 낱말 대조 `if` 한 줄이고,
`recommending.py` 의 재시도는 `for` 루프 한 개다. 노드 3개짜리 그래프는
`for` 루프보다 읽기 어렵다.

넣을 만해지는 조건은 셋 중 하나다.

1. 멀티턴 대화 (지금은 질문마다 무상태다)
2. 툴 콜
3. 사람 승인이 낀 흐름

준비는 돼 있다. 프롬프트 조립(순수)과 오케스트레이션이 이미 갈라져 있어서
루프만 그래프로 갈아끼우면 된다.

### 라우팅 개선

`PRODUCT_WORDS` 하드코딩은 약하다. 우리는 이미 임베딩을 갖고 있으니 질문 벡터로
라우팅하면 낱말이 안 겹쳐도 갈린다. "환불" 문제와 같은 구조다. 싸고 효과가 있다.

### mypy

넣는다면 `app/domain` 과 `app/adapters/stores` 에만 `strict` 로 건다.
`features/` 에 켜면 `dicts()` 가 주는 `dict[str, Any]` 때문에 `Any` 가 퍼져서
소음만 는다.

---

## 9. 운영으로 나갈 때

개발에서 경고로 넘어가던 것이 `APP_ENV=prod` 에서는 서버가 안 뜨는 이유가 된다.
뜨고 나서 첫 요청에 죽는 것보다 안 뜨는 편이 낫다. 배포가 실패했다는 것을 그
자리에서 알 수 있고, 반쯤 도는 서버가 트래픽을 안 받는다.

```
API_TOKEN 이 기본값     거절. 그 값은 공개돼 있어 인증이 없는 것과 같다
DB_PATH 가 안 잡힘      거절. 기본값은 소스 폴더 안이라 다시 배포하면 사라진다
USE_API=1 인데 키 없음   거절
```

### 쓰고 읽는 파일은 소스 폴더 밖이다

`DB_PATH` · `RUNS_PATH` · `WEB_DIR` 을 환경변수로 받는다. 기본값은 소스 폴더 안이고
그건 개발에서만 맞다. 소스 폴더에 쓰면 읽기 전용 컨테이너에서 못 돌고, 다시
배포하면 사라지고, 코드와 운영 데이터의 소유권이 섞인다.

설치해서 돌리면(wheel) `ROOT` 는 site-packages 를 가리킨다. 그래서 경로를 상수로
두면 안 된다.

### 화면은 별도 배포 대상이다

`web/` 은 wheel 에 **일부러 안 넣는다.** 없으면 마운트를 건너뛰고 API 만 뜬다.

`app/static/` 으로 옮겨 package data 로 싣는 길도 있지만 안 간다. 이 프로젝트는
앞단을 분리하기로 이미 정해 뒀다. 패키지 안으로 넣으면 그날 도로 꺼내야 하고,
그 사이에 파이썬 배포와 화면 배포의 주기가 묶인다.

```
지금    같은 프로세스가 web/ 을 같이 준다. WEB_DIR 로 어디를 볼지 정한다
운영    화면은 정적 호스팅이나 앞단 서버가 맡는다. 이 서버는 API 만 낸다
```

그래서 배포 산출물이 둘이다. `pip install` 로 가는 wheel 과, `web/` 을 그대로
올리는 정적 파일이다. wheel 하나만 올려 두고 화면이 안 보인다고 놀랄 자리가
여기라서 적어 둔다.

### 참거짓 값은 오타를 조용히 넘기지 않는다

`USE_API=true` 는 `== "1"` 로 보면 거짓이 된다. 모델만 바뀌는 게 아니라 임베딩
차원과 DB 파일까지 갈아타서, 상용을 켠 줄 알고 넣은 데이터가 다른 파일에 들어간다.
`env_bool()` 이 `1 true yes on y` 와 `0 false no off n` 을 받고 나머지는 뜰 때 거절한다.

### 상품 쓰기 문

`PRODUCT_WRITE_ENABLED=0` 이면 `POST` · `PATCH` · `DELETE` 가 405 가 되고 읽기와
reindex 만 남는다. 분리형으로 가는 날 코드를 지우기 전에 먼저 닫아 보고 되돌릴 수
있다. **문이 둘이면 누군가는 반드시 잘못된 문으로 쓰고, 다른 쪽은 그걸 모른다.**

### 표 모양의 버전

`schema_version` 표에 무엇이 어디까지 돌았는지 적는다. 전에는 뜰 때 마이그레이션을
그냥 돌려서, 손에 든 DB 파일이 어느 코드에 맞는지 물어볼 방법이 없었다.

단계는 멱등해야 한다. 이 표는 잠금이 아니라서 인스턴스 둘이 동시에 뜨면 같은
단계를 둘 다 돌 수 있다. 그때 안전한 것은 잠금이 아니라 멱등성이다.
alembic 은 아직 안 넣는다. 표가 열 개다.

### 쿼터는 세면서 잡는다

세고 나서 넣으면 그 사이가 열려 있다. 동시에 온 요청이 전부 같은 숫자를 보고
통과하면 상한이 있으나 마나다. LLM 을 부르기 전 관문이라 그 창이 곧 돈이다.

그래서 `usage.reserve()` 가 한 문장으로 세면서 넣는다. 끝나면 `usage.settle()` 이
그 칸을 채운다. 새 줄을 안 만들므로 한 번 쓰고 두 번 세이지 않는다.

---

## 10. 실행

```bash
python -m pipeline schema        CSV -> DB
python -m pipeline chunk         상세 청킹
python -m pipeline embed         임베딩 (--full 로 전량)
python -m pipeline verify        점검
uvicorn app.main:app --reload    AI 서버 + 화면 (http://127.0.0.1:8000)
pytest -q                        시험
```

저장소 뿌리에서 `-m` 으로 부른다. `-m` 이 뿌리를 `sys.path` 에 올려서 `app` 도
`pipeline` 도 그냥 import 된다. `pipeline/` 은 배포에 안 따라가므로
`console_scripts` 로 내보내지 않는다. 설치본에서 그 명령이 깨진다.

시험은 세 갈래다.

```
tests/test_*.py     순수 로직. DB 도 서버도 없이 돈다
tests/contract/     저장소가 포트의 약속을 지키는가. 임시 DB 를 자기가 만든다
tests/api/          진짜 앱을 세우고 HTTP 로 부른다. cosmetic.db 를 임시로 떠서
                    거기 붙고, 임베딩기는 가짜로 갈아 끼운다
```

`tests/api/` 는 embed.py 를 안 돌린 DB 에서도 돈다. 가짜 임베딩기로 벡터를
스스로 채우기 때문이다. DB 가 아예 없으면 `tests/api/seed.py` 가 최소 데이터를
만든다. 그래서 CI 가 schema.py 와 chunk.py 까지만 돌리고도 전부 돌릴 수 있다.
