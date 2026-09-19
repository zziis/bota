// Initialize Telegram WebApp if available
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor("#07090e");
    if (tg.setBackgroundColor) tg.setBackgroundColor("#07090e");
}

// User state
const currentUser = {
    id: tg?.initDataUnsafe?.user?.id || 999999,
    name: tg?.initDataUnsafe?.user?.first_name || "مستخدم أوكار",
    username: tg?.initDataUnsafe?.user?.username || "",
    currentSlot: null,
    isCameraOn: false,
    isMicOn: true,
    mediaStream: null
};

// 4 Mic Slots State
const micSlots = [
    { id: 0, role: "👑 المضيف (Dev)", name: "مطور أوكار", occupied: true, user_id: 1, isSpeaking: true },
    { id: 1, role: "مايك 1", name: "شاغر", occupied: false, user_id: null, isSpeaking: false },
    { id: 2, role: "مايك 2", name: "شاغر", occupied: false, user_id: null, isSpeaking: false },
    { id: 3, role: "مايك 3", name: "شاغر", occupied: false, user_id: null, isSpeaking: false }
];

function updateAvailableMicsCount() {
    const available = micSlots.filter(s => !s.occupied).length;
    document.getElementById("availableMics").innerText = available;
}

// Render slots
function renderSlots() {
    for (let i = 1; i <= 3; i++) {
        const slot = micSlots[i];
        const slotEl = document.getElementById(`slot-${i}`);
        const nameEl = slotEl.querySelector(".user-name");
        const actionBtn = slotEl.querySelector(".slot-action-btn");
        const avatarWrap = slotEl.querySelector(".avatar-wrapper");
        const micInd = slotEl.querySelector(".mic-status-indicator");

        if (slot.occupied) {
            slotEl.classList.add("active");
            nameEl.innerText = slot.name;
            micInd.className = "mic-status-indicator live";
            micInd.innerText = "🎙️";

            if (slot.user_id === currentUser.id) {
                actionBtn.innerText = "مغادرة المايك";
                actionBtn.className = "slot-action-btn leave-mic";
                actionBtn.onclick = () => leaveSlot(i);
                avatarWrap.classList.add("speaking");
            } else {
                actionBtn.innerText = "مشغول";
                actionBtn.className = "slot-action-btn";
                actionBtn.disabled = true;
            }
        } else {
            slotEl.classList.remove("active");
            avatarWrap.classList.remove("speaking");
            nameEl.innerText = "شاغر";
            micInd.className = "mic-status-indicator mute";
            micInd.innerText = "🔇";
            actionBtn.disabled = false;
            actionBtn.innerText = "اعتلاء المايك";
            actionBtn.className = "slot-action-btn take-mic";
            actionBtn.onclick = () => takeSlot(i);
        }
    }
    updateAvailableMicsCount();
}

// Take a mic seat
window.takeSlot = function(slotIndex) {
    if (currentUser.currentSlot !== null) {
        alert("أنت بالفعل على منصة المايك!");
        return;
    }
    micSlots[slotIndex].occupied = true;
    micSlots[slotIndex].name = currentUser.name;
    micSlots[slotIndex].user_id = currentUser.id;
    currentUser.currentSlot = slotIndex;

    renderSlots();
    addChatMessage("system", `🎙️ اعتلى [${currentUser.name}] المايك رقم ${slotIndex}!`);
};

// Leave a mic seat
window.leaveSlot = function(slotIndex) {
    micSlots[slotIndex].occupied = false;
    micSlots[slotIndex].name = "شاغر";
    micSlots[slotIndex].user_id = null;
    currentUser.currentSlot = null;

    renderSlots();
    addChatMessage("system", `🚶‍♂️ نزل [${currentUser.name}] من على منصة المايك.`);
};

// Camera & Video Streaming
const toggleCamBtn = document.getElementById("toggleCamBtn");
const toggleMicBtn = document.getElementById("toggleMicBtn");
const localVideo = document.getElementById("localVideo");
const videoOverlay = document.getElementById("videoOverlay");

