"""
storage.py - reading and writing our data files (both are CSV).

    cars.csv       the list of cars (read only)
    bookings.csv   all bookings (read at start, saved after every change)

Nothing here talks to the user directly. Each load function gives back the
data plus a message (or None) so the menu can decide how to show it.
"""

import csv
import os
import shutil
from datetime import datetime
from pathlib import Path

from rental import Booking, Car

# The columns of bookings.csv, in order (the same names as Booking.to_dict())
BOOKING_COLUMNS = [
    "booking_id", "customer", "phone", "car_id", "car_name", "plate", "daily_rate",
    "pickup_date", "days", "payment_method", "status", "created_at", "docs_checked",
    "signed_by", "picked_up_at", "returned_on", "late_fee", "damage_fee",
    "damage_note", "extra_payment_method",
]


def load_cars(path):
    """Read cars.csv. Returns (cars_dict, message)."""
    path = Path(path)
    if not path.exists():
        return {}, f"Car list not found ({path.name}). New bookings are turned off until it's added."

    cars, skipped = {}, 0
    try:
        with open(path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                try:
                    car = Car(
                        car_id=row["car_id"].strip().upper(),
                        brand=row["brand"].strip(),
                        model=row["model"].strip(),
                        car_type=row["type"].strip(),
                        plate=row["plate"].strip().upper(),
                        daily_rate=int(row["daily_rate"]),
                        image=(row.get("image") or "").strip(),
                    )
                    if not car.car_id or car.daily_rate <= 0:
                        raise ValueError
                    cars[car.car_id] = car
                except (KeyError, ValueError, AttributeError, TypeError):
                    skipped += 1        # one bad row shouldn't stop the whole list
    except (OSError, csv.Error, UnicodeDecodeError) as error:
        return {}, f"Couldn't read {path.name}: {error}"

    if not cars:
        return {}, f"{path.name} has no valid cars. New bookings are turned off."
    if skipped:
        return cars, f"Skipped {skipped} row(s) in {path.name} with missing or invalid values."
    return cars, None


def row_to_booking(row, line_number):
    """Turn one CSV row (all text) back into a Booking object."""
    missing = [column for column in BOOKING_COLUMNS if row.get(column) is None]
    if missing:
        raise ValueError(f"line {line_number} is missing {', '.join(missing)}")
    data = dict(row)
    # CSV stores everything as text, so turn yes/no and empty values back into Python values
    data["docs_checked"] = row["docs_checked"].strip().lower() in ("true", "yes", "1")
    data["returned_on"] = row["returned_on"].strip() or None
    data["late_fee"] = row["late_fee"].strip() or 0
    data["damage_fee"] = row["damage_fee"].strip() or 0
    try:
        return Booking.from_dict({column: data[column] for column in BOOKING_COLUMNS})
    except (ValueError, TypeError) as error:
        raise ValueError(f"line {line_number}: {error}")


def load_bookings(path):
    """Read bookings.csv. Returns (bookings_dict, message).

    Missing file  -> start with no bookings.
    Damaged file  -> keep a backup copy, warn the user, start with no bookings.
                     The original data is never lost.
    """
    path = Path(path)
    if not path.exists():
        return {}, f"No {path.name} found, so we're starting with an empty booking log."

    try:
        with open(path, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                raise ValueError("the file is empty")
            missing = [column for column in BOOKING_COLUMNS if column not in reader.fieldnames]
            if missing:
                shown = ", ".join(missing[:3]) + (" ..." if len(missing) > 3 else "")
                raise ValueError(f"missing column(s): {shown}")
            bookings = {}
            for line_number, row in enumerate(reader, start=2):   # line 1 is the header
                booking = row_to_booking(row, line_number)
                if booking.booking_id in bookings:
                    raise ValueError(f"booking ID {booking.booking_id} appears twice")
                bookings[booking.booking_id] = booking
        return bookings, None
    except (ValueError, KeyError, TypeError, csv.Error, UnicodeDecodeError) as error:
        backup = path.with_name(f"{path.stem}_damaged_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}")
        shutil.copy2(path, backup)
        return {}, (f"{path.name} is damaged ({error}). A copy was kept as {backup.name}, "
                    "so nothing is lost. Starting with an empty log for now.")
    except OSError as error:
        return {}, f"Couldn't open {path.name}: {error}"


def save_bookings(bookings, path):
    """Write every booking to bookings.csv (one row per booking).

    We write to a temporary file first and then swap it in, so if the program
    stops halfway through saving, the old file is still fine."""
    path = Path(path)
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=BOOKING_COLUMNS)
        writer.writeheader()
        for booking_id in sorted(bookings):
            writer.writerow(bookings[booking_id].to_dict())
    os.replace(temp_path, path)
