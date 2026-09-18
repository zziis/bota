import json
import logging
import uuid
import asyncio
from aiohttp import web, WSMsgType
from src.config import STATIC_DIR, ADMIN_IDS
from src import db

logger = logging.getLogger("KhayalServer")

# إدارة اتصالات WebRTC للمكالمات
rooms = {}

# قائمة محطات راديو FM الحية المباشرة والموثوقة
RADIO_STATIONS = [
    {
        "id": "quran_cairo",
        "name": "إذاعة القرآن الكريم - القاهرة",
        "genre": "قرآن كريم وتلاوات",
        "url": "https://stream.radiojar.com/8s5u8pdtw5zuv",
        "icon": "📖"
    },
    {
        "id": "quran_saudi",
        "name": "إذاعة نداء الإسلام - مكة المكرمة",
        "genre": "قرآن وبرامج إسلامية",
        "url": "https://n08.radiojar.com/0tpy1h0tw5zuv",
        "icon": "🕋"
    },
    {
        "id": "nogoum_fm",
        "name": "نجوم FM 100.6",
        "genre": "منوعات وترفيه وبرامج حية",
        "url": "https://streamer.nogoumfm.net/NOGOUM_FM",
        "icon": "⭐"
    },
    {
        "id": "monte_carlo",
        "name": "مونت كارلو الدولية - باريس",
        "genre": "أخبار وثقافة ومنوعات",
        "url": "https://montecarlodoualiyaaudio.global.ssl.fastly.net/mc-doualiya.mp3",
        "icon": "🌍"
    },
    {
        "id": "rotana_fm",
        "name": "روتانا FM",
        "genre": "طرب وموسيقى عربية",
        "url": "https://stream.rotana.net/rotanafm",
        "icon": "🎵"
    },
    {
        "id": "sky_news",
        "name": "سكاي نيوز عربية راديو",
        "genre": "أخبار حية على مدار الساعة",
        "url": "https://skynews.ice.infomaniak.ch/skynews-128.mp3",
        "icon": "📰"
    },
    {
        "id": "lofi_chill",
        "name": "خيال Chill & Lo-Fi",
        "genre": "موسيقى هادئة للاسترخاء والتركيز",
        "url": "https://stream.zeno.fm/f3wvbbqmdg8uv",
        "icon": "🌙"
    }
]

# طابور البحث عن خصم (Matchmaking Queue)
matchmaking_queue = [] # [ {"ws": ws, "userId": ..., "userName": ..., "bet": ...} ]
active_game_rooms = {}  # room_id -> { "player1": ..., "player2": ..., "board": [...], "turn": ... }

# اتصالات رومات خيال: دردشة + مايكات + مزامنة أغاني
social_room_clients = {}  # room_id -> ws -> info
social_room_seats = {}    # room_id -> seat -> {userId,userName}

async def social_rooms_list_api(request):
    items = await db.list_social_rooms()
    for item in items:
        item["online"] = len(social_room_clients.get(item["room_id"], {}))
    return web.json_response({"rooms": items})

async def social_room_create_api(request):
    try:
        data = await request.json()
        uid = int(data.get("userId"))
        name = str(data.get("name", "")).strip()[:40]
        desc = str(data.get("description", "")).strip()[:250]
        image = str(data.get("imageUrl", "")).strip()[:200000]
        if len(name) < 2:
            return web.json_response({"success": False, "message": "اكتب اسم الروم"}, status=400)
        rid, points = await db.create_social_room(uid, name, image, desc, 300)
        if not rid:
            return web.json_response({"success": False, "message": "تحتاج 300 نقطة لإنشاء الروم", "points": points}, status=400)
        return web.json_response({"success": True, "roomId": rid, "points": points})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def social_room_detail_api(request):
    rid = request.match_info['room_id']
    room = await db.get_social_room(rid)
    if not room: raise web.HTTPNotFound()
    room['messages'] = await db.get_room_messages(rid)
    room['songs'] = await db.get_room_songs(rid)
    room['online'] = len(social_room_clients.get(rid, {}))
    room['seats'] = social_room_seats.get(rid, {})
    return web.json_response(room)

async def social_room_song_api(request):
    rid = request.match_info['room_id']; data = await request.json()
    ok = await db.add_room_song(rid, int(data.get('userId')), str(data.get('title','أغنية'))[:80], str(data.get('url',''))[:1000])
    if not ok: return web.json_response({'success':False,'message':'إضافة الأغاني متاحة لمالك الروم'}, status=403)
    return web.json_response({'success':True})

