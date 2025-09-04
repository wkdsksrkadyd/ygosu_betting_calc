document.addEventListener("DOMContentLoaded", () => {
  const startDateInput = document.getElementById("startDate");
  const select = document.querySelector("select[name=select]");
  const searchBtn = document.getElementById("searchBtn");
  const resultsDiv = document.getElementById("rankingResults");

  const today = new Date();

  // YYYY-MM-DD 포맷 변환
  const formatDate = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };

  // 초기값: 이번 달
  const thisMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
  startDateInput.value = thisMonth;

  // ✅ select 초기값 월간 배팅
  select.value = "월간 배팅";
  startDateInput.type = "month";

  // ✅ select 변경 이벤트
  select.addEventListener("change", () => {
    if (select.value === "월간 배팅") {
      startDateInput.type = "month";
      startDateInput.value = thisMonth;
    } else {
      startDateInput.type = "date";
      // 오늘 날짜 - 1일
      const yesterday = new Date(today);
      yesterday.setDate(today.getDate() - 1);
      startDateInput.value = formatDate(yesterday);
    }
  });

  async function fetchRanking(type) {
    resultsDiv.innerHTML = "<p>불러오는 중...</p>";

    let url = "";
    if (type === "월간 배팅") {
      url = `/api/monthly_ranking?statMonth=${startDateInput.value}`;
    } else {
      url = `/api/daily_ranking?statDate=${startDateInput.value}`;
    }

    try {
      const response = await fetch(url);
      if (!response.ok) {
        resultsDiv.innerHTML = `<p>오류: ${response.status}</p>`;
        return;
      }

      const data = await response.json();
      if (!data || data.length === 0) {
        resultsDiv.innerHTML = "<p>기록이 없습니다.</p>";
        return;
      }

      // ✅ 테이블 렌더링
      let html = "<table><thead><tr><th>순위</th><th>닉네임</th><th>총 배팅액</th><th>베팅수</th></tr></thead><tbody>";
      data.forEach((row, idx) => {
        html += `<tr>
          <td>${idx + 1}</td>
          <td>${row.nickname}</td>
          <td>${Number(row.total_amount).toLocaleString()}</td>
          <td>${row.total_bets}</td>
        </tr>`;
      });
      html += "</tbody></table>";

      resultsDiv.innerHTML = html;
    } catch (err) {
      resultsDiv.innerHTML = `<p>요청 실패: ${err.message}</p>`;
    }
  }

  // ✅ 검색 버튼 이벤트
  searchBtn.addEventListener("click", (e) => {
    e.preventDefault();
    fetchRanking(select.value);
  });

  // ✅ 페이지 로드 시 자동 실행 → 이번 달 월간 랭킹 표시
  fetchRanking("월간 배팅");
});
