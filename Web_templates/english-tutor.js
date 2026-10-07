"use strict";

const state = {
    token: "",
    user: null,
    devices: [],
    deviceId: "",
    report: null,
    active: null,
    lessonTemplates: [],
    roleplayTemplates: [],
    libraryMode: "lesson",
    selectedTemplateId: null,
    recommendation: null,
    sessionPage: 1,
    sessionPageSize: 3,
    roadmapOpenChapterId: "",
    toastTimer: null,
    confirmResolver: null
};

const ENGLISH_TOPICS_BY_LEVEL = {
    starter: [
        ["Greeting", "Greeting - Chào hỏi"],
        ["Colors", "Colors - Màu sắc"],
        ["Numbers", "Numbers - Số đếm"],
        ["Animals", "Animals - Con vật"],
        ["Food", "Food - Đồ ăn"],
        ["Family", "Family - Gia đình"],
        ["Toys", "Toys - Đồ chơi"],
        ["Feelings", "Feelings - Cảm xúc"]
    ],
    a1: [
        ["Greeting", "Greeting - Chào hỏi nâng cao"],
        ["School", "School - Trường học"],
        ["Daily Routine", "Daily Routine - Sinh hoạt hằng ngày"],
        ["Shopping", "Shopping - Mua sắm"],
        ["Weather", "Weather - Thời tiết"],
        ["Body", "Body - Cơ thể"],
        ["Playground", "Playground - Sân chơi"],
        ["Health", "Health - Sức khỏe đơn giản"]
    ],
    a2: [
        ["Daily Routine", "Daily Routine - Kể về một ngày"],
        ["Hobbies", "Hobbies - Sở thích"],
        ["Travel", "Travel - Đi lại / du lịch"],
        ["Shopping", "Shopping - Mua sắm nâng cao"],
        ["School", "School - Hoạt động ở trường"],
        ["Food", "Food - Gọi món / sở thích ăn uống"],
        ["Transportation", "Transportation - Phương tiện"],
        ["Storytelling", "Storytelling - Kể chuyện ngắn"]
    ],
    b1: [
        ["Opinion", "Opinion - Nêu ý kiến"],
        ["Hobbies", "Hobbies - Nói về sở thích"],
        ["Travel", "Travel - Du lịch"],
        ["Problem Solving", "Problem Solving - Giải quyết vấn đề"],
        ["Storytelling", "Storytelling - Kể chuyện"],
        ["Environment", "Environment - Môi trường"],
        ["Technology", "Technology - Công nghệ"],
        ["Future Plans", "Future Plans - Kế hoạch tương lai"]
    ],
    b2: [
        ["Debate", "Debate - Tranh luận nhẹ"],
        ["Opinion", "Opinion - Trình bày quan điểm"],
        ["Presentation", "Presentation - Thuyết trình ngắn"],
        ["Problem Solving", "Problem Solving - Xử lý tình huống"],
        ["Technology", "Technology - Công nghệ"],
        ["Media", "Media - Truyền thông"],
        ["Culture", "Culture - Văn hóa"],
        ["Study Skills", "Study Skills - Kỹ năng học tập"]
    ]
};

document.addEventListener("DOMContentLoaded", initializeEnglishTutorPage);

async function initializeEnglishTutorPage() {
    state.token = localStorage.getItem("token") || "";

    if (!state.token) {
        redirectToLogin();
        return;
    }

    try {
        state.user = decodeJwtPayload(state.token);
        document.getElementById("currentUsername").textContent = state.user?.username || "Người dùng";
        renderTopicOptions();
        await loadDevices();

        if (!state.deviceId) {
            throw new Error("Tài khoản chưa có thiết bị được liên kết.");
        }

        document.getElementById("app").hidden = false;
        document.getElementById("pageLoading").hidden = true;
        await refreshAllData();
    } catch (error) {
        document.getElementById("pageLoading").innerHTML = `
            <div style="max-width:560px;padding:22px;text-align:center;line-height:1.6;">
                <div style="font-size:46px;margin-bottom:12px;">⚠️</div>
                <strong style="color:white;font-size:18px;">Không mở được trang Gia sư tiếng Anh</strong>
                <div style="margin-top:10px;">${escapeHTML(error.message || "Lỗi không xác định")}</div>
                <button style="margin-top:18px;min-height:44px;padding:0 16px;border:0;border-radius:10px;background:#2563eb;color:white;font-weight:700;" onclick="goBackToDashboard()">Quay về Trung tâm GMBOT</button>
            </div>
        `;
    }
}

function decodeJwtPayload(token) {
    try {
        const part = token.split(".")[1];
        if (!part) return null;
        const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
        const decoded = decodeURIComponent(
            atob(normalized)
                .split("")
                .map(char => `%${("00" + char.charCodeAt(0).toString(16)).slice(-2)}`)
                .join("")
        );
        return JSON.parse(decoded);
    } catch {
        return null;
    }
}

function redirectToLogin() {
    localStorage.removeItem("token");
    window.location.href = "/";
}

function goBackToDashboard() {
    window.location.href = "/";
}

async function apiFetch(url, options = {}) {
    const headers = {
        ...(options.headers || {}),
        Authorization: `Bearer ${state.token}`
    };

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
        redirectToLogin();
        throw new Error("Phiên đăng nhập đã hết hạn.");
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.error || `Máy chủ trả về lỗi ${response.status}`);
    }

    return data;
}

async function loadDevices() {
    const devices = await apiFetch("/api/devices");

    if (!Array.isArray(devices) || devices.length === 0) {
        throw new Error("Tài khoản chưa có thiết bị. Hãy quay về trang chính để liên kết thiết bị trước.");
    }

    state.devices = devices.filter(device => device && device.id);

    if (state.devices.length === 0) {
        throw new Error("Không tìm thấy thiết bị có agentId hợp lệ.");
    }

    const savedDeviceId = localStorage.getItem("englishTutorDeviceId") || "";
    const savedDevice = state.devices.find(device => device.id === savedDeviceId);
    state.deviceId = savedDevice ? savedDevice.id : state.devices[0].id;

    const select = document.getElementById("deviceSelect");
    select.innerHTML = state.devices.map(device => `
        <option value="${escapeHTML(device.id)}">${escapeHTML(device.name || device.id)}</option>
    `).join("");
    select.value = state.deviceId;

    if (state.devices.length === 1) {
        select.disabled = true;
    }
}

