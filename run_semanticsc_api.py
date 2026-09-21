# Semantic Scholar API Multithread without pagination
# Import necessary libraries

import requests
import re
import concurrent.futures
#import sys
# sys.stdout.reconfigure(encoding='utf-8')
#import json
#import time  # Import time module for execution time measuremen
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

#sys.stdout.reconfigure(encoding='utf-8')

# Search keyword
# query = "generative ai"

#timeout = 20
# Semantic Scholar API endpoint
url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"


# Function to check if a URL points to a PDF file
def is_pdf_url(url, timeout=3):
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        #print(f"Skipping invalid URL: {url}")
        return "N/A"
    try:

        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
        }
        response = requests.head(url, allow_redirects=True, timeout=timeout,headers=headers)
        # Cek jika URL langsung mengarah ke PDF
        if 'application/pdf' in response.headers.get('Content-Type', ''):
            return url  # Mengembalikan URL jika itu adalah PDF

        # Jika bukan PDF, ambil isi HTML
        elif 'text/html' in response.headers.get('Content-Type', ''):
            response = requests.get(url, timeout=timeout,headers=headers)
            # Mencari semua tautan PDF menggunakan regex
            pdf_links = re.findall(r'href="([^"]+\.pdf)"', response.text)
            if pdf_links:
                return pdf_links[0]  # Mengembalikan tautan PDF pertama yang ditemukan

            # Alternatif: cari tautan yang mungkin memiliki PDF di dalamnya
            pdf_links_alt = re.findall(r'href=["\']?([^"\'>]+\.pdf)["\']?', response.text)
            if pdf_links_alt:
                return pdf_links_alt[0]  # Mengembalikan tautan PDF pertama yang ditemukan

    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return False


def show_report(paper, pdf_url, pdf_available):
    # Membuat dictionary untuk satu paper
    
    
    publication_venue = paper.get("publicationVenue")

    if publication_venue and (publication_venue.get('type') == 'conference' or publication_venue.get('type') == 'N/A'):
        conference_name = publication_venue.get('name', 'N/A')
        publication_type = publication_venue.get('type', 'N/A')
    else:
        dash_ = "-"
        if isinstance(publication_venue, dict) and publication_venue.get('type') is not None:
            publication_type = 'journal' if publication_venue.get('type') == "journal" else publication_venue.get('type', 'N/A')
            conference_name = dash_
        else:
            # Default values if publication_venue is None or not a dictionary
            publication_type = 'other type'
            conference_name = dash_
                
    
    # Get the journal information (checking for None or invalid data)
    journal = paper.get("journal")
    if isinstance(journal, dict):
        # Safely get the journal name, volume, and pages with default values if not found
        journal_name = journal.get("name", "N/A")
        journal_vol = journal.get("volume", "N/A")
        journal_pages = journal.get("pages", "N/A")
    else:
        # If journal is not a valid dictionary, set values to N/A
        journal_name = "N/A"
        journal_vol = "N/A"
        journal_pages = "N/A"

    # If journal_name, journal_vol, or journal_pages are empty or tuple, replace them with "N/A"
    if not journal_name or isinstance(journal_name, tuple):
        journal_name = "N/A"

    if not journal_vol or isinstance(journal_vol, tuple):
        journal_vol = "N/A"

    if not journal_pages or isinstance(journal_pages, tuple):
        journal_pages = "N/A"
        
    
    doi_=paper.get("externalIds", {}).get("DOI")
    extracted_keywords="N/A"
     
    #abstract=paper.get('abstract')

    #if abstract is None and doi_:  # Hanya jika abstract kosong dan DOI ada
     #   with ThreadPoolExecutor() as executor:
      #      future = executor.submit(requests.get, f"https://api.semanticscholar.org/v1/paper/{doi_}", timeout=10)
       #     response = future.result()

        #    if response.status_code == 200:
         #       abstract = response.json().get('abstract', 'N/A')  # Ambil abstrak dari API
   #else:
    #    abstract=paper.get('abstract')
        
    source = "Semantic Scholar"

  
    report = {
        "Paper Id": paper.get('paperId', 'N/A') if paper.get('paperId') else 'N/A',
        "Title": paper.get('title', 'N/A') if paper.get('title') else 'N/A',
        "Abstract": paper.get('abstract', 'N/A') if paper.get('abstract') else 'N/A',
        "Year": paper.get('year', 'N/A') if paper.get('year') else 'N/A',
        "Authors": ", ".join([author['name'] for author in paper.get('authors', [])]),
        "Citation Count": paper.get('citationCount', 'N/A') if paper.get('citationCount') else 'N/A',
        "Discipline(s)": ", ".join(paper.get("fieldsOfStudy", [])) if isinstance(paper.get("fieldsOfStudy"), list) else "N/A",
        "Document Type": ", ".join(paper.get("publicationTypes", [])) if isinstance(paper.get("publicationTypes", []), list) else "N/A",
        "Journal Name": journal_name,
        "Journal Volume": journal_vol,
        "Journal Pages": journal_pages,
        "Conference Name": conference_name,
        "Publication Type": publication_type,
        "Venue": paper.get('venue', 'N/A') if paper.get("venue") else "N/A",
        "Publication Date": paper.get("publicationDate", "N/A") if paper.get("publicationDate") else "N/A",
        "Is Open Access": "Yes" if paper.get("isOpenAccess", "N/A") == True else "No" if paper.get("isOpenAccess", "N/A") == False else "N/A",
        "Open Access PDF URL": pdf_url,
        "PDF Available": 'Yes' if pdf_available else 'No',
        "URL": paper.get('url', 'N/A'),
        "DOI": doi_,
        "Extracted Keywords": extracted_keywords,
        "Source": source
        #"Corpus ID": paper.get("externalIds", {}).get("CorpusId", "N/A")
    }
    return report




