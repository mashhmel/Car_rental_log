"""
rental.py - the logic of the Car Rental Log.

Classes:
    Car            - one car from cars.csv (read-only, we never edit cars)
    Booking        - one booking (our main record type)
    BookingManager - keeps all bookings in a dictionary and applies the rules

This file never uses input() or print(). The menu files (app.py and main.py)
talk to the user. If something is wrong, the manager raises a ValueError with
a clear message, and the menu shows that message instead of crashing.
"""

from collections import Counter
from datetime import date, datetime, timedelta

# ----- Rules (change them here and the whole app follows) -----
LATE_FEE_RATE = 1.5        # late fee per day = daily rate x 1.5
MAX_DAYS = 60              # longest rental we allow
PAYMENT_METHODS = ["Cash", "Card", "Transfer"]

# ----- Booking statuses -----
BOOKED = "Booked"          # paid, waiting for pickup
PICKED_UP = "Picked up"    # customer has the car
RETURNED = "Returned"      # finished
OVERDUE = "Overdue"        # not stored - worked out from the dates
STATUS_FILTERS = ["All", BOOKED, PICKED_UP, OVERDUE, RETURNED]


def parse_date(value):
    """Turn 'YYYY-MM-DD' text (or a date) into a date object."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{value}' is not a valid date. Use YYYY-MM-DD.")


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class Car:
    """One car from the car list."""

    def __init__(self, car_id, brand, model, car_type, plate, daily_rate, image=""):
        self.car_id = car_id
        self.brand = brand
        self.model = model
        self.car_type = car_type
        self.plate = plate
        self.daily_rate = daily_rate
        self.image = image          # file name inside the images/ folder

    @property
    def name(self):
        return f"{self.brand} {self.model}"


class Booking:
    """One booking. The rental is paid in full when booking.
    Late fees and damage are charged as extras when the car comes back."""

    def __init__(self, booking_id, customer, phone, car_id, car_name, plate,
                 daily_rate, pickup_date, days, payment_method,
                 status=BOOKED, created_at="", docs_checked=False, signed_by="",
                 picked_up_at="", returned_on=None, late_fee=0, damage_fee=0,
                 damage_note="", extra_payment_method=""):
        self.booking_id = booking_id
        self.customer = customer
        self.phone = phone
        # We copy the car details so old bookings still make sense
        # even if cars.csv changes later.
        self.car_id = car_id
        self.car_name = car_name
        self.plate = plate
        self.daily_rate = int(daily_rate)
        self.pickup_date = parse_date(pickup_date)
        self.days = int(days)
        self.payment_method = payment_method
        self.status = status
        self.created_at = created_at
        # Filled in at pickup
        self.docs_checked = bool(docs_checked)
        self.signed_by = signed_by
        self.picked_up_at = picked_up_at
        # Filled in at return
        self.returned_on = parse_date(returned_on) if returned_on else None
        self.late_fee = int(late_fee)
        self.damage_fee = int(damage_fee)
        self.damage_note = damage_note
        self.extra_payment_method = extra_payment_method

    # ----- Worked-out values -----
    @property
    def return_date(self):
        """The day the car is due back."""
        return self.pickup_date + timedelta(days=self.days)

    @property
    def rental_cost(self):
        return self.days * self.daily_rate

    @property
    def extra_charges(self):
        return self.late_fee + self.damage_fee

    @property
    def total_paid(self):
        return self.rental_cost + self.extra_charges

    def is_active(self):
        """Active bookings block the car for their dates."""
        return self.status in (BOOKED, PICKED_UP)

    def is_overdue(self, today=None):
        today = today or date.today()
        return self.status == PICKED_UP and today > self.return_date

    def current_status(self, today=None):
        return OVERDUE if self.is_overdue(today) else self.status

    def late_days(self, returned_on):
        return max(0, (returned_on - self.return_date).days)

    def blocked_until(self, today=None):
        """The day the car is free again. A car that is still out with the customer
        stays blocked until it's actually returned, even if it's overdue."""
        today = today or date.today()
        if self.status == PICKED_UP:
            return max(self.return_date, today + timedelta(days=1))
        return self.return_date

    def overlaps(self, start, end, today=None):
        """True if [start, end) clashes with this booking's dates.
        Returning on the 20th and the next pickup on the 20th is fine."""
        return start < self.blocked_until(today) and end > self.pickup_date

    # ----- Converting to and from a dictionary (one row of bookings.csv) -----
    def to_dict(self):
        return {
            "booking_id": self.booking_id,
            "customer": self.customer,
            "phone": self.phone,
            "car_id": self.car_id,
            "car_name": self.car_name,
            "plate": self.plate,
            "daily_rate": self.daily_rate,
            "pickup_date": self.pickup_date.isoformat(),
            "days": self.days,
            "payment_method": self.payment_method,
            "status": self.status,
            "created_at": self.created_at,
            "docs_checked": self.docs_checked,
            "signed_by": self.signed_by,
            "picked_up_at": self.picked_up_at,
            "returned_on": self.returned_on.isoformat() if self.returned_on else None,
            "late_fee": self.late_fee,
            "damage_fee": self.damage_fee,
            "damage_note": self.damage_note,
            "extra_payment_method": self.extra_payment_method,
        }

    @classmethod
    def from_dict(cls, data):
        booking = cls(**data)
        if booking.status not in (BOOKED, PICKED_UP, RETURNED):
            raise ValueError(f"unknown status '{booking.status}' in {booking.booking_id}")
        return booking


class BookingManager:
    """Keeps every booking in a dictionary: {"B001": Booking, ...}.

    Why a dictionary? Almost every action (pickup, return, edit, delete)
    starts from a booking ID, and a dictionary finds an ID straight away
    instead of looping through a whole list."""

    def __init__(self, cars, bookings=None):
        self.cars = cars                     # {car_id: Car}, read from cars.csv
        self.bookings = bookings or {}       # {booking_id: Booking}

    # ----- Finding things -----
    def next_id(self):
        numbers = [int(bid[1:]) for bid in self.bookings if bid[1:].isdigit()]
        return f"B{max(numbers, default=0) + 1:03d}"

    def get_booking(self, booking_id):
        key = str(booking_id).strip().upper()
        if key not in self.bookings:
            raise ValueError(f"No booking with ID {key}.")
        return self.bookings[key]

    def get_car(self, car_id):
        key = str(car_id).strip().upper()
        if key not in self.cars:
            raise ValueError(f"No car with ID {key}.")
        return self.cars[key]

    def car_types(self):
        return sorted({car.car_type for car in self.cars.values()})

    # ----- Input checks (shared by add and edit) -----
    @staticmethod
    def check_customer(customer, phone):
        name = str(customer).strip()
        if not name:
            raise ValueError("Enter the customer's name.")
        digits = str(phone).strip().replace("-", "").replace(" ", "")
        if not digits.isdigit() or not 9 <= len(digits) <= 10:
            raise ValueError("Phone number should be 9-10 digits.")
        return name, digits

    @staticmethod
    def check_days(days):
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValueError("Number of days must be a whole number.")
        if days < 1:
            raise ValueError("Rental must be at least 1 day.")
        if days > MAX_DAYS:
            raise ValueError(f"Rental can't be longer than {MAX_DAYS} days.")
        return days

    # ----- Availability -----
    def blocking_booking(self, car_id, start, days, ignore_id=None, today=None):
        """Return the booking that blocks this car for these dates, or None."""
        end = start + timedelta(days=days)
        for booking in self.bookings.values():
            if (booking.car_id == car_id and booking.booking_id != ignore_id
                    and booking.is_active() and booking.overlaps(start, end, today)):
                return booking
        return None

    def browse_cars(self, start, days, car_type="All", max_rate=None, today=None):
        """Cars matching the filters, cheapest first.
        Gives a list of (car, blocking_booking) - blocking_booking is None if free."""
        results = []
        for car in sorted(self.cars.values(), key=lambda c: (c.daily_rate, c.name)):
            if car_type != "All" and car.car_type != car_type:
                continue
            if max_rate is not None and car.daily_rate > max_rate:
                continue
            results.append((car, self.blocking_booking(car.car_id, start, days, today=today)))
        return results

    # ----- Feature 1: Add -----
    def add_booking(self, customer, phone, car_id, pickup_date, days,
                    payment_method, today=None):
        today = today or date.today()
        name, phone = self.check_customer(customer, phone)
        car = self.get_car(car_id)
        pickup_date = parse_date(pickup_date)
        if pickup_date < today:
            raise ValueError("Pickup date can't be in the past.")
        days = self.check_days(days)
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Choose a payment method: Cash, Card or Transfer.")
        clash = self.blocking_booking(car.car_id, pickup_date, days, today=today)
        if clash:
            raise ValueError(
                f"{car.name} is already booked from {clash.pickup_date} to "
                f"{clash.blocked_until(today)} ({clash.booking_id}). Pick other dates or another car.")

        booking = Booking(self.next_id(), name, phone, car.car_id, car.name,
                          car.plate, car.daily_rate, pickup_date, days,
                          payment_method, created_at=now_text())
        self.bookings[booking.booking_id] = booking
        return booking

    # ----- Feature 3: Search / filter -----
    def search(self, keyword="", status="All", today=None):
        today = today or date.today()
        keyword = str(keyword).strip().lower()
        results = []
        for booking in self.bookings.values():
            if status == OVERDUE and not booking.is_overdue(today):
                continue
            if status not in ("All", OVERDUE) and booking.status != status:
                continue
            searchable = " ".join([booking.booking_id, booking.customer, booking.phone,
                                   booking.car_name, booking.plate]).lower()
            if keyword and keyword not in searchable:
                continue
            results.append(booking)
        return sorted(results, key=lambda b: b.booking_id, reverse=True)

    # ----- Feature 4: Update (pickup, return, edit) -----
    def pickup(self, booking_id, docs_checked, signed_by, today=None):
        today = today or date.today()
        booking = self.get_booking(booking_id)
        if booking.status != BOOKED:
            raise ValueError(f"Only Booked bookings can be picked up. This one is {booking.status}.")
        if today < booking.pickup_date:
            raise ValueError(f"This booking starts on {booking.pickup_date}. The car can't be picked up early.")
        if not docs_checked:
            raise ValueError("Check the customer's ID card and driver's license first.")
        if not str(signed_by).strip():
            raise ValueError("The customer must sign the damage agreement (type their full name).")
        booking.docs_checked = True
        booking.signed_by = str(signed_by).strip()
        booking.picked_up_at = now_text()
        booking.status = PICKED_UP
        return booking

    def return_quote(self, booking_id, returned_on, damage_fee=0, today=None):
        """Work out the final bill without changing anything (used for the preview)."""
        today = today or date.today()
        booking = self.get_booking(booking_id)
        if booking.status != PICKED_UP:
            raise ValueError(f"Only picked-up cars can be returned. This one is {booking.status}.")
        returned_on = parse_date(returned_on)
        if returned_on < booking.pickup_date:
            raise ValueError("Return date can't be before the pickup date.")
        if returned_on > today:
            raise ValueError("Return date can't be in the future.")
        try:
            damage_fee = int(damage_fee)
        except (TypeError, ValueError):
            raise ValueError("Damage fee must be a number.")
        if damage_fee < 0:
            raise ValueError("Damage fee can't be negative.")
        late_days = booking.late_days(returned_on)
        late_fee = round(late_days * booking.daily_rate * LATE_FEE_RATE)
        return {
            "already_paid": booking.rental_cost,
            "late_days": late_days,
            "late_fee": late_fee,
            "damage_fee": damage_fee,
            "extra_due": late_fee + damage_fee,
        }

    def return_car(self, booking_id, returned_on, damage_fee=0, damage_note="",
                   payment_method="", today=None):
        quote = self.return_quote(booking_id, returned_on, damage_fee, today)
        if quote["damage_fee"] > 0 and not str(damage_note).strip():
            raise ValueError("Add a short note describing the damage.")
        if quote["extra_due"] > 0 and payment_method not in PAYMENT_METHODS:
            raise ValueError("Choose how the customer pays the extra charges.")
        booking = self.get_booking(booking_id)
        booking.returned_on = parse_date(returned_on)
        booking.late_fee = quote["late_fee"]
        booking.damage_fee = quote["damage_fee"]
        booking.damage_note = str(damage_note).strip() if quote["damage_fee"] > 0 else ""
        booking.extra_payment_method = payment_method if quote["extra_due"] > 0 else ""
        booking.status = RETURNED
        return quote

    def edit_booking(self, booking_id, customer, phone, days):
        booking = self.get_booking(booking_id)
        if booking.status == RETURNED:
            raise ValueError("This booking is finished and can't be changed.")
        name, phone = self.check_customer(customer, phone)
        days = self.check_days(days)
        if days != booking.days:
            clash = self.blocking_booking(booking.car_id, booking.pickup_date, days,
                                          ignore_id=booking.booking_id)
            if clash:
                raise ValueError(
                    f"Can't change to {days} days: {booking.car_name} is booked "
                    f"from {clash.pickup_date} ({clash.booking_id}).")
        booking.customer, booking.phone, booking.days = name, phone, days
        return booking

    # ----- Feature 5: Delete -----
    def delete_booking(self, booking_id):
        booking = self.get_booking(booking_id)
        if booking.status == PICKED_UP:
            raise ValueError("This car is still out with the customer. Return it before deleting the booking.")
        del self.bookings[booking.booking_id]
        return booking

    # ----- Feature 7: Summary -----
    def summary(self, today=None):
        today = today or date.today()
        bookings = list(self.bookings.values())
        cars_out = {b.car_id for b in bookings if b.status == PICKED_UP}
        popular = Counter(b.car_name for b in bookings).most_common(1)
        rental_income = sum(b.rental_cost for b in bookings)
        late_income = sum(b.late_fee for b in bookings)
        damage_income = sum(b.damage_fee for b in bookings)
        return {
            "total_cars": len(self.cars),
            "cars_out": len(cars_out),
            "cars_in_shop": len(self.cars) - len(cars_out),
            "total_bookings": len(bookings),
            "booked": sum(1 for b in bookings if b.status == BOOKED),
            "picked_up": sum(1 for b in bookings if b.status == PICKED_UP),
            "overdue": sum(1 for b in bookings if b.is_overdue(today)),
            "pickups_today": sum(1 for b in bookings
                                 if b.status == BOOKED and b.pickup_date == today),
            "returns_today": sum(1 for b in bookings
                                 if b.status == PICKED_UP and b.return_date == today),
            "returned": sum(1 for b in bookings if b.status == RETURNED),
            "rental_income": rental_income,
            "late_fee_income": late_income,
            "damage_income": damage_income,
            "total_income": rental_income + late_income + damage_income,
            "most_popular": f"{popular[0][0]} ({popular[0][1]} bookings)" if popular else "-",
        }