async function onDeviceChange() {
    const select = document.getElementById("deviceSelect");
    state.deviceId = select.value;
    localStorage.setItem("englishTutorDeviceId", state.deviceId);
    state.selectedTemplateId = null;
    state.sessionPage = 1;
    state.roadmapOpenChapterId = "";
    await refreshAllData();
}

async function refreshAllData() {
    if (!state.deviceId) return;

    showToast("Đang tải dữ liệu học tiếng Anh...", "info");

    try {
        await Promise.all([
            loadEnglishReport(false),
            loadActiveLesson(),
            loadTemplateLibrary(),
            loadRecommendation()
        ]);

        buildRecommendation();
        renderDashboard();
        renderTemplateLibrary();
        renderStarterRoadmap();
        showToast("Đã tải dữ liệu mới nhất.", "success");
    } catch (error) {
        showToast(error.message || "Không tải được dữ liệu.", "error");
    }
}

async function loadEnglishReport(showSuccessMessage = false) {
    if (!state.deviceId) return;
    state.report = await apiFetch(`/api/english-tutor/report?deviceId=${encodeURIComponent(state.deviceId)}`);
    state.sessionPage = 1;
    renderReport();
    renderDashboard();
    renderStarterRoadmap();

    if (showSuccessMessage) {
        showToast("Đã tải báo cáo học tập mới nhất.", "success");
    }
}

async function loadActiveLesson() {
    if (!state.deviceId) return;
    state.active = await apiFetch(`/api/english-tutor/active?deviceId=${encodeURIComponent(state.deviceId)}`);
    renderActiveLesson();
    renderStarterRoadmap();
}

async function loadRecommendation() {
    if (!state.deviceId) return;
    state.recommendation = await apiFetch(
        `/api/english-tutor/recommendation?deviceId=${encodeURIComponent(state.deviceId)}`
    );
}

async function loadTemplateLibrary() {
    const [lessonResult, roleplayResult] = await Promise.all([
        apiFetch("/api/english-tutor/templates?mode=lesson"),
        apiFetch("/api/english-tutor/templates?mode=roleplay")
    ]);

    state.lessonTemplates = Array.isArray(lessonResult.templates) ? lessonResult.templates : [];
    state.roleplayTemplates = Array.isArray(roleplayResult.templates) ? roleplayResult.templates : [];
}

