// ==================== 1. التهيئة وبيانات المستخدم ====================
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('#080712');
    if (tg.setBackgroundColor) tg.setBackgroundColor('#080712');
}

const urlParams = new URLSearchParams(window.location.search);
const tgUser = tg?.initDataUnsafe?.user;
const userName = tgUser ? `${tgUser.first_name || ''} ${tgUser.last_name || ''}`.trim() : (urlParams.get('name') || 'مستخدم خيال');
const userId = tgUser?.id || parseInt(urlParams.get('userId')) || 998877;
let userPoints = 500;

// عناصر الواجهة العلوية
const headerPointsVal = document.getElementById('headerPointsVal');
const storePointsBalance = document.getElementById('storePointsBalance');
const currentSectionTitle = document.getElementById('currentSectionTitle');

// مزامنة رصيد المستخدم من السيرفر
async function fetchUserProfile() {
    try {
        const res = await fetch(`/api/user/profile?userId=${userId}`);
        if (res.ok) {
            const data = await res.json();
            userPoints = data.points;
            updatePointsDisplay();
        }
    } catch (e) {
        console.warn('تعذر جلب الملف الشخصي:', e);
    }
}

function updatePointsDisplay() {
    if (headerPointsVal) headerPointsVal.innerText = userPoints.toLocaleString();
    if (storePointsBalance) storePointsBalance.innerText = userPoints.toLocaleString();
}

// ==================== 2. إدارة التبويبات (TAB SWITCHING) ====================
const tabs = {
    'crash': { title: 'لعبة الطيارة (Crash)' },
    'games': { title: 'ألعاب وتحدي الخصوم' },
    'radio': { title: 'راديو خيال FM المباشر' },
    'shop': { title: 'متجر ورصيد النقاط' },
    'call': { title: 'مكالمة خيال المباشرة' }
};

function switchTab(tabId) {
    if (!tabs[tabId]) return;

    // إخفاء كل التبويبات
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    // تفعيل التبويب المختار
    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) targetTab.classList.add('active');

    const navBtn = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (navBtn) navBtn.classList.add('active');

    if (currentSectionTitle) currentSectionTitle.innerText = tabs[tabId].title;

    // في حال الانتقال لقسم المكالمة نهيئ الكاميرا والمايك إذا لم تُهيأ
    if (tabId === 'call' && !localStream) {
        initCallMedia();
    }
}

// ==================== 3. محرك الصوت المولد (WEB AUDIO SYNTHESIZER) ====================
let audioCtx = null;
function getAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    return audioCtx;
}

function playTone(freq, type, duration) {
    try {
        const ctx = getAudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type || 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + duration);
    } catch (e) {}
}

function playExplosionSound() {
    try {
        const ctx = getAudioContext();
        const bufferSize = ctx.sampleRate * 0.5;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(800, ctx.currentTime);
        filter.frequency.linearRampToValueAtTime(50, ctx.currentTime + 0.5);
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.6, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
        noise.connect(filter);
        filter.connect(gain);
        gain.connect(ctx.destination);
        noise.start();
    } catch (e) {}
}

function playCashoutSound() {
    playTone(523.25, 'sine', 0.15); // C5
    setTimeout(() => playTone(659.25, 'sine', 0.15), 100); // E5
    setTimeout(() => playTone(783.99, 'sine', 0.25), 200); // G5
}

// ==================== 4. لعبة الطيارة (AVIATOR / CRASH) ====================
let crashState = 'idle'; // 'idle', 'flying', 'crashed'
let currentMultiplier = 1.00;
let crashPoint = 2.00;
let crashBet = 50;
let hasCashedOut = false;
let crashInterval = null;
let flightStartTime = null;

const rocketWrapper = document.getElementById('rocketWrapper');
const multiplierDisplay = document.getElementById('multiplierValue');
const flightStateTag = document.getElementById('flightStateTag');
const explosionFx = document.getElementById('explosionFx');
const crashActionBtn = document.getElementById('crashActionBtn');
const crashBtnTitle = document.getElementById('crashBtnTitle');
const crashBtnSub = document.getElementById('crashBtnSub');
const betInput = document.getElementById('betInput');
const crashHistoryBar = document.getElementById('crashHistoryBar');

function adjustBet(delta) {
    if (crashState === 'flying') return;
    let val = parseInt(betInput.value) || 50;
    val = Math.max(10, val + delta);
    betInput.value = val;
    updateBetSubText();
}

function setBetMax() {
    if (crashState === 'flying') return;
    betInput.value = Math.max(10, userPoints);
    updateBetSubText();
}

function updateBetSubText() {
    if (crashState === 'idle') {
        crashBtnSub.innerText = `رهان: ${betInput.value} نقطة`;
    }
}
if (betInput) betInput.addEventListener('input', updateBetSubText);

async function handleCrashAction() {
    if (crashState === 'idle') {
        // بدء الإقلاع
        const bet = parseInt(betInput.value) || 50;
        if (bet > userPoints) {
            alert('رصيدك غير كافٍ! اشحن نقاطك من المتجر أو خفّض الرهان.');
            return;
        }

        // خصم الرهان من السيرفر
        try {
            const res = await fetch('/api/games/crash/settle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId, action: 'bet', amount: bet })
            });
            const data = await res.json();
            if (!data.success) {
                alert(data.message);
                return;
            }
            userPoints = data.newPoints;
            updatePointsDisplay();
        } catch (e) {
            console.error(e);
            return;
        }

        crashBet = bet;
        startFlight();

    } else if (crashState === 'flying' && !hasCashedOut) {
        // سحب الأرباح قبل الانفجار
        cashOutEarnings();
    }
}

