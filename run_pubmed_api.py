#PubMed Multithread
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree
import re
import sys
import time
import psutil
#import concurrent.futures
#import threading
#import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

start_time = time.time()

sys.stdout.reconfigure(encoding='utf-8')


def is_pdf_url(url, timeout=1):
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        #print(f"Skipping invalid URL: {url}")
        return "N/A"
    #headers = {
     #   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36'
    #}
    try:
        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
        }

        response = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if 'application/pdf' in response.headers.get('Content-Type', ''):
            return url
        elif 'text/html' in response.headers.get('Content-Type', ''):
            response = requests.get(url, timeout=timeout, headers=headers)
            pdf_links = re.findall(r'href="([^"]+\.pdf)"', response.text)
            if pdf_links:
                return pdf_links[0]
            
            pdf_links_alt = re.findall(r'href=["\']?([^"\'>]+\.pdf)["\']?', response.text)
            if pdf_links_alt:
                return pdf_links_alt[0]
    except requests.RequestException:
        return "False"



def search_pubmed(query, max_results):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_url = f"{base_url}esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "relevance",
        "retmode": "xml",
        "email": "tresnamf@gmail.com"
    }
    
    headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    response = requests.get(search_url, params=params, headers=headers)
    if response.status_code == 200:
        tree = ElementTree.fromstring(response.content)
        id_list = [id.text for id in tree.findall(".//Id")]
        return id_list
    else:
        print(f"Error during search: {response.status_code}")
        return []

def fetch_pubmed_article_in_batches(id_list, batch_size=200):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    fetch_url = f"{base_url}efetch.fcgi"
    for i in range(0, len(id_list), batch_size):
        batch_ids = id_list[i:i + batch_size]
        ids = ",".join(batch_ids)
        params = {
            "db": "pubmed",
            "id": ids,
            "retmode": "xml",
            "email": "tresnamf@gmail.com"
        }
        
        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
        }

        response = requests.get(fetch_url, params=params, headers=headers)
        if response.status_code == 200:
            yield ElementTree.fromstring(response.content)
        else:
            print(f"Error fetching articles: {response.status_code}")
            break
        

