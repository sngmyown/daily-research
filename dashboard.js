// ─── Market Intel Dashboard — dashboard.js ───
// 데이터는 data/market-data.json 파일에서 로드합니다.
// GitHub Actions가 매일 아침 이 파일을 자동으로 업데이트합니다.

const DATA_URL = './data/market-data.json';

// ─── 날짜 표시 ───
function setDateDisplay() {
  const now = new Date();
  const opts = { year: 'numeric', month: '2-digit', day: '2-digit',
                 weekday: 'short', hour: '2-digit', minute: '2-digit' };
  document.getElementById('date-display').textContent =
    now.toLocaleString('ko-KR', opts);
}
setDateDisplay();

// ─── 스파크라인 차트 ───
const sparkCharts = {};
function renderSparkline(id, dataArr, color) {
  const canvas = document.getElementById('spark-' + id);
  if (!canvas) return;
  if (sparkCharts[id]) sparkCharts[id].destroy();
  sparkCharts[id] = new Chart(canvas, {
    type: 'line',
    data: {
      labels: dataArr.map((_, i) => i),
      datasets: [{ data: dataArr, borderColor: color, borderWidth: 1.5,
                   fill: true,
                   backgroundColor: color.replace(')', ', 0.07)').replace('rgb', 'rgba'),
                   tension: 0.4, pointRadius: 0 }]
    },
    options: {
      responsive: false, animation: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      elements: { line: { borderCapStyle: 'round' } }
    }
  });
}

// ─── 지표 카드 렌더링 ───
function renderMetric(id, data) {
  const prev = data.prev_day;
  const curr = data.value;
  const diff = prev ? ((curr - prev) / Math.abs(prev) * 100) : 0;
  const direction = diff > 0.005 ? 'up' : diff < -0.005 ? 'down' : '';
  const sign = direction === 'up' ? '▲' : direction === 'down' ? '▼' : '–';
  const prefix = id === 'wti' || id === 'gold' ? '$' : '';

  document.getElementById('val-' + id).textContent = prefix + curr.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  document.getElementById('val-' + id).className = 'metric-value ' + direction;

  const deltaEl = document.getElementById('delta-' + id);
  deltaEl.innerHTML = `<span class="${direction}">${sign} ${Math.abs(diff).toFixed(2)}% 전일대비</span>`;

  if (data.note) document.getElementById('note-' + id).textContent = data.note;

  const sparkColor = direction === 'up' ? 'rgb(76,175,130)' : direction === 'down' ? 'rgb(224,90,58)' : 'rgb(136,136,128)';
  if (data.history) renderSparkline(id, data.history, sparkColor);
}

// ─── 비교 테이블 ───
function renderCompareTable(metrics) {
  const ids   = ['us10y', 'dxy', 'wti', 'gold'];
  const names = ['US 10Y', 'DXY', 'WTI', 'Gold'];
  const prefixes = ['', '', '$', '$'];
  const periods = ['prev_day', 'prev_week', 'prev_month', 'prev_year'];

  const tbody = document.getElementById('compare-tbody');
  tbody.innerHTML = ids.map((id, i) => {
    const d = metrics[id];
    if (!d) return '';
    const curr = d.value;
    const pref = prefixes[i];

    const cells = periods.map(p => {
      const ref = d[p];
      if (!ref) return '<td class="">—</td>';
      const pct = ((curr - ref) / Math.abs(ref) * 100);
      const cls = pct > 0.01 ? 'up' : pct < -0.01 ? 'down' : '';
      const sign = pct > 0.01 ? '▲' : pct < -0.01 ? '▼' : '–';
      return `<td class="${cls}">${sign} ${Math.abs(pct).toFixed(2)}%</td>`;
    }).join('');

    return `<tr>
      <td>${names[i]}</td>
      <td>${pref}${curr.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      ${cells}
    </tr>`;
  }).join('');
}

// ─── 경제 지표 ───
function renderEcon(items) {
  const grid = document.getElementById('econ-grid');
  if (!items || !items.length) {
    grid.innerHTML = '<div class="loading-cell">오늘 발표된 지표 없음</div>';
    return;
  }
  grid.innerHTML = items.map(item => `
    <div class="econ-item">
      <div class="econ-name">${item.name}</div>
      <div class="econ-val ${item.status}">${item.actual}</div>
      <div class="econ-meta">예측 ${item.forecast} &nbsp;·&nbsp; 이전 ${item.previous}</div>
      <span class="econ-badge ${item.status}">${
        item.status === 'beat'   ? 'BEAT' :
        item.status === 'miss'   ? 'MISS' :
        item.status === 'inline' ? 'IN LINE' : 'UPCOMING'
      }</span>
    </div>
  `).join('');
}

// ─── 뉴스 ───
function renderNews(items) {
  const container = document.getElementById('news-container');
  if (!items || !items.length) {
    container.innerHTML = '<div class="loading-cell">오늘의 뉴스 없음</div>';
    return;
  }
  const tagMap = { macro: '매크로', market: '시장', risk: '리스크', positive: '호재' };
  container.innerHTML = items.map(n => `
    <div class="news-card">
      <div class="news-top">
        <span class="news-tag ${n.tag}">${tagMap[n.tag] || n.tag}</span>
        <div class="news-title">${n.title}</div>
      </div>
      <div class="news-body">${n.body}</div>
      <div class="news-impact">
        <span class="impact-label">IMPACT</span>
        <span>${n.impact}</span>
      </div>
    </div>
  `).join('');
}

