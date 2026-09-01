# 벡터 저장소 객체를 한 번만 만든 뒤 필요한 곳에서 함께 사용하게 한다.

# 아직 저장소를 만들지 않았다는 뜻으로 None을 넣어 둔다.
_store = None


# 저장소 객체를 가져오며, 처음 호출됐을 때만 새 객체를 만든다.
def get_store():
    # 함수 안에서 모듈 전역 변수인 _store에 값을 넣기 위해 global을 사용한다.
    global _store
    # 저장소가 없을 때만 클래스를 불러와 객체를 생성한다.
    if _store is None:
        # 실제로 필요할 때 import하여 불필요한 초기 로딩과 순환 import를 피한다.
        from app.adapters.stores.sqlite_store import SqliteVectorStore

        # 저장소를 한 개 만들어 모듈 전역 변수에 담아 둔다.
        _store = SqliteVectorStore()
    # 이후 호출에서는 이미 만들어 둔 같은 저장소 객체를 반환한다.
    return _store
