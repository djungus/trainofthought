# 📬 TrainOfThought

TrainOfThought is a lightweight, zero-dependency, automated newsletter curation system that aggregates your favorite newsletters, news feeds, medical research, and custom deals, curating them using AI and delivering them directly to your inbox twice a week.

Designed specifically for **low-cost (100% free) execution** using GitHub Actions, Google Gemini Free Tier, and Resend or Gmail SMTP.

---

## 📂 Project Structure

```text
trainofthought/
├── .github/
│   └── workflows/
│       └── send_digest.yml     # GitHub Actions twice-weekly runner
├── config.json                 # Curation settings, feeds, and filters
├── curator.py                  # Curation engine python script (zero dependencies)
├── template.html               # Responsive HTML email template
└── README.md                   # Setup instructions (this file)
```

---

## ⚙️ Curation Configuration (`config.json`)

Configure your email address, RSS feed URLs, keyword queries (like Slickdeals, Reddit, or eBay search terms), and exclusions directly in `config.json`.
*   **Hobbies/Deals searches**: Feeds that pull listings from eBay or Slickdeals filtered by your topics (e.g. Celtics merchandise, Pokemon cards, skincare, travel, student deals).
*   **Local News & Newsletters**: Substack/Beehiiv URLs matching your reading subscriptions (e.g. Cate Hall, John/Hank Green, Escaping Flatland).

---

## 🚀 Setting Up Automation (GitHub Actions)

TrainOfThought is designed to run automatically on GitHub Actions on **Tuesdays and Fridays at 9:00 AM EST**.

### Step 1: Create a GitHub Repository
1. Initialize this directory as a git repository and push it to a new private GitHub repository.
   ```bash
   git init
   git add .
   git commit -m "Initialize TrainOfThought"
   git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Configure Secrets
Go to your GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions** and add the following repository secrets:

#### 1. Gemini AI Curation (Free)
*   **`GEMINI_API_KEY`**: Grab a free API key from [Google AI Studio](https://aistudio.google.com/). The free tier permits 15 RPM which is plenty.

#### 2. Email Delivery (Choose Resend OR Gmail SMTP)
*   **Option A: Resend API (Recommended)**
    *   **`RESEND_API_KEY`**: Grab a free API key from [Resend](https://resend.com) (free tier includes 3,000 emails/month).
*   **Option B: Gmail SMTP**
    *   **`SMTP_SERVER`**: `smtp.gmail.com`
    *   **`SMTP_PORT`**: `465`
    *   **`SMTP_USER`**: Your Gmail email address (e.g., `jungd@email.com`).
    *   **`SMTP_PASS`**: An **App Password** generated from Google Account Settings (Security -> 2-Step Verification -> App Passwords). *Do not use your main Gmail password.*

---

## 💻 Running Locally / Dry Run

You can dry run the curation pipeline locally to verify how it compiles and filters without sending an email (or by sending a test email).

1. Open a terminal/command prompt in the `trainofthought` directory.
2. (Optional) Set your API Keys/Credentials as temporary environment variables:
   ```powershell
   # Windows PowerShell
   $env:GEMINI_API_KEY="your-google-api-key"
   $env:RESEND_API_KEY="your-resend-api-key"
   ```
3. Run the script:
   ```bash
   py curator.py
   ```
4. Check the directory for `digest_preview.html` which is a local preview of the newsletter compiled during the run! Open this file in your browser to inspect it.