// ─── 메인 데이터 로드 ───
async function loadDashboard() {
  try {
    const res = await fetch(DATA_URL + '?t=' + Date.now());
    if (!res.ok) throw new Error('데이터 파일을 찾을 수 없습니다');
    const data = await res.json();

    // 지표 카드
    ['us10y', 'dxy', 'wti', 'gold'].forEach(id => {
      if (data.metrics && data.metrics[id]) renderMetric(id, data.metrics[id]);
    });

    // 비교 테이블
    if (data.metrics) renderCompareTable(data.metrics);

    // 경제 지표
    renderEcon(data.economic_announcements);

    // 뉴스
    renderNews(data.key_news);

    // 마지막 업데이트
    const lu = document.getElementById('last-updated');
    lu.textContent = '마지막 업데이트: ' + (data.updated_at || '알 수 없음');

  } catch (err) {
    console.error(err);
    // 데이터 파일이 아직 없을 때 샘플 데이터 표시
    loadSampleData();
  }
}

// ─── 샘플 데이터 (GitHub Actions 세팅 전 미리보기용) ───
function loadSampleData() {
  const sample = {
    metrics: {
      us10y: { value: 4.44, prev_day: 4.455, prev_week: 4.51, prev_month: 4.62, prev_year: 4.20,
               note: '2주 최저 / Gold에 유리',
               history: [4.58,4.54,4.51,4.56,4.53,4.62,4.59,4.55,4.51,4.48,4.455,4.44] },
      dxy:   { value: 98.94, prev_day: 98.96, prev_week: 97.80, prev_month: 98.56, prev_year: 99.26,
               note: '7주 고점 후 후퇴',
               history: [97.6,98.0,98.3,97.9,98.1,98.5,99.0,98.8,99.2,99.0,98.96,98.94] },
      wti:   { value: 87.59, prev_day: 88.90, prev_week: 95.20, prev_month: 105.80, prev_year: 60.80,
               note: '월간 -17% / 이란 협상 영향',
               history: [102,99.5,97,95,92,91.5,90,89.5,89.0,88.9,87.0,87.59] },
      gold:  { value: 4516, prev_day: 4495.83, prev_week: 4380, prev_month: 4700, prev_year: 3280,
               note: '52주 $3,248 ~ $5,595',
               history: [3280,3500,3800,4100,4300,4600,4800,5200,4900,4700,4496,4516] }
    },
    economic_announcements: [
      { name: 'Q1 GDP (2차 추정)', actual: '2.0%', forecast: '2.3%', previous: '0.5%', status: 'miss' },
      { name: 'PCE 물가 (4월, YoY)', actual: '3.8%', forecast: '3.8%', previous: '3.5%', status: 'inline' },
      { name: 'Core PCE (4월, YoY)', actual: '3.3%', forecast: '3.3%', previous: '3.2%', status: 'inline' },
      { name: '신규 실업수당 청구', actual: '209K', forecast: '215K', previous: '212K', status: 'beat' },
      { name: 'Fed 기준금리', actual: '3.50~3.75%', forecast: '동결', previous: '동결', status: 'inline' },
      { name: '12월 금리 인상 확률', actual: '~46%', forecast: '—', previous: '—', status: 'miss' }
    ],
    key_news: [
      {
        title: '미-이란, 60일 휴전 연장 잠정 합의 — 호르무즈 해협 개방 논의',
        body: '미국과 이란이 60일 휴전 연장과 호르무즈 해협 자유 통행을 포함한 MOU에 잠정 합의. 이란 30일 내 기뢰 제거 동의. 트럼프 최종 승인 미정.',
        tag: 'positive',
        impact: 'WTI 이달 -12% 원인. 협상 타결 시 유가 추가 하락 → 인플레 완화 → 금 채권 강세 예상.'
      },
      {
        title: 'PCE 예측 부합 · GDP 2차 추정 예측 하회 — Fed 동결 재확인',
        body: '4월 PCE 3.8% YoY, Core PCE 3.3%로 모두 예측 부합. Q1 GDP 2차 추정 2.0%로 예측 2.3% 하회. 연말까지 금리 동결 전망.',
        tag: 'macro',
        impact: 'US10Y 하락 압력. 달러 약세 요인. 단, 12월 인상 확률 46%는 여전히 주시 필요.'
      },
      {
        title: 'SpaceX IPO 로드쇼 6월 4일 — $1.75조 밸류에이션',
        body: 'SpaceX S-1 제출 완료. 로드쇼 6/4 출발, 나스닥 SPCX 상장 6/12 목표. 약 $750억 조달 예정.',
        tag: 'market',
        impact: '대형 IPO 자금 이동으로 단기 시장 유동성 흡수 가능. 기술주 변동성 확대.'
      }
    ],
    updated_at: new Date().toLocaleString('ko-KR')
  };

  ['us10y', 'dxy', 'wti', 'gold'].forEach(id => renderMetric(id, sample.metrics[id]));
  renderCompareTable(sample.metrics);
  renderEcon(sample.economic_announcements);
  renderNews(sample.key_news);
  document.getElementById('last-updated').textContent =
    '샘플 데이터 표시 중 — GitHub Actions 설정 후 자동 업데이트됩니다';
}

// ─── 초기화 ───
loadDashboard();
