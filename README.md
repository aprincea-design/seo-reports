# Weekly SEO Report Bot

Automatically pulls the SEO reports that Google and Bing expose to software,
every Monday morning, and saves them into the `reports/<date>/` folder of this
repo. No computer needs to be on.

## What it does automatically
- `GSC_Queries_7Days.xlsx`, `GSC_Queries_28Days.xlsx`
- `GSC_Pages_7Days.xlsx`, `GSC_Pages_28Days.xlsx`
- `GSC_Query_Page_Report.xlsx` (top 20 pages)
- `GSC_Sitemap_Report.xlsx`
- `Bing_Search_Performance.xlsx`
- `Bing_Page_Performance.xlsx`

## What you STILL download by hand each week (no API exists for these)
These have no export API. Budget ~5 minutes:
- **GSC Indexing → Pages report** → save as `GSC_Indexing_Report.xlsx`
- **Bing Index Coverage** → save as `Bing_Index_Coverage.xlsx`
- **Bing Site Explorer** → save as `Bing_Site_Explorer.xlsx`
Drop those into the same `reports/<date>/` folder so every week's set is complete.

---

## One-time setup

### 1. Google service account (lets the bot read GSC)
1. console.cloud.google.com → new project "seo-reports".
2. Enable the **Google Search Console API**.
3. Credentials → Create Credentials → **Service account** → create.
4. Open it → Keys → Add Key → **JSON**. A file downloads (keep it secret).
5. Copy the `client_email` value from inside that JSON.
6. In Search Console → your property → Settings → Users and permissions →
   add that email with **Full** access. (Without this step the bot sees nothing.)

### 2. Bing API key
Bing Webmaster Tools → Settings → **API access** → generate a key.

### 3. Put the secrets in GitHub
Repo → Settings → Secrets and variables → Actions → New repository secret:
- `GSC_SERVICE_ACCOUNT_JSON` = the entire contents of the downloaded JSON file
- `BING_API_KEY` = your Bing key

### 4. Edit two lines in `run_reports.py`
Set `GSC_SITE` and `BING_SITE` to your exact property strings (see comments in the file).

### 5. Test it
Repo → Actions tab → "Weekly SEO Reports" → **Run workflow**.
Watch the log. When it finishes, a `reports/<today>/` folder appears with the files.
After that it runs itself every Monday.

## Getting the files off GitHub
- Browse/download any file directly on github.com, OR
- Install GitHub Desktop and "clone" the repo to a folder on your computer — it
  syncs automatically, so the reports show up in a local folder you can point
  Google Drive/Dropbox at.
