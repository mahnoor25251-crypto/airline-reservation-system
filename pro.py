import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
from datetime import datetime
from abc import ABC, abstractmethod


# ─────────────────────────────────────────────
#  ORIGINAL OOP CODE (unchanged logic)
# ─────────────────────────────────────────────

class InvalidDataError(Exception):
    pass

class Passenger:
    def __init__(self, name, email, password):
        self.__name = name
        self.__email = email
        self.__password = password
    def get_name(self): return self.__name
    def get_email(self): return self.__email
    def passenger_detail(self):
        return f"Name: {self.__name}\nEmail: {self.__email}"

class Seat:
    def __init__(self, Class):
        self._Class = Class.lower()
    def class_detail(self):
        if self._Class == "economy":
            return "Economy: Standard Seats, Entertainment, Amenities"
        elif self._Class == "business":
            return "Business: Wider Seats, Dining, Airport Services, Amenities"

class Flight(Seat):
    booked_seats = []
    def __init__(self, flight_id, origin, destination, date, Class):
        super().__init__(Class)
        self._flight_id = flight_id
        self._origin_city = origin
        self._destination_city = destination
        self._date = date
        self.max_seats = 50
    def flight_detail(self):
        remaining = self.max_seats - len(Flight.booked_seats)
        return f"Flight {self._flight_id} | {self._origin_city} → {self._destination_city} | {self._date} | {remaining} seats left"

class Payment(ABC):
    def __init__(self, amount):
        self.amount = amount
    @abstractmethod
    def make_payment(self): pass

class CreditCardPayment(Payment):
    def make_payment(self): return f"Rs.{self.amount:,} paid via Credit Card ✓"

class CashPayment(Payment):
    def make_payment(self): return f"Rs.{self.amount:,} paid via Cash ✓"

class JazzCashPayment(Payment):
    def make_payment(self): return f"Rs.{self.amount:,} paid via JazzCash ✓"

class Booking(Flight, Passenger):
    booking_counter = 100
    def __init__(self, name, email, password, flight_id, origin, destination, date, Class, seat_quantity, total_price):
        Passenger.__init__(self, name, email, password)
        Flight.__init__(self, flight_id, origin, destination, date, Class)
        Booking.booking_counter += 1
        self.booking_id = Booking.booking_counter
        self.seat_quantity = seat_quantity
        self.total_price = total_price
        self.booking_status = "Active"
        self._booked_seats_list = []

class Admin:
    def __init__(self, admin_name, admin_password):
        self.__admin_name = admin_name
        self.__admin_password = admin_password
    def admin_detail(self): return f"Admin: {self.__admin_name}"


# ─────────────────────────────────────────────
#  DATABASE LAYER
# ─────────────────────────────────────────────

ROUTES = {
    1: {"origin": "Lahore",     "destination": "Karachi", "economy": 15000,  "business": 30000},
    2: {"origin": "Lahore",     "destination": "Dubai",   "economy": 50000,  "business": 90000},
    3: {"origin": "Islamabad",  "destination": "Turkey",  "economy": 70000,  "business": 120000},
    4: {"origin": "Karachi",    "destination": "UK",      "economy": 100000, "business": 180000},
}

def get_db():
    conn = sqlite3.connect("airline.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Check if bookings table has passenger_id column; if not, rebuild schema
    c.execute("CREATE TABLE IF NOT EXISTS passengers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS booked_seats_global (seat_number INTEGER PRIMARY KEY)")

    # Check bookings table columns
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookings'")
    if c.fetchone():
        cols = [row[1] for row in c.execute("PRAGMA table_info(bookings)")]
        if "passenger_id" not in cols:
            # Old schema — drop and recreate
            c.execute("DROP TABLE bookings")

    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER UNIQUE NOT NULL,
        passenger_id INTEGER,
        flight_id INTEGER,
        origin TEXT,
        destination TEXT,
        flight_date TEXT,
        class TEXT,
        seat_quantity INTEGER,
        booked_seats TEXT,
        total_price INTEGER,
        payment_method TEXT,
        status TEXT DEFAULT 'Active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(passenger_id) REFERENCES passengers(id)
    )""")
    conn.commit()
    conn.close()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def register_passenger(name, email, password):
    conn = get_db()
    try:
        conn.execute("INSERT INTO passengers (name,email,password_hash) VALUES (?,?,?)",
                     (name, email, hash_pw(password)))
        conn.commit()
        return conn.execute("SELECT id FROM passengers WHERE email=?", (email,)).fetchone()["id"]
    except sqlite3.IntegrityError:
        return conn.execute("SELECT id FROM passengers WHERE email=?", (email,)).fetchone()["id"]
    finally:
        conn.close()

def save_booking(booking_obj, passenger_id, seats, payment_method):
    conn = get_db()
    conn.execute("""INSERT INTO bookings
        (booking_id,passenger_id,flight_id,origin,destination,flight_date,class,seat_quantity,booked_seats,total_price,payment_method,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (booking_obj.booking_id, passenger_id,
         booking_obj._flight_id, booking_obj._origin_city,
         booking_obj._destination_city, booking_obj._date,
         booking_obj._Class, booking_obj.seat_quantity,
         str(seats), booking_obj.total_price, payment_method, "Active"))
    for s in seats:
        try:
            conn.execute("INSERT INTO booked_seats_global VALUES (?)", (s,))
        except:
            pass
    conn.commit()
    conn.close()

