from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify, session, make_response, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import secrets
from datetime import datetime, timezone, timedelta
import time
import os
from dotenv import load_dotenv
import threading
import urllib.parse

base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(base_dir), '.env'))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import requests

from zeno_fm_auth import get_zeno_token

spotify_client_id=os.getenv("spotify_client_id")
spotify_client_secret=os.getenv("spotify_client_secret")
ZENO_ICECAST_MOUNT=os.getenv("ZENO_ICECAST_MOUNT")
ZENO_ICECAST_PASSWORD=os.getenv("ZENO_ICECAST_PASSWORD")
domain=os.getenv("domain")

discord_webhook=os.getenv("discord_webhook")
EXCLUDED_NOTIFY_UID = "4iu5c737f2jidf8q6pnjqm2wb"
notified_flags = {}

def notify_discord_listen_along():
    if not discord_webhook:
        return
    try:
        requests.post(discord_webhook, json={"content": "spotify-listen along"}, timeout=5)
    except Exception as e:
        print(f"Discord webhook error: {e}")

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'

from flask_session import Session
Session(app)
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False, async_mode='gevent')

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

chat_users = {}
pinned_message = '' # 'Send "/as" to toggle autoscroll on new user messages.'
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
last_title=""
last_program=""
last_lyrics=""
last_song_start=time.time()
last_count=0

from utils.rando import generate_username
from utils import info_fetcher

import json
sched = json.load(open(base_dir+'/static/json/schedule.json'))

is_onair=False
onair_file=base_dir+'/onair'
if os.path.exists(onair_file): is_onair=True

def get_listener_count():
    global last_count
    token = get_zeno_token()

    totalcnt=last_count
    if not token:
        totalcnt='N/A'
    else:
        rr = requests.get(f"https://stream-tools.zenomedia.com/stations/{ZENO_ICECAST_MOUNT}/stats/live?include_outputs=true",headers={"Authorization": "Bearer "+token}).json()
        totalcnt=0
        if not 'data' in rr: return
        for d in rr['data']: totalcnt += d['uniqueListeners']
    if last_count==totalcnt: return
    last_count=totalcnt
   
    socketio.emit('listener_update', {"total_users":last_count } , room='chat_room')
    
np_offset = timedelta(hours=5, minutes=45)

days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

def update_icecast_metadata(prog, title):
    url=f"http://link.zeno.fm:80/admin/metadata?mount=/{ZENO_ICECAST_MOUNT}&mode=updinfo&song="
    requests.get(f"{url}{title} [{prog}]", auth=("source", ZENO_ICECAST_PASSWORD))

def convert_to_plain_lrc(lrc):
    plain_lyrics = ""
    try:
        lines = lrc.split("\n")
        for line in lines:
            if not line: continue
            time, words = line.split("]", 1)
            plain_lyrics += f"{words}\n"
        return plain_lyrics
    except:
        return plain_lyrics

def get_lyrics(r):
    # Prefer synced lyrics, fallback to plain
    if 'syncedLyrics' in r and r['syncedLyrics']: 
        return {"type": "synced", "data": r['syncedLyrics']}
    elif 'plainLyrics' in r and r['plainLyrics']: 
        return {"type": "plain", "data": r['plainLyrics']}
    # elif 'syncedLyrics' in r and r['syncedLyrics']: return {"type": "plain", "data": convert_to_plain_lrc(r['syncedLyrics'])}
    else: 
        return None

def lyrics_search(song,artists):
    global last_lyrics
    headers={"User-Agent": f"ARK FM (https://domain)"}
    r=requests.get("https://lrclib.net/api/search", params={"track_name": song, "artist_name": artists}, headers=headers).json()

    if r!=[]: r=r[0]

    last_lyrics = get_lyrics(r)
    #if not last_lyrics:
        #r=requests.get("https://lrclib.net/api/search"+params,headers=headers}).json()
        #if r!=0: r=r[0]
        #last_lyrics = get_lyrics(r)
        #if not last_lyrics:
        #socketio.emit('new_message', {"username":"lyrics_bot", "message":"Couldnt find lyrics" } , room='chat_room')
        #return
    socketio.emit('lyrics_update', {"lyrics":last_lyrics,"start_time":last_song_start}, room='chat_room')

