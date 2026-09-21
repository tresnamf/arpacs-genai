# DOAJ multithread with pagination cara 2
import requests
import re
import concurrent.futures
from datetime import datetime
import sys
#import chardet  # for detecting the encoding
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time  # Import time module for execution time measurement
import psutil  # Import psutil for CPU and memory usage monitoring
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter("ignore", InsecureRequestWarning)



sys.stdout.reconfigure(encoding='utf-8')


def is_pdf_url(url, timeout=1):
        # Validasi URL
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        #print(f"Skipping invalid URL: {url}")
        return "N/A"
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        # Cek jika URL langsung mengarah ke PDF
        if 'application/pdf' in response.headers.get('Content-Type', ''):
            return url  # Mengembalikan URL jika itu adalah PDF

        # Jika bukan PDF, ambil isi HTML
        elif 'text/html' in response.headers.get('Content-Type', ''):

            headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
            }

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
        # print(f"An error occurred: {e}")
        return False


# Function to check if the URL is valid
def is_valid_url(url):
        # Validasi URL

    if isinstance(url, str):  # Make sure the URL is a string
        return re.match(r'^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$', url, re.IGNORECASE) is not None
    return False


def get_domain_name(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc


def get_link_ojs_pdf(url,timeout = 1):

    try:
        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
        }

        # Get the HTML content of the page
        response = requests.get(url, timeout=timeout,verify=False, headers=headers)
        response.raise_for_status()  # Check for request errors

        # Search for the '/view/12865/' pattern in the HTML content
        match = re.search(r'(/view/\d+/)', response.text)

        if match:
            # Extract the entire matched string, including '/view/12865/'
            full_view_string = match.group(1)

            # Search for the PDF ID pattern in the same page
            pdf_id = re.search(rf'{re.escape(full_view_string)}(\d+)', response.text)

            if pdf_id:
                # Extract the ID for the PDF link
                pdf_id = pdf_id.group(1)
                pdf_link = f"{url}/{pdf_id}"
                return pdf_link
                #print(f"PDF Link: {pdf_link}")
            else:
                # print("No PDF ID found.")
                return False
        else:
            # print("Pattern '/view/id/' not found in the page.")
            return False

    except requests.RequestException as e:
        # print(f"An error occurred: {e}")
        return False


