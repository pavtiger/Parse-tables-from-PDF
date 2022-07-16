import argparse
from glob import glob
import os
import urllib.request
from dataclasses import dataclass
import time
import progressbar
import sys

import cv2
import numpy as np
from pdf2image import convert_from_path

from parse_table import convert_to_csv


# Important notice: This script assumes that there is a maximum of 1 table in a page (from research is seems to be true)


pbar = None

ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", required=False, help="Path to input pdf file to convert", default="")
ap.add_argument("-r", "--remote", required=False, help="Link to a remote location from where to obtain PDF file",
                default="")
ap.add_argument("-l", "--limit", required=False, help="Process only first N pages. (-1 if all)", default=-1)
ap.add_argument("-q", "--quality", required=False,
                help="PDF page render quality (default 200). Lower to reduce RAM usage",
                default=200)  # For instance, 300 requires ~8gb RAM

args = vars(ap.parse_args())


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class CaptureParams:
    start_time: int = None
    socketio: int = None
    sid: int = None
    console_prefix: str = None


def clear_directory(path):
    files = glob(path)
    for f in files:
        os.remove(f)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def emit_console(start_time, message, sid, socketio):
    current_time = int(time.time() * 1000)
    socketio.emit('progress', {
        'time': current_time - start_time,
        'stdout': message
    }, room=sid)


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


def process(prefix_path, start_time, pdf_file, quality, limit, capture_stdout, sid=None, socketio=None, mystdout=None):
    # Create directories if non-existent
    for path in ['', 'csv', 'detects', 'pages', 'cropped', 'debug']:
        os.makedirs(os.path.join(prefix_path, 'output', path), exist_ok=True)

    # Clear output directory
    for path in ['csv', 'detects', 'pages', 'cropped', 'debug']:
        clear_directory(os.path.join(prefix_path, 'output', path, '*'))

    pages = convert_from_path(pdf_file, quality)

    if limit == -1:
        limit = len(pages)

    console_prefix = ""
    flag = False
    for page_index, page in enumerate(pages[:limit]):
        print(f'Processing page number {page_index + 1}')
        image_path = f'{prefix_path}output/pages/page_{page_index}.jpg'
        page.save(image_path, 'PNG')  # Save page as an image

        detected_cont = detect_table(image_path, page_index, prefix_path)

        if detected_cont != Rect(0, 0, 0, 0):
            image = cv2.imread(image_path)
            cropped = image[detected_cont.y:detected_cont.y + detected_cont.h,
                      detected_cont.x:detected_cont.x + detected_cont.w]

            cropped_filename = f"{prefix_path}output/cropped/cropped_table_{page_index + 1}.jpg"
            cv2.imwrite(cropped_filename, cropped)

            if capture_stdout:
                flag = True
                console_prefix = console_prefix + mystdout.getvalue()
                mystdout = convert_to_csv(cropped_filename,
                                          f"{prefix_path}output/csv/export_table_page_{page_index + 1}.csv", True,
                                          CaptureParams(start_time, socketio, sid, console_prefix))
            else:
                convert_to_csv(cropped_filename, f"output/csv/export_table_page_{page_index}.csv", False)

            print('CSV file saved\n')

        else:
            print('No tables on this page\n')

        if capture_stdout and flag:
            emit_console(start_time, console_prefix + mystdout.getvalue(), sid, socketio)


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


if __name__ == '__main__':
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

    start_time = int(time.time() * 1000)  # Current time in milliseconds
    process('', start_time, pdf_file, quality, int(args["limit"]), False)