function showEnglishSection(section, clickedElement = null) {
    document.querySelectorAll(".page-section").forEach(item => item.classList.remove("active"));
    const target = document.getElementById(`section-${section}`);
    if (target) target.classList.add("active");

    document.querySelectorAll(".nav-item[data-section], .mobile-nav-item[data-section]").forEach(item => {
        item.classList.toggle("active", item.dataset.section === section);
    });

    if (section === "report") {
        renderReport();
    }

    if (section === "library") {
        renderTemplateLibrary();
    }

    if (section === "roadmap") {
        renderStarterRoadmap();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

function buildRecommendation() {
    const type = String(state.recommendation?.type || "empty").toLowerCase();
    const heroSpeech = document.getElementById("heroSpeech");

    if (!heroSpeech) return;

    if (type === "active") {
        heroSpeech.textContent = "Let's continue your lesson!";
        return;
    }

    if (type === "review") {
        heroSpeech.textContent = "Let's review and get stronger!";
        return;
    }

    if (type === "template") {
        heroSpeech.textContent = "Ready to learn something new?";
        return;
    }

    heroSpeech.textContent = "Ready to learn English?";
}

function renderDashboard() {
    const profile = state.report?.profile || {};
    const stats = state.report?.stats || {};
    const sessions = state.report?.sessions || [];
    const username = state.user?.username || "bạn";
    const level = normalizeLevel(profile.level || sessions[0]?.level || "starter");
    const weakWords = ensureArray(profile.weak_words);
    const weakPhrases = ensureArray(profile.weak_phrases);

    const hasWeakItems =
    weakWords.length > 0 ||
    weakPhrases.length > 0;

const quickReviewButton =
    document.getElementById("quickReviewButton");

if (quickReviewButton) {
    quickReviewButton.disabled = !hasWeakItems;

    if (hasWeakItems) {
        quickReviewButton.textContent = "⚡ Ôn nhanh 5 phút";
        quickReviewButton.title =
            "Tạo bài ôn từ các từ và câu bé còn yếu.";
    } else {
        quickReviewButton.textContent =
            "✓ Chưa có nội dung cần ôn";

        quickReviewButton.title =
            "Bé hiện chưa có từ hoặc câu yếu cần ôn.";
    }
}
    const totalMinutes = Number(profile.total_minutes || Math.ceil(Number(stats.total_seconds || 0) / 60) || 0);
    const totalSessions = Number(profile.total_sessions || stats.total_sessions || 0);
    const completedSessions = Number(stats.completed_sessions || 0);
    const overallProgress = Math.min(100, Math.round((completedSessions / Math.max(totalSessions, 1)) * 100));

    document.getElementById("welcomeTitle").textContent = `Xin chào ${username} 👋`;
    document.getElementById("welcomeSubtitle").textContent = `Trình độ hiện tại: ${level.toUpperCase()}. Hãy dành một buổi học ngắn để duy trì thói quen mỗi ngày. Sau khi học xong hãy nói "học xong rồi" để hệ thống đánh giá và lưu lại báo cáo học tập.`;
    document.getElementById("statStreak").textContent = Number(profile.streak_days || 0);
    document.getElementById("statSessions").textContent = totalSessions;
    document.getElementById("statMinutes").textContent = totalMinutes;
    document.getElementById("statAverage").textContent = Number(stats.avg_score || 0);
    document.getElementById("overallProgressLabel").textContent = `${overallProgress}%`;
    document.getElementById("overallProgressBar").style.width = `${overallProgress}%`;

    const recommendation = state.recommendation || {};
    const recommendationType = String(recommendation.type || "empty").toLowerCase();
    const titleEl = document.getElementById("recommendationTitle");
    const descEl = document.getElementById("recommendationDescription");
    const badgeEl = document.getElementById("recommendationBadge");
    const metaEl = document.getElementById("recommendationMeta");
    const startButton = document.getElementById("recommendedStartButton");

    titleEl.textContent = recommendation.title || "Chưa có bài học phù hợp";
    descEl.textContent = recommendation.reason || "Hãy chọn một bài trong thư viện hoặc tự tạo bài học mới.";
    badgeEl.textContent = normalizeLevel(recommendation.level || level).toUpperCase();

    const metaItems = [];

    if (recommendation.topic) {
        metaItems.push(`🎯 ${recommendation.topic}`);
    }

    if (recommendationType === "review") {
        metaItems.push("🔁 Ôn điểm yếu");
        metaItems.push(`🔤 ${ensureArray(recommendation.weakWords).length} từ yếu`);
        metaItems.push(`💬 ${ensureArray(recommendation.weakPhrases).length} câu yếu`);
    } else if (recommendationType === "active") {
        metaItems.push("▶️ Bài đang áp dụng");
        metaItems.push(recommendation.mode === "review" ? "🔁 Ôn nhanh" : "📘 Học tiếp");
    } else if (recommendationType === "template") {
        metaItems.push(recommendation.mode === "roleplay" ? "🎭 Nhập vai" : "📘 Bài học mới");
        metaItems.push(`🔤 ${Number(recommendation.targetWordCount || 0)} từ`);
        metaItems.push(`💬 ${Number(recommendation.targetPhraseCount || 0)} câu`);
    }

    if (Number(recommendation.estimatedMinutes || 0) > 0) {
        metaItems.push(`⏱ ${Number(recommendation.estimatedMinutes)} phút`);
    }

    metaEl.innerHTML = metaItems
        .map(item => `<span class="meta-chip">${escapeHTML(item)}</span>`)
        .join("");

    if (recommendationType === "active") {
        startButton.textContent = "▶ Xem bài đang học";
        startButton.disabled = false;
    } else if (recommendationType === "review") {
        startButton.textContent = "🔁 Ôn nhanh 5 phút";
        startButton.disabled = false;
    } else if (recommendationType === "template" && recommendation.templateId) {
        startButton.textContent = "▶ Bắt đầu bài đề xuất";
        startButton.disabled = false;
    } else {
        startButton.textContent = "Chưa có bài phù hợp";
        startButton.disabled = true;
    }

    const weakItems = [
        ...weakWords.map(item => ({ text: item, type: "word" })),
        ...weakPhrases.map(item => ({ text: item, type: "phrase" }))
    ].slice(0, 18);

    document.getElementById("weakItems").innerHTML = weakItems.length
        ? weakItems.map(item => `<span class="tag weak">${item.type === "word" ? "🔤" : "💬"} ${escapeHTML(item.text)}</span>`).join("")
        : `<span class="empty-text">Chưa có dữ liệu điểm yếu. Hãy hoàn thành ít nhất một buổi học để hệ thống bắt đầu theo dõi.</span>`;
}

function renderActiveLesson() {
    const titleEl = document.getElementById("activeLessonTitle");
    const statusEl = document.getElementById("activeLessonStatus");
    const contentEl = document.getElementById("activeLessonContent");
    const stopButton = document.getElementById("stopLessonButton");

    if (!state.active?.activeId) {
        titleEl.textContent = "Chưa có bài đang học";
        statusEl.textContent = "Chưa bật";
        statusEl.className = "pill neutral";
        contentEl.textContent = "Chọn một bài học hoặc tạo bài riêng để bắt đầu.";
        contentEl.classList.add("muted");
        stopButton.disabled = true;
        return;
    }

    const cleanContent = cleanActiveContent(state.active.content || "");
    const titleMatch = cleanContent.match(/Tiêu đề:\s*([^\n]+)/i);
    titleEl.textContent = titleMatch ? titleMatch[1].trim() : "Bài học tiếng Anh đang áp dụng";
    statusEl.textContent = "Đang hoạt động";
    statusEl.className = "pill";
    contentEl.textContent = cleanContent;
    contentEl.classList.remove("muted");
    stopButton.disabled = false;
}

function cleanActiveContent(content) {
    return String(content || "")
        .replace(/^\[ENGLISH_TUTOR\]\[[^\]]+\]\s*/, "")
        .replace(/^\[ENGLISH_TUTOR\]\s*/, "")
        .trim();
}

async function startRecommendedLesson() {
    const recommendation = state.recommendation || {};
    const type = String(recommendation.type || "empty").toLowerCase();

    if (type === "active") {
        document.getElementById("activeLessonTitle")?.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });
        showToast("Bài học này đang được áp dụng trên robot. Hãy gọi Sophia để học tiếp.", "info");
        return;
    }

    if (type === "review") {
        await startQuickReview();
        return;
    }

    if (type === "template" && recommendation.templateId) {
        await applyTemplate(recommendation.templateId);
        await loadRecommendation();
        buildRecommendation();
        renderDashboard();
        return;
    }

    showToast("Chưa có bài học được đề xuất.", "error");
}

async function startQuickReview() {
    if (!state.deviceId) {
        showToast("Chưa chọn thiết bị.", "error");
        return;
    }

    const profile = state.report?.profile || {};
    const weakWords = ensureArray(profile.weak_words);
    const weakPhrases = ensureArray(profile.weak_phrases);

    if (!weakWords.length && !weakPhrases.length) {
        showToast(
            "Bé hiện chưa có từ hoặc câu yếu cần ôn. Hãy chọn một bài học mới.",
            "info"
        );
        return;
    }

    try {
        showToast("Đang tạo bài ôn nhanh từ dữ liệu học tập...", "info");

        await apiFetch("/api/english-tutor/quick-review", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ deviceId: state.deviceId })
        });

        await Promise.all([
            loadActiveLesson(),
            loadRecommendation()
        ]);

        buildRecommendation();
        renderDashboard();
        showEnglishSection("today");
        showToast("Đã bật bài ôn nhanh. Hãy gọi Sophia để bắt đầu.", "success");
    } catch (error) {
        showToast(error.message || "Không tạo được bài ôn nhanh.", "error");
    }
}

