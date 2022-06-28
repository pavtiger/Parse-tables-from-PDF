import cv2
import numpy as np
import argparse
from dataclasses import dataclass
from pdf2image import convert_from_path
import urllib.request

from parse_table import convert_to_csv

# Important notice: This script assumes that there is a maximum of 1 table in a page (from research is seems to be true)


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


def detect_table(filename, page):
    im1 = cv2.imread(filename, 0)
    im = cv2.imread(filename)

    shape = im.shape

    ret, thresh_value = cv2.threshold(im1, 180, 255, cv2.THRESH_BINARY_INV)

    kernel = np.ones((5, 5), np.uint8)
    dilated_value = cv2.dilate(thresh_value, kernel, iterations=1)

    contours, hierarchy = cv2.findContours(dilated_value, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    max_space = 0
    table_coords = Rect(0, 0, 0, 0)
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Bounding the images
        if (w * h) > (shape[0] * shape[1] / 10) and (w * h) > max_space:
            max_space = (w * h)
            table_coords = Rect(x, y, w, h)

    cv2.rectangle(im, (table_coords.x, table_coords.y),
                  (table_coords.x + table_coords.w, table_coords.y + table_coords.h), (0, 0, 255), 5)
    cv2.imwrite(f'output/detects/detect_table_{page}.jpg', im)
    return table_coords


if __name__ == '__main__':
    pdf_file = ""
    if args["input"] == "":
        # Remote file
        pdf_file = "output/remote_document.pdf"
        urllib.request.urlretrieve(args["remote"], "output/remote_document.pdf")
    else:
        # Local file
        pdf_file = args["input"]

    pages = convert_from_path(pdf_file, args["quality"])

    if args["limit"] == -1:
        args["limit"] = len(pages)

    for page_index, page in enumerate(pages[:int(args["limit"])]):
        print(f'Processing page number {page_index}')
        image_path = f'output/pages/page_{page_index}.jpg'
        page.save(image_path, 'PNG')  # Save page as an image

        detected_cont = detect_table(image_path, page_index)

        if detected_cont != Rect(0, 0, 0, 0):
            image = cv2.imread(image_path)
            cropped = image[detected_cont.y:detected_cont.y + detected_cont.h, detected_cont.x:detected_cont.x + detected_cont.w]
            cropped_filename = f"output/cropped/cropped_table_{page_index}.jpg"
            cv2.imwrite(cropped_filename, cropped)

            # Convert to csv
            convert_to_csv(cropped_filename, f"output/csv/export_table_{page_index}.csv")
        else:
            print('No tables on this page')
