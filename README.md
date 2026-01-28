# 📘 InfoGuard AI – Automated Wikipedia Integrity Monitoring System

## 📌 Project Overview

InfoGuard AI is an automated monitoring system that tracks Wikipedia pages in real time, detects content changes, analyzes semantic drift using NLP models, and flags potentially suspicious or high-risk edits.

🔍 **The System Combines**
- `Web scraping` via Wikipedia API
- NLP-based `semantic similarity analysis`
- `Heuristic risk detection` (username + content)
- `Anomaly Detection` (z-score analysis)
- Saves the results to a CSV file
- Cloud persistence with `MongoDB`
- `CI/CD automation` using `GitHub Actions`

---

## 🔧 Use Cases

- Misinformation detection
- Public knowledge auditing
- Historical data integrity
- AI-assisted moderation
- Research on content evolution

---

## 🛠️ Tech Stack

| Purpose             | Tools / Libraries              |
|---------------------|-------------------------------|
| Language            | Python 3.8+                   |
| Web Scraping        | mwparserfromhell              |
| NLP                 | Sentence Transformers         |
| ML                  | Cosine Similarity             |
| Database            | MongoDB                       |
| CI/CD               | GitHub Actions                |
| Containerization    | Docker                        |

---

## 📊 Risk Scoring Logic
Final edit risk is computed using:

**Final Risk** = 
  0.5 × **Semantic Change** +
  0.3 × **Content Risk** +
  0.2 × **Username Risk**

Edits are flagged if:
- Semantic similarity drops significantly
- Risk score crosses threshold

---

## 🚀 How to Run

1. **Clone the Repository**
   ```bash
   git clone https://github.com/SiddheshCodeMaster/InfoGuard-AI.git
   cd InfoGuard-AI

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt

3. **Configure Environment**
   
   Create `.env` file:
   ```env
   MONGODB_URI=your_mongodb_connection_string

4. **Run Locally**
   ```bash
   python services/scraper/wiki_scrapper.py

5. **🐳 Docker Usage**
   ```bash
   docker build -t infoguard-ai .
   docker run --env MONGODB_URI=your_uri infoguard-ai

6. **⏱️ Automated Monitoring**
   
   The system runs automatically every 30 minutes using GitHub    Actions.
   Workflow file:
   ```bash
   .github/workflows/monitor.yml

--- 

## **🔮 Future Enhancements**
  - Real-time alerting system
  - Web dashboard
  - Editor behavior profiling
  - Advanced explainable AI
  - Multilingual monitoring

## **👨‍💻 Author**

Siddhesh Shankar
Data Science | NLP | DevOps | Backend Engineering

Portfolio: https://datasavywithsiddhesh.onrender.com/

### **📜 License**
MIT License
