import time
import os
from glob import glob
import urllib.request
import argparse
from dataclasses import dataclass
from threading import Thread
import progressbar
import shutil

import cv2
import numpy as np
import fitz

import asyncio
from aiohttp import web
import socketio
import eventlet
from flask import Flask, send_from_directory, render_template, request

from config import ip_address, port, server_quality, cors_allowed_origins
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

# urlib request options
user_agent = 'Mozilla/5.0'
headers = {'User-Agent': user_agent,}

# Create a Socket.IO server
sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins=cors_allowed_origins,
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
        test_request = urllib.request.Request(url, None, headers)
        u = urllib.request.urlopen(test_request)
        u.close()
        return True

    except urllib.error.HTTPError:
        print('error')
        return False


async def emit_message(message, sid, capture_stdout=True, index=None):
    if capture_stdout:
        print(f"log: {message}")
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
        if os.path.isfile(f):
            os.remove(f)
        else:
            shutil.rmtree(f)


def order_points(pts):
    # Initialize a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype = "float32")
    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis = 1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    # now, compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis = 1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    # return the ordered coordinates
    return rect


def four_point_transform(image, pts):
    # obtain a consistent order of the points and unpack them
    # individually
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordiates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype = "float32")
    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    # return the warped image
    return warped


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
    table_coords = None
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        rect = cv2.minAreaRect(cnt)

        # Bounding the images
        if (w * h) > (shape[0] * shape[1] / 15) and (w * h) > max_space:
            max_space = (w * h)
            table_coords = rect

    if table_coords is None:
        return None

    # Draw table rectangle on top of the image for debug purposes
    box = cv2.boxPoints(table_coords)
    box_points = []
    for i in range(4):
        box_points.append((int(box[i][0]), int(box[i][1])))

    crop = four_point_transform(im, box)

    cv2.line(im, box_points[0], box_points[1], (0, 255, 0), 3)
    cv2.line(im, box_points[1], box_points[2], (0, 255, 0), 3)
    cv2.line(im, box_points[2], box_points[3], (0, 255, 0), 3)
    cv2.line(im, box_points[3], box_points[0], (0, 255, 0), 3)
    cv2.imwrite(f'{prefix_path}output/detects/detect_table_{page}.jpg', im)

    return crop


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

    if capture_stdout:
        await sio.emit("init", {"page_cnt": limit}, room=sid)


    for page_index in range(limit):
        page = document.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(quality / 72, quality / 72))  # 72 is default scale

        image_path = f'{prefix_path}output/pages/page_{page_index}.jpg'
        pix.save(image_path)

        detected_cropped = detect_table(image_path, page_index, prefix_path)

        if detected_cropped is not None:
            # image = cv2.imread(image_path)
            # cropped = image[detected_cont.y:detected_cont.y + detected_cont.h,
            #           detected_cont.x:detected_cont.x + detected_cont.w]

            cropped_filename = f"{prefix_path}output/cropped/cropped_table_{page_index + 1}.jpg"
            cv2.imwrite(cropped_filename, detected_cropped)

            if capture_stdout:
                # Send current page to the user
                with open(cropped_filename, 'rb') as f:
                    image_data = f.read()

                await sio.emit("add_page_image", {"page_index": page_index, "image_data": image_data, "type": ".image_div_table"}, room=sid)

            await convert_to_csv(cropped_filename, page_index, f"{prefix_path}output/csv/export_table_page_{page_index + 1}.csv",
                       prefix_path, user_connected, capture_stdout, sio, sid)

            if capture_stdout and user_connected is not None and user_connected[sid]:
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
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)

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


async def client_main(args):
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

        if int(args["limit"]) == -1:
            args["limit"] = ""

        print('Processing started\n')
        await process('', pdf_file, quality, args["limit"], False)
        print('Task finished')


if __name__ == "__main__":
    if args["client"]:
        asyncio.run(client_main(args))

    elif args['server']:
        eventlet.monkey_patch()
        os.makedirs('static/output/processed_documents', exist_ok=True)
        clear_directory('static/output/processed_documents/remote_document_*')

        print(f"Listening on http://{ip_address}:{port}")
        web.run_app(init_app(), host=ip_address, port=port)

    else:
        print('You need to specify call type: -s/--server or -c/--client')