def get_link_doi_pdf(url):
    # Mengirim permintaan GET ke halaman
    #timeout=5
    headers = {
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    response = requests.get(url,verify=False, headers=headers)

    # Memastikan permintaan berhasil
    if response.status_code == 200:
        # Parsing konten HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Mencari tautan PDF
        pdf_link = None
        for a_tag in soup.find_all('a', href=True):
            if 'pdf' in a_tag['href']:
                pdf_link = a_tag['href']
                break
            

        # Menampilkan hasil tautan PDF
        if pdf_link:
            # Memastikan tautan menjadi absolut jika relatif
            if not pdf_link.startswith('http'):
                domain_name = get_domain_name(url)  # Mendapatkan domain utama
                pdf_link = 'http://' + domain_name + pdf_link

            # Menghapus string 'https://doi.org//' jika ada dalam pdf_link
            if pdf_link.startswith('http://doi.org//'):
                pdf_link = pdf_link.replace('http://doi.org//', 'http://')
            elif pdf_link.startswith('http://doi.org/articles/'):
                pdf_link = pdf_link.replace('http://doi.org/articles/', 'http://nature.com/articles/')



            return pdf_link

        # print('Tautan PDF:', pdf_link)
        else:
            return False
            # print('Tautan PDF tidak ditemukan.')
    else:
        return False

def get_doi_info(identifiers):
    doi_id = "N/A"
    doi_type = "N/A"
    if isinstance(identifiers, list):
        for identifier in identifiers:
            if identifier.get("type") == "doi":
                doi_id = identifier.get("id", "N/A")
                doi_type = identifier.get("type", "N/A")
                break
    return {"doi_id": doi_id, "doi_type": doi_type}


# Compile the paper data into a structured format
def compile_paper_data(article, bibjson, pdf_url, pdf_available, is_open_access):
    identifier_info = get_doi_info(bibjson.get('identifier', []))  # Extract DOI info
    return {
        "paperId": article.get('id', 'N/A'),
        "title": bibjson.get('title', 'N/A'),
        "abstract": bibjson.get('abstract', 'N/A'),
        "year": bibjson.get('year', 'N/A'),
        "authors": [author.get('name', 'N/A') for author in bibjson.get('author', [])],
        "citationCount": bibjson.get('citationCount', 'N/A'),
        "fieldsOfStudy": [subject.get('term', 'N/A') for subject in bibjson.get('subject', [])],
        "journal": {
            "name": bibjson.get('journal', {}).get('name', 'N/A'),
            "title": bibjson.get('journal', {}).get('title', 'N/A'),
            "volume": bibjson.get('journal', {}).get('volume', 'N/A'),
        },
        "start_page": bibjson.get('start_page', 'N/A'),
        "end_page": bibjson.get('end_page', 'N/A'),
        "publication_date": article.get('created_date', 'N/A'),
        "isOpenAccess": is_open_access,
        "url_": bibjson.get('link', 'N/A'),
        "identifier": identifier_info,  # Use the extracted DOI info
        "pdf_url": pdf_url,
        "pdf_available": pdf_available
    }


#na_pdf_count_filter = 0
# Display report of each paper
def show_report(paper):
    #print(paper)
    #global na_pdf_count_filter
    #na_pdf_count_filter += 1
    #print(na_pdf_count_filter)


    journal_info = paper.get("journal", {})
    if 'volume' in journal_info:
        document_type = "Journal Article"
    else:
        document_type = "Other Type"  # Adjust as needed

    # Publication type logic based on document type
    if 'journal' in document_type.lower():
        dash_ = "-"
        conference_name = dash_
        publication_type = "Journal Article"
        venue = dash_
    else:
        n_a = "N/A"
        conference_name = n_a
        publication_type = "Other Type"
        venue = n_a
 
    publication_date = paper.get('publication_date', 'N/A') if paper else 'N/A'
    if publication_date != 'N/A':
        publication_date_object = datetime.strptime(publication_date, "%Y-%m-%dT%H:%M:%SZ")
        formatted_publication_date = publication_date_object.strftime("%Y-%m-%d")

    else:
        dash_ = "-"
        formatted_publication_date = dash_

    links = paper.get("url_", []) if paper else 'N/A'
    if links and isinstance(links, list):
        first_url = links[0].get('url', 'N/A') if links else 'N/A'
      
    else:
        n_a = "N/A"
        first_url = n_a

    doi_info = paper.get("identifier", {}) if paper else 'N/A'
    extracted_keywords="N/A"
    source = "DOAJ"

    
    report = {
        "Paper Id": paper.get('paperId', 'N/A') if paper else 'N/A',
        "Title": paper.get('title', 'N/A') if paper else 'N/A',
        "Abstract": paper.get('abstract', 'N/A') if paper else 'N/A',
        "Year": paper.get('year', 'N/A') if paper else 'N/A',
        "Authors": ', '.join(paper.get('authors', [])) if paper else 'N/A',
        "Citation Count": paper.get('citationCount', 'N/A') if paper else 'N/A',
        "Discipline(s)": ", ".join(paper.get("fieldsOfStudy", [])) if paper else "N/A",
        "Document Type": document_type,
        "Journal Name": journal_info.get('title', 'N/A'),
        "Journal Volume": journal_info.get('volume', 'N/A'),
        "Journal Pages": f"{paper.get('start_page', 'N/A')}-{paper.get('end_page', 'N/A')}" if paper else 'N/A',
        "Conference Name": conference_name,
        "Publication Type": publication_type,
        "Venue": venue,
        "Publication Date": formatted_publication_date,
        "Is Open Access": "Yes" if paper and paper.get('isOpenAccess') is True else "No" if paper and paper.get('isOpenAccess') is False else "N/A",
        "Open Access PDF URL": paper.get('pdf_url', 'N/A') if paper else 'N/A',
        "PDF Available": 'Yes' if paper and paper.get('pdf_available') else 'No',
        "URL": first_url,
        "DOI": doi_info.get('doi_id', 'N/A') if paper else 'N/A',
        "Extracted Keywords": extracted_keywords,
        "Source": source
        #"DOI Type": doi_info.get('doi_type', 'N/A')
  
        
    }
    return report
    



na_pdf_count_filter_1 = 0
na_pdf_count_filter_2 = 0

def process_article(article):
    global na_pdf_count_filter_1, na_pdf_count_filter_2


    bibjson = article.get('bibjson', {})
    is_open_access = (
            bibjson.get('boai', False) or
            bibjson.get('i4oc_open_citations', False) or
            bibjson.get('oa_start', 0) == 0 or
            any(license.get('BY', False) for license in bibjson.get('license', []))
    )
    # Get all links
    all_links = bibjson.get('link', [])
    pdf_links = [link['url'] for link in all_links if link.get('url', '').endswith('.pdf')]

    link_pdf_available = None
    pdf_is_available = None

    if pdf_links:
        # print("filter1")
        link_pdf_available = pdf_links[0] if pdf_links else 'N/A'
        pdf_is_available = bool(link_pdf_available)


        return compile_paper_data(article, bibjson, link_pdf_available, pdf_is_available, is_open_access)
            
    else:
        na_pdf_count_filter_1 += 1

        # print("filter2")

        for link in all_links:

            # Mencetak semua URL yang ada
            link_pdf_available2 = link.get('url', 'N/A')
            # print("xxxx1", link_pdf_available2)
            detect_pdf_url = None
            pdf_is_available2 = None


                # Pola-pola URL untuk beberapa situs yang berbeda
            url_patterns = {
                "mdpi.com": lambda link: f"{link}/pdf",
                "frontiersin.org": lambda link: link.replace("/full", "/pdf"),
                "sciencedirect.com": lambda link: f"{link}/pdf",
                "ieeexplore.ieee.org": lambda link: link.replace("https://ieeexplore.ieee.org/document/",
                                                                 "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=").rstrip(
                    "/"),
                "tandfonline.com": lambda
                    link: f"{link.replace('https://www.tandfonline.com/doi/', 'https://www.tandfonline.com/doi/pdf/')}?download=true",
                "ncbi.nlm.nih.gov": lambda link: link.replace("/?tool=EBI", "/pdf"),
                "open-research-europe.ec.europa.eu": lambda link: f"{link}/pdf",
                "mental.jmir.org": lambda link: f"{link}/pdf",
                "mededu.jmir.org": lambda link: f"{link}/pdf",
                "humanfactors.jmir.org": lambda link: f"{link}/pdf",
                "jmir.org": lambda link: f"{link}/pdf",
                "spj.science.org": lambda
                    link: f"{link.replace('https://spj.science.org/doi/', 'https://spj.science.org/doi/pdf/')}?download=true",
                "researchprotocols.org": lambda link: f"{link}/pdf",
                "ebm-journal.org": lambda link: link.replace("/full", "/pdf"),
                "jstage.jst.go.jp": lambda link: link.replace("_html", "_pdf"),
                "journals.openedition.org": lambda link: link.replace("/aad", "/aad/pdf"),
                "gh.bmj.com": lambda link: f"{link}.pdf",
                "informatics.bmj.com": lambda link: f"{link}.pdf",
                "egms.de": lambda link: link.replace("/en/journals", "/pdf/journals").replace(".shtml", ".pdf"),
                "f1000research.com": lambda link: f"{link}/pdf",
                "fmch.bmj.com": lambda link: f"{link}.pdf",
                "royalsocietypublishing.org": lambda link: link.replace("https://royalsocietypublishing.org/doi/",
                                                                        "https://royalsocietypublishing.org/doi/epdf/")
            }


            for domain, transform_func in url_patterns.items():
                if domain in link_pdf_available2:
                    detect_pdf_url = transform_func(link_pdf_available2)
                    #print(detect_pdf_url)
                    pdf_is_available2 = bool(detect_pdf_url)
                    #print(pdf_is_available2)
                    break  # Keluar dari loop setelah menemukan domain yang cocok




            # Logika untuk menangani "/article/view" pada OJS
            if "/article/view" in link_pdf_available2 and not detect_pdf_url:
                detect_pdf_url = get_link_ojs_pdf(link_pdf_available2)
                pdf_is_available2 = bool(detect_pdf_url)

            # Logika untuk menangani doi
            if "doi.org" in link_pdf_available2 and not detect_pdf_url:
                detect_pdf_url = get_link_doi_pdf(link_pdf_available2)
                pdf_is_available2 = bool(detect_pdf_url)

            if detect_pdf_url is None or not pdf_is_available2:
                na_pdf_count_filter_2 += 1
                
                
            """
            Jika PDF tidak ditemukan dari domain spesifik, lakukan pengecekan menggunakan is_pdf_url
            if detect_pdf_url is None or not pdf_is_available2:
                detect_pdf_url = is_pdf_url(link_pdf_available2)
                pdf_is_available2 = bool(detect_pdf_url)
            """


            """
                    if detect_pdf_url or "/article/view" in link_pdf_available2:
                        # print("filter3")
                        if "/article/view" in link_pdf_available2:
                            detect_pdf_url = get_link_ojs_pdf(link_pdf_available2)
                            pdf_is_available2 = bool(detect_pdf_url)
                        else: 
                            detect_pdf_url = is_pdf_url(detect_pdf_url)
                            pdf_is_available2 = bool(detect_pdf_url)
                        return compile_paper_data(article, bibjson, detect_pdf_url, pdf_is_available2, is_open_access)
                    return None
            """
            return  compile_paper_data(article, bibjson, detect_pdf_url, pdf_is_available2, is_open_access)
                 
        
       

#default = 30
def get_doaj_data(query, page=1,page_size=100, paper_list=[],reset=1,time_limit_seconds=30):
    
    
    global na_pdf_count_filter_1, na_pdf_count_filter_2
    total_articles_processed=0
    
    total_available_pdf1 = 0
    total_available_pdf2 = 0
    
    start_time = time.time()
        
  
    #global total_articles_processed, total_available_pdf1, total_available_pdf2
    results_list = []
    


    # ==== DAPATKAN TOTAL RESULTS UNTUK MAX PAGES DINAMIS ====
    url_first = f"https://doaj.org/api/v4/search/articles/{query}?page=1&pageSize={page_size}"
    headers = {
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    response_first = requests.get(url_first, headers=headers)
    if response_first.status_code != 200:
        print(f"Failed to retrieve total results: {response_first.status_code}")
        return [], {}

    data_first = response_first.json()
    total_results = data_first.get('total', 0)
    if total_results == 0:
        print("No results found for the query.")
        return [], {}

    max_pages = (total_results + page_size - 1) // page_size
    print(f"Total results: {total_results}, Max pages: {max_pages}")
    
    while page <= max_pages:
        
            # ==== CEK TIME LIMIT SEBELUM MENGAMBIL HALAMAN ====
        if time.time() - start_time > time_limit_seconds:
            print("Time limit reached. Stopping collection.")
            break
        
        url = f"https://doaj.org/api/v4/search/articles/{query}?page={page}&pageSize={page_size}"
        headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
            }

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            articles = response.json().get('results', [])
            articles_count = len(articles)

            # Menambahkan pengecekan setiap 100 artikel dan mencetak artikel terakhir yang diproses
            #print(f"Memproses halaman {page} dengan {articles_count} artikel.")
            #print(f"Telah memproses {total_articles_processed} artikel sampai halaman {page}.")

            # Multithreading untuk memproses artikel di halaman saat ini
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Proses artikel satu per satu
                future_to_article = {executor.submit(process_article, article): article for article in articles}

                # Tunggu hingga semua artikel selesai diproses
                for future in concurrent.futures.as_completed(future_to_article):
                    
                    result= future.result()
   
                    if result:
                        paper_list.append(result)
                        report = show_report(result)  # Display the report for each article
                        total_articles_processed += 1  # Tambahkan setelah artikel selesai diproses
                        results_list.append(report)

            #print(f"Artikel terakhir yang diproses: {total_articles_processed}")

        else:
            print(f"Failed to retrieve data from page {page}: {response.status_code}")
            time.sleep(2)  # Tunggu sebentar sebelum mencoba lagi
            continue  # Coba lagi untuk halaman ini

        page += 1  # Lanjut ke halaman berikutnya

    #print(f"Total artikel yang diproses: {total_articles_processed}")

    #print("--------------------------------------------------")
    #print("na_pdf_count_filter_1", na_pdf_count_filter_1)
    total_available_pdf1 = total_articles_processed-na_pdf_count_filter_1
    #print("na_pdf_count_filter_2", na_pdf_count_filter_2)
    total_available_pdf2 = total_articles_processed-na_pdf_count_filter_2
    #print("--------------------------------------------------")
    #print(f"Available PDF Files without improved DOAJ PDF URL: {total_available_pdf1}")
    #print(f"Available PDF Files with improved DOAJ PDF URL: {total_available_pdf2}")
    #print(f"Successfully collected: {(total_articles_processed)} paper(s)")
    
    if reset==1:
        na_pdf_count_filter_1=0
        na_pdf_count_filter_2=0
    

    collection_retrieval = {
        
        "total_available_pdf1": total_available_pdf1,
        "total_available_pdf2": total_available_pdf2,
        "successfully_collected": total_articles_processed
        }
    
    
        
    return results_list, collection_retrieval
    