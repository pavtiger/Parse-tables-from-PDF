# Parse tables from PDF
This tool was created to automize the process of pulling tables from PDF documents. It goes through all the pages, 
recognises where tables are and then proceeds to transfer them to csv. Using pytesseract it parses text from each cell and determines its position in the table.

## Installation
Linux
```
sudo apt install tesseract-ocr tesseract-ocr-rus
sudo pip3 install pytesseract opencv-python tqdm
```

Windows
* Download tesseract exe from https://github.com/UB-Mannheim/tesseract/wiki.
* Install this exe in C:\Program Files (x86)\Tesseract-OCR
* Open virtual machine command prompt in windows or anaconda prompt.
* Run `pip install pytesseract`


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

You can also change the render quality (>= 200)
```
python3 main.py --input example/rencap2021.pdf --limit 10 --quality 300
```

All availible flags:
* _input_ - Path to input pdf file to convert
* _remote_ - Link to a remote location from where to obtain PDF file
* _limit_ - Process only first N pages. (-1 if all)
* _quality_ - PDF page render quality (default 200). Increasing will consume more RAM, but going under 200 is **highly unadvised**. This will cause recongision **errors**. For reference, 300 requires 8gb of RAM
