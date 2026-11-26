"""
main.py - simple command-line version of the Car Rental Log.

It uses exactly the same BookingManager (rental.py) and files (storage.py)
as the Streamlit app, so either one can be used. Run it with:  python main.py
"""

from datetime import date
from pathlib import Path

from rental import (PAYMENT_METHODS, PICKED_UP, STATUS_FILTERS,
                    BookingManager, parse_date)
from storage import load_bookings, load_cars, save_bookings

BASE_DIR = Path(__file__).resolve().parent
CARS_FILE = BASE_DIR / "cars.csv"
BOOKINGS_FILE = BASE_DIR / "bookings.csv"


# ---------------------------------------------------------------- input helpers
# Each helper keeps asking until the answer is valid, so bad input never crashes the program.
def ask_text(prompt, allow_empty=False):
    while True:
        answer = input(prompt).strip()
        if answer or allow_empty:
            return answer
        print("  This can't be empty.")


def ask_int(prompt, minimum=1, maximum=None, default=None):
    while True:
        answer = input(prompt).strip()
        if not answer and default is not None:
            return default
        if answer.lstrip("-").isdigit():
            number = int(answer)
            if number >= minimum and (maximum is None or number <= maximum):
                return number
        limit = f" and {maximum}" if maximum else " or more"
        print(f"  Enter a whole number, {minimum}{limit}.")


def ask_date(prompt, default=None):
    while True:
        answer = input(prompt).strip()
        if not answer and default:
            return default
        try:
            return parse_date(answer)
        except ValueError as error:
            print(f"  {error}")


