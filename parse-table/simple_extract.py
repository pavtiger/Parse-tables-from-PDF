# Install:
# camelot-py
# opencv-python
# ghostscript

import camelot

# PDF file to extract tables from
filename = "sber2021.pdf"

# extract all the tables in the PDF file
tables = camelot.read_pdf(f"pdf/{filename}")

# number of tables extracted
print("Total tables extracted:", tables.n)

# print the first table as Pandas DataFrame
if tables.n != 0:
    print(tables[0].df)

