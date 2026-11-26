# Testing table — Car Rental Log

Tested on: 17 Nov 2026 (rows 8, 9, 12b and 17 on 26 Nov 2026).
Re-run every row yourselves before submitting, update the dates and actual results, and write
"Not run yet" for anything you haven't run. Results that depend on today's date (overdue days,
late fees) will be different on the day you test.
How: by hand in the Streamlit app, plus 22 automated tests
(`python -m unittest discover -s tests -v` → all 26 pass).

| # | Input / action | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|
| 1 | **Add a valid record:** Browse cars → "Book" on Suzuki Swift → drop-off 3 days later, name "Anna Lee", phone 0812345678, Cash → Confirm booking | Booking created with a new ID, shown in Bookings | "Booking B013 confirmed", 3 × $29 = $87, appears in the Bookings table as Booked | Pass |
| 2 | **Empty required field:** Confirm booking with the name left empty | Rejected with a message, nothing saved | "Enter the customer's name." No new booking | Pass |
| 3 | **Invalid value:** phone "12ab"; damage charge –500; 0 days | Each one rejected | "Phone number should be 9-10 digits." / damage field won't accept below 0 / "Rental must be at least 1 day." | Pass |
| 4a | **Search that exists:** Bookings → search "anna" (lowercase) | Anna Lee's booking shown | 1 result: B013 Anna Lee | Pass |
| 4b | **Search that doesn't exist:** search "ferrari" | Friendly "no match" message | `No bookings match "ferrari".` | Pass |
| 5 | **Update and verify:** Manage → B009 → Edit details → days 3 → 4 → Save changes | Return date and price change, saved | "B009 updated. Collect $85 more." Bookings shows drop-off 24 Nov | Pass |
| 6a | **Cancel a deletion:** Manage → B010 → Cancel / delete, don't tick "Yes, delete B010" | Delete button stays off, nothing deleted | Button disabled, B010 still there | Pass |
| 6b | **Confirm a deletion:** tick "Yes, delete B010" → Delete booking | Booking removed, car free again | "Booking B010 deleted." Hyundai Staria bookable for those dates | Pass |
| 7 | **Restart and verify saved records:** close the app (Ctrl+C), run it again | All changes from tests 1–6 still there | B013 present, B009 still 4 days, B010 gone | Pass |
| 8 | **Missing data file:** rename `bookings.csv`, start the app | App opens with an empty log and a message | Warning: "No bookings.csv found, so we're starting with an empty booking log." | Pass |
| 9 | **Damaged data file** (on a test copy): replace `bookings.csv` with `this,is,not` / `our,booking,file`, start the app | Warning shown, file kept, app still opens | "bookings.csv is damaged (missing column(s): booking_id, customer, phone ...)", copy saved as `bookings_damaged_<date>.csv`, original not overwritten | Pass |
| 10 | **Double booking:** book Toyota Yaris Ativ BC-2033 for 18 Nov (it is out until 21 Nov) | Car shown as unavailable, booking blocked | Card shows "Booked until 21 Nov" and a disabled "Booked" button; New booking shows "Booked 16 Nov–21 Nov (B008)" | Pass |
| 11 | **Pickup without documents:** Manage → B013 → "Hand over the car" without ticking "ID card and driver's license checked" | Rejected | "Check the customer's ID card and driver's license first." | Pass |
| 12 | **Late return fee:** Return B006 (Mazda CX-5, $68/day, due 14 Nov) on 17 Nov | 3 days × $68 × 1.5 = $306 extra | Final bill shows late $306, extra to pay $306; red "Overdue 3 day(s)" banner | Pass |
| 12b | **Overdue car stays blocked:** B008 (Yaris BC-2033, due 21 Nov, not returned), Browse cars on 26 Nov | Car not bookable until it's returned | Card shows "Booked until 27 Nov" and a disabled "Booked" button | Pass |
| 13 | **On-time return, no damage** | Nothing extra to pay | Final bill: Late fee $0 ✅, Damage $0 ✅, Extra to pay $0 | Pass |
| 14 | **Can't delete a car that's out:** Manage → B007 (Picked up) → Cancel / delete | Not allowed | "This car is still out with the customer. Return it before deleting the booking." | Pass |
| 15 | **Missing cars.csv:** rename `cars.csv`, start the app | App opens, bookings still viewable, new bookings off | "Car list not found (cars.csv). New bookings are turned off until it's added." | Pass |
| 16 | **Drop-off before pick-up:** Browse cars → pick-up 22 Nov, drop-off 19 Nov → Search | Rejected | "Drop-off must be after pick-up." | Pass |
| 17 | **Unknown ID:** command-line menu → 5 (Manage booking) → type `B999` | Helpful message, nothing changes | "No booking with ID B999." and back to the menu | Pass |

## Summary check by hand

Small set (automated test `test_summary_numbers_by_hand`):

| Booking | Calculation | Amount |
|---|---|---|
| A: Toyota Yaris, 2 days × $35 | 2 × 35 | $70 |
| B: Honda CR-V, 3 days × $70 | 3 × 70 | $210 |
| B returned 1 day late | 1 × 70 × 1.5 | $105 |
| B damage | entered at return | $50 |
| **Total income** | 70 + 210 + 105 + 50 | **$435** |

The app's `summary()` gave rental income $280, late fees $105, damage $50,
total $435, 1 booked and 1 returned. **Pass.**
