# Car Rental Log — COSC 221 Final Project

**Team:** Team__ (replace with our registered team number)

| Member | Student ID | Main part |
|---|---|---|
| _Name 1_ | _ID_ | `rental.py` – classes and rules |
| _Name 2_ | _ID_ | `storage.py` + data files |
| _Name 3_ | _ID_ | Browse cars + New booking pages |
| _Name 4_ | _ID_ | Bookings + Manage booking pages |
| _Name 5_ | _ID_ | Summary page, `main.py`, testing and docs |

## What it does

A counter app for a small car rental shop. A customer walks in, the staff member
shows them the cars on screen, books one for them, hands over the car after checking
documents, and checks it back in when it's returned.

The app is for **staff only**. It runs on the shop computer (`localhost`), so customers
can't reach it from their own devices.

### Rules we chose
- Prices are in **US dollars**. The rental is **paid in full when booking** (cash, card or transfer).
- **Late return:** 1.5 × the daily rate for every late day.
- **Damage:** the staff member enters the charge at return. If the car comes back on
  time with no damage, there is nothing extra to pay.
- **Cancel before pickup:** full refund (the booking is deleted).
- A car can't be booked twice for overlapping dates. Returning on the 20th and the
  next pickup on the 20th is allowed.

## How to run

You need Python 3.10 or newer.

```bash
pip install -r requirements.txt

# Streamlit app (main interface)
python -m streamlit run app.py

# Command-line version (same data, same rules)
python main.py

# Automated tests
python -m unittest discover -s tests -v
```

The Streamlit app opens in the browser at http://localhost:8501. The theme (white and
dark navy) and the localhost-only setting come from `.streamlit/config.toml`.

## Features

| Required feature | Where it is |
|---|---|
| 1. Add a record | **New booking**: car, pick-up and drop-off dates, name, phone, payment. Every field is checked, and each booking gets a unique ID (B001, B002…). |
| 2. View records | **Browse cars** (car cards) and **Bookings** (table of all bookings). Friendly messages when there's nothing to show. |
| 3. Search / filter | **Bookings**: search by name, phone, plate, car or ID (not case-sensitive), filter by status. **Browse cars**: search bar with pick-up/drop-off dates, car type and max price. |
| 4. Update a record | **Manage booking**: Pickup (document check + signed damage agreement), Return (late fee + damage), Edit details (name, phone, days). |
| 5. Delete a record | **Manage booking → Cancel / delete**, with a "Yes, I'm sure" confirmation. Cars still out with a customer can't be deleted. |
| 6. Save and load | Everything is stored in CSV files: `bookings.csv` is saved after every change and loaded at start, and `cars.csv` holds the car list. |
| 7. Summary | **Summary** page: cars in the shop, cars out, overdue, upcoming pickups, rental income, late fees, damage charges, total income and most popular car. |

**Extension (we chose one):** a simple graphical interface made with Streamlit.
It has a top menu bar, a search banner with big car photo cards, suggests the next step for every
booking (Pickup → Return), shows today's pickups, returns and overdue cars in the top bar, and lets
staff click a table row to open a booking.

### Error handling
- Wrong input (empty name, bad phone, drop-off before pick-up, past date, negative damage…) shows a clear
  message and nothing is saved.
- An unknown booking or car ID shows "No booking with ID …".
- **Missing `bookings.csv`:** the app starts with an empty log.
- **Damaged `bookings.csv`** (empty file, wrong columns, a bad date or number, or the same ID twice):
  the app shows a warning, keeps a copy called `bookings_damaged_<date>.csv` and starts empty,
  so the old data is never lost.
- **Missing `cars.csv`:** the app still opens, but new bookings are turned off.
- Saving writes to a temporary file first, so a crash in the middle of saving can't
  break `bookings.csv`.

## File structure

```
car_rental_log/
├── app.py            Streamlit interface (the menu)
├── .streamlit/config.toml   Theme colours + localhost-only setting
├── main.py           Command-line interface (same features, backup)
├── rental.py         Logic: Car, Booking, BookingManager classes
├── storage.py        File handling: read and write the CSV files
├── cars.csv          24 fictional cars (read only)
├── bookings.csv      12 fictional sample bookings
├── images/           Car photos (C001.jpg, C002.jpg …)
├── tests/
│   └── test_rental.py   26 automated tests
├── TESTING.md        Testing table
├── CONTRIBUTIONS.md  What each member did
├── requirements.txt
└── README.md
```

### Design choices
- **Three layers.** The menus (`app.py`, `main.py`) only talk to the user. `rental.py`
  holds every rule and raises a `ValueError` with a message when something is wrong.
  `storage.py` is the only file that touches the data files. Because of this, the
  Streamlit app and the command-line menu share the same logic with no copied code.
- **Classes.** `Booking` is one record and knows its own return date, cost, late days and
  overdue status. `BookingManager` holds all bookings and applies the rules. `Car` is one
  row of `cars.csv`.
- **Why a dictionary?** Bookings are stored as `{"B001": Booking, ...}`. Almost every
  action (pickup, return, edit, delete) starts from a booking ID, so a dictionary finds it
  straight away instead of looping through a list. Searching still uses a simple loop,
  and sorting uses Python's built-in `sorted()`.
- **Car details are copied into each booking**, so old bookings still make sense even if
  `cars.csv` changes later.
- **Why CSV?** Each booking is one row, so the file is easy to read and check in any text
  editor or spreadsheet. `storage.py` turns the text back into numbers, dates and True/False
  when loading.
- **A car that is still out stays blocked**, even after its return date has passed, until
  staff record the return.

## Adding car photos

Put a photo for each car in the `images/` folder, named after its `image` column in
`cars.csv` (by default the car ID, e.g. `C001.jpg`). Any size works: the app crops
every photo to the same 4:3 shape. Cars without a photo show a dashed "Add photo" box.

## Known limitations
- Staff-only and runs on one computer. There are no user accounts or passwords; a real
  system would need proper logins and a secure server.
- Payments are only recorded (method and amount). No real payment system is connected.
- Documents are checked by eye. The app stores a tick and the customer's typed name as
  the signature, not scans of real IDs.
- One person at a time: if two copies of the app run at once, the last one to save wins.
- Returning a car early does not refund unused days.
- The car list can only be changed by editing `cars.csv`.
- If you open `bookings.csv` in Excel, don't save it from Excel: Excel can change the date
  format and drop the leading 0 of phone numbers. Use a text editor, or just use the app.
- All names and phone numbers in the sample data are made up.

## AI assistance

_(Keep this section accurate before submitting.)_ We used Claude (Anthropic) to help
plan the features and to draft parts of the code and documentation. Every team member
read, ran and tested the code, and can explain the part they are responsible for.
