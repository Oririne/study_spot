# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = "study-spot-dev-secret-2025"

# ============================================================
# IN-MEMORY DATA (swap for SQLite/Postgres later)
# ============================================================
SPOTS = [
    {
        "id": 1, "name": "Brew & Muse", "type": "Cafe", "icon": "fa-mug-saucer",
        "address": "123 Nguyen Hue, District 1", "distance": 0.3,
        "rating": 4.8, "review_count": 214, "price": "$$", "open": True,
        "hours": "7:00 – 22:00", "noise": "Low", "wifi_speed": "150 Mbps",
        "outlets": "Every table",
        "amenities": ["wifi", "outlets", "quiet", "coffee", "aircon"],
        "description": "A cozy café with excellent matcha, fast wifi, and plenty of power outlets. Perfect for deep work sessions.",
        "lat": 10.7769, "lng": 106.7009, "booking_enabled": True,
        "slots": ["08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"],
        "booking_price": 0,
    },
    {
        "id": 2, "name": "Central Library", "type": "Library", "icon": "fa-book",
        "address": "45 Ly Tu Trong, District 1", "distance": 0.8,
        "rating": 5.0, "review_count": 402, "price": "Free", "open": True,
        "hours": "8:00 – 21:00", "noise": "Silent", "wifi_speed": "80 Mbps",
        "outlets": "At desks",
        "amenities": ["wifi", "outlets", "quiet", "free", "printing"],
        "description": "The city's largest public library with dedicated silent zones, free access, and a huge reference collection.",
        "lat": 10.7800, "lng": 106.6980, "booking_enabled": True,
        "slots": ["08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00"],
        "booking_price": 0,
    },
    {
        "id": 3, "name": "CoWork Hub", "type": "Study Space", "icon": "fa-laptop",
        "address": "78 Le Loi, District 1", "distance": 1.1,
        "rating": 4.2, "review_count": 87, "price": "$$", "open": True,
        "hours": "8:00 – 20:00", "noise": "Medium", "wifi_speed": "200 Mbps",
        "outlets": "Every seat",
        "amenities": ["wifi", "outlets", "coffee", "whiteboard", "printing", "aircon"],
        "description": "A modern coworking space with private booths, whiteboards, and unlimited coffee. Great for group sessions.",
        "lat": 10.7730, "lng": 106.7040, "booking_enabled": True,
        "slots": ["08:00", "09:00", "10:00", "13:00", "14:00", "15:00"],
        "booking_price": 5.00,
    },
]

REVIEWS = [
    {"id": 1, "spot_id": 1, "user": "Alina M.", "avatar": "A", "rating": 5,
     "criteria": {"noise": 5, "wifi": 5, "outlets": 5},
     "text": "Found the perfect café with fast wifi and amazing matcha. The virtual companion kept me off my phone for 3 hours straight!",
     "date": "2025-03-12", "photos": 0},
    {"id": 2, "spot_id": 2, "user": "James K.", "avatar": "J", "rating": 5,
     "criteria": {"noise": 5, "wifi": 4, "outlets": 4},
     "text": "The silent zone is a game changer for exam prep. Free printing saved me so much money too.",
     "date": "2025-02-28", "photos": 0},
    {"id": 3, "spot_id": 3, "user": "Priya S.", "avatar": "P", "rating": 4,
     "criteria": {"noise": 3, "wifi": 5, "outlets": 5},
     "text": "Great for group projects. Whiteboards and fast wifi. Can get a bit noisy at lunchtime.",
     "date": "2025-03-01", "photos": 0},
]

USERS = {
    "demo": {"password": "demo123", "name": "Demo User", "email": "demo@studyspot.app",
             "role": "user", "avatar": "D"},
}
FAVORITES = {"demo": set()}
BOOKINGS = []
NEXT_REVIEW_ID = 4
NEXT_BOOKING_ID = 1

# ============================================================
# HELPERS
# ============================================================
def current_user():
    return USERS.get(session["username"]) if "username" in session else None

def star_list(rating):
    out = []
    for i in range(5):
        if i < int(rating): out.append("full")
        elif rating - i >= 0.5: out.append("half")
        else: out.append("empty")
    return out

@app.context_processor
def inject_helpers():
    return {"current_user": current_user(), "username": session.get("username"), "star_list": star_list}

def get_spot(spot_id):
    return next((s for s in SPOTS if s["id"] == spot_id), None)

def spots_with_favorites():
    spots = [dict(s) for s in SPOTS]
    u = session.get("username")
    favs = FAVORITES.get(u, set()) if u else set()
    for s in spots:
        s["is_favorite"] = s["id"] in favs
    return spots

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def home():
    featured = spots_with_favorites()[:3]
    for s in featured:
        s["stars"] = star_list(s["rating"])
    return render_template("index.html", spots=featured)

