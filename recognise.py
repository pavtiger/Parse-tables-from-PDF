import time
import os
from glob import glob
import urllib.request
import argparse
from dataclasses import dataclass
from threading import Thread
import progressbar

import cv2
import numpy as np
from pdf2image import convert_from_path
import fitz

from aiohttp import web
import socketio
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
MAX_BUFFER_SIZE = 50 * 1000 * 1000  # 50 MB

# Create a Socket.IO server
sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins=['http://pdf.pavtiger.com'],
                           maxHttpBufferSize=MAX_BUFFER_SIZE, async_handlers=True)
app = web.Application()
sio.attach(app)

# Static files server
async def index(request):
    with open('static/index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

app.router.add_static('/static', 'static')
app.router.add_get('/', index)


process_index = 0

user_connected = dict()
last_seen = dict()


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

    except urllib.error.HTTPError:
        print('error')
        return False


async def emit_message(message, sid, capture_stdout=True, index=None):
    if capture_stdout:
        if index is None:
            await sio.emit('init_info', {
                'stdout': message
            }, room=sid)
        else:
            await sio.emit('progress', {
                'stdout': message,
                'index': index
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


async def process(prefix_path, pdf_file, quality, limit, capture_stdout, sid=None, sio=None, user_connected=None):
    # Create directories if non-existent
    for path in ['', 'csv', 'detects', 'pages', 'cropped', 'debug']:
        os.makedirs(os.path.join(prefix_path, 'output', path), exist_ok=True)

    # Clear output directory
    for path in ['csv', 'detects', 'pages', 'cropped', 'debug']:
        clear_directory(os.path.join(prefix_path, 'output', path, '*'))

    document = fitz.open(pdf_file)

    if limit == "":
        limit = len(document)
    else:
        limit = min(int(limit), len(document))


    await sio.emit("init", {"page_cnt": limit}, room=sid)

    for page_index in range(limit):
        page = document.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(quality / 72, quality / 72))  # 72 is default scale

        image_path = f'{prefix_path}output/pages/page_{page_index}.jpg'
        pix.save(image_path)

        detected_cont = detect_table(image_path, page_index, prefix_path)

        if detected_cont != Rect(0, 0, 0, 0):
            image = cv2.imread(image_path)
            cropped = image[detected_cont.y:detected_cont.y + detected_cont.h,
                      detected_cont.x:detected_cont.x + detected_cont.w]

            cropped_filename = f"{prefix_path}output/cropped/cropped_table_{page_index + 1}.jpg"
            cv2.imwrite(cropped_filename, cropped)

            # Send current page to the user
            with open(cropped_filename, 'rb') as f:
                image_data = f.read()

            await sio.emit("add_page_image", {"page_index": page_index, "image_data": image_data, "type": ".image_div_table"}, room=sid)

            await convert_to_csv(cropped_filename, page_index, f"{prefix_path}output/csv/export_table_page_{page_index + 1}.csv",
                           user_connected, capture_stdout, sio, sid)

            if user_connected is not None and user_connected[sid]:
                await sio.emit('processing_finished', {'index': page_index}, room=sid)

        else:
            await sio.emit('nothing_found_on_page', {'index': page_index}, room=sid)

        if user_connected is not None and not user_connected[sid]:
            break


async def process_by_link(link, quality, limit, sid, download_on_finish):
    prefix_path = 'static/'
    await emit_message('Downloading document and rendering pages', sid)

    pdf_file = os.path.join(prefix_path, f"output/processed_documents/remote_document_{process_index}.pdf")
    if check_if_url_exists(link):
        urllib.request.urlretrieve(link, pdf_file)
    else:
        await emit_message('There is a problem loading file from this link. Check if it is correct\n', sid)
        return False

    # Main spreadsheet processing
    await emit_message('Processing started', sid)
    await process(prefix_path, pdf_file, quality, limit, True, sid, sio, user_connected)

    if download_on_finish:
        # Send download paths
        target_directory = f'{prefix_path}output/csv'
        paths = []
        for file in glob(os.path.join(target_directory, '*.csv')):
            paths.append(file)

        await emit_message("Processing finished, starting download", sid)
        await sio.emit('work_finish', {"download": True, "paths": paths}, room=sid)
    else:
        await sio.emit('work_finish', {"download": False, "paths": []}, room=sid)

    return True


@sio.event
async def connect(sid, environ):
    user_connected[sid] = True
    last_seen[sid] = int(time.time() * 1000)


@sio.event
async def connect_error(sid, data):
    print("The connection failed!")


@sio.event
async def disconnect(sid):
    user_connected[sid] = False
    await sio.disconnect(sid)


@sio.event
async def stop(sid):
    user_connected[sid] = False


@sio.on('pingserver')
async def pingserver(sid):
    if sid in last_seen.keys():
        last_seen[sid] = int(time.time() * 1000)


@sio.on("download_task")
async def download_task(sid, index):
    index = str(int(index) + 1)
    paths = [os.path.join('static/output/csv/', f'export_table_page_{index}.csv')]

    await sio.emit('work_finish', {"download": True, "paths": paths}, room=sid)


@sio.on("send_page_preview")
async def send_page_preview(sid, index):
    path = os.path.join('static/output/pages/', f'page_{index}.jpg')

    with open(path, 'rb') as f:
        image_data = f.read()

    await sio.emit('add_page_image', {"image_data": image_data, "page_index": index, "type": ".image_div"}, room=sid)


@sio.on('send')
async def get_data(sid, message):
    if not message['link'].lower().startswith('http'):
        return

    user_connected[sid] = True
    print(f'Started processing of {sid, message}')

    sio.start_background_task(process_by_link, message['link'], server_quality, message['limit'], sid, message['download_results'])


async def show_progress(block_num, block_size, total_size):
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


async def send_ping():
    print("start")
    while True:
        for user in user_connected.keys():
            if user_connected[user]:
                # print(f"ping {user}")
                if last_seen[user] is not None and int(time.time() * 1000) - last_seen[user] >= 20000:
                    user_connected[user] = False
                    print(f"User {user} deleted due to inactivity")
                    break

            await sio.emit('pingclient', user, room=user)
        await sio.sleep(1)


async def init_app():
    sio.start_background_task(send_ping)
    return app


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
        os.makedirs('static/output/processed_documents', exist_ok=True)
        clear_directory('static/output/processed_documents/remote_document_*')

        print(f"Listening on http://{ip_address}:{port}")
        web.run_app(init_app(), host=ip_address, port=port)

    else:
        print('You need to specify call type: -s/--server or -c/--client')
