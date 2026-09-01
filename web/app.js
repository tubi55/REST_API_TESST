const headers = {
  headers: {
    Authorization: "Bearer dev-token",
    "X-User-Id": "admin",
  },
};
const btn1 = document.querySelector("#btn1");
const btn2 = document.querySelector("#btn2");

//현재 프로젝트에서 headers가 필요한 이유는 현재 페이지의 담당 관리자가 "나"라는 것을 증명하기 위함
//로그인하려고 만든게 아님
//추후 외부 서비스 연결시 담당자가 나임을 구분시키기 위한 정보값

// 고객정보 get 방식으로 요청하는 함수 정의
const getCustomer = async () => {
  const res = await fetch("/api/customers", headers);
  if (!res.ok) throw new Error();
  return res.json();
};

// 첫번째 버튼 클릭시 고객정보 반환함수 호출구문
btn1.addEventListener("click", async () => {
  const result = await getCustomer();
  console.log(result);
});

// ==================================
// 상품정보 요청 함수 등록 및 호출
// ==================================
// 고객정보 get 방식으로 요청하는 함수 정의
const getProduct = async () => {
  const res = await fetch("/api/products", headers);
  if (!res.ok) throw new Error();
  return res.json();
};

btn2.addEventListener("click", async () => {
  const result = await getProduct();
  console.log(result.content);
});
