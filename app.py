# app.py — Study Spot
import os
import sqlite3
import random
import string
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Flask, render_template, request, jsonify, redirect, url_for,
                   session, flash, abort, g)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "study_spot.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

# ---------------------------------------------------------------- constants
SLOTS = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
AMENITIES = ["wifi", "outlets", "quiet", "food", "printing", "whiteboard"]
SEATS = [("window", "Window seat"), ("booth", "Booth"),
         ("table", "Shared table"), ("silent", "Silent room")]
CANCEL_CUTOFF_HOURS = 2

# ---------------------------------------------------------------- db helpers
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  notify_email INTEGER NOT NULL DEFAULT 1,
  public_profile INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS spots(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, type TEXT, icon TEXT, address TEXT, walk TEXT,
  distance REAL, price REAL DEFAULT 0,
  requires_payment INTEGER DEFAULT 0, auto_confirm INTEGER DEFAULT 1,
  capacity INTEGER DEFAULT 6, open INTEGER DEFAULT 1,
  rating REAL DEFAULT 0, reviews INTEGER DEFAULT 0,
  tags TEXT, description TEXT, lat REAL, lng REAL,
  status TEXT DEFAULT 'published');

CREATE TABLE IF NOT EXISTS favorites(
  user_id INTEGER NOT NULL, spot_id INTEGER NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(user_id, spot_id));

CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL, spot_id INTEGER NOT NULL,
  date TEXT NOT NULL, time TEXT NOT NULL, party INTEGER NOT NULL,
  seat TEXT, price REAL DEFAULT 0, status TEXT NOT NULL,
  code TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL, spot_id INTEGER NOT NULL,
  rating INTEGER NOT NULL, noise INTEGER, wifi INTEGER, outlets INTEGER,
  body TEXT, photo TEXT, status TEXT DEFAULT 'published',
  created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, review_id INTEGER NOT NULL,
  user_id INTEGER, reason TEXT, resolved INTEGER DEFAULT 0, created_at TEXT);

CREATE TABLE IF NOT EXISTS spot_suggestions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
  name TEXT NOT NULL, address TEXT, notes TEXT,
  status TEXT DEFAULT 'pending', created_at TEXT);

CREATE TABLE IF NOT EXISTS study_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
  minutes INTEGER NOT NULL, started_at TEXT NOT NULL);
