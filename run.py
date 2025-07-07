from app import create_app, socketio  # ✅ assuming run.py is outside app folder

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True)
