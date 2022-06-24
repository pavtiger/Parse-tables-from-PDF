import cv2
from PIL import Image
import io
import numpy as np

try:
    import urllib.request as urllib
except ModuleNotFoundError:
    import urllib

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract


filename = "images/rencap2021.png"

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
cv2.imshow("horizontal line", horizontal)
cv2.waitKey(0)

# Vertical lines
verticalsize = vertical.shape[0] // scale
verticalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, verticalsize))
vertical = cv2.erode(vertical, verticalStructure, (-1, -1))
vertical = cv2.dilate(vertical, verticalStructure, (-1, -1))

cv2.imshow("horizontal line", vertical)
cv2.waitKey(0)

# Table line
table = horizontal + vertical
cv2.imshow("table", table)
cv2.waitKey(0)

# The joint points between horizontal line and vertical line.
joints = cv2.bitwise_and(horizontal, vertical)
cv2.imshow("joint points", joints)
cv2.waitKey(0)