"""

# Coordinates updated to real locations (London area) for the map to render properly.
SEED_SPOTS = [
    dict(name="The Workshop Coffee", type="Cafe", icon="fa-mug-hot",
         address="27 Ngo Duc Ke, Hoan Kiem", walk="0.4 mi", distance=0.4,
         price=0, requires_payment=0, auto_confirm=1, capacity=40, open=1,
         rating=4.8, reviews=512, tags="wifi,outlets,quiet",
         description="Located on the top floor of an old building, this spacious loft cafe is famous for its high ceilings, huge tables, and laptop-friendly policy.",
         lat=21.0288, lng=105.8518),
    dict(name="National Library of Vietnam", type="Library", icon="fa-book",
         address="31 Trang Thi, Hoan Kiem", walk="0.6 mi", distance=0.6,
         price=0, requires_payment=0, auto_confirm=1, capacity=200, open=1,
         rating=4.7, reviews=318, tags="quiet,printing,free,wifi",
         description="A stunning colonial-era building with vast reading rooms, a massive collection of literature, and the absolute quietest study environment.",
         lat=21.02601, lng=105.84922),
    dict(name="Work-It Coworking Space", type="Study Space", icon="fa-laptop",
         address="14 Ngo Quyen, Hoan Kiem", walk="0.8 mi", distance=0.8,
         price=5.0, requires_payment=1, auto_confirm=1, capacity=80, open=1,
         rating=4.9, reviews=145, tags="wifi,outlets,quiet,whiteboard",
         description="A modern, professional coworking space right in the city center. Perfect for deep work, with ergonomic chairs and lightning-fast wifi.",
         lat=21.0252, lng=105.8511),
    dict(name="Tranquil Books & Coffee", type="Cafe", icon="fa-mug-saucer",
         address="5 Nguyen Quang Bich, Hoan Kiem", walk="0.5 mi", distance=0.5,
         price=1.5, requires_payment=1, auto_confirm=1, capacity=25, open=1,
         rating=4.8, reviews=420, tags="wifi,quiet,food,scenic",
         description="A hushed, book-lined library cafe tucked in an Old Quarter alley. Built for reading, writing, and deep focus with excellent jazz music.",
         lat=21.0325, lng=105.8456),
    dict(name="Hanoi University of Science and Technology (HUST)", type="Study Space", icon="fa-graduation-cap",
         address="1 Dai Co Viet, Hai Ba Trung", walk="1.8 mi", distance=1.8,
         price=0, requires_payment=0, auto_confirm=1, capacity=300, open=1,
         rating=4.7, reviews=560, tags="wifi,quiet,outlets",
         description="A top technical university with sprawling campuses, multiple campus libraries, and many quiet corners for students to cram.",
         lat=21.00639, lng=105.84306),
    dict(name="The Coffee House - Hai Ba Trung", type="Cafe", icon="fa-mug-hot",
         address="23M Hai Ba Trung, Hoan Kiem", walk="0.7 mi", distance=0.7,
         price=0, requires_payment=0, auto_confirm=1, capacity=50, open=1,
         rating=4.4, reviews=210, tags="wifi,outlets,quiet,food",
         description="A modern, spacious cafe chain famous among local students for its reliable wifi, air conditioning, and comfortable seating.",
         lat=21.024, lng=105.8531),
    dict(name="Toong Coworking Space", type="Study Space", icon="fa-building",
         address="8 Trang Thi, Hoan Kiem", walk="0.6 mi", distance=0.6,
         price=6.0, requires_payment=1, auto_confirm=0, capacity=60, open=1,
         rating=4.6, reviews=92, tags="wifi,outlets,quiet,printing",
         description="An upscale, boutique coworking space with beautiful Indochine architecture. Includes free tea, coffee, and private phone booths.",
         lat=21.0257, lng=105.8500),
    dict(name="Cong Caphe (Trieu Viet Vuong)", type="Cafe", icon="fa-mug-saucer",
         address="152D Trieu Viet Vuong, Hai Ba Trung", walk="1.2 mi", distance=1.2,
         price=2.0, requires_payment=1, auto_confirm=1, capacity=40, open=1,
         rating=4.5, reviews=380, tags="wifi,food,outlets",
         description="The original location of this nostalgic, Communist-kitsch cafe chain. Great for a focused afternoon with a coconut coffee.",
         lat=21.0191, lng=105.8490),
]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) c FROM spots").fetchone()["c"] == 0:
        for s in SEED_SPOTS:
            db.execute(
                """INSERT INTO spots(name,type,icon,address,walk,distance,price,
                   requires_payment,auto_confirm,capacity,open,rating,reviews,
                   tags,description,lat,lng,status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'published')""",
                (s["name"], s["type"], s["icon"], s["address"], s["walk"],
                 s["distance"], s["price"], s["requires_payment"],
                 s["auto_confirm"], s["capacity"], s["open"], s["rating"],
                 s["reviews"], s["tags"], s["description"], s["lat"], s["lng"]))
    if db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        db.execute(
            "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
            ("Site Admin", "admin@studyspot.dev",
             generate_password_hash("admin123"), "admin", datetime.utcnow().isoformat()))
    db.commit()
    db.close()

# ---------------------------------------------------------------- auth
def current_user():
    if "current_user" not in g:
        uid = session.get("user_id")
        g.current_user = (get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                          if uid else None)
    return g.current_user

def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not current_user():
            if request.path.startswith("/api/"):
                return jsonify({"error": "auth", "message": "Log in required"}), 401
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*a, **kw)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        u = current_user()
        if not u or u["role"] != "admin":
            abort(403)
        return view(*a, **kw)
    return wrapped

@app.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "AMENITIES": AMENITIES,
        "SEATS": SEATS,
        "today": date.today().isoformat(),
    }

# ---------------------------------------------------------------- helpers
def spot_or_404(spot_id):
    spot = get_db().execute("SELECT * FROM spots WHERE id=?", (spot_id,)).fetchone()
    if not spot:
        abort(404)
    return spot

def slot_availability(spot, day):
    rows = get_db().execute(
        """SELECT time, COUNT(*) n FROM bookings
           WHERE spot_id=? AND date=? AND status IN ('confirmed','pending')
           GROUP BY time""", (spot["id"], day)).fetchall()
    taken = {r["time"]: r["n"] for r in rows}
    out = []
    for t in SLOTS:
        left = max(spot["capacity"] - taken.get(t, 0), 0)
        out.append({"time": t, "remaining": left, "full": left == 0})
    return out

def booking_dt(b):
    return datetime.strptime(f"{b['date']} {b['time']}", "%Y-%m-%d %H:%M")

def favorite_ids():
    u = current_user()
    if not u:
        return set()
    return {r["spot_id"] for r in get_db().execute(
        "SELECT spot_id FROM favorites WHERE user_id=?", (u["id"],))}

def new_code():
    return "SS-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

# ---------------------------------------------------------------- home
@app.route("/")
def home():
    db = get_db()
    featured = db.execute(
        "SELECT * FROM spots WHERE status='published' ORDER BY rating DESC LIMIT 3").fetchall()
    nearby = db.execute(
        "SELECT * FROM spots WHERE status='published' ORDER BY distance ASC LIMIT 3").fetchall()
    review_feed = db.execute(
        """SELECT r.*, u.name uname, s.name sname FROM reviews r
           JOIN users u ON u.id=r.user_id JOIN spots s ON s.id=r.spot_id
           WHERE r.status='published' ORDER BY r.id DESC LIMIT 3""").fetchall()
    return render_template("index.html", featured=featured, nearby=nearby,
                           review_feed=review_feed, favs=favorite_ids())

# ---------------------------------------------------------------- find spots
@app.route("/spots")
def spots():
    db = get_db()
    all_spots = db.execute("SELECT * FROM spots WHERE status='published'").fetchall()
    q = request.args.get("q", "").strip().lower()
    ftype = request.args.get("type", "")
    amen = request.args.getlist("amenity")
    max_dist = request.args.get("max_distance", "")
    sort = request.args.get("sort", "distance")
    view = request.args.get("view", "list")

    result = []
    for s in all_spots:
        tags = (s["tags"] or "").split(",")
        if q and q not in s["name"].lower() and q not in (s["address"] or "").lower() \
                and q not in (s["type"] or "").lower():
            continue
        if ftype and s["type"] != ftype:
            continue
        if amen and not all(a in tags for a in amen):
            continue
        if max_dist:
            try:
                if s["distance"] > float(max_dist):
                    continue
            except ValueError:
                pass
        result.append(s)

    if sort == "rating":
        result.sort(key=lambda s: s["rating"], reverse=True)
    elif sort == "reviews":
        result.sort(key=lambda s: s["reviews"], reverse=True)
    else:
        result.sort(key=lambda s: s["distance"])

    types = sorted({s["type"] for s in all_spots})

    # Row → dict for JSON serialization (map needs a plain dict list)
    spots_map = [
        {
            "id": s["id"],
            "name": s["name"],
            "type": s["type"],
            "walk": s["walk"],
            "rating": s["rating"],
            "reviews": s["reviews"],
            "lat": s["lat"],
            "lng": s["lng"],
        }
        for s in result
    ]

    return render_template(
        "spots.html",
        spots=result,
        spots_map=spots_map,
        types=types,
        q=q,
        ftype=ftype,
        amen=amen,
        max_dist=max_dist,
        sort=sort,
        view=view,
        favs=favorite_ids(),
    )

@app.route("/spots/<int:spot_id>")
def spot_detail(spot_id):
    db = get_db()
    spot = spot_or_404(spot_id)
    reviews = db.execute(
        """SELECT r.*, u.name uname FROM reviews r JOIN users u ON u.id=r.user_id
           WHERE r.spot_id=? AND r.status='published' ORDER BY r.id DESC""",
        (spot_id,)).fetchall()
    avg = db.execute(
        """SELECT AVG(rating) a, AVG(noise) n, AVG(wifi) w, AVG(outlets) o
           FROM reviews WHERE spot_id=? AND status='published'""", (spot_id,)).fetchone()
    availability = slot_availability(spot, date.today().isoformat())
    mine = db.execute(
        """SELECT id FROM reviews WHERE spot_id=? AND user_id=?""",
        (spot_id, current_user()["id"] if current_user() else -1)).fetchone()
    return render_template("spot_detail.html", spot=spot, reviews=reviews,
                           avg=avg, availability=availability,
                           favs=favorite_ids(), already_reviewed=bool(mine),
                           today=date.today().isoformat())

# ---------------------------------------------------------------- booking
@app.route("/spots/<int:spot_id>/book", methods=["GET", "POST"])
@login_required
def book_spot(spot_id):
    spot = spot_or_404(spot_id)
    day = request.values.get("date") or date.today().isoformat()
    availability = slot_availability(spot, day)

    if request.method == "POST":
        time_ = request.form.get("time", "")
        party = request.form.get("party", "1")
        seat = request.form.get("seat", "table")

        errors = []
        try:
            if datetime.strptime(day, "%Y-%m-%d").date() < date.today():
                errors.append("Pick a date from today onwards.")
        except ValueError:
            errors.append("Invalid date.")
        if time_ not in SLOTS:
            errors.append("Choose a valid time slot.")
        try:
            party_n = max(1, min(int(party), spot["capacity"]))
        except ValueError:
            party_n = 1
            errors.append("Invalid party size.")
        if not errors:
            slot = next(s for s in slot_availability(spot, day) if s["time"] == time_)
            if slot["full"]:
                errors.append(f"The {time_} slot is fully booked.")
            if party_n > slot["remaining"]:
                errors.append(f"Only {slot['remaining']} seat(s) left at {time_}.")

        if spot["requires_payment"] and not request.form.get("card_number"):
            errors.append("Payment details are required for this venue.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("book.html", spot=spot, day=day,
                                   availability=availability, favs=favorite_ids()), 400

        total = round(spot["price"] * party_n, 2)
        status = "confirmed" if spot["auto_confirm"] else "pending"
        code = new_code()
        cur = get_db().execute(
            """INSERT INTO bookings(user_id,spot_id,date,time,party,seat,price,
               status,code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (current_user()["id"], spot["id"], day, time_, party_n, seat,
             total, status, code, datetime.utcnow().isoformat()))
        get_db().commit()
        return redirect(url_for("booking_confirmation", booking_id=cur.lastrowid))

    return render_template("book.html", spot=spot, day=day,
                           availability=availability, favs=favorite_ids())