toggleCamBtn.addEventListener("click", async () => {
    if (!currentUser.isCameraOn) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            currentUser.mediaStream = stream;
            localVideo.srcObject = stream;
            localVideo.style.display = "block";
            videoOverlay.style.display = "none";
            currentUser.isCameraOn = true;
            toggleCamBtn.innerText = "🛑 إيقاف الكاميرا";
            toggleCamBtn.classList.add("live");
            addChatMessage("system", `📹 قام [${currentUser.name}] بتشغيل الكاميرا في الكبسولة.`);
        } catch (err) {
            console.warn("Camera access denied or simulated:", err);
            // Simulated live preview for unsupported environments
            localVideo.style.display = "none";
            videoOverlay.innerHTML = "<div class='camera-off-icon'>🟢</div><span>كاميرا متصلة (بث تجريبي)</span>";
            currentUser.isCameraOn = true;
            toggleCamBtn.innerText = "🛑 إيقاف الكاميرا";
            toggleCamBtn.classList.add("live");
        }
    } else {
        if (currentUser.mediaStream) {
            currentUser.mediaStream.getTracks().forEach(track => track.stop());
            currentUser.mediaStream = null;
        }
        localVideo.style.display = "none";
        videoOverlay.style.display = "flex";
        videoOverlay.innerHTML = "<div class='camera-off-icon'>📷</div><span>الكاميرا غير مفعلة</span>";
        currentUser.isCameraOn = false;
        toggleCamBtn.innerText = "📹 تشغيل الكاميرا";
        toggleCamBtn.classList.remove("live");
    }
});

toggleMicBtn.addEventListener("click", () => {
    currentUser.isMicOn = !currentUser.isMicOn;
    if (currentUser.isMicOn) {
        toggleMicBtn.innerText = "🎙️ المايك: يعمل";
        toggleMicBtn.classList.add("live");
    } else {
        toggleMicBtn.innerText = "🔇 المايك: مكتوم";
        toggleMicBtn.classList.remove("live");
    }
});

// Raise Hand
const raiseHandBtn = document.getElementById("raiseHandBtn");
raiseHandBtn.addEventListener("click", () => {
    addChatMessage("system", `✋ قام [${currentUser.name}] برفع يده طلباً للحديث على المنصة.`);
    sendReaction("✋");
});

// Public Chat
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    addChatMessage("user", text, currentUser.name);
    chatInput.value = "";
});

function addChatMessage(type, text, sender = "") {
    const msgEl = document.createElement("div");
    msgEl.className = `msg ${type}`;
    if (type === "system") {
        msgEl.innerHTML = `<span>⚡️ ${text}</span>`;
    } else {
        msgEl.innerHTML = `<span class="sender cyan">👤 ${sender}:</span> <span class="text">${text}</span>`;
    }
    chatMessages.appendChild(msgEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Floating Reactions
window.sendReaction = function(emoji) {
    const canvas = document.getElementById("reactionsCanvas");
    const span = document.createElement("span");
    span.className = "floating-emoji";
    span.innerText = emoji;
    span.style.left = `${Math.random() * 60 + 20}%`;
    canvas.appendChild(span);

    setTimeout(() => {
        span.remove();
    }, 2500);
};

// Create Room Modal
const createRoomBtn = document.getElementById("createRoomBtn");
const createRoomModal = document.getElementById("createRoomModal");
const closeModalBtn = document.getElementById("closeModalBtn");
const newRoomForm = document.getElementById("newRoomForm");

createRoomBtn.addEventListener("click", () => {
    createRoomModal.classList.add("active");
});

closeModalBtn.addEventListener("click", () => {
    createRoomModal.classList.remove("active");
});

newRoomForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const title = document.getElementById("roomTitleInput").value.trim();
    const desc = document.getElementById("roomDescInput").value.trim() || "روم صوتية في كبسولة أوكار";
    
    document.getElementById("currentRoomTitle").innerText = `🏰 ${title}`;
    document.getElementById("currentRoomDesc").innerText = desc;

    createRoomModal.classList.remove("active");
    addChatMessage("system", `🎉 تم إنشاء الروم الجديدة: [${title}] بنجاح!`);
});

document.getElementById("leaveRoomBtn").addEventListener("click", () => {
    if (tg?.close) {
        tg.close();
    } else {
        alert("تم الخروج من كبسولة الروم.");
    }
});

// Initialize on load
renderSlots();