def fetch_program_info():
    npt = datetime.now(timezone.utc) + np_offset

    weekday = npt.weekday()
    tday = days[weekday]
    hour = npt.hour
    
    day_schedule = sched[tday]
    day_schedule.sort(key=lambda x: x['time'])
    if hour<day_schedule[0]['time']:
        tday = days[(weekday - 1) % 7]
        day_schedule = sched[tday]
        day_schedule.sort(key=lambda x: x['time'])
        cur_show = day_schedule [-1]
    else:
        for show in day_schedule:
            if hour>=show['time']: cur_show=show

    global last_title, last_program, last_lyrics, last_song_start

    program = cur_show['program']
    if cur_show['stream']=="na":
        if program != last_program:
            last_program = program
            last_lyrics = ""
            last_title = ""
            socketio.emit('pinned_message', {
                'message': "Lyrics fetch will be skipped for current program."
            }, room='chat_room')
            socketio.emit('lyrics_update', {"lyrics": None, "start_time": last_song_start}, room='chat_room')
        return

    if not last_title and last_program == program: return

    if program!=last_program:
        socketio.emit('pinned_message', {
            'message': pinned_message
        }, room='chat_room')


    try:
        func = getattr(info_fetcher, "get_"+cur_show['id'])
        try: title = func()
        except: title= "  "
    except: title = ""

    if title!=last_title or program!=last_program:
        last_title=title
        last_program=program
        last_song_start=time.time()

        update_icecast_metadata(program,title)

        if ' by ' in title: socketio.start_background_task(lyrics_search,*title.rsplit(' by ',1))
        else: 
            last_lyrics=None
            # socketio.emit('new_message', {"username":"lyrics_bot", "message":"Skipped lyrics search" } , room='chat_room')

def call_fetch_program_info():
    if is_onair: return
    socketio.start_background_task(fetch_program_info)

call_fetch_program_info()
scheduler.add_job(
    func=call_fetch_program_info,
    trigger=IntervalTrigger(seconds=20),
    id='twentysec_task',
    name='Run every 20sec',
    replace_existing=True
)

def call_get_listener_count():
    socketio.start_background_task(get_listener_count)

call_get_listener_count()
scheduler.add_job(
    func=call_get_listener_count,
    trigger=IntervalTrigger(minutes=1),
    id='minute_task',
    name='Run every minute task',
    replace_existing=True
)


@app.route('/')
def index():
    if 'user' not in session:
        session['user'] = generate_username()
    
    return render_template('index.html',
                         mail_domain='.'.join(domain.split('.', 1)[1:]),
                         ZENO_ICECAST_MOUNT=ZENO_ICECAST_MOUNT, 
                         username=session['user'],
                         pinned_message=pinned_message, total_users=len(chat_users))



@app.route('/home')
def home():
    if 'user' not in session:
        session['user'] = generate_username()

    return render_template('home.html',
                         mail_domain='.'.join(domain.split('.', 1)[1:]),
                         ZENO_ICECAST_MOUNT=ZENO_ICECAST_MOUNT,
                         username=session['user'],
                         pinned_message=pinned_message, total_users=len(chat_users))


@app.get('/admin')
def admin():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
            return "Invalid password", 401

    session['user'] = "Admin"

    if not 'message' in request.args and not 'onair_title' in request.args: return "Session set"

    if 'message' in request.args:
        global pinned_message
        pinned_message = request.args.get('message')
    
        socketio.emit('pinned_message', {
            'message': pinned_message
        }, room='chat_room')

        return "Message Pinned!"

    if 'onair_title' in request.args:
        global is_onair
        onair_title = request.args.get('onair_title').strip()
        if not onair_title:
            is_onair=False
            os.remove(onair_file)
            return "Resuming Automted stream."
        else:
            is_onair=True
            with open(onair_file,'w') as f: pass
            update_icecast_metadata("ON AIR",onair_title)
            return "Stopped automated stream. Good luck with the self-stream"

