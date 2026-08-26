document.addEventListener("DOMContentLoaded", () => {
    // --------------------------------------------------------
    // 전역 상태 변수
    // --------------------------------------------------------
    let currentTab = "dashboard";
    let selectedYear = "2026";
    let allTargets = [];
    let planSubView = "matrix"; // 'matrix' | 'year' | 'calendar'
    let yearViewSelectedYear = 2026;  // year shown in year-tab detail view
    let _yearViewCalendarCache = null; // cache for renderYearViewTable
    let mapFilterMode = "year"; // 'year' | 'month' | 'all'
    let selectedContinent = "all"; // 'all' | '아시아' | '유럽' | '오세아니아' | '북미' | '중동/기타'
    let mapTheme = "dark"; // 'dark' | 'light'
    // 연간 세부 계획 - 카테고리/뷰모드 상태
    let yearViewCategoryFilter = "all"; // 'all' | 'cat1' .. 'cat6'
    let yearViewMode = "list"; // 'list' | 'station'
    let stationCountryFilter = "all";
    let stationCodeFilter = "all";

    // --------------------------------------------------------
    // UI 요소 선택
    // --------------------------------------------------------
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");
    const globalYearSelect = document.getElementById("global-year-select");

    // 대시보드 요소
    const statTotal = document.getElementById("stat-total-val");
    const statDirect = document.getElementById("stat-direct-val");
    const statIndirect = document.getElementById("stat-indirect-val");
    const currentMonthLbl = document.getElementById("current-month-lbl");
    const monthCountBadge = document.getElementById("month-count-badge");
    const thisMonthTableBody = document.getElementById("this-month-table-body");

    // 월드맵 요소
    const worldMapImg = document.getElementById("world-map-img");
    const mapMarkersLayer = document.getElementById("map-markers-layer");
    const mapTooltip = document.getElementById("map-tooltip");
    const mapTargetCountBadge = document.getElementById("map-target-count-badge");
    const mapYearLbl = document.getElementById("map-year-lbl");
    const mapMonthLbl = document.getElementById("map-month-lbl");
    const mapViewFilterBtns = document.querySelectorAll("#map-view-filter .map-filter-btn");
    const continentPills = document.querySelectorAll("#continent-filter-pills .continent-pill");
    const btnMapThemeDark = document.getElementById("btn-map-theme-dark");
    const btnMapThemeLight = document.getElementById("btn-map-theme-light");

    // 연간 계획 (5개년 매트릭스 + 연도별 + 캘린더) 요소
    const btnViewMatrix = document.getElementById("btn-view-matrix");
    const btnViewYear = document.getElementById("btn-view-year");
    const btnViewCalendar = document.getElementById("btn-view-calendar");
    const matrixViewContainer = document.getElementById("matrix-view-container");
    const yearViewContainer = document.getElementById("year-view-container");
    const calendarGrid = document.getElementById("calendar-grid-container");
    const matrixTableBody = document.getElementById("matrix-table-body");
    const yearViewTableBody = document.getElementById("year-view-table-body");
    const yearViewTitle = document.getElementById("year-view-title");
    const yearViewCountBadge = document.getElementById("year-view-count-badge");
    const yearViewTypeFilter = document.getElementById("year-view-type-filter");
    const yearViewMonthFilter = document.getElementById("year-view-month-filter");
    const calendarYearBadge = document.getElementById("calendar-year-badge"); // may be null

    // 리스트 필터 요소
    const filterMonthSelect = document.getElementById("filter-month-select");
    const filterTypeSelect = document.getElementById("filter-type-select");
    const listTableBody = document.getElementById("list-table-body");

    // 상세 모달 요소
    const detailModal = document.getElementById("audit-detail-modal");
    const detailForm = document.getElementById("audit-detail-form");
    const btnCloseDetailModal = document.getElementById("btn-close-detail-modal");
    const btnCancelDetailModal = document.getElementById("btn-cancel-detail-modal");
    
    // 이벤트 모달 요소
    const eventModal = document.getElementById("event-add-modal");
    const eventForm = document.getElementById("event-add-form");
    const btnOpenEventModal = document.getElementById("btn-open-event-modal");
    const btnCloseEventModal = document.getElementById("btn-close-event-modal");
    const btnCancelEventModal = document.getElementById("btn-cancel-event-modal");
    const eventTargetSelect = document.getElementById("event-target-select");

    // --------------------------------------------------------
    // 전 세계 공항/지점 좌표 및 대륙 데이터베이스
    // --------------------------------------------------------
    const STATION_DB = {
        // 국내
        "ICN": { name: "인천", country: "대한민국", continent: "아시아", lat: 37.46, lon: 126.44 },
        "GMP": { name: "김포", country: "대한민국", continent: "아시아", lat: 37.55, lon: 126.79 },
        "CJU": { name: "제주", country: "대한민국", continent: "아시아", lat: 33.51, lon: 126.49 },
        "TAE": { name: "대구", country: "대한민국", continent: "아시아", lat: 35.89, lon: 128.65 },
        "KWJ": { name: "광주", country: "대한민국", continent: "아시아", lat: 35.12, lon: 126.80 },
        "PUS": { name: "부산(김해)", country: "대한민국", continent: "아시아", lat: 35.17, lon: 128.93 },
        "CJJ": { name: "청주", country: "대한민국", continent: "아시아", lat: 36.71, lon: 127.49 },
        "KAEMS": { name: "사천(KAEMS)", country: "대한민국", continent: "아시아", lat: 35.08, lon: 128.07 },
        
        // 일본
        "NRT": { name: "도쿄(나리타)", country: "일본", continent: "아시아", lat: 35.76, lon: 140.38 },
        "HND": { name: "도쿄(하네다)", country: "일본", continent: "아시아", lat: 35.54, lon: 139.77 },
        "KIX": { name: "오사카(간사이)", country: "일본", continent: "아시아", lat: 34.43, lon: 135.23 },
        "FUK": { name: "후쿠오카", country: "일본", continent: "아시아", lat: 33.58, lon: 130.45 },
        "CTS": { name: "삿포로(신치토세)", country: "일본", continent: "아시아", lat: 42.77, lon: 141.69 },
        "OKA": { name: "오키나와(나하)", country: "일본", continent: "아시아", lat: 26.19, lon: 127.64 },
        "KMJ": { name: "구마모토", country: "일본", continent: "아시아", lat: 32.83, lon: 130.85 },
        "OIT": { name: "오이타", country: "일본", continent: "아시아", lat: 33.47, lon: 131.73 },
        "NGO": { name: "나고야", country: "일본", continent: "아시아", lat: 34.85, lon: 136.80 },
        "KKJ": { name: "기타큐슈", country: "일본", continent: "아시아", lat: 33.84, lon: 130.94 },
        "KOJ": { name: "가고시마", country: "일본", continent: "아시아", lat: 31.80, lon: 130.71 },
        "HSG": { name: "사가", country: "일본", continent: "아시아", lat: 33.14, lon: 130.30 },

        // 동남아 및 오세아니아
        "GUM": { name: "괌", country: "미국(괌)", continent: "오세아니아", lat: 13.48, lon: 144.79 },
        "SPN": { name: "사이판", country: "미국(북마리아나)", continent: "오세아니아", lat: 15.11, lon: 145.72 },
        "SYD": { name: "시드니", country: "호주", continent: "오세아니아", lat: -33.94, lon: 151.17 },
        "VTE": { name: "비엔티안", country: "라오스", continent: "아시아", lat: 17.98, lon: 102.56 },
        "CNX": { name: "치앙마이", country: "태국", continent: "아시아", lat: 18.76, lon: 98.96 },
        "BKK": { name: "방콕(수완나품)", country: "태국", continent: "아시아", lat: 13.69, lon: 100.75 },
        "DMK": { name: "방콕(돈므앙)", country: "태국", continent: "아시아", lat: 13.91, lon: 100.60 },
        "SGN": { name: "호치민", country: "베트남", continent: "아시아", lat: 10.81, lon: 106.65 },
        "DAD": { name: "다낭", country: "베트남", continent: "아시아", lat: 16.04, lon: 108.19 },
        "CXR": { name: "나트랑(깜라인)", country: "베트남", continent: "아시아", lat: 11.99, lon: 109.21 },
        "HAN": { name: "하노이", country: "베트남", continent: "아시아", lat: 21.22, lon: 105.80 },
        "PQC": { name: "푸꾸옥", country: "베트남", continent: "아시아", lat: 10.16, lon: 103.99 },
        "KLO": { name: "칼리보(보라카이)", country: "필리핀", continent: "아시아", lat: 11.67, lon: 122.37 },
        "CRK": { name: "클락", country: "필리핀", continent: "아시아", lat: 15.18, lon: 120.55 },
        "CEB": { name: "세부", country: "필리핀", continent: "아시아", lat: 10.30, lon: 123.97 },
        "MNL": { name: "마닐라", country: "필리핀", continent: "아시아", lat: 14.50, lon: 121.01 },
        "TAG": { name: "보홀(탁빌라란)", country: "필리핀", continent: "아시아", lat: 9.56, lon: 123.76 },
        "BKI": { name: "코타키나발루", country: "말레이시아", continent: "아시아", lat: 5.93, lon: 116.05 },
        "SIN": { name: "싱가포르", country: "싱가포르", continent: "아시아", lat: 1.36, lon: 103.99 },
        "DPS": { name: "발리", country: "인도네시아", continent: "아시아", lat: -8.74, lon: 115.16 },
        "CGK": { name: "자카르타", country: "인도네시아", continent: "아시아", lat: -6.12, lon: 106.65 },

        // 중화권
        "HKG": { name: "홍콩", country: "홍콩", continent: "아시아", lat: 22.30, lon: 113.91 },
        "MFM": { name: "마카오", country: "마카오", continent: "아시아", lat: 22.14, lon: 113.59 },
        "TPE": { name: "타이베이(타오위안)", country: "대만", continent: "아시아", lat: 25.07, lon: 121.23 },
        "TSA": { name: "타이베이(송산)", country: "대만", continent: "아시아", lat: 25.06, lon: 121.55 },
        "RMQ": { name: "타이중", country: "대만", continent: "아시아", lat: 24.26, lon: 120.62 },
        "KHH": { name: "가오슝", country: "대만", continent: "아시아", lat: 22.57, lon: 120.35 },
        "TNN": { name: "타이난", country: "대만", continent: "아시아", lat: 22.95, lon: 120.20 },
        "PEK": { name: "베이징(서우두)", country: "중국", continent: "아시아", lat: 40.07, lon: 116.59 },
        "PKX": { name: "베이징(다싱)", country: "중국", continent: "아시아", lat: 39.50, lon: 116.41 },
        "PVG": { name: "상하이(푸둥)", country: "중국", continent: "아시아", lat: 31.14, lon: 121.80 },
        "SHA": { name: "상하이(훙차오)", country: "중국", continent: "아시아", lat: 31.19, lon: 121.33 },
        "WNZ": { name: "원저우", country: "중국", continent: "아시아", lat: 27.91, lon: 120.85 },
        "SHE": { name: "선양", country: "중국", continent: "아시아", lat: 41.63, lon: 123.48 },
        "WUH": { name: "우한", country: "중국", continent: "아시아", lat: 30.78, lon: 114.20 },
        "DYG": { name: "장자제", country: "중국", continent: "아시아", lat: 29.10, lon: 110.44 },
        "TAO": { name: "칭다오", country: "중국", continent: "아시아", lat: 36.26, lon: 120.37 },
        "TNA": { name: "지난", country: "중국", continent: "아시아", lat: 36.85, lon: 116.97 },
        "YNJ": { name: "연길(옌지)", country: "중국", continent: "아시아", lat: 42.88, lon: 129.45 },
        "TSN": { name: "톈진", country: "중국", continent: "아시아", lat: 39.12, lon: 117.34 },
        "HAK": { name: "하이커우", country: "중국", continent: "아시아", lat: 19.93, lon: 110.45 },
        "SYX": { name: "싼야", country: "중국", continent: "아시아", lat: 18.30, lon: 109.41 },
        "XMN": { name: "샤먼", country: "중국", continent: "아시아", lat: 24.54, lon: 118.12 },
        "CTU": { name: "청두", country: "중국", continent: "아시아", lat: 30.57, lon: 103.94 },
        "KMG": { name: "쿤밍", country: "중국", continent: "아시아", lat: 25.10, lon: 102.92 },

        // 중앙/북/남아시아 및 중동
        "UBN": { name: "울란바토르", country: "몽골", continent: "아시아", lat: 47.64, lon: 106.82 },
        "ULN": { name: "울란바토르(구)", country: "몽골", continent: "아시아", lat: 47.84, lon: 106.76 },
        "KHV": { name: "하바롭스크", country: "러시아", continent: "아시아", lat: 48.52, lon: 135.18 },
        "VVO": { name: "블라디보스토크", country: "러시아", continent: "아시아", lat: 43.39, lon: 132.14 },
        "FRU": { name: "비슈케크", country: "키르기스스탄", continent: "아시아", lat: 43.06, lon: 74.47 },
        "TAS": { name: "타슈켄트", country: "우즈베키스탄", continent: "아시아", lat: 41.25, lon: 69.28 },
        "DAC": { name: "다카", country: "방글라데시", continent: "아시아", lat: 23.84, lon: 90.39 },
        "AUH": { name: "아부다비", country: "UAE", continent: "중동/기타", lat: 24.43, lon: 54.65 },

        // 유럽
        "ZAG": { name: "자그레브", country: "크로아티아", continent: "유럽", lat: 45.74, lon: 16.06 },
        "CDG": { name: "파리(샤를드골)", country: "프랑스", continent: "유럽", lat: 49.00, lon: 2.54 },
        "FCO": { name: "로마(피우미치노)", country: "이탈리아", continent: "유럽", lat: 41.80, lon: 12.23 },
        "BCN": { name: "바르셀로나", country: "스페인", continent: "유럽", lat: 41.29, lon: 2.07 },
        "FRA": { name: "프랑크푸르트", country: "독일", continent: "유럽", lat: 50.03, lon: 8.57 },
        "HAM": { name: "함부르크", country: "독일", continent: "유럽", lat: 53.63, lon: 9.98 },
        "BER": { name: "베를린", country: "독일", continent: "유럽", lat: 52.36, lon: 13.50 },
        "N3": { name: "아른슈타트(N3)", country: "독일", continent: "유럽", lat: 50.84, lon: 10.98 },
        "CWL": { name: "웨일스(GE)", country: "영국", continent: "유럽", lat: 51.39, lon: -3.34 },

        // 북미
        "YVR": { name: "밴쿠버", country: "캐나다", continent: "북미", lat: 49.19, lon: -123.18 },
        "STDAERO": { name: "댈러스(StandardAero)", country: "미국", continent: "북미", lat: 32.77, lon: -96.79 }
    };

    // --------------------------------------------------------
    // 6대 심사 분야 카테고리 메타데이터
    // DB 카테고리값 → cat1~cat6 매핑
    // --------------------------------------------------------
    const CATEGORY_META = [
        {
            key: "cat1",
            label: "국내 주재정비",
            color: "#58a6ff",
            icon: "fa-house",
            badgeClass: "cat-badge-1",
            rowClass: "cat-row-1",
            // DB에 저장된 category 값 목록 (부분일치 포함)
            match: ["국내주재", "국내 주재", "국내업체"]
        },
        {
            key: "cat2",
            label: "해외 주재정비",
            color: "#79c0ff",
            icon: "fa-plane",
            badgeClass: "cat-badge-2",
            rowClass: "cat-row-2",
            match: ["해외주재", "해외 주재", "해외운항지점"]
        },
        {
            key: "cat3",
            label: "국내 운항정비 위탁",
            color: "#3fb950",
            icon: "fa-screwdriver-wrench",
            badgeClass: "cat-badge-3",
            rowClass: "cat-row-3",
            match: ["국내운항", "국내 운항", "완전위탁"]
        },
        {
            key: "cat4",
            label: "해외 운항정비 위탁",
            color: "#39d353",
            icon: "fa-globe",
            badgeClass: "cat-badge-4",
            rowClass: "cat-row-4",
            match: ["해외운항", "해외 운항"]
        },
        {
            key: "cat5",
            label: "항공기 중정비 위탁",
            color: "#bc8cff",
            icon: "fa-gears",
            badgeClass: "cat-badge-5",
            rowClass: "cat-row-5",
            match: ["중정비", "중 정비"]
        },
        {
            key: "cat6",
            label: "엔진 중정비 위탁",
            color: "#f0883e",
            icon: "fa-fire-flame-curved",
            badgeClass: "cat-badge-6",
            rowClass: "cat-row-6",
            match: ["엔진", "엔좄", "engine"]
        }
    ];

    /**
     * DB category 문자열 → CATEGORY_META 항목 반환
     * 매핑 안 되면 null 반환
     */
    function resolveCategoryMeta(categoryStr) {
        if (!categoryStr) return null;
        const lower = categoryStr.toLowerCase().replace(/\s/g, "");
        for (const meta of CATEGORY_META) {
            for (const kw of meta.match) {
                if (lower.includes(kw.toLowerCase().replace(/\s/g, ""))) {
                    return meta;
                }
            }
        }
        return null;
    }

    /** 카테고리 배지 HTML 생성 */
    function getCategoryBadgeHtml(categoryStr) {
        const meta = resolveCategoryMeta(categoryStr);
        if (meta) {
            return `<span class="cat-badge ${meta.badgeClass}"><i class="fa-solid ${meta.icon}"></i> ${categoryStr}</span>`;
        }
        return `<span class="badge badge-blue" style="font-size:11px;">${categoryStr}</span>`;
    }

    function resolveStation(stationName, category) {
        if (!stationName) stationName = "";
        
        const matches = stationName.match(/\b([A-Z]{3})\b/g);
        if (matches) {
            for (const code of matches) {
                if (STATION_DB[code]) {
                    return { ...STATION_DB[code], code: code };
                }
            }
        }
        
        for (const [code, info] of Object.entries(STATION_DB)) {
            if (stationName.includes(info.name) || stationName.includes(code)) {
                return { ...info, code: code };
            }
        }

        if (category === "국내업체" || stationName.includes("기술") || stationName.includes("기획") || stationName.includes("자재") || stationName.includes("통제") || stationName.includes("운항정비")) {
            return { name: "서울(본사/공항)", country: "대한민국", continent: "아시아", lat: 37.56, lon: 126.97, code: "HQ" };
        }
        
        return { name: stationName, country: "기타", continent: "아시아", lat: 36.5, lon: 127.5, code: "ETC" };
    }

    function latLonToPercent(lat, lon) {
        // 태평양 중심 지도(map.webp) 기준 투영 (Left edge = -30° lon)
        const normLon = (lon - (-30) + 360) % 360;
        const xPct = (normLon / 360.0) * 100.0;
        
        // Miller 도법 기준 위도(lat) Y% 계산
        const rad = (lat * Math.PI) / 180.0;
        const millerY = 1.25 * Math.log(Math.tan(Math.PI / 4.0 + 0.4 * rad));
        const yPct = 56.0 - (millerY * 19.5);
        
        return { 
            x: Math.max(2, Math.min(98, xPct)), 
            y: Math.max(2, Math.min(98, yPct)) 
        };
    }

    // --------------------------------------------------------
    // 토스트 알림 헬퍼 함수
    // --------------------------------------------------------
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const icon = type === 'success' ? 'fa-circle-check' : (type === 'error' ? 'fa-triangle-exclamation' : 'fa-circle-info');
        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // --------------------------------------------------------
    // API 통신 공통 함수 (토큰 자동 첨부)
    // --------------------------------------------------------
    let currentUser = null;
    let authToken = localStorage.getItem("audit_auth_token") || "";

    async function apiFetch(url, options = {}) {
        try {
            const headers = options.headers || {};
            if (authToken) {
                headers["Authorization"] = `Bearer ${authToken}`;
            }
            if (options.body && typeof options.body === 'string' && !headers['Content-Type']) {
                headers['Content-Type'] = 'application/json';
            }
            options.headers = headers;

            const response = await fetch(url, options);
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                const errMsg = errData.detail || response.statusText;
                showToast(`오류: ${errMsg}`, 'error');
                return null;
            }
            return await response.json();
        } catch (error) {
            console.error("API 요청 실패:", error);
            showToast("서버와 통신할 수 없습니다. 백엔드 서버 상태를 확인해주세요.", 'error');
            return null;
        }
    }

    // --------------------------------------------------------
    // 네비게이션 및 탭 전환
    // --------------------------------------------------------
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            navItems.forEach(nav => nav.classList.remove("active"));
            tabPanes.forEach(pane => pane.classList.remove("active"));

            item.classList.add("active");
            currentTab = item.getAttribute("data-tab");
            const targetPane = document.getElementById(`tab-${currentTab}`);
            if (targetPane) targetPane.classList.add("active");

            updatePageTitles();
            loadTabData();
        });
    });

    function updatePageTitles() {
        if (currentTab === "dashboard") {
            pageTitle.textContent = "대시보드";
            pageSubtitle.textContent = `${selectedYear}년 품질심사 현황 및 글로벌 네트워크 위치입니다.`;
        } else if (currentTab === "mypage") {
            pageTitle.textContent = "내 심사 일정 (마이페이지)";
            pageSubtitle.textContent = "본인에게 배정된 심사 일정과 자격 만료/보수교육 주기를 확인합니다.";
        } else if (currentTab === "calendar") {
            pageTitle.textContent = "연간 세부 계획";
            pageSubtitle.textContent = `2026~2030년 5개년 자동 롤링 매트릭스 및 ${selectedYear}년 캘린더 계획입니다.`;
        } else if (currentTab === "list") {
            pageTitle.textContent = "월별 목록";
            pageSubtitle.textContent = `${selectedYear}년도 월별 예정 심사 대상 세부 목록입니다.`;
        } else if (currentTab === "manage") {
            pageTitle.textContent = "심사 대상 관리";
            pageSubtitle.textContent = "품질심사 대상 지점/업체 정보 및 운항/비운항 상태를 관리합니다.";
        } else if (currentTab === "auditors") {
            pageTitle.textContent = "품질심사원 관리";
            pageSubtitle.textContent = "심사원의 자격 상태, 보수교육 및 정기평가 주기를 시각적으로 추적 및 관리합니다.";
        } else if (currentTab === "users") {
            pageTitle.textContent = "계정 및 권한 관리";
            pageSubtitle.textContent = "시스템 관리자 및 심사원 계정 목록을 관리하고 비밀번호를 초기화합니다.";
        }
    }

    globalYearSelect.addEventListener("change", (e) => {
        selectedYear = e.target.value;
        if (calendarYearBadge) calendarYearBadge.textContent = `${selectedYear}년`;
        document.querySelectorAll(".current-year-label").forEach(el => el.textContent = selectedYear);
        updatePageTitles();
        loadTabData();
    });

    function loadTabData() {
        if (currentTab === "dashboard") {
            loadDashboardData();
        } else if (currentTab === "mypage") {
            loadMyPageData();
        } else if (currentTab === "calendar") {
            if (planSubView === "matrix") {
                loadMatrixData();
            } else if (planSubView === "year") {
                loadYearViewData();
            } else {
                loadCalendarData();
            }
        } else if (currentTab === "list") {
            loadListData();
        } else if (currentTab === "manage") {
            loadManageData();
        } else if (currentTab === "auditors") {
            loadAuditorData();
        } else if (currentTab === "users") {
            loadUsersTable();
        }
    }

    // --------------------------------------------------------
    // 1. 대시보드 데이터 렌더링
    // --------------------------------------------------------
    let latestDashboardData = null;
    async function loadDashboardData() {
        const data = await apiFetch(`/api/dashboard?year=${selectedYear}`);
        if (!data) return;

        latestDashboardData = data;

        statTotal.textContent = data.stats.total;
        statDirect.textContent = data.stats.direct;
        statIndirect.textContent = data.stats.indirect;

        currentMonthLbl.textContent = data.current_month;
        monthCountBadge.textContent = `${data.this_month_audits.length}건`;

        thisMonthTableBody.innerHTML = "";
        if (data.this_month_audits.length === 0) {
            thisMonthTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-secondary);">이번 달 실시 예정인 심사가 없습니다.</td></tr>`;
        } else {
            data.this_month_audits.forEach(audit => {
                const tr = document.createElement("tr");
                tr.setAttribute("data-target-id", audit.target_id);
                tr.innerHTML = `
                    <td>${audit.category}</td>
                    <td><span class="badge ${audit.operation_status === '운항' ? 'badge-green' : 'badge-orange'}">${audit.operation_status}</span></td>
                    <td style="font-weight:600;">${audit.station_name}</td>
                    <td><span class="badge ${audit.audit_type === '직접' ? 'badge-blue' : 'badge-orange'}">${audit.symbol} ${audit.audit_type}</span></td>
                    <td>${audit.scheduled_date}</td>
                    <td><i class="fa-solid fa-user-gear"></i> ${audit.auditor || '-'}</td>
                    <td><span class="badge ${audit.status === '완료' ? 'badge-green' : 'badge-blue'}">${audit.status}</span></td>
                `;
                tr.addEventListener("mouseenter", () => highlightMapPin(audit.target_id, true));
                tr.addEventListener("mouseleave", () => highlightMapPin(audit.target_id, false));
                tr.addEventListener("click", () => openDetailModal(audit));
                thisMonthTableBody.appendChild(tr);
            });
        }

        renderWorldMap();

        // Monthly timeline bar chart on dashboard
        const calendarData = await apiFetch(`/api/calendar?year=${selectedYear}`);
        if (calendarData) {
            const tlBadge = document.getElementById("timeline-year-badge");
            if (tlBadge) tlBadge.textContent = `${selectedYear}년`;
            renderMonthlyTimelineChart(calendarData, "monthly-timeline-chart", null);
        }
    }

    // --------------------------------------------------------
    // 월드맵 렌더링
    // --------------------------------------------------------
    async function renderWorldMap() {
        if (!mapMarkersLayer || !latestDashboardData) return;

        if (mapYearLbl) mapYearLbl.textContent = `${selectedYear}년`;
        if (mapMonthLbl) mapMonthLbl.textContent = `${latestDashboardData.current_month}월`;

        let targetsToDisplay = [];
        if (mapFilterMode === "year") {
            targetsToDisplay = latestDashboardData.year_audits;
        } else if (mapFilterMode === "month") {
            targetsToDisplay = latestDashboardData.this_month_audits;
        } else if (mapFilterMode === "all") {
            if (allTargets.length === 0) {
                allTargets = await apiFetch("/api/targets");
            }
            targetsToDisplay = (allTargets || []).map(t => ({
                target_id: t.id,
                station_name: t.station_name,
                category: t.category,
                operation_status: t.operation_status,
                base_interval: t.base_interval,
                audit_type: "대상",
                symbol: "●",
                scheduled_date: "-",
                auditor: "",
                status: "등록",
                remarks: ""
            }));
        }

        const continentCounts = { "아시아": 0, "유럽": 0, "오세아니아": 0, "북미": 0, "중동/기타": 0 };
        const enrichedItems = targetsToDisplay.map(item => {
            const locInfo = resolveStation(item.station_name, item.category);
            const pos = latLonToPercent(locInfo.lat, locInfo.lon);
            const isThisMonth = latestDashboardData.this_month_audits.some(a => a.target_id === item.target_id);
            if (continentCounts[locInfo.continent] !== undefined) {
                continentCounts[locInfo.continent]++;
            }
            return { ...item, locInfo, pos, isThisMonth };
        });

        document.getElementById("count-asia").textContent = continentCounts["아시아"] || 0;
        document.getElementById("count-europe").textContent = continentCounts["유럽"] || 0;
        document.getElementById("count-oceania").textContent = continentCounts["오세아니아"] || 0;
        document.getElementById("count-north-america").textContent = continentCounts["북미"] || 0;
        document.getElementById("count-middle-east").textContent = continentCounts["중동/기타"] || 0;

        let filteredItems = enrichedItems;
        if (selectedContinent !== "all") {
            filteredItems = enrichedItems.filter(item => item.locInfo.continent === selectedContinent);
        }

        if (mapTargetCountBadge) {
            mapTargetCountBadge.textContent = `${filteredItems.length}개소`;
        }

        mapMarkersLayer.innerHTML = "";
        filteredItems.forEach(item => {
            const pin = document.createElement("div");
            pin.className = "map-pin";
            pin.setAttribute("data-target-id", item.target_id);
            pin.style.left = `${item.pos.x}%`;
            pin.style.top = `${item.pos.y}%`;

            let pinTypeClass = item.audit_type === "직접" ? "pin-direct" : "pin-indirect";
            if (item.operation_status === "비운항") pinTypeClass = "pin-inactive";
            pin.classList.add(pinTypeClass);

            if (item.isThisMonth) pin.classList.add("pin-pulse");

            pin.innerHTML = `
                <div class="pin-marker">
                    <span class="pin-symbol">${item.symbol || '●'}</span>
                </div>
                <div class="pin-label">${item.locInfo.code || item.station_name.substring(0, 4)}</div>
            `;

            pin.addEventListener("mouseenter", (e) => {
                showMapTooltip(item, e);
                highlightTableRow(item.target_id, true);
            });
            pin.addEventListener("mousemove", (e) => positionMapTooltip(e));
            pin.addEventListener("mouseleave", () => {
                hideMapTooltip();
                highlightTableRow(item.target_id, false);
            });
            pin.addEventListener("click", () => openDetailModal(item));

            mapMarkersLayer.appendChild(pin);
        });
    }

    function showMapTooltip(item, e) {
        if (!mapTooltip) return;

        const auditTypeBadge = item.audit_type === "직접" 
            ? '<span class="badge badge-blue">● 직접 심사</span>' 
            : '<span class="badge badge-orange">◎ 간접 심사</span>';

        const monthBadge = item.isThisMonth 
            ? '<span class="badge badge-accent" style="margin-left:4px;">🔥 이달의 심사</span>' 
            : '';

        mapTooltip.innerHTML = `
            <div class="tt-header">
                <span class="tt-title">${item.station_name}</span>
                <span>${auditTypeBadge}${monthBadge}</span>
            </div>
            <div class="tt-row"><span>국가/대륙</span><strong>${item.locInfo.country} (${item.locInfo.continent})</strong></div>
            <div class="tt-row"><span>심사 분야</span><strong>${item.category}</strong></div>
            <div class="tt-row"><span>운항 상태</span><strong>${item.operation_status}</strong></div>
            <div class="tt-row"><span>심사 예정일</span><strong>${item.scheduled_date || '-'}</strong></div>
            <div class="tt-row"><span>담당자</span><strong>${item.auditor || '미정'}</strong></div>
            <div class="tt-footer"><i class="fa-solid fa-arrow-pointer"></i> 클릭하여 상세 계획 및 롤링 수정</div>
        `;
        mapTooltip.style.display = "block";
        positionMapTooltip(e);
    }

    function positionMapTooltip(e) {
        if (!mapTooltip || !mapTooltip.parentElement) return;
        const rect = mapTooltip.parentElement.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        mapTooltip.style.left = `${mouseX}px`;
        mapTooltip.style.top = `${mouseY}px`;
    }

    function hideMapTooltip() {
        if (mapTooltip) mapTooltip.style.display = "none";
    }

    function highlightMapPin(targetId, isHighlight) {
        if (!mapMarkersLayer) return;
        const pins = mapMarkersLayer.querySelectorAll(`.map-pin[data-target-id="${targetId}"]`);
        pins.forEach(pin => {
            if (isHighlight) pin.classList.add("highlighted");
            else pin.classList.remove("highlighted");
        });
    }

    function highlightTableRow(targetId, isHighlight) {
        if (!thisMonthTableBody) return;
        const rows = thisMonthTableBody.querySelectorAll(`tr[data-target-id="${targetId}"]`);
        rows.forEach(r => {
            if (isHighlight) r.classList.add("row-map-highlight");
            else r.classList.remove("row-map-highlight");
        });
    }

    // 맵 컨트롤러 이벤트 바인딩
    if (mapViewFilterBtns) {
        mapViewFilterBtns.forEach(btn => {
            btn.addEventListener("click", async () => {
                mapViewFilterBtns.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                mapFilterMode = btn.getAttribute("data-filter");
                renderWorldMap();
            });
        });
    }

    if (continentPills) {
        continentPills.forEach(pill => {
            pill.addEventListener("click", () => {
                continentPills.forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                selectedContinent = pill.getAttribute("data-continent");
                renderWorldMap();
            });
        });
    }

    if (btnMapThemeDark && btnMapThemeLight && worldMapImg) {
        btnMapThemeDark.addEventListener("click", () => {
            btnMapThemeDark.classList.add("active");
            btnMapThemeLight.classList.remove("active");
            worldMapImg.src = "/static/map_continents_dark.webp";
            worldMapImg.classList.remove("light-theme");
            mapTheme = "dark";
        });

        btnMapThemeLight.addEventListener("click", () => {
            btnMapThemeLight.classList.add("active");
            btnMapThemeDark.classList.remove("active");
            worldMapImg.src = "/static/map_continents.webp";
            worldMapImg.classList.add("light-theme");
            mapTheme = "light";
        });
    }

    // --------------------------------------------------------
    // 2. 연간 세부 계획 (매트릭스 뷰 & 캘린더 뷰)
    // --------------------------------------------------------
    // 2.0 보기 모드 스위치 (matrix | year | calendar)
    function switchPlanView(view) {
        planSubView = view;
        [btnViewMatrix, btnViewYear, btnViewCalendar].forEach(b => b && b.classList.remove("active"));
        matrixViewContainer.style.display = view === "matrix" ? "block" : "none";
        if (yearViewContainer) yearViewContainer.style.display = view === "year" ? "block" : "none";
        calendarGrid.style.display = view === "calendar" ? "grid" : "none";

        if (view === "matrix") { btnViewMatrix && btnViewMatrix.classList.add("active"); loadMatrixData(); }
        else if (view === "year") { btnViewYear && btnViewYear.classList.add("active"); loadYearViewData(); }
        else { btnViewCalendar && btnViewCalendar.classList.add("active"); loadCalendarData(); }
    }

    if (btnViewMatrix) btnViewMatrix.addEventListener("click", () => switchPlanView("matrix"));
    if (btnViewYear) btnViewYear.addEventListener("click", () => switchPlanView("year"));
    if (btnViewCalendar) btnViewCalendar.addEventListener("click", () => switchPlanView("calendar"));

    // 2.1 2026~2030 5개년 롤링 매트릭스 렌더링
    async function loadMatrixData() {
        matrixTableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:30px;">2026~2030 5개년 롤링 스케줄을 계산 중입니다...</td></tr>`;
        const multiSchedule = await apiFetch(`/api/multi_year_schedule?start_year=2026&end_year=2030`);
        if (!multiSchedule) return;

        matrixTableBody.innerHTML = "";

        multiSchedule.forEach(item => {
            const tr = document.createElement("tr");
            if (item.operation_status === "비운항") {
                tr.style.opacity = "0.55";
                tr.style.backgroundColor = "rgba(0,0,0,0.15)";
            }

            const intervalBadge = item.base_interval === 1 
                ? '<span class="badge badge-accent" style="font-size:11px;">1년(매년직접)</span>' 
                : '<span class="badge badge-gray" style="font-size:11px;">2년(교차)</span>';

            let yearCellsHtml = "";
            for (let y = 2026; y <= 2030; y++) {
                const s = item.schedule[y];
                if (item.operation_status === "비운항") {
                    yearCellsHtml += `<td style="text-align:center; color:var(--text-secondary); font-size:11px;">-</td>`;
                } else if (s) {
                    const badgeClass = s.audit_type === "직접" ? "badge-blue" : "badge-orange";
                    const isManual = s.id ? '<i class="fa-solid fa-pen" style="font-size:8px; margin-left:2px;"></i>' : '';
                    yearCellsHtml += `
                        <td style="text-align:center;">
                            <button class="btn btn-xs ${badgeClass} matrix-cell-btn" 
                                data-target-id="${item.id}" 
                                data-station-name="${item.station_name}"
                                data-category="${item.category}"
                                data-op-status="${item.operation_status}"
                                data-year="${y}" 
                                data-audit-id="${s.id || ''}"
                                data-audit-type="${s.audit_type}"
                                data-status="${s.status}"
                                data-scheduled-date="${s.scheduled_date}"
                                data-auditor="${s.auditor || ''}"
                                data-remarks="${s.remarks || ''}"
                                title="${y}년 ${s.audit_type}심사 (${s.scheduled_date}) - 클릭 시 수정 및 롤링">
                                ${s.symbol} ${s.audit_type}${isManual}
                            </button>
                        </td>
                    `;
                } else {
                    yearCellsHtml += `
                        <td style="text-align:center;">
                            <button class="btn btn-xs btn-outline matrix-cell-empty-btn" 
                                data-target-id="${item.id}" 
                                data-station-name="${item.station_name}"
                                data-category="${item.category}"
                                data-op-status="${item.operation_status}"
                                data-year="${y}" 
                                title="${y}년 계획 수동 추가 (클릭 시 이후 롤링 계산)">
                                -
                            </button>
                        </td>
                    `;
                }
            }

            tr.innerHTML = `
                <td>${item.id}</td>
                <td><span class="badge badge-blue" style="font-size:11px;">${item.category}</span></td>
                <td><span class="badge ${item.operation_status === '운항' ? 'badge-green' : 'badge-orange'}" style="font-size:11px;">${item.operation_status}</span></td>
                <td style="font-weight:600;">${item.station_name}</td>
                <td>${intervalBadge}</td>
                ${yearCellsHtml}
            `;

            tr.querySelectorAll(".matrix-cell-btn").forEach(btn => {
                btn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const auditObj = {
                        id: btn.getAttribute("data-audit-id") ? parseInt(btn.getAttribute("data-audit-id")) : null,
                        target_id: parseInt(btn.getAttribute("data-target-id")),
                        station_name: btn.getAttribute("data-station-name"),
                        category: btn.getAttribute("data-category"),
                        operation_status: btn.getAttribute("data-op-status"),
                        audit_type: btn.getAttribute("data-audit-type"),
                        status: btn.getAttribute("data-status"),
                        scheduled_date: btn.getAttribute("data-scheduled-date"),
                        auditor: btn.getAttribute("data-auditor"),
                        remarks: btn.getAttribute("data-remarks")
                    };
                    selectedYear = btn.getAttribute("data-year");
                    globalYearSelect.value = selectedYear;
                    openDetailModal(auditObj);
                });
            });

            tr.querySelectorAll(".matrix-cell-empty-btn").forEach(btn => {
                btn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const targetYear = btn.getAttribute("data-year");
                    const auditObj = {
                        id: null,
                        target_id: parseInt(btn.getAttribute("data-target-id")),
                        station_name: btn.getAttribute("data-station-name"),
                        category: btn.getAttribute("data-category"),
                        operation_status: btn.getAttribute("data-op-status"),
                        audit_type: "직접",
                        status: "계획",
                        scheduled_date: `${targetYear}-06-01`,
                        auditor: "",
                        remarks: "수동 신규 편성"
                    };
                    selectedYear = targetYear;
                    globalYearSelect.value = selectedYear;
                    openDetailModal(auditObj);
                });
            });

            matrixTableBody.appendChild(tr);
        });
    }

    // 2.2 연간 12개월 캘린더 렌더링
    async function loadCalendarData() {
        calendarGrid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding: 50px;">${selectedYear}년 달력을 생성하는 중입니다...</div>`;
        const calendarData = await apiFetch(`/api/calendar?year=${selectedYear}`);
        if (!calendarData) return;

        calendarGrid.innerHTML = "";
        
        for (let month = 1; month <= 12; month++) {
            const monthBox = document.createElement("div");
            monthBox.className = "month-box";
            
            const monthTitle = document.createElement("div");
            monthTitle.className = "month-title";
            monthTitle.textContent = `${month}월`;
            monthBox.appendChild(monthTitle);
            
            const monthEvents = document.createElement("div");
            monthEvents.className = "month-events";
            
            const audits = calendarData[month] || [];
            if (audits.length === 0) {
                monthEvents.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-secondary); font-size:12px;">심사 없음</div>`;
            } else {
                audits.sort((a, b) => a.day - b.day);
                
                audits.forEach(audit => {
                    const eventCard = document.createElement("div");
                    eventCard.className = "month-event-card";
                    
                    let borderLeftColor = audit.audit_type === "직접" ? "var(--accent-blue)" : "var(--accent-orange)";
                    if (audit.status === "완료") {
                        borderLeftColor = "var(--accent-green)";
                        eventCard.style.background = "rgba(63, 185, 80, 0.05)";
                    }
                    eventCard.style.borderLeft = `4px solid ${borderLeftColor}`;
                    
                    eventCard.innerHTML = `
                        <div class="month-event-header">
                            <span class="event-day">${audit.day}일</span>
                            <span class="badge ${audit.status === '완료' ? 'badge-green' : 'badge-blue'}" style="font-size:8px; padding:2px 6px;">${audit.status}</span>
                        </div>
                        <div class="event-title" title="${audit.station_name}">${audit.station_name}</div>
                        <div class="event-meta">
                            <span>${audit.symbol} ${audit.audit_type}</span>
                            <span>${audit.auditor || '담당미정'}</span>
                        </div>
                    `;
                    eventCard.addEventListener("click", (e) => {
                        e.stopPropagation();
                        openDetailModal(audit);
                    });
                    monthEvents.appendChild(eventCard);
                });
            }
            
            monthBox.appendChild(monthEvents);
            calendarGrid.appendChild(monthBox);
        }
    }

    // --------------------------------------------------------
    // 2.3 월별 타임라인 바 차트 렌더링
    // --------------------------------------------------------
    function renderMonthlyTimelineChart(calendarData, containerId, onMonthClick) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];
        const maxCount = Math.max(1, ...MONTHS.map((_, i) => (calendarData[i+1] || []).length));
        const nowMonth = new Date().getMonth() + 1;

        const bars = MONTHS.map((m, i) => {
            const mn = i + 1;
            const audits = calendarData[mn] || [];
            const total = audits.length;
            const direct = audits.filter(a => a.audit_type === "직접").length;
            const indirect = total - direct;
            const barH = total > 0 ? Math.round((total / maxCount) * 84) : 0;
            const indirectH = total > 0 ? Math.round((indirect / total) * barH) : 0;
            const directH = barH - indirectH;
            const isCurrent = mn === nowMonth;

            return `
                <div class="tl-col${isCurrent ? ' tl-col-current' : ''}${onMonthClick ? ' tl-col-clickable' : ''}" 
                     data-month="${mn}" 
                     title="${m}: 직접 ${direct}건 / 간접 ${indirect}건 / 합계 ${total}건">
                    <div class="tl-bar-wrap">
                        ${barH > 0 ? `
                            <div class="tl-bar" style="height:${barH}px;">
                                ${indirectH > 0 ? `<div class="tl-bar-indirect" style="height:${indirectH}px;"></div>` : ''}
                                ${directH > 0 ? `<div class="tl-bar-direct" style="height:${directH}px;"></div>` : ''}
                            </div>
                        ` : `<div class="tl-bar-empty"></div>`}
                        <div class="tl-count">${total > 0 ? total : ''}</div>
                    </div>
                    <div class="tl-label">${m}</div>
                </div>
            `;
        }).join('');

        container.innerHTML = `<div class="tl-chart">${bars}</div>`;

        if (onMonthClick) {
            container.querySelectorAll(".tl-col-clickable").forEach(col => {
                col.addEventListener("click", () => onMonthClick(parseInt(col.getAttribute("data-month"))));
            });
        }
    }

    // --------------------------------------------------------
    // 2.4 연도별 상세 계획 뷰 (연도 탭 클릭 시 해당 1개년 목록)
    // --------------------------------------------------------
    async function loadYearViewData() {
        _yearViewCalendarCache = null;
        if (yearViewTitle) yearViewTitle.textContent = `${yearViewSelectedYear}년`;

        const calendarData = await apiFetch(`/api/calendar?year=${yearViewSelectedYear}`);
        if (!calendarData) return;
        _yearViewCalendarCache = calendarData;

        if (yearViewMode === "station") {
            // 지점별 뷰: 드롭다운 재구성 후 렌더링
            let allAudits = [];
            for (let m = 1; m <= 12; m++) {
                (calendarData[m] || []).forEach(a => allAudits.push({ ...a, _month: m }));
            }
            updateCategoryCountBadges(allAudits);
            renderCategorySummaryBar(allAudits);
            buildStationDropdowns(allAudits);
            renderStationGroupView(calendarData);
        } else {
            // 목록 뷰: 테이블 렌더링 (타임라인은 renderYearViewTable 내부에서 처리)
            renderYearViewTable(calendarData);
        }
    }

    function renderYearViewTable(calendarData) {
        if (!yearViewTableBody || !calendarData) return;
        const typeFilter = yearViewTypeFilter ? yearViewTypeFilter.value : "all";
        const monthFilter = yearViewMonthFilter ? parseInt(yearViewMonthFilter.value) : 0;

        // Flatten all months
        let allAudits = [];
        for (let m = 1; m <= 12; m++) {
            (calendarData[m] || []).forEach(a => allAudits.push({ ...a, _month: m }));
        }

        // 카테고리 건수 업데이트 (전체 기준)
        updateCategoryCountBadges(allAudits);

        // 카테고리 범례 바 렌더링
        renderCategorySummaryBar(allAudits);

        // Filter: 구분 + 월 + 카테고리
        const filtered = allAudits.filter(a => {
            if (monthFilter > 0 && a._month !== monthFilter) return false;
            if (typeFilter !== "all" && a.audit_type !== typeFilter) return false;
            if (yearViewCategoryFilter !== "all") {
                const meta = resolveCategoryMeta(a.category);
                if (!meta || meta.key !== yearViewCategoryFilter) return false;
            }
            return true;
        });

        if (yearViewCountBadge) yearViewCountBadge.textContent = `${filtered.length}건`;
        yearViewTableBody.innerHTML = "";

        if (filtered.length === 0) {
            yearViewTableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-secondary); padding:30px;">${yearViewSelectedYear}년 해당 조건의 심사 계획이 없습니다.</td></tr>`;
            return;
        }

        filtered.sort((a, b) => {
            // 카테고리 순 → 월 순 → 일 순
            const metaA = resolveCategoryMeta(a.category);
            const metaB = resolveCategoryMeta(b.category);
            const catIdxA = metaA ? CATEGORY_META.indexOf(metaA) : 99;
            const catIdxB = metaB ? CATEGORY_META.indexOf(metaB) : 99;
            if (catIdxA !== catIdxB) return catIdxA - catIdxB;
            return a._month - b._month || (a.day || 1) - (b.day || 1);
        });

        filtered.forEach(audit => {
            const tr = document.createElement("tr");
            const meta = resolveCategoryMeta(audit.category);
            if (meta) tr.classList.add(meta.rowClass);

            tr.innerHTML = `
                <td>${getCategoryBadgeHtml(audit.category)}</td>
                <td><span class="badge ${audit.operation_status === '운항' ? 'badge-green' : 'badge-orange'}" style="font-size:11px;">${audit.operation_status}</span></td>
                <td style="font-weight:600;">${audit.station_name}</td>
                <td><span class="badge ${audit.audit_type === '직접' ? 'badge-blue' : 'badge-orange'}">${audit.symbol} ${audit.audit_type}</span></td>
                <td style="text-align:center; font-weight:700; color:var(--accent-blue);">${audit._month}월</td>
                <td>${audit.scheduled_date || '-'}</td>
                <td><i class="fa-solid fa-user-gear" style="font-size:11px;"></i> ${audit.auditor || '-'}</td>
                <td><span class="badge ${audit.status === '완료' ? 'badge-green' : 'badge-blue'}" style="font-size:11px;">${audit.status}</span></td>
                <td style="font-size:11px; color:var(--text-secondary);">${audit.remarks || ''}</td>
            `;
            tr.style.cursor = "pointer";
            tr.addEventListener("click", () => openDetailModal({ ...audit, _month: undefined }));
            yearViewTableBody.appendChild(tr);
        });

        // 필터된 데이터로 미니 타임라인 재렌더링
        const filteredCalendarData = rebuildCalendarFromAudits(filtered);
        renderMonthlyTimelineChart(filteredCalendarData, "year-view-timeline", (month) => {
            if (yearViewMonthFilter) {
                yearViewMonthFilter.value = month;
                renderYearViewTable(_yearViewCalendarCache);
            }
        });
    }

    /** 카테고리별 건수 배지 업데이트 */
    function updateCategoryCountBadges(allAudits) {
        const el = id => document.getElementById(id);
        const counts = { all: allAudits.length };
        CATEGORY_META.forEach(m => { counts[m.key] = 0; });
        allAudits.forEach(a => {
            const meta = resolveCategoryMeta(a.category);
            if (meta) counts[meta.key] = (counts[meta.key] || 0) + 1;
        });
        if (el("cat-count-all")) el("cat-count-all").textContent = counts.all;
        CATEGORY_META.forEach(m => {
            const badge = el(`cat-count-${m.key}`);
            if (badge) badge.textContent = counts[m.key] || 0;
        });
    }

    /** 카테고리 범례 바 렌더링 */
    function renderCategorySummaryBar(allAudits) {
        const bar = document.getElementById("cat-summary-bar");
        if (!bar) return;
        const counts = {};
        allAudits.forEach(a => {
            const meta = resolveCategoryMeta(a.category);
            const key = meta ? meta.key : "etc";
            counts[key] = (counts[key] || 0) + 1;
        });
        bar.innerHTML = CATEGORY_META
            .filter(m => (counts[m.key] || 0) > 0)
            .map(m => `
                <span class="cat-summary-item">
                    <span class="cat-dot" style="background:${m.color};"></span>
                    ${m.label} <strong style="color:${m.color};">${counts[m.key]}</strong>건
                </span>
            `).join('<span style="color:var(--card-border); padding:0 4px;">|</span>');
    }

    /** flat 심사 배열 → {1:[],2:[],...12:[]} 재구성 */
    function rebuildCalendarFromAudits(audits) {
        const cal = {};
        for (let m = 1; m <= 12; m++) cal[m] = [];
        audits.forEach(a => {
            const m = a._month || a.month;
            if (m >= 1 && m <= 12) cal[m].push(a);
        });
        return cal;
    }

    // --------------------------------------------------------
    // 지점별 뷰 (Station Group View)
    // --------------------------------------------------------
    /** 국가/지점 드롭다운 동적 생성 */
    function buildStationDropdowns(allAudits) {
        const countrySet = new Set();
        const stationMap = {}; // country -> [{code, name}]

        allAudits.forEach(a => {
            const loc = resolveStation(a.station_name, a.category);
            if (!loc) return;
            countrySet.add(loc.country);
            if (!stationMap[loc.country]) stationMap[loc.country] = [];
            const exists = stationMap[loc.country].some(s => s.code === loc.code);
            if (!exists) stationMap[loc.country].push({ code: loc.code, name: loc.name, stationName: a.station_name });
        });

        const countrySel = document.getElementById("station-country-select");
        const codeSel = document.getElementById("station-code-select");
        if (!countrySel || !codeSel) return;

        // 국가 드롭다운
        const prevCountry = countrySel.value;
        countrySel.innerHTML = '<option value="all">전체 국가</option>';
        [...countrySet].sort().forEach(c => {
            const opt = document.createElement("option");
            opt.value = c;
            opt.textContent = c;
            countrySel.appendChild(opt);
        });
        if (prevCountry && countrySel.querySelector(`option[value="${prevCountry}"]`)) {
            countrySel.value = prevCountry;
        }

        // 지점 드롭다운 업데이트
        function updateCodeDropdown() {
            const selectedCountry = countrySel.value;
            const prevCode = codeSel.value;
            codeSel.innerHTML = '<option value="all">전체 지점</option>';
            const stations = selectedCountry === "all"
                ? Object.values(stationMap).flat()
                : (stationMap[selectedCountry] || []);
            // 중복 제거
            const seen = new Set();
            stations.forEach(s => {
                if (!seen.has(s.code)) {
                    seen.add(s.code);
                    const opt = document.createElement("option");
                    opt.value = s.code;
                    opt.textContent = `${s.code} (${s.name})`;
                    codeSel.appendChild(opt);
                }
            });
            if (prevCode && codeSel.querySelector(`option[value="${prevCode}"]`)) {
                codeSel.value = prevCode;
            }
        }

        countrySel.onchange = () => {
            stationCountryFilter = countrySel.value;
            updateCodeDropdown();
            renderStationGroupView(_yearViewCalendarCache);
        };
        codeSel.onchange = () => {
            stationCodeFilter = codeSel.value;
            renderStationGroupView(_yearViewCalendarCache);
        };

        updateCodeDropdown();
    }

    /** 지점별 계층 뷰 렌더링 */
    function renderStationGroupView(calendarData) {
        const container = document.getElementById("station-group-view");
        if (!container || !calendarData) return;

        // 필터 조건 적용하여 데이터 추출
        const typeFilter = yearViewTypeFilter ? yearViewTypeFilter.value : "all";
        const monthFilter = yearViewMonthFilter ? parseInt(yearViewMonthFilter.value) : 0;

        let allAudits = [];
        for (let m = 1; m <= 12; m++) {
            (calendarData[m] || []).forEach(a => allAudits.push({ ...a, _month: m }));
        }

        let filtered = allAudits.filter(a => {
            if (monthFilter > 0 && a._month !== monthFilter) return false;
            if (typeFilter !== "all" && a.audit_type !== typeFilter) return false;
            if (yearViewCategoryFilter !== "all") {
                const meta = resolveCategoryMeta(a.category);
                if (!meta || meta.key !== yearViewCategoryFilter) return false;
            }
            return true;
        });

        // 국가/지점 필터
        const enriched = filtered.map(a => {
            const loc = resolveStation(a.station_name, a.category);
            return { ...a, _loc: loc };
        });

        let stationFiltered = enriched;
        if (stationCountryFilter !== "all") {
            stationFiltered = enriched.filter(a => a._loc && a._loc.country === stationCountryFilter);
        }
        if (stationCodeFilter !== "all") {
            stationFiltered = stationFiltered.filter(a => a._loc && a._loc.code === stationCodeFilter);
        }

        // 건수 업데이트
        if (yearViewCountBadge) yearViewCountBadge.textContent = `${stationFiltered.length}건`;

        if (stationFiltered.length === 0) {
            container.innerHTML = `
                <div class="station-empty-state section-card">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    선택한 필터 조건에 해당하는 심사 계획이 없습니다.
                </div>`;
            return;
        }

        // 국가 → 지점코드 → 카테고리 순으로 그루핑
        const groupedByStation = {}; // key: "country||stationCode"
        stationFiltered.forEach(a => {
            const loc = a._loc || { country: "기타", code: "ETC", name: a.station_name };
            const key = `${loc.country}||${loc.code}`;
            if (!groupedByStation[key]) {
                groupedByStation[key] = { loc, audits: [] };
            }
            groupedByStation[key].audits.push(a);
        });

        // 지점 카드 렌더링
        container.innerHTML = "";
        Object.entries(groupedByStation)
            .sort(([, a], [, b]) => a.loc.country.localeCompare(b.loc.country) || a.loc.code.localeCompare(b.loc.code))
            .forEach(([, group]) => {
                const { loc, audits } = group;

                // 카테고리별 서브그룹
                const catGroups = {};
                audits.forEach(a => {
                    const meta = resolveCategoryMeta(a.category);
                    const catKey = meta ? meta.key : "etc";
                    if (!catGroups[catKey]) catGroups[catKey] = { meta, audits: [] };
                    catGroups[catKey].audits.push(a);
                });

                // 직접/간접 건수
                const directCnt = audits.filter(a => a.audit_type === "직접").length;
                const indirectCnt = audits.length - directCnt;

                const card = document.createElement("div");
                card.className = "station-group-card";

                // 헤더
                const header = document.createElement("div");
                header.className = "station-group-header";
                header.innerHTML = `
                    <div class="station-group-icon">
                        <i class="fa-solid fa-location-dot" style="color:var(--accent-blue);"></i>
                    </div>
                    <div class="station-group-info">
                        <div class="station-group-title">
                            ${loc.code}
                            <span style="font-size:13px; font-weight:400; color:var(--text-secondary);"> — ${loc.name}</span>
                            <span class="badge badge-accent" style="font-size:10px;">${audits.length}건</span>
                        </div>
                        <div class="station-group-meta">
                            <span><i class="fa-solid fa-flag" style="font-size:10px;"></i> ${loc.country}</span>
                            <span><i class="fa-solid fa-globe" style="font-size:10px;"></i> ${loc.continent || ''}</span>
                            ${directCnt > 0 ? `<span><span style="color:var(--accent-blue);">● 직접</span> ${directCnt}건</span>` : ''}
                            ${indirectCnt > 0 ? `<span><span style="color:var(--accent-orange);">◎ 간접</span> ${indirectCnt}건</span>` : ''}
                        </div>
                    </div>
                    <i class="fa-solid fa-chevron-down station-group-chevron"></i>
                `;

                // 클릭 시 펼치기/접기
                header.addEventListener("click", () => {
                    card.classList.toggle("collapsed");
                });

                // 본문: 카테고리별 소그룹
                const body = document.createElement("div");
                body.className = "station-group-body";

                CATEGORY_META.forEach(catMeta => {
                    const cg = catGroups[catMeta.key];
                    if (!cg) return;

                    const catGroupEl = document.createElement("div");
                    catGroupEl.className = "station-cat-group";
                    catGroupEl.innerHTML = `
                        <div class="station-cat-label">
                            <span class="cat-dot" style="background:${catMeta.color};"></span>
                            <i class="fa-solid ${catMeta.icon}" style="color:${catMeta.color};"></i>
                            ${catMeta.label} (${cg.audits.length}건)
                        </div>
                    `;

                    cg.audits.forEach(audit => {
                        const item = document.createElement("div");
                        item.className = "station-audit-item";
                        item.innerHTML = `
                            <span class="station-audit-name">${audit.station_name}</span>
                            <div class="station-audit-chips">
                                <span class="badge ${audit.audit_type === '직접' ? 'badge-blue' : 'badge-orange'}" style="font-size:10px;">
                                    ${audit.symbol} ${audit.audit_type}
                                </span>
                                <span class="badge badge-gray" style="font-size:10px;">${audit._month}월</span>
                                ${audit.scheduled_date ? `<span style="font-size:11px; color:var(--text-secondary);"><i class="fa-solid fa-calendar-check"></i> ${audit.scheduled_date}</span>` : ''}
                                <span class="badge ${audit.status === '완료' ? 'badge-green' : 'badge-blue'}" style="font-size:10px;">${audit.status}</span>
                                ${audit.auditor ? `<span style="font-size:11px; color:var(--text-secondary);"><i class="fa-solid fa-user"></i> ${audit.auditor}</span>` : ''}
                            </div>
                        `;
                        item.addEventListener("click", () => openDetailModal({ ...audit, _month: undefined }));
                        catGroupEl.appendChild(item);
                    });

                    body.appendChild(catGroupEl);
                });

                // 매핑 안된 카테고리도 표시
                if (catGroups["etc"]) {
                    const cg = catGroups["etc"];
                    const catGroupEl = document.createElement("div");
                    catGroupEl.className = "station-cat-group";
                    catGroupEl.innerHTML = `<div class="station-cat-label"><span class="cat-dot" style="background:#8b949e;"></span> 기타 (${cg.audits.length}건)</div>`;
                    cg.audits.forEach(audit => {
                        const item = document.createElement("div");
                        item.className = "station-audit-item";
                        item.innerHTML = `<span class="station-audit-name">${audit.station_name}</span>
                            <div class="station-audit-chips">
                                <span class="badge ${audit.audit_type === '직접' ? 'badge-blue' : 'badge-orange'}" style="font-size:10px;">${audit.symbol} ${audit.audit_type}</span>
                                <span class="badge badge-gray" style="font-size:10px;">${audit._month}월</span>
                            </div>`;
                        item.addEventListener("click", () => openDetailModal({ ...audit, _month: undefined }));
                        catGroupEl.appendChild(item);
                    });
                    body.appendChild(catGroupEl);
                }

                card.appendChild(header);
                card.appendChild(body);
                container.appendChild(card);
            });
    }

    // 연도 탭 이벤트 바인딩
    document.querySelectorAll("#year-tab-bar .year-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#year-tab-bar .year-tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            yearViewSelectedYear = parseInt(btn.getAttribute("data-year"));
            loadYearViewData();
        });
    });

    if (yearViewTypeFilter) yearViewTypeFilter.addEventListener("change", () => {
        if (yearViewMode === "list") renderYearViewTable(_yearViewCalendarCache);
        else renderStationGroupView(_yearViewCalendarCache);
    });
    if (yearViewMonthFilter) yearViewMonthFilter.addEventListener("change", () => {
        if (yearViewMode === "list") renderYearViewTable(_yearViewCalendarCache);
        else renderStationGroupView(_yearViewCalendarCache);
    });

    // 카테고리 탭 이벤트 바인딩
    document.querySelectorAll("#cat-filter-tabs .cat-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#cat-filter-tabs .cat-tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            yearViewCategoryFilter = btn.getAttribute("data-cat");
            if (yearViewMode === "list") renderYearViewTable(_yearViewCalendarCache);
            else renderStationGroupView(_yearViewCalendarCache);
        });
    });

    // 뷰 모드 토글 이벤트 바인딩
    const btnViewModeList = document.getElementById("btn-view-mode-list");
    const btnViewModeStation = document.getElementById("btn-view-mode-station");
    const stationFilterRow = document.getElementById("station-filter-row");
    const yearListViewSection = document.getElementById("year-list-view-section");
    const yearStationViewSection = document.getElementById("year-station-view-section");

    function switchYearViewMode(mode) {
        yearViewMode = mode;
        [btnViewModeList, btnViewModeStation].forEach(b => b && b.classList.remove("active"));
        if (mode === "list") {
            btnViewModeList && btnViewModeList.classList.add("active");
            if (stationFilterRow) stationFilterRow.style.display = "none";
            if (yearListViewSection) yearListViewSection.style.display = "block";
            if (yearStationViewSection) yearStationViewSection.style.display = "none";
            renderYearViewTable(_yearViewCalendarCache);
        } else {
            btnViewModeStation && btnViewModeStation.classList.add("active");
            if (stationFilterRow) stationFilterRow.style.display = "flex";
            if (yearListViewSection) yearListViewSection.style.display = "none";
            if (yearStationViewSection) yearStationViewSection.style.display = "block";
            // 드롭다운 구성 후 렌더링
            let allAudits = [];
            if (_yearViewCalendarCache) {
                for (let m = 1; m <= 12; m++) {
                    (_yearViewCalendarCache[m] || []).forEach(a => allAudits.push({ ...a, _month: m }));
                }
            }
            buildStationDropdowns(allAudits);
            renderStationGroupView(_yearViewCalendarCache);
        }
    }

    if (btnViewModeList) btnViewModeList.addEventListener("click", () => switchYearViewMode("list"));
    if (btnViewModeStation) btnViewModeStation.addEventListener("click", () => switchYearViewMode("station"));

    // --------------------------------------------------------
    // 3. 월별 필터 목록 데이터 렌더링
    // --------------------------------------------------------
    async function loadListData() {
        listTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;">데이터를 불러오는 중입니다...</td></tr>`;
        const selectedMonth = filterMonthSelect.value;
        const typeFilter = filterTypeSelect.value;
        
        const data = await apiFetch(`/api/list?year=${selectedYear}&month=${selectedMonth}`);
        if (!data) return;

        listTableBody.innerHTML = "";
        
        const filtered = data.filter(audit => {
            if (typeFilter === "all") return true;
            return audit.audit_type === typeFilter;
        });

        if (filtered.length === 0) {
            listTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-secondary);">${selectedYear}년 ${selectedMonth}월 예정 심사 일정이 없습니다.</td></tr>`;
            return;
        }

        filtered.forEach(audit => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${audit.category}</td>
                <td><span class="badge ${audit.operation_status === '운항' ? 'badge-green' : 'badge-orange'}">${audit.operation_status}</span></td>
                <td style="font-weight:600;">${audit.station_name}</td>
                <td><span class="badge ${audit.audit_type === '직접' ? 'badge-blue' : 'badge-orange'}">${audit.symbol} ${audit.audit_type}</span></td>
                <td>${audit.scheduled_date}</td>
                <td><i class="fa-solid fa-user-gear"></i> ${audit.auditor || '-'}</td>
                <td><span class="badge ${audit.status === '완료' ? 'badge-green' : 'badge-blue'}">${audit.status}</span></td>
            `;
            tr.addEventListener("click", () => openDetailModal(audit));
            listTableBody.appendChild(tr);
        });
    }

    filterMonthSelect.addEventListener("change", loadListData);
    filterTypeSelect.addEventListener("change", loadListData);

    // --------------------------------------------------------
    // 4. 모달 활성화 및 수동 입력 동적 롤링 (Reset & Roll-over)
    // --------------------------------------------------------
    function openDetailModal(audit) {
        document.getElementById("detail-id").value = audit.id || "";
        document.getElementById("detail-target-id").value = audit.target_id;
        document.getElementById("detail-year").value = selectedYear;
        
        document.getElementById("detail-station-name").value = audit.station_name;
        document.getElementById("detail-category").value = audit.category;
        document.getElementById("detail-op-status").value = audit.operation_status;
        
        document.getElementById("detail-audit-type").value = audit.audit_type || "직접";
        document.getElementById("detail-status").value = audit.status || "계획";
        
        document.getElementById("detail-scheduled-date").value = audit.scheduled_date || `${selectedYear}-06-01`;
        document.getElementById("detail-auditor").value = audit.auditor || "";
        document.getElementById("detail-remarks").value = audit.remarks || "";
        
        detailModal.classList.add("active");
    }

    function closeDetailModal() {
        detailModal.classList.remove("active");
        detailForm.reset();
    }

    btnCloseDetailModal.addEventListener("click", closeDetailModal);
    btnCancelDetailModal.addEventListener("click", closeDetailModal);
    
    detailForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            id: document.getElementById("detail-id").value ? parseInt(document.getElementById("detail-id").value) : null,
            target_id: parseInt(document.getElementById("detail-target-id").value),
            year: parseInt(document.getElementById("detail-year").value),
            audit_type: document.getElementById("detail-audit-type").value,
            status: document.getElementById("detail-status").value,
            scheduled_date: document.getElementById("detail-scheduled-date").value,
            auditor: document.getElementById("detail-auditor").value,
            remarks: document.getElementById("detail-remarks").value
        };
        
        const res = await apiFetch("/api/history/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (res && res.status === "success") {
            closeDetailModal();
            loadTabData();
        }
    });

    // --------------------------------------------------------
    // 5. 모달: 신규 기종/지점 이벤트 등록
    // --------------------------------------------------------
    async function loadTargetsToEventModal() {
        if (allTargets.length === 0) {
            allTargets = await apiFetch("/api/targets");
        }
        if (!allTargets) return;
        
        eventTargetSelect.innerHTML = '<option value="" disabled selected>대상을 선택하세요</option>';
        allTargets.forEach(t => {
            const opt = document.createElement("option");
            opt.value = t.id;
            opt.textContent = `[${t.category}] ${t.station_name} (${t.operation_status})`;
            eventTargetSelect.appendChild(opt);
        });
    }

    btnOpenEventModal.addEventListener("click", () => {
        loadTargetsToEventModal();
        eventModal.classList.add("active");
    });

    function closeEventModal() {
        eventModal.classList.remove("active");
        eventForm.reset();
    }

    btnCloseEventModal.addEventListener("click", closeEventModal);
    btnCancelEventModal.addEventListener("click", closeEventModal);

    eventForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            target_id: parseInt(eventTargetSelect.value),
            year: parseInt(document.getElementById("event-year-select").value),
            detail: document.getElementById("event-detail").value
        };
        
        const res = await apiFetch("/api/event/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (res && res.status === "success") {
            closeEventModal();
            alert("신규 이벤트가 성공적으로 등록되었으며 2026~2030년 롤링 스케줄이 자동 갱신(Reset & Roll-over)되었습니다.");
            loadTabData();
        }
    });

    // --------------------------------------------------------
    // --------------------------------------------------------
    // 6. 심사 대상 관리 (CRUD) + 기종/엔진 형식 필터 & 다중선택
    // --------------------------------------------------------
    const targetModal = document.getElementById("target-manage-modal");
    const targetForm = document.getElementById("target-manage-form");
    const btnOpenTargetModal = document.getElementById("btn-open-target-modal");
    const btnCloseTargetModal = document.getElementById("btn-close-target-modal");
    const btnCancelTargetModal = document.getElementById("btn-cancel-target-modal");
    const manageTableBody = document.getElementById("manage-table-body");
    const targetCountLbl = document.getElementById("target-count-lbl");
    const firstAuditFields = document.getElementById("first-audit-fields");
    const btnSubmitTarget = document.getElementById("btn-submit-target");

    // 필터 엘리먼트
    const manageFilterCategory = document.getElementById("manage-filter-category");
    const manageFilterAircraft = document.getElementById("manage-filter-aircraft");
    const manageFilterEngine = document.getElementById("manage-filter-engine");
    const manageSearchInput = document.getElementById("manage-search-input");

    // 기종/엔진 뱃지 렌더러
    function formatAircraftBadges(typesStr) {
        if (!typesStr || typesStr.trim() === "" || typesStr.toUpperCase() === "N/A") {
            return `<span class="badge-na">N/A</span>`;
        }
        const list = typesStr.split(",").map(s => s.trim()).filter(s => s.length > 0);
        if (list.length === 0) return `<span class="badge-na">N/A</span>`;
        const badges = list.map(ac => `<span class="badge-aircraft"><i class="fa-solid fa-plane"></i> ${ac}</span>`).join("");
        return `<div class="type-badges-container">${badges}</div>`;
    }

    function formatEngineBadges(typesStr) {
        if (!typesStr || typesStr.trim() === "" || typesStr.toUpperCase() === "N/A") {
            return `<span class="badge-na">N/A</span>`;
        }
        const list = typesStr.split(",").map(s => s.trim()).filter(s => s.length > 0);
        if (list.length === 0) return `<span class="badge-na">N/A</span>`;
        const badges = list.map(eng => `<span class="badge-engine"><i class="fa-solid fa-fire-flame-curved"></i> ${eng}</span>`).join("");
        return `<div class="type-badges-container">${badges}</div>`;
    }

    // 모달 태그 버튼 토글 도우미
    function setupTagToggle(btn) {
        const isSelected = btn.classList.toggle("selected");
        const icon = btn.querySelector("i");
        if (icon) {
            icon.className = isSelected ? "fa-solid fa-square-check" : "fa-regular fa-square";
        }
    }

    function setTagState(btn, select) {
        if (select) {
            btn.classList.add("selected");
            const icon = btn.querySelector("i");
            if (icon) icon.className = "fa-solid fa-square-check";
        } else {
            btn.classList.remove("selected");
            const icon = btn.querySelector("i");
            if (icon) icon.className = "fa-regular fa-square";
        }
    }

    // 태그 버튼 이벤트 리스너 바인딩
    document.querySelectorAll("#target-ac-tags-grid .type-check-btn, #target-eng-tags-grid .type-check-btn").forEach(btn => {
        btn.addEventListener("click", () => setupTagToggle(btn));
    });

    const btnAcSelectAll = document.getElementById("btn-ac-select-all");
    const btnAcClearAll = document.getElementById("btn-ac-clear-all");
    const btnEngSelectAll = document.getElementById("btn-eng-select-all");
    const btnEngClearAll = document.getElementById("btn-eng-clear-all");

    if (btnAcSelectAll) {
        btnAcSelectAll.addEventListener("click", () => {
            document.querySelectorAll("#target-ac-tags-grid .type-check-btn").forEach(btn => setTagState(btn, true));
        });
    }
    if (btnAcClearAll) {
        btnAcClearAll.addEventListener("click", () => {
            document.querySelectorAll("#target-ac-tags-grid .type-check-btn").forEach(btn => setTagState(btn, false));
        });
    }
    if (btnEngSelectAll) {
        btnEngSelectAll.addEventListener("click", () => {
            document.querySelectorAll("#target-eng-tags-grid .type-check-btn").forEach(btn => setTagState(btn, true));
        });
    }
    if (btnEngClearAll) {
        btnEngClearAll.addEventListener("click", () => {
            document.querySelectorAll("#target-eng-tags-grid .type-check-btn").forEach(btn => setTagState(btn, false));
        });
    }

    // 심사 대상 테이블 렌더링 (필터 적용)
    function renderManageTable() {
        if (!manageTableBody || !allTargets) return;

        const catFilter = manageFilterCategory ? manageFilterCategory.value : "all";
        const acFilter = manageFilterAircraft ? manageFilterAircraft.value : "all";
        const engFilter = manageFilterEngine ? manageFilterEngine.value : "all";
        const searchKeyword = manageSearchInput ? manageSearchInput.value.trim().toLowerCase() : "";

        const filtered = allTargets.filter(target => {
            // 카테고리 필터
            if (catFilter !== "all") {
                const meta = resolveCategoryMeta(target.category);
                if (!meta || !meta.match.some(m => m.includes(catFilter) || catFilter.includes(m))) {
                    // direct category string fallback
                    if (!target.category || !target.category.includes(catFilter)) {
                        return false;
                    }
                }
            }

            // 기종 필터
            if (acFilter !== "all") {
                const targetAc = (target.aircraft_types || "").toUpperCase();
                if (acFilter === "na") {
                    if (targetAc.length > 0 && targetAc !== "N/A") return false;
                } else {
                    if (!targetAc.includes(acFilter.toUpperCase())) return false;
                }
            }

            // 엔진 필터
            if (engFilter !== "all") {
                const targetEng = (target.engine_types || "").toUpperCase();
                if (engFilter === "na") {
                    if (targetEng.length > 0 && targetEng !== "N/A") return false;
                } else {
                    if (!targetEng.includes(engFilter.toUpperCase())) return false;
                }
            }

            // 검색어 필터
            if (searchKeyword.length > 0) {
                const name = (target.station_name || "").toLowerCase();
                const cat = (target.category || "").toLowerCase();
                const ac = (target.aircraft_types || "").toLowerCase();
                const eng = (target.engine_types || "").toLowerCase();
                if (!name.includes(searchKeyword) && !cat.includes(searchKeyword) && !ac.includes(searchKeyword) && !eng.includes(searchKeyword)) {
                    return false;
                }
            }

            return true;
        });

        if (targetCountLbl) targetCountLbl.textContent = filtered.length;
        manageTableBody.innerHTML = "";

        if (filtered.length === 0) {
            manageTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-secondary); padding:30px;"><i class="fa-solid fa-magnifying-glass"></i> 조건에 일치하는 심사 대상이 없습니다.</td></tr>`;
            return;
        }

        filtered.forEach(target => {
            const tr = document.createElement("tr");
            const intervalText = target.base_interval === 1 ? "1년(매년직접)" : "2년(교차)";
            
            tr.innerHTML = `
                <td>${target.id}</td>
                <td>${getCategoryBadgeHtml(target.category)}</td>
                <td style="font-weight:600;">${target.station_name}</td>
                <td>${formatAircraftBadges(target.aircraft_types)}</td>
                <td>${formatEngineBadges(target.engine_types)}</td>
                <td><span class="badge ${target.operation_status === '운항' ? 'badge-green' : 'badge-orange'}">${target.operation_status}</span></td>
                <td>${intervalText}</td>
                <td style="text-align:center;">
                    <button class="btn btn-secondary btn-xs btn-edit-target" style="margin-right:6px;"><i class="fa-solid fa-pen-to-square"></i> 수정</button>
                    <button class="btn btn-danger btn-xs btn-delete-target"><i class="fa-solid fa-trash-can"></i> 삭제</button>
                </td>
            `;
            
            tr.querySelector(".btn-edit-target").addEventListener("click", (e) => {
                e.stopPropagation();
                openTargetModal(target);
            });
            
            tr.querySelector(".btn-delete-target").addEventListener("click", (e) => {
                e.stopPropagation();
                deleteTarget(target.id, target.station_name);
            });
            
            manageTableBody.appendChild(tr);
        });
    }

    // 필터 변경 이벤트 등록
    if (manageFilterCategory) manageFilterCategory.addEventListener("change", renderManageTable);
    if (manageFilterAircraft) manageFilterAircraft.addEventListener("change", renderManageTable);
    if (manageFilterEngine) manageFilterEngine.addEventListener("change", renderManageTable);
    if (manageSearchInput) manageSearchInput.addEventListener("input", renderManageTable);

    async function loadManageData() {
        manageTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:30px;">심사 대상을 조회하고 있습니다...</td></tr>`;
        allTargets = await apiFetch("/api/targets");
        if (!allTargets) return;
        renderManageTable();
    }

    function openTargetModal(target = null) {
        if (target) {
            document.getElementById("target-modal-title").textContent = "심사 대상 정보 수정";
            document.getElementById("target-edit-id").value = target.id;
            document.getElementById("target-name-input").value = target.station_name;
            document.getElementById("target-category-select").value = target.category;
            document.getElementById("target-status-select").value = target.operation_status;
            document.getElementById("target-interval-input").value = target.base_interval;

            // 기종 태그 복원
            const targetAcs = (target.aircraft_types || "").split(",").map(s => s.trim().toUpperCase());
            document.querySelectorAll("#target-ac-tags-grid .type-check-btn").forEach(btn => {
                const val = btn.getAttribute("data-val").toUpperCase();
                setTagState(btn, targetAcs.includes(val));
            });

            // 엔진 태그 복원
            const targetEngs = (target.engine_types || "").split(",").map(s => s.trim().toUpperCase());
            document.querySelectorAll("#target-eng-tags-grid .type-check-btn").forEach(btn => {
                const val = btn.getAttribute("data-val").toUpperCase();
                setTagState(btn, targetEngs.includes(val));
            });
            
            firstAuditFields.style.display = "none";
            btnSubmitTarget.textContent = "수정하기";
        } else {
            document.getElementById("target-modal-title").textContent = "신규 심사 대상 등록";
            document.getElementById("target-edit-id").value = "";
            document.getElementById("target-name-input").value = "";
            document.getElementById("target-category-select").value = "해외운항지점";
            document.getElementById("target-status-select").value = "운항";
            document.getElementById("target-interval-input").value = "2";

            // 태그 초기화 (기본 B738 / CFM56 선택)
            document.querySelectorAll("#target-ac-tags-grid .type-check-btn").forEach(btn => {
                const val = btn.getAttribute("data-val");
                setTagState(btn, val === "B738");
            });
            document.querySelectorAll("#target-eng-tags-grid .type-check-btn").forEach(btn => {
                const val = btn.getAttribute("data-val");
                setTagState(btn, val === "CFM56");
            });
            
            firstAuditFields.style.display = "block";
            document.getElementById("target-first-date").value = "2026-06-01";
            document.getElementById("target-first-auditor").value = "";
            btnSubmitTarget.textContent = "등록하기";
        }
        targetModal.classList.add("active");
    }

    function closeTargetModal() {
        targetModal.classList.remove("active");
        targetForm.reset();
    }

    if (btnOpenTargetModal) btnOpenTargetModal.addEventListener("click", () => openTargetModal(null));
    if (btnCloseTargetModal) btnCloseTargetModal.addEventListener("click", closeTargetModal);
    if (btnCancelTargetModal) btnCancelTargetModal.addEventListener("click", closeTargetModal);

    targetForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const editId = document.getElementById("target-edit-id").value;
        const stationName = document.getElementById("target-name-input").value;
        const category = document.getElementById("target-category-select").value;
        const status = document.getElementById("target-status-select").value;
        const interval = parseInt(document.getElementById("target-interval-input").value);

        // 선택된 기종들 수집
        const selectedAcs = [];
        document.querySelectorAll("#target-ac-tags-grid .type-check-btn.selected").forEach(btn => {
            selectedAcs.push(btn.getAttribute("data-val"));
        });

        // 선택된 엔진들 수집
        const selectedEngs = [];
        document.querySelectorAll("#target-eng-tags-grid .type-check-btn.selected").forEach(btn => {
            selectedEngs.push(btn.getAttribute("data-val"));
        });
        
        let url = "/api/target/add";
        let payload = {
            category: category,
            station_name: stationName,
            operation_status: status,
            base_interval: interval,
            aircraft_types: selectedAcs.join(", "),
            engine_types: selectedEngs.join(", ")
        };
        
        if (editId) {
            url = "/api/target/update";
            payload.id = parseInt(editId);
        } else {
            payload.first_audit_type = document.getElementById("target-first-type").value;
            payload.first_scheduled_date = document.getElementById("target-first-date").value;
            payload.first_auditor = document.getElementById("target-first-auditor").value;
        }
        
        const res = await apiFetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (res && res.status === "success") {
            closeTargetModal();
            allTargets = [];
            loadManageData();
        }
    });

    async function deleteTarget(id, name) {
        if (confirm(`[경고] '${name}' 심사 대상을 정말 삭제하시겠습니까?\n삭제 시 이 대상에 연결된 모든 계획 일정 및 이력 데이터가 영구적으로 제거됩니다.`)) {
            const res = await apiFetch("/api/target/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: id })
            });
            
            if (res && res.status === "success") {
                allTargets = [];
                loadManageData();
            }
        }
    }

    // --------------------------------------------------------
    // 5. 심사원 관리 모듈
    // --------------------------------------------------------
    let allAuditors = [];
    let auditorFilter = "all"; // 'all' | 'action'

    // 만료일 프리빠 (+24개월 계산, JS 클라이언트육)
    function addMonthsJS(dateStr, months) {
        if (!dateStr) return null;
        const d = new Date(dateStr);
        if (isNaN(d)) return null;
        d.setMonth(d.getMonth() + months);
        return d.toISOString().slice(0, 10);
    }

    function formatDate(dateStr) {
        if (!dateStr) return '—';
        return dateStr.replace(/-/g, '.');
    }

    function statusBadgeHtml(status) {
        if (status === '만료') return '<span class="badge-status-expired"><i class="fa-solid fa-circle-xmark"></i> 만료</span>';
        if (status === '임박') return '<span class="badge-status-warning"><i class="fa-solid fa-triangle-exclamation"></i> 임박</span>';
        return '<span class="badge-status-normal"><i class="fa-solid fa-circle-check"></i> 정상</span>';
    }

    function ddayHtml(days) {
        if (days === null || days === undefined) return '';
        if (days < 0) return `<span class="dday-tag dday-expired">D+${Math.abs(days)}</span>`;
        if (days <= 180) return `<span class="dday-tag dday-warning">D-${days}</span>`;
        return `<span class="dday-tag dday-ok">D-${days}</span>`;
    }

    // 심사원 목록 로드
    async function loadAuditorData() {
        const data = await apiFetch('/api/auditors');
        if (!data) return;
        allAuditors = data;
        renderAuditorTable();
        updateAuditorStats();
    }

    function updateAuditorStats() {
        const total = allAuditors.length;
        const trainAlert = allAuditors.filter(a => a.refresh_status === '임박' || a.refresh_status === '만료').length;
        const evalAlert = allAuditors.filter(a => a.eval_status === '임박' || a.eval_status === '만료').length;

        document.getElementById('auditor-stat-total').textContent = total;
        document.getElementById('auditor-stat-train').textContent = trainAlert;
        document.getElementById('auditor-stat-eval').textContent = evalAlert;
        document.getElementById('auditor-count-badge').textContent = `${total}명`;
    }

    function renderAuditorTable() {
        const tbody = document.getElementById('auditor-table-body');
        let filtered = auditorFilter === 'action'
            ? allAuditors.filter(a => a.status === '임박' || a.status === '만료')
            : allAuditors;

        if (filtered.length === 0) {
            tbody.innerHTML = `<tr><td colspan="12" style="text-align:center; padding:40px; color:var(--text-secondary);">
                <i class="fa-solid fa-user-check" style="font-size:32px; margin-bottom:12px; display:block;"></i>
                ${ auditorFilter === 'action' ? '조치 필요 사항이 없습니다. 축하합니다! 관리가 잘 되고 있습니다.' : '등록된 심사원이 없습니다.'}
            </td></tr>`;
            return;
        }

        tbody.innerHTML = filtered.map((a, i) => {
            const rowClass = a.status === '만료' ? 'row-expired' : (a.status === '임박' ? 'row-warning' : '');
            const refreshDate = a.last_refresher_date || a.initial_training_date;
            const evalDate = a.last_eval_date || a.initial_eval_date;

            const refreshDueClass = a.refresh_status === '만료' ? 'date-expired' : (a.refresh_status === '임박' ? 'date-warning' : '');
            const evalDueClass = a.eval_status === '만료' ? 'date-expired' : (a.eval_status === '임박' ? 'date-warning' : '');

            return `<tr class="${rowClass}" style="cursor:default;">
                <td>${a.id}</td>
                <td>
                    <div style="font-weight:700;">${a.name_kr}</div>
                    <div style="font-size:11px; color:var(--text-secondary);">${a.name_en || ''}</div>
                </td>
                <td>${a.department || '—'}</td>
                <td><code style="font-size:12px;">${a.employee_id || '—'}</code></td>
                <td>${statusBadgeHtml(a.status)}</td>
                <td>${formatDate(refreshDate)}</td>
                <td class="${refreshDueClass}">${formatDate(a.next_refresher_due)}${ddayHtml(a.refresh_days_left)}</td>
                <td>${statusBadgeHtml(a.refresh_status)}</td>
                <td>${formatDate(evalDate)}</td>
                <td class="${evalDueClass}">${formatDate(a.next_eval_due)}${ddayHtml(a.eval_days_left)}</td>
                <td>${statusBadgeHtml(a.eval_status)}</td>
                <td style="text-align:center; white-space:nowrap;">
                    <button class="btn btn-secondary" style="padding:4px 10px; font-size:12px; margin-right:4px;" onclick="openAuditorModal(${a.id})">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="btn" style="padding:4px 10px; font-size:12px; background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3);" onclick="deleteAuditor(${a.id}, '${a.name_kr}')">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>`;
        }).join('');
    }

    // 필터 토글
    window.setAuditorFilter = function(mode) {
        auditorFilter = mode;
        document.getElementById('btn-auditor-filter-all').classList.toggle('active', mode === 'all');
        document.getElementById('btn-auditor-filter-action').classList.toggle('active', mode === 'action');
        renderAuditorTable();
    };

    // --- 알림 팝업 ---
    async function loadAndShowAlerts() {
        const data = await apiFetch('/api/auditors/alerts');
        if (!data || data.count === 0) return;

        // 사이드바 배지
        const badge = document.getElementById('nav-auditor-alert-count');
        badge.textContent = data.count;
        badge.style.display = 'inline-flex';

        // 팝업 내용 렌더링
        const list = document.getElementById('auditor-alert-list');
        list.innerHTML = data.alerts.map(a => {
            const isExpired = a.status === '만료';
            const cardClass = isExpired ? '' : 'alert-warning';
            const icon = isExpired ? '⚠️' : '🔔';
            const msgs = a.messages.map(m => `<div class="alert-card-msg">▸ ${m}</div>`).join('');
            return `<div class="alert-card ${cardClass}">
                <div class="alert-card-icon">${icon}</div>
                <div class="alert-card-body">
                    <div class="alert-card-name">${a.name_kr} <span style="font-size:12px; font-weight:400; color:var(--text-secondary);">(${a.name_en || ''} / ${a.employee_id || ''})</span></div>
                    <div class="alert-card-sub">${a.department || ''}</div>
                    <div class="alert-card-messages">${msgs}</div>
                </div>
            </div>`;
        }).join('');

        // 팝업 열기
        document.getElementById('auditor-alert-modal').classList.add('active');
    }

    document.getElementById('btn-close-auditor-alert').addEventListener('click', () => {
        document.getElementById('auditor-alert-modal').classList.remove('active');
    });
    document.getElementById('btn-close-auditor-alert2').addEventListener('click', () => {
        document.getElementById('auditor-alert-modal').classList.remove('active');
    });
    document.getElementById('btn-goto-auditor-tab').addEventListener('click', () => {
        document.getElementById('auditor-alert-modal').classList.remove('active');
        // 심사원 탭으로 이동
        navItems.forEach(nav => nav.classList.remove('active'));
        tabPanes.forEach(pane => pane.classList.remove('active'));
        const navAuditors = document.querySelector('[data-tab="auditors"]');
        if (navAuditors) navAuditors.classList.add('active');
        document.getElementById('tab-auditors').classList.add('active');
        currentTab = 'auditors';
        updatePageTitles();
        loadAuditorData();
    });

    // --- CRUD 모달 ---
    const auditorManageModal = document.getElementById('auditor-manage-modal');
    const auditorManageForm = document.getElementById('auditor-manage-form');

    function openAuditorModal(id) {
        auditorManageForm.reset();
        document.getElementById('refresher-due-preview').textContent = '— 날짜 입력 후 자동 표시됩니다 —';
        document.getElementById('eval-due-preview').textContent = '— 날짜 입력 후 자동 표시됩니다 —';

        if (id) {
            const a = allAuditors.find(x => x.id === id);
            if (!a) return;
            document.getElementById('auditor-modal-title').innerHTML = '<i class="fa-solid fa-pen-to-square"></i> 심사원 정보 수정';
            document.getElementById('btn-submit-auditor').textContent = '저장하기';
            document.getElementById('auditor-edit-id').value = id;
            document.getElementById('auditor-name-kr').value = a.name_kr || '';
            document.getElementById('auditor-name-en').value = a.name_en || '';
            document.getElementById('auditor-dept').value = a.department || '';
            document.getElementById('auditor-emp-id').value = a.employee_id || '';
            document.getElementById('auditor-contact').value = a.contact || '';
            document.getElementById('auditor-qual').value = a.qualification || '';
            document.getElementById('auditor-cert').value = a.cert_number || '';
            document.getElementById('auditor-init-train').value = a.initial_training_date || '';
            document.getElementById('auditor-last-refresh').value = a.last_refresher_date || '';
            document.getElementById('auditor-init-eval').value = a.initial_eval_date || '';
            document.getElementById('auditor-last-eval').value = a.last_eval_date || '';
            document.getElementById('auditor-remarks').value = a.remarks || '';
            // 프리비유
            if (a.next_refresher_due) document.getElementById('refresher-due-preview').textContent = `활동 만료일: ${formatDate(a.next_refresher_due)}`;
            if (a.next_eval_due) document.getElementById('eval-due-preview').textContent = `평가 만료일: ${formatDate(a.next_eval_due)}`;
        } else {
            document.getElementById('auditor-modal-title').innerHTML = '<i class="fa-solid fa-id-badge"></i> 신규 심사원 등록';
            document.getElementById('btn-submit-auditor').textContent = '등록하기';
            document.getElementById('auditor-edit-id').value = '';
        }
        auditorManageModal.classList.add('active');
    }
    window.openAuditorModal = openAuditorModal;

    // 만료일 프리비유 (JS 실시간)
    window.previewRefresherDue = function() {
        const lastRefresh = document.getElementById('auditor-last-refresh').value;
        const initTrain = document.getElementById('auditor-init-train').value;
        const base = lastRefresh || initTrain;
        const due = addMonthsJS(base, 24);
        document.getElementById('refresher-due-preview').textContent = due
            ? `만료 예정일: ${formatDate(due)} (+24개월)`
            : '— 날짜 입력 후 자동 표시됩니다 —';
    };
    window.previewEvalDue = function() {
        const lastEval = document.getElementById('auditor-last-eval').value;
        const initEval = document.getElementById('auditor-init-eval').value;
        const base = lastEval || initEval;
        const due = addMonthsJS(base, 24);
        document.getElementById('eval-due-preview').textContent = due
            ? `만료 예정일: ${formatDate(due)} (+24개월)`
            : '— 날짜 입력 후 자동 표시됩니다 —';
    };

    // 모달 닫기
    document.getElementById('btn-close-auditor-modal').addEventListener('click', () => auditorManageModal.classList.remove('active'));
    document.getElementById('btn-cancel-auditor-modal').addEventListener('click', () => auditorManageModal.classList.remove('active'));
    document.getElementById('btn-open-auditor-modal').addEventListener('click', () => openAuditorModal(null));

    // 배경에서 닫기
    auditorManageModal.addEventListener('click', e => {
        if (e.target === auditorManageModal) auditorManageModal.classList.remove('active');
    });
    document.getElementById('auditor-alert-modal').addEventListener('click', e => {
        if (e.target === document.getElementById('auditor-alert-modal'))
            document.getElementById('auditor-alert-modal').classList.remove('active');
    });

    // 폼 제출
    auditorManageForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('auditor-edit-id').value;
        const payload = {
            name_kr: document.getElementById('auditor-name-kr').value.trim(),
            name_en: document.getElementById('auditor-name-en').value.trim(),
            department: document.getElementById('auditor-dept').value.trim(),
            employee_id: document.getElementById('auditor-emp-id').value.trim(),
            contact: document.getElementById('auditor-contact').value.trim(),
            qualification: document.getElementById('auditor-qual').value.trim(),
            cert_number: document.getElementById('auditor-cert').value.trim(),
            initial_training_date: document.getElementById('auditor-init-train').value || null,
            last_refresher_date: document.getElementById('auditor-last-refresh').value || null,
            initial_eval_date: document.getElementById('auditor-init-eval').value || null,
            last_eval_date: document.getElementById('auditor-last-eval').value || null,
            remarks: document.getElementById('auditor-remarks').value.trim(),
        };
        const url = id ? '/api/auditor/update' : '/api/auditor/add';
        if (id) payload.id = parseInt(id);

        const res = await apiFetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res && res.status === 'success') {
            auditorManageModal.classList.remove('active');
            loadAuditorData();
        }
    });

    window.deleteAuditor = async function(id, name) {
        if (confirm(`[경고] '${name}' 심사원을 정말 삭제하시겠습니까?\n삭제 시 모든 정보가 영구 제거됩니다.`)) {
            const res = await apiFetch('/api/auditor/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            });
            if (res && res.status === 'success') {
                showToast(`'${name}' 심사원이 삭제되었습니다.`, 'info');
                loadAuditorData();
            }
        }
    };

    // ========================================================
    // 인증 및 권한 관리 (Authentication & Role Management)
    // ========================================================
    const loginModal = document.getElementById('login-modal');
    const loginForm = document.getElementById('login-form');
    const changePwModal = document.getElementById('change-password-modal');
    const changePwForm = document.getElementById('change-password-form');
    const authLoggedIn = document.getElementById('auth-logged-in');
    const authLoggedOut = document.getElementById('auth-logged-out');
    const headerRoleChip = document.getElementById('header-role-chip');
    const headerUserName = document.getElementById('header-user-name');
    const btnOpenLoginModal = document.getElementById('btn-open-login-modal');
    const btnCloseLoginModal = document.getElementById('btn-close-login-modal');
    const btnCancelLogin = document.getElementById('btn-cancel-login');
    const btnOpenChangePw = document.getElementById('btn-open-change-pw');
    const btnCloseChangePw = document.getElementById('btn-close-password-modal');
    const btnCancelChangePw = document.getElementById('btn-cancel-password-modal');
    const btnLogout = document.getElementById('btn-logout');
    const navUsers = document.getElementById('nav-users');
    const sidebarUserCard = document.getElementById('sidebar-user-card');
    const sidebarUserName = document.getElementById('sidebar-user-name');
    const sidebarUserRole = document.getElementById('sidebar-user-role');

    // UI 업데이트: 로그인 상태에 따른 헤더 및 권한 요소 제어
    function updateAuthUI() {
        if (currentUser) {
            // 로그인 상태
            if (authLoggedIn) authLoggedIn.style.display = 'flex';
            if (authLoggedOut) authLoggedOut.style.display = 'none';
            if (sidebarUserCard) sidebarUserCard.style.display = 'flex';

            const isAdmin = currentUser.role === 'admin';
            
            if (headerRoleChip) {
                headerRoleChip.textContent = isAdmin ? '관리자' : '심사원';
                headerRoleChip.className = `role-chip ${isAdmin ? 'admin' : 'user'}`;
            }
            if (headerUserName) {
                headerUserName.textContent = currentUser.name + (currentUser.employee_id ? ` (${currentUser.employee_id})` : '');
            }
            if (sidebarUserName) sidebarUserName.textContent = currentUser.name;
            if (sidebarUserRole) sidebarUserRole.textContent = isAdmin ? '전체 관리자' : '공인 품질심사원';

            // 권한별 메뉴 가시성
            if (navUsers) navUsers.style.display = isAdmin ? 'flex' : 'none';
            document.querySelectorAll('.admin-only').forEach(el => {
                el.style.display = isAdmin ? '' : 'none';
            });
        } else {
            // 미로그인 (게스트/조회 모드)
            if (authLoggedIn) authLoggedIn.style.display = 'none';
            if (authLoggedOut) authLoggedOut.style.display = 'flex';
            if (sidebarUserCard) sidebarUserCard.style.display = 'none';
            if (navUsers) navUsers.style.display = 'none';
            document.querySelectorAll('.admin-only').forEach(el => {
                el.style.display = 'none';
            });
        }
    }

    // 서버에 세션 유효성 확인
    async function checkAuthStatus() {
        if (!authToken) {
            currentUser = null;
            updateAuthUI();
            return;
        }
        try {
            const res = await fetch('/api/auth/me', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            const data = await res.json();
            if (data && data.authenticated && data.user) {
                currentUser = data.user;
            } else {
                currentUser = null;
                authToken = "";
                localStorage.removeItem("audit_auth_token");
            }
        } catch (e) {
            currentUser = null;
        }
        updateAuthUI();
    }

    // 로그인 실행
    async function doLogin(username, password) {
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                authToken = data.token;
                currentUser = data.user;
                localStorage.setItem("audit_auth_token", authToken);
                updateAuthUI();
                if (loginModal) loginModal.classList.remove('active');
                showToast(`${currentUser.name}님, 환영합니다! (${currentUser.role === 'admin' ? '관리자 권한' : '심사원 권한'})`, 'success');
                
                // 로그인 후 현재 탭 갱신 (마이페이지일 경우 로드)
                loadTabData();
            } else {
                showToast(data.detail || '로그인 실패: 아이디와 비밀번호를 확인해주세요.', 'error');
            }
        } catch (e) {
            showToast('로그인 요청 중 통신 오류가 발생했습니다.', 'error');
        }
    }

    // 빠른 테스트 로그인 (전역 바인딩)
    window.quickLogin = function(username, password) {
        document.getElementById('login-username').value = username;
        document.getElementById('login-password').value = password;
        doLogin(username, password);
    };

    // 로그아웃
    async function doLogout() {
        if (confirm('로그아웃 하시겠습니까?')) {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${authToken}` }
            }).catch(() => {});
            
            authToken = "";
            currentUser = null;
            localStorage.removeItem("audit_auth_token");
            updateAuthUI();
            showToast('로그아웃 되었습니다.', 'info');
            
            // 만약 관리자 탭이나 마이페이지에 있었다면 대시보드로 이동
            if (currentTab === 'users' || currentTab === 'mypage') {
                const dashNav = document.querySelector('[data-tab="dashboard"]');
                if (dashNav) dashNav.click();
            } else {
                loadTabData();
            }
        }
    }

    // 모달 이벤트 리스너 바인딩
    if (btnOpenLoginModal) btnOpenLoginModal.addEventListener('click', () => loginModal.classList.add('active'));
    if (btnCloseLoginModal) btnCloseLoginModal.addEventListener('click', () => loginModal.classList.remove('active'));
    if (btnCancelLogin) btnCancelLogin.addEventListener('click', () => loginModal.classList.remove('active'));
    if (loginModal) {
        loginModal.addEventListener('click', (e) => {
            if (e.target === loginModal) loginModal.classList.remove('active');
        });
    }

    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const u = document.getElementById('login-username').value.trim();
            const p = document.getElementById('login-password').value.trim();
            doLogin(u, p);
        });
    }

    if (btnLogout) btnLogout.addEventListener('click', doLogout);

    // 비밀번호 변경 모달 리스너
    if (btnOpenChangePw) btnOpenChangePw.addEventListener('click', () => {
        if (changePwForm) changePwForm.reset();
        if (changePwModal) changePwModal.classList.add('active');
    });
    if (btnCloseChangePw) btnCloseChangePw.addEventListener('click', () => changePwModal.classList.remove('active'));
    if (btnCancelChangePw) btnCancelChangePw.addEventListener('click', () => changePwModal.classList.remove('active'));
    if (changePwModal) {
        changePwModal.addEventListener('click', (e) => {
            if (e.target === changePwModal) changePwModal.classList.remove('active');
        });
    }

    if (changePwForm) {
        changePwForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const oldPw = document.getElementById('pw-current').value.trim();
            const newPw = document.getElementById('pw-new').value.trim();
            const confirmPw = document.getElementById('pw-new-confirm').value.trim();

            if (newPw !== confirmPw) {
                showToast('새 비밀번호와 비밀번호 확인이 일치하지 않습니다.', 'error');
                return;
            }

            const res = await apiFetch('/api/auth/change_password', {
                method: 'POST',
                body: JSON.stringify({ old_password: oldPw, new_password: newPw })
            });
            if (res && res.status === 'success') {
                showToast(res.message || '비밀번호가 변경되었습니다.', 'success');
                changePwModal.classList.remove('active');
            }
        });
    }

    // ========================================================
    // 심사원 전용 마이페이지 (My Page) 로직
    // ========================================================
    async function loadMyPageData() {
        if (!currentUser) {
            // 로그인되어 있지 않은 경우 로그인 모달 표시
            showToast('심사원 마이페이지를 이용하시려면 먼저 로그인해주세요.', 'info');
            if (loginModal) loginModal.classList.add('active');
            return;
        }

        // 프로필 정보 갱신
        document.getElementById('my-name-display').textContent = `${currentUser.name} 심사원`;
        document.getElementById('my-role-badge').textContent = currentUser.role === 'admin' ? '시스템 관리자' : '품질심사원';
        document.getElementById('my-dept-badge').textContent = currentUser.department || '정비품질보증팀';
        document.getElementById('my-empid-badge').textContent = currentUser.employee_id ? `사번: ${currentUser.employee_id}` : '관리자 계정';

        // 1. 심사원 상세 자격 정보 조회 (auditor_id 기반)
        if (currentUser.auditor_id) {
            const auditors = await apiFetch('/api/auditors');
            if (auditors) {
                const myAuditor = auditors.find(a => a.id === currentUser.auditor_id);
                if (myAuditor) {
                    renderMyQualificationCards(myAuditor);
                }
            }
        } else {
            // 관리자의 경우
            document.getElementById('my-refresher-due-display').textContent = '관리자 계정 (해당 없음)';
            document.getElementById('my-refresher-dday-badge').textContent = '정상';
            document.getElementById('my-refresher-dday-badge').className = 'qual-card-dday dday-normal';
            document.getElementById('my-eval-due-display').textContent = '관리자 계정 (해당 없음)';
            document.getElementById('my-eval-dday-badge').textContent = '정상';
            document.getElementById('my-eval-dday-badge').className = 'qual-card-dday dday-normal';
        }

        // 2. 본인 배정 일정 목록 조회
        const multiScheds = await apiFetch(`/api/multi_year_schedule?start_year=${selectedYear}&end_year=${selectedYear}`);
        const tbody = document.getElementById('my-schedule-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!multiScheds) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">일정을 불러올 수 없습니다.</td></tr>';
            return;
        }

        const myName = currentUser.name;
        const myEmpId = currentUser.employee_id;
        const myAudits = [];

        multiScheds.forEach(target => {
            const sched = target.schedule && target.schedule[parseInt(selectedYear)];
            if (sched && sched.status !== '비운항') {
                const auditorField = sched.auditor || '';
                // 이름이나 사번이 포함되어 있는지 확인
                const isAssigned = (myName && auditorField.includes(myName)) || 
                                   (myEmpId && auditorField.includes(myEmpId)) ||
                                   (currentUser.role === 'admin'); // 관리자는 전체 일정 참고 가능

                if (isAssigned) {
                    myAudits.push({
                        ...sched,
                        station_name: target.station_name,
                        category: target.category,
                        operation_status: target.operation_status
                    });
                }
            }
        });

        // 통계 지표 업데이트
        const directCount = myAudits.filter(a => a.audit_type === '직접').length;
        const indirectCount = myAudits.filter(a => a.audit_type === '간접').length;
        document.getElementById('my-total-audit-count').innerHTML = `${myAudits.length}<small>건</small>`;
        document.getElementById('my-direct-audit-count').innerHTML = `${directCount}<small>건</small>`;
        document.getElementById('my-indirect-audit-count').innerHTML = `${indirectCount}<small>건</small>`;

        if (myAudits.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4" style="color:var(--text-secondary);">${selectedYear}년에 배정된 심사 일정이 없습니다.</td></tr>`;
            return;
        }

        // 날짜순 정렬
        myAudits.sort((a, b) => (a.scheduled_date || '').localeCompare(b.scheduled_date || ''));

        myAudits.forEach(audit => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${audit.scheduled_date || '-'}</strong></td>
                <td style="font-weight:600; color:var(--text-primary);">${audit.station_name}</td>
                <td>${audit.category}</td>
                <td><span class="badge ${audit.audit_type === '직접' ? 'badge-blue' : 'badge-orange'}">${audit.symbol || ''} ${audit.audit_type}</span></td>
                <td><span class="badge ${audit.operation_status === '운항' ? 'badge-green' : 'badge-orange'}">${audit.operation_status}</span></td>
                <td><span class="badge ${audit.status === '완료' ? 'badge-green' : 'badge-blue'}">${audit.status}</span></td>
                <td><small style="color:var(--text-secondary);">${audit.remarks || '-'}</small></td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderMyQualificationCards(auditor) {
        // 보수교육
        const refDue = auditor.next_refresher_due || '-';
        const refDays = auditor.refresh_days_left;
        const refStatus = auditor.refresh_status || '정상';
        
        document.getElementById('my-refresher-due-display').textContent = `만료예정일: ${refDue}`;
        const refBadge = document.getElementById('my-refresher-dday-badge');
        if (refDays !== null && refDays !== undefined) {
            if (refDays < 0) {
                refBadge.textContent = `만료됨 (D+${Math.abs(refDays)}일 경과)`;
                refBadge.className = 'qual-card-dday dday-danger';
            } else {
                refBadge.textContent = `D-${refDays}일 남음 (${refStatus})`;
                refBadge.className = `qual-card-dday ${refStatus === '임박' ? 'dday-warning' : 'dday-normal'}`;
            }
        } else {
            refBadge.textContent = '일정 미등록';
            refBadge.className = 'qual-card-dday dday-normal';
        }

        // 정기평가
        const evalDue = auditor.next_eval_due || '-';
        const evalDays = auditor.eval_days_left;
        const evalStatus = auditor.eval_status || '정상';

        document.getElementById('my-eval-due-display').textContent = `만료예정일: ${evalDue}`;
        const evalBadge = document.getElementById('my-eval-dday-badge');
        if (evalDays !== null && evalDays !== undefined) {
            if (evalDays < 0) {
                evalBadge.textContent = `만료됨 (D+${Math.abs(evalDays)}일 경과)`;
                evalBadge.className = 'qual-card-dday dday-danger';
            } else {
                evalBadge.textContent = `D-${evalDays}일 남음 (${evalStatus})`;
                evalBadge.className = `qual-card-dday ${evalStatus === '임박' ? 'dday-warning' : 'dday-normal'}`;
            }
        } else {
            evalBadge.textContent = '일정 미등록';
            evalBadge.className = 'qual-card-dday dday-normal';
        }
    }

    const btnRefreshMySchedule = document.getElementById('btn-refresh-my-schedule');
    if (btnRefreshMySchedule) {
        btnRefreshMySchedule.addEventListener('click', loadMyPageData);
    }

    // ========================================================
    // 계정 및 권한 관리 (Users Management - Admin Only)
    // ========================================================
    async function loadUsersTable() {
        if (!currentUser || currentUser.role !== 'admin') {
            showToast('관리자 권한이 필요합니다.', 'error');
            return;
        }

        const users = await apiFetch('/api/users');
        const tbody = document.getElementById('users-table-body');
        const badge = document.getElementById('user-count-badge');
        if (!tbody) return;

        tbody.innerHTML = '';
        if (!users) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">계정 목록을 불러올 수 없습니다.</td></tr>';
            return;
        }

        if (badge) badge.textContent = `총 ${users.length}명`;

        users.forEach((user, idx) => {
            const tr = document.createElement('tr');
            const isAdmin = user.role === 'admin';
            tr.innerHTML = `
                <td>${idx + 1}</td>
                <td><code>${user.username}</code></td>
                <td><strong>${user.name}</strong></td>
                <td>${user.department || '-'}</td>
                <td><span class="role-chip ${isAdmin ? 'admin' : 'user'}">${isAdmin ? '관리자' : '심사원'}</span></td>
                <td><small>${user.qualification || user.cert_number || '-'}</small></td>
                <td><small style="color:var(--text-secondary);">${user.created_at || '-'}</small></td>
                <td style="text-align:center;">
                    <button class="btn btn-secondary btn-sm" onclick="resetUserPassword(${user.id}, '${user.name}', '${user.username}')" title="비밀번호 초기화">
                        <i class="fa-solid fa-rotate-left"></i> 비밀번호 초기화
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    window.resetUserPassword = async function(userId, name, username) {
        const newPw = prompt(`'${name}(${username})' 사용자의 비밀번호를 초기화합니다.\n설정할 초기 비밀번호를 입력해주세요:`, '1234');
        if (newPw === null) return;
        if (!newPw.trim()) {
            alert('비밀번호를 입력해주세요.');
            return;
        }

        const res = await apiFetch('/api/users/reset_password', {
            method: 'POST',
            body: JSON.stringify({ user_id: userId, new_password: newPw.trim() })
        });
        if (res && res.status === 'success') {
            showToast(res.message, 'success');
        }
    };

    const btnRefreshUsers = document.getElementById('btn-refresh-users');
    if (btnRefreshUsers) {
        btnRefreshUsers.addEventListener('click', loadUsersTable);
    }

    // --------------------------------------------------------
    // 초기 로딩 실행 (인증 확인 후 탭 로드)
    // --------------------------------------------------------
    checkAuthStatus().then(() => {
        loadTabData();
        setTimeout(() => loadAndShowAlerts(), 1200);
    });
});