function startFlight() {
    crashState = 'flying';
    hasCashedOut = false;
    currentMultiplier = 1.00;
    explosionFx.classList.add('hidden');
    flightStateTag.innerText = 'الطيارة في الجو... 🚀';

    // توليد نقطة الانفجار عشوائياً (مع منحنيات واقعية للعبة Crash)
    const rand = Math.random();
    if (rand < 0.10) {
        crashPoint = +(1.05 + Math.random() * 0.2).toFixed(2); // 1.05x - 1.25x
    } else if (rand < 0.50) {
        crashPoint = +(1.25 + Math.random() * 1.5).toFixed(2); // 1.25x - 2.75x
    } else if (rand < 0.85) {
        crashPoint = +(2.75 + Math.random() * 3.5).toFixed(2); // 2.75x - 6.25x
    } else {
        crashPoint = +(6.25 + Math.random() * 12.0).toFixed(2); // 6.25x - 18.0x
    }

    // تحديث زر الأكشن إلى سحب الأرباح (Cash Out)
    crashActionBtn.className = 'btn-main-action cashout-btn';
    crashBtnTitle.innerText = '💰 سحب الأرباح (Cash Out)';
    crashBtnSub.innerText = `اربح ${Math.floor(crashBet * currentMultiplier)} نقطة`;

    flightStartTime = Date.now();
    crashInterval = setInterval(updateFlightFrame, 50);
}

function updateFlightFrame() {
    const elapsed = (Date.now() - flightStartTime) / 1000;
    // تزايد تسارعي للمضاعف
    currentMultiplier = +(1.00 + Math.pow(elapsed * 0.55, 1.8)).toFixed(2);

    if (currentMultiplier >= crashPoint) {
        triggerCrashExplosion();
        return;
    }

    multiplierDisplay.innerText = currentMultiplier.toFixed(2);
    if (!hasCashedOut) {
        const potentialWin = Math.floor(crashBet * currentMultiplier);
        crashBtnSub.innerText = `اربح ${potentialWin.toLocaleString()} نقطة`;
    }

    // تحريك الطائرة من اليسار باتجاه اليمين والأعلى
    const progress = Math.min(1, elapsed / 8);
    const moveX = progress * 160;
    const moveY = progress * 140;
    rocketWrapper.style.transform = `translate(${moveX}px, -${moveY}px) rotate(${progress * 18}deg)`;

    // صوت إقلاع مستمر خفيف
    if (Math.random() < 0.3) {
        playTone(200 + (currentMultiplier * 50), 'triangle', 0.05);
    }
}

async function cashOutEarnings() {
    hasCashedOut = true;
    const winMultiplier = currentMultiplier;
    const winAmount = Math.floor(crashBet * winMultiplier);

    playCashoutSound();
    flightStateTag.innerText = `تم السحب بنجاح! +${winAmount.toLocaleString()} نقطة 🎉`;

    // إرسال الأرباح للسيرفر
    try {
        const res = await fetch('/api/games/crash/settle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId, action: 'cashout', winAmount, multiplier: winMultiplier })
        });
        const data = await res.json();
        if (data.success) {
            userPoints = data.newPoints;
            updatePointsDisplay();
        }
    } catch (e) {
        console.error(e);
    }

    crashActionBtn.className = 'btn-main-action';
    crashBtnTitle.innerText = `✅ سحبت ${winAmount.toLocaleString()} نقطة`;
    crashBtnSub.innerText = 'انتظر انتهاء الجولة...';
}

function triggerCrashExplosion() {
    clearInterval(crashInterval);
    crashState = 'crashed';
    multiplierDisplay.innerText = crashPoint.toFixed(2);

    playExplosionSound();
    explosionFx.classList.remove('hidden');
    flightStateTag.innerText = `💥 انفجرت الطائرة عند ${crashPoint}x`;

    // إضافة للتاريخ
    addCrashHistoryBadge(crashPoint);

    if (!hasCashedOut) {
        crashActionBtn.className = 'btn-main-action';
        crashBtnTitle.innerText = '💥 انفجرت الطائرة!';
        crashBtnSub.innerText = `خسرت ${crashBet} نقطة`;
    }

    setTimeout(() => {
        resetCrashToIdle();
    }, 2500);
}

function resetCrashToIdle() {
    crashState = 'idle';
    hasCashedOut = false;
    currentMultiplier = 1.00;
    multiplierDisplay.innerText = '1.00';
    flightStateTag.innerText = 'جاهز للإقلاع';
    explosionFx.classList.add('hidden');
    rocketWrapper.style.transform = 'translate(0px, 0px) rotate(0deg)';

    crashActionBtn.className = 'btn-main-action fly-btn';
    crashBtnTitle.innerText = '🚀 إقلاع الطائرة';
    updateBetSubText();
}

