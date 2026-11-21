# Table to CSV

Turns a table you lasso into a CSV file you can open in Numbers or Excel.

- **How to use it:** lasso a table on screen (a spreadsheet, a web page, a screenshot). When Lasso sees
  rows and columns, **Table to CSV** appears in the toolbar. Click it: the file is saved in
  `~/LassoWorkspace/table-to-csv/` and shown in Finder.
- **Sends:** nothing. It runs `scripts/to-csv.py` on your Mac, in Lasso's sandbox, with no internet.
- **Needs:** Lasso 0.24.0 or later, and Python 3 (`/usr/bin/python3`).
