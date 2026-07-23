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
    "Data Scientist"
]

def fetch_existing_urls():
    """Fetch existing job URLs to avoid duplicate entries."""
    existing_urls = set()
    has_more = True
    start_cursor = None

    while has_more:
        kwargs = {"database_id": DATABASE_ID, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = notion.databases.query(**kwargs)
        
        for result in response.get("results", []):
            url_prop = result["properties"].get("Apply Link", {}).get("url")
            if url_prop:
                existing_urls.add(url_prop)
                
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
        
    return existing_urls

def push_to_notion(job, existing_urls):
    job_url = job.get("job_url")
    if not job_url or job_url in existing_urls:
        return False  # Skip duplicates

    title = str(job.get("title", "Untitled"))
    company = str(job.get("company", "N/A"))
    description = str(job.get("description", ""))[:1900]  # Notion limit per text block is 2000 chars
    date_posted = str(job.get("date_posted", datetime.now().strftime("%Y-%m-%d")))
    site = str(job.get("site", "Other")).title()

    # Heuristic for experience requirements
    exp_text = "0-2 Years / Entry Level"

    try:
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Job Title": {"title": [{"text": {"content": title}}]},
                "Company": {"rich_text": [{"text": {"content": company}}]},
                "Apply Link": {"url": job_url},
                "Experience": {"rich_text": [{"text": {"content": exp_text}}]},
                "Post Date": {"rich_text": [{"text": {"content": date_posted}}]},
                "Source": {"select": {"name": site}},
                "Job Description": {"rich_text": [{"text": {"content": description}}]},
            }
        )
        print(f"Added: {title} at {company}")
        existing_urls.add(job_url)
        return True
    except Exception as e:
        print(f"Error pushing {title}: {e}")
        return False

def main():
    existing_urls = fetch_existing_urls()
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
                country_indeed="India"  # Change or remove depending on target market
            )

            for _, job in jobs.iterrows():
                push_to_notion(job, existing_urls)

        except Exception as e:
            print(f"Scraping failed for {role}: {e}")

if __name__ == "__main__":
    main()