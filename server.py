import time
import os
from glob import glob
import urllib.request
import sys
from io import StringIO
from queue import Queue
from threading import Thread

from flask_socketio import SocketIO
import eventlet
from flask import Flask, send_from_directory, render_template, request

from config import ip_address, port, server_quality
from main import emit_console, process


# Init app
app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
process_queue = Queue()

BAR_LENGTH = 50


def process_by_link(link, quality, limit, sid):
    backup = sys.stdout
    sys.stdout = mystdout = StringIO()

    print('Processing started')
    print(' ' * BAR_LENGTH)
    console_prefix, prefix_path = '', 'static/'

    start_time = int(time.time() * 1000)  # Current time in milliseconds
    emit_console(start_time, mystdout.getvalue(), sid, socketio)

    pdf_file = "output/remote_document.pdf"
    urllib.request.urlretrieve(link, pdf_file)

    process(prefix_path, start_time, pdf_file, quality, int(limit), True, sid, socketio, mystdout)

    # Send download paths
    target_directory = f'{prefix_path}output/csv'
    paths = []
    for file in glob(os.path.join(target_directory, '*.csv')):
        paths.append(file)

    for i, path in enumerate(paths):
        paths[i] = path.replace(prefix_path, '')

    print("Starting download")
    current_time = int(time.time() * 1000)
    socketio.emit('progress', {
        'time': current_time - start_time,
        'stdout': console_prefix + mystdout.getvalue()
    }, room=sid)

    socketio.emit('download', paths, room=sid)
    sys.stdout = backup


# Return main page
@app.route('/')
def root():
    return render_template('main.html')


@socketio.on('send')
def get_data(message):
    if not message['link'].lower().startswith('http'):
        return

    if not process_queue.empty():
        socketio.emit('progress', {'stdout': 'Server busy', 'time': 0}, room=request.sid)

    process_queue.put({'sid': request.sid, 'message': message})


# Get files from server (e.g libs)
@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


def game_loop():
    while True:
        if process_queue.empty() > 0:
            item = process_queue.get()
            process_by_link(item['message']['link'], server_quality, item['message']['limit'], item['sid'])
            process_queue.task_done()

        time.sleep(1)


if __name__ == "__main__":
    eventlet.monkey_patch()

    x = Thread(target=game_loop, args=())
    x.start()

    print(f"Listening on http://{ip_address}:{port}")
    socketio.run(app, host=ip_address, port=port)
