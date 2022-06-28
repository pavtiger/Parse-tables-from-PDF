# Parse tables from PDF

## Installation
```
# sudo apt install tesseract-ocr-rus
# sudo apt install tesseract-ocr

# sudo pip3 install pytesseract
# sudo pip3 install tqdm
```

## Running
From local PDF file
```
python3 main.py --input example/rencap2021.pdf --limit 10
```

And from remote PDF file
```
python3 main.py --remote https://www.renbroker.ru/storage/uploads/2022/02/24/6217a2faacba6-_2021_1.pdf --limit 10
```

All data will output to `output/` directory. You can find example results in `example/`.

You can also lower the render quality to reduce RAM usage
```
python3 main.py --input example/rencap2021.pdf --limit 10 --quality 100
```

All availible flags:
* _input_ - Path to input pdf file to convert
* _remote_ - Link to a remote location from where to obtain PDF file
* _limit_ - Process only first N pages. (-1 if all)
* _quality_ - PDF page render quality (default 200). Lower to reduce RAM usage. For example, 300 requires 8gb of RAM
