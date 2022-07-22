# Parse tables from PDF

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/c4359133095e40e89611e46dd48beed3)](https://app.codacy.com/gh/pavtiger/Parse-tables-from-PDF?utm_source=github.com&utm_medium=referral&utm_content=pavtiger/Parse-tables-from-PDF&utm_campaign=Badge_Grade_Settings)

This tool was created to automize the process of pulling tables from PDF documents. It goes through all the pages, 
recognises where tables are and then proceeds to transfer them to csv. Using pytesseract it parses text from each cell and determines its position in the table.

You can use this tool by either directly running the python script along with some flags or by running a Web server that will host a web page for uploading files to procees them on server and return the csv files. Whilst displaying the current progress.

Here's the front page
![image](https://user-images.githubusercontent.com/36619129/176673780-6ea4bd77-7f36-42f2-bfba-b199e533f29f.png)

## Installation
Linux using `apt`
```shell
# Required
sudo apt install tesseract-ocr tesseract-ocr-rus
sudo pip install pytesseract opencv-python tqdm progressbar

# Optional for webserver
sudo pip install flask flask-socketio eventlet
```

Windows
* Download tesseract exe from https://github.com/UB-Mannheim/tesseract/wiki.
* Install this exe in C:\Program Files (x86)\Tesseract-OCR
* Open virtual machine command prompt in windows or anaconda prompt.
* Run `pip install pytesseract`

## Running

### Running locally
From PDF file
```shell
python3 recognise_cli.py --input example/rencap2021.pdf --limit 10
```

And from remote PDF file
```shell
python3 recognise_cli.py --remote https://www.renbroker.ru/storage/uploads/2022/02/24/6217a2faacba6-_2021_1.pdf --limit 10
```

All data will output to `output/` directory. You can find example results in `example/`.

You can also change the render quality (>= 200)
```shell
python3 recognise_cli.py --input example/rencap2021.pdf --limit 10 --quality 300
```

### Running web server
```shell
python3 recognise_ws.py
```

All available flags:
* _input_ - Path to input pdf file to convert
* _remote_ - Link to a remote location from where to obtain PDF file
* _limit_ - Process only first N pages. (-1 if all)
* _quality_ - PDF page render quality (default 200). Increasing will consume more RAM, but going under 200 is **highly unadvised**. This will cause recongision **errors**. For reference, 300 requires 8gb of RAM
