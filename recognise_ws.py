import time
import os
from glob import glob
import urllib.request
import sys
from io import StringIO
from threading import Thread
from collections import deque

from flask_socketio import SocketIO
import eventlet
from flask import Flask, send_from_directory, render_template, request

from config import ip_address, port, server_quality
from recognise_cli import emit_console, process, clear_directory


# Init app
app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
process_queue = deque()
process_index = -1

user_connected = dict()

BAR_LENGTH = 50


def check_if_url_exists(url):
    try:
        u = urllib.request.urlopen(url)
        u.close()
        return True
    except:
        return False


def process_by_link(link, quality, limit, sid):
    backup = sys.stdout
    sys.stdout = mystdout = StringIO()

    console_prefix, prefix_path = '', 'static/'
    start_time = int(time.time() * 1000)  # Current time in milliseconds

    pdf_file = f"output/remote_document_{process_index}.pdf"
    if check_if_url_exists(link):
        urllib.request.urlretrieve(link, pdf_file)
        print('Processing started\n')
        emit_console(start_time, mystdout.getvalue(), sid, socketio)

    else:
        print('There is a problem loading file from this link. Check if it is correct')
        emit_console(start_time, mystdout.getvalue(), sid, socketio)
        
        sys.stdout = backup
        return False

    # Main spreadsheet processing
    process(prefix_path, start_time, pdf_file, quality, int(limit), True, sid, socketio, mystdout, user_connected)

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
    return True


# Return main page
@app.route('/')
def root():
    return render_template('main.html')


@socketio.event
def connect():
    user_connected[request.sid] = True


@socketio.event
def connect_error(data):
    print("The connection failed!")


@socketio.event
def disconnect():
    user_connected[request.sid] = False


@socketio.on('send')
def get_data(message):
    if not message['link'].lower().startswith('http'):
        return

    if len(process_queue) > 0:
        for elem in process_queue:
            if elem['sid'] == request.sid:
                socketio.emit('progress', {'stdout': 'You already have an ongoing request', 'time': 0}, room=request.sid)
                return

        socketio.emit('progress', {'stdout': 'Server busy', 'time': 0}, room=request.sid)

    process_queue.append({'sid': request.sid, 'message': message})


# Get files from server (e.g libs)
@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


def process_caller():
    global process_index, process_queue

    while True:
        if len(process_queue) > 0:
            item = process_queue[0]
            print(f'Started processing of {item}')

            process_by_link(item['message']['link'], server_quality, item['message']['limit'], item['sid'])
            print(f'Processing ended')
            
            process_index += 1
            process_queue.popleft()

        time.sleep(1)


if __name__ == "__main__":
    eventlet.monkey_patch()
    clear_directory('output/remote_document_*')

    x = Thread(target=process_caller, args=())
    x.start()

    print(f"Listening on http://{ip_address}:{port}")
    socketio.run(app, host=ip_address, port=port)
