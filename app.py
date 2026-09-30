import csv, io, os, random, re, secrets, sqlite3, datetime as dt
import numpy as np
from flask import Flask, abort, jsonify, redirect, request, session
from detector import zscore, iforest
from werkzeug.security import check_password_hash, generate_password_hash

DB = os.environ.get("DB_PATH", "costs.db")
SERVICES = ["EC2", "RDS", "S3", "Lambda", "Data Transfer"]
BASE = [420, 260, 90, 60, 110]
DAYS = 90
app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


@app.before_request
def remove_copied_sentence_period():
    path = request.path
    if not path.endswith("."):
        return None
    canonical = path[:-1]
    if canonical in {"/dashboard", "/cost-optimization", "/overview", "/how-it-works", "/reviews", "/cost-data", "/company-playbooks", "/login", "/signup"}:
        return redirect(canonical, code=308)
    if canonical.startswith("/learn/") and canonical.rsplit("/", 1)[-1] in {
        "what-it-does", "why-it-matters", "how-it-works", "customer-stories"
    }:
        return redirect(canonical, code=308)
    if canonical.startswith("/company/") and canonical.rsplit("/", 1)[-1] in {
        "aws", "azure", "google-cloud", "netflix"
    }:
        return redirect(canonical, code=308)
    return None


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def value(k, i):
    return round(BASE[k] * (1 + i * .004) * (1 if i % 7 < 5 else .9) * (1 + random.gauss(0, .04)), 2)


def seed(c):
    c.execute("DELETE FROM costs")
    start = dt.date.today() - dt.timedelta(days=DAYS - 1)
    for i in range(DAYS):
        d = (start + dt.timedelta(days=i)).isoformat()
        for k, s in enumerate(SERVICES):
            c.execute("INSERT INTO costs VALUES (?,?,?)", (d, s, value(k, i)))
    c.commit()


def init_db():
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS costs(day TEXT, service TEXT, cost REAL, PRIMARY KEY(day, service))")
        c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL, rating INTEGER NOT NULL, review TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        review_columns = {row[1] for row in c.execute("PRAGMA table_info(reviews)").fetchall()}
        if "owner_key" not in review_columns:
            c.execute("ALTER TABLE reviews ADD COLUMN owner_key TEXT NOT NULL DEFAULT ''")
        c.execute("CREATE TABLE IF NOT EXISTS review_votes(review_id INTEGER NOT NULL, voter_key TEXT NOT NULL, vote TEXT NOT NULL CHECK(vote IN ('like','dislike')), PRIMARY KEY(review_id, voter_key), FOREIGN KEY(review_id) REFERENCES reviews(id) ON DELETE CASCADE)")
        if c.execute("SELECT COUNT(*) FROM costs").fetchone()[0] == 0:
            seed(c)
            c.execute("INSERT OR REPLACE INTO app_meta VALUES ('cost_source', 'Demo seed data')")
        elif c.execute("SELECT 1 FROM app_meta WHERE key='cost_source'").fetchone() is None:
            c.execute("INSERT INTO app_meta VALUES ('cost_source', 'Existing dataset')")


def load():
    rows = conn().execute("SELECT day, service, cost FROM costs ORDER BY day").fetchall()
    dates = sorted({r["day"] for r in rows})
    idx = {d: i for i, d in enumerate(dates)}
    svc = {s: [0.0] * len(dates) for s in sorted({r["service"] for r in rows})}
    for r in rows:
        svc[r["service"]][idx[r["day"]]] = r["cost"]
    return dates, svc


def total(svc):
    return [round(sum(v[i] for v in svc.values()), 2) for i in range(len(next(iter(svc.values()))))]


def culprit(svc, i, w):
    w = min(w, i)
    if w < 2:
        return ""
    best, bz = "", -1
    for s, v in svc.items():
        win = np.array(v[i - w:i])
        z = abs(v[i] - win.mean()) / max(win.std(), win.mean() * .01)
        if z > bz:
            best, bz = s, z
    return best


