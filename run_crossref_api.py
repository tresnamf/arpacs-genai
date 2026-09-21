import requests
import time
import html
import re
import pandas as pd

import html
import re

import pandas as pd
import html
import re

def clean_abstract(abstract):
    """
    Clean Crossref abstract (HTML/JATS tags) and standardize empty values to 'N/A'.
    """

    # None
    if abstract is None:
        return "N/A"

    # NaN dari pandas
    if isinstance(abstract, float) and pd.isna(abstract):
        return "N/A"

    # jika list (kadang dari API)
    if isinstance(abstract, list):
        abstract = " ".join(map(str, abstract))

    # convert ke string
    abstract = str(abstract).strip()

    # string kosong
    if abstract == "":
        return "N/A"

    # decode HTML entity
    abstract = html.unescape(abstract)

    # hapus tag HTML / JATS
    abstract = re.sub(r"<.*?>", "", abstract)

    abstract = abstract.strip()

    if abstract == "":
        return "N/A"

    return abstract

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


def get_crossref_data(
    query,
    rows=100,
    time_limit_seconds=30
):
    start_time = time.time()
    all_results = []

    base_url = "https://api.crossref.org/works"
    headers = {
  
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }


    cursor = "*"

    while True:

        if time.time() - start_time > time_limit_seconds:
            print("Time limit reached. Stopping collection.")
            break

        params = {
            "query.title": query,   
            "rows": rows,
            "cursor": cursor
        }

        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code != 200:
            print("Request failed:", response.status_code)
            break

        data = response.json()
        items = data.get("message", {}).get("items", [])

        if not items:
            break
        
        EXCLUDED_TYPES = {
        "blog",
        "edited-book",
        "blog-post",
        "collection",
        "dataset",
        "dissertation",
        "other",
        "patent",
        "peer-review",
        "poster",
        "protocol",
        "registered-report",
        "software",
        "standard",
        "web-resource",
        "component",        # ⚠️ supplementary material (.sXXX)
        "posted-content",    # ⚠️ preprint / editorial
        "reference-entry",
        "book-chapter",
        "book",
        "monograph"
        }

        
        for item in items:
            
            doi = item.get("DOI", "N/A")

            item_type = item.get("type", "N/A")

            if item_type in EXCLUDED_TYPES:
                continue
     
            
            title = item.get("title", ["N/A"])[0]
            abstract = clean_abstract(item.get("abstract"))
            
            
            # Year
            issued = item.get("issued", {}).get("date-parts", [[None]])
            year = issued[0][0] if issued and issued[0] else "N/A"

            # Authors
            authors = []
            for a in item.get("author", []):
                name = " ".join(filter(None, [
                    a.get("given"),
                    a.get("family")
                ]))
                authors.append(name)

            journal_info = item.get("type", "N/A")
            

            if journal_info == "journal-article":
                document_type = item.get("type", "N/A")
                conference_name = "-"
                publication_type = item.get("type", "N/A")
                venue = item.get("event", {}).get("location", "N/A")
            elif journal_info == "proceedings-article":
                document_type = item.get("type", "N/A")
                conference_name = item.get("container-title", ["N/A"])[0]
                publication_type = item.get("type", "N/A")
                venue = item.get("event", {}).get("location", "N/A")
            elif journal_info == "book-chapter":
                document_type = item.get("type", "N/A") 
                conference_name = "-"
                publication_type = item.get("type", "N/A")
                venue = item.get("event", {}).get("location", "N/A")
            else:
                document_type = item.get("type", "N/A")
                conference_name = "-"
                publication_type = item.get("type", "N/A")
                venue = item.get("event", {}).get("location", "N/A")

            
    
            # Venue
            journal_name = item.get("container-title", ["N/A"])[0]

            # Volume & pages
            journal_vol = item.get("volume", "N/A")
            journal_pages = item.get("page", "N/A")

            # Citation count
            citation_count = item.get("is-referenced-by-count", "N/A")

            publication_date = format_date_ymd(issued)
            
            main_url=item.get("resource", {}).get("primary", {}).get("URL", "N/A")


                
            """ PDF_PATTERNS = [
            "/pdf",                # umum
            ".pdf",                # umum
            "articlepdf",          # RSC
            "/doi/pdf",            # PNAS, Science
            "fulltext.pdf",        # beberapa OJS
            "/pre/pdf"
            ]

            for link in item.get("link", []):
                url = link.get("URL", "").lower()
                if any(p in url for p in PDF_PATTERNS):
                    pdf_url = link.get("URL")
                    is_open_access = "Yes"
                    pdf_available = "Yes"
                    break
            """
       

            pdf_url = "N/A"
            is_open_access = "No"
            pdf_available = "No"
            extracted_keywords="N/A"
            
            links = item.get("link", [])
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


            if "xml" in pdf_url:
                continue
            if len(title) <20:
                continue
            
            report = {
                "Paper Id": doi,
                "Title": title,
                "Abstract": abstract,
                "Year": year,
                "Authors": ", ".join(authors),
                "Citation Count": citation_count,
                "Discipline(s)": ", ".join(item.get("subject", [])) or "N/A",
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
                "Source": "Crossref"
            }

            all_results.append(report)

        # === DEDUPLIKASI: title sama, authors sama, DOI beda → pertahankan DOI yang dianggap terbaru (lebih besar) ===
        dedup_map = {}

        for paper in all_results:
            
            key = (paper["Title"].lower().strip(), paper["Authors"].lower().strip())
            doi = paper.get("DOI", "").strip()

            if key not in dedup_map:
                dedup_map[key] = paper
                dedup_map[key]["_doi"] = doi  # simpan sementara
            else:
                # Bandingkan DOI, pertahankan yang "lebih besar" sebagai yang terbaru
                if doi > dedup_map[key]["_doi"]:
                    dedup_map[key] = paper
                    dedup_map[key]["_doi"] = doi

        # overwrite hasil dedup
        all_results = [v for v in dedup_map.values()]

        # hapus field sementara
        for p in all_results:
            p.pop("_doi", None)
   
        

        # Update cursor
        cursor = data.get("message", {}).get("next-cursor")
        if not cursor:
            break

        time.sleep(1)  # polite rate limiting

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
