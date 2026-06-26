from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify, session, make_response, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import secrets
from datetime import datetime, timezone, timedelta
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
pinned_message = 'Send "/as" to toggle autoscroll on new user messages.'
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
last_title=""
last_program=""
last_lyrics=""
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

    if not token:
        last_count='N/A'
    else:
        rr = requests.get(f"https://stream-tools.zenomedia.com/stations/{ZENO_ICECAST_MOUNT}/stats/live?include_outputs=true",headers={"Authorization": "Bearer "+token}).json()
        totalcnt=0
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
    if 'plainLyrics' in r: return r['plainLyrics']
    elif 'syncedLyrics' in r: return convert_to_plain_lrc(r['syncedLyrics'])
    else: return None

def lyrics_search(song,artists):
    global last_lyrics
    params=f"?track_name={song}&artist_name={artists}"
    headers={"User-Agent": f"ARK FM (https://domain)"}
    r=requests.get("https://lrclib.net/api/search"+params,headers=headers).json()

    if r!=[]: r=r[0]

    last_lyrics = get_lyrics(r)
    if not last_lyrics:
        #r=requests.get("https://lrclib.net/api/search"+params,headers=headers}).json()
        #if r!=0: r=r[0]
        #last_lyrics = get_lyrics(r)
        #if not last_lyrics:
        socketio.emit('new_message', {"username":"lyrics_bot", "message":"Couldnt find lyrics" } , room='chat_room')
        return
    socketio.emit('new_message', {"username":"lyrics_bot", "message":last_lyrics } , room='chat_room')

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

    global last_title, last_program, last_lyrics

    if cur_show['stream']=="na":
        last_program = cur_show['program']
        last_lyrics = ""
        last_title = ""
        socketio.emit('pinned_message', {
            'message': "Lyrics fetch will be skipped for current program."
        }, room='chat_room')
        return

    program = cur_show['program']
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

        update_icecast_metadata(program,title)

        if ' by ' in title: socketio.start_background_task(lyrics_search,*title.split('by'))
        else: 
            last_lyrics=""
            socketio.emit('new_message', {"username":"lyrics_bot", "message":"Skipped lyrics search" } , room='chat_room')

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

        if last_lyrics:
            emit('new_message', {"username":"lyrics_bot", "message":last_lyrics })

        emit('listener_update', {"total_users":last_count })

listen_alongs = {} # {"saan":"prabesh_sp_uid"}
sp_activities={} # {"saaan_dc_id":{track:,user:,count:}}
sp_users = {} # {prabesh_sp_uid:{"token":}}

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

def sp_rf_token(sp_refresh):
    r=requests.post("https://accounts.spotify.com/api/token",data={"grant_type":"refresh_token","refresh_token":sp_refresh},auth=(spotify_client_id,spotify_client_secret))
    if r.status_code==200:
        sp_token=r.json()['access_token']
    else: sp_token=None
    return sp_token

@app.get('/spotify')
def sp_home():
    sp_token=request.cookies.get('access_token')
    sp_refresh=request.cookies.get('refresh_token')
    user=None
    if sp_token:
        r=requests.get('https://api.spotify.com/v1/me',headers = {"Authorization":"Bearer "+sp_token})
        if r.status_code==200:
            user=r.json()['display_name']
            sp_uid=r.json()['id']
        elif sp_refresh:
            sp_token=sp_rf_token(sp_refresh)
            if sp_token:
                r=requests.get('https://api.spotify.com/v1/me',headers = {"Authorization":"Bearer "+sp_token}).json()
                user=r['display_name']
                sp_uid=r['id']

    html_content = render_template('spotify.html', user=user, spotify_client_id=spotify_client_id, domain=domain)
    resp = make_response(html_content)
    if not user:
        resp.delete_cookie('refresh_token', path='/')
        resp.delete_cookie('access_token', path='/')
        resp.delete_cookie('user_id', path='/')
    else:
        global sp_users
        sp_users[sp_uid]={'token':sp_refresh}
        resp.set_cookie('refresh_token', sp_refresh, path='/', httponly=True, samesite='Lax')
        resp.set_cookie('access_token', sp_token, path='/', httponly=True, samesite='Lax')
        resp.set_cookie('user_id', sp_uid, path='/', httponly=True, samesite='Lax')
    return resp

@socketio.on('hi_spotify')
def handle_spotify_con(data):
    sp_uid = request.cookies.get('user_id','')
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
        emit('error', {"message":rr.json()['error']['message'] })
        return

    for la in listen_alongs:
        if sp_uid in listen_alongs[la]:
            listen_alongs[la].remove(sp_uid)
            la_cnt=len(listen_alongs[la])
            socketio.emit('count_update', {"uid":la,"count":la_cnt} , room='spotify')
            sp_activities[la]['count']=la_cnt
    del sp_users[sp_uid]