@app.get("/")
def index():
    return app.send_static_file("home.html")


@app.get("/dashboard")
@app.get("/cost-optimization")
def dashboard():
    return app.send_static_file("index.html")


@app.get("/learn/<topic>")
def learn(topic):
    if topic not in {"what-it-does", "why-it-matters", "how-it-works", "customer-stories"}:
        abort(404)
    if topic == "customer-stories":
        return redirect("/reviews", code=308)
    return app.send_static_file("learn.html")


@app.get("/company/<slug>")
def company(slug):
    if slug not in {"aws", "azure", "google-cloud", "netflix"}:
        abort(404)
    return app.send_static_file("company.html")


@app.get("/login")
@app.get("/signup")
def auth_page():
    return app.send_static_file("auth.html")


@app.get("/api/auth/me")
def auth_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(authenticated=False)
    with conn() as c:
        user = c.execute("SELECT id, name, email FROM users WHERE id=?", (user_id,)).fetchone()
    if user is None:
        session.clear()
        return jsonify(authenticated=False)
    return jsonify(authenticated=True, user=dict(user))


@app.post("/api/auth/signup")
def auth_signup():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not name or len(name) > 80:
        return jsonify(error="Enter your name (up to 80 characters)."), 400
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8 or len(password) > 128:
        return jsonify(error="Password must be between 8 and 128 characters."), 400
    try:
        with conn() as c:
            cursor = c.execute("INSERT INTO users(name, email, password_hash) VALUES (?,?,?)", (name, email, generate_password_hash(password)))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="An account with this email already exists. Try logging in."), 409
    session.clear()
    session["user_id"] = user_id
    return jsonify(ok=True, next="/cost-optimization"), 201


