import cv2
import io
import numpy as np
import pandas as pd
from tqdm import tqdm
import sys
import time
from io import StringIO

try:
    import urllib.request as urllib
except ModuleNotFoundError:
    import urllib

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract


DEBUG_MODE = False
BAR_LENGTH = 50




class Cell:
    def __init__(self, x, y, w, h, text):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text

    def __le___(self, other):
        return (self.x + self.w / 2) <= (other.x + other.w / 2)

    def __lt__(self, other):
        return (self.x + self.w / 2) < (other.x + other.w / 2)


# Read an image by filepath
def imgread(im):
    try:
        image = Image.open(io.BytesIO(urllib.urlopen(im).read()))
    except ValueError:
        try:
            image = Image.open(im)
        except FileExistsError:
            return None
    try:
        image = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    except:
        return None
    return image


def extract_value(x):
    return x[0].text


def emit_console(start_time, message, sid, socketio):
    current_time = int(time.time() * 1000)
    socketio.emit('progress', {
        'time': current_time - start_time,
        'stdout': message
    }, room=sid)


def convert_to_csv(filename, output_path, capture_stdout, capture_params=None):
    start_time = int(time.time() * 1000)

    last_post_time = start_time

    im = imgread(filename)
    width, height, _ = im.shape

    im = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    threshold = cv2.adaptiveThreshold(~im, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2)

    # Copy threshold, then for horizontal and vertical lines' detection.
    horizontal = threshold.copy()
    vertical = threshold.copy()
    scale = 15  # Play with this variable in order to increase/decrease the amount of lines to be detected

    # Specify size on horizontal axis
    horizontal_size = horizontal.shape[1] // scale
    horizontal_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_size, 1))
    horizontal = cv2.erode(horizontal, horizontal_structure, (-1, -1))
    horizontal = cv2.dilate(horizontal, horizontal_structure, (-1, -1))

    # Vertical lines
    vertical_size = vertical.shape[0] // scale
    vertical_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_size))
    vertical = cv2.erode(vertical, vertical_structure, (-1, -1))
    vertical = cv2.dilate(vertical, vertical_structure, (-1, -1))

    # All table lines
    table = horizontal + vertical

    cont, _ = cv2.findContours(table, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Remove table lines (vertical and horizontal) from the image
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thick_table = cv2.dilate(table, kernel, iterations=1)  # Thicken mask

    raw_image = im
    for i in range(len(thick_table)):
        for j in range(len(thick_table[i])):
            if thick_table[i][j] == 255:
                raw_image[i][j] = 255

    last_y = -1
    row_index = 0
    table_array, row = [], []

    if capture_stdout:
        sys.stdout = mystdout = StringIO()

    # Iterate over all contours and recognise text inside
    for ind, cnt in [enumerate(tqdm(cont)), enumerate(cont)][capture_stdout]:
        x, y, w, h = cv2.boundingRect(cnt)
        if (w * h) > (width * height * 0.75):
            continue  # Continue if the contour is the whole table

        cropped_image = raw_image[y:y + h, x: x + w]

        # Parse text
        text = pytesseract.image_to_string(cropped_image, lang="rus", config="--psm 4")
        text = text.strip('\u000C')  # Remove unwanted characters
        text = text.replace('\n', '')

        if text == '':  # If text is not recognised try searching for digits specifically
            text = pytesseract.image_to_string(cropped_image, lang='eng',
                                               config='--psm 10 --oem 3 -c tessedit_char_whitelist=0123456789')
            # Remove unwanted characters
            text = text.strip('\u000C')
            text = text.replace('\n', '')

        if (y + h / 2) < last_y:  # If the new cell is on a different row than the predecessor
            row_index += 1
            table_array.append(row)
            row = []

        last_y = y
        row.append(Cell(x, y, w, h, text))

        if DEBUG_MODE:  # Show a window with the image we are trying to recognise
            cv2.namedWindow("output", cv2.WINDOW_NORMAL)  # Create window with freedom of dimensions
            cv2.imshow("output", cropped_image)  # Show image
            cv2.waitKey(0)

        current_time = int(time.time() * 1000)
        if capture_stdout:
            progress_bar = '⬛' * int(BAR_LENGTH * (ind / len(cont)))
            print(progress_bar.ljust(BAR_LENGTH, '⬜'))

            if current_time - last_post_time > 1000:
                emit_console(capture_params.start_time, capture_params.console_prefix + mystdout.getvalue(), capture_params.sid, capture_params.socketio)

                last_post_time = current_time

            if ind != len(cnt) - 1: sys.stdout = mystdout = StringIO()

    for i in range(len(table_array)):
        table_array[i].sort()  # Sort cells in every row to get the correct order (initially it's not the correct)

    for i in range(len(table_array)):
        for j in range(len(table_array[i])):
            table_array[i][j] = table_array[i][j].text

    table_array.reverse()

    df = pd.DataFrame(table_array)
    df.to_csv(output_path)

    if capture_stdout:
        return mystdout


if __name__ == '__main__':
    filename = "example/cropped/cropped_table_8.jpg"
    convert_to_csv(filename, 'dataframe.csv', False)