@socketio.on('connect')
def handle_connect():
    global chat_users
    if 'user' in session:
        username = session['user']
        
        if not username in chat_users: 
            chat_users[username]=1
            # Send user list to all clients
            emit('online_update', {
                'total_users': len(chat_users)
            }, room='chat_room')
        else: chat_users[username]+=1

        join_room('chat_room')
        
        emit('online_update', {
            'total_users': len(chat_users)
        })

        if pinned_message:
            emit('pinned_message_update', {
                'message': pinned_message
            })

        emit('lyrics_update', {"lyrics":last_lyrics,"start_time":last_song_start})

        emit('listener_update', {"total_users":last_count })

listen_alongs = {} # {"saan":"prabesh_sp_uid"}
sp_activities={} # {"saaan_dc_id":{track:,user:,count:}}
sp_users = {} # {prabesh_sp_uid:{"token":}}
spotify_active_sockets = set()

spotify_users_file = os.path.join(base_dir, 'data', 'spotify_users.json')
spotify_users = {}
if os.path.exists(spotify_users_file):
    try:
        with open(spotify_users_file, 'r') as f:
            spotify_users = json.load(f)
    except Exception as e:
        print(f"Error loading {spotify_users_file}: {e}")
        spotify_users = {}

_startup_now = time.time()
for _idx, (_u_id, _u_info) in enumerate(spotify_users.items()):
    if _u_info.get('refresh_token'):
        sp_users[_u_id] = {'token': _u_info['refresh_token']}
    _u_info['next_poll'] = _startup_now + (_idx * 0.5)

@socketio.on('disconnect')
def handle_disconnect():
    global chat_users
    if 'user' in session:
        user = session['user']
        if user in chat_users:chat_users[user]-=1
        if chat_users[user] <= 0:
          del chat_users[user]
          emit('online_update', {
              'total_users': len(chat_users)
          }, room='chat_room')
    sp_uid = request.cookies.get('user_id')
    if sp_uid and sp_uid in spotify_active_sockets:
        spotify_active_sockets.discard(sp_uid)

@socketio.on('send_message')
def handle_send_message(data):
    if 'user' not in session:
        return
    
    username = session['user']
    message = data.get('message', '').strip()
    
    if not message:
        return

    message_data = {
        'username': username,
        'message': message
    }
    
    emit('new_message', message_data, room='chat_room')

def save_spotify_users():
    try:
        with open(spotify_users_file, 'w') as f:
            json.dump(spotify_users, f, indent=2)
    except Exception as e:
        print(f"Error saving {spotify_users_file}: {e}")

def sp_rf_token(sp_refresh):
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": sp_refresh},
        auth=(spotify_client_id, spotify_client_secret),
        timeout=10
    )
    if r.status_code == 200:
        return r.json().get('access_token')
    return None

def get_user_access_token(uid):
    user_info = spotify_users.get(uid)
    now = time.time()
    if user_info:
        if user_info.get('access_token') and user_info.get('expires_at', 0) > (now + 60):
            return user_info['access_token']
        refresh_token = user_info.get('refresh_token')
    elif uid in sp_users and 'token' in sp_users[uid]:
        refresh_token = sp_users[uid]['token']
    else:
        return None

    if not refresh_token:
        return None

    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(spotify_client_id, spotify_client_secret),
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            new_access = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            if user_info:
                user_info['access_token'] = new_access
                user_info['expires_at'] = now + expires_in
                if 'refresh_token' in data:
                    user_info['refresh_token'] = data['refresh_token']
                    if uid in sp_users:
                        sp_users[uid]['token'] = data['refresh_token']
                save_spotify_users()
            return new_access
        else:
            print(f"Failed to refresh token for {uid}: {r.status_code} {r.text}")
            if user_info and r.status_code in (400, 401):
                user_info['auth_failed'] = True
                save_spotify_users()
            return None
    except Exception as e:
        print(f"Exception refreshing token for {uid}: {e}")
        return None

