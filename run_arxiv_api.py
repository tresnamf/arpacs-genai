import requests
import xml.etree.ElementTree as ET
import json
import time

#default time_limit_seconds=30
def get_arxiv_data(query, max_results=100, time_limit_seconds=30):
    start_time = time.time()
    start = 0
    all_results = []
    
    # Load kategori arXiv sekali saja
    with open("arxiv_categories_full.json", "r", encoding="utf-8") as f:
        category_mapping = json.load(f)


    # Ambil totalResults dari API
    url_total = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=1"
    headers = {
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    response_total = requests.get(url_total, headers=headers)
    root_total = ET.fromstring(response_total.content)
    total_results = int(root_total.find('{http://a9.com/-/spec/opensearch/1.1/}totalResults').text)
    print(f"Total results for query '{query}': {total_results}")

    increment_options = list(range(1, 11))  # Increment 1-10 untuk batch kosong

    while start < total_results:
        
        # Cek batas waktu
        if time.time() - start_time > time_limit_seconds:
            print("Time limit reached. Stopping collection.")
            break
        
        url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start={start}&max_results={max_results}"
        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to retrieve data at start={start}: {response.status_code}")
            start += max_results
            continue

        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)

        if not entries:
            # Batch kosong → geser offset sedikit
            for inc in increment_options:
                start += inc
                print(f"No entries at start={start}. Trying next offset...")
                url_retry = f"http://export.arxiv.org/api/query?search_query=all:{query}&start={start}&max_results={max_results}"
                headers = {
                "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
                }

                response_retry = requests.get(url_retry, headers=headers)
                root_retry = ET.fromstring(response_retry.content)
                entries_retry = root_retry.findall('atom:entry', ns)
                if entries_retry:
                    entries = entries_retry
                    break
            else:
                print("No entries found after trying increments 1-10. Stopping.")
                break

        for entry in entries:
            paper_id = entry.find('atom:id', ns).text.strip().split('/')[-1]
            title = entry.find('atom:title', ns).text.strip()
            abstract = entry.find('atom:summary', ns).text.strip()
            updated = entry.find('atom:updated', ns).text.strip()
            year = updated[:4] if updated else 'N/A'
            authors = [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)]
            citation_count = "N/A"

            categories = [tag.attrib['term'] for tag in entry.findall('atom:category', ns)]
            mapped_labels = [category_mapping.get(tag, "Unknown Category") for tag in categories]

            document_ref = entry.find('{http://arxiv.org/schemas/atom}journal_ref')
            if document_ref is not None and document_ref.text.strip():
                document_type = "Post-print"
                publication_type = "Post-print"
            else:
                document_type = "Pre-print"
                publication_type = "Pre-print"

            journal_name = "N/A"
            journal_vol = "N/A"
            journal_pages = "N/A"
            conference_name = "N/A"
            venue = "N/A"
            publication_date = updated

            links = entry.findall('atom:link', ns)
            pdf_url = "N/A"
            for link in links:
                if link.attrib.get('title') == 'pdf':
                    pdf_url = link.attrib.get('href')
                    break
            is_open_access = "Yes" if pdf_url is not None else "No"
            pdf_available = is_open_access

            abs_url = None
            for link in entry.findall('atom:link', ns):
                if link.attrib.get('rel') == 'alternate' and link.attrib.get('type') == 'text/html':
                    abs_url = link.attrib.get('href')
                    break
            first_url = abs_url

            arxiv_id_with_version = paper_id.split('/')[-1]
            arxiv_id = arxiv_id_with_version.split('v')[0]
            doi_ = f"10.48550/arXiv.{arxiv_id}"
            extracted_keywords = "N/A"
            source = "arXiv"

            report = {
                "Paper Id": paper_id,
                "Title": title,
                "Abstract": abstract,
                "Year": year,
                "Authors": ", ".join(authors),
                "Citation Count": citation_count,
                "Discipline(s)": ", ".join(mapped_labels),
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
                "URL": first_url,
                "DOI": doi_,
                "Extracted Keywords": extracted_keywords,
                "Source": source
            }

            all_results.append(report)
        

        start += max_results
        time.sleep(3)  # rate limit

    # Hitung statistik
    count_open_access = sum(1 for paper in all_results if paper.get("Is Open Access") == "Yes")
    collection_retrieval = {
        "total_available_pdf1": count_open_access,
        "total_available_pdf2": count_open_access,
        "successfully_collected": len(all_results)
    }

    return all_results, collection_retrieval