@app.route("/bookings/<int:booking_id>/confirmation")
@login_required
def booking_confirmation(booking_id):
    b = get_db().execute(
        """SELECT b.*, s.name sname, s.address saddress, s.icon sicon
           FROM bookings b JOIN spots s ON s.id=b.spot_id
           WHERE b.id=? AND b.user_id=?""",
        (booking_id, current_user()["id"])).fetchone()
    if not b:
        abort(404)
    return render_template("booking_confirmation.html", b=b)

@app.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    db = get_db()
    b = db.execute("SELECT * FROM bookings WHERE id=? AND user_id=?",
                   (booking_id, current_user()["id"])).fetchone()
    if not b:
        abort(404)
    if b["status"] == "cancelled":
        flash("That booking is already cancelled.", "error")
    elif booking_dt(b) - datetime.now() < timedelta(hours=CANCEL_CUTOFF_HOURS):
        flash(f"Cancellation closes {CANCEL_CUTOFF_HOURS}h before the session. "
              "Please contact the venue.", "error")
    else:
        db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
        db.commit()
        flash("Booking cancelled. Your seat has been released.", "success")
    return redirect(request.referrer or url_for("account_bookings"))

@app.route("/api/availability/<int:spot_id>")
def api_availability(spot_id):
    spot = spot_or_404(spot_id)
    day = request.args.get("date") or date.today().isoformat()
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "bad date"}), 400
    return jsonify({"date": day, "slots": slot_availability(spot, day)})

