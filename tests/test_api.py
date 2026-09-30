import os, io, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
import pytest
from app import app, init_db


@pytest.fixture
def client():
    init_db()
    c = app.test_client()
    c.post("/api/reset")
    return c


def test_costs_shape(client):
    d = client.get("/api/costs").get_json()
    assert len(d["dates"]) == len(d["total"]) == 90 and "EC2" in d["services"]


def test_zscore_finds_injected_spike(client):
    client.post("/api/spike", json={"service": "EC2"})
    a = client.get("/api/anomalies?service=EC2&method=zscore&window=14&threshold=3").get_json()
    assert any(x["cause"] == "EC2" for x in a)


def test_isolation_forest_runs(client):
    client.post("/api/spike", json={"service": "RDS"})
    a = client.get("/api/anomalies?method=iforest&contamination=0.05").get_json()
    assert len(a) >= 1 and "score" in a[0]


def test_forecast_and_next_day(client):
    client.post("/api/next")
    f = client.get("/api/forecast?budget=1").get_json()
    assert f["over"] is True and f["projected"] > 0


def test_upload_success(client):
    payload = b"date,service,cost\n2024-01-01,EC2,10\n2024-01-02,EC2,11\n2024-01-03,EC2,12\n2024-01-04,EC2,13\n2024-01-05,EC2,14\n2024-01-06,EC2,15\n2024-01-07,EC2,16\n2024-01-08,EC2,17\n2024-01-09,EC2,18\n2024-01-10,EC2,19\n2024-01-11,EC2,20\n2024-01-12,EC2,21\n2024-01-13,EC2,22\n2024-01-14,EC2,23\n2024-01-15,EC2,24\n2024-01-16,EC2,25\n2024-01-17,EC2,26\n2024-01-18,EC2,27\n2024-01-19,EC2,28\n2024-01-20,EC2,29\n"
    res = client.post("/api/upload", data={"file": (io.BytesIO(payload), "x.csv")})
    assert res.status_code == 200
    assert res.get_json()["rows"] == 20
    assert "Imported" in res.get_json()["message"]


def test_upload_validation(client):
    assert client.post("/api/upload", data={"file": (io.BytesIO(b"a,b\n1,2"), "x.csv")}).status_code == 400


def test_direct_page_routes(client):
    paths = ["/", "/dashboard", "/cost-optimization", "/login", "/signup", "/learn/what-it-does", "/learn/why-it-matters",
             "/learn/how-it-works", "/learn/customer-stories", "/overview", "/how-it-works", "/reviews",
             "/cost-data", "/company-playbooks", "/company/aws", "/company/azure",
             "/company/google-cloud", "/company/netflix"]
    assert all(client.get(path).status_code == 200 for path in paths if path != "/learn/customer-stories")
    assert client.get("/learn/customer-stories").status_code == 308
    assert client.get("/dashboard.").status_code == 308
    assert client.get("/company/aws.").status_code == 308
    assert client.get("/reviews.").status_code == 308
    assert client.get("/login.").status_code == 308
    assert client.get("/not-a-page").status_code == 404


def test_cost_trend_uses_current_dataset(client):
    data = client.get("/api/cost-trend").get_json()
    assert len(data["dates"]) == 30
    assert len(data["total"]) == 30
    assert data["source"] == "Demo seed data"
    assert "not a cloud-provider live feed" in data["note"]


def test_review_submission_and_validation(client):
    response = client.post("/api/reviews", json={
        "name": "Test User", "role": "FinOps", "rating": 5, "review": "Useful cost insights.", "owner_key": "owner-1"
    })
    assert response.status_code == 201
    review_id = response.get_json()["id"]
    assert response.get_json()["rating"] == 5
    assert len(client.get("/api/reviews").get_json()) == 1
    owned_review = client.get("/api/reviews?voter=owner-1").get_json()[0]
    assert owned_review["can_edit"] == 1
    assert owned_review["likes"] == 0 and owned_review["dislikes"] == 0
    assert client.post("/api/reviews", json={"rating": 8}).status_code == 400
    assert client.patch(f"/api/reviews/{review_id}", json={"owner_key":"wrong","name":"Hacker","role":"FinOps", "rating":1,"review":"No"}).status_code == 404
    assert client.patch(f"/api/reviews/{review_id}", json={"owner_key":"owner-1","name":"Updated User","role":"FinOps","rating":4,"review":"Updated details."}).status_code == 200
    assert client.get("/api/reviews?voter=reader").get_json()[0]["name"] == "Updated User"
    vote = client.post(f"/api/reviews/{review_id}/vote", json={"voter_key":"reader","vote":"like"}).get_json()
    assert vote["likes"] == 1 and vote["my_vote"] == "like"
    vote = client.post(f"/api/reviews/{review_id}/vote", json={"voter_key":"reader","vote":"dislike"}).get_json()
    assert vote["likes"] == 0 and vote["dislikes"] == 1 and vote["my_vote"] == "dislike"
    assert client.delete(f"/api/reviews/{review_id}", json={"owner_key":"wrong"}).status_code == 404
    assert client.delete(f"/api/reviews/{review_id}", json={"owner_key":"owner-1"}).status_code == 200
    assert client.get("/api/reviews").get_json() == []


def test_signup_login_and_logout(client):
    assert client.get("/api/auth/me").get_json()["authenticated"] is False
    signup = client.post("/api/auth/signup", json={
        "name": "Cloud User", "email": "cloud@example.com", "password": "correct-horse-battery"
    })
    assert signup.status_code == 201
    assert signup.get_json()["next"] == "/cost-optimization"
    assert client.get("/api/auth/me").get_json()["user"]["name"] == "Cloud User"
    assert client.post("/api/auth/signup", json={
        "name": "Duplicate", "email": "CLOUD@example.com", "password": "correct-horse-battery"
    }).status_code == 409
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").get_json()["authenticated"] is False
    assert client.post("/api/auth/login", json={"email": "cloud@example.com", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "cloud@example.com", "password": "correct-horse-battery"}).status_code == 200
    assert client.get("/api/auth/me").get_json()["authenticated"] is True