function setLibraryMode(mode) {
    state.libraryMode = mode === "roleplay" ? "roleplay" : "lesson";
    state.selectedTemplateId = null;
    document.getElementById("modeLessonButton").classList.toggle("active", state.libraryMode === "lesson");
    document.getElementById("modeRoleplayButton").classList.toggle("active", state.libraryMode === "roleplay");
    renderTemplateLibrary();
}

function renderTemplateLibrary() {
    const grid = document.getElementById("templateGrid");
    if (!grid) return;

    const selectedLevel = normalizeLevel(document.getElementById("libraryLevelFilter")?.value || "");
    const keyword = String(document.getElementById("librarySearch")?.value || "").trim().toLowerCase();
    const source = state.libraryMode === "roleplay" ? state.roleplayTemplates : state.lessonTemplates;

    const filtered = source.filter(template => {
        const levelOk = !selectedLevel || normalizeLevel(template.level) === selectedLevel;
        const text = `${template.title || ""} ${template.topic || ""} ${template.scenario || ""}`.toLowerCase();
        const searchOk = !keyword || text.includes(keyword);
        return levelOk && searchOk;
    });

    if (!filtered.length) {
        grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;padding:28px;text-align:center;border:1px dashed rgba(255,255,255,0.14);border-radius:16px;">Không tìm thấy giáo trình phù hợp.</div>`;
        renderTemplateDetail(null);
        return;
    }

    grid.innerHTML = filtered.map(template => {
        const isActive = String(state.selectedTemplateId) === String(template.id);
        const wordsCount = ensureArray(template.target_words).length;
        const phrasesCount = ensureArray(template.target_phrases).length;
        return `
            <button type="button" class="template-card ${isActive ? "active" : ""}" onclick="selectTemplate('${escapeJsString(template.id)}')">
                <div class="template-card-top">
                    <div class="template-card-icon">${state.libraryMode === "roleplay" ? "🎭" : "📘"}</div>
                    <span class="pill">${escapeHTML(normalizeLevel(template.level).toUpperCase())}</span>
                </div>
                <h3>${escapeHTML(template.title || "Bài học tiếng Anh")}</h3>
                <p>${escapeHTML(template.scenario || template.tutor_note || `Chủ đề ${template.topic || "General"}`)}</p>
                <div class="meta-row">
                    <span class="meta-chip">🎯 ${escapeHTML(template.topic || "General")}</span>
                    <span class="meta-chip">🔤 ${wordsCount}</span>
                    <span class="meta-chip">💬 ${phrasesCount}</span>
                </div>
            </button>
        `;
    }).join("");

    const selected = filtered.find(template => String(template.id) === String(state.selectedTemplateId));
    renderTemplateDetail(selected || null);
}

function selectTemplate(templateId) {
    state.selectedTemplateId = templateId;
    renderTemplateLibrary();
}

function renderTemplateDetail(template) {
    const detail = document.getElementById("templateDetail");
    if (!detail) return;

    if (!template) {
        detail.innerHTML = `
            <div class="empty-detail">
                <div class="empty-icon">${state.libraryMode === "roleplay" ? "🎭" : "📚"}</div>
                <h3>Chọn một ${state.libraryMode === "roleplay" ? "tình huống" : "giáo trình"}</h3>
                <p>Thông tin chi tiết sẽ hiển thị tại đây.</p>
            </div>
        `;
        return;
    }

    const words = ensureArray(template.target_words);
    const phrases = ensureArray(template.target_phrases);

    detail.innerHTML = `
        <div class="panel-header">
            <div>
                <div class="eyebrow">${state.libraryMode === "roleplay" ? "TÌNH HUỐNG NHẬP VAI" : "GIÁO TRÌNH"}</div>
                <h2>${escapeHTML(template.title || "Bài học tiếng Anh")}</h2>
            </div>
            <span class="pill">${escapeHTML(normalizeLevel(template.level).toUpperCase())}</span>
        </div>

        <div class="meta-row">
            <span class="meta-chip">🎯 ${escapeHTML(template.topic || "General")}</span>
            <span class="meta-chip">${state.libraryMode === "roleplay" ? "🎭 Nhập vai" : "📘 Bài học"}</span>
        </div>

        ${template.scenario ? `
            <div class="detail-section">
                <h4>Tình huống</h4>
                <div class="muted" style="line-height:1.6;">${escapeHTML(template.scenario)}</div>
            </div>
        ` : ""}

        <div class="detail-section">
            <h4>Từ mục tiêu</h4>
            ${words.length ? `<div class="tag-list">${words.map(word => `<span class="tag">${escapeHTML(word)}</span>`).join("")}</div>` : `<div class="muted">Không có danh sách từ riêng.</div>`}
        </div>

        <div class="detail-section">
            <h4>Câu mục tiêu</h4>
            ${phrases.length ? `<ul class="detail-list">${phrases.map(phrase => `<li>${escapeHTML(phrase)}</li>`).join("")}</ul>` : `<div class="muted">Không có câu mẫu riêng.</div>`}
        </div>

        ${template.tutor_note ? `
            <div class="detail-section">
                <h4>Ghi chú cho gia sư</h4>
                <div class="muted" style="line-height:1.6;">${escapeHTML(template.tutor_note)}</div>
            </div>
        ` : ""}

        <div class="form-actions" style="margin-top:22px;">
            <button class="button primary large" type="button" onclick="applyTemplate('${escapeJsString(template.id)}')">🚀 Áp dụng bài này</button>
        </div>
    `;
}

async function applyTemplate(templateId) {
    if (!state.deviceId) {
        showToast("Chưa chọn thiết bị.", "error");
        return;
    }

    try {
        showToast("Đang áp dụng giáo trình...", "info");
        await apiFetch("/api/english-tutor/activate-template", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                deviceId: state.deviceId,
                templateId
            })
        });
        await Promise.all([
            loadActiveLesson(),
            loadRecommendation()
        ]);
        buildRecommendation();
        renderDashboard();
        showEnglishSection("today");
        showToast("Đã áp dụng bài học. Hãy gọi Sophia hoặc nói Xin chào để bắt đầu.", "success");
    } catch (error) {
        showToast(error.message, "error");
    }
}

