import requests
import pandas as pd
import time

def get_openalex_data(query, per_page=100, time_limit_seconds=30):
    base_url = "https://api.openalex.org/works"
    headers = {
  
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }
    all_results = []
    start_time = time.time()
    page = 1

    while True:
        # Stop jika sudah melewati batas waktu
        if time.time() - start_time > time_limit_seconds:
            #print("[OpenAlex] Time limit reached. Stopping collection.")
            break

        params = {
            "search": query,
            "page": page,
            "per_page": per_page
        }

        try:
            res = requests.get(base_url, params=params, headers=headers)
            if res.status_code != 200:
                #print(f"[OpenAlex] Request failed (status {res.status_code}) on page {page}")
                break
            data = res.json()
        except Exception as e:
            #print(f"[OpenAlex] Exception on page {page}: {e}")
            break

        results = data.get("results", [])
        if not results:
            #print("[OpenAlex] No more results. Stopping.")
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
        
        
        for w in results:
            
            item_type = w.get("raw_type", "N/A")
            
            if item_type in EXCLUDED_TYPES:
                continue
            paper_id = w.get("id", "N/A")
            title = w.get("title", "N/A")
            if (title is None or (isinstance(title, float) and pd.isna(title)) or title == ""):
                title = "N/A"
            else:
                title = title
            
            
            abstract_index = w.get("abstract_inverted_index")

            # reconstruct
            if abstract_index:
                max_index = max(i for idxs in abstract_index.values() for i in idxs) + 1
                words = [""] * max_index
                for word, idxs in abstract_index.items():
                    for i in idxs:
                        words[i] = word
                abstract = " ".join(words)
            else:
                abstract = "N/A"
            
            year = w.get("publication_year", "N/A")
            authors_list = [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author") and a["author"].get("display_name")]
            authors = ", ".join(authors_list) if authors_list else "N/A"
            if w.get("primary_topic"):
                topic = w["primary_topic"].get("display_name", "N/A")
                subfield = w["primary_topic"].get("subfield", {}).get("display_name", "N/A")
                field = w["primary_topic"].get("field", {}).get("display_name", "N/A")
                domain = w["primary_topic"].get("domain", {}).get("display_name", "N/A")
            else:
                topic = subfield = field = domain = "N/A"

            # Gabungkan semua menjadi satu string
            discipline = f"{topic}, {subfield}, {field}, {domain}"
                        
            journal_info = w.get("primary_location", {}).get("raw_type") or "N/A"
            

            if journal_info == "journal-article":
                document_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                conference_name = "-"
                publication_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                #venue = w.get("event", {}).get("location", "N/A") or "N/A"
            elif journal_info == "proceedings-article":
                document_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                conference_name = w.get("primary_location", {}).get("raw_source_name") or "N/A"
                publication_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                #venue = w.get("event", {}).get("location", "N/A") or "N/A"
            elif journal_info == "book-chapter":
                document_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                conference_name = "-"
                publication_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                #venue = w.get("event", {}).get("location", "N/A")
            else:
                document_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                conference_name = "-"
                publication_type = w.get("primary_location", {}).get("raw_type") or "N/A"
                #venue = w.get("event", {}).get("location", "N/A") or "N/A"
            venue = w.get("host_venue", {}).get("display_name", "N/A") or "N/A"
            journal_name = w.get("primary_location", {}).get("raw_source_name") or "N/A"
            # Volume & pages
            journal_vol = w.get("biblio", {}).get("volume") or "N/A"
            page_start = w.get("biblio", {}).get("first_page")
            page_end = w.get("biblio", {}).get("last_page")

            if page_start and page_end:
                journal_pages = f"{page_start}-{page_end}"
            elif page_start:
                journal_pages = page_start
            elif page_end:
                journal_pages = page_end
            else:
                journal_pages = "N/A"
            
            citation_count = w.get("cited_by_count", 0)
            publication_date = w.get("publication_date", "N/A")
            
            pdf_url = w.get("primary_location", {}).get("pdf_url", "N/A")
            if pdf_url:
                pdf_url = pdf_url
                pdf_available = "Yes"
            else:
                pdf_url = "N/A"
                pdf_available = "No"
            
            is_oa =  w.get("primary_location", {}).get("is_oa", False) 
            is_open_access = "Yes" if is_oa else "No"
                
            extracted_keywords="N/A"    
            main_url = w.get("primary_location", {}).get("landing_page_url")
            if not main_url:
                main_url = w.get("primary_location", {}).get("doi", "N/A")

   
            doi = w.get("ids", {}).get("doi", "N/A").replace("https://doi.org/", "") if w.get("ids") else "N/A"
            source = "OpenAlex"

            
        
            report  = {
        
                "Paper Id": paper_id,
                "Title": title,
                "Abstract": abstract,
                "Year": year,
                "Authors": authors,
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
                "DOI": doi,
                "Extracted Keywords": extracted_keywords,
                "Source": source
            }
            
            all_results.append(report)

        #print(f"[OpenAlex] Page {page} collected ({len(results)} papers)")

        page += 1  # next page
        time.sleep(1)  # polite delay

    # Deduplication
    all_results = pd.DataFrame(all_results)
    all_results = all_results.drop_duplicates(subset=["Title", "Authors"], keep="last")
    all_results = all_results.dropna(subset=["Title"])
    all_results = all_results.to_dict(orient="records")

    # Collection statistics

    count_open_access = sum(
    1 for paper in all_results
    if paper.get("Is Open Access") == "Yes"
    )
    

    collection_retrieval = {
        "total_available_pdf1": count_open_access,
        "total_available_pdf2": count_open_access,
        "successfully_collected": len(all_results)
    }
    
    return all_results, collection_retrieval