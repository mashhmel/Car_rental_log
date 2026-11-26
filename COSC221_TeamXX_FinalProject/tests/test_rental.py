"""
Automated tests for the Car Rental Log.
Run from the project folder:  python -m unittest discover -s tests -v
"""

import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rental import BOOKED, PICKED_UP, RETURNED, OVERDUE, BookingManager, Car  # noqa: E402
from storage import load_bookings, load_cars, save_bookings  # noqa: E402

TODAY = date(2026, 11, 17)


def make_manager():
    cars = {
        "C001": Car("C001", "Toyota", "Yaris", "Sedan", "AB-1111", 35),
        "C002": Car("C002", "Honda", "CR-V", "SUV", "KK-2222", 70),
    }
    return BookingManager(cars)


class AddBookingTests(unittest.TestCase):
    def setUp(self):
        self.m = make_manager()

    def test_valid_booking(self):
        b = self.m.add_booking("Anna Lee", "0812345678", "C002", "2026-11-20", 3, "Card", today=TODAY)
        self.assertEqual(b.booking_id, "B001")
        self.assertEqual(b.rental_cost, 210)
        self.assertEqual(b.return_date, date(2026, 11, 23))
        self.assertEqual(b.status, BOOKED)

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            self.m.add_booking("   ", "0812345678", "C001", "2026-11-20", 2, "Cash", today=TODAY)
        self.assertEqual(len(self.m.bookings), 0)

    def test_bad_phone_rejected(self):
        with self.assertRaises(ValueError):
            self.m.add_booking("Anna", "12ab", "C001", "2026-11-20", 2, "Cash", today=TODAY)

    def test_zero_days_rejected(self):
        with self.assertRaises(ValueError):
            self.m.add_booking("Anna", "0812345678", "C001", "2026-11-20", 0, "Cash", today=TODAY)

    def test_past_date_rejected(self):
        with self.assertRaises(ValueError):
            self.m.add_booking("Anna", "0812345678", "C001", "2026-11-01", 2, "Cash", today=TODAY)

    def test_double_booking_blocked_but_back_to_back_allowed(self):
        self.m.add_booking("Anna", "0812345678", "C001", "2026-11-20", 3, "Cash", today=TODAY)
        with self.assertRaises(ValueError):
            self.m.add_booking("Ben", "0812345679", "C001", "2026-11-21", 1, "Cash", today=TODAY)
        # first booking returns on the 23rd, so a pickup on the 23rd is fine
        b = self.m.add_booking("Ben", "0812345679", "C001", "2026-11-23", 1, "Cash", today=TODAY)
        self.assertEqual(b.booking_id, "B002")


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.m = make_manager()
        self.b = self.m.add_booking("Anna", "0812345678", "C002", "2026-11-17", 3, "Card", today=TODAY)

    def test_pickup_needs_documents_and_signature(self):
        with self.assertRaises(ValueError):
            self.m.pickup("B001", False, "Anna", today=TODAY)
        with self.assertRaises(ValueError):
            self.m.pickup("B001", True, "  ", today=TODAY)
        self.m.pickup("b001", True, "Anna", today=TODAY)   # lowercase ID still works
        self.assertEqual(self.b.status, PICKED_UP)

    def test_on_time_return_has_no_extra(self):
        self.m.pickup("B001", True, "Anna", today=TODAY)
        quote = self.m.return_car("B001", "2026-11-20", today=date(2026, 11, 20))
        self.assertEqual(quote["extra_due"], 0)
        self.assertEqual(self.b.status, RETURNED)

    def test_late_return_fee(self):
        self.m.pickup("B001", True, "Anna", today=TODAY)
        # due 20 Nov, back 22 Nov -> 2 days x $70 x 1.5 = $210
        quote = self.m.return_car("B001", "2026-11-22", payment_method="Cash", today=date(2026, 11, 22))
        self.assertEqual(quote["late_days"], 2)
        self.assertEqual(quote["late_fee"], 210)
        self.assertEqual(self.b.total_paid, 420)

    def test_damage_needs_note(self):
        self.m.pickup("B001", True, "Anna", today=TODAY)
        with self.assertRaises(ValueError):
            self.m.return_car("B001", "2026-11-20", damage_fee=50, payment_method="Cash",
                              today=date(2026, 11, 20))
        quote = self.m.return_car("B001", "2026-11-20", damage_fee=50, damage_note="Scratch",
                                  payment_method="Cash", today=date(2026, 11, 20))
        self.assertEqual(quote["extra_due"], 50)

    def test_edit_booking(self):
        self.m.edit_booking("B001", "Anna Lee", "0899999999", 5)
        self.assertEqual(self.b.customer, "Anna Lee")
        self.assertEqual(self.b.rental_cost, 350)

    def test_unknown_id(self):
        with self.assertRaises(ValueError):
            self.m.get_booking("B999")

    def test_overdue_car_stays_blocked(self):
        # B001 picked up 17 Nov for 3 days (due 20 Nov) and never returned.
        self.m.pickup("B001", True, "Anna", today=TODAY)
        late_today = date(2026, 11, 26)
        clash = self.m.blocking_booking("C002", late_today, 2, today=late_today)
        self.assertEqual(clash.booking_id, "B001")
        with self.assertRaises(ValueError):
            self.m.add_booking("Ben", "0812345679", "C002", late_today, 2, "Cash", today=late_today)
        # once it's returned, the car is free again
        self.m.return_car("B001", late_today, payment_method="Cash", today=late_today)
        self.assertIsNone(self.m.blocking_booking("C002", late_today, 2, today=late_today))

    def test_overdue_status(self):
        self.m.pickup("B001", True, "Anna", today=TODAY)
        self.assertEqual(self.b.current_status(date(2026, 11, 20)), PICKED_UP)
        self.assertEqual(self.b.current_status(date(2026, 11, 21)), OVERDUE)


