from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room
import random
import string
import secrets
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

chat_users = {}
pinned_message = ""
ADMIN_PASSWORD = "adarkmin"  

from utils.rando import generate_username

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

        emit('pinned_message_update', {
            'message': pinned_message
        })
        
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
