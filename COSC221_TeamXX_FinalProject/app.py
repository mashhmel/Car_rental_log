"""
app.py - the Streamlit staff app (our main menu / interface).

Run it with:   python -m streamlit run app.py
(.streamlit/config.toml sets the white + navy theme and keeps the app on localhost)

Pages (top menu):  Browse cars | New booking | Bookings | Manage booking | Summary

This file only shows things and collects input. Every rule lives in
rental.py (BookingManager) and every file operation lives in storage.py.
"""

from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from rental import (BOOKED, LATE_FEE_RATE, OVERDUE, PAYMENT_METHODS,
                    PICKED_UP, RETURNED, STATUS_FILTERS, BookingManager)
from storage import load_bookings, load_cars, save_bookings

BASE_DIR = Path(__file__).resolve().parent
CARS_FILE = BASE_DIR / "cars.csv"
BOOKINGS_FILE = BASE_DIR / "bookings.csv"
IMAGES_DIR = BASE_DIR / "images"

PAGES = {   # page name -> icon shown in the top menu
    "Browse cars": ":material/directions_car:",
    "New booking": ":material/add_circle:",
    "Bookings": ":material/list_alt:",
    "Manage booking": ":material/edit_calendar:",
    "Summary": ":material/bar_chart:",
}
STATUS_DOTS = {BOOKED: "🔵", PICKED_UP: "🟠", OVERDUE: "🔴", RETURNED: "🟢"}
ACTIONS = ["Pickup", "Return", "Edit details", "Cancel / delete"]
NAVY = "#0B2545"

st.set_page_config(page_title="Car Rental Log", page_icon="🚗", layout="wide",
                   initial_sidebar_state="collapsed")

