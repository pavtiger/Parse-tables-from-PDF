# sudo apt install tesseract-ocr-rus
# sudo apt install pytesseract
# sudo apt install tesseract-ocr

import cv2
from PIL import Image
import io
import numpy as np
import math

try:
    import urllib.request as urllib
except ModuleNotFoundError:
    import urllib

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract

filename = "pdf/cropped/cropped_table_1.jpg"


# read an image by filepath
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

# cv2.imshow("horizontal line", vertical)

# Table line
table = horizontal + vertical
# cv2.imshow("table", table)

# The joint points between horizontal line and vertical line.
joints = cv2.bitwise_and(horizontal, vertical)
# cv2.imshow("joint points", joints)

# image = imgread('images/22.png')

cont, _ = cv2.findContours(table, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
for cnt in cont:
    x, y, w, h = cv2.boundingRect(cnt)
    cv2.rectangle(im, (x, y), (x + w, y + h), (0, 0, 255), 3)
    cropped_image = im[y:y + h, x: x + w]

    # final_extract = image[y:y + h, x:x + w]
    # final_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    # get_border = cv2.copyMakeBorder(final_extract, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=[255, 255])
    # resize = cv2.resize(get_border, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # dil = cv2.dilate(resize, final_kernel, iterations=1)
    # ero = cv2.erode(dil, final_kernel, iterations=2)
    # ocr = pytesseract.image_to_string(ero)
    # if len(ocr) == 0:
    #     ocr = pytesseract.image_to_string(ero, config='--psm 3')


    # Read text
    print(" ------- " * 5)
    text = pytesseract.image_to_string(cropped_image, lang="rus", config="--psm 4")
    print("rus", text)

    # text = pytesseract.image_to_string(cropped_image, config="--psm 4")
    # print(4, text)
    # text = pytesseract.image_to_string(cropped_image, config="--psm 11")
    # print(11, text)
    # text = pytesseract.image_to_string(cropped_image, config="--psm 12")
    # print(12, text)

    cv2.namedWindow("output", cv2.WINDOW_NORMAL)  # Create window with freedom of dimensions
    # imS = cv2.resize(im, (height, width))  # Resize image
    cv2.imshow("output", cropped_image)  # Show image
    cv2.waitKey(0)

    cv2.waitKey(0)