@app.post("/api/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    with conn() as c:
        user = c.execute("SELECT id, password_hash FROM users WHERE email=?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Email or password is incorrect."), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(ok=True, next="/cost-optimization")


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/overview")
@app.get("/how-it-works")
@app.get("/reviews")
@app.get("/cost-data")
@app.get("/company-playbooks")
def info_page():
    page = request.path.lstrip("/")
    if page not in {"overview", "how-it-works", "reviews", "cost-data", "company-playbooks"}:
        abort(404)
    return app.send_static_file("info-page.html")


@app.get("/api/costs")
def costs():
    dates, svc = load()
    with conn() as c:
        source = c.execute("SELECT value FROM app_meta WHERE key='cost_source'").fetchone()
    return jsonify(dates=dates, services=svc, total=total(svc), source=source[0] if source else "Existing dataset")


@app.get("/api/cost-trend")
def cost_trend():
    dates, services = load()
    start = max(0, len(dates) - 30)
    recent_dates = dates[start:]
    series = {name: values[start:] for name, values in services.items()}
    with conn() as c:
        source = c.execute("SELECT value FROM app_meta WHERE key='cost_source'").fetchone()
    return jsonify(
        dates=recent_dates,
        services=series,
        total=total(series) if series else [],
        source=source[0] if source else "Existing dataset",
        note="This is the dataset currently loaded in CloudCost Guard; it is not a cloud-provider live feed or company-published spend.",
    )


@app.get("/api/reviews")
def reviews():
    voter_key = request.args.get("voter", "")
    with conn() as c:
        rows = c.execute("""SELECT r.id, r.name, r.role, r.rating, r.review, r.created_at,
            (SELECT COUNT(*) FROM review_votes v WHERE v.review_id=r.id AND v.vote='like') AS likes,
            (SELECT COUNT(*) FROM review_votes v WHERE v.review_id=r.id AND v.vote='dislike') AS dislikes,
            (SELECT vote FROM review_votes v WHERE v.review_id=r.id AND v.voter_key=?) AS my_vote,
            CASE WHEN r.owner_key='' OR r.owner_key=? THEN 1 ELSE 0 END AS can_edit
            FROM reviews r ORDER BY r.id DESC""", (voter_key, voter_key)).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/reviews")
def submit_review():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    role = str(data.get("role", "")).strip()
    review = str(data.get("review", "")).strip()
    owner_key = str(data.get("owner_key", "")).strip()
    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if not name or not role or not review or not owner_key or rating not in range(1, 6):
        return jsonify(error="Provide your name, role, review, a browser key, and a rating from 1 to 5."), 400
    if len(name) > 80 or len(role) > 100 or len(review) > 1000 or len(owner_key) > 128:
        return jsonify(error="Name, role, or review exceeds the allowed length."), 400
    with conn() as c:
        cursor = c.execute("INSERT INTO reviews(name, role, rating, review, owner_key) VALUES (?,?,?,?,?)", (name, role, rating, review, owner_key))
        review_id = cursor.lastrowid
        row = c.execute("SELECT id, name, role, rating, review, created_at FROM reviews WHERE id=?", (review_id,)).fetchone()
    return jsonify(dict(row)), 201


@app.patch("/api/reviews/<int:review_id>")
def update_review(review_id):
    data = request.get_json(silent=True) or {}
    owner_key = str(data.get("owner_key", "")).strip()
    name = str(data.get("name", "")).strip()
    role = str(data.get("role", "")).strip()
    review = str(data.get("review", "")).strip()
    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if not owner_key:
        return jsonify(error="This review can only be edited from the browser that submitted it."), 403
    if not name or not role or not review or rating not in range(1, 6):
        return jsonify(error="Provide your name, role, review, and a rating from 1 to 5."), 400
    if len(name) > 80 or len(role) > 100 or len(review) > 1000:
        return jsonify(error="Name, role, or review exceeds the allowed length."), 400
    with conn() as c:
        result = c.execute("UPDATE reviews SET name=?, role=?, rating=?, review=?, owner_key=? WHERE id=? AND (owner_key=? OR owner_key='')", (name, role, rating, review, owner_key, review_id, owner_key))
        if result.rowcount == 0:
            return jsonify(error="Review not found or it was not submitted from this browser."), 404
        row = c.execute("SELECT id, name, role, rating, review, created_at FROM reviews WHERE id=?", (review_id,)).fetchone()
    return jsonify(dict(row))


@app.delete("/api/reviews/<int:review_id>")
def delete_review(review_id):
    data = request.get_json(silent=True) or {}
    owner_key = str(data.get("owner_key", "")).strip()
    if not owner_key:
        return jsonify(error="This review can only be deleted from the browser that submitted it."), 403
    with conn() as c:
        exists = c.execute("SELECT 1 FROM reviews WHERE id=? AND (owner_key=? OR owner_key='')", (review_id, owner_key)).fetchone()
        if exists is None:
            return jsonify(error="Review not found or it was not submitted from this browser."), 404
        c.execute("DELETE FROM review_votes WHERE review_id=?", (review_id,))
        result = c.execute("DELETE FROM reviews WHERE id=? AND (owner_key=? OR owner_key='')", (review_id, owner_key))
        if result.rowcount == 0:
            return jsonify(error="Review not found or it was not submitted from this browser."), 404
    return jsonify(ok=True)


@app.post("/api/reviews/<int:review_id>/vote")
def vote_review(review_id):
    data = request.get_json(silent=True) or {}
    voter_key = str(data.get("voter_key", "")).strip()
    vote = data.get("vote")
    if not voter_key or len(voter_key) > 128 or vote not in {"like", "dislike"}:
        return jsonify(error="A browser key and either like or dislike are required."), 400
    with conn() as c:
        if c.execute("SELECT 1 FROM reviews WHERE id=?", (review_id,)).fetchone() is None:
            return jsonify(error="Review not found."), 404
        current = c.execute("SELECT vote FROM review_votes WHERE review_id=? AND voter_key=?", (review_id, voter_key)).fetchone()
        if current and current[0] == vote:
            c.execute("DELETE FROM review_votes WHERE review_id=? AND voter_key=?", (review_id, voter_key))
        else:
            c.execute("INSERT OR REPLACE INTO review_votes(review_id, voter_key, vote) VALUES (?,?,?)", (review_id, voter_key, vote))
        counts = c.execute("SELECT SUM(vote='like'), SUM(vote='dislike') FROM review_votes WHERE review_id=?", (review_id,)).fetchone()
        selected = c.execute("SELECT vote FROM review_votes WHERE review_id=? AND voter_key=?", (review_id, voter_key)).fetchone()
    return jsonify(likes=counts[0] or 0, dislikes=counts[1] or 0, my_vote=selected[0] if selected else None)


@app.get("/api/anomalies")
def anomalies():
    q = request.args
    name, method = q.get("service", "All"), q.get("method", "zscore")
    w, th, cont = int(q.get("window", 14)), float(q.get("threshold", 3)), float(q.get("contamination", .04))
    dates, svc = load()
    vals = total(svc) if name == "All" else svc.get(name, [])
    found = zscore(vals, w, th) if method == "zscore" else iforest(vals, cont)
    for f in found:
        f["date"], f["cause"] = dates[f["i"]], culprit(svc, f["i"], w)
    return jsonify(found)


@app.get("/api/forecast")
def forecast():
    _, svc = load()
    t = total(svc)
    budget = float(request.args.get("budget", 30000))
    proj = sum(t[-7:]) / 7 * 30
    return jsonify(last30=sum(t[-30:]), projected=proj, budget=budget, over=proj > budget)


@app.post("/api/spike")
def spike():
    s = (request.get_json(silent=True) or {}).get("service", "All")
    s = random.choice(SERVICES) if s not in SERVICES else s
    dates, _ = load()
    day = random.choice(dates[-10:])
    with conn() as c:
        c.execute("UPDATE costs SET cost=cost*? WHERE day=? AND service=?", (round(random.uniform(2, 3.5), 2), day, s))
    return jsonify(service=s, day=day)


@app.post("/api/next")
def next_day():
    dates, _ = load()
    d = (dt.date.fromisoformat(dates[-1]) + dt.timedelta(days=1)).isoformat()
    hit = random.randrange(5) if random.random() < .2 else -1
    with conn() as c:
        for k, s in enumerate(SERVICES):
            v = value(k, len(dates)) * (random.uniform(2.2, 3.2) if k == hit else 1)
            c.execute("INSERT OR REPLACE INTO costs VALUES (?,?,?)", (d, s, round(v, 2)))
    return jsonify(day=d)


@app.post("/api/reset")
def reset():
    with conn() as c:
        seed(c)
        c.execute("INSERT OR REPLACE INTO app_meta VALUES ('cost_source', 'Demo seed data')")
    return jsonify(ok=True)


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify(error="Attach a CSV file with columns: date,service,cost"), 400
    try:
        rows = [(r["date"], r["service"], float(r["cost"])) for r in csv.DictReader(io.StringIO(f.read().decode("utf-8-sig")))]
        for r in rows:
            dt.date.fromisoformat(r[0])
    except (KeyError, ValueError, UnicodeDecodeError):
        return jsonify(error="Invalid CSV. Expected columns date (YYYY-MM-DD), service, cost."), 400
    if len({r[0] for r in rows}) < 20:
        return jsonify(error="Provide at least 20 days of data."), 400
    with conn() as c:
        c.execute("DELETE FROM costs")
        c.executemany("INSERT OR REPLACE INTO costs VALUES (?,?,?)", rows)
        c.execute("INSERT OR REPLACE INTO app_meta VALUES ('cost_source', 'Uploaded CSV')")
    return jsonify(rows=len(rows), message=f"Imported {len(rows)} rows from CSV and refreshed the dashboard.")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
