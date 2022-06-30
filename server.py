import time
import os
from glob import glob
import cv2
import urllib.request
import sys
from io import StringIO
from queue import Queue
from threading import Thread

from flask_socketio import SocketIO, emit
from pdf2image import convert_from_path
import eventlet
from flask import Flask, send_from_directory, send_file, render_template, Response, request, g

from ip import ip_address, port
from main import detect_table, Rect, clear_directory
from parse_table import convert_to_csv


# Init app
app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
process_queue = Queue()

BAR_LENGTH = 50


def emit_console(start_time, message, sid):
    current_time = int(time.time() * 1000)
    socketio.emit('progress', {
        'time': current_time - start_time,
        'stdout': message
    }, room=sid)


def process_by_link(link, quality, limit, sid):
    backup = sys.stdout
    sys.stdout = mystdout = StringIO()

    print('Processing started')
    print(' ' * BAR_LENGTH)
    console_prefix, prefix_path = '', 'static/'

    start_time = int(time.time() * 1000)  # Current time in milliseconds
    emit_console(start_time, mystdout.getvalue(), sid)

    # Clear output directory
    clear_directory(f'{prefix_path}output/csv/*')
    clear_directory(f'{prefix_path}output/detects/*')
    clear_directory(f'{prefix_path}output/pages/*')
    clear_directory(f'{prefix_path}output/cropped/*')

    pdf_file = "output/remote_document.pdf"
    urllib.request.urlretrieve(link, pdf_file)
    pages = convert_from_path(pdf_file, quality)

    if limit == -1:
        limit = len(pages)

    for page_index, page in enumerate(pages[:int(limit)]):
        print(f'Processing page number {page_index + 1}')

        image_path = f'{prefix_path}output/pages/page_{page_index}.jpg'
        page.save(image_path, 'PNG')  # Save page as an image

        detected_cont = detect_table(image_path, page_index, 'static/')

        if detected_cont != Rect(0, 0, 0, 0):
            image = cv2.imread(image_path)
            cropped = image[detected_cont.y:detected_cont.y + detected_cont.h,
                      detected_cont.x:detected_cont.x + detected_cont.w]

            cropped_filename = f"{prefix_path}output/cropped/cropped_table_{page_index + 1}.jpg"
            cv2.imwrite(cropped_filename, cropped)

            # Convert to csv
            console_prefix = console_prefix + mystdout.getvalue()
            mystdout = convert_to_csv(cropped_filename, f"{prefix_path}output/csv/export_table_page_{page_index + 1}.csv",
                           socketio, mystdout, sid, start_time, console_prefix)
            print('CSV file saved\n')

        else:
            print('No tables on this page\n')

        emit_console(start_time, console_prefix + mystdout.getvalue(), sid)

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
            process_by_link(item['message']['link'], 150, item['message']['limit'], item['sid'])
            process_queue.task_done()

        time.sleep(1)


if __name__ == "__main__":
    eventlet.monkey_patch()

    x = Thread(target=game_loop, args=())
    x.start()

    print(f"Listening on http://{ip_address}:{port}")
    socketio.run(app, host=ip_address, port=port)
