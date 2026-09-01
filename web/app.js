const headers = {
  headers: {
    Authorization: "Bearer dev-token",
    "X-User-Id": "admin",
  },
};
const btn1 = document.querySelector("#btn1");
const btn2 = document.querySelector("#btn2");
const btn3 = document.querySelector("#btn3");

// ==================================
//  회원정보 요청 함수 등록 및 호출
// ==================================

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
//  상품정보 요청 함수 등록 및 호출
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

// ==========================================================
//  인자로 특정 고객 아이디를 받아서 고객정보 요청 함수 등록 및 호출
// ==========================================================

const getCustomerInfo = async (id) => {
  const res = await fetch(`/api/customers/${id}`, headers);
  if (!res.ok) throw new Error();
  return res.json();
};

btn3.addEventListener("click", async () => {
  const result = await getCustomerInfo("C001");
  console.log(result);
});
