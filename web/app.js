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
  const result = await res.json();
  return result;
};

// 상품정보 확인 함수
const getProduct = async () => {
  const res = await fetch("/api/products", headers);
  if (!res.ok) throw new Error();
  // 응답객체를 json형태로 변환하는 작업도 시간이 걸리는 작업이기 때문에 await로 promise객체 정보값이 완료될때까지 홀딩(동기화)
  const result = await res.json();
  console.log(result);
  return result;
};

// 특정 고객의 종합적인 구매 정보 확인함수
const getCustomerInfo = async (id) => {
  const res = await fetch(`/api/customers/${id}`, headers);
  if (!res.ok) throw new Error();
  const result = await res.json();
  console.log(result);
  return result;
};

// 리스트로 출력할 고객정보 배열로 반환함수
const getCustomerList = async () => {
  const lists = await getCustomer();
  let tags = "";

  // 배열을 반복돌면서 각각의 데이터와 순번 출력
  lists.forEach((data, index) => {
    tags += `
      <button data-id=${data.customer_id}>${data.name}</button>
    `;
  });

  // 반복돌면서 문자열로 만든 버튼 태그 문자열을 Section안쪽에 돔으로 추가
  frame.innerHTML = tags;

  // 추가된 버튼을 모두 찾음
  const btns = document.querySelectorAll("#frame button");
  // 해당 버튼을 반복돌면서 이벤트 연결
  btns.forEach((btn) => {
    const cid = btn.getAttribute("data-id");
    btn.addEventListener("click", () => getCustomerInfo(cid));
  });
};

getCustomerList();

// ==========================================
//  폼안쪽의 정보들을 객체형태로 한번에 받아노는 법
// ==========================================
const form = document.querySelector("#productForm");
const btnSubmit = document.querySelector("#btnSubmit");

getProduct();

btnSubmit.addEventListener("click", async (e) => {
  // submit의 기본 이벤트 기능은 페이지이동이 포함되어 있기에
  // 기본 이벤트 기능을 막아줌
  e.preventDefault();

  // form안쪽에 있는 값을 모두 가져와서 키와, value분리
  const formInit = new FormData(form).entries();
  // 키와 value값 분리된걸 하나의 객체(딕셔너리)형태로 묶어줌
  const productInfo = Object.fromEntries(formInit);

  console.log(productInfo);

  const res = await fetch("/api/products", {
    method: "POST",
    headers: {
      Authorization: "Bearer dev-token",
      "X-User-Id": "admin",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(productInfo),
  });

  console.log(res);
});

/*
  fetch함수의 두번쨰 인자로 전달되는 객체 정보 구조
  {
    method: "POST",
    headers: {
      Authorization: "Bearer dev-token",
      "X-User-Id": "admin",
      "Content-Type": "application/json"
    }
    body: 서버에 전달할 문자화된 JSON 정보
  }
*/