def register_spotify_user(uid, refresh_token, access_token=None, expires_in=3600, display_name=None, profile_image=None):
    global spotify_users, sp_users
    now = time.time()
    user_info = spotify_users.get(uid, {})
    user_info['refresh_token'] = refresh_token
    if access_token:
        user_info['access_token'] = access_token
        user_info['expires_at'] = now + expires_in
    if display_name:
        user_info['display_name'] = display_name
    elif not user_info.get('display_name'):
        user_info['display_name'] = uid
    if profile_image is not None:
        user_info['profile_image'] = profile_image
    user_info['auth_failed'] = False
    user_info['idle_count'] = 0
    user_info['next_poll'] = now
    spotify_users[uid] = user_info
    sp_users[uid] = {'token': refresh_token}
    save_spotify_users()

def play_track_on_user_device(sp_token, track):
    if not sp_token or not track:
        return False, "Missing authentication or track"

    headers = {"Authorization": f"Bearer {sp_token}"}
    track_uri = track if track.startswith("spotify:track:") else f"spotify:track:{track}"

    device_id = None
    try:
        dev_resp = requests.get("https://api.spotify.com/v1/me/player/devices", headers=headers, timeout=5)
        if dev_resp.status_code == 200:
            devices = dev_resp.json().get('devices', [])
            # Priority 1: currently active device that is not restricted
            for d in devices:
                if d.get('is_active') and not d.get('is_restricted'):
                    device_id = d.get('id')
                    break
            # Priority 2: any non-restricted device
            if not device_id:
                for d in devices:
                    if not d.get('is_restricted') and d.get('id'):
                        device_id = d.get('id')
                        break
    except Exception as e:
        print(f"Error checking Spotify devices: {e}")

    url = "https://api.spotify.com/v1/me/player/play"
    if device_id:
        url += f"?device_id={device_id}"

    payload = {
        "uris": [track_uri],
        "position_ms": 0
    }

    try:
        rr = requests.put(url, headers=headers, json=payload, timeout=6)
        if rr.status_code not in (200, 204):
            err_msg = "Could not start playback on your Spotify player."
            try:
                err_data = rr.json()
                err_msg = err_data.get('error', {}).get('message', err_msg)
            except:
                pass
            return False, err_msg

        # Android / Mobile Connect quirk workaround:
        # Spotify mobile apps often accept `uris` (returning 204), unload the old song,
        # but pause rather than automatically starting the new track.
        # We verify player state and send a resume trigger if it was left paused.
        time.sleep(0.35)
        state_resp = requests.get("https://api.spotify.com/v1/me/player", headers=headers, timeout=4)
        if state_resp.status_code == 200 and state_resp.text.strip():
            state = state_resp.json()
            if not state.get('is_playing'):
                # Send resume command directly to device
                requests.put(url, headers=headers, timeout=4)

        return True, "OK"
    except Exception as e:
        print(f"Exception in play_track_on_user_device: {e}")
        return False, str(e)

def set_user_activity(uid, track, user, profile, title, artist, cover, start=None):
    global listen_alongs, sp_activities, sp_users
    if not start:
        start = time.time()

    previous_track = sp_activities.get(uid, {}).get('track')
    count = sp_activities.get(uid, {}).get('count', 0)

    sp_data = {
        "track": track,
        "user": user,
        "profile": profile,
        "title": title,
        "artist": artist,
        "cover": cover,
        "count": count,
        "start": start,
        "uid": uid
    }
    sp_activities[uid] = sp_data
    socketio.emit('sp_update', sp_data, room='spotify')

    # Only sync playback to listeners if the track has actually changed
    if uid in listen_alongs and previous_track != track:
        for listener_spid in list(listen_alongs[uid]):
            listener_token = get_user_access_token(listener_spid)
            if listener_token:
                success, _ = play_track_on_user_device(listener_token, track)
                if success:
                    continue
            if listener_spid in listen_alongs[uid]:
                listen_alongs[uid].remove(listener_spid)
                la_cnt = len(listen_alongs[uid])
                socketio.emit('count_update', {"uid": uid, "count": la_cnt}, room='spotify')
                sp_activities[uid]['count'] = la_cnt

