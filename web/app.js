const headers = {
  headers: {
    Authorization: "Bearer dev-token",
    "X-User-Id": "admin",
  },
};
const btn1 = document.querySelector("#btn1");
const btn2 = document.querySelector("#btn2");
const btn3 = document.querySelector("#btn3");
const section = document.querySelector("#frame");

// ==================================
//  회원정보 요청 함수 등록 및 호출
// ==================================

// 고객정보 확인함수
const getCustomer = async () => {
  const res = await fetch("/api/customers", headers);
  if (!res.ok) throw new Error();
  return res.json();
};

// 상품정보 확인 함수
const getProduct = async () => {
  const res = await fetch("/api/products", headers);
  if (!res.ok) throw new Error();
  return res.json();
};

// 특정 고객의 종합적인 구매 정보 확인함수
const getCustomerInfo = async (id) => {
  const res = await fetch(`/api/customers/${id}`, headers);
  if (!res.ok) throw new Error();
  return res.json();
};

// 리스트로 출력할 고객정보 배열로 반환함수

const getCustomerList = async () => {
  const lists = await getCustomer();

  let tags = "";

  // 배열을 반복돌면서 각각의 데이터와 순번 출력
  lists.forEach((data, index) => {
    console.log(data);
    tags += `
      <button>${data.name}</button>
    `;
  });

  console.log(tags);
  frame.innerHTML = tags;
};

getCustomerList();