# ---------------------------------------------------------------- favorites
@app.route("/favorites")
def favorites():
    u = current_user()
    if not u:
        return render_template("favorites.html", spots=[], favs=set(), guest=True)
    rows = get_db().execute(
        """SELECT s.* FROM favorites f JOIN spots s ON s.id=f.spot_id
           WHERE f.user_id=? ORDER BY f.created_at DESC""", (u["id"],)).fetchall()
    return render_template("favorites.html", spots=rows, favs=favorite_ids(),
                           guest=False)

@app.route("/api/favorite/<int:spot_id>", methods=["POST"])
def api_toggle_favorite(spot_id):
    u = current_user()
    if not u:
        return jsonify({"error": "auth", "message": "Log in to save favorites"}), 401
    spot_or_404(spot_id)
    db = get_db()
    row = db.execute("SELECT 1 FROM favorites WHERE user_id=? AND spot_id=?",
                     (u["id"], spot_id)).fetchone()
    if row:
        db.execute("DELETE FROM favorites WHERE user_id=? AND spot_id=?",
                   (u["id"], spot_id))
        state = False
    else:
        db.execute("INSERT INTO favorites(user_id,spot_id,created_at) VALUES(?,?,?)",
                   (u["id"], spot_id, datetime.utcnow().isoformat()))
        state = True
    db.commit()
    return jsonify({"favorited": state, "spot_id": spot_id})

