"""FastAPI 서버를 만들고 API 라우터와 관리자 화면을 연결한다."""

# 화면 폴더가 없을 때 경고를 남기기 위해 사용한다.
import logging

# 폴더가 실제로 있는지 확인하기 위해 사용한다.
from pathlib import Path

# 웹 서버 본체를 만드는 클래스다.
from fastapi import FastAPI

# HTML 과 JS 같은 파일을 그대로 내려 주는 도구다.
from fastapi.staticfiles import StaticFiles

# 뜰 때와 내려갈 때 할 일을 담은 함수다.
from app.api.lifespan import lifespan

# 주소가 모여 있는 네 파일을 가져온다.
from app.api.routers import ask, customers, health, products

# 화면 파일이 들어 있는 폴더 위치다.
from app.core.config import WEB_DIR

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# title 과 version 은 자동 생성되는 API 문서에 그대로 나온다.
app = FastAPI(title="화장품 관리자 대시보드 API", version="2.0", lifespan=lifespan)

# 네 파일의 주소를 차례로 붙인다. 이 파일은 조립만 한다.
for module in (health, customers, products, ask):
    # 각 파일이 만들어 둔 router 를 그대로 붙인다.
    app.include_router(module.router)

# 화면 폴더가 있을 때만 붙인다.
if Path(WEB_DIR).is_dir():
    # html=True 는 주소 끝에 파일 이름이 없으면 index.html 을 준다는 뜻이다.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
# 폴더가 없을 때다.
else:
    # 화면이 없어도 API 는 그대로 돌아야 하므로 멈추지 않고 경고만 남긴다.
    log.warning("화면 폴더가 없어 마운트를 건너뛴다: %s (API 는 그대로 돈다)", WEB_DIR)
