import requests
import pandas as pd
import uuid
import time

def get_scopus_data(query, api_key="", count=25, time_limit_seconds=30):

    url = "https://api.elsevier.com/content/search/scopus"
    headers = {"X-ELS-APIKey": api_key}
    
    all_results = []
    start_time = time.time()
    start_index = 0
    
    while True:
        if time.time() - start_time > time_limit_seconds:
            print("Time limit reached. Stopping collection.")
            break
        
        params = {
            "query": query,
            "count": count,
            "start": start_index
        }
        
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            print("Error:", r.status_code, r.text)
            break
        
        data = r.json()
        entries = data.get("search-results", {}).get("entry", [])
        if not entries:
            break
        
        for e in entries:
            
            if e.get("pii", "N/A") == "N/A":
                continue
            
            paper_id = e.get("dc:identifier").replace("SCOPUS_ID:", "")
            title = e.get("dc:title", "N/A")
            
            publication_date = e.get("prism:coverDate", "N/A")
            year = publication_date.split("-")[0] if publication_date != "N/A" else "N/A"
            #authors = e.get("dc:creator", "N/A")
            
            authors_list = e.get("author", [])

            if authors_list:
                authors = ", ".join(a.get("authname", "") for a in authors_list)
            else:
                authors = e.get("dc:creator", "N/A")
            
            citation_count = e.get("citedby-count", "N/A")
            abstract = "N/A"  # Search API tidak menyediakan abstract
            discipline = "N/A"  # Tidak ada di API search
            
            
            document_type = e.get("prism:aggregationType", "N/A")
              
                  
            if document_type == "Journal" or document_type == "Book" or document_type == "Book Series":
                document_type = e.get("prism:aggregationType", "N/A")
                conference_name = "-"
                publication_type = e.get("prism:aggregationType", "N/A")
            elif document_type == "Conference Proceeding": 
                document_type = e.get("prism:aggregationType", "N/A")
                conference_name = e.get("prism:publicationName", "N/A")
                publication_type = e.get("prism:aggregationType", "N/A")
            else:
                document_type = e.get("prism:aggregationType", "N/A")
                conference_name = "-"
                publication_type = e.get("prism:aggregationType", "N/A")

            
            journal_name = e.get("prism:publicationName", "N/A")
            journal_vol = e.get("prism:volume", "N/A")
            journal_pages = e.get("prism:pageRange", "N/A") or "N/A"
            venue = "N/A"
            is_open_access = e.get("openaccessFlag", False)
            
            if is_open_access:
                is_open_access = "Yes"
                pii = e.get("pii", "N/A")
                pdf_url = "https://www.sciencedirect.com/science/article/pii/" + pii +  "/pdf"
                pdf_available = "Yes" 
                main_url = "https://www.sciencedirect.com/science/article/pii/" + pii
                
            else:
                is_open_access = "No"
                pii = e.get("pii", "N/A")
                pdf_url = "N/A"
                pdf_available = "No"
                main_url = "https://www.sciencedirect.com/science/article/pii/" + pii
            

           
            doi = e.get("prism:doi", "N/A")
            extracted_keywords = "N/A"
            source = "Scopus"
            
            report = {
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
        
        start_index += count
    
    
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
