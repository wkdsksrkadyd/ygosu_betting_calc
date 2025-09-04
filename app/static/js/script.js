document.addEventListener("DOMContentLoaded", () => {
  const startDateInput = document.getElementById("startDate");
  const endDateInput = document.getElementById("endDate");
  const select = document.querySelector("select[name=select]");
  const searchBtn = document.getElementById("searchBtn");
  const resultsDiv = document.getElementById("results");

  const today = new Date();

  // YYYY-MM 포맷 변환
  const formatMonth = (y, m) => `${y}-${String(m + 1).padStart(2, "0")}`;
  // YYYY-MM-DD 포맷 변환
  const formatDate = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };
  // 해당 월의 마지막 날짜 구하기
  const getMonthEndDate = (ym) => {
    const [y, m] = ym.split("-").map(Number);
    const lastDay = new Date(y, m, 0).getDate();
    return `${ym}-${String(lastDay).padStart(2, "0")}`;
  };

  // 최근 3개월 기본값
  const year = today.getFullYear();
  const month = today.getMonth(); // 0~11
  const endMonthVal = formatMonth(year, month);
  let startYear = year;
  let startMonth = month - 2;
  if (startMonth < 0) {
    startMonth += 12;
    startYear -= 1;
  }
  const startMonthVal = formatMonth(startYear, startMonth);

  // 초기 상태: 월간 배팅 모드
  startDateInput.type = "month";
  endDateInput.type = "month";
  startDateInput.value = startMonthVal;
  endDateInput.value = endMonthVal;

  // ✅ select 변경 이벤트
  select.addEventListener("change", () => {
    if (select.value === "월간 배팅") {
      startDateInput.type = "month";
      endDateInput.type = "month";
      startDateInput.value = startMonthVal;
      endDateInput.value = endMonthVal;
    } else {
      startDateInput.type = "date";
      endDateInput.type = "date";

      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
      const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);

      startDateInput.value = formatDate(firstDay);
      endDateInput.value = formatDate(lastDay);
    }
  });

  async function fetchStats(type) {
    const nickname = document.getElementById("nickname").value.trim();
    if (!nickname) return;

    resultsDiv.innerHTML = "<p>불러오는 중...</p>";

    const endpoint = type === "월간 배팅" ? "monthly_stats" : "daily_stats";
    let url = `https://ygosu-betting-calc.onrender.com/api/${endpoint}?nickname=${encodeURIComponent(nickname)}`;

    if (type === "일간 배팅") {
      url += `&startDate=${startDateInput.value}&endDate=${endDateInput.value}`;
    } else {
      const startYM = startDateInput.value;
      const endYM = endDateInput.value;
      const startDate = `${startYM}-01`;
      const endDate = getMonthEndDate(endYM);

      url += `&startDate=${startDate}&endDate=${endDate}`;
    }

    try {
      const response = await fetch(url);
      if (!response.ok) {
        resultsDiv.innerHTML = `<p>오류: ${response.status}</p>`;
        return;
      }

      const data = await response.json();
      if (data.error) {
        resultsDiv.innerHTML = `<p>${data.error}</p>`;
        return;
      }
      if (Object.keys(data).length === 0) {
        resultsDiv.innerHTML = `<p>기록이 없습니다.</p>`;
        return;
      }

      let html = "";
      for (const [nick, stats] of Object.entries(data)) {
        html += `<h3>${nick} (${type})</h3>`;
        if (stats.length === 0) {
          html += `<p>기록 없음</p>`;
        } else {
          html += "<table><thead><tr><th>날짜</th><th>총 배팅액</th><th>순수익</th><th>베팅수</th><th>승리</th><th>승률(%)</th></tr></thead><tbody>";
          stats.forEach((row) => {
            html += `<tr>
              <td>${row.stat_date || row.stat_month}</td>
              <td>${Number(row.total_amount).toLocaleString()}</td>
              <td>${Number(row.total_profit).toLocaleString()}</td>
              <td>${row.total_bets}</td>
              <td>${row.wins}</td>
              <td>${row.win_rate}</td>
            </tr>`;
          });
          html += "</tbody></table>";
        }
      }
      resultsDiv.innerHTML = html;
    } catch (err) {
      resultsDiv.innerHTML = `<p>요청 실패: ${err.message}</p>`;
    }
  }

  // ✅ 검색 버튼 이벤트
  searchBtn.addEventListener("click", (e) => {
    e.preventDefault();
    fetchStats(select.value);
  });
});