function renderTopicOptions() {
    const levelElement = document.getElementById("customLevel");
    const topicElement = document.getElementById("customTopic");
    if (!levelElement || !topicElement) return;

    const level = normalizeLevel(levelElement.value || "starter");
    const topics = ENGLISH_TOPICS_BY_LEVEL[level] || ENGLISH_TOPICS_BY_LEVEL.starter;
    const oldValue = topicElement.value;

    topicElement.innerHTML = topics.map(([value, label]) => `<option value="${escapeHTML(value)}">${escapeHTML(label)}</option>`).join("");
    if (topics.some(([value]) => value === oldValue)) {
        topicElement.value = oldValue;
    }
}

function fillExampleLesson() {
    document.getElementById("customTitle").value = "Animals - My favorite animal";
    document.getElementById("customLevel").value = "starter";
    renderTopicOptions();
    document.getElementById("customTopic").value = "Animals";
    document.getElementById("customWords").value = "cat, dog, elephant, tiger, rabbit";
    document.getElementById("customPhrases").value = "This is a cat.\nI like dogs.\nThe elephant is big.\nMy favorite animal is a rabbit.";
    document.getElementById("customNote").value = "Nói chậm, hỏi mỗi lượt một câu. Dùng ví dụ vui nhộn và khích lệ người học trả lời bằng câu tiếng Anh ngắn.";
    showToast("Đã điền bài mẫu. Bạn có thể sửa lại trước khi áp dụng.", "success");
}

async function activateCustomLesson() {
    if (!state.deviceId) {
        showToast("Chưa chọn thiết bị.", "error");
        return;
    }

    const title = document.getElementById("customTitle").value.trim();
    const level = document.getElementById("customLevel").value;
    const topic = document.getElementById("customTopic").value;
    const targetWords = document.getElementById("customWords").value.trim();
    const targetPhrases = document.getElementById("customPhrases").value.trim();
    const note = document.getElementById("customNote").value.trim();

    if (!title) {
        showToast("Hãy nhập tiêu đề bài học.", "error");
        document.getElementById("customTitle").focus();
        return;
    }

    try {
        showToast("Đang tạo và áp dụng bài học...", "info");
        await apiFetch("/api/english-tutor/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                deviceId: state.deviceId,
                title,
                level,
                topic,
                targetWords,
                targetPhrases,
                note
            })
        });
        await Promise.all([
            loadActiveLesson(),
            loadRecommendation()
        ]);
        buildRecommendation();
        renderDashboard();
        showEnglishSection("today");
        showToast("Đã bật bài học mới. Hãy gọi Sophia để bắt đầu.", "success");
    } catch (error) {
        showToast(error.message, "error");
    }
}

async function stopActiveLesson() {
    if (!state.active?.activeId) return;

    const confirmed = await showConfirm(
        "Tắt bài đang học?",
        "Bài Gia sư tiếng Anh đang áp dụng sẽ bị xóa khỏi robot. Lịch sử các buổi đã hoàn thành vẫn được giữ lại."
    );

    if (!confirmed) return;

    try {
        showToast("Đang tắt bài học...", "info");
        await apiFetch("/api/english-tutor/active", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ deviceId: state.deviceId })
        });
        await Promise.all([
            loadActiveLesson(),
            loadRecommendation()
        ]);
        buildRecommendation();
        renderDashboard();
        showToast("Đã tắt chế độ Gia sư tiếng Anh.", "success");
    } catch (error) {
        showToast(error.message, "error");
    }
}

function getSessionTimeValue(session) {
    const value =
        session?.completed_at ||
        session?.last_seen_at ||
        session?.started_at ||
        session?.created_at ||
        "";

    const timestamp = new Date(value).getTime();
    return Number.isFinite(timestamp) ? timestamp : 0;
}

function renderReport() {
    if (!state.report) return;

    const profile = state.report.profile || {};
    const stats = state.report.stats || {};
    const sessions = Array.isArray(state.report.sessions) ? state.report.sessions : [];
    const knownWords = ensureArray(profile.known_words);
    const weakWords = ensureArray(profile.weak_words);
    const weakPhrases = ensureArray(profile.weak_phrases);

    setText("reportCompleted", Number(stats.completed_sessions || 0));
    setText("reportStarted", Number(stats.started_sessions || 0));
    setText("reportAbandoned", Number(stats.abandoned_sessions || 0));
    setText("reportAverage", Number(stats.avg_score || 0));
    setText("knownWordCount", `${knownWords.length} từ`);
    setText("weakWordCount", `${weakWords.length + weakPhrases.length} mục`);

    document.getElementById("knownWordList").innerHTML = knownWords.length
        ? knownWords.slice(0, 80).map(word => `<span class="tag">${escapeHTML(word)}</span>`).join("")
        : `<span class="empty-text">Chưa có từ nào được ghi nhận là đã biết.</span>`;

    const weakItems = [
        ...weakWords.map(word => `🔤 ${word}`),
        ...weakPhrases.map(phrase => `💬 ${phrase}`)
    ];

    document.getElementById("reportWeakList").innerHTML = weakItems.length
        ? weakItems.slice(0, 80).map(item => `<span class="tag weak">${escapeHTML(item)}</span>`).join("")
        : `<span class="empty-text">Chưa có nội dung cần ôn thêm.</span>`;

    const sessionList = document.getElementById("sessionList");
    const pagination = document.getElementById("sessionPagination");
    const prevButton = document.getElementById("sessionPrevButton");
    const nextButton = document.getElementById("sessionNextButton");
    const pageInfo = document.getElementById("sessionPageInfo");

    if (!sessionList) return;

    if (!sessions.length) {
        sessionList.innerHTML = `<div class="empty-state">Chưa có lịch sử học tiếng Anh.</div>`;

        if (pagination) {
            pagination.hidden = true;
        }

        return;
    }

    /*
     * Luôn sắp xếp buổi mới nhất lên trước để trang 1
     * chắc chắn chứa đúng 3 buổi học gần nhất.
     */
    const sortedSessions = [...sessions].sort(
        (first, second) => getSessionTimeValue(second) - getSessionTimeValue(first)
    );

    const pageSize = Math.max(1, Number(state.sessionPageSize || 3));
    const totalPages = Math.max(1, Math.ceil(sortedSessions.length / pageSize));

    state.sessionPage = Math.min(
        Math.max(1, Number(state.sessionPage || 1)),
        totalPages
    );

    const startIndex = (state.sessionPage - 1) * pageSize;
    const visibleSessions = sortedSessions.slice(startIndex, startIndex + pageSize);

    sessionList.innerHTML = visibleSessions.map(session => {
        const status = String(session.status || "started").toLowerCase();
        const statusLabel = status === "completed" ? "Hoàn thành" : status === "abandoned" ? "Bỏ dở" : "Đang học";
        const statusClass = status === "completed" ? "status-completed" : status === "abandoned" ? "status-abandoned" : "status-started";
        const durationMinutes = Math.max(0, Math.ceil(Number(session.duration_seconds || 0) / 60));
        const score = Number(session.score || 0);
        const dateText = formatDateTime(
            session.completed_at ||
            session.last_seen_at ||
            session.started_at ||
            session.created_at
        );

        return `
            <div class="session-item">
                <div class="session-main">
                    <div class="session-title">${escapeHTML(session.lesson_title || "Bài học tiếng Anh")}</div>
                    <div class="session-subtitle">${escapeHTML(session.topic || "General")} · ${escapeHTML(normalizeLevel(session.level).toUpperCase())} · ${escapeHTML(dateText)}</div>
                    ${session.summary ? `<div class="session-subtitle" style="margin-top:7px;">${escapeHTML(session.summary)}</div>` : ""}
                </div>
                <div class="session-cell"><span class="status-badge ${statusClass}">${statusLabel}</span></div>
                <div class="session-cell">⏱ ${durationMinutes} phút</div>
                <div class="session-cell">⭐ ${score || 0}/100</div>
            </div>
        `;
    }).join("");

    if (pagination) {
        pagination.hidden = totalPages <= 1;
    }

    if (pageInfo) {
        const firstItem = startIndex + 1;
        const lastItem = Math.min(startIndex + visibleSessions.length, sortedSessions.length);

        pageInfo.textContent =
            `Đang xem ${firstItem}-${lastItem} / ${sortedSessions.length} buổi`;
    }

    if (prevButton) {
        prevButton.disabled = state.sessionPage <= 1;
    }

    if (nextButton) {
        nextButton.disabled = state.sessionPage >= totalPages;
    }
}