def remove_user_activity(uid):
    global sp_activities
    if uid in sp_activities:
        sp_activities.pop(uid, None)
        socketio.emit('sp_remove', {"uid": uid}, room='spotify')

def handle_user_inactive(uid, user_info):
    now = time.time()
    user_info['is_active'] = False
    notified_flags.pop(uid, None)
    user_info['current_track'] = None
    idle_count = user_info.get('idle_count', 0) + 1
    user_info['idle_count'] = idle_count

    remove_user_activity(uid)

    # Industry standard tiered backoff:
    # 30s -> 60s (1m) -> 120s (2m) -> 300s (5m steady state)
    idle_tiers = [30, 60, 120, 300]
    tier_idx = min(idle_count - 1, len(idle_tiers) - 1)
    interval = idle_tiers[tier_idx]

    # Active site presence boost: if user has /spotify page open, don't back off to 5 min
    if uid in spotify_active_sockets:
        interval = min(interval, 45)

    user_info['next_poll'] = now + interval
    save_spotify_users()

def poll_single_user(uid):
    user_info = spotify_users.get(uid)
    if not user_info or user_info.get('auth_failed'):
        return

    token = get_user_access_token(uid)
    now = time.time()
    if not token:
        user_info['next_poll'] = now + 120
        save_spotify_users()
        return

    try:
        resp = requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8
        )
    except Exception as e:
        print(f"Error querying Spotify player for {uid}: {e}")
        user_info['next_poll'] = now + 30
        return

    user_info['last_poll'] = now

    if resp.status_code == 429:
        retry_after = int(resp.headers.get('Retry-After', 10))
        user_info['next_poll'] = now + retry_after + 2
        save_spotify_users()
        return

    if resp.status_code == 401:
        user_info['expires_at'] = 0
        user_info['next_poll'] = now + 5
        save_spotify_users()
        return

    if resp.status_code == 204 or not resp.text.strip():
        handle_user_inactive(uid, user_info)
        return

    if resp.status_code == 200:
        try:
            data = resp.json()
        except:
            handle_user_inactive(uid, user_info)
            return

        is_playing = data.get('is_playing', False)
        item = data.get('item')
        if not is_playing or not item or item.get('type') != 'track':
            handle_user_inactive(uid, user_info)
            return

        track_id = item.get('id')
        if not track_id:
            handle_user_inactive(uid, user_info)
            return

        title = item.get('name', 'Unknown')
        artists = ", ".join(a.get('name', '') for a in item.get('artists', []))
        duration_ms = item.get('duration_ms', 0)
        progress_ms = data.get('progress_ms', 0)
        images = item.get('album', {}).get('images', [])
        cover = images[0]['url'] if images else ""

        timestamp_ms = data.get('timestamp') or int(now * 1000)
        start_ts = (timestamp_ms - progress_ms) / 1000.0

        user_name = user_info.get('display_name') or uid
        profile_img = user_info.get('profile_image') or ""

        set_user_activity(
            uid=uid,
            track=track_id,
            user=user_name,
            profile=profile_img,
            title=title,
            artist=artists,
            cover=cover,
            start=start_ts
        )

        if uid != EXCLUDED_NOTIFY_UID and not notified_flags.get(uid):
            notified_flags[uid] = True
            notify_discord_listen_along()

        user_info['idle_count'] = 0
        user_info['current_track'] = track_id
        user_info['is_active'] = True

        # Adaptive interval calculation
        remaining_sec = max(0, (duration_ms - progress_ms) / 1000.0)
        if remaining_sec <= 20:
            next_interval = max(5, int(remaining_sec) + 1)
        else:
            next_interval = 15

        user_info['next_poll'] = now + next_interval
        save_spotify_users()
        return

    user_info['next_poll'] = now + 60
    save_spotify_users()

def spotify_worker_tick():
    now = time.time()
    due_users = []
    for uid, info in list(spotify_users.items()):
        if info.get('auth_failed'):
            continue
        if info.get('next_poll', 0) <= now:
            due_users.append(uid)
            info['next_poll'] = now + 30

    for uid in due_users:
        socketio.start_background_task(poll_single_user, uid)

