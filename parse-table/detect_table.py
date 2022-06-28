import cv2
import numpy as np
import matplotlib.pyplot as plt


file = f'images/aton2021_2.png'

im1 = cv2.imread(file, 0)
im = cv2.imread(file)

shape = im.shape

ret, thresh_value = cv2.threshold(im1, 180, 255, cv2.THRESH_BINARY_INV)

kernel = np.ones((5, 5), np.uint8)
dilated_value = cv2.dilate(thresh_value, kernel, iterations=1)

contours, hierarchy = cv2.findContours(dilated_value, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
print(hierarchy)

cordinates = []
for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    cordinates.append((x, y, w, h))
    # bounding the images
    if (w * h) > (shape[0] * shape[1] / 10):
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 0, 255), 1)

plt.imshow(im)
cv2.imwrite('detect_table.jpg', im)