async def social_room_ws(request):
    rid = request.match_info['room_id']; ws = web.WebSocketResponse(heartbeat=25); await ws.prepare(request)
    if not await db.get_social_room(rid):
        await ws.close(); return ws
    social_room_clients.setdefault(rid, {})
    social_room_seats.setdefault(rid, {})
    info = {'userId': None, 'userName': 'مستخدم'}
    async def broadcast(payload, exclude=None):
        for c in list(social_room_clients.get(rid, {})):
            if c != exclude and not c.closed:
                try: await c.send_json(payload)
                except: pass
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT: continue
            try: data=json.loads(msg.data)
            except: continue
            typ=data.get('type')
            if typ=='join':
                info={'userId':int(data.get('userId')), 'userName':str(data.get('userName','مستخدم'))[:60]}
                social_room_clients[rid][ws]=info
                await ws.send_json({'type':'state','seats':social_room_seats[rid], 'peers':[v for c,v in social_room_clients[rid].items() if c!=ws]})
                await broadcast({'type':'presence','online':len(social_room_clients[rid])})
            elif typ=='chat' and info['userId']:
                text=str(data.get('text','')).strip()[:1500]
                if text:
                    mid=await db.save_room_message(rid,info['userId'],info['userName'],text)
                    await broadcast({'type':'chat','id':mid,'userId':info['userId'],'userName':info['userName'],'message':text}, None)
            elif typ=='take-seat' and info['userId']:
                seat=str(data.get('seat'))
                # مستخدم واحد = مقعد واحد
                for k,v in list(social_room_seats[rid].items()):
                    if int(v['userId'])==info['userId']: del social_room_seats[rid][k]
                if seat not in social_room_seats[rid] and seat in [str(i) for i in range(1,9)]:
                    social_room_seats[rid][seat]=info.copy()
                await broadcast({'type':'seats','seats':social_room_seats[rid]}, None)
            elif typ=='leave-seat' and info['userId']:
                for k,v in list(social_room_seats[rid].items()):
                    if int(v['userId'])==info['userId']: del social_room_seats[rid][k]
                await broadcast({'type':'seats','seats':social_room_seats[rid]}, None)
            elif typ in ('offer','answer','candidate'):
                target=int(data.get('target',0))
                for c,ci in social_room_clients[rid].items():
                    if ci.get('userId')==target and not c.closed:
                        data['from']=info['userId']; data['fromName']=info['userName']; await c.send_json(data); break
            elif typ=='song-play':
                room=await db.get_social_room(rid)
                if room and int(room['owner_id'])==info['userId']:
                    await broadcast({'type':'song-play','url':str(data.get('url','')),'title':str(data.get('title',''))}, None)
    finally:
        social_room_clients.get(rid,{}).pop(ws,None)
        if info['userId']:
            for k,v in list(social_room_seats.get(rid,{}).items()):
                if int(v['userId'])==info['userId']: del social_room_seats[rid][k]
        await broadcast({'type':'seats','seats':social_room_seats.get(rid,{})}, None)
        await broadcast({'type':'presence','online':len(social_room_clients.get(rid,{}))}, None)
    return ws

# ==================== WEBSOCKETS ====================

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

                        for client in list(rooms[room_id].keys()):
                            if client != ws and not client.closed:
                                await client.send_json({
                                    "type": "peer-joined",
                                    "userId": current_peer_info["id"],
                                    "userName": current_peer_info["name"]
                                })

                    elif msg_type in ["offer", "answer", "candidate", "leave"]:
                        for client in list(rooms[room_id].keys()):
                            if client != ws and not client.closed:
                                await client.send_json(data)
                except Exception as e:
                    logger.error(f"خطأ في إشارة المكالمة: {e}")
    finally:
        if room_id in rooms and ws in rooms[room_id]:
            del rooms[room_id][ws]
            for client in list(rooms[room_id].keys()):
                if not client.closed:
                    try:
                        await client.send_json({"type": "peer-left"})
                    except Exception:
                        pass
            if len(rooms[room_id]) == 0:
                del rooms[room_id]
    return ws


