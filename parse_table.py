import cv2
import io
import os
import numpy as np
import pandas as pd
from tqdm import tqdm

try:
    import urllib.request as urllib
except ModuleNotFoundError:
    import urllib

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract

from config import debug_mode


BAR_LENGTH = 50


class Cell:
    def __init__(self, x, y, w, h, text, conf):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.conf = conf

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

    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def extract_value(x):
    return x[0].text


async def convert_to_csv(filename, page_index, output_path, prefix_path, user_connected, capture_stdout, sio=None, sid=None):
    # Create page render debug directory
    debug_dir = f"{prefix_path}output/debug/cells_{str(page_index).zfill(4)}"
    os.makedirs(debug_dir, exist_ok=True)

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
    for i, _ in enumerate(thick_table):
        for j, _ in enumerate(thick_table[i]):
            if thick_table[i][j] == 255:
                raw_image[i][j] = 255

    last_y = -1
    row_index = 0
    table_array, row = [], []

    # Iterate over all contours and recognise text inside
    if capture_stdout:
        iterate_obj = enumerate(cont)
    else:
        iterate_obj = enumerate(tqdm(cont))

    for ind, cnt in iterate_obj:
        x, y, w, h = cv2.boundingRect(cnt)
        if (w * h) > (width * height * 0.75):
            continue  # Skip if the contour is the whole table itself

        cropped_image = raw_image[y:y + h, x: x + w]
        cv2.imwrite(os.path.join(debug_dir, f"box_{str(ind).zfill(4)}.jpg"), cropped_image)

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

        # text = text[text.conf != -1]
        # lines = text.groupby('block_num')['text'].apply(list)
        # conf = text.groupby(['block_num'])['conf'].mean()
        row.append(Cell(x, y, w, h, text, 0))

        if debug_mode:  # Show a window with the image we are trying to recognise
            cv2.namedWindow("output", cv2.WINDOW_NORMAL)  # Create window with freedom of dimensions
            cv2.imshow("output", cropped_image)  # Show image
            cv2.waitKey(0)

        if capture_stdout:
            await sio.emit('progress', {
                'stdout': int(ind / len(cont) * 100),
                'index': page_index
            }, room=sid)

        if user_connected is not None and not user_connected[sid]:
            print("User disconnected or pressed stop")
            break

    # sio.emit('send_table', {
    #     'table': table_array,
    # }, room=sid)

    for i, _ in enumerate(table_array):
        table_array[i].sort()  # Sort cells in every row to get the correct order (initially it's not the correct)

    for i in range(len(table_array)):
        for j in range(len(table_array[i])):
            table_array[i][j] = table_array[i][j].text

    table_array.reverse()

    df = pd.DataFrame(table_array)
    df.to_csv(output_path)