@app.route("/spots")
def spots_page():
    q     = request.args.get("q", "").strip().lower()
    noise = request.args.get("noise", "")
    wifi  = request.args.get("wifi", "")
    sort  = request.args.get("sort", "distance")
    view  = request.args.get("view", "list")

    results = spots_with_favorites()
    if q:
        results = [s for s in results if q in s["name"].lower() or q in s["address"].lower() or q in s["type"].lower()]
    if noise:
        results = [s for s in results if s["noise"].lower() == noise.lower()]
    if wifi:
        results = [s for s in results if int(s["wifi_speed"].split()[0]) >= int(wifi)]

    if sort == "rating": results.sort(key=lambda s: s["rating"], reverse=True)
    elif sort == "price": results.sort(key=lambda s: s["price"])
    else: results.sort(key=lambda s: s["distance"])

    for s in results:
        s["stars"] = star_list(s["rating"])
    return render_template("spots.html", spots=results, q=q, noise=noise, wifi=wifi, sort=sort, view=view)

@app.route("/spots/<int:spot_id>")
def spot_detail(spot_id):
    spot = get_spot(spot_id)
    if not spot:
        flash("Spot not found.", "error")
        return redirect(url_for("spots_page"))
    spot = dict(spot)
    u = session.get("username")
    spot["is_favorite"] = spot_id in FAVORITES.get(u, set()) if u else False
    spot["stars"] = star_list(spot["rating"])
    spot_reviews = [r for r in REVIEWS if r["spot_id"] == spot_id]
    return render_template("spot_detail.html", spot=spot, reviews=spot_reviews)

