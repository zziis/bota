// تهيئة Telegram WebApp إذا كان يعمل داخل تلجرام
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('#0a0915');
    if (tg.setBackgroundColor) tg.setBackgroundColor('#0a0915');
}

// استخراج بيانات الغرفة والمستخدم
const urlParams = new URLSearchParams(window.location.search);
const roomId = urlParams.get('room') || 'khayal-room';
const tgUser = tg?.initDataUnsafe?.user;
const userName = tgUser ? `${tgUser.first_name || ''} ${tgUser.last_name || ''}`.trim() : (urlParams.get('name') || 'مستخدم خيال');
const userId = tgUser?.id || Math.floor(Math.random() * 100000);

// عناصر واجهة المستخدم
const statusBadge = document.getElementById('callStatusBadge');
const statusText = document.getElementById('statusText');
const waitingCard = document.getElementById('waitingCard');
const roomLinkInput = document.getElementById('roomLinkInput');
const copyLinkBtn = document.getElementById('copyLinkBtn');
const remoteVideo = document.getElementById('remoteVideo');
const remoteAvatarCard = document.getElementById('remoteAvatarCard');
const remoteUserName = document.getElementById('remoteUserName');
const localVideo = document.getElementById('localVideo');
const localContainer = document.getElementById('localContainer');
const callTimer = document.getElementById('callTimer');
const toggleMicBtn = document.getElementById('toggleMicBtn');
const toggleCamBtn = document.getElementById('toggleCamBtn');
const flipCamBtn = document.getElementById('flipCamBtn');
const endCallBtn = document.getElementById('endCallBtn');

// إعداد رابط الغرفة
roomLinkInput.value = window.location.href;
copyLinkBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(roomLinkInput.value).then(() => {
        copyLinkBtn.innerText = 'تم النسخ!';
        setTimeout(() => copyLinkBtn.innerText = 'نسخ الرابط', 2000);
    });
});

// متغيرات WebRTC والوسائط
let localStream = null;
let peerConnection = null;
let ws = null;
let isAudioMuted = false;
let isVideoMuted = true; // البدء صوتياً مع إمكانية تفعيل الكاميرا
let currentFacingMode = 'user';
let timerInterval = null;
let callStartTime = null;
let videoSender = null;
let remoteStream = new MediaStream();
let pendingIceCandidates = [];

// خوادم STUN العامة المجانية
const rtcConfig = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' }
    ]
};

// تشغيل الوسائط المحلية: مايك فقط عند الدخول. الكاميرا لا تُطلب إلا عند ضغط زر الكاميرا.
async function initLocalStream() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        isVideoMuted = true;
        updateCamUI();
        setStatus('جاهز صوتياً', 'connected');
    } catch (audioErr) {
        console.error('تعذر الوصول للمايكروفون:', audioErr);
        setStatus('خطأ بالصلاحيات', 'danger');
        alert('يرجى منح إذن استخدام الميكروفون للتمكن من إجراء المكالمة.');
    }
}