class DeleteAndSearchTests(unittest.TestCase):
    def setUp(self):
        self.m = make_manager()
        self.m.add_booking("Anna Lee", "0812345678", "C001", "2026-11-17", 2, "Cash", today=TODAY)
        self.m.add_booking("Ben Carter", "0812345679", "C002", "2026-11-18", 2, "Card", today=TODAY)

    def test_delete_booked_frees_car(self):
        self.m.delete_booking("B002")
        self.assertNotIn("B002", self.m.bookings)
        self.assertIsNone(self.m.blocking_booking("C002", date(2026, 11, 18), 2))

    def test_cannot_delete_car_that_is_out(self):
        self.m.pickup("B001", True, "Anna", today=TODAY)
        with self.assertRaises(ValueError):
            self.m.delete_booking("B001")

    def test_search_found_and_not_found(self):
        self.assertEqual(len(self.m.search("anna", today=TODAY)), 1)
        self.assertEqual(len(self.m.search("cr-v", today=TODAY)), 1)
        self.assertEqual(self.m.search("ferrari", today=TODAY), [])
        self.assertEqual(len(self.m.search(status=BOOKED, today=TODAY)), 2)


class SummaryTests(unittest.TestCase):
    def test_summary_numbers_by_hand(self):
        m = make_manager()
        m.add_booking("A", "0811111111", "C001", "2026-11-17", 2, "Cash", today=TODAY)   # 2 x $35 = $70
        m.add_booking("B", "0822222222", "C002", "2026-11-17", 3, "Card", today=TODAY)   # 3 x $70 = $210
        m.pickup("B002", True, "B", today=TODAY)
        # back 1 day late: 1 x $70 x 1.5 = $105, plus $50 damage
        m.return_car("B002", "2026-11-21", 50, "Dent", "Cash", today=date(2026, 11, 21))
        s = m.summary(today=date(2026, 11, 21))
        self.assertEqual(s["rental_income"], 280)
        self.assertEqual(s["late_fee_income"], 105)
        self.assertEqual(s["damage_income"], 50)
        self.assertEqual(s["total_income"], 435)
        self.assertEqual(s["booked"], 1)
        self.assertEqual(s["returned"], 1)
        self.assertEqual(s["cars_out"], 0)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.path = self.folder / "bookings.csv"

    def damaged_check(self, bad_text):
        """Write a broken bookings.csv and check it's reported, backed up and left untouched."""
        self.path.write_text(bad_text, encoding="utf-8")
        loaded, message = load_bookings(self.path)
        self.assertEqual(loaded, {})
        self.assertIn("damaged", message)
        backups = list(self.folder.glob("bookings_damaged_*.csv"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), bad_text)
        self.assertEqual(self.path.read_text(encoding="utf-8"), bad_text)   # original not overwritten

    def test_save_then_load_keeps_bookings(self):
        m = make_manager()
        m.add_booking("Anna", "0812345678", "C001", "2026-11-20", 2, "Cash", today=TODAY)
        m.pickup("B001", True, "Anna", today=date(2026, 11, 20))
        save_bookings(m.bookings, self.path)
        loaded, message = load_bookings(self.path)
        self.assertIsNone(message)
        b = loaded["B001"]
        self.assertEqual(b.customer, "Anna")
        self.assertEqual(b.phone, "0812345678")          # leading zero kept
        self.assertEqual(b.return_date, date(2026, 11, 22))
        self.assertIs(b.docs_checked, True)               # "True" text turned back into True
        self.assertIsNone(b.returned_on)                  # empty cell turned back into None
        self.assertEqual(b.to_dict(), m.bookings["B001"].to_dict())

    def test_missing_file_starts_empty(self):
        loaded, message = load_bookings(self.folder / "nothing.csv")
        self.assertEqual(loaded, {})
        self.assertIn("empty", message)

    def test_damaged_file_empty(self):
        self.damaged_check("")

    def test_damaged_file_wrong_columns(self):
        self.damaged_check("name,price\nAnna,10\n")

    def test_damaged_file_bad_value(self):
        m = make_manager()
        m.add_booking("Anna", "0812345678", "C001", "2026-11-20", 2, "Cash", today=TODAY)
        save_bookings(m.bookings, self.path)
        broken = self.path.read_text(encoding="utf-8").replace("2026-11-20", "not-a-date")
        self.damaged_check(broken)

    def test_damaged_file_duplicate_id(self):
        m = make_manager()
        m.add_booking("Anna", "0812345678", "C001", "2026-11-20", 2, "Cash", today=TODAY)
        save_bookings(m.bookings, self.path)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.damaged_check("\n".join(lines + [lines[1]]) + "\n")

    def test_missing_cars_file(self):
        cars, message = load_cars(self.folder / "cars.csv")
        self.assertEqual(cars, {})
        self.assertIn("not found", message)

    def test_project_sample_data_loads(self):
        project = Path(__file__).resolve().parent.parent
        cars, car_msg = load_cars(project / "cars.csv")
        bookings, booking_msg = load_bookings(project / "bookings.csv")
        self.assertIsNone(car_msg)
        self.assertIsNone(booking_msg)
        self.assertGreaterEqual(len(bookings), 10)
        self.assertTrue(all(b.car_id in cars for b in bookings.values()))
        with open(project / "bookings.csv", newline="", encoding="utf-8") as file:
            self.assertEqual(len(list(csv.DictReader(file))), len(bookings))


if __name__ == "__main__":
    unittest.main()