@socketio.on('add_to_playlist')
def add_to_playlist(data):
    track = data.get('track','').strip()
    sp_token = request.cookies.get('access_token')
    sp_refresh=request.cookies.get('refresh_token')
    user_id = request.cookies.get('user_id')

    pl_name="ark - listen along"

    if not sp_token or not user_id: return
    headers={"Authorization":"Bearer "+sp_token}

    the_pl=None
    url="https://api.spotify.com/v1/me/playlists?limit=50"
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            sp_token=sp_rf_token(sp_refresh)
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
        url = data.get('next')

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

    sp_token=sp_rf_token(sp_refresh)
    rr=requests.put("https://api.spotify.com/v1/me/player/play",headers={"Authorization":"Bearer "+sp_token},json={"uris":["spotify:track:"+track]})
    if rr.status_code!=204:
        emit('error', {"message":rr.json()['error']['message'] })
        return

    if not uid in listen_alongs: listen_alongs[uid]=[]
    listen_alongs[uid].append(user_id)
    la_cnt=len(listen_alongs[uid])
    socketio.emit('count_update', {"uid":uid,"count":la_cnt} , room='spotify')
    sp_activities[uid]['count']=la_cnt


@app.get('/activity_seek')
def sp_activity_seek():
    return 'meh'
    uid = request.args.get('uid')
    seek = int(request.args.get('seek'))
    if not uid in sp_activities: return 'UID khoi'

    position_ms = int((datetime.now(timezone.utc).timestamp() - sp_activities[uid]['start'])*1000)
    position_ms+=seek

    if uid in listen_alongs:
        for listener_spid in listen_alongs[uid]:
            print(sp_users)
            listener_refresh = sp_users[listener_spid]['token']
            print(sp_users)
            listener_token=sp_rf_token(listener_refresh)
            if listener_token:
                rr=requests.put("https://api.spotify.com/v1/me/player/seek",headers={"Authorization":"Bearer "+listener_token},params={"position_ms":position_ms})
                print(rr.text)
    return 'OK'

@app.get('/activity')
def sp_activity():
    global listen_alongs,sp_activities, sp_users
    track = request.args.get('track')
    uid = request.args.get('uid')
    user = request.args.get('user')
    profile = request.args.get('profile')
    title = request.args.get('title')
    artist=request.args.get('artist')
    cover=request.args.get('cover')
    start=request.args.get('start')
    if start: start = datetime.fromisoformat(start.replace(' 00:00', '+00:00')).timestamp()
    else: start=datetime.now(timezone.utc).timestamp()

    count=0
    if uid in sp_activities: count = sp_activities[uid]['count']
    sp_data={"track":track,"user":user,"profile":profile,"title":title,"artist": artist,"cover":cover,"count":count,"start":start}
    sp_activities[uid]=sp_data
    sp_data['uid']=uid
    socketio.emit('sp_update', sp_data , room='spotify')

    if uid in listen_alongs:
        for listener_spid in listen_alongs[uid]:
            listener_refresh = sp_users[listener_spid]['token']
            listener_token=sp_rf_token(listener_refresh)
            if listener_token:
                rr=requests.put("https://api.spotify.com/v1/me/player/play",headers={"Authorization":"Bearer "+listener_token},json={"uris":["spotify:track:"+track]})
                print(rr.text)
                if rr.status_code==204:
                    continue
            del sp_users[listener_spid]                    
            listen_alongs[uid].remove(listener_spid)
            la_cnt=len(listen_alongs[uid])
            socketio.emit('count_update', {"uid":uid,"count":la_cnt} , room='spotify')
            sp_activities[uid]['count']=la_cnt

    return 'OK'

@app.get('/activity_rm')
def sp_activity_rm():
    uid = request.args.get('uid')

    sp_activities.pop(uid,None)
    socketio.emit('sp_remove', {"uid":uid} , room='spotify')

    # listen_alongs.pop(uid,None)

    return 'OK'

@app.get('/callback')
def sp_callback():
    global sp_users
    code = request.args.get('code')
    r=requests.post("https://accounts.spotify.com/api/token",data={"grant_type":"authorization_code","code":code,"redirect_uri":f"https://{domain}/callback","client_id":spotify_client_id,"client_secret":spotify_client_secret}).json()
    if not 'access_token' in r: return render_template('spotify.html',alert="Spotify Oauth Failed! Try again later.")

    user=requests.get('https://api.spotify.com/v1/me',headers = {"Authorization":"Bearer "+r['access_token']}).json()
    html_content = redirect('/spotify')
    resp = make_response(html_content)

    resp.set_cookie('refresh_token', r['refresh_token'], path='/', httponly=True, samesite='Lax')
    resp.set_cookie('access_token', r['access_token'], path='/', httponly=True, samesite='Lax')
    resp.set_cookie('user_id', user['id'], path='/', httponly=True, samesite='Lax')
    sp_users[user['id']]={"token":r['refresh_token']}
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
