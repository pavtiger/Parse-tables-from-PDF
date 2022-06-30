import base64
from threading import Thread
import time
import os
import subprocess
from glob import glob
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile
import threading
import sys
import asyncio
import cv2
from io import StringIO
from multiprocessing import Process
import urllib.request

from flask_socketio import SocketIO, emit
from pdf2image import convert_from_path
import eventlet
from flask import Flask, send_from_directory, send_file, render_template, Response, request, g

from ip import ip_address, port
from main import detect_table, Rect
from parse_table import convert_to_csv


# Init app
# async_mode = None
app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)


def clear_directory(path):
    files = glob(path)
    for f in files:
        os.remove(f)


def process_by_link(link, quality, limit, sid):
    log = "Processing started\n\n"
    prefix_path = 'static/'

    start_time = int(time.time() * 1000)  # Current time in milliseconds
    socketio.emit('progress', {
        'time': 0,
        'stdout': log
    }, room=sid)

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
        print(f'Processing page number {page_index}')
        log += f'Finished processing page number {page_index}\n\n'

        image_path = f'{prefix_path}output/pages/page_{page_index}.jpg'
        page.save(image_path, 'PNG')  # Save page as an image

        detected_cont = detect_table(image_path, page_index)

        if detected_cont != Rect(0, 0, 0, 0):
            image = cv2.imread(image_path)
            cropped = image[detected_cont.y:detected_cont.y + detected_cont.h,
                      detected_cont.x:detected_cont.x + detected_cont.w]
            cropped_filename = f"{prefix_path}output/cropped/cropped_table_{page_index}.jpg"
            cv2.imwrite(cropped_filename, cropped)

            # Convert to csv
            convert_to_csv(cropped_filename, f"{prefix_path}output/csv/export_table_page_{page_index}.csv")
        else:
            print('No tables on this page')
            log += 'No tables on this page\n'

        current_time = int(time.time() * 1000)
        socketio.emit('progress', {
            'time': current_time - start_time,
            'stdout': log
        }, room=sid)


    # Send download paths
    target_directory = f'{prefix_path}output/csv'
    paths = []
    for file in glob(os.path.join(target_directory, '*.csv')):
        paths.append(file)

    for i, path in enumerate(paths):
        paths[i] = path.replace(prefix_path, '')

    print(paths)

    socketio.emit('download', paths, room=sid)


# Return main page
@app.route('/')
def root():
    return render_template('main.html')


@socketio.on('send')
def get_data(message):
    print(message)
    process_by_link(message['link'], 100, 10, request.sid)


# def feedback(sid):
#     start_time = int(time.time() * 1000)  # Current time in milliseconds
#
#     # old_stdout = sys.stdout
#     # new_stdout = StringIO()
#     # sys.stdout = new_stdout
#
#     with app.test_request_context():
#         # while thr.is_alive():
#         while True:
#             print('feedback', datetime.now().strftime("%H:%M:%S %p"))
#
#             # new_stdout.getvalue()
#
#             current_time = int(time.time() * 1000)
#             socketio.emit('progress', {
#                 'time': current_time - start_time,
#                 'stdout': log
#             }, room=sid)
#             time.sleep(1)
#
#         # Send download paths
#         target_directory = 'output/csv'
#         paths = []
#         for file in glob(os.path.join(target_directory, '*.csv')):
#             paths.append(file)
#
#         socketio.emit('download', paths, room=sid)
#
#     # sys.stdout = old_stdout


# Get files from server (e.g libs)
@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


# We start a parallel thread for game logics. This loop is constantly running
def game_loop(name):
    while True:
        # Process game logic here if you need to

        time.sleep(0.01)


if __name__ == "__main__":
    # This code and game_loop() are needed if you want to do wome tasks in background of the app (e.g. collision check)
    eventlet.monkey_patch()

    print(f"Listening on http://{ip_address}:{port}")
    socketio.run(app, host=ip_address, port=port)
