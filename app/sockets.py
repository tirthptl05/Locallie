# app/sockets.py

from flask_socketio import emit
from . import socketio

@socketio.on('send_reply')
def handle_send_reply(data):
    # Example data: {'help_id': 1, 'message': 'Hello', 'from': 'local@abc.com'}
    emit('new_reply', data, broadcast=True)