# Style touches on top of the theme in .streamlit/config.toml
st.markdown(f"""
<style>
  [data-testid="stHeader"] {{display: none;}}
  .block-container {{padding-top: 1rem; max-width: 1280px;}}

  /* top menu bar */
  .st-key-topbar {{background: {NAVY}; border-radius: 16px 16px 0 0; padding: 14px 22px;}}
  .st-key-topbar .brand {{color: #fff; font-weight: 700; font-size: 1.25rem; white-space: nowrap;}}
  .st-key-topbar [data-testid="stBaseButton-tertiary"] {{color: #fff; padding: 6px 14px;}}
  .st-key-topbar [data-testid="stBaseButton-tertiary"]:hover {{background: rgba(255,255,255,.1);
      border-radius: 999px; color: #fff;}}
  .st-key-topbar [data-testid="stBaseButton-primary"] {{background: transparent; color: #fff;
      border: 1.5px solid #fff; border-radius: 999px; padding: 6px 14px;}}
  .st-key-topbar .today {{color: #C9D6EA; font-size: .85rem; white-space: nowrap;}}
  .st-key-topbar .today b {{color: #fff;}}
  .st-key-topbar .today .warn {{color: #FF9B9B;}}
  .navgap {{background: {NAVY}; height: 18px; border-radius: 0 0 16px 16px; margin-top: -1rem;
            margin-bottom: 1.2rem;}}

  /* hero search banner (Browse cars) */
  .st-key-hero {{background: {NAVY}; border-radius: 0 0 16px 16px; padding: 8px 28px 26px;
                 margin-top: -1.2rem; margin-bottom: 1.2rem;}}
  .st-key-hero h1 {{color: #fff; font-size: 2.6rem; margin: 0; padding: 0;}}
  .st-key-hero .ticks {{color: #E3EAF5; font-size: 1.05rem; margin: 2px 0 10px;}}
  .st-key-hero [data-testid="stForm"] {{background: #fff; border: 3px solid #8DB3E2;
                 border-radius: 12px; padding: 14px 16px;}}
  .st-key-hero [data-testid="stFormSubmitButton"] button {{background: {NAVY}; color: #fff;
                 height: 2.6rem; font-weight: 700;}}

  /* car cards */
  .car-name {{font-size: 1.2rem; font-weight: 700; color: {NAVY}; margin-top: 4px;}}
  .price {{font-size: 1.5rem; font-weight: 800; color: {NAVY};}}
  .price small {{font-size: .9rem; font-weight: 400; color: #5A6B85;}}
  .chip {{display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem;
          background: #EAF0F8; color: #13315C; margin-right: 4px;}}
  .chip.busy {{background: #F1F1F1; color: #6B6B6B;}}
  .photo-slot {{aspect-ratio: 4/3; border: 1.5px dashed #B8C4D6; border-radius: 12px;
                display: flex; align-items: center; justify-content: center; text-align: center;
                color: #7A8AA3; font-size: .9rem; background: #F7F9FC;}}
  .step {{font-weight: 700; color: {NAVY}; margin: .6rem 0 .2rem;}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def money(amount):
    return f"${amount:,.0f}"


def status_label(status):
    return f"{STATUS_DOTS.get(status, '')} {status}"


def get_manager():
    """Load the files once per session and keep the manager in session_state
    (Streamlit reruns this whole script after every click)."""
    if "manager" not in st.session_state:
        cars, car_message = load_cars(CARS_FILE)
        bookings, booking_message = load_bookings(BOOKINGS_FILE)
        st.session_state.manager = BookingManager(cars, bookings)
        st.session_state.load_messages = [m for m in (car_message, booking_message) if m]
    return st.session_state.manager


def save(manager):
    """Save after every change. Returns an error message, or None if it worked."""
    try:
        save_bookings(manager.bookings, BOOKINGS_FILE)
        return None
    except OSError as error:
        return f"Couldn't save bookings.csv: {error}"


def flash(message, kind="success"):
    """Remember a message to show after the page reloads."""
    st.session_state.flash = (kind, message)


def show_flash():
    if "flash" in st.session_state:
        kind, message = st.session_state.pop("flash")
        getattr(st, kind)(message)


def go_to(page, **values):
    """Button callback: switch page and pre-fill some fields."""
    st.session_state.page = page
    for key, value in values.items():
        st.session_state[key] = value


@st.cache_data(show_spinner=False)
def load_photo(path_text, modified_time):
    """Crop every photo to the same 4:3 shape on a white background."""
    with Image.open(path_text) as photo:
        rgb_photo = _flatten_to_white_rgb(photo)
        return ImageOps.fit(rgb_photo, (800, 600))


def show_car_photo(car):
    photo_path = IMAGES_DIR / (car.image or f"{car.car_id}.jpg")
    if photo_path.is_file():
        try:
            st.image(load_photo(str(photo_path), photo_path.stat().st_mtime), width="stretch")
            return
        except OSError:
            pass  # broken image file: show the placeholder instead
    st.markdown(
        f"<div class='photo-slot'>📷<br>images/{photo_path.name}</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- top menu
def top_bar(manager, today):
    s = manager.summary(today)
    overdue = f"<span class='warn'><b>{s['overdue']}</b> overdue</span>" if s["overdue"] else "<b>0</b> overdue"
    with st.container(key="topbar"):
        left, right = st.columns([1, 3], vertical_alignment="center")
        left.markdown(f"<div class='brand'>🚗 Car Rental Log</div>"
                      f"<div class='today'>Today: <b>{s['pickups_today']}</b> pickups · "
                      f"<b>{s['returns_today']}</b> returns · {overdue}</div>", unsafe_allow_html=True)
        with right:
            with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
                for page, icon in PAGES.items():
                    st.button(page, icon=icon, key=f"nav_{page}",
                              type="primary" if st.session_state.page == page else "tertiary",
                              on_click=go_to, args=(page,))
    if st.session_state.page != "Browse cars":
        st.markdown("<div class='navgap'></div>", unsafe_allow_html=True)
    for message in st.session_state.get("load_messages", []):
        st.warning(message)


# ---------------------------------------------------------------- 1. Browse cars
def browse_page(manager, today):
    if not manager.cars:
        st.error("No cars loaded. Add cars.csv to the project folder and restart the app.")
        return

    rates = sorted(car.daily_rate for car in manager.cars.values())
    price_min = rates[0] // 5 * 5               # round to nice numbers, e.g. $25 ... $200
    price_max = -(-rates[-1] // 5) * 5
    search = st.session_state.setdefault("search", {
        "start": today, "end": today + timedelta(days=1), "type": "All",
        "max_rate": price_max, "only_free": False})
    if search["start"] < today:   # app left open overnight
        search.update(start=today, end=max(search["end"], today + timedelta(days=1)))

    # Each search field has a fixed key so Streamlit always remembers what was picked.
    # When we come back from another page, the fields are filled in again from `search`.
    types = ["All"] + manager.car_types()
    remembered = {"f_start": search["start"], "f_end": search["end"], "f_type": search["type"],
                  "f_max": search["max_rate"], "f_free": search["only_free"]}
    for key, value in remembered.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.f_start < today:
        st.session_state.f_start = today
    if st.session_state.f_end <= today:
        st.session_state.f_end = today + timedelta(days=1)
    if st.session_state.f_type not in types:
        st.session_state.f_type = "All"
    st.session_state.f_max = min(max(st.session_state.f_max, price_min), price_max)

    with st.container(key="hero"):
        st.markdown("<h1>Car rental – find, book &amp; go</h1>"
                    "<div class='ticks'>✓ Pay once, no hidden fees &nbsp; ✓ Free cancellation before "
                    f"pickup &nbsp; ✓ {len(manager.cars)} cars to choose from</div>",
                    unsafe_allow_html=True)
        with st.form("search_form", border=False):
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1.3], vertical_alignment="bottom")
            start = c1.date_input("Pick-up date", key="f_start", min_value=today)
            end = c2.date_input("Drop-off date", key="f_end", min_value=today + timedelta(days=1))
            car_type = c3.selectbox("Car type", types, key="f_type")
            max_rate = c4.slider("Max price / day", price_min, price_max, key="f_max", step=5,
                                 format="$%d")
            submitted = c5.form_submit_button("Search", icon=":material/search:", width="stretch")
            only_free = st.checkbox("Only available cars", key="f_free")
        if submitted:
            if end <= start:
                st.error("Drop-off must be after pick-up.")
            else:
                search.update(start=start, end=end, type=car_type, max_rate=max_rate, only_free=only_free)

    start, end = search["start"], search["end"]
    days = (end - start).days
    results = manager.browse_cars(start, days, search["type"], search["max_rate"], today)
    free = sum(1 for _, clash in results if clash is None)
    if search["only_free"]:
        results = [(car, clash) for car, clash in results if clash is None]
    if not results:
        st.info("No cars match. Try a higher price or another type.")
        return
    st.markdown(f"#### {free} cars available · {start:%d %b} → {end:%d %b} ({days} day{'s' if days > 1 else ''})")

    columns = st.columns(3, gap="medium")
    for index, (car, clash) in enumerate(results):
        with columns[index % 3]:
            with st.container(border=True):
                show_car_photo(car)
                st.markdown(f"<div class='car-name'>{car.name}</div>"
                            f"<span class='chip'>{car.car_type}</span>"
                            + ("" if clash is None else
                               f"<span class='chip busy'>Booked until {clash.blocked_until(today):%d %b}</span>"),
                            unsafe_allow_html=True)
                left, right = st.columns([3, 2], vertical_alignment="center")
                left.markdown(f"<div class='price'>{money(car.daily_rate)} <small>/ day</small></div>",
                              unsafe_allow_html=True)
                if clash is None:
                    right.button("Book", key=f"book_{car.car_id}", type="primary", width="stretch",
                                 help=f"{days} day(s) = {money(car.daily_rate * days)}",
                                 on_click=go_to, args=("New booking",),
                                 kwargs={"nb_car": car.car_id, "nb_start": start, "nb_end": end})
                else:
                    right.button("Booked", key=f"busy_{car.car_id}", disabled=True, width="stretch")


# ---------------------------------------------------------------- 2. New booking
def confirm_booking():
    """Callback for the Confirm booking button."""
    manager = st.session_state.manager
    days = (st.session_state.nb_end - st.session_state.nb_start).days
    try:
        booking = manager.add_booking(
            st.session_state.nb_name, st.session_state.nb_phone, st.session_state.nb_car,
            st.session_state.nb_start, days, st.session_state.nb_payment)
    except ValueError as error:
        st.session_state.nb_error = str(error)
        return
    st.session_state.nb_error = save(manager)
    st.session_state.nb_receipt = booking.booking_id
    st.session_state.nb_name = ""
    st.session_state.nb_phone = ""


def new_booking_page(manager, today):
    st.title("New booking")
    if not manager.cars:
        st.error("No cars loaded, so new bookings are turned off.")
        return

    receipt_id = st.session_state.pop("nb_receipt", None)
    if receipt_id in manager.bookings:
        b = manager.bookings[receipt_id]
        with st.container(border=True):
            st.success(f"**Booking {b.booking_id} confirmed** · {b.customer} · {b.car_name} · "
                       f"{b.pickup_date:%d %b} → {b.return_date:%d %b} · {money(b.rental_cost)}", icon="✅")
            st.caption("Customer brings ID card + driver's license at pickup.")
            c1, c2 = st.columns(2)
            c1.button("Open booking", icon=":material/edit_calendar:", width="stretch",
                      on_click=go_to, args=("Manage booking",), kwargs={"mb_id": b.booking_id})
            c2.button("Book another car", icon=":material/directions_car:", width="stretch",
                      on_click=go_to, args=("Browse cars",))
    if st.session_state.get("nb_error"):
        st.error(st.session_state.pop("nb_error"), icon="⚠️")

    # Default values (set before the widgets are drawn)
    car_ids = sorted(manager.cars, key=lambda cid: (manager.cars[cid].daily_rate, cid))
    if st.session_state.get("nb_car") not in manager.cars:
        st.session_state.nb_car = car_ids[0]
    if st.session_state.get("nb_start", today) < today:
        st.session_state.nb_start = today
    st.session_state.setdefault("nb_start", today)
    if st.session_state.get("nb_end", today) <= st.session_state.nb_start:
        st.session_state.nb_end = st.session_state.nb_start + timedelta(days=1)
    st.session_state.setdefault("nb_payment", PAYMENT_METHODS[0])

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("<div class='step'>① Car and dates</div>", unsafe_allow_html=True)
        st.selectbox("Car", car_ids, key="nb_car",
                     format_func=lambda cid: f"{manager.cars[cid].name} · {manager.cars[cid].car_type} · "
                                             f"{money(manager.cars[cid].daily_rate)}/day")
        d1, d2 = st.columns(2)
        d1.date_input("Pick-up date", key="nb_start", min_value=today)
        d2.date_input("Drop-off date", key="nb_end",
                      min_value=st.session_state.nb_start + timedelta(days=1))

        st.markdown("<div class='step'>② Customer</div>", unsafe_allow_html=True)
        st.text_input("Full name", key="nb_name", placeholder="Somchai Jaidee")
        st.text_input("Phone", key="nb_phone", placeholder="0812345678")

        st.markdown("<div class='step'>③ Payment</div>", unsafe_allow_html=True)
        st.segmented_control("Payment method", PAYMENT_METHODS, key="nb_payment",
                             label_visibility="collapsed")

    with right:
        car = manager.cars[st.session_state.nb_car]
        start, end = st.session_state.nb_start, st.session_state.nb_end
        days = (end - start).days
        with st.container(border=True):
            show_car_photo(car)
            st.markdown(f"<div class='car-name'>{car.name}</div><span class='chip'>{car.car_type}</span>"
                        f"<span class='chip'>{car.plate}</span>", unsafe_allow_html=True)
            st.write(f"{start:%a %d %b} → {end:%a %d %b} · {days} day(s) × {money(car.daily_rate)}")
            st.markdown(f"<div class='price'>{money(days * car.daily_rate)} <small>total</small></div>",
                        unsafe_allow_html=True)
            clash = manager.blocking_booking(car.car_id, start, days, today=today)
            if clash:
                st.warning(f"Booked {clash.pickup_date:%d %b}–{clash.blocked_until(today):%d %b} ({clash.booking_id}). "
                           "Pick other dates or another car.")
            st.button("Confirm booking", type="primary", width="stretch",
                      icon=":material/check:", on_click=confirm_booking)


# ---------------------------------------------------------------- 3. Bookings
def bookings_page(manager, today):
    st.title("Bookings")
    if not manager.bookings:
        st.info("No bookings yet.")
        return

    col1, col2 = st.columns([2, 3], vertical_alignment="bottom")
    keyword = col1.text_input("Search", placeholder="Search name, phone, plate, car or ID",
                              label_visibility="collapsed")
    status = col2.segmented_control("Status", STATUS_FILTERS, default="All",
                                    label_visibility="collapsed") or "All"
    results = manager.search(keyword, status, today)
    if not results:
        st.info(f'No bookings match "{keyword}".' if keyword else f"No {status.lower()} bookings.")
        return

    rows = [{
        "ID": b.booking_id,
        "Customer": b.customer,
        "Phone": b.phone,
        "Car": f"{b.car_name} ({b.plate})",
        "Pick-up": b.pickup_date,
        "Drop-off": b.return_date,
        "Status": status_label(b.current_status(today)),
        "Paid": b.total_paid,
    } for b in results]
    event = st.dataframe(
        rows, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key="bookings_table",
        column_config={"Paid": st.column_config.NumberColumn(format="$%d"),
                       "Pick-up": st.column_config.DateColumn(format="D MMM YYYY"),
                       "Drop-off": st.column_config.DateColumn(format="D MMM YYYY")})

    selected = event.selection.rows if event and event.selection else []
    if selected and selected[0] < len(results):
        b = results[selected[0]]
        st.button(f"Open {b.booking_id} · {b.customer}", type="primary",
                  icon=":material/arrow_forward:", on_click=go_to,
                  args=("Manage booking",), kwargs={"mb_id": b.booking_id})
    else:
        st.caption(f"{len(results)} booking(s) · click a row to open it")


# ---------------------------------------------------------------- 4. Manage booking
def suggested_action(b):
    return "Pickup" if b.status == BOOKED else "Return"


def next_step_banner(b, today):
    if b.status == BOOKED and today < b.pickup_date:
        st.info(f"Pickup on **{b.pickup_date:%a %d %b}**", icon=":material/schedule:")
    elif b.status == BOOKED:
        st.info("**Next: Pickup**", icon=":material/key:")
    elif b.is_overdue(today):
        st.error(f"**Overdue {(today - b.return_date).days} day(s)** · call {b.phone}",
                 icon=":material/warning:")
    elif b.status == PICKED_UP:
        st.info(f"**Next: Return** · due {b.return_date:%a %d %b}", icon=":material/assignment_return:")
    else:
        st.success(f"Returned {b.returned_on:%d %b %Y}", icon=":material/task_alt:")


def manage_page(manager, today):
    st.title("Manage booking")
    show_flash()
    if not manager.bookings:
        st.info("No bookings yet.")
        return

    ids = sorted(manager.bookings, reverse=True)
    if st.session_state.get("mb_id") not in ids:
        st.session_state.mb_id = ids[0]
    booking_id = st.selectbox(
        "Booking", ids, key="mb_id", label_visibility="collapsed",
        format_func=lambda bid: f"{bid} · {manager.bookings[bid].customer} · "
                                f"{manager.bookings[bid].car_name} · "
                                f"{status_label(manager.bookings[bid].current_status(today))}")
    b = manager.bookings[booking_id]
    # After a pickup/return, jump to the new suggested step instead of staying on the old one
    if st.session_state.pop("reset_action", None) == b.booking_id:
        st.session_state.pop(f"action_{b.booking_id}", None)

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**{b.customer}**  \n{b.phone}")
        c2.markdown(f"**{b.car_name}**  \n{b.plate}")
        c3.markdown(f"**{b.pickup_date:%d %b} → {b.return_date:%d %b}**  \n"
                    f"{b.days} day(s) × {money(b.daily_rate)}")
        c4.markdown(f"**{status_label(b.current_status(today))}**  \nPaid {money(b.total_paid)}")
    next_step_banner(b, today)

    action = st.segmented_control("Action", ACTIONS, default=suggested_action(b),
                                  key=f"action_{b.booking_id}",
                                  label_visibility="collapsed") or suggested_action(b)
    if action == "Pickup":
        pickup_section(manager, b, today)
    elif action == "Return":
        return_section(manager, b, today)
    elif action == "Edit details":
        edit_section(manager, b)
    else:
        delete_section(manager, b)


def pickup_section(manager, b, today):
    if b.status != BOOKED:
        if b.picked_up_at:
            st.success(f"Picked up {b.picked_up_at} · signed by **{b.signed_by}**")
        return
    if today < b.pickup_date:
        st.caption(f"Pickup opens on {b.pickup_date:%d %b %Y}.")
        return

    with st.container(border=True):
        docs = st.checkbox("ID card and driver's license checked", key=f"docs_{b.booking_id}")
        st.markdown(f"> I'll return the **{b.car_name}** by **{b.return_date:%d %b %Y}**, pay for any damage, "
                    f"and pay **{money(b.daily_rate * LATE_FEE_RATE)}** per late day.")
        signed = st.text_input("Customer signs (full name)", key=f"sign_{b.booking_id}",
                               placeholder=b.customer)
        if st.button("Hand over the car", type="primary", icon=":material/key:"):
            try:
                manager.pickup(b.booking_id, docs, signed, today)
            except ValueError as error:
                st.error(str(error))
                return
            error = save(manager)
            st.session_state.reset_action = b.booking_id
            flash(error or f"{b.car_name} handed over to {b.customer}. Due back {b.return_date:%d %b}.",
                  "error" if error else "success")
            st.rerun()


def return_section(manager, b, today):
    if b.status == RETURNED:
        st.markdown(final_bill_text(b.rental_cost, b.late_days(b.returned_on), b.late_fee,
                                    b.damage_fee, b.damage_note))
        return
    if b.status != PICKED_UP:
        st.caption("Not picked up yet.")
        return

    with st.container(border=True):
        c1, c2 = st.columns(2)
        returned_on = c1.date_input("Return date", value=today, min_value=b.pickup_date,
                                    max_value=today, key=f"ret_date_{b.booking_id}")
        damage_level = c2.segmented_control("Damage", ["None", "Minor", "Major"],
                                            default="None", key=f"ret_level_{b.booking_id}") or "None"
        damage_fee, note = 0, ""
        if damage_level != "None":
            d1, d2 = st.columns([1, 2])
            damage_fee = d1.number_input("Damage charge ($)", min_value=0, step=10,
                                         value=50 if damage_level == "Minor" else 300,
                                         key=f"ret_fee_{b.booking_id}_{damage_level}")
            note = d2.text_input("What's damaged?", key=f"ret_note_{b.booking_id}",
                                 placeholder="Scratch on rear bumper")
            note = f"{damage_level}: {note}" if note.strip() else ""

        try:
            quote = manager.return_quote(b.booking_id, returned_on, damage_fee, today)
        except ValueError as error:
            st.error(str(error))
            return
        st.markdown(final_bill_text(quote["already_paid"], quote["late_days"], quote["late_fee"],
                                    quote["damage_fee"], note))

        payment = ""
        if quote["extra_due"] > 0:
            payment = st.segmented_control("Extra paid by", PAYMENT_METHODS,
                                           key=f"ret_pay_{b.booking_id}") or ""
        if st.button("Confirm return", type="primary", icon=":material/assignment_return:"):
            try:
                manager.return_car(b.booking_id, returned_on, damage_fee, note, payment, today)
            except ValueError as error:
                st.error(str(error))
                return
            error = save(manager)
            st.session_state.reset_action = b.booking_id
            flash(error or f"{b.car_name} returned. Extra charged: {money(quote['extra_due'])}.",
                  "error" if error else "success")
            st.rerun()


def final_bill_text(already_paid, late_days, late_fee, damage_fee, note):
    lines = ["| Final bill | |\n|---|---:|", f"| Rental (paid) | {money(already_paid)} |"]
    lines.append(f"| Late ({late_days} day(s)) | {money(late_fee)} |" if late_days
                 else "| Late fee | $0 ✅ |")
    lines.append(f"| Damage ({note or 'add a note'}) | {money(damage_fee)} |" if damage_fee
                 else "| Damage | $0 ✅ |")
    lines.append(f"| **Extra to pay** | **{money(late_fee + damage_fee)}** |")
    return "\n".join(lines)


def edit_section(manager, b):
    if b.status == RETURNED:
        st.caption("Finished bookings can't be edited.")
        return
    with st.form(f"edit_{b.booking_id}", border=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        name = c1.text_input("Customer name", value=b.customer)
        phone = c2.text_input("Phone", value=b.phone)
        days = c3.number_input("Days", min_value=1, max_value=60, value=b.days, step=1)
        submitted = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
    if submitted:
        old_cost = b.rental_cost
        try:
            manager.edit_booking(b.booking_id, name, phone, days)
        except ValueError as error:
            st.error(str(error))
            return
        error = save(manager)
        difference = b.rental_cost - old_cost
        note = ""
        if difference > 0:
            note = f" Collect {money(difference)} more."
        elif difference < 0:
            note = f" Refund {money(-difference)}."
        flash(error or f"{b.booking_id} updated.{note}", "error" if error else "success")
        st.rerun()


def delete_section(manager, b):
    if b.status == PICKED_UP:
        st.warning("Car is still out. Return it first.")
        return
    with st.container(border=True):
        if b.status == BOOKED:
            st.write(f"Full refund: **{money(b.rental_cost)}**")
        else:
            st.write("Removes this finished booking from the records.")
        sure = st.checkbox(f"Yes, delete {b.booking_id}", key=f"del_{b.booking_id}")
        if st.button("Delete booking", disabled=not sure, icon=":material/delete:"):
            try:
                manager.delete_booking(b.booking_id)
            except ValueError as error:
                st.error(str(error))
                return
            error = save(manager)
            flash(error or f"Booking {b.booking_id} deleted.", "error" if error else "success")
            st.rerun()


# ---------------------------------------------------------------- 5. Summary
def summary_page(manager, today):
    st.title("Summary")
    s = manager.summary(today)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cars in shop", f"{s['cars_in_shop']} / {s['total_cars']}", border=True)
    c2.metric("Cars out", s["cars_out"], border=True)
    c3.metric("Overdue", s["overdue"], border=True)
    c4.metric("Upcoming pickups", s["booked"], border=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rental income", money(s["rental_income"]), border=True)
    c2.metric("Late fees", money(s["late_fee_income"]), border=True)
    c3.metric("Damage", money(s["damage_income"]), border=True)
    c4.metric("Total income", money(s["total_income"]), border=True)

    st.write(f"**Most popular:** {s['most_popular']}  ·  **{s['total_bookings']} bookings** "
             f"({s['booked']} booked, {s['picked_up']} out, {s['returned']} returned)")

    overdue = manager.search(status=OVERDUE, today=today)
    if overdue:
        st.subheader("Overdue")
        st.dataframe([{"ID": b.booking_id, "Customer": b.customer, "Phone": b.phone,
                       "Car": f"{b.car_name} ({b.plate})", "Was due": b.return_date,
                       "Days late": (today - b.return_date).days} for b in overdue],
                     hide_index=True, width="stretch")


# ---------------------------------------------------------------- main
def main():
    manager = get_manager()
    today = date.today()
    if st.session_state.get("page") not in PAGES:
        st.session_state.page = "Browse cars"
    top_bar(manager, today)

    page = st.session_state.page
    if page == "Browse cars":
        browse_page(manager, today)
    elif page == "New booking":
        new_booking_page(manager, today)
    elif page == "Bookings":
        bookings_page(manager, today)
    elif page == "Manage booking":
        manage_page(manager, today)
    else:
        summary_page(manager, today)


main()
