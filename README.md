# Academic Summarizer

An AI-powered Django web application that summarizes academic papers using Groq + Llama 3.1. Upload a PDF and receive a structured five-section summary — Abstract, Key Points, Methodology, Results, and Conclusion — in seconds.

## Features

- **Drag-and-drop PDF upload** with file validation
- **Automatic text extraction** via pdfplumber (primary) + PyPDF2 (fallback)
- **Groq AI summarization** (`llama-3.1-70b-versatile`) — extremely fast LPU inference
- **Five-section structured summary**: Abstract, Key Points, Methodology, Results, Conclusion
- **Export** summaries as PDF (ReportLab) or Word (python-docx)
- **Summary history** with search and pagination
- **User authentication** — register, login, per-user paper isolation
- **Admin panel** for papers and summaries
- **Responsive Bootstrap 5 UI** with drag-and-drop, dark navbar, mobile-friendly

## Quick Start

### 1. Clone and set up

```bash
git clone <repo-url>
cd academic_summarizer
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set:
#   SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
#   GROQ_API_KEY=<your key from https://console.groq.com>
```

**Getting a Groq API key (free):**
1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign in with your Google or GitHub account
3. Navigate to **API Keys** → **Create API Key**
4. Copy the key into your `.env` file

**Free tier:** ~14 400 requests/day · 6 000 tokens/min · no credit card required

### 3. Set up the database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run the development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` — register an account and upload your first paper.

## Docker (Production)

```bash
cp .env.example .env
# Fill in GROQ_API_KEY, SECRET_KEY, POSTGRES_PASSWORD in .env

make build
make up
make superuser
```

Open `http://localhost` (served via Nginx on port 80).

## Docker (Development)

```bash
# Edit .env.dev and set GROQ_API_KEY
make dev
```

Open `http://localhost:8000`.

## Project Structure

```
academic_summarizer/
├── academic_summarizer/    # Django project config (settings, urls, wsgi)
├── papers/                 # Paper upload, storage, PDF extraction
│   ├── models.py           # Paper model
│   ├── services.py         # PDF text extraction (pdfplumber + PyPDF2)
│   ├── views.py            # Upload, list, detail, delete, re-summarize
│   └── forms.py            # Upload + search + registration forms
├── summarizer/             # AI summarization + export
│   ├── models.py           # Summary model (FK → Paper)
│   ├── services.py         # Groq API integration ← core logic
│   ├── views.py            # Summary detail, history, PDF/Word export
│   └── urls.py
├── templates/              # Global templates (base, home, auth)
├── static/                 # CSS + JS
├── media/                  # Uploaded PDFs (gitignored)
├── .env.example
└── requirements.txt
```

## Groq API Integration

| Feature | Detail |
|---|---|
| **Model** | `llama-3.1-70b-versatile` — 70B parameter Llama 3.1, 128K context |
| **Speed** | Groq LPU hardware — typical response in 2–5 seconds |
| **Temperature** | `0.3` — balanced between creativity and precision |
| **Error handling** | `APIStatusError` (429 rate limit, 4xx) and `APIConnectionError` |
| **JSON parsing** | Strips markdown fences + regex fallback |

See `summarizer/services.py` for the full implementation.

## Production Deployment

```bash
# Set in .env:
DEBUG=False
SECRET_KEY=<strong-random-key>
ALLOWED_HOSTS=yourdomain.com
GROQ_API_KEY=<your-key>

# With Docker:
make build && make up && make superuser
```

## Requirements

- Python 3.11+
- Django 5.0+
- Groq API key ([get one free here](https://console.groq.com)) — no credit card required

## License

MIT
