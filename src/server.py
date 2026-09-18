import json
import logging
import uuid
from aiohttp import web, WSMsgType
from src.config import STATIC_DIR

logger = logging.getLogger("KhayalServer")

# إدارة غرف مكالمات WebRTC
# rooms = { room_id: { ws: { "user_id": ..., "user_name": ... } } }
rooms = {}

async def websocket_call_handler(request):
    """معالج WebSocket لإشارات WebRTC للمكالمات الحية"""
    room_id = request.match_info.get("room_id", "default")
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    if room_id not in rooms:
        rooms[room_id] = {}

    current_peer_info = {"id": None, "name": "غير معروف"}

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")

                    if msg_type == "join":
                        current_peer_info["id"] = data.get("userId")
                        current_peer_info["name"] = data.get("userName", "مستخدم خيال")
                        rooms[room_id][ws] = current_peer_info

                        # إشعار باقي المتصلين في الغرفة بوجود نظير جديد
                        for client in list(rooms[room_id].keys()):
                            if client != ws and not client.closed:
                                await client.send_json({
                                    "type": "peer-joined",
                                    "userId": current_peer_info["id"],
                                    "userName": current_peer_info["name"]
                                })

                    elif msg_type in ["offer", "answer", "candidate", "leave"]:
                        # إعادة توجيه الإشارة للطرف الآخر في الغرفة
                        for client in list(rooms[room_id].keys()):
                            if client != ws and not client.closed:
                                await client.send_json(data)

                except Exception as e:
                    logger.error(f"خطأ في معالجة إشارة WebSocket: {e}")

            elif msg.type == WSMsgType.ERROR:
                logger.warning(f"WebSocket اتصال انقطع مع خطأ: {ws.exception()}")

    finally:
        # عند إغلاق الاتصال
        if room_id in rooms and ws in rooms[room_id]:
            del rooms[room_id][ws]
            # إشعار الطرف المتبقي
            for client in list(rooms[room_id].keys()):
                if not client.closed:
                    try:
                        await client.send_json({"type": "peer-left"})
                    except Exception:
                        pass

            if len(rooms[room_id]) == 0:
                del rooms[room_id]

    return ws

async def health_check(request):
    """فحص سلامة الخادم (مفيد لخدمات مثل Render)"""
    return web.json_response({"status": "active", "service": "Khayal Call & Bot Server"})

async def create_room_api(request):
    """توليد معرف غرفة مكالمة جديد"""
    room_id = f"khayal-{uuid.uuid4().hex[:8]}"
    return web.json_response({"room_id": room_id})

def create_app():
    """إنشاء وتهيئة تطبيق aiohttp"""
    app = web.Application()
    
    # واجهات برمجة التطبيقات
    app.router.add_get("/api/health", health_check)
    app.router.add_get("/api/create_room", create_room_api)
    
    # إشارات WebRTC
    app.router.add_get("/ws/call/{room_id}", websocket_call_handler)
    
    # الملفات الثابتة وتطبيق الويب المصغر
    app.router.add_static("/css", f"{STATIC_DIR}/css")
    app.router.add_static("/js", f"{STATIC_DIR}/js")
    app.router.add_static("/images", f"{STATIC_DIR}/images")
    
    async def index_handler(request):
        return web.FileResponse(f"{STATIC_DIR}/index.html")
    
    async def ended_handler(request):
        return web.FileResponse(f"{STATIC_DIR}/call-ended.html")
        
    app.router.add_get("/", index_handler)
    app.router.add_get("/call", index_handler)
    app.router.add_get("/call-ended.html", ended_handler)
    app.router.add_get("/games", lambda request: web.FileResponse(f"{STATIC_DIR}/games.html"))

    return app
