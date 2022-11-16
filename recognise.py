import time
import os
from glob import glob
import urllib.request
import argparse
import sys
from io import StringIO
from dataclasses import dataclass
from threading import Thread
from collections import deque
import progressbar

import cv2
import numpy as np
from pdf2image import convert_from_path

from flask_socketio import SocketIO
import eventlet
from flask import Flask, send_from_directory, render_template, request

from config import ip_address, port, server_quality
from parse_table import convert_to_csv

# Important notice: This script assumes that there is a maximum of 1 table in a page (from research is seems to be true)
ap = argparse.ArgumentParser()
ap.add_argument("-s", "--server", action='store_true')
ap.add_argument("-c", "--client", action='store_true')

ap.add_argument("-i", "--input", required=False, help="Path to input pdf file to convert", default="")
ap.add_argument("-r", "--remote", required=False, help="Link to a remote location from where to obtain PDF file",
                default="")
ap.add_argument("-l", "--limit", required=False, help="Process only first N pages. (-1 if all). All by default",
                default=-1)
ap.add_argument("-q", "--quality", required=False,
                help="PDF page render quality (default 200). Lower to reduce RAM usage",
                default=200)  # For instance, 300 requires ~8gb RAM

args = vars(ap.parse_args())

# Init app
pbar = None
app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
process_queue = deque()
process_index = -1

user_connected = dict()

BAR_LENGTH = 50


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


def check_if_url_exists(url):
    try:
        u = urllib.request.urlopen(url)
        u.close()
        return True
    except:
        return False


def emit_message(message, sid, capture_stdout=True):
    if capture_stdout:
        socketio.emit('progress', {
            'stdout': message + '\n'
        }, room=sid)
    else:
        print(message)


def clear_directory(path):
    files = glob(path)
    for f in files:
        os.remove(f)


def detect_table(filename, page, prefix_path):
    im1 = cv2.imread(filename, 0)
    im = cv2.imread(filename)

    shape = im.shape

    _, thresh_value = cv2.threshold(im1, 200, 255, cv2.THRESH_BINARY_INV)

    kernel = np.ones((5, 5), np.uint8)
    dilated_value = cv2.dilate(thresh_value, kernel, iterations=1)
    cv2.imwrite(f'{prefix_path}output/debug/dilated_value_{page}.jpg', dilated_value)

    contours, _ = cv2.findContours(dilated_value, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    max_space = 0
    table_coords = Rect(0, 0, 0, 0)
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Bounding the images
        if (w * h) > (shape[0] * shape[1] / 15) and (w * h) > max_space:
            max_space = (w * h)
            table_coords = Rect(x, y, w, h)

    cv2.rectangle(im, (table_coords.x, table_coords.y),
                  (table_coords.x + table_coords.w, table_coords.y + table_coords.h), (0, 0, 255), 5)
    cv2.imwrite(f'{prefix_path}output/detects/detect_table_{page}.jpg', im)
    return table_coords


def process(prefix_path, pdf_file, quality, limit, capture_stdout, sid=None, socketio=None, user_connected=None):
    # Create directories if non-existent
    for path in ['', 'csv', 'detects', 'pages', 'cropped', 'debug']:
        os.makedirs(os.path.join(prefix_path, 'output', path), exist_ok=True)

    # Clear output directory
    for path in ['csv', 'detects', 'pages', 'cropped', 'debug']:
        clear_directory(os.path.join(prefix_path, 'output', path, '*'))

    pages = convert_from_path(pdf_file, quality)

    if limit == -1:
        limit = len(pages)

    for page_index, page in enumerate(pages[:limit]):
        emit_message(f'Processing page number {page_index + 1}', sid, capture_stdout)
        image_path = f'{prefix_path}output/pages/page_{page_index}.jpg'
        page.save(image_path, 'PNG')  # Save page as an image

        detected_cont = detect_table(image_path, page_index, prefix_path)

        if detected_cont != Rect(0, 0, 0, 0):
            image = cv2.imread(image_path)
            cropped = image[detected_cont.y:detected_cont.y + detected_cont.h,
                      detected_cont.x:detected_cont.x + detected_cont.w]

            cropped_filename = f"{prefix_path}output/cropped/cropped_table_{page_index + 1}.jpg"
            cv2.imwrite(cropped_filename, cropped)

            convert_to_csv(cropped_filename, f"{prefix_path}output/csv/export_table_page_{page_index + 1}.csv",
                           capture_stdout, socketio, sid)

            emit_message('CSV file saved\n', sid, capture_stdout)

        else:
            emit_message('No tables on this page\n', sid, capture_stdout)

        if user_connected is not None and not user_connected[sid]:
            break


def process_by_link(link, quality, limit, sid):
    console_prefix, prefix_path = '', 'static/'
    emit_message('Downloading document\n', sid)

    pdf_file = f"output/remote_document_{process_index}.pdf"
    if check_if_url_exists(link):
        urllib.request.urlretrieve(link, pdf_file)
        emit_message('Processing started\n', sid)

    else:
        emit_message('There is a problem loading file from this link. Check if it is correct\n', sid)
        return False

    # Main spreadsheet processing
    process(prefix_path, pdf_file, quality, int(limit), True, sid, socketio, user_connected)

    # Send download paths
    target_directory = f'{prefix_path}output/csv'
    paths = []
    for file in glob(os.path.join(target_directory, '*.csv')):
        paths.append(file)

    for i, path in enumerate(paths):
        paths[i] = path.replace(prefix_path, '')

    emit_message("Starting download", sid)
    socketio.emit('download', paths, room=sid)
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
                socketio.emit('progress', {'stdout': 'You already have an ongoing request', 'time': 0},
                              room=request.sid)
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


def show_progress(block_num, block_size, total_size):
    global pbar
    if pbar is None:
        pbar = progressbar.ProgressBar(maxval=total_size)
        pbar.start()

    downloaded = block_num * block_size
    if downloaded < total_size:
        pbar.update(downloaded)
    else:
        pbar.finish()
        pbar = None


if __name__ == "__main__":
    if args["client"]:
        if args["remote"] == "" and args["input"] == "":
            print("You need to specify either link to a remote pdf file (--remote https://somewebsite.com) or local "
                  "file (--input filepath/file.pdf)")

        else:
            quality = int(args["quality"])
            if quality < 200:
                print('Quality is set to a number smaller than 200. THis is highly unadvised and '
                      'will cause recognition errors')
                print('Change quality to 200? [Y/n]')

                if input().lower() != 'n':
                    quality = 200

            pdf_file = ""
            if args["input"] == "":
                # Remote file
                pdf_file = "output/remote_document.pdf"
                print("File download started")
                urllib.request.urlretrieve(args["remote"], pdf_file, show_progress)
                print()
            else:
                # Local file
                pdf_file = args["input"]

            print('Processing started\n')
            process('', pdf_file, quality, int(args["limit"]), False)
            print('Task finished')

    elif args['server']:
        eventlet.monkey_patch()
        clear_directory('output/remote_document_*')

        x = Thread(target=process_caller, args=())
        x.start()

        print(f"Listening on http://{ip_address}:{port}")
        socketio.run(app, host=ip_address, port=port)

    else:
        print('You need to specify call type: -s/--server or -c/--client')
