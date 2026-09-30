<div align="center">

🛡️ CloudCost Guard

An automated, policy-driven cloud cost governance and optimization platform designed to keep your AWS, Azure, and GCP bills under tight control.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/MadhavPendyala/cloudcost-guard/ci.yml?branch=main)](https://github.com/MadhavPendyala/cloudcost-guard/actions)
[![Docker Hub](https://img.shields.io/docker/v/tony141203/cloudcost-guard?label=docker)](https://hub.docker.com/)

</div>

---

🚀 Overview

**CloudCost Guard** is a developer-first tool that continuously scans your multi-cloud infrastructure to detect cost anomalies, unoptimized resources, and budget violations before they hit your monthly invoice. Think of it as a security guard, but specifically for your cloud budget.

---

 ✨ Key Features

🔍 Real-Time Cost Anomaly Detection:** Uses machine learning models to spot unusual cost spikes and alerts your team immediately via Slack, Webhooks, or Email.
🧹 Automated Resource Cleanup:** Identifies and safely flags/terminates orphan resources such as unattached EBS/Managed disks, idle load balancers, and unassociated public IPs.
📋 Policy-as-Code Governance:** Enforces custom guardrails (e.g., maximum allowed EC2 instance sizes, required resource tagging) using easy-to-write configuration policies.
📊 Multi-Cloud Visibility:** Unified dashboards aggregating cost metrics seamlessly across AWS, Azure, and Google Cloud Platform (GCP).
💬 CI/CD Integration:** Integrates into pull requests to provide proactive cost estimates for Infrastructure-as-Code (Terraform, CloudFormation).

---
 🏗️ Architecture
```
+--------------------------------------------+
   |           CloudCost Guard Core             |
   +--------------------------------------------+
     |                 |                |
     v                 v                v
 [ AWS API ]     [ Azure API ]     [ GCP API ]
     |                 |                |
     +-----------------+----------------+
                       |
                       v
        { Anomaly Detection Engine }
                       |
        +--------------+--------------+
        |                             |
        v                             v
 [ Slack Alerts ]            [ Auto-Remediation ]
```
 🛠️ Tech Stack

  Core Engine:** Python (FastAPI, Celery)
  ML/Anomalies:** Scikit-learn (Isolation Forest)
  Cloud SDKs:** Boto3, Azure SDK, Google Cloud Client Libraries
  Database:** PostgreSQL (with SQLAlchemy ORM)
  Frontend:** React, Tailwind CSS (optional dashboard view)

