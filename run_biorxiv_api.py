import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time



# Membuat URL dengan tanggal yang sudah dihitung

#default = 30
def get_biorxiv_data(query,time_limit_seconds=15):
    
    start_time = time.time()

    # Mendapatkan tanggal saat ini
    current_date = datetime.now()

    # Mengurangi 1 bulan dari tanggal saat ini
    one_month_ago = current_date - relativedelta(months=1)

    # Format tanggal dalam format 'YYYY-MM-DD'
    start_date = one_month_ago.strftime('%Y-%m-%d')
    end_date = current_date.strftime('%Y-%m-%d')
    # URL dasar API medRxiv dengan rentang tanggal tertentu
    base_url = f"https://api.biorxiv.org/details/biorxiv/{start_date}/{end_date}/"

    # Inisialisasi cursor dan jumlah total preprints
    cursor = 1
    papers_per_request = 100
    #max_total = 50  # Batasi hingga 1000 preprints
    # Kata kunci untuk pencarian
    keyword = query  # Ganti kata kunci sesuai dengan yang Anda cari

    # List untuk menyimpan semua preprints dan PDF links
    all_preprints = []
    headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    # Mengirim permintaan GET pertama untuk mendapatkan total preprints
    response = requests.get(f"{base_url}{cursor}")

    # Mengecek status response dan mendapatkan total preprints
    if response.status_code == 200:
        data = response.json()
        total_papers = int(data['messages'][0]['total'])  # Total preprints
        print(f"Total preprints available: {total_papers}")

        # Loop untuk mengambil preprints hingga mencapai total yang diinginkan
        while cursor <= total_papers:
            elapsed_time=time.time() - start_time
            if elapsed_time > time_limit_seconds:
                print("Time limit reached. Stopping collection.")
                break

            # Bangun URL dengan cursor saat ini
            url = f"{base_url}{cursor}"
            headers = {
            "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
            }

            # Mengirim permintaan GET ke API untuk mengambil preprints
            response = requests.get(url, headers=headers)
            
            # Mengecek status response dan memproses data
            if response.status_code == 200:
                data = response.json()
                preprints = data.get('collection', [])
                
                # Menyaring preprints berdasarkan kata kunci dalam judul atau abstrak
                for item in preprints:
                    all_preprints.append(item)
    

                # Update cursor untuk permintaan berikutnya
                cursor += papers_per_request
                
                

            else:
                print(f"Failed to fetch data. Status code: {response.status_code}")
                break

        # Menampilkan hasil jika berhasil
        #print(f"Total preprints retrieved: {len(all_preprints)}")
        # Cek jumlah preprints dan link PDF
        
        results_list = []
        # Menampilkan 5 preprints pertama dan PDF links yang sesuai
        for item in all_preprints:

            
            title_words = set(item['title'].lower().split())  # Mengubah title menjadi set kata
            #abstract_words = set(item['abstract'].lower().split())  # Mengubah abstract menjadi set kata
            #keyword_words = set(keyword.lower().split())  # Mengubah keyword menjadi set kata
                    
            # Menggunakan issubset untuk memeriksa apakah semua kata dalam keyword ada dalam title atau abstract
            if title_words:
                paper_id="N/A"
                title=item['title']
                abstract=item['abstract']
                pub_date=item['date']
                year=pub_date[:4] if pub_date else 'N/A'
                authors=item['authors']
                citation_count = "N/A"
                categories=item['category']
                
                if item['published'] == "NA":
                    document_type = "Pre-print"
                    publication_type = "Pre-print"
                else:
                    document_type = "Post-print"
                    publication_type = "Post-print"
                        
                journal_name= "N/A"
                journal_vol= "N/A"
                journal_pages= "N/A"
                conference_name= "N/A"
                venue="N/A"
                publication_date=pub_date
                
                # DOI dan versi yang diberikan
                doi_ = item['doi']
                version = item['version']

                # Membuat URL kombinasi untuk PDF
                pdf_url = f"https://www.biorxiv.org/content/{doi_}v{version}.full.pdf"
            
                is_open_access = "Yes" if pdf_url is not None else "No"
                pdf_available = is_open_access
                    
                first_url = f"https://www.biorxiv.org/content/{doi_}v{version}"
                extracted_keywords="N/A"
                source = "bioRxiv"

                report = {
                        "Paper Id": paper_id,
                        "Title": title,
                        "Abstract": abstract,
                        "Year": year,
                        "Authors": authors,
                        "Citation Count": citation_count,
                        "Discipline(s)": categories,
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

                results_list.append(report)
    else:
        print(f"Failed to retrieve data: {response.status_code}")

    
    count_open_access = sum(1 for paper in results_list if paper.get("Is Open Access") == "Yes")
    collection_retrieval = {
    "total_available_pdf1": count_open_access,
    "total_available_pdf2": count_open_access,
    "successfully_collected": len(results_list)
    }
    
    return results_list, collection_retrieval