function addCrashHistoryBadge(val) {
    if (!crashHistoryBar) return;
    const badge = document.createElement('span');
    let color = 'red';
    if (val >= 5) color = 'gold';
    else if (val >= 2) color = 'purple';
    else if (val >= 1.5) color = 'cyan';
    badge.className = `hist-badge ${color}`;
    badge.innerText = `${val.toFixed(2)}x`;
    crashHistoryBar.prepend(badge);
    if (crashHistoryBar.children.length > 8) {
        crashHistoryBar.removeChild(crashHistoryBar.lastChild);
    }
}

// ==================== 5. قسم الألعاب (GAMES HUB & MATCHMAKING) ====================
let currentGameSubView = 'xo';
let xoMode = 'solo'; // 'solo' or 'online'
let xoBoardState = ["", "", "", "", "", "", "", "", ""];
let isMyTurn = true;
let mySymbol = 'X';
let opponentSymbol = 'O';
let currentOnlineRoomId = null;
let currentMatchBet = 50;
let matchWs = null;

function switchGameMode(mode) {
    currentGameSubView = mode;
    document.querySelectorAll('.games-nav-pills .pill').forEach((btn, idx) => {
        btn.classList.toggle('active', (mode === 'xo' && idx === 0) || (mode === 'reflex' && idx === 1));
    });
    document.getElementById('game-xo-view').classList.toggle('hidden', mode !== 'xo');
    document.getElementById('game-reflex-view').classList.toggle('hidden', mode !== 'reflex');
}

// لعبة X-O الفردية ضد AI
function startSoloXO() {
    xoMode = 'solo';
    mySymbol = 'X';
    opponentSymbol = 'O';
    isMyTurn = true;
    xoBoardState = ["", "", "", "", "", "", "", "", ""];

    document.getElementById('xoModeSelector').classList.add('hidden');
    document.getElementById('activeMatchContainer').classList.remove('hidden');
    document.getElementById('p1Name').innerText = 'أنت (X)';
    document.getElementById('p2Name').innerText = 'الذكاء الاصطناعي (O)';
    document.getElementById('turnIndicator').innerText = 'دورك الآن للعب 🎯';
    renderXOBoard();
}

function handleCellClick(index) {
    if (xoBoardState[index] !== "" || !isMyTurn) return;

    // تسجيل حركة اللاعب
    makeXOMove(index, mySymbol);

    if (checkXOWin(mySymbol)) {
        document.getElementById('turnIndicator').innerText = 'مبروك! فزت بالمباراة 🏆';
        if (xoMode === 'online' && matchWs) {
            matchWs.send(JSON.stringify({ action: 'game_over', roomId: currentOnlineRoomId, winner: mySymbol }));
        }
        playCashoutSound();
        return;
    }

    if (isBoardFull()) {
        document.getElementById('turnIndicator').innerText = 'تعادل! لا يوجد فائز 🤝';
        if (xoMode === 'online' && matchWs) {
            matchWs.send(JSON.stringify({ action: 'game_over', roomId: currentOnlineRoomId, winner: 'draw' }));
        }
        return;
    }

    isMyTurn = false;
    document.getElementById('turnIndicator').innerText = 'دور الخصم للتفكير... ⏳';

    if (xoMode === 'solo') {
        // حركة الذكاء الاصطناعي
        setTimeout(makeAIMove, 600);
    } else if (xoMode === 'online' && matchWs) {
        // إرسال الحركة عبر WebSocket
        matchWs.send(JSON.stringify({
            action: 'make_move',
            roomId: currentOnlineRoomId,
            index: index,
            symbol: mySymbol
        }));
    }
}

function makeXOMove(index, symbol) {
    xoBoardState[index] = symbol;
    playTone(symbol === 'X' ? 440 : 330, 'sine', 0.1);
    renderXOBoard();
}

function makeAIMove() {
    // خوارزمية ذكاء اصطناعي بسيطة وسريعة
    const emptyIndices = xoBoardState.map((val, idx) => val === "" ? idx : null).filter(val => val !== null);
    if (emptyIndices.length === 0) return;

    // محاولة الفوز أو منع فوز الخصم
    let chosenIndex = null;
    for (let idx of emptyIndices) {
        xoBoardState[idx] = opponentSymbol;
        if (checkXOWin(opponentSymbol)) { chosenIndex = idx; }
        xoBoardState[idx] = "";
        if (chosenIndex !== null) break;
    }

    if (chosenIndex === null) {
        for (let idx of emptyIndices) {
            xoBoardState[idx] = mySymbol;
            if (checkXOWin(mySymbol)) { chosenIndex = idx; }
            xoBoardState[idx] = "";
            if (chosenIndex !== null) break;
        }
    }

    if (chosenIndex === null) {
        // إذا كان المركز فارغاً نأخذه
        if (xoBoardState[4] === "") chosenIndex = 4;
        else chosenIndex = emptyIndices[Math.floor(Math.random() * emptyIndices.length)];
    }

    makeXOMove(chosenIndex, opponentSymbol);

    if (checkXOWin(opponentSymbol)) {
        document.getElementById('turnIndicator').innerText = 'للأسف! فاز الخصم 😢';
        return;
    }

    if (isBoardFull()) {
        document.getElementById('turnIndicator').innerText = 'تعادل! 🤝';
        return;
    }

    isMyTurn = true;
    document.getElementById('turnIndicator').innerText = 'دورك الآن للعب 🎯';
}