function changeSessionPage(direction) {
    const sessions = Array.isArray(state.report?.sessions)
        ? state.report.sessions
        : [];

    if (!sessions.length) return;

    const pageSize = Math.max(1, Number(state.sessionPageSize || 3));
    const totalPages = Math.max(1, Math.ceil(sessions.length / pageSize));
    const nextPage = Math.min(
        Math.max(1, Number(state.sessionPage || 1) + Number(direction || 0)),
        totalPages
    );

    if (nextPage === state.sessionPage) return;

    state.sessionPage = nextPage;
    renderReport();

    document.getElementById("sessionList")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


/* ===== STARTER ROADMAP UI V4 ===== */
function getStarterRoadmap() {
    return Array.isArray(window.STARTER_ROADMAP)
        ? window.STARTER_ROADMAP
        : [];
}

function getAllRoadmapLessons() {
    return getStarterRoadmap().flatMap(chapter => {
        const lessons = Array.isArray(chapter?.lessons)
            ? chapter.lessons
            : [];

        return lessons.map(lesson => ({ chapter, lesson }));
    });
}

function normalizeRoadmapText(value) {
    return String(value || "")
        .normalize("NFKC")
        .trim()
        .toLowerCase()
        .replace(/[–—]/g, "-")
        .replace(/\s+/g, " ");
}

function getCompletedRoadmapLessonIds() {
    const sessions = Array.isArray(state.report?.sessions)
        ? state.report.sessions
        : [];

    const completedTitles = new Set(
        sessions
            .filter(session => String(session?.status || "").toLowerCase() === "completed")
            .map(session => normalizeRoadmapText(session?.lesson_title))
            .filter(Boolean)
    );

    const completedIds = new Set();

    getAllRoadmapLessons().forEach(({ lesson }) => {
        const expectedTitle = normalizeRoadmapText(lesson.fullTitle);

        if (completedTitles.has(expectedTitle)) {
            completedIds.add(lesson.id);
        }
    });

    return completedIds;
}

function getActiveRoadmapLessonId() {
    const activeText = normalizeRoadmapText([
        state.active?.title,
        state.active?.lesson_title,
        state.active?.content
    ].filter(Boolean).join("\n"));

    if (!activeText) return "";

    const match = getAllRoadmapLessons().find(({ lesson }) =>
        activeText.includes(normalizeRoadmapText(lesson.fullTitle))
    );

    return match?.lesson?.id || "";
}

function findRoadmapLesson(lessonId) {
    return getAllRoadmapLessons().find(
        item => String(item.lesson?.id) === String(lessonId)
    ) || null;
}

function getNextRoadmapLesson(completedIds) {
    return getAllRoadmapLessons().find(
        ({ lesson }) => !completedIds.has(lesson.id)
    ) || null;
}

function getRoadmapLessonStatus(lesson, completedIds, activeLessonId, nextLessonId) {
    if (completedIds.has(lesson.id)) return "completed";
    if (lesson.id === activeLessonId) return "active";
    if (lesson.id === nextLessonId) return "next";
    return "pending";
}

function getRoadmapStatusLabel(status) {
    if (status === "completed") return "Đã hoàn thành";
    if (status === "active") return "Đang áp dụng";
    if (status === "next") return "Bài tiếp theo";
    return "Chưa học";
}

function getRoadmapButtonLabel(status) {
    if (status === "completed") return "↻ Học lại";
    if (status === "active") return "▶ Tiếp tục học";
    if (status === "next") return "▶ Bắt đầu bài tiếp theo";
    return "Bắt đầu bài";
}

function renderStarterRoadmap() {
    const container = document.getElementById("roadmapChapterList");
    if (!container) return;

    const roadmap = getStarterRoadmap();
    const allLessons = getAllRoadmapLessons();
    const completedIds = getCompletedRoadmapLessonIds();
    const activeLessonId = getActiveRoadmapLessonId();
    const nextItem = getNextRoadmapLesson(completedIds);
    const nextLessonId = nextItem?.lesson?.id || "";
    const completedCount = completedIds.size;
    const totalCount = allLessons.length;
    const progressPercent = totalCount
        ? Math.round((completedCount / totalCount) * 100)
        : 0;

    setText("roadmapCompletedCount", completedCount);
    setText("roadmapTotalCount", totalCount);
    setText("roadmapProgressPercent", `${progressPercent}%`);

    const progressBar = document.getElementById("roadmapOverallProgressBar");
    if (progressBar) {
        progressBar.style.width = `${progressPercent}%`;
    }

    const nextTitle = document.getElementById("roadmapNextTitle");
    const nextDescription = document.getElementById("roadmapNextDescription");
    const continueButton = document.getElementById("roadmapContinueButton");

    if (completedCount >= totalCount && totalCount > 0) {
        if (nextTitle) nextTitle.textContent = "Bạn đã hoàn thành toàn bộ Starter!";
        if (nextDescription) {
            nextDescription.textContent =
                "Có thể học lại bất kỳ bài nào để củng cố từ và câu đã học.";
        }
        if (continueButton) {
            continueButton.textContent = "Xem lại từ đầu";
            continueButton.disabled = false;
            continueButton.dataset.lessonId = allLessons[0]?.lesson?.id || "";
        }
    } else if (activeLessonId) {
        const activeItem = findRoadmapLesson(activeLessonId);
        if (nextTitle) {
            nextTitle.textContent = activeItem?.lesson?.fullTitle || "Bài đang áp dụng";
        }
        if (nextDescription) {
            nextDescription.textContent =
                "Bài này đang được áp dụng trên robot. Hãy gọi Sophia để tiếp tục.";
        }
        if (continueButton) {
            continueButton.textContent = "▶ Tiếp tục bài đang học";
            continueButton.disabled = false;
            continueButton.dataset.lessonId = activeLessonId;
        }
    } else if (nextItem) {
        if (nextTitle) nextTitle.textContent = nextItem.lesson.fullTitle;
        if (nextDescription) {
            nextDescription.textContent =
                `${nextItem.chapter.icon} Chương ${nextItem.chapter.number}: ` +
                `${nextItem.chapter.title} · khoảng ${nextItem.lesson.estimatedMinutes} phút`;
        }
        if (continueButton) {
            continueButton.textContent = "▶ Bắt đầu bài tiếp theo";
            continueButton.disabled = false;
            continueButton.dataset.lessonId = nextItem.lesson.id;
        }
    } else {
        if (nextTitle) nextTitle.textContent = "Chưa có dữ liệu lộ trình";
        if (nextDescription) nextDescription.textContent = "Không tìm thấy danh sách bài Starter.";
        if (continueButton) {
            continueButton.disabled = true;
            continueButton.dataset.lessonId = "";
        }
    }

    if (!state.roadmapOpenChapterId) {
        state.roadmapOpenChapterId =
            nextItem?.chapter?.id ||
            findRoadmapLesson(activeLessonId)?.chapter?.id ||
            roadmap[0]?.id ||
            "";
    }

    container.innerHTML = roadmap.map(chapter => {
        const chapterLessons = Array.isArray(chapter?.lessons)
            ? chapter.lessons
            : [];
        const chapterCompleted = chapterLessons.filter(lesson =>
            completedIds.has(lesson.id)
        ).length;
        const chapterPercent = chapterLessons.length
            ? Math.round((chapterCompleted / chapterLessons.length) * 100)
            : 0;
        const isOpen = state.roadmapOpenChapterId === chapter.id;
        const chapterHasActive = chapterLessons.some(lesson => lesson.id === activeLessonId);
        const chapterHasNext = chapterLessons.some(lesson => lesson.id === nextLessonId);

        const lessonHtml = chapterLessons.map(lesson => {
            const status = getRoadmapLessonStatus(
                lesson,
                completedIds,
                activeLessonId,
                nextLessonId
            );
            const wordsCount = ensureArray(lesson.targetWords).length;
            const phrasesCount = ensureArray(lesson.targetPhrases).length;
            const statusIcon =
                status === "completed" ? "✓" :
                status === "active" ? "▶" :
                status === "next" ? "★" :
                lesson.type === "review" ? "↻" : "○";

            return `
                <article class="roadmap-lesson-card status-${status}">
                    <div class="roadmap-lesson-status-icon" aria-hidden="true">
                        ${statusIcon}
                    </div>

                    <div class="roadmap-lesson-main">
                        <div class="roadmap-lesson-topline">
                            <span class="roadmap-lesson-code">${escapeHTML(lesson.code)}</span>
                            <span class="roadmap-status-badge status-${status}">
                                ${escapeHTML(getRoadmapStatusLabel(status))}
                            </span>
                        </div>

                        <h3>${escapeHTML(lesson.title)}</h3>
                        <p>${escapeHTML(lesson.objective || "Bài học Starter")}</p>

                        <div class="roadmap-lesson-meta">
                            <span>⏱ ${Number(lesson.estimatedMinutes || 0)} phút</span>
                            <span>🔤 ${wordsCount} từ</span>
                            <span>💬 ${phrasesCount} câu</span>
                            ${lesson.type === "review" ? "<span>🔁 Ôn chương</span>" : ""}
                        </div>
                    </div>

                    <button
                        class="button ${status === "next" || status === "active" ? "primary" : "secondary"} roadmap-lesson-button"
                        type="button"
                        onclick="startRoadmapLesson('${escapeJsString(lesson.id)}')"
                    >
                        ${escapeHTML(getRoadmapButtonLabel(status))}
                    </button>
                </article>
            `;
        }).join("");

        return `
            <article class="roadmap-chapter-card ${isOpen ? "open" : ""} ${chapterHasActive ? "has-active" : ""} ${chapterHasNext ? "has-next" : ""}">
                <button
                    class="roadmap-chapter-header"
                    type="button"
                    onclick="toggleRoadmapChapter('${escapeJsString(chapter.id)}')"
                    aria-expanded="${isOpen ? "true" : "false"}"
                >
                    <span class="roadmap-chapter-icon">${escapeHTML(chapter.icon || "📘")}</span>

                    <span class="roadmap-chapter-heading">
                        <span class="roadmap-chapter-eyebrow">
                            CHƯƠNG ${Number(chapter.number || 0)} · ${escapeHTML(chapter.englishTitle || "Starter")}
                        </span>
                        <strong>${escapeHTML(chapter.title || "Chương Starter")}</strong>
                        <small>${escapeHTML(chapter.description || "")}</small>
                    </span>

                    <span class="roadmap-chapter-progress-wrap">
                        <span class="roadmap-chapter-count">
                            ${chapterCompleted}/${chapterLessons.length} bài
                        </span>
                        <span class="roadmap-mini-progress">
                            <span style="width:${chapterPercent}%"></span>
                        </span>
                        <span class="roadmap-chapter-toggle">${isOpen ? "−" : "+"}</span>
                    </span>
                </button>

                <div class="roadmap-lesson-list" ${isOpen ? "" : "hidden"}>
                    ${lessonHtml}
                </div>
            </article>
        `;
    }).join("");
}

function toggleRoadmapChapter(chapterId) {
    state.roadmapOpenChapterId =
        state.roadmapOpenChapterId === chapterId
            ? ""
            : chapterId;

    renderStarterRoadmap();
}

function continueStarterRoadmap() {
    const button = document.getElementById("roadmapContinueButton");
    const lessonId = button?.dataset?.lessonId || "";

    if (!lessonId) {
        showToast("Chưa xác định được bài tiếp theo.", "error");
        return;
    }

    startRoadmapLesson(lessonId);
}

function buildRoadmapTutorNote(chapter, lesson) {
    const reviewInstruction = lesson.type === "review"
        ? "Đây là bài ôn tập cuối chương. Hãy trộn câu hỏi nhận biết, lựa chọn và hội thoại ngắn; không đọc lại cả danh sách từ cùng lúc."
        : "Dạy lần lượt từng nhóm nhỏ, mỗi lượt chỉ hỏi một câu ngắn và khuyến khích người học trả lời bằng tiếng Anh.";

    return [
        `Đây là bài chính thức thuộc Lộ trình Starter, Chương ${chapter.number}: ${chapter.title}, mã bài ${lesson.code}.`,
        `Mục tiêu: ${lesson.objective}`,
        reviewInstruction,
        "Dùng đúng các từ và câu mục tiêu đã cung cấp; có thể tạo ví dụ rất ngắn phù hợp trẻ em Việt Nam.",
        "Nếu câu mẫu có dấu ba chấm, hãy điền thông tin người học đã biết; không hỏi lại thông tin đã có trong bộ nhớ.",
        "Không yêu cầu phát âm giống người bản xứ. Nếu đúng ý hoặc gần đúng thì công nhận là đạt.",
        "Mỗi từ hoặc câu chỉ được yêu cầu nói lại tối đa một lần; sau đó khen và chuyển tiếp.",
        "Khi người học nói học xong rồi hoặc done, phải gọi complete-english-tutor để lưu kết quả."
    ].join(" ");
}

async function startRoadmapLesson(lessonId) {
    if (!state.deviceId) {
        showToast("Chưa chọn thiết bị.", "error");
        return;
    }

    const item = findRoadmapLesson(lessonId);

    if (!item) {
        showToast("Không tìm thấy bài học trong lộ trình Starter.", "error");
        return;
    }

    const activeLessonId = getActiveRoadmapLessonId();

    if (activeLessonId === item.lesson.id) {
        showEnglishSection("today");
        showToast("Bài này đang được áp dụng. Hãy gọi Sophia để tiếp tục.", "info");
        return;
    }

    try {
        showToast(`Đang áp dụng ${item.lesson.fullTitle}...`, "info");

        await apiFetch("/api/english-tutor/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                deviceId: state.deviceId,
                title: item.lesson.fullTitle,
                level: "starter",
                topic: item.chapter.topic,
                targetWords: ensureArray(item.lesson.targetWords).join(", "),
                targetPhrases: ensureArray(item.lesson.targetPhrases).join("\n"),
                note: buildRoadmapTutorNote(item.chapter, item.lesson)
            })
        });

        await Promise.all([
            loadActiveLesson(),
            loadRecommendation()
        ]);

        buildRecommendation();
        renderDashboard();
        renderStarterRoadmap();
        showEnglishSection("today");

        showToast(
            `Đã bật ${item.lesson.fullTitle}. Hãy gọi Sophia để bắt đầu.`,
            "success"
        );
    } catch (error) {
        showToast(error.message || "Không áp dụng được bài trong lộ trình.", "error");
    }
}
/* ===== END STARTER ROADMAP UI V4 ===== */