# ---------- BOOKING ----------
@app.route("/spots/<int:spot_id>/book", methods=["GET", "POST"])
def booking(spot_id):
    if "username" not in session:
        flash("Please log in to book a spot.", "info")
        return redirect(url_for("login", next=f"spots/{spot_id}/book"))
    spot = get_spot(spot_id)
    if not spot:
        flash("Spot not found.", "error")
        return redirect(url_for("spots_page"))
    if not spot["booking_enabled"]:
        flash("Booking is not available for this spot yet.", "error")
        return redirect(url_for("spot_detail", spot_id=spot_id))

    if request.method == "POST":
        date_val = request.form.get("date", "")
        time_val = request.form.get("time", "")
        people   = request.form.get("people", "1")
        seat     = request.form.get("seat", "Any")
        name     = request.form.get("name", "")
        email    = request.form.get("email", "")

        if not date_val or not time_val or not name or not email:
            flash("Please fill in all required fields.", "error")
            return render_template("booking.html", spot=spot, today=date.today().isoformat())

        global NEXT_BOOKING_ID
        booking_id = NEXT_BOOKING_ID
        NEXT_BOOKING_ID += 1
        BOOKINGS.append({
            "id": booking_id, "spot_id": spot_id, "spot_name": spot["name"],
            "date": date_val, "time": time_val, "people": int(people),
            "seat": seat, "name": name, "email": email,
            "status": "Confirmed" if spot["booking_price"] == 0 else "Pending",
            "price": spot["booking_price"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "username": session.get("username"),
        })
        return redirect(url_for("booking_confirmation", booking_id=booking_id))

    return render_template("booking.html", spot=spot, today=date.today().isoformat())

@app.route("/bookings/<int:booking_id>/confirmation")
def booking_confirmation(booking_id):
    booking = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if not booking:
        flash("Booking not found.", "error")
        return redirect(url_for("home"))
    return render_template("booking_confirmation.html", booking=booking)

@app.route("/api/booking/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    if "username" not in session:
        return jsonify({"error": "login_required"}), 401
    for b in BOOKINGS:
        if b["id"] == booking_id and b.get("username") == session["username"]:
            b["status"] = "Cancelled"
            return jsonify({"ok": True, "status": "Cancelled"})
    return jsonify({"error": "not_found"}), 404

# ---------- FAVORITES ----------
@app.route("/favorites")
def favorites():
    if "username" not in session:
        flash("Please log in to view your favorites.", "info")
        return redirect(url_for("login", next="favorites"))
    fav_ids = FAVORITES.get(session["username"], set())
    fav_spots = []
    for s in SPOTS:
        if s["id"] in fav_ids:
            spot = dict(s)
            spot["stars"] = star_list(spot["rating"])
            spot["is_favorite"] = True
            fav_spots.append(spot)
    return render_template("favorites.html", spots=fav_spots)

@app.route("/api/favorite/<int:spot_id>", methods=["POST"])
def toggle_favorite(spot_id):
    if "username" not in session:
        return jsonify({"error": "login_required", "message": "Please log in to save favorites."}), 401
    u = session["username"]
    if spot_id in FAVORITES[u]:
        FAVORITES[u].remove(spot_id)
        return jsonify({"favorited": False, "spot_id": spot_id})
    FAVORITES[u].add(spot_id)
    return jsonify({"favorited": True, "spot_id": spot_id})

# ---------- COMPANION ----------
@app.route("/companion")
def companion():
    return render_template("companion.html")

# ---------- REVIEWS ----------
@app.route("/reviews")
def reviews_page():
    q = request.args.get("q", "").strip().lower()
    results = []
    for r in REVIEWS:
        spot = get_spot(r["spot_id"])
        if not spot: continue
        item = dict(r)
        item["spot_name"] = spot["name"]
        item["spot_icon"] = spot["icon"]
        item["stars"] = star_list(item["rating"])
        if q and q not in item["text"].lower() and q not in item["user"].lower() and q not in item["spot_name"].lower():
            continue
        results.append(item)
    return render_template("reviews.html", reviews=results, q=q)

@app.route("/spots/<int:spot_id>/review", methods=["GET", "POST"])
def write_review(spot_id):
    spot = get_spot(spot_id)
    if not spot:
        flash("Spot not found.", "error")
        return redirect(url_for("spots_page"))
    if "username" not in session:
        flash("Please log in to write a review.", "info")
        return redirect(url_for("login", next=f"spots/{spot_id}/review"))

    if request.method == "POST":
        rating  = int(request.form.get("rating", 5))
        noise   = int(request.form.get("noise", 3))
        wifi    = int(request.form.get("wifi", 3))
        outlets = int(request.form.get("outlets", 3))
        text    = request.form.get("text", "").strip()
        if not text:
            flash("Review text cannot be empty.", "error")
            return render_template("write_review.html", spot=spot)

        global NEXT_REVIEW_ID
        user = USERS[session["username"]]
        REVIEWS.append({
            "id": NEXT_REVIEW_ID, "spot_id": spot_id, "user": user["name"],
            "avatar": user.get("avatar", user["name"][0].upper()),
            "rating": rating, "criteria": {"noise": noise, "wifi": wifi, "outlets": outlets},
            "text": text, "date": datetime.now().strftime("%Y-%m-%d"), "photos": 0,
        })
        NEXT_REVIEW_ID += 1

        spot_reviews = [r for r in REVIEWS if r["spot_id"] == spot_id]
        avg = round(sum(r["rating"] for r in spot_reviews) / len(spot_reviews), 1)
        for s in SPOTS:
            if s["id"] == spot_id:
                s["rating"] = avg
                s["review_count"] = len(spot_reviews)
                break
        flash("Thanks for your review!", "success")
        return redirect(url_for("spot_detail", spot_id=spot_id))

    return render_template("write_review.html", spot=spot)

# ---------- AUTH ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if username in USERS and USERS[username]["password"] == password:
            session["username"] = username
            flash(f"Welcome back, {USERS[username]['name']}!", "success")
            nxt = request.args.get("next") or request.form.get("next")
            return redirect(f"/{nxt}" if nxt else url_for("home"))
        flash("Invalid username or password. Try demo / demo123", "error")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        email    = request.form.get("email", "").strip()
        name     = request.form.get("name", "").strip()
        if not all([username, password, email, name]):
            flash("Please fill in all fields.", "error")
            return render_template("signup.html")
        if username in USERS:
            flash("Username already taken.", "error")
            return render_template("signup.html")
        USERS[username] = {"password": password, "name": name, "email": email,
                           "role": "user", "avatar": name[0].upper()}
        FAVORITES[username] = set()
        session["username"] = username
        flash("Account created! Welcome to StudySpot.", "success")
        return redirect(url_for("home"))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# ---------- ACCOUNT ----------
@app.route("/account")
def account():
    if "username" not in session:
        flash("Please log in to view your account.", "info")
        return redirect(url_for("login", next="account"))
    user = USERS[session["username"]]
    my_reviews  = [r for r in REVIEWS if r["user"] == user["name"]]
    my_bookings = [b for b in BOOKINGS if b.get("username") == session["username"]]
    return render_template("account.html", user=user,
                           review_count=len(my_reviews),
                           booking_count=len(my_bookings),
                           favorites_count=len(FAVORITES.get(session["username"], set())))

@app.route("/account/bookings")
def my_bookings():
    if "username" not in session:
        flash("Please log in to view your bookings.", "info")
        return redirect(url_for("login", next="account/bookings"))
    bookings = [b for b in BOOKINGS if b.get("username") == session["username"]]
    return render_template("my_bookings.html", bookings=bookings)

@app.route("/account/contributions")
def contributions():
    if "username" not in session:
        flash("Please log in to view your contributions.", "info")
        return redirect(url_for("login", next="account/contributions"))
    user = USERS[session["username"]]
    my_reviews = [r for r in REVIEWS if r["user"] == user["name"]]
    for r in my_reviews:
        spot = get_spot(r["spot_id"])
        r["spot_name"] = spot["name"] if spot else "Unknown"
        r["stars"] = star_list(r["rating"])
    return render_template("contributions.html", reviews=my_reviews)

# ---------- SUPPORT ----------
@app.route("/help")
def help_page():
    return render_template("help.html")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)