function renderXOBoard() {
    const cells = document.querySelectorAll('.xo-cell');
    cells.forEach((cell, idx) => {
        const val = xoBoardState[idx];
        cell.innerText = val;
        cell.className = `xo-cell ${val ? val.toLowerCase() : ''}`;
    });
}

function checkXOWin(symbol) {
    const lines = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ];
    return lines.some(([a, b, c]) => xoBoardState[a] === symbol && xoBoardState[b] === symbol && xoBoardState[c] === symbol);
}

function isBoardFull() {
    return xoBoardState.every(c => c !== "");
}

function quitCurrentMatch() {
    if (xoMode === 'online' && matchWs) {
        matchWs.send(JSON.stringify({ action: 'cancel_search' }));
    }
    document.getElementById('activeMatchContainer').classList.add('hidden');
    document.getElementById('xoModeSelector').classList.remove('hidden');
}

// البحث عن خصم أونلاين (Online Matchmaking)
function showMatchmakingModal() {
    document.getElementById('matchModal').classList.remove('hidden');
}
function closeMatchModal() {
    if (matchWs) {
        matchWs.send(JSON.stringify({ action: 'cancel_search' }));
    }
    document.getElementById('matchModal').classList.add('hidden');
    document.getElementById('searchSpinner').style.display = 'none';
    document.getElementById('searchStatusText').innerText = 'اضغط لبدء البحث';
}

function selectMatchBet(amount) {
    currentMatchBet = amount;
    document.querySelectorAll('.bet-chips .chip').forEach(btn => {
        btn.classList.toggle('active', btn.innerText.includes(amount));
    });
}

function startMatchmaking() {
    if (userPoints < currentMatchBet) {
        alert('رصيدك غير كافٍ لهذا الرهان! اشحن نقاطك أولاً.');
        return;
    }

    document.getElementById('searchSpinner').style.display = 'block';
    document.getElementById('searchStatusText').innerText = 'جاري البحث عن خصم متاح داخل خيال...';

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    matchWs = new WebSocket(`${protocol}//${window.location.host}/ws/matchmaking`);

    matchWs.onopen = () => {
        matchWs.send(JSON.stringify({
            action: 'find_match',
            userId: userId,
            userName: userName,
            bet: currentMatchBet
        }));
    };

    matchWs.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.action === 'waiting_for_opponent') {
            document.getElementById('searchStatusText').innerText = 'في انتظار انضمام لاعب آخر... ⏳';
        } else if (data.action === 'match_found') {
            closeMatchModal();
            xoMode = 'online';
            currentOnlineRoomId = data.roomId;
            mySymbol = data.symbol;
            opponentSymbol = mySymbol === 'X' ? 'O' : 'X';
            isMyTurn = data.myTurn;
            xoBoardState = ["", "", "", "", "", "", "", "", ""];

            document.getElementById('xoModeSelector').classList.add('hidden');
            document.getElementById('activeMatchContainer').classList.remove('hidden');
            document.getElementById('p1Name').innerText = `${userName} (${mySymbol})`;
            document.getElementById('p2Name').innerText = `${data.opponentName} (${opponentSymbol})`;
            document.getElementById('turnIndicator').innerText = isMyTurn ? 'دورك الآن للعب! 🎯' : 'دور الخصم... ⏳';

            userPoints -= currentMatchBet;
            updatePointsDisplay();
            renderXOBoard();
        } else if (data.action === 'opponent_moved') {
            makeXOMove(data.index, data.symbol);
            if (!checkXOWin(data.symbol) && !isBoardFull()) {
                isMyTurn = true;
                document.getElementById('turnIndicator').innerText = 'دورك الآن للعب! 🎯';
            }
        } else if (data.action === 'opponent_left') {
            alert(data.message);
            fetchUserProfile();
            quitCurrentMatch();
        } else if (data.action === 'error') {
            alert(data.message);
            closeMatchModal();
        }
    };
}

// لعبة سرعة النيون (Reflex)
let reflexTimer = 20;
let reflexScore = 0;
let reflexInterval = null;

function startReflexGame() {
    reflexScore = 0;
    reflexTimer = 20;
    document.getElementById('reflexScore').innerText = '0';
    document.getElementById('reflexTimer').innerText = '20';
    document.getElementById('reflexStartOverlay').classList.add('hidden');
    document.getElementById('reflexTarget').classList.remove('hidden');

    repositionReflexTarget();

    reflexInterval = setInterval(() => {
        reflexTimer--;
        document.getElementById('reflexTimer').innerText = reflexTimer;
        if (reflexTimer <= 0) {
            clearInterval(reflexInterval);
            document.getElementById('reflexTarget').classList.add('hidden');
            document.getElementById('reflexStartOverlay').classList.remove('hidden');
            alert(`انتهى الوقت! أحرزت ${reflexScore} نقطة ⚡`);
        }
    }, 1000);
}

function hitReflexTarget() {
    reflexScore += 10;
    document.getElementById('reflexScore').innerText = reflexScore;
    playTone(600 + reflexScore * 10, 'sine', 0.08);
    repositionReflexTarget();
}

function repositionReflexTarget() {
    const box = document.getElementById('reflexBox');
    const target = document.getElementById('reflexTarget');
    const maxX = box.clientWidth - 50;
    const maxY = box.clientHeight - 50;
    target.style.left = `${Math.floor(Math.random() * maxX)}px`;
    target.style.top = `${Math.floor(Math.random() * maxY)}px`;
}