def get_total_cited(pmid):
    url = f"https://pubmed.ncbi.nlm.nih.gov/?linkname=pubmed_pubmed_citedin&from_uid={pmid}"
    headers = {
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        results_amount = soup.find('div', class_='results-amount')

        if results_amount:
            total_cited = results_amount.find('span', class_='value').text.strip()
            return total_cited
        else:
            return 'N/A'
    else:
        #print(f"Error: {response.status_code}")
        return 'N/A'


def is_open_access(article):
    pmcid = article.find(".//ArticleId[@IdType='pmc']")
    return pmcid is not None

na_pdf_count_filter_1 = 0
na_pdf_count_filter_2 = 0

processed_pmids = set()

def process_article_details(article):
    
    
    global na_pdf_count_filter_1, na_pdf_count_filter_2,processed_pmids
    
    
    
    #lock = threading.Lock()
    # Extract article details
    pmid = article.find(".//PMID").text if article.find(".//PMID") is not None else "N/A"
    
    # Skip if this pmid has already been processed
    if pmid in processed_pmids:
        print(f"Duplicate article found with PMID {pmid}. Skipping.")
        return
    processed_pmids.add(pmid)  # Add the pmid to the set
    
    
    
    article_title = article.find(".//ArticleTitle").text if article.find(".//ArticleTitle") is not None else "N/A"
    abstract = article.find(".//AbstractText").text if article.find(".//AbstractText") is not None else "N/A"
    # Bersihkan karakter non-printable
    #clean_raw_abstract = re.sub(r'[^\x20-\x7E\n]', '', raw_abstract)
    # Normalisasi Unicode
    #abstract = unicodedata.normalize("NFKD", clean_raw_abstract).strip()

    authors = article.findall(".//Author")
    authors_names = []
    for author in authors:
        last_name = author.find('LastName') 
        initials = author.find('Initials')

        last_name_text = last_name.text if last_name is not None else 'Unknown'
        initials_text = initials.text if initials is not None else ''

        authors_names.append(f"{last_name_text} {initials_text}")


    cited_articles = get_total_cited(pmid)
    mesh_terms = article.findall(".//MeshHeadingList/MeshHeading/DescriptorName")
    document_type = article.find(".//PublicationType").text if article.find(".//PublicationType") is not None else "N/A"
    journal_title = article.find(".//Journal/Title").text if article.find(".//Journal/Title") is not None else "N/A"
    journal_volume = article.find(".//JournalIssue/Volume").text if article.find(".//JournalIssue/Volume") is not None else "N/A"
    journal_pages = article.find(".//Pagination/MedlinePgn").text if article.find(".//Pagination/MedlinePgn") is not None else "N/A"
    
    
    pub_year = article.find(".//PubDate/Year").text if article.find(".//PubDate/Year") is not None else "N/A"
    
    # Month mapping for formatting the publication date
    month_mapping = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", "Jul": "07",
                     "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
    month_name = article.find(".//PubDate/Month").text if article.find(".//PubDate/Month") is not None else "01"
    pub_month = month_mapping.get(month_name, "01")
    pub_day = article.find(".//PubDate/Day").text if article.find(".//PubDate/Day") is not None else "01"
    pub_date = f"{pub_year}-{pub_month.zfill(2)}-{pub_day.zfill(2)}" if pub_year != "N/A" else "N/A"
    
    # Extract DOI
    doi = article.find(".//ArticleIdList/ArticleId[@IdType='doi']").text if article.find(".//ArticleIdList/ArticleId[@IdType='doi']") is not None else "N/A"

    if mesh_terms:
        mesh_terms_list = ', '.join([term.text for term in mesh_terms])
        
    else:
        mesh_terms_list = "N/A"
        
    # Publication type logic based on document type
    if 'journal' in document_type.lower():
        dash_ = "-"
        publication_type = "Journal Article"
        conference_name = dash_
        publication_type
        venue = dash_
    

    else:
        n_a = "N/A"
        publication_type = "Other Type"
        conference_name = n_a
        venue = n_a
    
    open_access = is_open_access(article)
    if open_access == True:
        open_access = "Yes"
    else:
        open_access = "No"
        
    
    
    pmc_id = article.findall(".//ArticleIdList/ArticleId[@IdType='pmc']")
    # Pastikan pdf_url selalu terdefinisi, misalnya sebagai "False"
    pdf_url = "False"
    check_pdf_url = "No"
    
    #with lock:  # Ensure that counters are updated safely in a multithreaded environment
    na_pdf_count_filter_1 += 1  # Count for articles with no accessible PDF
    
    if pmc_id:
        #na_pdf_count_filter_3 += 1 
        pmc_id_value = pmc_id[0].text
        
        if pmc_id_value.startswith("PMC"):
            pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id_value}/pdf"
            check_pdf_url = pdf_url
            if check_pdf_url:
                check_pdf_url = "Yes"
            

    else:
        #with lock:  # Ensure this is thread-safe as well
        na_pdf_count_filter_2 += 1  # Count for articles without PMC ID
        pdf_url = "N/A"
        check_pdf_url = "No"
    
    first_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"
    extracted_keywords="N/A"
    source = "PubMed"
 
        
    report = {
        "Paper Id": pmid,
        "Title": article_title,
        "Abstract": abstract,
        "Year": pub_year,
        "Authors": ', '.join(authors_names).encode('utf-8', errors='replace').decode('utf-8'),
        "Citation Count": cited_articles,
        "Discipline(s)": mesh_terms_list,
        "Document Type": document_type,
        "Journal Name": journal_title,
        "Journal Volume": journal_volume,
        "Journal Pages": journal_pages,
        "Conference Name": conference_name,
        "Publication Type": publication_type,
        "Venue": venue,
        "Publication Date": pub_date,
        "Is Open Access": open_access,
        "Open Access PDF URL": pdf_url,
        "PDF Available": check_pdf_url,
        "URL": first_url,
        "DOI": doi,
        "Extracted Keywords": extracted_keywords,
        "Source": source
        
        #"DOI Type": doi_info.get('doi_type', 'N/A')
  
        
    }
    return report



#def display_article_details_multithreaded(articles_batches,reset=1):
    

def get_pubmed_data(query,reset=1):
    global na_pdf_count_filter_1, na_pdf_count_filter_2,processed_pmids
    total_articles_processed=0
    results_list=[]
    
    total_available_pdf1 = 0
    total_available_pdf2 = 0
    #default max_results=2000
    id_list = search_pubmed(query,max_results=2000)
    if id_list:
        articles_batches = fetch_pubmed_article_in_batches(id_list, batch_size=200)
    else:
        articles_batches = []  # Initialize as an empty list if no articles are found
        
    # Process each batch with multithreading
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_article_details, article): article for batch in articles_batches for article in batch}
        
        
        for future in as_completed(futures):
            report = future.result()  # Ensures exception handling
            if report:
                total_articles_processed += 1
                results_list.append(report)



    #print("--------------------------------------------------")
    #print("na_pdf_count_filter_1", na_pdf_count_filter_1)
    total_available_pdf1 = total_articles_processed - na_pdf_count_filter_1
    #print("na_pdf_count_filter_2", na_pdf_count_filter_2)
    total_available_pdf2 = total_articles_processed - na_pdf_count_filter_2
    #print("--------------------------------------------------")
    #print(f"Available PDF Files without improved DOAJ PDF URL: {total_available_pdf1}")
    #print(f"Available PDF Files with improved DOAJ PDF URL: {total_available_pdf2}")
    #print(f"Successfully collected: {total_articles_processed} paper(s)")  
    
    if reset==1:
        na_pdf_count_filter_1 = 0
        na_pdf_count_filter_2 = 0
        processed_pmids = set()
        
   
        
    collection_retrieval = {
        
        "total_available_pdf1": total_available_pdf1,
        "total_available_pdf2": total_available_pdf2,
        "successfully_collected": total_articles_processed
        }
    
    print("total_available_pdf1",total_available_pdf1)
    print("total_available_pdf2",total_available_pdf2)
    print("successfully_collected",total_articles_processed)

    return results_list, collection_retrieval
        