// إنشاء اتصال WebSocket لإشارات WebRTC
function connectSignalingServer() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/call/${roomId}`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('متصل بخادم الإشارات لمكالمات خيال');
        ws.send(JSON.stringify({
            type: 'join',
            room: roomId,
            userId: userId,
            userName: userName
        }));
    };

    ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        console.log('إشارة واردة:', data.type);

        switch (data.type) {
            case 'peer-joined':
                // انضم طرف جديد، نقوم بإنشاء العرض (Offer)
                setStatus('جاري الاتصال بالطرف الآخر...', 'calling');
                createPeerConnection();
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                ws.send(JSON.stringify({
                    type: 'offer',
                    room: roomId,
                    offer: offer,
                    callerName: userName
                }));
                break;

            case 'offer':
                // استلام عرض مكالمة
                setStatus('تم استلام اتصال...', 'calling');
                createPeerConnection();
                if (data.callerName) {
                    remoteUserName.innerText = data.callerName;
                }
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
                await flushPendingIceCandidates();
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                ws.send(JSON.stringify({
                    type: 'answer',
                    room: roomId,
                    answer: answer
                }));
                break;

            case 'answer':
                // استلام الرد
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                await flushPendingIceCandidates();
                break;

            case 'candidate':
                // تبادل مرشحي ICE
                if (peerConnection && data.candidate) {
                    const candidate = new RTCIceCandidate(data.candidate);
                    if (peerConnection.remoteDescription) {
                        try {
                            await peerConnection.addIceCandidate(candidate);
                        } catch (e) {
                            console.error('خطأ في إضافة مرشح ICE:', e);
                        }
                    } else {
                        pendingIceCandidates.push(candidate);
                    }
                }
                break;

            case 'peer-left':
                handlePeerDisconnect();
                break;
        }
    };

    ws.onclose = () => {
        console.log('انقطع الاتصال بخادم الإشارات');
    };
}

async function flushPendingIceCandidates() {
    if (!peerConnection || !peerConnection.remoteDescription) return;
    const queued = pendingIceCandidates.splice(0);
    for (const candidate of queued) {
        try { await peerConnection.addIceCandidate(candidate); }
        catch (e) { console.error('خطأ في ICE المؤجل:', e); }
    }
}

// إنشاء وإعداد اتصال النظير (Peer Connection)
function createPeerConnection() {
    if (peerConnection) return;

    peerConnection = new RTCPeerConnection(rtcConfig);

    // نرسل الصوت من البداية. ونحجز مسار فيديو في SDP حتى يمكن تشغيل الكاميرا
    // لاحقاً عبر replaceTrack بدون إنشاء اتصال جديد أو قطع الصوت.
    if (localStream) {
        localStream.getAudioTracks().forEach(track => peerConnection.addTrack(track, localStream));
    }
    const videoTransceiver = peerConnection.addTransceiver('video', { direction: 'sendrecv' });
    videoSender = videoTransceiver.sender;

    // إرسال مرشحي ICE
    peerConnection.onicecandidate = (event) => {
        if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'candidate',
                room: roomId,
                candidate: event.candidate
            }));
        }
    };

    // استلام الصوت/الفيديو للطرف البعيد في Stream واحد ثابت
    peerConnection.ontrack = (event) => {
        console.log('تم استلام مسار الطرف البعيد:', event.track.kind);
        waitingCard.classList.add('hidden');

        if (!remoteStream.getTracks().some(t => t.id === event.track.id)) {
            remoteStream.addTrack(event.track);
        }
        remoteVideo.srcObject = remoteStream;
        // بعض متصفحات الهاتف تحتاج play() صراحة بعد إسناد الـ stream.
        remoteVideo.play().catch(() => {});

        if (event.track.kind === 'video') {
            const showVideo = () => {
                remoteVideo.classList.remove('hidden');
                remoteAvatarCard.style.display = 'none';
            };
            const hideVideo = () => {
                remoteVideo.classList.add('hidden');
                remoteAvatarCard.style.display = 'flex';
            };
            event.track.addEventListener('unmute', showVideo);
            event.track.addEventListener('mute', hideVideo);
            event.track.addEventListener('ended', hideVideo);
            if (!event.track.muted && event.track.readyState === 'live') showVideo();
            else hideVideo();
        }
    };

    // مراقبة حالة الاتصال
    peerConnection.onconnectionstatechange = () => {
        console.log('حالة الاتصال:', peerConnection.connectionState);
        if (peerConnection.connectionState === 'connected') {
            setStatus('المكالمة جارية 🟢', 'connected');
            waitingCard.classList.add('hidden');
            startTimer();
        } else if (peerConnection.connectionState === 'disconnected' || peerConnection.connectionState === 'failed') {
            handlePeerDisconnect();
        }
    };
}

// معالجة مغادرة الطرف الآخر
function handlePeerDisconnect() {
    setStatus('انتهت المكالمة', '');
    stopTimer();
    waitingCard.classList.remove('hidden');
    waitingCard.querySelector('h2').innerText = 'تم إنهاء المكالمة';
    waitingCard.querySelector('p').innerText = 'غادر الطرف الآخر المكالمة.';
    
    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }
}

// تحديث شارة الحالة
function setStatus(text, badgeClass) {
    statusText.innerText = text;
    statusBadge.className = 'status-badge ' + (badgeClass || '');
}

// مؤقت المكالمة
function startTimer() {
    if (timerInterval) return;
    callStartTime = Date.now();
    timerInterval = setInterval(() => {
        const delta = Math.floor((Date.now() - callStartTime) / 1000);
        const mins = String(Math.floor(delta / 60)).padStart(2, '0');
        const secs = String(delta % 60).padStart(2, '0');
        callTimer.innerText = `${mins}:${secs}`;
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// أزرار التحكم
toggleMicBtn.addEventListener('click', () => {
    if (!localStream) return;
    const audioTrack = localStream.getAudioTracks()[0];
    if (audioTrack) {
        isAudioMuted = !isAudioMuted;
        audioTrack.enabled = !isAudioMuted;
        toggleMicBtn.classList.toggle('muted', isAudioMuted);
        toggleMicBtn.classList.toggle('active', !isAudioMuted);
    }
});

toggleCamBtn.addEventListener('click', async () => {
    if (!localStream) return;

    // إغلاق الكاميرا: نوقف مسار الكاميرا فقط ونبقي اتصال WebRTC والصوت كما هما.
    if (!isVideoMuted) {
        const oldTrack = localStream.getVideoTracks()[0];
        if (videoSender) await videoSender.replaceTrack(null);
        if (oldTrack) {
            oldTrack.stop();
            localStream.removeTrack(oldTrack);
        }
        localVideo.srcObject = null;
        isVideoMuted = true;
        updateCamUI();
        return;
    }

    // فتح الكاميرا لأول مرة/من جديد بدون addTrack، حتى لا تبدأ renegotiation تفصل المكالمة.
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: currentFacingMode },
            audio: false
        });
        const videoTrack = stream.getVideoTracks()[0];
        localStream.addTrack(videoTrack);
        localVideo.srcObject = localStream;

        if (peerConnection && !videoSender) {
            const transceiver = peerConnection.getTransceivers().find(t => t.receiver?.track?.kind === 'video');
            videoSender = transceiver?.sender || null;
        }
        if (videoSender) await videoSender.replaceTrack(videoTrack);

        isVideoMuted = false;
        updateCamUI();
        localVideo.play().catch(() => {});
    } catch (e) {
        console.error('تعذر فتح الكاميرا:', e);
        alert('تعذر فتح الكاميرا. تأكد من منح صلاحية الكاميرا.');
    }
});

function updateCamUI() {
    toggleCamBtn.classList.toggle('active', !isVideoMuted);
    if (isVideoMuted) {
        localContainer.classList.add('cam-off');
    } else {
        localContainer.classList.remove('cam-off');
    }
}

flipCamBtn.addEventListener('click', async () => {
    if (isVideoMuted || !localStream) return;
    currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
    
    const oldTrack = localStream.getVideoTracks()[0];
    if (oldTrack) {
        oldTrack.stop();
        localStream.removeTrack(oldTrack);
    }

    try {
        const newStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: currentFacingMode }
        });
        const newTrack = newStream.getVideoTracks()[0];
        localStream.addTrack(newTrack);
        localVideo.srcObject = localStream;

        if (peerConnection) {
            const sender = peerConnection.getSenders().find(s => s.track && s.track.kind === 'video');
            if (sender) {
                await sender.replaceTrack(newTrack);
                videoSender = sender;
            } else if (videoSender) {
                await videoSender.replaceTrack(newTrack);
            }
        }
    } catch (e) {
        console.error('خطأ في تبديل الكاميرا:', e);
    }
});

endCallBtn.addEventListener('click', () => {
    if (confirm('هل تريد إنهاء المكالمة؟')) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'leave', room: roomId }));
        }
        if (localStream) {
            localStream.getTracks().forEach(t => t.stop());
        }
        if (peerConnection) {
            peerConnection.close();
        }
        stopTimer();
        
        if (tg) {
            tg.close();
        } else {
            window.location.href = '/call-ended.html';
        }
    }
});

// بدء التشغيل
(async function start() {
    await initLocalStream();
    connectSignalingServer();
})();
