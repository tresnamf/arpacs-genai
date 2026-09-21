import requests
import re
import time

def format_date_ymd(date_parts):
    """
    date_parts: list seperti [[YYYY, MM, DD]] dari Crossref
    return: string 'YYYY-MM-DD' atau 'N/A'
    """
    if not date_parts or not date_parts[0]:
        return "N/A"

    parts = date_parts[0]

    year = parts[0] if len(parts) > 0 and parts[0] else None
    month = parts[1] if len(parts) > 1 and parts[1] else 1
    day = parts[2] if len(parts) > 2 and parts[2] else 1

    if not year:
        return "N/A"

    return f"{year:04d}-{month:02d}-{day:02d}"

 
def get_wos_data(query, api_key="", count=25, time_limit_seconds=30):
    
    url = "https://api.clarivate.com/apis/wos-starter/v1/documents"

    headers = {
        "X-ApiKey": api_key,
        "Accept": "application/json"
    }

    params = {
        "q": f"TS={query}",
        "db": "WOS",
        "limit": count,
        "page": 1
    }

    start_time = time.time()
    while True:
        if time.time() - start_time > time_limit_seconds:
            print("Time limit reached. Stopping collection.")
            break

        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

        all_results = []



        for hit in data.get("hits", []):
            #print(json.dumps(hit, indent=2))

            paper_id = hit.get("uid", "N/A").replace("WOS:", "")
            # ---- Basic identifiers ----
            doi = hit.get("identifiers", {}).get("doi", "N/A")


            if doi != "N/A":
                try:
                    cr_url = f"https://api.crossref.org/works/{doi}"
                    cr_r = requests.get(cr_url, timeout=3)

                    if cr_r.status_code == 200:
                        cr_item = cr_r.json().get("message", {})

                        # Abstract
                        abstract = cr_item.get("abstract", "N/A")
                        if abstract != "N/A":
                            abstract = re.sub("<[^>]+>", "", abstract).strip()

                        # Discipline / subject
                        subjects = ", ".join(cr_item.get("subject", [])) or "N/A",
                        if subjects:
                            discipline = ", ".join(subjects)

                        
                        # ---- Citation count ----
                        citation_counts = {
                            c.get("db"): c.get("count", 0)
                            for c in hit.get("citations", [])
                        }

                        citation_count_wos = citation_counts.get("WOS", 0)
                        if citation_count_wos == 0:
                            citation_count = cr_item.get("is-referenced-by-count", "N/A")
                            
                        # Year
                        issued = cr_item.get("issued", {}).get("date-parts", [[None]])
                        year = issued[0][0] if issued and issued[0] else "N/A"
                        
                        publication_date = format_date_ymd(issued)
                        
                            
                        pdf_url = "N/A"
                        is_open_access = "No"
                        pdf_available = "No"
                        extracted_keywords="N/A"

                        links = cr_item.get("link", [])
                        if links:
                            # 1️⃣ Prioritas: URL yang mengandung "pdf"
                            pdf_url = next(
                                (link.get("URL") for link in links if "pdf" in link.get("URL", "").lower()),
                                None
                            )
                            
                            if pdf_url:
                                
                                is_open_access = "Yes"
                                pdf_available = "Yes"

                            # 2️⃣ Content-Type = application/pdf
                            elif any(link.get("content-type", "").lower() == "application/pdf" for link in links):
                                pdf_url = next(
                                    link.get("URL") for link in links if link.get("content-type", "").lower() == "application/pdf"
                                )
                                is_open_access = "Yes"
                                pdf_available = "Yes"

                            # 3️⃣ Fallback: ambil link pertama (tanpa klaim PDF)
                            else:
                                pdf_url = links[0].get("URL", "N/A")
                                is_open_access = "No"
                                pdf_available = "No"

                                # ✅ Jika main_url mengandung ".pdf", klaim PDF
                                if ".pdf" in main_url.lower():
                                    pdf_url = main_url
                                    is_open_access = "Yes"
                                    pdf_available = "Yes"
                                    
                        elif ".pdf" in main_url.lower():
                            pdf_url = main_url
                            is_open_access = "Yes"
                            pdf_available = "Yes"
                    
                except Exception:
                    pass


            title = hit.get("title", "N/A")


            # ---- Year & publication date ----
            #year = hit.get("source", {}).get("publishYear", "N/A")
            #publish_month = hit.get("source", {}).get("publishMonth")
            #publication_date = f"{year}-{publish_month}" if publish_month else str(year)

            # ---- Authors ----
            authors = [
                a.get("displayName")
                for a in hit.get("names", {}).get("authors", [])
                if a.get("displayName")
            ]

            

            # ---- Document & publication types ----
            document_type = ", ".join(hit.get("types", [])) or "N/A"
            publication_type = ", ".join(hit.get("sourceTypes", [])) or "N/A"

            # ---- Journal / venue ----
            journal_name = hit.get("source", {}).get("sourceTitle", "N/A")
            journal_vol = hit.get("source", {}).get("volume", "N/A")

            pages = hit.get("source", {}).get("pages", {})
            journal_pages = pages.get("range") or "N/A"

            if publication_type == "Proceedings Paper":
                conference_name = journal_name
            else:
                conference_name = "N/A"
                
            venue = "N/A"


            # ---- URLs ----
            main_url = hit.get("links", {}).get("record", "N/A")

            # ---- Keywords ----
            extracted_keywords = ", ".join(
                hit.get("keywords", {}).get("authorKeywords", [])
            )
            extracted_keywords = re.sub(r"</?italic>", "", extracted_keywords)
            
            source= "WoS"

            report = {
                "Paper Id": paper_id,
                "Title": title,
                "Abstract": abstract,
                "Year": year,
                "Authors": ", ".join(authors),
                "Citation Count": citation_count,
                "Discipline(s)": discipline,
                "Document Type": document_type,
                "Journal Name": journal_name,
                "Journal Volume": journal_vol,
                "Journal Pages": journal_pages,
                "Conference Name": conference_name,
                "Publication Type": publication_type,
                "Venue": venue,
                "Publication Date": publication_date,
                "Is Open Access": is_open_access,
                "Open Access PDF URL": pdf_url,
                "PDF Available": pdf_available,
                "URL": main_url,
                "Extracted Keywords": extracted_keywords,
                "DOI": doi,
                "Source": source
            }

            all_results.append(report)

    # Collection statistics
    count_open_access = sum(
        1 for p in all_results if p["Is Open Access"] == "Yes"
    )

    collection_retrieval = {
        "total_available_pdf1": count_open_access,
        "total_available_pdf2": count_open_access,
        "successfully_collected": len(all_results)
    }

    return all_results, collection_retrieval