async def websocket_matchmaking_handler(request):
    """معالج البحث عن خصم أونلاين لمباريات X-O وألعاب التحدي"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    player_info = None
    current_room_id = None

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                action = data.get("action")

                if action == "find_match":
                    user_id = data.get("userId")
                    user_name = data.get("userName", "لاعب")
                    bet = int(data.get("bet", 50))

                    # التحقق من رصيد النقاط
                    current_pts = await db.get_points(user_id)
                    if current_pts < bet:
                        await ws.send_json({"action": "error", "message": "رصيد نقاطك غير كافٍ لهذا الرهان!"})
                        continue

                    player_info = {
                        "ws": ws,
                        "userId": user_id,
                        "userName": user_name,
                        "bet": bet
                    }

                    # البحث عن خصم في الطابور
                    opponent = None
                    for waiting in matchmaking_queue:
                        if waiting["userId"] != user_id and waiting["bet"] == bet and not waiting["ws"].closed:
                            opponent = waiting
                            matchmaking_queue.remove(waiting)
                            break

                    if opponent:
                        # إنشاء غرفة مباراة بين الطرفين
                        current_room_id = f"game_{uuid.uuid4().hex[:8]}"
                        active_game_rooms[current_room_id] = {
                            "p1": player_info,
                            "p2": opponent,
                            "board": [""] * 9,
                            "turn": player_info["userId"],
                            "bet": bet
                        }

                        # خصم الرهان من الطرفين
                        await db.update_points(player_info["userId"], -bet, "match_bet", f"رهان مباراة X-O {current_room_id}")
                        await db.update_points(opponent["userId"], -bet, "match_bet", f"رهان مباراة X-O {current_room_id}")

                        # إشعار اللاعبين ببدء المباراة
                        await player_info["ws"].send_json({
                            "action": "match_found",
                            "roomId": current_room_id,
                            "symbol": "X",
                            "myTurn": True,
                            "opponentName": opponent["userName"],
                            "bet": bet
                        })
                        await opponent["ws"].send_json({
                            "action": "match_found",
                            "roomId": current_room_id,
                            "symbol": "O",
                            "myTurn": False,
                            "opponentName": player_info["userName"],
                            "bet": bet
                        })
                    else:
                        matchmaking_queue.append(player_info)
                        await ws.send_json({"action": "waiting_for_opponent"})

                elif action == "make_move":
                    room_id = data.get("roomId")
                    cell_index = data.get("index")
                    symbol = data.get("symbol")

                    room = active_game_rooms.get(room_id)
                    if room:
                        room["board"][cell_index] = symbol
                        # إرسال الحركة للطرف الآخر
                        other_player = room["p2"] if ws == room["p1"]["ws"] else room["p1"]
                        if not other_player["ws"].closed:
                            await other_player["ws"].send_json({
                                "action": "opponent_moved",
                                "index": cell_index,
                                "symbol": symbol
                            })

                elif action == "game_over":
                    room_id = data.get("roomId")
                    winner_symbol = data.get("winner") # "X", "O", or "draw"
                    room = active_game_rooms.get(room_id)
                    if room:
                        bet = room["bet"]
                        if winner_symbol == "draw":
                            # استرجاع الرهان
                            await db.update_points(room["p1"]["userId"], bet, "match_refund", "تعادل X-O")
                            await db.update_points(room["p2"]["userId"], bet, "match_refund", "تعادل X-O")
                        else:
                            winner = room["p1"] if winner_symbol == "X" else room["p2"]
                            prize = bet * 2
                            await db.update_points(winner["userId"], prize, "match_win", f"فوز في مباراة X-O {prize} نقطة")

                        if room_id in active_game_rooms:
                            del active_game_rooms[room_id]

                elif action == "cancel_search":
                    if player_info in matchmaking_queue:
                        matchmaking_queue.remove(player_info)
                        await ws.send_json({"action": "search_cancelled"})

    finally:
        if player_info in matchmaking_queue:
            matchmaking_queue.remove(player_info)
        if current_room_id and current_room_id in active_game_rooms:
            room = active_game_rooms[current_room_id]
            # في حال انسحاب لاعب أثناء المباراة يعتبر الطرف الآخر فائزاً
            other = room["p2"] if ws == room["p1"]["ws"] else room["p1"]
            if not other["ws"].closed:
                prize = room["bet"] * 2
                await db.update_points(other["userId"], prize, "forfeit_win", "فوز لانسحاب الخصم")
                await other["ws"].send_json({"action": "opponent_left", "message": "انسحب الخصم! فزت بالمباراة والنقاط 🏆"})
            del active_game_rooms[current_room_id]

    return ws

# ==================== REST APIS ====================

async def get_user_profile(request):
    """جلب بيانات المستخدم ورصيد النقاط"""
    user_id = request.query.get("userId")
    if not user_id or not user_id.isdigit():
        return web.json_response({"error": "معرف غير صالح"}, status=400)
    
    uid = int(user_id)
    user = await db.get_user(uid)
    if not user:
        await db.add_or_update_user(uid, "", "مستخدم خيال")
        user = await db.get_user(uid)

    return web.json_response({
        "userId": user["user_id"],
        "name": user["full_name"],
        "points": user.get("points", 500),
        "lastDaily": user.get("last_daily_claim", "")
    })

async def claim_daily_api(request):
    """استلام المكافأة اليومية"""
    try:
        data = await request.json()
        user_id = int(data.get("userId"))
        result = await db.claim_daily_bonus(user_id, 100)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def crash_settle_api(request):
    """تسوية رهان لعبة الطيارة (إضافة أرباح أو خصم رهان)"""
    try:
        data = await request.json()
        user_id = int(data.get("userId"))
        action_type = data.get("action") # "bet" or "cashout"
        amount = int(data.get("amount", 0))

        if action_type == "bet":
            current_pts = await db.get_points(user_id)
            if current_pts < amount or amount <= 0:
                return web.json_response({"success": False, "message": "رصيد النقاط غير كافٍ للرهان!"}, status=400)
            new_pts = await db.update_points(user_id, -amount, "crash_bet", f"رهان طائرة {amount} نقطة")
            return web.json_response({"success": True, "newPoints": new_pts})

        elif action_type == "cashout":
            win_amount = int(data.get("winAmount", 0))
            multiplier = data.get("multiplier", 1.0)
            new_pts = await db.update_points(user_id, win_amount, "crash_win", f"فوز طائرة بمضاعف {multiplier}x (+{win_amount} نقطة)")
            return web.json_response({"success": True, "newPoints": new_pts})

        return web.json_response({"success": False, "message": "نوع عملية غير معروف"}, status=400)
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def request_points_api(request):
    """إرسال طلب شراء نقاط وإشعار المشرف في تلجرام"""
    from src.bot import bot
    try:
        data = await request.json()
        user_id = int(data.get("userId"))
        user_name = data.get("userName", "مستخدم")
        package_name = data.get("packageName", "باقة نقاط")
        points = int(data.get("points", 1000))
        price = data.get("price", "1$")

        # حفظ الطلب في قاعدة البيانات
        req_id = await db.create_point_request(user_id, user_name, package_name, points, price)

        # إشعار المشرفين في تلجرام مع أزرار الموافقة والرفض
        if bot:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            admin_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ موافقة وشحن النقاط", callback_data=f"approve_pts_{req_id}"),
                    InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"reject_pts_{req_id}")
                ]
            ])
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=(
                            "💎 <b>طلب شراء نقاط جديد!</b>\n\n"
                            f"👤 <b>المستخدم:</b> {user_name} (<code>{user_id}</code>)\n"
                            f"📦 <b>الباقة:</b> {package_name}\n"
                            f"💰 <b>النقاط المطلوبة:</b> {points:,} نقطة\n"
                            f"💵 <b>القيمة:</b> {price}\n"
                            f"🆔 <b>رقم الطلب:</b> #{req_id}"
                        ),
                        reply_markup=admin_kb
                    )
                except Exception as err:
                    logger.error(f"فشل إشعار المشرف {admin_id}: {err}")

        return web.json_response({"success": True, "message": "تم إرسال طلب الشحن للإدارة بنجاح!"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def get_radio_stations(request):
    """قائمة إذاعات FM الحية"""
    return web.json_response({"stations": RADIO_STATIONS})

async def health_check(request):
    return web.json_response({"status": "active", "service": "Khayal Super-App Server"})

async def create_room_api(request):
    room_id = f"khayal-{uuid.uuid4().hex[:8]}"
    return web.json_response({"room_id": room_id})

def create_app():
    """إنشاء وتهيئة تطبيق aiohttp"""
    app = web.Application()

    # واجهات برمجة التطبيقات
    app.router.add_get("/api/health", health_check)
    app.router.add_get("/api/create_room", create_room_api)
    app.router.add_get("/api/user/profile", get_user_profile)
    app.router.add_post("/api/points/daily", claim_daily_api)
    app.router.add_post("/api/points/request", request_points_api)
    app.router.add_post("/api/games/crash/settle", crash_settle_api)
    app.router.add_get("/api/radio/stations", get_radio_stations)
    app.router.add_get("/api/rooms", social_rooms_list_api)
    app.router.add_post("/api/rooms", social_room_create_api)
    app.router.add_get("/api/rooms/{room_id}", social_room_detail_api)
    app.router.add_post("/api/rooms/{room_id}/songs", social_room_song_api)

    # WebSockets
    app.router.add_get("/ws/call/{room_id}", websocket_call_handler)
    app.router.add_get("/ws/matchmaking", websocket_matchmaking_handler)
    app.router.add_get("/ws/rooms/{room_id}", social_room_ws)

    # الملفات الثابتة
    app.router.add_static("/css", f"{STATIC_DIR}/css")
    app.router.add_static("/js", f"{STATIC_DIR}/js")
    app.router.add_static("/images", f"{STATIC_DIR}/images")

    async def index_handler(request):
        return web.FileResponse(f"{STATIC_DIR}/index.html")

    async def ended_handler(request):
        return web.FileResponse(f"{STATIC_DIR}/call-ended.html")

    app.router.add_get("/", index_handler)
    app.router.add_get("/call", index_handler)
    app.router.add_get("/games", index_handler)
    app.router.add_get("/crash", index_handler)
    app.router.add_get("/radio", index_handler)
    app.router.add_get("/shop", index_handler)
    app.router.add_get("/call-ended.html", ended_handler)

    return app