def ask_yes_no(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer y or n.")


def ask_choice(prompt, options):
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    return options[ask_int(prompt, 1, len(options)) - 1]


def save(manager):
    try:
        save_bookings(manager.bookings, BOOKINGS_FILE)
    except OSError as error:
        print(f"  Warning: couldn't save bookings.csv ({error}).")


# ---------------------------------------------------------------- display
def print_bookings(bookings, today):
    if not bookings:
        print("  No bookings to show.")
        return
    print(f"  {'ID':<5} {'Customer':<18} {'Car':<20} {'Plate':<8} {'Pick-up':<11} {'Drop-off':<11} {'Status':<10} {'Paid':>9}")
    for b in bookings:
        print(f"  {b.booking_id:<5} {b.customer[:18]:<18} {b.car_name[:20]:<20} {b.plate:<8} "
              f"{b.pickup_date!s:<11} {b.return_date!s:<11} {b.current_status(today):<10} ${b.total_paid:>8,}")


# ---------------------------------------------------------------- menu actions
def browse_cars(manager, today):
    start = ask_date(f"Pickup date (YYYY-MM-DD) [Enter = {today}]: ", default=today)
    days = ask_int("Number of days [Enter = 1]: ", 1, 60, default=1)
    car_type = ask_choice("Car type: ", ["All"] + manager.car_types())
    free = [car for car, clash in manager.browse_cars(start, days, car_type, today=today) if clash is None]
    if not free:
        print("  No free cars for those dates.")
    for car in free:
        print(f"  {car.car_id}  {car.name:<22} {car.car_type:<10} {car.plate:<8} ${car.daily_rate:>4,}/day")
    return start, days


def new_booking(manager, today):
    if not manager.cars:
        print("  No cars loaded, so new bookings are turned off.")
        return
    start, days = browse_cars(manager, today)
    car_id = manager.get_car(ask_text("Car ID: ")).car_id      # stops here if the ID is wrong
    name = ask_text("Customer name: ")
    phone = ask_text("Phone number: ")
    manager.check_customer(name, phone)                         # stops here if the phone is wrong
    payment = ask_choice("Payment method: ", PAYMENT_METHODS)
    booking = manager.add_booking(name, phone, car_id, start, days, payment, today)
    print(f"  {booking.car_name} x {booking.days} day(s) = ${booking.rental_cost:,}, "
          f"back on {booking.return_date}")
    if ask_yes_no("  Confirm booking? (y/n): "):
        save(manager)
        print(f"  Booking {booking.booking_id} confirmed.")
    else:
        manager.bookings.pop(booking.booking_id)
        print("  Booking cancelled.")


def search_bookings(manager, today):
    keyword = ask_text("Search (name, phone, plate, car, ID) [Enter = everything]: ", allow_empty=True)
    status = ask_choice("Status: ", STATUS_FILTERS)
    results = manager.search(keyword, status, today)
    if not results:
        print(f'  No bookings match "{keyword}".' if keyword else "  No bookings match.")
    else:
        print_bookings(results, today)


def manage_booking(manager, today):
    booking = manager.get_booking(ask_text("Booking ID: "))
    print_bookings([booking], today)
    action = ask_choice("Action: ", ["Pickup", "Return", "Edit details", "Back"])
    if action == "Pickup":
        docs = ask_yes_no("  ID card and driver's license checked? (y/n): ")
        print(f"  The customer agrees to pay for any damage and late fees until {booking.return_date}.")
        signed = ask_text("  Customer signs (full name): ")
        manager.pickup(booking.booking_id, docs, signed, today)
        save(manager)
        print("  Car handed over.")
    elif action == "Return":
        returned_on = ask_date(f"  Return date [Enter = {today}]: ", default=today)
        damage_fee = ask_int("  Damage charge in $ [Enter = 0]: ", 0, default=0)
        note = ask_text("  What's damaged?: ") if damage_fee else ""
        quote = manager.return_quote(booking.booking_id, returned_on, damage_fee, today)
        print(f"  Late fee: ${quote['late_fee']:,} ({quote['late_days']} day(s) late)  "
              f"Damage: ${quote['damage_fee']:,}  Extra to pay: ${quote['extra_due']:,}")
        payment = ask_choice("  Paid by: ", PAYMENT_METHODS) if quote["extra_due"] else ""
        if ask_yes_no("  Confirm return? (y/n): "):
            manager.return_car(booking.booking_id, returned_on, damage_fee, note, payment, today)
            save(manager)
            print("  Car returned and available again.")
    elif action == "Edit details":
        name = ask_text(f"  Name [{booking.customer}]: ", allow_empty=True) or booking.customer
        phone = ask_text(f"  Phone [{booking.phone}]: ", allow_empty=True) or booking.phone
        days = ask_int(f"  Days [{booking.days}]: ", 1, 60, default=booking.days)
        manager.edit_booking(booking.booking_id, name, phone, days)
        save(manager)
        print("  Booking updated.")


def delete_booking(manager, today):
    booking = manager.get_booking(ask_text("Booking ID: "))
    print_bookings([booking], today)
    if booking.status == PICKED_UP:
        print("  This car is still out. Return it before deleting.")
        return
    if ask_yes_no(f"  Delete {booking.booking_id} ({booking.customer})? (y/n): "):
        manager.delete_booking(booking.booking_id)
        save(manager)
        print(f"  {booking.booking_id} deleted.")
    else:
        print("  Cancelled. Nothing was deleted.")


def show_summary(manager, today):
    s = manager.summary(today)
    print(f"""
  Cars in the shop:   {s['cars_in_shop']} / {s['total_cars']}
  Cars out now:       {s['cars_out']}
  Overdue:            {s['overdue']}
  Upcoming pickups:   {s['booked']}
  Rental income:      ${s['rental_income']:,}
  Late fees:          ${s['late_fee_income']:,}
  Damage charges:     ${s['damage_income']:,}
  Total income:       ${s['total_income']:,}
  Most popular car:   {s['most_popular']}""")


# ---------------------------------------------------------------- main loop
def main():
    cars, car_message = load_cars(CARS_FILE)
    bookings, booking_message = load_bookings(BOOKINGS_FILE)
    for message in (car_message, booking_message):
        if message:
            print(f"! {message}")
    manager = BookingManager(cars, bookings)

    actions = {
        "1": ("Browse free cars", browse_cars),
        "2": ("New booking", new_booking),
        "3": ("View all bookings", lambda m, t: print_bookings(m.search(today=t), t)),
        "4": ("Search bookings", search_bookings),
        "5": ("Manage booking (pickup / return / edit)", manage_booking),
        "6": ("Delete booking", delete_booking),
        "7": ("Summary", show_summary),
    }
    while True:
        today = date.today()
        print("\n===== CAR RENTAL LOG =====")
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("0. Exit")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye! All changes are saved.")
            break
        if choice not in actions:
            print("  Please choose a number from the menu.")
            continue
        try:
            actions[choice][1](manager, today)
        except ValueError as error:      # rule broken, e.g. unknown ID or bad phone
            print(f"  {error}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye! All changes are saved.")
