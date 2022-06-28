# sudo apt install tesseract-ocr-rus
# sudo apt install pytesseract
# sudo apt install tesseract-ocr
# sudo pip3 install tqdm

import cv2
import io
import numpy as np
import pandas as pd
from dataclasses import dataclass
from functools import cmp_to_key
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


class cell:
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


def convert_to_csv(filename, output_path):
    im = imgread(filename)
    width, height, _ = im.shape

    im = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    threshold = cv2.adaptiveThreshold(~im, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2)

    # Copy threshold, then for horizontal and vertical lines' detection.
    horizontal = threshold.copy()
    vertical = threshold.copy()
    scale = 15  # Play with this variable in order to increase/decrease the amount of lines to be detected

    # Specify size on horizontal axis
    horizontalsize = horizontal.shape[1] // scale
    horizontalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontalsize, 1))
    horizontal = cv2.erode(horizontal, horizontalStructure, (-1, -1))
    horizontal = cv2.dilate(horizontal, horizontalStructure, (-1, -1))

    # Vertical lines
    verticalsize = vertical.shape[0] // scale
    verticalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, verticalsize))
    vertical = cv2.erode(vertical, verticalStructure, (-1, -1))
    vertical = cv2.dilate(vertical, verticalStructure, (-1, -1))

    # All table lines
    table = horizontal + vertical

    cont, _ = cv2.findContours(table, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    thick_table = cv2.dilate(table, kernel, iterations=1)

    raw_image = im
    for i in range(len(thick_table)):
        for j in range(len(thick_table[i])):
            if thick_table[i][j] == 255:
                raw_image[i][j] = 255

    last_y = -1
    row_index = 0
    table_array, row = [], []

    for cnt in tqdm(cont):
        x, y, w, h = cv2.boundingRect(cnt)
        if (w * h) > (width * height * 0.75):
            continue

        cropped_image = raw_image[y:y + h, x: x + w]

        # Parse text
        text = pytesseract.image_to_string(cropped_image, lang="rus", config="--psm 4")
        text = text.strip('\u000C')  # Remove unwanted characters
        text = text.replace('\n', '')

        # print(text, '\n', number)
        if text == '':
            text = pytesseract.image_to_string(cropped_image, lang='eng',
                                                 config='--psm 10 --oem 3 -c tessedit_char_whitelist=0123456789')
            text = text.strip('\u000C')  # Remove unwanted characters
            text = text.replace('\n', '')

        if (y + h / 2) < last_y:
            row_index += 1
            table_array.append(row)
            row = []

        last_y = y
        row.append(cell(x, y, w, h, text))

        # cv2.namedWindow("output", cv2.WINDOW_NORMAL)  # Create window with freedom of dimensions
        # cv2.imshow("output", cropped_image)  # Show image
        # cv2.waitKey(0)

    for i in range(len(table_array)):
        table_array[i].sort()

    for i in range(len(table_array)):
        for j in range(len(table_array[i])):
            table_array[i][j] = table_array[i][j].text

    table_array.reverse()

    df = pd.DataFrame(table_array)
    df.to_csv(output_path)


if __name__ == '__main__':
    filename = "pdf/cropped/cropped_table_8.jpg"

    convert_to_csv(filename, 'dataframe.csv')