def cancel_booking_db(booking_id):
    conn = get_db()
    row = conn.execute("SELECT booked_seats FROM bookings WHERE booking_id=?", (booking_id,)).fetchone()
    if row:
        seats = eval(row["booked_seats"])
        conn.execute("UPDATE bookings SET status='Cancelled' WHERE booking_id=?", (booking_id,))
        for s in seats:
            conn.execute("DELETE FROM booked_seats_global WHERE seat_number=?", (s,))
        conn.commit()
    conn.close()

def get_all_bookings():
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, COALESCE(p.name,'Unknown') as name, COALESCE(p.email,'') as email
        FROM bookings b
        LEFT JOIN passengers p ON b.passenger_id = p.id
        ORDER BY b.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_global_booked_seats():
    conn = get_db()
    rows = conn.execute("SELECT seat_number FROM booked_seats_global").fetchall()
    conn.close()
    return [r["seat_number"] for r in rows]

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM bookings").fetchone()["c"]
    active = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Active'").fetchone()["c"]
    revenue = conn.execute("SELECT SUM(total_price) as s FROM bookings WHERE status='Active'").fetchone()["s"] or 0
    passengers = conn.execute("SELECT COUNT(*) as c FROM passengers").fetchone()["c"]
    conn.close()
    return {"total": total, "active": active, "revenue": revenue, "passengers": passengers}


# ─────────────────────────────────────────────
#  GUI APPLICATION
# ─────────────────────────────────────────────

COLORS = {
    "bg":        "#0A0E1A",
    "panel":     "#111827",
    "card":      "#1A2233",
    "accent":    "#3B82F6",
    "accent2":   "#06B6D4",
    "success":   "#10B981",
    "danger":    "#EF4444",
    "warning":   "#F59E0B",
    "text":      "#F1F5F9",
    "muted":     "#94A3B8",
    "border":    "#1E293B",
    "input_bg":  "#0F172A",
    "hover":     "#2563EB",
}

FONT_HEAD  = ("Segoe UI", 22, "bold")
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_BODY  = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 11)


class AirlineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()
        Flight.booked_seats = get_global_booked_seats()

        self.title("SkyLine — Airline Reservation System")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(bg=COLORS["bg"])

        # state
        self.current_page = tk.StringVar(value="dashboard")
        self.booking_data  = {}

        self._build_ui()
        self.show_page("dashboard")

    # ── layout ──────────────────────────────
    def _build_ui(self):
        # sidebar
        self.sidebar = tk.Frame(self, bg=COLORS["panel"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # logo
        logo_f = tk.Frame(self.sidebar, bg=COLORS["panel"])
        logo_f.pack(fill="x", pady=(28,24), padx=20)
        tk.Label(logo_f, text="✈  SkyLine", font=("Segoe UI", 17, "bold"),
                 bg=COLORS["panel"], fg=COLORS["accent"]).pack(anchor="w")
        tk.Label(logo_f, text="Reservation System", font=FONT_SMALL,
                 bg=COLORS["panel"], fg=COLORS["muted"]).pack(anchor="w")

        # nav items
        self.nav_btns = {}
        nav_items = [
            ("dashboard",  "🏠", "Dashboard"),
            ("book",       "🎫", "New Booking"),
            ("bookings",   "📋", "All Bookings"),
            ("seats",      "💺", "Seat Map"),
            ("admin",      "⚙️",  "Admin Panel"),
        ]
        nav_frame = tk.Frame(self.sidebar, bg=COLORS["panel"])
        nav_frame.pack(fill="both", expand=True, padx=10)

        for key, icon, label in nav_items:
            btn = tk.Button(nav_frame, text=f" {icon}  {label}",
                            font=FONT_BODY, anchor="w",
                            bg=COLORS["panel"], fg=COLORS["muted"],
                            activebackground=COLORS["card"],
                            activeforeground=COLORS["text"],
                            relief="flat", bd=0, padx=12, pady=10,
                            cursor="hand2",
                            command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", pady=2)
            self.nav_btns[key] = btn

        # main content area
        self.main = tk.Frame(self, bg=COLORS["bg"])
        self.main.pack(side="left", fill="both", expand=True)

        self.pages = {}
        for page_id in ("dashboard","book","bookings","seats","admin"):
            f = tk.Frame(self.main, bg=COLORS["bg"])
            self.pages[page_id] = f

    def show_page(self, page_id):
        for k, btn in self.nav_btns.items():
            btn.config(
                bg=COLORS["card"] if k==page_id else COLORS["panel"],
                fg=COLORS["text"] if k==page_id else COLORS["muted"],
            )
        for f in self.pages.values():
            f.pack_forget()

        frame = self.pages[page_id]
        # rebuild each time for fresh data
        for w in frame.winfo_children():
            w.destroy()

        builders = {
            "dashboard": self._build_dashboard,
            "book":      self._build_booking,
            "bookings":  self._build_all_bookings,
            "seats":     self._build_seat_map,
            "admin":     self._build_admin,
        }
        builders[page_id](frame)
        frame.pack(side="left", fill="both", expand=True)

    # ── helpers ─────────────────────────────
    def _header(self, parent, title, subtitle=""):
        hf = tk.Frame(parent, bg=COLORS["bg"])
        hf.pack(fill="x", padx=32, pady=(28,0))
        tk.Label(hf, text=title, font=FONT_HEAD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        if subtitle:
            tk.Label(hf, text=subtitle, font=FONT_BODY,
                     bg=COLORS["bg"], fg=COLORS["muted"]).pack(anchor="w")
        tk.Frame(hf, height=1, bg=COLORS["border"]).pack(fill="x", pady=(12,0))

    def _card(self, parent, **kwargs):
        c = tk.Frame(parent, bg=COLORS["card"],
                     highlightbackground=COLORS["border"],
                     highlightthickness=1, **kwargs)
        return c

    def _label(self, parent, text, font=None, fg=None, **kwargs):
        return tk.Label(parent, text=text,
                        font=font or FONT_BODY,
                        fg=fg or COLORS["text"],
                        bg=parent.cget("bg"), **kwargs)

    def _entry(self, parent, placeholder="", **kwargs):
        v = tk.StringVar()
        e = tk.Entry(parent, textvariable=v,
                     font=FONT_BODY, bg=COLORS["input_bg"],
                     fg=COLORS["text"], insertbackground=COLORS["text"],
                     relief="flat", bd=0,
                     highlightbackground=COLORS["border"],
                     highlightthickness=1, **kwargs)
        if placeholder:
            e.insert(0, placeholder)
            e.config(fg=COLORS["muted"])
            def on_focus_in(ev, ph=placeholder):
                if e.get()==ph: e.delete(0,"end"); e.config(fg=COLORS["text"])
            def on_focus_out(ev, ph=placeholder):
                if not e.get(): e.insert(0,ph); e.config(fg=COLORS["muted"])
            e.bind("<FocusIn>", on_focus_in)
            e.bind("<FocusOut>", on_focus_out)
        return e, v

    def _btn(self, parent, text, command, color=None, **kwargs):
        c = color or COLORS["accent"]
        b = tk.Button(parent, text=text, command=command,
                      font=FONT_BODY, bg=c, fg="white",
                      activebackground=COLORS["hover"],
                      activeforeground="white",
                      relief="flat", bd=0, padx=20, pady=9,
                      cursor="hand2", **kwargs)
        return b

    # ── DASHBOARD ───────────────────────────
    def _build_dashboard(self, parent):
        self._header(parent, "✈  Dashboard", f"Welcome back  ·  {datetime.now().strftime('%d %b %Y')}")
        stats = get_stats()

        # stat cards
        sf = tk.Frame(parent, bg=COLORS["bg"])
        sf.pack(fill="x", padx=32, pady=20)
        stat_data = [
            ("Total Bookings",  stats["total"],    COLORS["accent"],  "🎫"),
            ("Active",          stats["active"],   COLORS["success"], "✅"),
            ("Passengers",      stats["passengers"],COLORS["accent2"],"👤"),
            ("Revenue (Rs.)",   f"{stats['revenue']:,}", COLORS["warning"],"💰"),
        ]
        sf.columnconfigure((0,1,2,3), weight=1)
        for i,(label,val,color,icon) in enumerate(stat_data):
            c = self._card(sf)
            c.grid(row=0, column=i, padx=8, pady=4, sticky="ew")
            tk.Label(c, text=icon, font=("Segoe UI",24),
                     bg=COLORS["card"], fg=color).pack(anchor="w", padx=18, pady=(16,4))
            tk.Label(c, text=str(val), font=("Segoe UI",26,"bold"),
                     bg=COLORS["card"], fg=COLORS["text"]).pack(anchor="w", padx=18)
            tk.Label(c, text=label, font=FONT_SMALL,
                     bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w", padx=18, pady=(2,16))

        # routes overview
        rf = tk.Frame(parent, bg=COLORS["bg"])
        rf.pack(fill="x", padx=32, pady=(0,16))
        rf.columnconfigure((0,1), weight=1)

        # recent bookings
        lf = self._card(rf)
        lf.grid(row=0, column=0, padx=(0,8), pady=4, sticky="nsew")
        tk.Label(lf, text="Recent Bookings", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(14,8))

        bookings = get_all_bookings()[:6]
        if not bookings:
            tk.Label(lf, text="No bookings yet", font=FONT_BODY,
                     bg=COLORS["card"], fg=COLORS["muted"]).pack(padx=16, pady=20)
        else:
            for b in bookings:
                row = tk.Frame(lf, bg=COLORS["card"])
                row.pack(fill="x", padx=16, pady=3)
                status_color = COLORS["success"] if b["status"]=="Active" else COLORS["danger"]
                tk.Label(row, text=f"#{b['booking_id']}", font=FONT_MONO,
                         bg=COLORS["card"], fg=COLORS["accent"]).pack(side="left")
                tk.Label(row, text=f"  {b['name']}", font=FONT_BODY,
                         bg=COLORS["card"], fg=COLORS["text"]).pack(side="left")
                tk.Label(row, text=f"  {b['origin']} → {b['destination']}", font=FONT_SMALL,
                         bg=COLORS["card"], fg=COLORS["muted"]).pack(side="left")
                tk.Label(row, text=b["status"], font=FONT_SMALL,
                         bg=COLORS["card"], fg=status_color).pack(side="right")
        tk.Frame(lf, height=14, bg=COLORS["card"]).pack()

        # routes card
        rcard = self._card(rf)
        rcard.grid(row=0, column=1, padx=(8,0), pady=4, sticky="nsew")
        tk.Label(rcard, text="Available Routes", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(14,8))
        for k,v in ROUTES.items():
            row = tk.Frame(rcard, bg=COLORS["card"])
            row.pack(fill="x", padx=16, pady=4)
            tk.Label(row, text=f"Route {k}", font=FONT_MONO,
                     bg=COLORS["card"], fg=COLORS["accent2"]).pack(side="left")
            tk.Label(row, text=f"  {v['origin']} → {v['destination']}", font=FONT_BODY,
                     bg=COLORS["card"], fg=COLORS["text"]).pack(side="left")
            tk.Label(row, text=f"Eco: Rs.{v['economy']:,}", font=FONT_SMALL,
                     bg=COLORS["card"], fg=COLORS["muted"]).pack(side="right")
        tk.Frame(rcard, height=14, bg=COLORS["card"]).pack()

    # ── BOOKING WIZARD ───────────────────────
    def _build_booking(self, parent):
        self._header(parent, "🎫  New Booking", "Complete all steps to reserve your seat")

        # scrollable
        canvas = tk.Canvas(parent, bg=COLORS["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=COLORS["bg"])
        win_id = canvas.create_window((0,0), window=inner, anchor="nw")

        def on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", on_resize)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        pad = dict(padx=32, pady=8)

        # ── Step 1: Passenger Info ──
        s1 = self._card(inner)
        s1.pack(fill="x", **pad)
        tk.Label(s1, text="Step 1 — Passenger Information", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["accent"]).pack(anchor="w", padx=16, pady=(14,4))

        fields_f = tk.Frame(s1, bg=COLORS["card"])
        fields_f.pack(fill="x", padx=16, pady=8)

        tk.Label(fields_f, text="Full Name", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=0,sticky="w",pady=2)
        name_e, name_v = self._entry(fields_f, "e.g. Ahmed Ali", width=30)
        name_e.grid(row=1, column=0, padx=(0,20), ipady=7, sticky="ew")

        tk.Label(fields_f, text="Gmail Address", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=1,sticky="w",pady=2)
        email_e, email_v = self._entry(fields_f, "name@gmail.com", width=30)
        email_e.grid(row=1, column=1, padx=(0,20), ipady=7, sticky="ew")

        tk.Label(fields_f, text="Password (min 5 chars)", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=2,sticky="w",pady=2)
        pw_e, pw_v = self._entry(fields_f, "••••••", width=20)
        pw_e.config(show="*")
        pw_e.grid(row=1, column=2, ipady=7, sticky="ew")

        # ── Step 2: Flight ──
        s2 = self._card(inner)
        s2.pack(fill="x", **pad)
        tk.Label(s2, text="Step 2 — Flight Selection", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["accent"]).pack(anchor="w", padx=16, pady=(14,4))

        flt_f = tk.Frame(s2, bg=COLORS["card"])
        flt_f.pack(fill="x", padx=16, pady=8)

        tk.Label(flt_f, text="Route", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=0,sticky="w")
        route_var = tk.StringVar(value="1 — Lahore → Karachi")
        route_cb = ttk.Combobox(flt_f, textvariable=route_var, width=28,
                                values=[f"{k} — {v['origin']} → {v['destination']}" for k,v in ROUTES.items()],
                                state="readonly")
        route_cb.grid(row=1,column=0,padx=(0,20),ipady=5)

        tk.Label(flt_f, text="Class", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=1,sticky="w")
        class_var = tk.StringVar(value="economy")
        class_cb = ttk.Combobox(flt_f, textvariable=class_var, width=14,
                                values=["economy","business"], state="readonly")
        class_cb.grid(row=1,column=1,padx=(0,20),ipady=5)

        tk.Label(flt_f, text="Flight ID", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=2,sticky="w")
        fid_e, fid_v = self._entry(flt_f, "e.g. 101", width=12)
        fid_e.grid(row=1,column=2,padx=(0,20),ipady=7)

        tk.Label(flt_f, text="Date (DD-MM-YYYY)", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=3,sticky="w")
        date_e, date_v = self._entry(flt_f, datetime.now().strftime("%d-%m-%Y"), width=16)
        date_e.grid(row=1,column=3,ipady=7)

        tk.Label(flt_f, text="Number of Seats", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=2,column=0,sticky="w",pady=(12,2))
        qty_var = tk.IntVar(value=1)
        qty_spin = tk.Spinbox(flt_f, from_=1, to=10, textvariable=qty_var,
                              font=FONT_BODY, bg=COLORS["input_bg"], fg=COLORS["text"],
                              relief="flat", width=6)
        qty_spin.grid(row=3,column=0,padx=(0,20),ipady=5)

        price_lbl = tk.Label(flt_f, text="Price per seat: Rs.15,000", font=FONT_BODY,
                              bg=COLORS["card"], fg=COLORS["success"])
        price_lbl.grid(row=3,column=1,columnspan=2,sticky="w")

        total_lbl = tk.Label(flt_f, text="Total: Rs.15,000", font=("Segoe UI",13,"bold"),
                             bg=COLORS["card"], fg=COLORS["warning"])
        total_lbl.grid(row=3,column=3,sticky="w")

        def update_price(*_):
            rk = int(route_var.get().split()[0])
            cl = class_var.get()
            pp = ROUTES[rk][cl]
            qty = qty_var.get()
            price_lbl.config(text=f"Price per seat: Rs.{pp:,}")
            total_lbl.config(text=f"Total: Rs.{pp*qty:,}")
        route_cb.bind("<<ComboboxSelected>>", update_price)
        class_cb.bind("<<ComboboxSelected>>", update_price)
        qty_spin.config(command=update_price)

        # ── Step 3: Seat Selection ──
        s3 = self._card(inner)
        s3.pack(fill="x", **pad)
        tk.Label(s3, text="Step 3 — Select Your Seats", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["accent"]).pack(anchor="w", padx=16, pady=(14,4))

        seat_info = tk.Label(s3, text="Choose seats from the map below  (grey = taken, click to select)",
                             font=FONT_SMALL, bg=COLORS["card"], fg=COLORS["muted"])
        seat_info.pack(anchor="w", padx=16)

        mini_map = tk.Frame(s3, bg=COLORS["card"])
        mini_map.pack(padx=16, pady=10)

        selected_seats = []
        seat_btns = {}
        global_booked = get_global_booked_seats()

        def refresh_mini_map():
            for w in mini_map.winfo_children():
                w.destroy()
            selected_seats.clear()
            seat_btns.clear()
            gb = get_global_booked_seats()
            for i in range(1, 51):
                row_n = (i-1)//10
                col_n = (i-1)%10
                if i in gb:
                    color = COLORS["muted"]
                    state = "disabled"
                else:
                    color = COLORS["border"]
                    state = "normal"
                b = tk.Button(mini_map, text=str(i), width=3, font=FONT_SMALL,
                              bg=color, fg=COLORS["text"], relief="flat",
                              state=state, cursor="hand2",
                              command=lambda n=i: toggle_seat(n))
                b.grid(row=row_n, column=col_n, padx=1, pady=1)
                seat_btns[i] = b

        def toggle_seat(n):
            qty = qty_var.get()
            if n in selected_seats:
                selected_seats.remove(n)
                seat_btns[n].config(bg=COLORS["border"])
            else:
                if len(selected_seats) >= qty:
                    messagebox.showwarning("Limit", f"You can only select {qty} seat(s).")
                    return
                selected_seats.append(n)
                seat_btns[n].config(bg=COLORS["success"])

        refresh_mini_map()

        # ── Step 4: Payment ──
        s4 = self._card(inner)
        s4.pack(fill="x", **pad)
        tk.Label(s4, text="Step 4 — Payment Method", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["accent"]).pack(anchor="w", padx=16, pady=(14,4))

        pay_var = tk.StringVar(value="Credit Card")
        pay_f = tk.Frame(s4, bg=COLORS["card"])
        pay_f.pack(fill="x", padx=16, pady=8)
        for pm in ["Credit Card","Cash","JazzCash"]:
            rb = tk.Radiobutton(pay_f, text=pm, variable=pay_var, value=pm,
                                font=FONT_BODY, bg=COLORS["card"], fg=COLORS["text"],
                                activebackground=COLORS["card"],
                                selectcolor=COLORS["accent"])
            rb.pack(side="left", padx=16)

        # ── Confirm button ──
        btn_f = tk.Frame(inner, bg=COLORS["bg"])
        btn_f.pack(fill="x", padx=32, pady=(8,24))

        def confirm_booking():
            # validation
            name = name_v.get().strip()
            email = email_v.get().strip()
            password = pw_v.get().strip()

            if not name or name in ("e.g. Ahmed Ali",):
                messagebox.showerror("Error","Please enter your name"); return
            if not name.replace(" ","").isalpha():
                messagebox.showerror("Error","Name must contain only letters"); return
            if "@gmail.com" not in email:
                messagebox.showerror("Error","Please enter a valid Gmail address"); return
            if len(password) < 5:
                messagebox.showerror("Error","Password must be at least 5 characters"); return
            if not fid_v.get().strip().isdigit():
                messagebox.showerror("Error","Enter a valid numeric Flight ID"); return
            qty = qty_var.get()
            if len(selected_seats) != qty:
                messagebox.showerror("Error",f"Please select exactly {qty} seat(s). You've selected {len(selected_seats)}."); return

            rk = int(route_var.get().split()[0])
            cl = class_var.get()
            route = ROUTES[rk]
            price_per = route[cl]
            total = price_per * qty

            b = Booking(name, email, password,
                        int(fid_v.get()), route["origin"], route["destination"],
                        date_v.get(), cl, qty, total)
            b._booked_seats_list = selected_seats[:]
            for s in selected_seats:
                Flight.booked_seats.append(s)

            pm = pay_var.get()
            pmap = {"Credit Card": CreditCardPayment, "Cash": CashPayment, "JazzCash": JazzCashPayment}
            payment = pmap[pm](total)

            pid = register_passenger(name, email, password)
            save_booking(b, pid, selected_seats[:], pm)

            msg = (f"Booking Confirmed!\n\n"
                   f"Booking ID : #{b.booking_id}\n"
                   f"Passenger  : {name}\n"
                   f"Route      : {route['origin']} → {route['destination']}\n"
                   f"Class      : {cl.title()}\n"
                   f"Seats      : {selected_seats}\n"
                   f"Payment    : {payment.make_payment()}")
            messagebox.showinfo("✅ Booking Confirmed", msg)
            self.show_page("bookings")

        self._btn(btn_f, "✅  Confirm Booking", confirm_booking,
                  color=COLORS["success"]).pack(side="left", padx=(0,12))
        self._btn(btn_f, "🔄  Reset Form",
                  lambda: self.show_page("book"),
                  color=COLORS["muted"]).pack(side="left")

    # ── ALL BOOKINGS ─────────────────────────
    def _build_all_bookings(self, parent):
        self._header(parent, "📋  All Bookings", "View, manage and cancel reservations")

        # search bar
        sf = tk.Frame(parent, bg=COLORS["bg"])
        sf.pack(fill="x", padx=32, pady=12)
        search_e, search_v = self._entry(sf, "Search by name, route, ID...", width=36)
        search_e.pack(side="left", ipady=7)
        self._btn(sf, "Search", lambda: load_table(search_v.get()), COLORS["accent"]).pack(side="left", padx=8)
        self._btn(sf, "Show All", lambda: load_table(""), COLORS["muted"]).pack(side="left")

        # table
        cols = ("ID","Passenger","Email","Route","Class","Seats","Total","Payment","Status","Date")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
                        background=COLORS["card"], fieldbackground=COLORS["card"],
                        foreground=COLORS["text"], rowheight=32,
                        font=FONT_BODY)
        style.configure("Custom.Treeview.Heading",
                        background=COLORS["panel"], foreground=COLORS["muted"],
                        font=FONT_SMALL)
        style.map("Custom.Treeview", background=[("selected", COLORS["accent"])])

        tree_f = tk.Frame(parent, bg=COLORS["bg"])
        tree_f.pack(fill="both", expand=True, padx=32, pady=(0,8))

        tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                            style="Custom.Treeview", selectmode="browse")
        widths = [60,120,160,160,80,80,100,110,80,100]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=40, anchor="center")

        vsb = ttk.Scrollbar(tree_f, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_f, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)

        def load_table(q=""):
            for r in tree.get_children():
                tree.delete(r)
            bookings = get_all_bookings()
            for b in bookings:
                route = f"{b['origin']} → {b['destination']}"
                if q and q.lower() not in (b['name']+route+str(b['booking_id'])+b['status']).lower():
                    continue
                tag = "active" if b["status"]=="Active" else "cancelled"
                tree.insert("","end", iid=str(b["booking_id"]),
                            values=(f"#{b['booking_id']}", b['name'], b['email'],
                                    route, b['class'].title(), b['booked_seats'],
                                    f"Rs.{b['total_price']:,}", b['payment_method'],
                                    b['status'], b['created_at'][:10]),
                            tags=(tag,))
            tree.tag_configure("active",    foreground=COLORS["text"])
            tree.tag_configure("cancelled", foreground=COLORS["muted"])

        load_table()

        # cancel button
        def cancel_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select","Please select a booking first"); return
            bid = int(sel[0].replace("#",""))
            if messagebox.askyesno("Cancel Booking", f"Cancel booking #{bid}?"):
                cancel_booking_db(bid)
                Flight.booked_seats = get_global_booked_seats()
                load_table(search_v.get())
                messagebox.showinfo("Done", f"Booking #{bid} cancelled.")

        btn_row = tk.Frame(parent, bg=COLORS["bg"])
        btn_row.pack(fill="x", padx=32, pady=(0,16))
        self._btn(btn_row, "❌  Cancel Selected Booking", cancel_selected,
                  color=COLORS["danger"]).pack(side="left")
        self._btn(btn_row, "🔄  Refresh", lambda: load_table(""),
                  color=COLORS["muted"]).pack(side="left", padx=8)

    # ── SEAT MAP ─────────────────────────────
    def _build_seat_map(self, parent):
        self._header(parent, "💺  Seat Map", "Live view of all 50 seats")

        legend_f = tk.Frame(parent, bg=COLORS["bg"])
        legend_f.pack(fill="x", padx=32, pady=(12,4))
        for color, label in [(COLORS["success"],"Available"),(COLORS["danger"],"Booked")]:
            sq = tk.Frame(legend_f, bg=color, width=14, height=14)
            sq.pack(side="left")
            tk.Label(legend_f, text=f"  {label}    ", font=FONT_SMALL,
                     bg=COLORS["bg"], fg=COLORS["muted"]).pack(side="left")

        map_outer = self._card(parent)
        map_outer.pack(padx=32, pady=8)

        grid_f = tk.Frame(map_outer, bg=COLORS["card"])
        grid_f.pack(padx=24, pady=20)

        booked = set(get_global_booked_seats())
        tk.Label(grid_f, text="   FRONT OF AIRCRAFT   ", font=FONT_SMALL,
                 bg=COLORS["card"], fg=COLORS["muted"]).grid(row=0,column=0,columnspan=11,pady=(0,10))

        for row_n in range(5):
            tk.Label(grid_f, text=f"Row {row_n+1}", font=FONT_SMALL,
                     bg=COLORS["card"], fg=COLORS["muted"]).grid(row=row_n+1, column=0, padx=(0,8))
            for col_n in range(10):
                seat_n = row_n*10 + col_n + 1
                color = COLORS["danger"] if seat_n in booked else COLORS["success"]
                lbl = tk.Label(grid_f, text=str(seat_n), width=4, font=FONT_SMALL,
                               bg=color, fg="white", relief="flat")
                lbl.grid(row=row_n+1, column=col_n+1, padx=2, pady=2, ipady=5)
                if (col_n+1) % 3 == 0 and col_n < 9:
                    tk.Label(grid_f, text=" ", bg=COLORS["card"]).grid(row=row_n+1, column=col_n+2)

        avail = 50 - len(booked)
        tk.Label(map_outer, text=f"Available: {avail} / 50", font=FONT_BODY,
                 bg=COLORS["card"], fg=COLORS["success"]).pack(pady=(0,16))

        self._btn(map_outer, "🔄  Refresh", lambda: self.show_page("seats"),
                  color=COLORS["accent"]).pack(pady=(0,16))

    # ── ADMIN ────────────────────────────────
    def _build_admin(self, parent):
        self._header(parent, "⚙️  Admin Panel", "System management — Ali (admin123)")

        af = tk.Frame(parent, bg=COLORS["bg"])
        af.pack(fill="x", padx=32, pady=16)
        af.columnconfigure((0,1), weight=1)

        # add flight card
        fc = self._card(af)
        fc.grid(row=0,column=0,padx=(0,10),sticky="nsew")
        tk.Label(fc, text="Add New Flight", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(14,4))

        fl_f = tk.Frame(fc, bg=COLORS["card"])
        fl_f.pack(fill="x", padx=16, pady=8)
        fields = [("Flight ID","e.g. 201"),("Origin","City"),("Destination","City"),("Date","DD-MM-YYYY")]
        entries = {}
        for i,(lbl,ph) in enumerate(fields):
            tk.Label(fl_f, text=lbl, font=FONT_SMALL,
                     bg=COLORS["card"], fg=COLORS["muted"]).grid(row=i*2,column=0,sticky="w",pady=(6,1))
            e,v = self._entry(fl_f, ph, width=28)
            e.grid(row=i*2+1,column=0,ipady=7,sticky="ew")
            entries[lbl] = v

        def add_flight():
            admin = Admin("Ali","admin123")
            admin.add_flight()
            messagebox.showinfo("Admin", f"Flight '{entries['Flight ID'].get()}' added successfully!\n{admin.admin_detail()}")

        self._btn(fc, "➕  Add Flight", add_flight, COLORS["accent"]).pack(anchor="w", padx=16, pady=(8,16))

        # stats card
        sc = self._card(af)
        sc.grid(row=0,column=1,padx=(10,0),sticky="nsew")
        tk.Label(sc, text="System Statistics", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(14,4))

        stats = get_stats()
        stat_rows = [
            ("Total Bookings",   stats["total"]),
            ("Active Bookings",  stats["active"]),
            ("Total Passengers", stats["passengers"]),
            ("Seats Booked",     len(get_global_booked_seats())),
            ("Seats Available",  50 - len(get_global_booked_seats())),
            ("Total Revenue",    f"Rs.{stats['revenue']:,}"),
        ]
        for label, val in stat_rows:
            row = tk.Frame(sc, bg=COLORS["card"])
            row.pack(fill="x", padx=16, pady=5)
            tk.Label(row, text=label, font=FONT_SMALL,
                     bg=COLORS["card"], fg=COLORS["muted"]).pack(side="left")
            tk.Label(row, text=str(val), font=("Segoe UI",11,"bold"),
                     bg=COLORS["card"], fg=COLORS["text"]).pack(side="right")
        tk.Frame(sc, height=14, bg=COLORS["card"]).pack()

        # export
        ex_card = self._card(af)
        ex_card.grid(row=1,column=0,columnspan=2,pady=(12,0),sticky="ew")
        tk.Label(ex_card, text="Export Data", font=FONT_TITLE,
                 bg=COLORS["card"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(14,4))

        def export_csv():
            import csv
            bookings = get_all_bookings()
            fname = f"bookings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(fname, "w", newline="") as f:
                if bookings:
                    w = csv.DictWriter(f, fieldnames=bookings[0].keys())
                    w.writeheader()
                    w.writerows(bookings)
            messagebox.showinfo("Export", f"Data exported to:\n{fname}")

        self._btn(ex_card, "📥  Export Bookings to CSV", export_csv,
                  color=COLORS["accent2"]).pack(anchor="w", padx=16, pady=(4,16))


if __name__ == "__main__":
    app = AirlineApp()
    app.mainloop()