scheduler.add_job(
    func=spotify_worker_tick,
    trigger=IntervalTrigger(seconds=3),
    id='spotify_poller_task',
    name='Spotify Poller Worker',
    replace_existing=True
)

@app.get('/spotify')
def sp_home():
    sp_token=request.cookies.get('access_token')
    sp_refresh=request.cookies.get('refresh_token')
    sp_uid_cookie=request.cookies.get('user_id')
    user=None
    sp_uid=None
    profile_img=""
    if sp_token:
        try:
            r=requests.get('https://api.spotify.com/v1/me',headers = {"Authorization":"Bearer "+sp_token}, timeout=8)
            if r.status_code==200:
                udata=r.json()
                user=udata.get('display_name') or udata.get('id')
                sp_uid=udata.get('id')
                if udata.get('images'):
                    profile_img = udata['images'][0].get('url', '')
        except Exception as e:
            print(f"Error in sp_home checking access token: {e}")

    if not user and sp_refresh:
        sp_token = (sp_uid_cookie and get_user_access_token(sp_uid_cookie)) or sp_rf_token(sp_refresh)
        if sp_token:
            try:
                r=requests.get('https://api.spotify.com/v1/me',headers = {"Authorization":"Bearer "+sp_token}, timeout=8)
                if r.status_code==200:
                    udata=r.json()
                    user=udata.get('display_name') or udata.get('id')
                    sp_uid=udata.get('id')
                    if udata.get('images'):
                        profile_img = udata['images'][0].get('url', '')
            except Exception as e:
                print(f"Error in sp_home checking refreshed token: {e}")

    html_content = render_template('spotify.html', user=user, spotify_client_id=spotify_client_id, domain=domain)
    resp = make_response(html_content)
    if not user:
        resp.delete_cookie('refresh_token', path='/')
        resp.delete_cookie('access_token', path='/')
        resp.delete_cookie('user_id', path='/')
    else:
        register_spotify_user(
            uid=sp_uid,
            refresh_token=sp_refresh,
            access_token=sp_token,
            display_name=user,
            profile_image=profile_img
        )
        resp.set_cookie('refresh_token', sp_refresh, path='/', httponly=True, samesite='Lax')
        resp.set_cookie('access_token', sp_token, path='/', httponly=True, samesite='Lax')
        resp.set_cookie('user_id', sp_uid, path='/', httponly=True, samesite='Lax')
    return resp

@socketio.on('hi_spotify')
def handle_spotify_con(data):
    sp_uid = request.cookies.get('user_id','')
    if sp_uid:
        spotify_active_sockets.add(sp_uid)
        if sp_uid in spotify_users:
            spotify_users[sp_uid]['next_poll'] = time.time()

    leave_room('chat_room')
    socketio.emit('sp_list', sp_activities)
    join_room('spotify')

    for uid in listen_alongs:
        for listener_refresh in listen_alongs[uid]:
            if listener_refresh==sp_uid:
                socketio.emit('listening_to', {'uid':uid})
                return

@socketio.on('stop_listen_along')
def stop_listen_along():
    global sp_activities
    sp_token = request.cookies.get('access_token')
    sp_uid = request.cookies.get('user_id')
    if not sp_token: return

    rr=requests.put("https://api.spotify.com/v1/me/player/pause",headers={"Authorization":"Bearer "+sp_token})
    if rr.status_code!=200:
        err_msg = "Could not pause playback."
        try:
            err_msg = rr.json()['error']['message']
        except:
            pass
        emit('error', {"message": err_msg})
        return

    for la in listen_alongs:
        if sp_uid in listen_alongs[la]:
            listen_alongs[la].remove(sp_uid)
            la_cnt=len(listen_alongs[la])
            socketio.emit('count_update', {"uid":la,"count":la_cnt} , room='spotify')
            sp_activities[la]['count']=la_cnt

