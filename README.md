# CloudCost Guard

Cloud cost monitoring with anomaly detection: a Flask REST API, SQLite storage, two detectors
(rolling z-score and Isolation Forest), an interactive Chart.js dashboard, Docker packaging and GitHub Actions CI.

## Run locally
    pip install -r requirements.txt
    python app.py            # http://localhost:5000
    pytest -q                # run tests

## Run with Docker
    docker build -t cloudcost-guard .
    docker run -p 8000:8000 -v costdata:/data cloudcost-guard   # http://localhost:8000

## API
| Endpoint | Purpose |
|---|---|
| GET /api/costs | Daily cost per service and total |
| GET /api/anomalies?service=&method=zscore\|iforest&window=&threshold=&contamination= | Detected anomalies with likely cause |
| GET /api/forecast?budget= | 30-day projection vs budget |
| POST /api/spike, /api/next, /api/reset | Simulate spike, add a day, regenerate data |
| POST /api/upload | Replace data with a CSV (date,service,cost) |

## Design notes
- Z-score: compares each day with the mean and std of the previous N days. Simple, explainable, needs no training.
- Isolation Forest: unsupervised model on value, day-over-day change and deviation from the 7-day mean.
  It always flags the chosen contamination share of points, so tune "expected outliers".
- Likely cause: the service with the highest z-score on the anomalous day.
- Real data: export AWS Cost Explorer data to CSV (date,service,cost) and upload it, or call boto3 `get_cost_and_usage` and insert into the `costs` table.

## Deploy
Push to GitHub (CI runs tests and builds the image), then create a Render/Railway/AWS App Runner web service from the Dockerfile.

## Future work
Email/Slack alerts, user login, Prophet/LSTM forecasting, multi-account support.