// ==================== 6. قسم راديو خيال FM ومسجل الصوت ====================
let radioAudio = document.getElementById('globalRadioAudio');
let isRadioPlaying = false;
let currentStation = null;
let mediaRecorder = null;
let recordedChunks = [];
let recordInterval = null;

async function loadRadioStations() {
    try {
        const res = await fetch('/api/radio/stations');
        const data = await res.json();
        const list = document.getElementById('stationsList');
        if (!list) return;

        list.innerHTML = '';
        data.stations.forEach((st, idx) => {
            const item = document.createElement('div');
            item.className = `station-item ${idx === 0 ? 'active' : ''}`;
            item.innerHTML = `
                <span class="st-icon">${st.icon}</span>
                <div class="st-info">
                    <h4>${st.name}</h4>
                    <span>${st.genre}</span>
                </div>
            `;
            item.onclick = () => selectStation(st, item);
            list.appendChild(item);

            if (idx === 0) currentStation = st;
        });
    } catch (e) {
        console.error('خطأ تحميل الإذاعات:', e);
    }
}

function selectStation(station, element) {
    currentStation = station;
    document.querySelectorAll('.station-item').forEach(el => el.classList.remove('active'));
    if (element) element.classList.add('active');

    document.getElementById('currentStationIcon').innerText = station.icon;
    document.getElementById('currentStationName').innerText = station.name;
    document.getElementById('currentStationGenre').innerText = station.genre;

    if (isRadioPlaying) {
        playCurrentStation();
    }
}

function toggleRadioPlay() {
    if (!currentStation) return;

    if (isRadioPlaying) {
        radioAudio.pause();
        isRadioPlaying = false;
        document.getElementById('playIcon').innerText = '▶️';
        document.getElementById('equalizerBars').classList.remove('playing');
    } else {
        playCurrentStation();
    }
}

function playCurrentStation() {
    radioAudio.src = currentStation.url;
    radioAudio.play().then(() => {
        isRadioPlaying = true;
        document.getElementById('playIcon').innerText = '⏸️';
        document.getElementById('equalizerBars').classList.add('playing');
    }).catch(err => {
        console.error('خطأ تشغيل المحطة:', err);
        tuneRadio(1, true);
    });
}

function setRadioVolume(val) {
    if (radioAudio) radioAudio.volume = parseFloat(val);
}


function tuneRadio(step=1, auto=false){
 const stations=[...document.querySelectorAll('.station-item')]; if(!stations.length)return;
 let i=stations.findIndex(x=>x.classList.contains('active')); if(i<0)i=0; i=(i+step+stations.length)%stations.length; stations[i].click();
 const f=document.getElementById('fmFrequency'); if(f)f.textContent=(87.5+(i*2.15)%20.4).toFixed(1)+' FM';
 if(!auto) playCurrentStation();
}

// مسجل الصوت
async function toggleRecording() {
    const btn = document.getElementById('recordBtn');
    const text = document.getElementById('recordBtnText');
    const player = document.getElementById('recordedAudio');
    const timer = document.getElementById('recordTimer');

    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        btn.classList.remove('recording');
        text.innerText = 'بدء التسجيل';
        clearInterval(recordInterval);
    } else {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            recordedChunks = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) recordedChunks.push(e.data);
            };

            mediaRecorder.onstop = () => {
                const blob = new Blob(recordedChunks, { type: 'audio/webm' });
                player.src = URL.createObjectURL(blob);
                player.classList.remove('hidden');
            };

            mediaRecorder.start();
            btn.classList.add('recording');
            text.innerText = 'إيقاف التسجيل ⏹️';

            let sec = 0;
            recordInterval = setInterval(() => {
                sec++;
                const mins = String(Math.floor(sec / 60)).padStart(2, '0');
                const secs = String(sec % 60).padStart(2, '0');
                timer.innerText = `${mins}:${secs}`;
            }, 1000);
        } catch (e) {
            alert('يرجى منح إذن استخدام الميكروفون للتسجيل.');
        }
    }
}

// ==================== 7. قسم المتجر وشراء النقاط ====================
async function claimDailyBonus() {
    try {
        const res = await fetch('/api/points/daily', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId })
        });
        const data = await res.json();
        if (data.success) {
            userPoints = data.points;
            updatePointsDisplay();
            playCashoutSound();
            alert(data.message);
        } else {
            alert(data.message);
        }
    } catch (e) {
        alert('حدث خطأ في استلام الهدية.');
    }
}

async function requestPackage(packageName, points, price) {
    if (!confirm(`هل تريد طلب شحن "${packageName}" (${points.toLocaleString()} نقطة) مقابل ${price}؟`)) return;

    try {
        const res = await fetch('/api/points/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                userId,
                userName,
                packageName,
                points,
                price
            })
        });
        const data = await res.json();
        if (data.success) {
            alert('✅ تم إرسال طلب الشحن بنجاح!\nسيقوم المشرف بمراجعته وتفعيل النقاط لحسابك قريباً.');
        } else {
            alert('تعذر إرسال الطلب.');
        }
    } catch (e) {
        alert('حدث خطأ في إرسال طلب الشحن.');
    }
}

