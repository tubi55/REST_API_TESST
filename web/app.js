const btn1 = document.querySelector("#btn1");

// async 기본적으로 js는 비동기방식이라서 외부서버에서 데이터를 가지고오기전에 안쪽 코드가 실행되지 않도록 막아주기 위한 함수 설정
const getCustomer = async () => {
  // api 라우터에 설정된 url로 고객정보 호출 요청
  const res = await fetch("/api/customers", {
    // 요청 보낼때 관리자인지 구별하기 위한 인증 토큰
    headers: {
      Authorization: "Bearer dev-token",
      "X-User-Id": "admin",
    },
  });

  if (!res.ok) throw new Error();
  return res.json();
};

// btn1을 클릭하면 getCustomer함수 호출
// 만약 내부적으로 fetch(서버통신) 로직이 들어가 있는 함수호출시 async await을 안쓰면 발생하는 문제
// fetch는 promise 객체 반환 (값이 정해지지 않은 약속된 상태의 객체 (pending, fullfilled, rejected))
// async await 없이 fetch 반환값을 값을 호출하면 무조건 결과값이 Promise<pending>이라는 상태로 출력됨 (서버응답이 완료되지 않았기 때문)
// async await로 호출해야지 fullfilled로 완료된 상태의 결과값을 확인 가능
btn1.addEventListener("click", async () => {
  const result = await getCustomer();
  console.log(result);
});
