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
let pendingIceCandidates = [];
let videoSender = null;

// خوادم STUN العامة المجانية
const rtcConfig = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' }
    ]
};

// تشغيل الوسائط المحلية (الصوت أولاً)
async function initLocalStream() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            video: false
        });
        localVideo.srcObject = localStream;
        isVideoMuted = true;
        updateCamUI();
        setStatus('جاهز صوتياً', 'connected');
    } catch (audioErr) {
        console.error('تعذر الوصول للمايكروفون:', audioErr);
        setStatus('خطأ بالصلاحيات', 'danger');
        alert('يرجى منح إذن استخدام الميكروفون للتمكن من إجراء المكالمة.');
        throw audioErr;
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
                await flushPendingIce();
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
                await flushPendingIce();
                break;

            case 'candidate':
                // تبادل مرشحي ICE
                if (data.candidate) {
                    try {
                        const candidate = new RTCIceCandidate(data.candidate);
                        if (peerConnection && peerConnection.remoteDescription) {
                            await peerConnection.addIceCandidate(candidate);
                        } else {
                            pendingIceCandidates.push(candidate);
                        }
                    } catch (e) {
                        console.error('خطأ في إضافة مرشح ICE:', e);
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

async function flushPendingIce() {
    if (!peerConnection || !peerConnection.remoteDescription) return;
    const queued = pendingIceCandidates.splice(0);
    for (const candidate of queued) {
        try { await peerConnection.addIceCandidate(candidate); } catch (e) { console.warn('ICE queue:', e); }
    }
}

// إنشاء وإعداد اتصال النظير (Peer Connection)
function createPeerConnection() {
    if (peerConnection) return;

    peerConnection = new RTCPeerConnection(rtcConfig);

    // إضافة المسارات المحلية (Local Tracks)
    if (localStream) {
        localStream.getAudioTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });
    }
    // نحجز مسار فيديو من البداية. تشغيل الكاميرا لاحقاً يستخدم replaceTrack
    // ولا ينشئ Offer جديداً ولا يقطع الصوت.
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

    // استلام مسارات الطرف البعيد (Remote Stream)
    peerConnection.ontrack = (event) => {
        console.log('تم استلام تدفق الطرف البعيد');
        waitingCard.classList.add('hidden');
        
        const remoteStream = event.streams[0];
        remoteVideo.srcObject = remoteStream;
        remoteVideo.muted = false;
        remoteVideo.volume = 1;
        remoteVideo.play().catch(() => {});

        // فحص ما إذا كان هناك فيديو فعال من الطرف البعيد
        const videoTrack = remoteStream.getVideoTracks()[0];
        if (videoTrack && videoTrack.enabled) {
            remoteVideo.classList.remove('hidden');
            remoteAvatarCard.style.display = 'none';
        }

        videoTrack?.addEventListener('mute', () => {
            remoteVideo.classList.add('hidden');
            remoteAvatarCard.style.display = 'flex';
        });
        videoTrack?.addEventListener('unmute', () => {
            remoteVideo.classList.remove('hidden');
            remoteAvatarCard.style.display = 'none';
        });
    };

    // مراقبة حالة الاتصال
    peerConnection.onconnectionstatechange = () => {
        console.log('حالة الاتصال:', peerConnection.connectionState);
        if (peerConnection.connectionState === 'connected') {
            setStatus('المكالمة جارية 🟢', 'connected');
            waitingCard.classList.add('hidden');
            startTimer();
        } else if (peerConnection.connectionState === 'disconnected') {
            setStatus('جاري استعادة الاتصال...', 'calling');
        } else if (peerConnection.connectionState === 'failed') {
            setStatus('تعذر الاتصال', 'danger');
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
    if (!localStream || !peerConnection) return;
    toggleCamBtn.disabled = true;
    try {
        let videoTrack = localStream.getVideoTracks()[0];
        const sender = videoSender;

        if (isVideoMuted) {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: currentFacingMode, width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            });
            videoTrack = stream.getVideoTracks()[0];
            localStream.getVideoTracks().forEach(t => {
                t.stop();
                localStream.removeTrack(t);
            });
            localStream.addTrack(videoTrack);
            localVideo.srcObject = localStream;
            if (sender) await sender.replaceTrack(videoTrack);
            isVideoMuted = false;
        } else {
            if (sender) await sender.replaceTrack(null);
            if (videoTrack) {
                videoTrack.stop();
                localStream.removeTrack(videoTrack);
            }
            localVideo.srcObject = localStream;
            isVideoMuted = true;
        }
        updateCamUI();
    } catch (e) {
        console.error('خطأ الكاميرا:', e);
        alert('تعذر فتح الكاميرا. تحقق من إذن الكاميرا.');
    } finally {
        toggleCamBtn.disabled = false;
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
    if (isVideoMuted || !localStream || !peerConnection) return;
    currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
    try {
        const newStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: currentFacingMode },
            audio: false
        });
        const newTrack = newStream.getVideoTracks()[0];
        const oldTrack = localStream.getVideoTracks()[0];
        const sender = peerConnection.getSenders().find(s => s.track && s.track.kind === 'video');
        if (sender) await sender.replaceTrack(newTrack);
        if (oldTrack) {
            oldTrack.stop();
            localStream.removeTrack(oldTrack);
        }
        localStream.addTrack(newTrack);
        localVideo.srcObject = localStream;
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
