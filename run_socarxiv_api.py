import requests
import time

# Fungsi untuk mendapatkan data dari server
def get_data_from_server(url, params, max_retries=5):
    retries = 0
    headers = {
       "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }
    while retries < max_retries:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 429:
            retries += 1
            print(f"Too many requests. Retrying in 5 seconds... ({retries}/{max_retries})")
            time.sleep(5)  # Tunggu 5 detik sebelum mencoba lagi
            continue  # Coba lagi
        return response
    # Jika sudah melewati max_retries
    print("Maximum retries reached. Stopping requests.")
    return None

def get_socarxiv_data(query):
    # Endpoint API OSF untuk mengambil preprints tanpa user_id
    url = "https://api.osf.io/v2/preprints/"
    keyword = query  # Menyimpan query pencarian yang diberikan

    # Menambahkan filter untuk mencari preprints terkait Developmental Psychology di PsyArXiv
    params = {
        "filter[provider]": "socarxiv",  # Menyaring hanya preprints yang ada di PsyArXiv
        "page": 1  # Halaman pertama
    }

    max_total = 25  # Jumlah total artikel yang ingin diambil
    all_preprints = []  # Menyimpan artikel yang ditemukan

    while len(all_preprints) < max_total:
        # Mengatur jumlah artikel per halaman (misalnya 10 artikel per halaman)
        params["size"] = 10

        # Mengirim request GET ke API
        response = get_data_from_server(url, params=params)

        # Mengecek status response dan mencetak data
        if response.status_code == 200:
            data = response.json()  # Mengambil data dalam format JSON
            articles = data["data"]  # Menyimpan data preprints

            for item in articles:
                all_preprints.append(item)

            # Menampilkan link pagination jika ada lebih banyak halaman
            if "links" in data and "next" in data["links"]:
                params["page"] += 1  # Melanjutkan ke halaman berikutnya
            else:
                break  # Jika tidak ada halaman berikutnya, hentikan loop
        else:
            print(f"Error: {response.status_code}, {response.text}")
            break  # Keluar dari loop jika ada error dalam request

    # Setelah mendapatkan semua preprints, proses setiap artikel untuk menyiapkan laporan
    results_list = []
    headers = {
        "User-Agent": "ARPACS/2.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }
    for item in all_preprints:
        title = item['attributes']['title']

        # Membagi title menjadi kata-kata (set) untuk pencocokan
        title_words = set(title.lower().split())  # Mengubah title menjadi set kata
        keyword_words = set(keyword.lower().split())  # Mengubah keyword menjadi set kata

        # Menggunakan intersection untuk memeriksa apakah ada kata dalam keyword yang ada di title
        if title_words:
            paper_id = item['id']
            title = item['attributes']['title']
            abstract = item['attributes']['description']
            pub_date = item['attributes']['date_published']
            year = pub_date[:4] if pub_date else 'N/A'

   
            # Mendapatkan URL kontributor
            contributors = []
            contributors_url = item['relationships']['contributors']['links']['related']['href']

            contributors_response = requests.get(contributors_url, headers=headers)

            if contributors_response.status_code == 200:
                try:
                    contributors_data = contributors_response.json()
                    for contributor in contributors_data.get("data", []):
                        if ('embeds' in contributor and 
                            'users' in contributor['embeds'] and 
                            'data' in contributor['embeds']['users']):
                            author = contributor['embeds']['users']['data']
                            full_name = author['attributes']['full_name']
                            contributors.append(full_name)
                except Exception as e:
                    print(f"JSON parse error for {contributors_url}: {e}")
                    contributors = ["N/A"]
            else:
                print(f"Contributor request failed ({contributors_response.status_code}): {contributors_url}")
                contributors = ["N/A"]

            authors = ", ".join(contributors) if contributors else "N/A"
            
            citation_count = "N/A"
            categories = [subject[0]['text'] for subject in item['attributes']['subjects'] if isinstance(subject, list) and isinstance(subject[0], dict)] or ["N/A"]
            categories = ', '.join(categories)

            if item['attributes']['reviews_state'] == "accepted" or item['attributes']['reviews_state'] == "approved":
                document_type = 'Post-print'  # Sudah dipublikasikan
                publication_type = 'Post-print'  # Sudah dipublikasikan
            else:
                document_type = 'Pre-print'  # Belum dipublikasikan atau masih dalam tahap review
                publication_type = 'Pre-print'  # Belum dipublikasikan atau masih dalam tahap review

            journal_name = "N/A"
            journal_vol = "N/A"
            journal_pages = "N/A"
            conference_name = "N/A"
            venue = "N/A"
            publication_date = pub_date[:10]  # Mengambil tanggal hanya 10 karakter pertama (YYYY-MM-DD)

            pdf_url = item['links'].get('iri', 'N/A')
            if pdf_url != 'N/A':
                pdf_url_with_download = pdf_url + '/download'
            else:
                pdf_url_with_download = 'N/A'

            is_open_access = "Yes" if pdf_url != 'N/A' else "No"
            pdf_available = is_open_access

            # DOI dan versi yang diberikan
            doi_link = item['links'].get('preprint_doi', 'N/A')
            doi_ = doi_link.replace('https://doi.org/', '') if doi_link != 'N/A' else 'N/A'
            first_url = item['links'].get('html', 'N/A')
            extracted_keywords = item['attributes'].get('tags', []) or ["N/A"]
            extracted_keywords = ", ".join(extracted_keywords)
            source = "SocArXiv"

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
                "Open Access PDF URL": pdf_url_with_download,
                "PDF Available": pdf_available,
                "URL": first_url,
                "DOI": doi_,
                "Extracted Keywords": extracted_keywords,
                "Source": source
                
            }

            results_list.append(report)

    # Menghitung jumlah preprints yang tersedia dalam akses terbuka
    count_open_access = sum(1 for paper in results_list if paper.get("Is Open Access") == "Yes")
    collection_retrieval = {
        "total_available_pdf1": count_open_access,
        "total_available_pdf2": count_open_access,
        "successfully_collected": len(results_list)
    }

    return results_list, collection_retrieval