// ==================== 8. قسم المكالمات (WEBRTC) ====================
let localStream = null;
let peerConnection = null;
let callWs = null;
let isAudioMuted = false;
let isVideoMuted = true;
const roomId = urlParams.get('room') || 'khayal-room';

const rtcConfig = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
    ]
};

async function initCallMedia() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
        });
        document.getElementById('localVideo').srcObject = localStream;
        localStream.getVideoTracks().forEach(t => t.enabled = false);
        connectCallSignaling();
    } catch (err) {
        console.warn('تعذر فتح الكاميرا، المحاولة بالصوت:', err);
        try {
            localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            connectCallSignaling();
        } catch (e) {
            console.error('تعذر الوصول للميكروفون');
        }
    }
}

function connectCallSignaling() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    callWs = new WebSocket(`${protocol}//${window.location.host}/ws/call/${roomId}`);

    callWs.onopen = () => {
        callWs.send(JSON.stringify({ type: 'join', room: roomId, userId, userName }));
    };

    callWs.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'peer-joined') {
            createCallPeerConnection();
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            callWs.send(JSON.stringify({ type: 'offer', room: roomId, offer, callerName: userName }));
        } else if (data.type === 'offer') {
            createCallPeerConnection();
            if (data.callerName) document.getElementById('remoteUserName').innerText = data.callerName;
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            callWs.send(JSON.stringify({ type: 'answer', room: roomId, answer }));
        } else if (data.type === 'answer') {
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
        } else if (data.type === 'candidate' && peerConnection) {
            await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
        } else if (data.type === 'peer-left') {
            document.getElementById('waitingCard').classList.remove('hidden');
        }
    };
}

function createCallPeerConnection() {
    if (peerConnection) return;
    peerConnection = new RTCPeerConnection(rtcConfig);
    if (localStream) {
        localStream.getTracks().forEach(t => peerConnection.addTrack(t, localStream));
    }
    peerConnection.onicecandidate = (e) => {
        if (e.candidate && callWs && callWs.readyState === WebSocket.OPEN) {
            callWs.send(JSON.stringify({ type: 'candidate', room: roomId, candidate: e.candidate }));
        }
    };
    peerConnection.ontrack = (e) => {
        document.getElementById('waitingCard').classList.add('hidden');
        const rVideo = document.getElementById('remoteVideo');
        rVideo.srcObject = e.streams[0];
        rVideo.classList.remove('hidden');
        document.getElementById('remoteAvatarCard').style.display = 'none';
    };
}

// أزرار المكالمة
document.getElementById('toggleMicBtn')?.addEventListener('click', () => {
    if (!localStream) return;
    const aTrack = localStream.getAudioTracks()[0];
    if (aTrack) {
        isAudioMuted = !isAudioMuted;
        aTrack.enabled = !isAudioMuted;
        document.getElementById('toggleMicBtn').classList.toggle('active', !isAudioMuted);
    }
});

document.getElementById('toggleCamBtn')?.addEventListener('click', () => {
    if (!localStream) return;
    const vTrack = localStream.getVideoTracks()[0];
    if (vTrack) {
        isVideoMuted = !isVideoMuted;
        vTrack.enabled = !isVideoMuted;
        document.getElementById('toggleCamBtn').classList.toggle('active', !isVideoMuted);
        document.getElementById('localContainer').classList.toggle('cam-off', isVideoMuted);
    }
});

document.getElementById('endCallBtn')?.addEventListener('click', () => {
    if (confirm('إنهاء المكالمة؟')) {
        if (callWs) callWs.send(JSON.stringify({ type: 'leave', room: roomId }));
        if (tg) tg.close();
        else switchTab('crash');
    }
});

// نسخ رابط المكالمة
document.getElementById('copyLinkBtn')?.addEventListener('click', () => {
    navigator.clipboard.writeText(window.location.href);
    alert('تم نسخ الرابط!');
});

// ==================== بدء التطبيق ====================
(async function init() {
    await fetchUserProfile();
    await loadRadioStations();

    // فحص التبويب الممرر في المسار
    const path = window.location.pathname.replace('/', '');
    if (tabs[path]) {
        switchTab(path);
    } else if (urlParams.get('tab') && tabs[urlParams.get('tab')]) {
        switchTab(urlParams.get('tab'));
    } else {
        switchTab('crash'); // التبويب الافتراضي هو لعبة الطيارة
    }
})();

// ==================== رومات خيال ====================
let socialRoomId=null, socialRoomWs=null, socialRoomData=null, roomLocalStream=null, roomMicMuted=false;
const roomPeers = new Map();
const roomKnownPeers = new Set();
tabs.rooms = {title:'رومات خيال'};

const _switchTab = switchTab;
switchTab = function(tabId){ _switchTab(tabId); if(tabId==='rooms' && !socialRoomId) loadSocialRooms(); };

