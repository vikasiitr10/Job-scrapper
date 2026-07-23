import os
from datetime import datetime
from jobspy import scrape_jobs
from notion_client import Client

# Initialize Notion Client
notion = Client(auth=os.environ.get("NOTION_TOKEN"))
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

# Keywords targeted for freshers / < 2 years experience
ROLES = [
    "Data Analyst",
    "Business Analyst",
    "Product Analyst",
    "Associate Product Manager",
    "APM",
    "AI Engineer",
    "Data Scientist",
]


def resolve_data_source_id(database_id: str) -> str:
    """
    Notion's 2025-09 API split each database into one or more 'data sources'.
    NOTION_DATABASE_ID (from the page URL) is the *database* id, not the
    data source id. We look it up once here rather than assuming they match.
    """
    db = notion.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise RuntimeError(
            f"No data sources found for database {database_id}. "
            "Check that NOTION_DATABASE_ID is correct and the integration has access."
        )
    # Most databases have exactly one data source unless you've split it.
    return data_sources[0]["id"]


def fetch_existing_urls(data_source_id: str):
    """Fetch existing job URLs to avoid duplicate entries."""
    existing_urls = set()
    has_more = True
    start_cursor = None
    while has_more:
        kwargs = {"data_source_id": data_source_id, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        response = notion.data_sources.query(**kwargs)

        for result in response.get("results", []):
            url_prop = result.get("properties", {}).get("Apply Link", {}).get("url")
            if url_prop:
                existing_urls.add(url_prop)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return existing_urls


def push_to_notion(job, existing_urls, database_id):
    job_url = job.get("job_url")
    if not job_url or job_url in existing_urls:
        return False  # Skip duplicates

    title = str(job.get("title") or "Untitled")
    company = str(job.get("company") or "N/A")
    description = str(job.get("description") or "")[:1900]  # Notion rich_text limit is 2000 chars
    date_posted_raw = job.get("date_posted")
    date_posted = str(date_posted_raw) if date_posted_raw not in (None, "", "nan") else datetime.now().strftime("%Y-%m-%d")
    site = str(job.get("site") or "Other").title()

    # Heuristic for experience requirements
    exp_text = "0-2 Years / Entry Level"

    try:
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Job Title": {"title": [{"text": {"content": title}}]},
                "Company": {"rich_text": [{"text": {"content": company}}]},
                "Apply Link": {"url": job_url},
                "Experience": {"rich_text": [{"text": {"content": exp_text}}]},
                "Post Date": {"date": {"start": date_posted}},
                "Source": {"select": {"name": site}},
                "Job Description": {"rich_text": [{"text": {"content": description}}]},
            },
        )
        print(f"Added: {title} at {company}")
        existing_urls.add(job_url)
        return True
    except Exception as e:
        print(f"Error pushing {title}: {e}")
        return False


def main():
    if not DATABASE_ID:
        raise RuntimeError("NOTION_DATABASE_ID environment variable is not set.")

    data_source_id = resolve_data_source_id(DATABASE_ID)
    existing_urls = fetch_existing_urls(data_source_id)
    print(f"Found {len(existing_urls)} existing jobs in Notion.")

    for role in ROLES:
        print(f"Scraping for: {role}...")
        try:
            # Scrape last 3 hours of posts to catch fresh listings
            jobs = scrape_jobs(
                site_name=["linkedin", "naukri", "indeed", "google"],
                search_term=f"{role} junior entry level",
                results_wanted=15,
                hours_old=3,
                country_indeed="India",  # Change or remove depending on target market
            )
            if jobs is None or jobs.empty:
                print(f"No results for: {role}")
                continue
            for _, job in jobs.iterrows():
                push_to_notion(job, existing_urls, DATABASE_ID)
        except Exception as e:
            print(f"Scraping failed for {role}: {e}")


if __name__ == "__main__":
    main()
