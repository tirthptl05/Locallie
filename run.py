# run.py

from app import create_app, socketio
import app.sockets  # 👈 important to load the event listeners

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True)