async function loadSocialRooms(){
  const box=document.getElementById('roomsList'); if(!box)return; box.innerHTML='<div class="loader-spinner"></div>';
  try{ const r=await fetch('/api/rooms'); const d=await r.json(); box.innerHTML='';
    if(!d.rooms.length) box.innerHTML='<div class="room-cost-note">لا توجد رومات بعد — كن أول من ينشئ روم.</div>';
    d.rooms.forEach(x=>{ const el=document.createElement('div');el.className='room-card';
      const img=x.image_url||'/images/avatar.jpg'; el.innerHTML=`<img src="${escapeAttr(img)}"><div class="room-card-info"><h3>${escapeHtml(x.name)}</h3><p>${escapeHtml(x.description||'بدون نبذة')}</p><small>● ${x.online||0} متصل</small></div><button class="btn-secondary">دخول</button>`;
      el.querySelector('button').onclick=()=>enterSocialRoom(x.room_id);box.appendChild(el); });
  }catch(e){box.innerHTML='<div class="room-cost-note">تعذر تحميل الرومات.</div>'}
}
function escapeHtml(v){const d=document.createElement('div');d.textContent=v??'';return d.innerHTML} function escapeAttr(v){return String(v||'').replace(/"/g,'&quot;')}
function openCreateRoom(){document.getElementById('roomsDirectory').classList.add('hidden');document.getElementById('createRoomPanel').classList.remove('hidden')}
function closeCreateRoom(){document.getElementById('createRoomPanel').classList.add('hidden');document.getElementById('roomsDirectory').classList.remove('hidden')}
async function fileToDataUrl(file){return new Promise((ok,no)=>{if(!file)return ok('');const rd=new FileReader();rd.onload=()=>ok(rd.result);rd.onerror=no;rd.readAsDataURL(file)})}

async function compressRoomImage(file){
  const data=await fileToDataUrl(file); const img=new Image(); img.src=data; await img.decode();
  const max=640, scale=Math.min(1,max/Math.max(img.width,img.height));
  const c=document.createElement('canvas');c.width=Math.max(1,Math.round(img.width*scale));c.height=Math.max(1,Math.round(img.height*scale));
  c.getContext('2d').drawImage(img,0,0,c.width,c.height); return c.toDataURL('image/jpeg',.78);
}

async function createSocialRoom(){
 const name=document.getElementById('newRoomName').value.trim(), description=document.getElementById('newRoomDesc').value.trim();
 if(name.length<2)return alert('اكتب اسم الروم'); if(userPoints<300)return alert('رصيدك غير كافٍ. إنشاء الروم يحتاج 300 نقطة.');
 let imageUrl=''; const f=document.getElementById('newRoomImage').files[0]; if(f){if(f.size>3*1024*1024)return alert('صورة الروم يجب أن تكون أقل من 3MB');imageUrl=await compressRoomImage(f)}
 const r=await fetch('/api/rooms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId,userName,name,description,imageUrl})}); const d=await r.json();
 if(!r.ok)return alert(d.message||'تعذر إنشاء الروم'); userPoints=d.points;updatePointsDisplay();closeCreateRoom();await enterSocialRoom(d.roomId);
}
async function enterSocialRoom(rid){
 socialRoomId=rid; const r=await fetch(`/api/rooms/${encodeURIComponent(rid)}`); socialRoomData=await r.json();
 document.getElementById('roomsDirectory').classList.add('hidden');document.getElementById('createRoomPanel').classList.add('hidden');document.getElementById('roomInside').classList.remove('hidden');
 document.getElementById('insideRoomName').textContent=socialRoomData.name; document.getElementById('insideOnline').textContent=`${socialRoomData.online||0} متصل`;
 document.getElementById('roomSongAdmin').classList.toggle('hidden',Number(socialRoomData.owner_id)!==Number(userId)); renderRoomMessages(socialRoomData.messages||[]);renderSeats(socialRoomData.seats||{});renderSongs(socialRoomData.songs||[]);
 const proto=location.protocol==='https:'?'wss:':'ws:'; socialRoomWs=new WebSocket(`${proto}//${location.host}/ws/rooms/${encodeURIComponent(rid)}`);
 socialRoomWs.onopen=()=>socialRoomWs.send(JSON.stringify({type:'join',userId,userName})); socialRoomWs.onmessage=handleRoomWs;
}
function handleRoomWs(ev){const d=JSON.parse(ev.data);if(d.type==='chat')appendRoomMessage(d);if(d.type==='seats')renderSeats(d.seats);if(d.type==='presence'){document.getElementById('insideOnline').textContent=`${d.online} متصل`;(d.peers||[]).forEach(p=>{if(Number(p.userId)!==Number(userId))roomKnownPeers.add(Number(p.userId))})}if(d.type==='state'){renderSeats(d.seats);(d.peers||[]).forEach(p=>{if(Number(p.userId)!==Number(userId))roomKnownPeers.add(Number(p.userId))});if(roomLocalStream)roomKnownPeers.forEach(id=>maybeConnectRoomPeer(id,true))}if(['offer','answer','candidate'].includes(d.type))handleRoomSignal(d);if(d.type==='song-play')playRoomSongLocal(d.url,d.title)}
function renderRoomMessages(items){const b=document.getElementById('roomMessages');b.innerHTML='';items.forEach(appendRoomMessage)}
function appendRoomMessage(m){const b=document.getElementById('roomMessages');const e=document.createElement('div');e.className='room-msg';e.innerHTML=`<b>${escapeHtml(m.userName||m.user_name)}</b>${escapeHtml(m.message)}`;b.appendChild(e);b.scrollTop=b.scrollHeight}
function sendRoomChat(){const i=document.getElementById('roomChatInput'),t=i.value.trim();if(t&&socialRoomWs?.readyState===1){socialRoomWs.send(JSON.stringify({type:'chat',text:t}));i.value=''}}
function renderSeats(seats){const b=document.getElementById('micSeats');b.innerHTML='';for(let n=1;n<=8;n++){const x=seats[String(n)],e=document.createElement('button');e.className='mic-seat'+(x?' taken':'');e.innerHTML=x?`<span class="mic-icon">🎙️</span><span>${escapeHtml(x.userName)}</span>`:`<span class="mic-icon">＋</span><span>مايك ${n}</span>`;e.onclick=()=>{if(!x)takeMicSeat(n)};b.appendChild(e)}}
async function ensureRoomMic(){if(roomLocalStream)return roomLocalStream;try{roomLocalStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});return roomLocalStream}catch(e){alert('اسمح للمتصفح باستخدام المايك');throw e}}
async function takeMicSeat(n){await ensureRoomMic();socialRoomWs?.send(JSON.stringify({type:'take-seat',seat:String(n)}));roomKnownPeers.forEach(id=>maybeConnectRoomPeer(id,true))}
function leaveMySeat(){socialRoomWs?.send(JSON.stringify({type:'leave-seat'}));if(roomLocalStream){roomLocalStream.getTracks().forEach(t=>t.stop());roomLocalStream=null}roomPeers.forEach(pc=>pc.close());roomPeers.clear()}
function toggleRoomMic(){if(!roomLocalStream)return alert('اصعد على أحد المايكات أولاً');roomMicMuted=!roomMicMuted;roomLocalStream.getAudioTracks().forEach(t=>t.enabled=!roomMicMuted);document.getElementById('roomMicToggle').textContent=roomMicMuted?'🔇 فتح':'🎙️ كتم'}
async function getRoomPc(peerId){if(roomPeers.has(peerId))return roomPeers.get(peerId);const pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});roomPeers.set(peerId,pc);if(roomLocalStream)roomLocalStream.getTracks().forEach(t=>pc.addTrack(t,roomLocalStream));pc.onicecandidate=e=>{if(e.candidate)socialRoomWs?.send(JSON.stringify({type:'candidate',target:peerId,candidate:e.candidate}))};pc.ontrack=e=>{let a=document.getElementById(`room-audio-${peerId}`);if(!a){a=document.createElement('audio');a.id=`room-audio-${peerId}`;a.autoplay=true;a.playsInline=true;document.body.appendChild(a)}a.srcObject=e.streams[0];a.play().catch(()=>{})};return pc}
async function maybeConnectRoomPeer(peerId,initiator){if(Number(peerId)===Number(userId)||!roomLocalStream)return;const pc=await getRoomPc(Number(peerId));if(initiator&&pc.signalingState==='stable'){const offer=await pc.createOffer();await pc.setLocalDescription(offer);socialRoomWs?.send(JSON.stringify({type:'offer',target:Number(peerId),sdp:offer}))}}
async function handleRoomSignal(d){const from=Number(d.from);if(d.type==='offer'){await ensureRoomMic();const pc=await getRoomPc(from);await pc.setRemoteDescription(new RTCSessionDescription(d.sdp));const ans=await pc.createAnswer();await pc.setLocalDescription(ans);socialRoomWs.send(JSON.stringify({type:'answer',target:from,sdp:ans}))}else if(d.type==='answer'){const pc=await getRoomPc(from);await pc.setRemoteDescription(new RTCSessionDescription(d.sdp))}else if(d.type==='candidate'){const pc=await getRoomPc(from);try{await pc.addIceCandidate(new RTCIceCandidate(d.candidate))}catch(e){}}}
async function addRoomSong(){const title=document.getElementById('songTitle').value.trim(),url=document.getElementById('songUrl').value.trim();if(!title||!url)return alert('اكتب اسم الأغنية والرابط المباشر');const r=await fetch(`/api/rooms/${encodeURIComponent(socialRoomId)}/songs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId,title,url})});const d=await r.json();if(!r.ok)return alert(d.message);socialRoomData=await (await fetch(`/api/rooms/${encodeURIComponent(socialRoomId)}`)).json();renderSongs(socialRoomData.songs)}
function renderSongs(items){const b=document.getElementById('roomSongs');b.innerHTML='';items.forEach(x=>{const e=document.createElement('div');e.className='room-song-row';e.innerHTML=`<span>🎵 ${escapeHtml(x.title)}</span><button>تشغيل</button>`;e.querySelector('button').onclick=()=>{if(Number(socialRoomData.owner_id)!==Number(userId))return playRoomSongLocal(x.url,x.title);socialRoomWs?.send(JSON.stringify({type:'song-play',url:x.url,title:x.title}))};b.appendChild(e)})}
function playRoomSongLocal(url,title){const a=document.getElementById('roomAudio');a.src=url;a.play().catch(()=>alert('تعذر تشغيل الرابط. استخدم رابط صوت مباشر HTTPS.'))}
function leaveSocialRoom(){leaveMySeat();if(socialRoomWs){socialRoomWs.close();socialRoomWs=null}socialRoomId=null;socialRoomData=null;document.getElementById('roomInside').classList.add('hidden');document.getElementById('roomsDirectory').classList.remove('hidden');loadSocialRooms()}
