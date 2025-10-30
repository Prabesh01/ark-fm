from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room
import random
import string
import secrets
from datetime import datetime, timezone
import os
base_dir = os.path.dirname(os.path.abspath(__file__))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'

from flask_session import Session
Session(app)
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False, async_mode='eventlet')

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

import eventlet
eventlet.monkey_patch()

chat_users = {}
pinned_message = 'Send "/as" to toggle autoscroll on new user messages.'
ADMIN_PASSWORD = "adarkmin"  
last_title=""
last_program=""
last_lyrics=""
last_count=0

from utils.rando import generate_username
from utils import info_fetcher

import json
sched = json.load(open(base_dir+'/static/json/schedule.json'))
creds = json.load(open(base_dir+'/creds.json'))

def get_zeno_token():
    global creds    
    rr = requests.post("https://tools.zeno.fm/auth/realms/broadcasters/protocol/openid-connect/token",data={"grant_type":"refresh_token","refresh_token":creds['refresh_token'],"client_id":"zeno-tools"})

    if rr.status_code !=200: return None
    with open(base_dir+'/creds.json','w') as f:
        json.dump(rr.json(),f)
    return rr.json()['access_token']

def get_listener_count():
    global last_count
    token = creds['access_token']
    test_token = requests.get("https://stream-tools.zenomedia.com/users/me",headers={"Authorization": "Bearer "+token})
    if test_token.json() == {"message":"Not authorized"}: token = get_token()

    if not token:
        last_count='N/A'

    rr = requests.get("https://stream-tools.zenomedia.com/stations/bfeoaqiomuquv/stats/live?include_outputs=true",headers={"Authorization": "Bearer "+token}).json()
    totalcnt=0
    for d in rr['data']: totalcnt += d['uniqueListeners']

    if last_count==totalcnt: return
    last_count=totalcnt
   
    socketio.emit('listener_update', {"total_users":last_count } , room='chat_room')
    
import datetime
from datetime import timedelta
np_offset = timedelta(hours=5, minutes=45)

days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

def update_icecast_metadata(prog, title):
    url="http://link.zeno.fm:80/admin/metadata?mount=/bfeoaqiomuquv&mode=updinfo&song="
    requests.get(f"{url}{title} [{prog}]", auth=("source", "6GeTEy67"))

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
    headers={"User-Agent": "ARK FM (https://ark.cote.ws/)"}
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
    npt = datetime.datetime.now(timezone.utc) + np_offset

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
                         username=session['user'],
                         pinned_message=pinned_message, total_users=len(chat_users))

@app.get('/admin')
def admin():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
            return "Invalid password", 401

    session['user'] = "Admin"

    if not 'message' in request.args: return "Session set"

    global pinned_message
    pinned_message = request.args.get('message')
    
    socketio.emit('pinned_message', {
        'message': pinned_message
    }, room='chat_room')

    return "Pinned!"

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

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