@socketio.on('add_to_playlist')
def add_to_playlist(data):
    track = data.get('track','').strip()
    user_id = request.cookies.get('user_id')
    sp_token = (user_id and get_user_access_token(user_id)) or request.cookies.get('access_token')
    sp_refresh = request.cookies.get('refresh_token')

    pl_name="ark - listen along"

    if not sp_token or not user_id: return
    headers={"Authorization":"Bearer "+sp_token}

    the_pl=None
    url="https://api.spotify.com/v1/me/playlists?limit=50"
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            sp_token = (user_id and get_user_access_token(user_id)) or sp_rf_token(sp_refresh)
            if not sp_token:
                emit('error', {"message":"Try again later!" })
                return
            headers={"Authorization":"Bearer "+sp_token}
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                emit('error', {"message":"Try again later!" })
                return

        for playlist in response.json().get("items", []):
            if playlist["name"] == pl_name:
                if playlist['owner']['id']==user_id:
                    the_pl=playlist['id']
                    break
        if the_pl: break
        url = response.json().get('next')

    if not the_pl:
        the_pl=requests.post(f"https://api.spotify.com/v1/users/{user_id}/playlists",headers = {"Authorization":"Bearer "+sp_token},json={"name":pl_name, "public": False}).json()['id']
    requests.post(f"https://api.spotify.com/v1/playlists/{the_pl}/tracks",json={"uris":[f"spotify:track:{track}"]}, headers={"Authorization":"Bearer "+sp_token})
    emit('alert', {"message":"Added to your playlist." })

@socketio.on('listen_along')
def listen_along(data):
    global listen_alongs, sp_activities, sp_users
    user_id = request.cookies.get('user_id')

    uid = data.get('uid', '').strip()
    track = data.get('track','').strip()
    sp_refresh = request.cookies.get('refresh_token')

    if not user_id in sp_users: sp_users[user_id]={}
    sp_users[user_id]={"token":sp_refresh}

    if not sp_refresh: return
    for la in listen_alongs:
        if user_id in listen_alongs[la]:
            listen_alongs[la].remove(user_id)
            la_cnt=len(listen_alongs[la])
            socketio.emit('count_update', {"uid":la,"count":la_cnt} , room='spotify')
            sp_activities[la]['count']=la_cnt

    sp_token = (user_id and get_user_access_token(user_id)) or sp_rf_token(sp_refresh)
    if not sp_token:
        emit('error', {"message": "Could not authenticate with Spotify."})
        return

    success, err_msg = play_track_on_user_device(sp_token, track)
    if not success:
        emit('error', {"message": err_msg})
        return

    if not uid in listen_alongs: listen_alongs[uid]=[]
    listen_alongs[uid].append(user_id)
    la_cnt=len(listen_alongs[uid])
    socketio.emit('count_update', {"uid":uid,"count":la_cnt} , room='spotify')
    sp_activities[uid]['count']=la_cnt

@app.get('/activity_seek')
def sp_activity_seek():
    return 'meh'

@app.get('/activity')
def sp_activity():
    track = request.args.get('track')
    uid = request.args.get('uid')
    user = request.args.get('user')
    profile = request.args.get('profile')
    title = request.args.get('title')
    artist = request.args.get('artist')
    cover = request.args.get('cover')
    start = request.args.get('start')
    if start:
        try:
            start = datetime.fromisoformat(start.replace(' 00:00', '+00:00')).timestamp()
        except:
            start = time.time()
    else:
        start = time.time()

    set_user_activity(uid=uid, track=track, user=user, profile=profile,
                      title=title, artist=artist, cover=cover, start=start)
    return 'OK'

@app.get('/activity_rm')
def sp_activity_rm():
    uid = request.args.get('uid')
    if uid:
        remove_user_activity(uid)
    return 'OK'