@app.route("/api/favorites")
def api_favorites():
    return jsonify({"favorites": sorted(favorite_ids())})

# ---------------------------------------------------------------- companion
@app.route("/companion")
def companion():
    u = current_user()
    history = []
    total = 0
    if u:
        rows = get_db().execute(
            "SELECT * FROM study_sessions WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (u["id"],)).fetchall()
        history = rows
        total = get_db().execute(
            "SELECT COALESCE(SUM(minutes),0) t FROM study_sessions WHERE user_id=?",
            (u["id"],)).fetchone()["t"]
    return render_template("companion.html", history=history, total=total)

@app.route("/api/study-session", methods=["POST"])
@login_required
def api_study_session():
    data = request.get_json(silent=True) or {}
    try:
        minutes = int(data.get("minutes", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "bad payload"}), 400
    if minutes <= 0 or minutes > 600:
        return jsonify({"error": "minutes out of range"}), 400
    get_db().execute(
        "INSERT INTO study_sessions(user_id,minutes,started_at) VALUES(?,?,?)",
        (current_user()["id"], minutes, datetime.utcnow().isoformat()))
    get_db().commit()
    return jsonify({"ok": True, "minutes": minutes})

# ---------------------------------------------------------------- reviews
@app.route("/reviews")
def reviews():
    db = get_db()
    q = request.args.get("q", "").strip().lower()
    spot_id = request.args.get("spot_id", "")
    sort = request.args.get("sort", "new")
    min_rating = request.args.get("min_rating", "")

    sql = """SELECT r.*, u.name uname, s.name sname, s.id sid
             FROM reviews r JOIN users u ON u.id=r.user_id
             JOIN spots s ON s.id=r.spot_id WHERE r.status='published'"""
    params = []
    if spot_id:
        sql += " AND r.spot_id=?"
        params.append(spot_id)
    if min_rating:
        sql += " AND r.rating>=?"
        params.append(min_rating)
    sql += " ORDER BY r.rating DESC" if sort == "rating" else " ORDER BY r.id DESC"
    rows = db.execute(sql, params).fetchall()

    if q:
        rows = [r for r in rows
                if q in (r["body"] or "").lower() or q in r["sname"].lower()
                or q in r["uname"].lower()]

    all_spots = db.execute("SELECT id,name FROM spots ORDER BY name").fetchall()
    return render_template("reviews.html", reviews=rows, all_spots=all_spots,
                           q=q, spot_id=spot_id, sort=sort, min_rating=min_rating)

@app.route("/spots/<int:spot_id>/review", methods=["GET", "POST"])
@login_required
def write_review(spot_id):
    spot = spot_or_404(spot_id)
    if request.method == "POST":
        try:
            rating = int(request.form.get("rating", 0))
        except ValueError:
            rating = 0
        if rating not in (1, 2, 3, 4, 5):
            flash("Pick a star rating from 1 to 5.", "error")
            return redirect(url_for("write_review", spot_id=spot_id))
        body = (request.form.get("body") or "").strip()
        if len(body) < 20:
            flash("Please write at least 20 characters so it helps others.", "error")
            return redirect(url_for("write_review", spot_id=spot_id))

        def num(field):
            try:
                return max(1, min(int(request.form.get(field, 3)), 5))
            except ValueError:
                return 3

        db = get_db()
        db.execute(
            """INSERT INTO reviews(user_id,spot_id,rating,noise,wifi,outlets,
               body,photo,status,created_at) VALUES(?,?,?,?,?,?,?,?,'published',?)""",
            (current_user()["id"], spot_id, rating, num("noise"), num("wifi"),
             num("outlets"), body, request.form.get("photo") or None,
             datetime.utcnow().isoformat()))
        new_count = spot["reviews"] + 1
        new_rating = round((spot["rating"] * spot["reviews"] + rating) / new_count, 2)
        db.execute("UPDATE spots SET rating=?, reviews=? WHERE id=?",
                   (new_rating, new_count, spot_id))
        db.commit()
        flash("Thanks! Your review is live.", "success")
        return redirect(url_for("spot_detail", spot_id=spot_id))

    return render_template("review_form.html", spot=spot)

@app.route("/reviews/suggest", methods=["POST"])
@login_required
def suggest_spot():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Tell us the name of the place.", "error")
        return redirect(url_for("reviews"))
    get_db().execute(
        """INSERT INTO spot_suggestions(user_id,name,address,notes,status,created_at)
           VALUES(?,?,?,?,'pending',?)""",
        (current_user()["id"], name, request.form.get("address"),
         request.form.get("notes"), datetime.utcnow().isoformat()))
    get_db().commit()
    flash("Suggestion received — an admin will review it.", "success")
    return redirect(url_for("reviews"))

@app.route("/api/report/<int:review_id>", methods=["POST"])
@login_required
def api_report(review_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM reviews WHERE id=?", (review_id,)).fetchone():
        return jsonify({"error": "not found"}), 404
    db.execute("INSERT INTO reports(review_id,user_id,reason,created_at) VALUES(?,?,?,?)",
               (review_id, current_user()["id"],
                (request.form.get("reason") or "inappropriate"),
                datetime.utcnow().isoformat()))
    db.commit()
    return jsonify({"ok": True})

# ---------------------------------------------------------------- account
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], pw):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}!", "success")
            nxt = request.form.get("next") or request.args.get("next")
            return redirect(nxt if nxt and nxt.startswith("/") else url_for("home"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html", next=request.args.get("next", ""))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        errors = []
        if len(name) < 2:
            errors.append("Enter your name.")
        if "@" not in email or "." not in email:
            errors.append("Enter a valid email.")
        if len(pw) < 6:
            errors.append("Password needs at least 6 characters.")
        if not errors and get_db().execute(
                "SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            errors.append("That email is already registered.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("signup.html", name=name, email=email), 400
        cur = get_db().execute(
            "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'user',?)",
            (name, email, generate_password_hash(pw), datetime.utcnow().isoformat()))
        get_db().commit()
        session["user_id"] = cur.lastrowid
        flash("Account created — welcome to Study Spot!", "success")
        return redirect(url_for("home"))
    return render_template("signup.html", name="", email="")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    u = current_user()
    if request.method == "POST":
        name = (request.form.get("name") or u["name"]).strip()
        notify = 1 if request.form.get("notify_email") else 0
        public = 1 if request.form.get("public_profile") else 0
        get_db().execute(
            "UPDATE users SET name=?, notify_email=?, public_profile=? WHERE id=?",
            (name, notify, public, u["id"]))
        get_db().commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account"))
    stats = {
        "favorites": len(favorite_ids()),
        "bookings": get_db().execute(
            "SELECT COUNT(*) c FROM bookings WHERE user_id=?", (u["id"],)).fetchone()["c"],
        "reviews": get_db().execute(
            "SELECT COUNT(*) c FROM reviews WHERE user_id=?", (u["id"],)).fetchone()["c"],
        "minutes": get_db().execute(
            "SELECT COALESCE(SUM(minutes),0) t FROM study_sessions WHERE user_id=?",
            (u["id"],)).fetchone()["t"],
    }
    return render_template("account.html", u=u, stats=stats)

@app.route("/account/bookings")
@login_required
def account_bookings():
    rows = get_db().execute(
        """SELECT b.*, s.name sname, s.address saddress, s.icon sicon
           FROM bookings b JOIN spots s ON s.id=b.spot_id
           WHERE b.user_id=? ORDER BY b.date DESC, b.time DESC""",
        (current_user()["id"],)).fetchall()
    return render_template("account_bookings.html", bookings=rows,
                           now=datetime.now(), cutoff=CANCEL_CUTOFF_HOURS)

@app.route("/account/contributions")
@login_required
def account_contributions():
    db = get_db()
    uid = current_user()["id"]
    my_reviews = db.execute(
        """SELECT r.*, s.name sname, s.id sid FROM reviews r
           JOIN spots s ON s.id=r.spot_id WHERE r.user_id=? ORDER BY r.id DESC""",
        (uid,)).fetchall()
    my_suggestions = db.execute(
        "SELECT * FROM spot_suggestions WHERE user_id=? ORDER BY id DESC",
        (uid,)).fetchall()
    return render_template("account_contributions.html", my_reviews=my_reviews,
                           my_suggestions=my_suggestions)

# ---------------------------------------------------------------- support
@app.route("/help", methods=["GET", "POST"])
def help_page():
    if request.method == "POST":
        flash("Message sent — support replies within one business day.", "success")
        return redirect(url_for("help_page") + "#contact")
    return render_template("help.html")

# ---------------------------------------------------------------- admin
@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    return render_template(
        "admin.html",
        spots=db.execute("SELECT * FROM spots ORDER BY id").fetchall(),
        bookings=db.execute(
            """SELECT b.*, s.name sname, u.name uname FROM bookings b
               JOIN spots s ON s.id=b.spot_id JOIN users u ON u.id=b.user_id
               ORDER BY b.id DESC LIMIT 25""").fetchall(),
        reports=db.execute(
            """SELECT rp.*, r.body, r.id rid, s.name sname, u.name uname
               FROM reports rp JOIN reviews r ON r.id=rp.review_id
               JOIN spots s ON s.id=r.spot_id JOIN users u ON u.id=r.user_id
               WHERE rp.resolved=0 ORDER BY rp.id DESC""").fetchall(),
        suggestions=db.execute(
            "SELECT * FROM spot_suggestions WHERE status='pending' ORDER BY id").fetchall(),
    )

@app.route("/admin/action", methods=["POST"])
@admin_required
def admin_action():
    db = get_db()
    kind = request.form.get("kind")
    action = request.form.get("action")
    try:
        item_id = int(request.form.get("id", 0))
    except ValueError:
        abort(400)

    if kind == "booking":
        db.execute("UPDATE bookings SET status=? WHERE id=?",
                   ({"confirm": "confirmed", "cancel": "cancelled"}.get(action, "pending"),
                    item_id))
    elif kind == "report":
        db.execute("UPDATE reports SET resolved=1 WHERE id=?", (item_id,))
        if action == "hide":
            db.execute(
                "UPDATE reviews SET status='hidden' WHERE id=(SELECT review_id FROM reports WHERE id=?)",
                (item_id,))
    elif kind == "spot":
        db.execute("UPDATE spots SET status=? WHERE id=?",
                   ("published" if action == "publish" else "hidden", item_id))
    elif kind == "suggestion":
        if action == "approve":
            s = db.execute("SELECT * FROM spot_suggestions WHERE id=?",
                           (item_id,)).fetchone()
            if s:
                db.execute(
                    """INSERT INTO spots(name,type,icon,address,walk,distance,price,
                       requires_payment,auto_confirm,capacity,open,rating,reviews,
                       tags,description,lat,lng,status)
                       VALUES(?,?,?,?,?,?,0,0,1,6,1,0,0,'wifi,quiet',?,51.5,-0.12,'published')""",
                    (s["name"], "Study Space", "fa-location-dot", s["address"] or "",
                     "—", 5.0, s["notes"] or ""))
            db.execute("UPDATE spot_suggestions SET status='approved' WHERE id=?", (item_id,))
        else:
            db.execute("UPDATE spot_suggestions SET status='rejected' WHERE id=?", (item_id,))
    db.commit()
    flash("Admin action applied.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403,
                           msg="You don't have access to that page."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           msg="We couldn't find that page."), 404

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