#default = 30
def get_semantic_data(query, time_limit_seconds=30, limit=100):
    start_time = time.time()
    results_list = []

    total_available_pdf1 = 0
    total_available_pdf2 = 0
    successfully_collected = 0


	
    query_params = {
            "query": query,
            "fields": "paperId,title,abstract,year,authors,citationCount,fieldsOfStudy,publicationTypes,journal,venue,publicationVenue,publicationDate,url,openAccessPdf,isOpenAccess,externalIds",
            "limit": limit
        }

    
    next_token = None
    
    while True:
        # Cek batas waktu sebelum request baru
        
        if time.time() - start_time > time_limit_seconds:
            print("Time limit reached. Stopping collection before next batch.")
            break
        
        if next_token:
            query_params["token"] = next_token
        else:
            query_params.pop("token", None)

	
        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
        }

        response = requests.get(url, params=query_params,headers=headers)
	

        if response.status_code != 200:
            print(f"Failed to retrieve data: {response.status_code}")
            break

        data = response.json()
        results = data.get("data", [])
        next_token = data.get("token", None)

        if not results:  # tidak ada hasil lagi
            break

        na_pdf_count_filter_1 = 0
        na_pdf_count_filter_2 = 0

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_pdf_check = {}

            for paper in results:
                if time.time() - start_time > time_limit_seconds:
                    print("Time limit reached. Stopping collection before next batch!!!!.")
                    break

                open_access_pdf = paper.get("openAccessPdf")
                pdf_url = open_access_pdf["url"] if open_access_pdf else None

                if pdf_url:
                    report = show_report(paper, pdf_url, True)
                    results_list.append(report)
                else:
                    na_pdf_count_filter_1 += 1
                    detect_pdf_url = "https://www.semanticscholar.org/reader/" + paper.get("paperId")
                    future = executor.submit(is_pdf_url, detect_pdf_url)
                    future_to_pdf_check[future] = paper

            for future in concurrent.futures.as_completed(future_to_pdf_check):
                paper = future_to_pdf_check[future]
                try:
                    pdf_available2 = future.result()
                    if pdf_available2:
                        report = show_report(paper, pdf_available2, True)
                    else:
                        na_pdf_count_filter_2 += 1
                        report = show_report(paper, "N/A", False)
                    results_list.append(report)
                except Exception as exc:
                    print(f"Error checking {paper.get('paperId', 'N/A')}: {exc}")

        total_available_pdf1 += len(results) - na_pdf_count_filter_1
        total_available_pdf2 += len(results) - na_pdf_count_filter_2
        successfully_collected += len(results)
        



        # Geser ke batch berikutnya
        if not next_token:
            break
        
        #print("total_available_pdf1",total_available_pdf1)
        #print("total_available_pdf2",total_available_pdf2)
        #print("successfully_collected",successfully_collected)



    collection_retrieval = {
        "total_available_pdf1": total_available_pdf1,
        "total_available_pdf2": total_available_pdf2,
        "successfully_collected": successfully_collected
    }

    return results_list, collection_retrieval