@app.get('/callback')
def sp_callback():
    error = request.args.get('error')
    if error:
        print(f"Spotify authorization error in callback: {error}")
        return render_template('spotify.html', alert=f"Spotify Authorization Failed: {error}")

    code = request.args.get('code')
    if not code:
        return render_template('spotify.html', alert="Missing authorization code from Spotify.")

    try:
        token_resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"https://{domain}/callback",
                "client_id": spotify_client_id,
                "client_secret": spotify_client_secret
            },
            timeout=10
        )
    except Exception as e:
        print(f"Exception during Spotify token exchange: {e}")
        return render_template('spotify.html', alert="Network error during Spotify authorization.")

    if token_resp.status_code != 200:
        print(f"Spotify token exchange failed ({token_resp.status_code}): {token_resp.text}")
        return render_template('spotify.html', alert="Spotify OAuth Failed! Try again later.")

    try:
        r = token_resp.json()
    except Exception as e:
        print(f"Error parsing token JSON: {e}, text: {token_resp.text}")
        return render_template('spotify.html', alert="Spotify OAuth Failed: Invalid token response.")

    access_token = r.get('access_token')
    refresh_token = r.get('refresh_token')
    if not access_token or not refresh_token:
        print(f"Missing tokens in response: {r}")
        return render_template('spotify.html', alert="Spotify OAuth Failed! Incomplete token data.")

    try:
        user_resp = requests.get(
            'https://api.spotify.com/v1/me',
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
    except Exception as e:
        print(f"Exception fetching Spotify user profile: {e}")
        return render_template('spotify.html', alert="Network error fetching user profile.")

    if user_resp.status_code != 200:
        print(f"Spotify /v1/me failed ({user_resp.status_code}): {user_resp.text}")
        return render_template('spotify.html', alert=f"Failed to fetch Spotify profile ({user_resp.status_code}).")

    try:
        user = user_resp.json()
    except Exception as e:
        print(f"Error parsing /v1/me JSON: {e}, text: {user_resp.text}")
        return render_template('spotify.html', alert="Failed to parse Spotify user profile.")

    user_id = user.get('id')
    if not user_id:
        print(f"User response missing 'id': {user}")
        return render_template('spotify.html', alert="Spotify user profile missing user ID.")

    profile_img = ""
    if user.get('images'):
        profile_img = user['images'][0].get('url', '')

    display_name = user.get('display_name') or user_id

    register_spotify_user(
        uid=user_id,
        refresh_token=refresh_token,
        access_token=access_token,
        expires_in=r.get('expires_in', 3600),
        display_name=display_name,
        profile_image=profile_img
    )

    resp = make_response(redirect('/spotify'))
    resp.set_cookie('refresh_token', refresh_token, path='/', httponly=True, samesite='Lax')
    resp.set_cookie('access_token', access_token, path='/', httponly=True, samesite='Lax')
    resp.set_cookie('user_id', user_id, path='/', httponly=True, samesite='Lax')
    return resp

@app.get('/playlist')
def get_playlist():
    global radio_queue

    uid = request.args.get('uid', '').strip()
    if not uid in radio_queue: return 'Invalid radio'

    plid = request.args.get('playlist','').strip()
    sp_token = request.cookies.get('access_token')

    url = f'https://api.spotify.com/v1/playlists/{plid}/tracks'
    headers = {'Authorization': f'Bearer {sp_token}'}

    tracks = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for item in data['items']:
                item=item['track']
                try: tracks.append([item['id'],item['name'],item["artists"][0]['name'],int(item['duration_ms']/1000)-1])
                except: pass
            url = data.get('next')
        else:
            return f"Error fetching playlist: {response.text}"

    if not tracks: return "empty"
    radio_queue[uid]= tracks
    with open(base_dir+"/radio_queue.json","w") as f: json.dump(radio_queue,f)
    return "OK"

radio_queue=json.load(open(base_dir+"/radio_queue.json"))
def play_radio(radio,index):
    ltn = len(radio_queue[radio])
    if ltn==0: return
    if index>ltn: index=0
    to_play=radio_queue[radio][index]

    with app.test_request_context('/activity', query_string={
        'track': to_play[0],
        'uid': radio,
        'title': to_play[1],
        'artist': to_play[2],
    }): sp_activity()

    timer = threading.Timer(to_play[-1], play_radio,args=(radio,index+1))
    timer.start()

for radio in radio_queue:
    play_radio(radio,0)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
