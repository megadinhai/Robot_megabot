/* ===== ENGLISH TUTOR PARENT REPORT V1 ===== */
(() => {
  'use strict';

  const REPORT_API = '/api/english-tutor/report';

  /*
   * Danh sách những ID thường dùng cho ô chọn thiết bị.
   * Code sẽ tự tìm ô nào đang tồn tại trên trang.
   */
  const DEVICE_SELECTORS = [
    '#deviceSelect',
    '#agentSelect',
    '#tutorDeviceSelect',
    '#englishTutorDeviceSelect',
    'select[name="agent_id"]',
    'select[name="device_id"]'
  ];

  function byId(id) {
    return document.getElementById(id);
  }

  function toNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function asArray(value) {
    if (Array.isArray(value)) {
      return value
        .map((item) => String(item).trim())
        .filter(Boolean);
    }

    if (typeof value === 'string') {
      return value
        .split(/[,;\n]/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    return [];
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function formatDateTime(value) {
    if (!value) {
      return 'Không rõ thời gian';
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }

  function resolveDeviceId() {
    for (const selector of DEVICE_SELECTORS) {
      const element = document.querySelector(selector);

      if (element && element.value) {
        return String(element.value).trim();
      }
    }

    /*
     * state.deviceId thuộc file english-tutor.js hiện có.
     * Chỉ dùng làm phương án dự phòng khi ô select chưa kịp cập nhật.
     */
    try {
      if (
        typeof state !== 'undefined' &&
        state &&
        state.deviceId
      ) {
        return String(state.deviceId).trim();
      }
    } catch (_error) {
      // Không làm gián đoạn báo cáo nếu state chưa sẵn sàng.
    }

    return String(
      localStorage.getItem('englishTutorDeviceId') || ''
    ).trim();
  }

  function extractTokenValue(value) {
    const trimmed = String(value || '').trim();

    if (!trimmed) {
      return '';
    }

    try {
      const parsed = JSON.parse(trimmed);

      if (typeof parsed === 'string') {
        return parsed;
      }

      return (
        parsed.token ||
        parsed.access_token ||
        parsed.accessToken ||
        parsed.auth_token ||
        parsed.authToken ||
        parsed.jwt ||
        ''
      );
    } catch (_error) {
      return trimmed;
    }
  }

  function readTokenFromLocalStorage() {
    const preferredKeys = [
      'token',
      'access_token',
      'accessToken',
      'auth_token',
      'authToken',
      'jwt'
    ];

    for (const key of preferredKeys) {
      const value = localStorage.getItem(key);

      if (value) {
        const token = extractTokenValue(value);

        if (token) {
          return token;
        }
      }
    }

    /*
     * Nếu tên key không nằm trong danh sách trên,
     * tiếp tục tìm mọi key có chữ token hoặc jwt.
     */
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);

      if (!key || !/(token|jwt)/i.test(key)) {
        continue;
      }

      const value = localStorage.getItem(key);

      if (value) {
        const token = extractTokenValue(value);

        if (token) {
          return token;
        }
      }
    }

    return '';
  }

  async function requestReport(url) {
    const token = readTokenFromLocalStorage();

    const headers = {
      Accept: 'application/json'
    };

    if (token) {
      headers.Authorization = /^Bearer\s+/i.test(token)
        ? token
        : `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');

      throw new Error(
        `API trả về lỗi ${response.status}: ` +
        `${errorText || response.statusText}`
      );
    }

    return response.json();
  }

  function normalizeReport(payload) {
    /*
     * Hỗ trợ cả:
     * { profile, stats, sessions }
     *
     * và:
     * { success: true, data: { profile, stats, sessions } }
     */
    const root =
      payload &&
      payload.data &&
      typeof payload.data === 'object'
        ? payload.data
        : payload || {};

    const profile =
      root.profile ||
      root.student_profile ||
      root.studentProfile ||
      {};

    const stats =
      root.stats ||
      root.statistics ||
      {};

    let sessions = [];

    if (Array.isArray(root.sessions)) {
      sessions = root.sessions;
    } else if (Array.isArray(root.history)) {
      sessions = root.history;
    } else if (Array.isArray(root.learning_sessions)) {
      sessions = root.learning_sessions;
    }

    const sortedSessions = [...sessions].sort((a, b) => {
      const timeA = new Date(
        a.created_at ||
        a.completed_at ||
        a.started_at ||
        0
      ).getTime();

      const timeB = new Date(
        b.created_at ||
        b.completed_at ||
        b.started_at ||
        0
      ).getTime();

      return timeB - timeA;
    });

    const knownWords = asArray(
      profile.known_words ||
      root.known_words
    );

    const knownPhrases = asArray(
      profile.known_phrases ||
      root.known_phrases
    );

    const weakWords = asArray(
      profile.weak_words ||
      root.weak_words
    );

    const weakPhrases = asArray(
      profile.weak_phrases ||
      root.weak_phrases
    );

    const calculatedMinutes = sortedSessions.reduce(
      (total, session) => {
        const seconds = toNumber(session.duration_seconds, 0);
        const minutes = toNumber(session.duration_minutes, 0);

        if (seconds > 0) {
          return total + seconds / 60;
        }

        return total + minutes;
      },
      0
    );

    const validScores = sortedSessions
      .map((session) => toNumber(session.score, NaN))
      .filter(Number.isFinite);

    const calculatedAverage = validScores.length
      ? validScores.reduce((total, score) => total + score, 0) /
        validScores.length
      : 0;

    return {
      profile,
      stats,
      sessions: sortedSessions,
      knownWords,
      knownPhrases,
      weakWords,
      weakPhrases,

      totalSessions: toNumber(
        stats.total_sessions ??
        stats.totalSessions ??
        profile.total_sessions ??
        profile.totalSessions,
        sortedSessions.length
      ),

      totalMinutes: toNumber(
        stats.total_minutes ??
        stats.totalMinutes ??
        profile.total_minutes ??
        profile.totalMinutes,
        Math.round(calculatedMinutes)
      ),

      averageScore: toNumber(
        stats.average_score ??
        stats.averageScore ??
        stats.avg_score ??
        stats.avgScore,
        calculatedAverage
      ),

      streakDays: toNumber(
        stats.streak_days ??
        stats.streakDays ??
        profile.streak_days ??
        profile.streakDays,
        0
      )
    };
  }

  /*
   * Hỗ trợ cả thang điểm 10 và thang điểm 100.
   */
  function scoreOutOfTen(value) {
    const score = toNumber(value, 0);

    if (score > 10) {
      return Math.min(10, score / 10);
    }

    return Math.max(0, Math.min(10, score));
  }

  function getSessionMinutes(session) {
    const seconds = toNumber(session.duration_seconds, 0);

    if (seconds > 0) {
      return Math.max(1, Math.round(seconds / 60));
    }

    return Math.max(
      0,
      Math.round(toNumber(session.duration_minutes, 0))
    );
  }

  function renderOverview(report) {
    byId('parent-report-total-sessions').textContent =
      String(report.totalSessions);

    byId('parent-report-total-minutes').textContent =
      String(Math.round(report.totalMinutes));

    byId('parent-report-average-score').textContent =
      report.averageScore
        ? `${scoreOutOfTen(report.averageScore).toFixed(1)}/10`
        : 'Chưa có';

    byId('parent-report-streak').textContent =
      `${report.streakDays} ngày`;

    byId('parent-report-known-count').textContent =
      String(
        report.knownWords.length +
        report.knownPhrases.length
      );

    byId('parent-report-weak-count').textContent =
      String(
        report.weakWords.length +
        report.weakPhrases.length
      );
  }

  function renderScoreChart(sessions) {
    const container = byId('parent-report-score-chart');

    /*
     * Lấy tối đa 10 buổi gần nhất.
     * reverse để buổi cũ nằm bên trên, buổi mới nằm dưới.
     */
    const recentSessions = sessions.slice(0, 10).reverse();

    if (!recentSessions.length) {
      container.innerHTML =
        '<div class="parent-report-empty">' +
        'Chưa có dữ liệu điểm.' +
        '</div>';

      return;
    }

    container.innerHTML = recentSessions
      .map((session, index) => {
        const score = scoreOutOfTen(session.score);

        const title =
          session.lesson_title ||
          session.topic ||
          `Buổi ${index + 1}`;

        return `
          <div
            class="parent-report-bar-row"
            title="${escapeHtml(title)}: ${score.toFixed(1)}/10"
          >
            <div class="parent-report-bar-label">
              ${index + 1}
            </div>

            <div class="parent-report-bar-track">
              <div
                class="parent-report-bar-fill"
                style="width:${score * 10}%"
              ></div>
            </div>

            <div class="parent-report-bar-value">
              ${score.toFixed(1)}
            </div>
          </div>
        `;
      })
      .join('');
  }

  function renderTimeChart(sessions) {
    const container = byId('parent-report-time-chart');
    const recentSessions = sessions.slice(0, 10).reverse();

    if (!recentSessions.length) {
      container.innerHTML =
        '<div class="parent-report-empty">' +
        'Chưa có dữ liệu thời gian học.' +
        '</div>';

      return;
    }

    const minuteValues = recentSessions.map(getSessionMinutes);
    const maximumMinutes = Math.max(...minuteValues, 1);

    container.innerHTML = recentSessions
      .map((session, index) => {
        const minutes = minuteValues[index];

        const barWidth = Math.max(
          4,
          Math.round((minutes / maximumMinutes) * 100)
        );

        const title =
          session.lesson_title ||
          session.topic ||
          `Buổi ${index + 1}`;

        return `
          <div
            class="parent-report-bar-row"
            title="${escapeHtml(title)}: ${minutes} phút"
          >
            <div class="parent-report-bar-label">
              ${index + 1}
            </div>

            <div class="parent-report-bar-track">
              <div
                class="parent-report-bar-fill parent-report-time-fill"
                style="width:${barWidth}%"
              ></div>
            </div>

            <div class="parent-report-bar-value">
              ${minutes}p
            </div>
          </div>
        `;
      })
      .join('');
  }

  function renderWeakItems(report) {
    const container = byId('parent-report-weak-items');

    const weakItems = [
      ...report.weakWords.map((text) => ({
        type: 'Từ',
        text
      })),

      ...report.weakPhrases.map((text) => ({
        type: 'Câu',
        text
      }))
    ];

    if (!weakItems.length) {
      container.innerHTML =
        '<div class="parent-report-empty">' +
        'Hiện chưa có từ hoặc câu cần ôn.' +
        '</div>';

      return;
    }

    container.innerHTML = weakItems
      .slice(0, 30)
      .map((item) => `
        <div class="parent-report-chip">
          <span>${escapeHtml(item.type)}</span>
          ${escapeHtml(item.text)}
        </div>
      `)
      .join('');
  }

  function renderHistory(sessions) {
    const tableBody = byId('parent-report-history-body');

    if (!sessions.length) {
      tableBody.innerHTML = `
        <tr>
          <td
            colspan="5"
            class="parent-report-empty"
          >
            Chưa có lịch sử buổi học.
          </td>
        </tr>
      `;

      return;
    }

    tableBody.innerHTML = sessions
      .slice(0, 20)
      .map((session) => {
        const hasScore =
          session.score !== null &&
          session.score !== undefined &&
          Number.isFinite(Number(session.score));

        const displayedScore = hasScore
          ? `${scoreOutOfTen(session.score).toFixed(1)}/10`
          : '—';

        const title =
          session.lesson_title ||
          session.topic ||
          'Bài học tiếng Anh';

        const mode =
          session.mode ||
          'lesson';

        const minutes =
          getSessionMinutes(session);

        const summary =
          session.summary ||
          session.status ||
          '';

        const sessionTime =
          session.created_at ||
          session.completed_at ||
          session.started_at;

        return `
          <tr>
            <td>
              ${escapeHtml(formatDateTime(sessionTime))}
            </td>

            <td>
              <strong>${escapeHtml(title)}</strong>

              ${
                summary
                  ? `<small>${escapeHtml(summary)}</small>`
                  : ''
              }
            </td>

            <td>${escapeHtml(mode)}</td>

            <td>${escapeHtml(displayedScore)}</td>

            <td>${minutes} phút</td>
          </tr>
        `;
      })
      .join('');
  }

  function calculateAverageScore(sessions) {
    const scores = sessions
      .map((session) => scoreOutOfTen(session.score))
      .filter((score) => score > 0);

    if (!scores.length) {
      return 0;
    }

    return (
      scores.reduce((total, score) => total + score, 0) /
      scores.length
    );
  }

  function buildParentComment(report) {
    if (!report.sessions.length) {
      return (
        'Chưa có đủ dữ liệu để nhận xét. ' +
        'Hãy hoàn thành ít nhất một buổi học để hệ thống ' +
        'bắt đầu theo dõi tiến bộ.'
      );
    }

    const comments = [];

    const averageScore =
      scoreOutOfTen(report.averageScore);

    const weakCount =
      report.weakWords.length +
      report.weakPhrases.length;

    const knownCount =
      report.knownWords.length +
      report.knownPhrases.length;

    if (averageScore >= 8) {
      comments.push(
        'Kết quả học tập hiện tại tốt và khá ổn định.'
      );
    } else if (averageScore >= 6.5) {
      comments.push(
        'Kết quả học tập đang ở mức khá và còn khả năng cải thiện rõ rệt.'
      );
    } else if (averageScore > 0) {
      comments.push(
        'Học viên cần thêm các buổi ôn ngắn để củng cố kiến thức nền.'
      );
    }

    if (report.streakDays >= 3) {
      comments.push(
        `Học viên đang duy trì chuỗi ` +
        `${report.streakDays} ngày học liên tiếp.`
      );
    } else {
      comments.push(
        'Nên duy trì lịch học đều đặn mỗi ngày từ 10 đến 15 phút.'
      );
    }

    if (knownCount > 0) {
      comments.push(
        `Hệ thống đã ghi nhận ${knownCount} ` +
        'từ hoặc câu học viên đã nắm được.'
      );
    }

    if (weakCount > 0) {
      comments.push(
        `Hiện còn ${weakCount} từ hoặc câu cần ôn; ` +
        'nên dùng chức năng Ôn nhanh trong buổi tiếp theo.'
      );
    } else {
      comments.push(
        'Hiện chưa có nội dung yếu cần ôn riêng.'
      );
    }

    const latestThreeAverage =
      calculateAverageScore(report.sessions.slice(0, 3));

    const previousThreeAverage =
      calculateAverageScore(report.sessions.slice(3, 6));

    if (latestThreeAverage && previousThreeAverage) {
      if (
        latestThreeAverage >=
        previousThreeAverage + 0.5
      ) {
        comments.push(
          'Điểm của ba buổi gần nhất đang có xu hướng tăng.'
        );
      } else if (
        latestThreeAverage + 0.5 <
        previousThreeAverage
      ) {
        comments.push(
          'Điểm gần đây có dấu hiệu giảm nhẹ; ' +
          'nên ưu tiên ôn lại các mục yếu trước khi học bài mới.'
        );
      } else {
        comments.push(
          'Kết quả các buổi gần đây tương đối ổn định.'
        );
      }
    }

    return comments.join(' ');
  }

  function setLoading(isLoading, message = '') {
    const statusElement =
      byId('parent-report-status');

    const refreshButton =
      byId('parent-report-refresh');

    if (refreshButton) {
      refreshButton.disabled = isLoading;
    }

    if (statusElement) {
      statusElement.textContent = message;
      statusElement.classList.remove('is-error');
    }
  }

  function showError(error) {
    const statusElement =
      byId('parent-report-status');

    if (statusElement) {
      statusElement.textContent =
        `Không tải được báo cáo: ${error.message}`;

      statusElement.classList.add('is-error');
    }

    console.error(
      '[English Tutor Parent Report]',
      error
    );
  }

  async function loadParentReport() {
    if (!byId('parent-report-section')) {
      return;
    }

    setLoading(true, 'Đang tải báo cáo...');

    try {
      const deviceId = resolveDeviceId();

      if (!deviceId) {
        setLoading(
          false,
          'Đang chờ danh sách thiết bị được tải...'
        );
        return;
      }

      const queryString =
        `?deviceId=${encodeURIComponent(deviceId)}`;

      const payload = await requestReport(
        `${REPORT_API}${queryString}`
      );

      const report = normalizeReport(payload);

      renderOverview(report);
      renderScoreChart(report.sessions);
      renderTimeChart(report.sessions);
      renderWeakItems(report);
      renderHistory(report.sessions);

      byId('parent-report-comment').textContent =
        buildParentComment(report);

      const updatedTime =
        new Intl.DateTimeFormat('vi-VN', {
          hour: '2-digit',
          minute: '2-digit'
        }).format(new Date());

      setLoading(
        false,
        `Đã cập nhật lúc ${updatedTime}`
      );
    } catch (error) {
      setLoading(false, '');
      showError(error);
    }
  }

  function bindEvents() {
    const refreshButton =
      byId('parent-report-refresh');

    if (refreshButton) {
      refreshButton.addEventListener(
        'click',
        loadParentReport
      );
    }

    for (const selector of DEVICE_SELECTORS) {
      const element =
        document.querySelector(selector);

      if (element) {
        element.addEventListener(
          'change',
          loadParentReport
        );
      }
    }
  }

  function waitForDeviceAndLoad(attempt = 0) {
    if (!byId('parent-report-section')) {
      return;
    }

    if (resolveDeviceId()) {
      loadParentReport();
      return;
    }

    if (attempt >= 40) {
      setLoading(
        false,
        'Chưa tìm thấy thiết bị. Hãy chọn lại thiết bị ở thanh trên.'
      );
      return;
    }

    setLoading(
      false,
      'Đang chờ danh sách thiết bị được tải...'
    );

    window.setTimeout(() => {
      waitForDeviceAndLoad(attempt + 1);
    }, 250);
  }

  function initializeParentReport() {
    if (!byId('parent-report-section')) {
      return;
    }

    bindEvents();
    waitForDeviceAndLoad();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initializeParentReport,
      { once: true }
    );
  } else {
    initializeParentReport();
  }

  /*
   * Cho phép gọi lại từ Console hoặc từ code Tutor hiện có.
   */
  window.loadEnglishTutorParentReport =
    loadParentReport;
})();
/* ===== END ENGLISH TUTOR PARENT REPORT V1 ===== */
