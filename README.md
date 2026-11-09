# ⚖️ LexGuard Intelligence
### AI Contract Risk & Compliance Auditor

**LexGuard** is a full-stack legal intelligence platform designed to automate contract reviews, flag critical liabilities (such as broad indemnification and uncapped financial damages), detect missing protective clauses, and provide an interactive AI advisory chat with multi-session history support.

---

## 🚀 Key Features

* **Universal Document Ingestion:** Seamlessly parses `.pdf`, `.docx`, and `.txt` files with fallback OCR support for scanned documents.
* **Automated Risk Evaluation:** Scans clauses, filters out duplicate alerts, and categorizes exposures into High and Medium risk tiers.
* **Interactive Document Reader:** Click on any flagged risk to instantly jump to the corresponding section in the document viewer.
* **Multi-Session AI Chatbot:** Powered by Google Gemini (`gemini-2.5-flash`) with conversation history and a sidebar UI to manage multiple chat sessions.
* **Voice Guidance:** Integrated Text-to-Speech (TTS) audio summaries for accessibility and hands-free review audits.

---

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn, Google GenAI SDK (`google-genai`), PyMuPDF (fitz), python-docx, EasyOCR.
* **Frontend:** React, Vite, Modern CSS (Glassmorphism UI).

---

## ⚙️ Getting Started & Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/vaishnavigupta129/LexGuard-AI-Contract-Analyzer.git](https://github.com/vaishnavigupta129/LexGuard-AI-Contract-Analyzer.git)
cd LexGuard-AI-Contract-Analyzer
