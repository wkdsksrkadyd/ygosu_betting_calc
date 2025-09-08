// static/js/script.js
document.addEventListener("DOMContentLoaded", () => {
  const startDateInput = document.getElementById("startDate");
  const endDateInput   = document.getElementById("endDate");
  const select         = document.querySelector("select[name=select]");
  const searchBtn      = document.getElementById("searchBtn");
  const resultsDiv     = document.getElementById("results");
  const form           = document.getElementById("searchForm");

  const today = new Date();

  // Utils
  const fmtMonth = (y, mIdx) => `${y}-${String(mIdx + 1).padStart(2, "0")}`;
  const fmtDate  = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const monthEnd = (ym) => {
    const [y, m] = ym.split("-").map(Number);
    const last   = new Date(y, m, 0).getDate();
    return `${ym}-${String(last).padStart(2, "0")}`;
  };
  const nfmt = (v) => Number(v || 0).toLocaleString();
  const pfmt = (v) => {
    const num = Number(v);
    if (Number.isFinite(num)) return `${num.toFixed(2)}%`;
    return "-";
  };

  // 초기 기본값: 월간 배팅(최근 3개월)
  const curY = today.getFullYear();
  const curM = today.getMonth(); // 0~11
  const endMonthVal = fmtMonth(curY, curM);
  let sY = curY, sM = curM - 2;
  if (sM < 0) { sM += 12; sY -= 1; }
  const startMonthVal = fmtMonth(sY, sM);

  startDateInput.type  = "month";
  endDateInput.type    = "month";
  startDateInput.value = startMonthVal;
  endDateInput.value   = endMonthVal;

  // 모드 변경
  select.addEventListener("change", () => {
    if (select.value === "월간 배팅") {
      startDateInput.type  = "month";
      endDateInput.type    = "month";
      startDateInput.value = startMonthVal;
      endDateInput.value   = endMonthVal;
    } else {
      startDateInput.type = "date";
      endDateInput.type   = "date";
      const first = new Date(today.getFullYear(), today.getMonth(), 1);
      const last  = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      startDateInput.value = fmtDate(first);
      endDateInput.value   = fmtDate(last);
    }
  });

  async function fetchStats(type) {
    const nicknameEl = document.getElementById("nickname");
    const nickname = nicknameEl ? nicknameEl.value.trim() : "";
    if (!nickname) return;

    resultsDiv.innerHTML = "<p>불러오는 중...</p>";

    const isMonthly = type === "월간 배팅";
    const endpoint  = isMonthly ? "/api/monthly_stats" : "/api/daily_stats";

    const params = new URLSearchParams();
    params.set("nickname", nickname);

    // index.html은 전체(파라미터 없음), 폴더별 페이지는 window.BOARD_SLUG로 고정
    if (typeof window !== "undefined" && window.BOARD_SLUG) {
      params.set("boardSlug", window.BOARD_SLUG);
    }

    if (isMonthly) {
      const startYM = startDateInput.value; // YYYY-MM
      const endYM   = endDateInput.value;   // YYYY-MM
      if (startYM) params.set("startMonth", startYM);
      if (endYM)   params.set("endMonth",   endYM);
    } else {
      if (startDateInput.value) params.set("startDate", startDateInput.value); // YYYY-MM-DD
      if (endDateInput.value)   params.set("endDate",   endDateInput.value);   // YYYY-MM-DD
    }

    try {
      const res = await fetch(`${endpoint}?${params.toString()}`, {
        headers: { "Accept": "application/json" }
      });
      if (!res.ok) {
        resultsDiv.innerHTML = `<p>오류: ${res.status} ${res.statusText}</p>`;
        return;
      }
      const data = await res.json();
      if (!data || data.error) {
        resultsDiv.innerHTML = `<p>${data?.error || "결과가 없습니다."}</p>`;
        return;
      }
      if (Object.keys(data).length === 0) {
        resultsDiv.innerHTML = `<p>기록이 없습니다.</p>`;
        return;
      }

      let html = "";
      for (const [nick, stats] of Object.entries(data)) {
        html += `<h3>${nick} (${type})</h3>`;
        if (!Array.isArray(stats) || stats.length === 0) {
          html += `<p>기록 없음</p>`;
          continue;
        }
        html += `<table>
          <thead>
            <tr>
              <th>${isMonthly ? "월" : "날짜"}</th>
              <th>총 배팅액</th>
              <th>순이익</th>
              <th>베팅수</th>
              <th>승리</th>
              <th>승률(%)</th>
            </tr>
          </thead>
          <tbody>`;

        stats.forEach((row) => {
          const key = row.stat_month || row.stat_date || "-";
          html += `<tr>
            <td>${key}</td>
            <td>${nfmt(row.total_amount)}</td>
            <td>${nfmt(row.total_profit)}</td>
            <td>${nfmt(row.total_bets)}</td>
            <td>${nfmt(row.wins)}</td>
            <td>${pfmt(row.win_rate)}</td>
          </tr>`;
        });

        html += `</tbody></table>`;
      }
      resultsDiv.innerHTML = html;
    } catch (err) {
      resultsDiv.innerHTML = `<p>요청 실패: ${err?.message || err}</p>`;
    }
  }

  // 검색 버튼 클릭
  if (searchBtn) {
    searchBtn.addEventListener("click", (e) => {
      e.preventDefault();
      fetchStats(select.value);
    });
  }

  // 엔터 제출 지원
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      fetchStats(select.value);
    });
  }
});
