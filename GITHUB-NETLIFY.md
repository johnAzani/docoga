# GitHub → Netlify — Step-by-Step Connection Guide

**Why this way?** Once connected, every change you push to GitHub deploys to
your live site automatically. Edit a price on your phone via github.com →
site updates in ~30 seconds. No commands needed ever again.

**What you need:** the file `docoga-github-repo.zip` (in this workspace —
download it), a free GitHub account, a free Netlify account.

---

## Step 1 — Get the files onto your computer

1. Download **`docoga-github-repo.zip`** from this workspace.
2. Unzip it (right-click → Extract). You get a folder called `docoga`.

## Step 2 — Put the code on GitHub (choose ONE path)

### Path A — GitHub website only (no software, easiest) ✅

1. Log in at **github.com** → click **+** (top right) → **New repository**
2. Repository name: `docoga` · Visibility: **Private** ✅ → **Create repository**
3. On the next screen click **"uploading an existing file"**
4. Open your unzipped `docoga` folder and drag **everything INSIDE it**
   (site folder, worker folder, the .md files, netlify.toml, .gitignore)
   into the GitHub upload area.
   ⚠️ Drag the *contents* of the docoga folder — not the folder itself.
5. Click **Commit changes**.

*If `.gitignore` won't drag (hidden-file issues on Mac), skip it — then on
GitHub: Add file → Create new file → name it `.gitignore` → paste:*

```
unlock-codes.txt
.code_hashes.js
.DS_Store
node_modules/
```

### Path B — GitHub Desktop (free app, still zero commands)

1. Install **GitHub Desktop** (desktop.github.com) and log in.
2. File → **Add local repository…** → choose your unzipped `docoga` folder →
   it says "this is not a repository" → click **create a repository** →
   keep the name `docoga` → **Create repository**
3. Click **Publish repository** → keep **Private** ✅ → Publish.

### Path C — Command line (if you're comfortable with git)

```bash
cd docoga
git init
git add .
git commit -m "DocOga v1.2 — production launch"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/docoga.git
git push -u origin main
```

## Step 3 — Connect Netlify (2 minutes)

1. Go to **netlify.com** → sign up **using GitHub** (one click, no new password)
2. Dashboard → **Add new site** → **Import an existing project**
3. Choose **GitHub** → authorize Netlify → select the **docoga** repository
4. The settings are **auto-filled from `netlify.toml`**:
   - Branch: `main` · Build command: *(empty)* · Publish directory: `site`
   (If ever asked manually: publish directory = **`site`**)
5. Click **Deploy** ⏱️
6. In under a minute you're live at something like
   `https://docoga.netlify.app` — open it on your phone and test all 4 tools.

## Step 4 — Connect your domain (after you buy docoga.top)

1. Netlify → your site → **Domain management** → **Add a domain** →
   enter `docoga.top`
2. Netlify shows you the exact DNS records to set (usually an **A record**
   for `@` and a **CNAME** for `www`)
3. Go to wherever you bought the domain (Truehost/Whogohost/Namecheap) →
   DNS settings → enter exactly what Netlify showed
4. Wait for DNS (10 minutes to a few hours) → HTTPS padlock is issued
   **automatically and free** by Netlify

## Step 5 — The daily workflow (this is the good part)

- Change something on **github.com** → open any file → ✏️ pencil icon →
  edit → Commit → **live in ~30 seconds**
- Or edit locally and push via GitHub Desktop
- Netlify free plan: 100GB bandwidth/month — thousands of visitors daily

## Security rules

1. **Repository stays PRIVATE** — it contains your business plan and guides.
2. **`unlock-codes.txt` is never in the repo** (gitignored + excluded from the
   zip). Your ₦374k code inventory lives only on your own computer/phone.
3. Payment secret keys (Flutterwave) go ONLY into Cloudflare Worker secrets —
   never into GitHub, never into Netlify.
4. Netlify publishes **only the `site/` folder** — your private files in the
   repo (PLAN.md etc.) are never exposed by the website.

## After you're live

Return to `DEPLOY.md`: Flutterwave payment link (Step 3) → Worker secrets
(AUTOMATE.md) → the 4 config lines in `site/index.html` → ₦100 end-to-end
test → final checklist → launch. 🚀