function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    if (!toast) return;

    if (state.toastTimer) clearTimeout(state.toastTimer);
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    state.toastTimer = setTimeout(() => {
        toast.className = "toast";
    }, 3800);
}

function showConfirm(title, message) {
    const modal = document.getElementById("confirmModal");
    document.getElementById("confirmTitle").textContent = title;
    document.getElementById("confirmMessage").textContent = message;
    modal.hidden = false;

    return new Promise(resolve => {
        state.confirmResolver = resolve;
    });
}

function closeConfirmModal(result) {
    document.getElementById("confirmModal").hidden = true;
    if (state.confirmResolver) {
        state.confirmResolver(Boolean(result));
        state.confirmResolver = null;
    }
}

function normalizeLevel(value) {
    const level = String(value || "").trim().toLowerCase();
    return ["starter", "a1", "a2", "b1", "b2"].includes(level) ? level : level;
}

function ensureArray(value) {
    if (Array.isArray(value)) return value.filter(Boolean).map(item => String(item));
    if (!value) return [];
    if (typeof value === "string") {
        try {
            const parsed = JSON.parse(value);
            if (Array.isArray(parsed)) return parsed.filter(Boolean).map(item => String(item));
        } catch {
            return value.split(/[,\n]/).map(item => item.trim()).filter(Boolean);
        }
    }
    return [];
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = String(value);
}

function formatDateTime(value) {
    if (!value) return "Không rõ thời gian";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Không rõ thời gian";
    return date.toLocaleString("vi-VN", {
        hour12: false,
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>'"]/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;"
    }[character]));
}

function escapeJsString(value) {
    return String(value ?? "")
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'")
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n");
}
