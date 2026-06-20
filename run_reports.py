#!/usr/bin/env python3
"""
Weekly SEO report puller.

Pulls the 6 reports that Google and Bing actually expose to software:
  GSC: Queries (7d, 28d), Pages (7d, 28d), Query+Page (top 20 pages), Sitemaps
  Bing: Query performance (28d), Page performance (28d)

Reports 4, 8, 9 from your list (GSC Indexing detail, Bing Index Coverage,
Bing Site Explorer) have NO export API and must be downloaded by hand.

Outputs land in ./reports/<YYYY-MM-DD>/ as .xlsx files using your naming
convention. The GitHub Action commits that folder back to the repo.
"""

import os
import json
import datetime as dt

import requests
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ============================================================
# CONFIG  --  EDIT THESE TWO LINES
# ============================================================
# Your GSC property, EXACTLY as it appears in Search Console.
#   - Domain property:      "sc-domain:mydeskdoctor.com"
#   - URL-prefix property:  "https://mydeskdoctor.com/"
GSC_SITE = "sc-domain:mydeskdoctor.com"

# Your Bing site, exactly as listed in Bing Webmaster Tools (usually the URL form)
BING_SITE = "https://mydeskdoctor.com/"

TOP_N_PAGES = 20  # for the Query+Page report
# ============================================================

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
TODAY = dt.date.today()
OUTDIR = os.path.join("reports", TODAY.isoformat())
os.makedirs(OUTDIR, exist_ok=True)


def save(df: pd.DataFrame, filename: str):
    """Write a dataframe to xlsx in today's output folder."""
    path = os.path.join(OUTDIR, filename)
    df.to_excel(path, index=False)
    print(f"  saved {filename}  ({len(df)} rows)")


# ------------------------------------------------------------
# GOOGLE SEARCH CONSOLE
# ------------------------------------------------------------
def gsc_service():
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=GSC_SCOPES
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def gsc_query(service, start, end, dimensions, row_limit=25000):
    """Page through the Search Analytics API and return a flat list of rows."""
    out = []
    start_row = 0
    while True:
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "startRow": start_row,
        }
        resp = service.searchanalytics().query(siteUrl=GSC_SITE, body=body).execute()
        rows = resp.get("rows", [])
        out.extend(rows)
        if len(rows) < row_limit:
            break
        start_row += row_limit
    return out


def gsc_rows_to_df(rows, dim_names):
    records = []
    for r in rows:
        rec = {}
        for i, name in enumerate(dim_names):
            rec[name] = r["keys"][i]
        rec["Clicks"] = r.get("clicks", 0)
        rec["Impressions"] = r.get("impressions", 0)
        rec["CTR"] = round(r.get("ctr", 0) * 100, 2)          # as a percentage
        rec["Position"] = round(r.get("position", 0), 1)
        records.append(rec)
    return pd.DataFrame(records)


def run_gsc():
    print("Google Search Console...")
    svc = gsc_service()
    end = TODAY - dt.timedelta(days=2)   # GSC data lags ~2 days
    start_7 = end - dt.timedelta(days=6)
    start_28 = end - dt.timedelta(days=27)

    # 1 & 2: Queries and Pages, 7d + 28d
    save(gsc_rows_to_df(gsc_query(svc, start_7, end, ["query"]), ["Query"]),
         "GSC_Queries_7Days.xlsx")
    save(gsc_rows_to_df(gsc_query(svc, start_28, end, ["query"]), ["Query"]),
         "GSC_Queries_28Days.xlsx")
    save(gsc_rows_to_df(gsc_query(svc, start_7, end, ["page"]), ["Page"]),
         "GSC_Pages_7Days.xlsx")
    pages_28 = gsc_rows_to_df(gsc_query(svc, start_28, end, ["page"]), ["Page"])
    save(pages_28, "GSC_Pages_28Days.xlsx")

    # 3: Query + Page for top N pages (by clicks over 28d)
    top_pages = set(
        pages_28.sort_values("Clicks", ascending=False)
        .head(TOP_N_PAGES)["Page"].tolist()
    )
    qp = gsc_rows_to_df(
        gsc_query(svc, start_28, end, ["page", "query"]), ["Page", "Query"]
    )
    qp = qp[qp["Page"].isin(top_pages)].sort_values(
        ["Page", "Clicks"], ascending=[True, False]
    )
    save(qp, "GSC_Query_Page_Report.xlsx")

    # 5: Sitemaps
    sm = svc.sitemaps().list(siteUrl=GSC_SITE).execute().get("sitemap", [])
    sm_records = []
    for s in sm:
        sm_records.append({
            "Sitemap": s.get("path"),
            "Type": s.get("type"),
            "LastSubmitted": s.get("lastSubmitted"),
            "LastDownloaded": s.get("lastDownloaded"),
            "IsPending": s.get("isPending"),
            "IsSitemapsIndex": s.get("isSitemapsIndex"),
            "Warnings": s.get("warnings"),
            "Errors": s.get("errors"),
        })
    save(pd.DataFrame(sm_records), "GSC_Sitemap_Report.xlsx")


# ------------------------------------------------------------
# BING WEBMASTER TOOLS
# ------------------------------------------------------------
BING_BASE = "https://ssl.bing.com/webmaster/api.svc/json"


def bing_call(method):
    key = os.environ["BING_API_KEY"]
    url = f"{BING_BASE}/{method}?apikey={key}&siteUrl={BING_SITE}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json().get("d", [])


def bing_ms_to_date(s):
    # Bing returns dates like "/Date(1399100400000)/"
    ms = int(s.replace("/Date(", "").replace(")/", "").split("-")[0].split("+")[0])
    return dt.datetime.utcfromtimestamp(ms / 1000).date()


def bing_summarize(rows, label_field):
    """Bing returns ~6 months of daily rows. Filter to last 28 days and aggregate."""
    cutoff = TODAY - dt.timedelta(days=28)
    agg = {}
    for row in rows:
        d = bing_ms_to_date(row["Date"])
        if d < cutoff:
            continue
        key = row[label_field]
        a = agg.setdefault(key, {"Clicks": 0, "Impressions": 0, "pos_weighted": 0.0})
        clicks = row.get("Clicks", 0)
        impr = row.get("Impressions", 0)
        # AvgImpressionPosition is historically returned x10 by this API
        pos = row.get("AvgImpressionPosition", 0) / 10.0
        a["Clicks"] += clicks
        a["Impressions"] += impr
        a["pos_weighted"] += pos * impr
    records = []
    for key, a in agg.items():
        impr = a["Impressions"]
        records.append({
            label_field: key,
            "Clicks": a["Clicks"],
            "Impressions": impr,
            "CTR": round(100 * a["Clicks"] / impr, 2) if impr else 0,
            "AvgPosition": round(a["pos_weighted"] / impr, 1) if impr else 0,
        })
    df = pd.DataFrame(records).sort_values("Clicks", ascending=False)
    return df


def run_bing():
    print("Bing Webmaster Tools...")
    save(bing_summarize(bing_call("GetQueryStats"), "Query"),
         "Bing_Search_Performance.xlsx")
    save(bing_summarize(bing_call("GetPageStats"), "Query"),  # Bing labels the URL field "Query"
         "Bing_Page_Performance.xlsx")


# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"Run date: {TODAY}  ->  {OUTDIR}\n")
    try:
        run_gsc()
    except Exception as e:
        print(f"  GSC FAILED: {e}")
    try:
        run_bing()
    except Exception as e:
        print(f"  Bing FAILED: {e}")
    print("\nDone. Manual-only this week: GSC Indexing report, "
          "Bing Index Coverage, Bing Site Explorer.")
