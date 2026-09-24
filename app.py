from email.utils import quote

import nltk

def ensure_nltk_resource(resource_name, download_name=None):
    try:
        nltk.data.find(resource_name)
    except LookupError:
        nltk.download(download_name or resource_name.split("/")[-1])

# Pastikan stopwords tersedia
ensure_nltk_resource("corpora/stopwords", "stopwords")

# Pastikan punkt dan punkt_tab tersedia
ensure_nltk_resource("tokenizers/punkt", "punkt")
ensure_nltk_resource("tokenizers/punkt_tab", "punkt_tab")

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

import mysql.connector

import time
from run_semanticsc_api import get_semantic_data
from run_doaj_api import get_doaj_data
from run_pubmed_api import get_pubmed_data
from run_arxiv_api import get_arxiv_data
from run_medrxiv_api import get_medrxiv_data
from run_biorxiv_api import get_biorxiv_data
from run_psyarxiv_api import get_psyarxiv_data
from run_socarxiv_api import get_socarxiv_data
from run_edarxiv_api import get_edarxiv_data
from run_crossref_api import get_crossref_data
from run_openalex_api import get_openalex_data
from run_scopus_api import get_scopus_data
from run_wos_api import get_wos_data
from run_ai_api import get_ai_data
import pandas as pd
import streamlit as st
import psutil  # Import psutil for CPU and memory usage monitoring
import math
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed
#import fitz  # PyMuPDF
from io import BytesIO
from sentence_transformers import SentenceTransformer, util
import requests
import csv
from streamlit_tags import st_tags
#import os
import re
#from urllib.parse import urlparse
#import uuid
import PyPDF2
#import io
from bs4 import BeautifulSoup
import torch
from impact_factor.core import Factor
from langdetect import detect
import itertools
from docx import Document
from collections import Counter
from rank_bm25 import BM25Okapi
import numpy as np
import json
from openai import OpenAI
from datetime import datetime, date
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import base64
import warnings
warnings.filterwarnings(
    "ignore",
    message="Multiple definitions in dictionary"
)

st.set_page_config(layout="wide")
#st.cache_data.clear()
#st.cache_resource.clear()

USER_CREDENTIALS = {
    "[INPUT-USERNAME]": "[INPUT-PASSWORD]",
}

def login():

    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/e/ee/Okayama_University_Logo.svg" 
                alt="Okayama Logo" style="width: 230px; min-width: 230px;">
            <div>
                <h2 style="margin: 0; padding: 0;">Welcome to ARPACS Project</h2>
                <p style="margin: 4px 0 0 0; font-size: 14px; color: gray;">
                    A Reference Paper Collection System – Open Access Paper Retrieval via APIs
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True  # ← penting banget!
    )


    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Wrong username or password.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.rerun()

def extract_abstract_from_url(url):
    """Ekstrak Abstract dari PDF halaman pertama tanpa mengambil bagian Keywords."""
    # Validasi URL
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        return "N/A"

    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return "N/A"

    if len(response.content) < 1024:  # Pastikan PDF valid
        return "N/A"

    pdf_file = BytesIO(response.content)

    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
    except PyPDF2.errors.PdfReadError:
        pdf_file.seek(0)
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file, strict=False)
        except:
            return "N/A"

    # Ambil halaman pertama
    page = pdf_reader.pages[0]
    text = page.extract_text() or ""
    lines = text.splitlines()

    abstract_text = None
    abstract_labels = ["Abstract", "ABSTRACT"]

    for i, line in enumerate(lines):
        stripped = line.strip()
        for label in abstract_labels:
            if stripped.startswith(label):
                # Ambil isi setelah label
                content = stripped[len(label):].strip()
                abstract_lines = []
                if content:
                    abstract_lines.append(content)

                # Tambahkan baris berikutnya sampai ketemu "Introduction" atau akhir halaman
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if re.match(r"^(?:1\.|I\.)\s*(?:Introduction|Background)", next_line, re.IGNORECASE):
                        break
                    if next_line:
                        abstract_lines.append(next_line)
                abstract_text = " ".join(abstract_lines).strip()
                # Hentikan di Keywords, Received, Accepted, Published
                remove_pattern = r'(Keywords:|KEYWORDS:|Key words:|Key Words:|Received:|Accepted:|Published:).*'
                
                abstract_text = re.sub(remove_pattern, '', abstract_text, flags=re.IGNORECASE | re.DOTALL).strip()
                


    return abstract_text if abstract_text else "N/A"


def is_valid_docx(file_content):
    # Memeriksa magic number (signature byte) untuk file DOCX
    # File DOCX harus memiliki signature '504b' (PK) di awal file (file zip)
    magic_number = file_content.read(4)
    file_content.seek(0)
    return magic_number == b'PK\x03\x04'

def extract_keywords_from_docx(docx_content):
    # Membaca file DOCX dari byte stream menggunakan python-docx
    try:
        doc = Document(docx_content)
    except Exception as ex:
        return "N/A"

    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"

    match_same_line = re.search(r'(Keywords?|KEYWORDS|Key Words|Index Terms)\s*[:]*\s*(.+?)(?=\s*(?:Introduction|Background|1\.|I\.|Received:|Accepted:|Published:|To whom correspondence|Frontier|The Author|CC-BY|=-|\d{4}/\d{2}/\d{2}|\d{1,2} \w{3} \d{4}|Abbreviations|How to cite this Article|doi:|arXiv:|Manuscript received|Manuscri pt|ABSTRACT|Data and Code Availability|All rights reserved|=- |Correspondence:|\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b|$))', text, re.IGNORECASE | re.DOTALL)

    if match_same_line:
        keywords_text = match_same_line.group(2).strip()
        return keywords_text.replace("\n", " ").replace("=-", " ").strip()

    # Jika tidak ditemukan dalam satu baris, coba regex lain untuk kondisi Keywords \n
    match_newline = re.search(r'(Keywords?|KEYWORDS|Key Words|Index Terms)\s*[:]*\s*(.+?)(?=\s*(?:Introduction|Background|1\.|I\.|Received:|Accepted:|Published:|To whom correspondence|Frontier|The Author|CC-BY|=-|\d{4}/\d{2}/\d{2}|\d{1,2} \w{3} \d{4}|Abbreviations|How to cite this Article|doi:|arXiv:|Manuscript received|Manuscri pt|ABSTRACT|Data and Code Availability|All rights reserved|=- |Correspondence:|\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b|$))', text, re.IGNORECASE | re.DOTALL)

    if match_newline:
        keywords_text = match_newline.group(2).replace("\n", " ").strip()
        return keywords_text.replace("=-", " ").strip()

    return "-"  # Jika tidak ditemukan kata kunci

def extract_keywords_from_url(url):
    # Validasi URL
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        return "N/A"  # Invalid URL

    try:
        # Mengambil file PDF dari URL
        response = requests.get(url, timeout=3)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        try:
            # Jika ada error SSL, coba lagi tanpa verifikasi SSL
            response = requests.get(url, verify=False, timeout=3)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return "N/A"  # Failed to retrieve data (SSL error or other issues)
    except requests.exceptions.RequestException:
        return "N/A"  # General Request Exception

    if response.status_code == 200:
        # Membaca konten PDF
        pdf_file = BytesIO(response.content)

        
        # Jika bukan PDF atau PDF gagal, lanjutkan dengan file DOCX
        if url.endswith('.docx') or is_valid_docx(pdf_file):
            try:
                docx_text = extract_keywords_from_docx(pdf_file)
                if docx_text:
                    return docx_text  # Mengembalikan kata kunci dari DOCX
            except Exception as ex:
                return f"N/A: {str(ex)}"  # Error membuka file DOCX
        else:
            if len(response.content) < 1024:
                return "N/A"  # File terlalu kecil, tidak valid

            try:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
            except PyPDF2.errors.PdfReadError as e:
                if "EOF marker not found" in str(e):
                    pdf_file.seek(0)
                    try:
                        pdf_reader = PyPDF2.PdfReader(pdf_file, strict=False)
                    except PyPDF2.errors.PdfReadError:
                        return "N/A"  # PDF format error
                else:
                    return "N/A"  # Other PDF reading error


        keywords_text = None
        keyword_label_line_num = None
        

        # Daftar kemungkinan label untuk kata kunci
        keyword_labels = [
            "Keywords:", "Keywords", "KEYWORDS", "Key Words", "Key words", "Index Terms"
        ]

        # Maksimal 2 halaman yang dicek
        num_pages = len(pdf_reader.pages)
        all_text = ""
        

        for page_num in range(min(2, num_pages)):  # Batasi hingga maksimal 2 halaman
            page = pdf_reader.pages[page_num]
            text = page.extract_text() or ""
            lines = text.splitlines()
            all_text +=text


        # Regex untuk mencari kata kunci yang ada setelah label "Keywords" dalam baris yang sama
        match_same_line = re.search(r'(Keywords?|KEYWORDS|Key Words|Index Terms)\s*[:]*\s*(.+?)(?=\s*(?:Introduction|Background|1\.|I\.|Received:|Accepted:|Published:|To whom correspondence|Frontier|The Author|. CC-BY|=-|\d{4}/\d{2}/\d{2}|\d{1,2} \w{3} \d{4}|Abbreviations|How to cite this Article|doi:|arXiv:|Manuscript received|Manuscri pt|ABSTRACT|Data and Code Availability|All rights reserved|=- |Correspondence:|\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b|$))', all_text, re.IGNORECASE | re.DOTALL)

        if match_same_line:
            # Ambil teks setelah "Keywords" dalam satu baris
            keywords_text = match_same_line.group(2).strip()
            lines = all_text.splitlines()
            
        
            for i, line in enumerate(lines):
                stripped = line.strip()
                for label in keyword_labels:
                    if stripped.startswith(label):
                        # Ambil isi setelah label di baris yang sama
                        content = stripped[len(label):].strip()
                        keyword_lines = []
                        if content:
                            keyword_lines.append(content)
                        # Tambahkan baris-baris berikutnya (maks 2) jika masih lanjutan
                        for j in range(i + 1, min(i + 3, len(lines))):
                            next_line = lines[j].strip()
                            if not next_line:
                                break
                            keyword_lines.append(next_line)
                        keywords_text = " ".join(keyword_lines).strip()
                        break
                if keywords_text:
                    break

    
            keywords_text = keywords_text.replace("\n", " ")
            keywords_text = re.sub(r"=--", " ", keywords_text)
            keywords_text = re.sub(r"=-", " ", keywords_text)

            
            if keywords_text and keyword_label_line_num is not None:
                return f"{keywords_text}"
            else:
                return f"{keywords_text}"
        
        
        # Jika tidak ditemukan dalam satu baris, coba regex lain untuk kondisi Keywords \n
        match_newline = re.search(r'(Keywords?|KEYWORDS|Key Words|Index Terms)\s*[:]*\s*(.+?)(?=\s*(?:Introduction|Background|1\.|I\.|Received:|Accepted:|Published:|To whom correspondence|Frontier|The Author|. CC-BY|=-|\d{4}/\d{2}/\d{2}|\d{1,2} \w{3} \d{4}|Abbreviations|How to cite this Article|doi:|arXiv:|Manuscript received|Manuscri pt|ABSTRACT|Data and Code Availability|All rights reserved|=- |Correspondence:|\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b\s+\b\w+\b|$))', all_text, re.IGNORECASE | re.DOTALL)

        if match_newline:
            # Ambil teks setelah "Keywords" di baris berikutnya
            keywords_text = match_newline.group(2).replace("\n", " ").strip()
            lines = all_text.splitlines()

            # Mencari baris untuk label "Keywords"
            for i, line in enumerate(lines):
                if line.strip().startswith(match_newline.group(1).strip()):
                    keyword_label_line_num = i + 1
                    break
            
            keywords_text = keywords_text.replace("\n", " ")
            keywords_text = re.sub(r"=--", " ", keywords_text)
            keywords_text = re.sub(r"=-", " ", keywords_text)

            
            if keywords_text and keyword_label_line_num is not None:
                #return f"Keywords <line {keyword_label_line_num}>\n{keywords_text} <line {keyword_label_line_num + len(keywords_text.splitlines())}>"
                return f"{keywords_text}"
           
            else:
                return f"{keywords_text}"

        # Jika tidak ditemukan kedua cara
        return "-"  # Tidak ditemukan kata kunci

    else:
        return "N/A"  # Failed to retrieve PDF


def extract_keywords_pmc_pubmed(url):
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        #print(f"Skipping invalid URL: {url}")
        return "N/A"
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=1)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Cari section dengan id="kwd-group1"
        kwd_section = soup.find('section', {'id': 'kwd-group1', 'class': 'kwd-group'})
        if kwd_section:
            p_tag = kwd_section.find('p')
            if p_tag:
                # Hapus <strong> supaya tersisa teks keyword-nya saja
                strong_tag = p_tag.find('strong')
                if strong_tag:
                    strong_tag.extract()
                return p_tag.get_text(strip=True)

        return "-"
    except Exception as e:
        #print(f"Error extracting keywords from {url}: {e}")
        return "N/A"


def extract_abstract_pmc_pubmed(url):
    """Ekstrak abstract dari halaman PMC/PubMed HTML"""
    if not isinstance(url, str) or not re.match(r'^https?://', url):
        return "N/A"
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=3)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Cari section abstract
        abstract_section = soup.find('section', {'class': 'abstract'})
        if abstract_section:
            paragraphs = abstract_section.find_all('p')
            abstract_lines = []
            for p in paragraphs:
                # Hapus Database URL atau link jika ada
                text = p.get_text(separator=" ", strip=True)
                text = re.sub(r"(?i)Database URL:.*", "", text)
                if text:
                    abstract_lines.append(text)
            abstract_text = " ".join(abstract_lines).strip()
            return abstract_text if abstract_text else "N/A"

        return "N/A"
    except Exception as e:
        #print(f"Error extracting abstract from {url}: {e}")
        return "N/A"

  
def get_journal_data_crossref(doi, key, default_value=None):

    url = f"https://api.crossref.org/works/{quote(doi)}"
    headers = {
            "User-Agent": "AcademicResearch/1.0 (mailto:tresnamf@s.okayama-u.ac.jp)"
    }

    response = requests.get(url, headers=headers, timeout=20)
    
        
    # Cek apakah respons berhasil
    if response.status_code == 200:
        metadata = response.json()
        
        # Mengambil data berdasarkan key yang diberikan, jika tidak ada kembalikan default_value
        value = metadata['message'].get(key, default_value)
        
        
        return value
    else:
        return default_value  # Jika ada error, kembalikan default_value


def get_journal_title_crossref(doi):
    if doi == "N/A" or doi is None:
        return "N/A"
    else:
        title_list = get_journal_data_crossref(doi, 'title', [])
        if isinstance(title_list, list) and title_list:
            return title_list[0]
        return "N/A"


def get_journal_abstract_crossref(doi):
    if doi == "N/A" or doi is None:
        return "N/A"
    else:
        return get_journal_data_crossref(doi, 'abstract', "N/A")

def get_journal_doc_type_crossref(doi):
    if doi == "N/A" or doi is None:
        return "N/A"
    else:
        return get_journal_data_crossref(doi, 'type', "N/A")

def get_journal_name_crossref(doi):
    if doi == "N/A" or doi is None:
        return "N/A"
    else:
        # Membuat URL untuk CrossRef API
        url = f"https://api.crossref.org/works/{doi}"
        
        
        # Mengirim permintaan ke API
        response = requests.get(url)
        
        if response.status_code == 200:
            metadata = response.json()
            # Mengambil data berdasarkan key yang diberikan, jika tidak ada kembalikan default_value
            value = metadata['message'].get('container-title', "N/A")
            
            if isinstance(value, list):
                if value:  # Jika list tidak kosong
                    # Flatten jika value adalah nested list
                    value = list(itertools.chain(*value))  # Meratakan list bersarang
                    return value[0]  # Ambil elemen pertama setelah flattening
                else:
                    return "N/A"  # Jika list kosong

            return value  # Jika bukan list, kembalikan value
        else:
            return "N/A"  # Jika ada error, kembalikan default_value

def get_journal_page_crossref(doi):
    if doi == "N/A" or doi is None:
        return "N/A"
    else:
        return get_journal_data_crossref(doi, 'page', "N/A")

def get_journal_vol_crossref(doi):
    if doi == "N/A" or doi is None:
        return "N/A"
    else:
        return get_journal_data_crossref(doi, 'volume', "N/A")


# Fungsi untuk mendapatkan citation count (is-referenced-by-count) berdasarkan DOI
def get_journal_citation_crossref(doi):
    if doi == "N/A" or doi is None:
        return "0"
    else:
        return get_journal_data_crossref(doi, 'is-referenced-by-count', 0)

# Fungsi untuk mendapatkan ISSN pertama berdasarkan DOI
def get_journal_issn_crossref(doi):
    issn_list = get_journal_data_crossref(doi, 'ISSN', [])
    if isinstance(issn_list, list) and issn_list:
        return issn_list[0]  # Mengambil ISSN pertama jika ada
    return "N/A"  # Jika ISSN tidak ditemukan, kembalikan "N/A"

def get_journal_pdf_crossref(doi, key = 'link', default_value="N/A"):
    # Membuat URL untuk CrossRef API
    url = f"https://api.crossref.org/works/{doi}"
    
    # Mengirim permintaan ke API
    response = requests.get(url)
    
    # Cek apakah respons berhasil
    if response.status_code == 200:
        metadata = response.json()
        
        # Mengambil data berdasarkan key yang diberikan, jika tidak ada kembalikan default_value
        value = metadata['message'].get(key, default_value)
        
        # Jika key adalah 'link' dan value berupa list of dictionaries, ekstrak URL dengan content-type 'application/pdf'
        if key == 'link' and isinstance(value, list):
            # Mencari URL pertama dengan content-type 'application/pdf'
            for item in value:
                if item.get('content-type') == 'application/pdf':
                    return item.get('URL', default_value)  # Mengembalikan URL pertama yang ditemukan
                elif item.get('content-type') == 'unspecified':
                    return item.get('URL', default_value)  # Mengembalikan URL pertama yang ditemukan
                
            
            return default_value  # Jika tidak ada URL yang cocok ditemukan
        
        return value
    else:
        return default_value  # Jika ada error, kembalikan default_value


def get_pdf_unpaywall(doi):
    try:
        r = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": "tresnamf@gmail.com"},
            timeout=3
        )

        if r.status_code == 200:
            data = r.json()

            best = data.get("best_oa_location")
            if best and best.get("url_for_pdf"):
                return best["url_for_pdf"]

            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    return loc["url_for_pdf"]

        return "N/A"

    except Exception:
        return "N/A"


def format_date_for_mysql(date_str):

    # Jika sudah datetime.date → langsung kembalikan
    if isinstance(date_str, date):
        return date_str

    if date_str is None:
        return None

    # Ubah ke string untuk pengecekan
    s = str(date_str).strip()

    if s in ["", "N/A", "None"]:
        return None

    # 1. ISO format with Z e.g. 2025-04-05T16:48:09Z
    try:
        dt = datetime.fromisoformat(s.replace("Z", ""))
        return dt.date()
    except Exception:
        pass

    # 2. DD/MM/YYYY
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        pass

    # 3. YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        pass

    return None



def get_journal_if(issn):
    
    if issn == "N/A" or issn is None:
        return 0
    
    fa = Factor()
    if_journal = fa.search(issn)
    
    if if_journal:
        impact_factor = if_journal[0].get('factor', 0)
        return impact_factor
    else:
        return 0
    
    
# Fungsi untuk mendeteksi bahasa
def is_english(text):
    try:
        return detect(text) == 'en'
    except:
        return False 


def normalize_keywords(kw_list):
    normalized = []
    for kw in kw_list:
        # Jika ada koma di elemen, split dan strip
        if ',' in kw:
            split_kw = [k.strip() for k in kw.split(',')]
            normalized.extend(split_kw)
        else:
            normalized.append(kw.strip())
    return normalized

@st.cache_resource(show_spinner="Loading model...")
def load_model():
    try:
        device = "cuda"
        st.success(f"Model loaded successfully on {device.upper()}!")
        #model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v1", device=device)
        #model =  SentenceTransformer("sentence-transformers/all-distilroberta-v1", device=device) 6m 3s 1l 56sec -->7
        model =  SentenceTransformer("sentence-transformers/all-mpnet-base-v2", device=device) 
        #model =  SentenceTransformer("allenai/scibert_scivocab_uncased", device=device) 4h 6m 67.50 sec --> 7
        #model =  SentenceTransformer("allenai/specter", device=device) 4h 6m 90.32sec --> 5
        
        
        #model = SentenceTransformer("sentence-transformers/allenai/scibert_scivocab_uncased", device=device) 5m 4s 1l 107sec --> 7
        #model =  SentenceTransformer("sentence-transformers/all-roberta-large-v1", device=device) 7m 2s 1l 221sec --> 7
        
        #model =  SentenceTransformer("sentence-transformers/multi-qa-distilbert-cos-v1", device=device) 1h 9m 71.77sec --> 7 tapi sorting kurang baik
        #model =  SentenceTransformer("sentence-transformers/bert-base-nli-mean-tokens", device=device) 2h 8m 79sec --> 6 beberapa tidak relevan
        #model =  SentenceTransformer("sentence-transformers/bert-base-nli-stsb-mean-tokens", device=device) 7m 3s 77sec --> 7 beberapa sorting kurang relevan
        #model =  SentenceTransformer("sentence-transformers/bert-base-nli-max-tokens", device=device) 10h 91.83sec --> 6 beberapa sorting kurang relevan
        #model =  SentenceTransformer("sentence-transformers/stsb-bert-base", device=device) 8m 2s 68sec --> 7   beberapa sorting kurang relevan
        #model =  SentenceTransformer("malteos/scincl", device=device) 10 h --> 63sec --> 7 rank terlalu tinggi
        #model =  SentenceTransformer("distilbert/distilroberta-base", device=device) 10h 66.23 -->7

        return model
    except NotImplementedError as e:
        st.error("There was a problem loading the model. Please reload the page and try again.")
        # Tombol reload model
        if st.button("🔄 Reload model"):
            st.cache_resource.clear()  # hapus semua cache resource agar model di-load ulang
            st.rerun()    # reload halaman (pakai experimental_rerun karena st.rerun() sudah deprecated)
        st.stop()  # stop further execution
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        st.stop()

model = load_model()



def normalize_values(df, column_name):
    # Normalisasi untuk fitur utama (seperti Citation Count atau Impact Factor)
    df[column_name] = pd.to_numeric(df[column_name], errors='coerce')
    min_value = df[column_name].min()
    max_value = df[column_name].max()
        
    return min_value, max_value


def parse_embedding(x):
    try:

        if isinstance(x, str):
            vector_list = json.loads(x)
            arr = np.array(vector_list, dtype=np.float32).flatten()
        #arr = np.array(x, dtype=np.float32).flatten()
        # Pastikan dimensinya sama, jika tidak, isi dengan nol
        #if arr.shape[0] != target_dim:
            #arr = np.zeros(target_dim, dtype=np.float32)
            
        #if arr.shape[0]==target_dim:
         
            return arr
        else:
            return None
    except Exception as e:
        print(f"Error parsing embedding: {e}")
        #return np.zeros(target_dim, dtype=np.float32)





def compute_similarity(user_keywords, extracted_keywords, model, existing_emb=None):
    """Compute text similarity using cached embedding if available."""

    # Jika title kosong → tidak bisa hitung similarity
    if not user_keywords or not extracted_keywords or not user_keywords.strip() or not extracted_keywords.strip():
        return 0.0, None

    

    # Normalize
    user_keywords = user_keywords.lower()
    extracted_keywords = extracted_keywords.lower()

    
    # Query embedding selalu dihitung (query hanya 1 di seluruh proses)
    user_embedding = model.encode(user_keywords,device=model.device)

    # Jika embedding title sudah tersedia → langsung pakai
    if existing_emb is not None:
        try:
            extracted_embedding = np.array(existing_emb,dtype=np.float32)
            #print("saya existing embedd")
        except:
            extracted_embedding = model.encode(extracted_keywords,device=model.device)
            #print("saya extract keyword 1")
    else:
        # Kalau belum ada embedding simpanan, encode baru
        extracted_embedding = model.encode(extracted_keywords,device=model.device)
        #print("saya extract keyword 2", extracted_keywords)

    # Hitung cosine similarity
    try:
        similarity_score = util.cos_sim(user_embedding, extracted_embedding).item()
    except Exception as e:
        print(f"Error during similarity calculation: {e}")
        return 0.0, extracted_embedding

    return similarity_score, extracted_embedding



# Fungsi untuk menghitung IDF (Inverse Document Frequency)
def compute_idf(query, documents):
    idf = {}
    total_documents = len(documents)
    for term in query.split():
        doc_freq = sum(1 for doc in documents if term in doc)
        idf[term] = math.log((total_documents - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
    return idf

# Fungsi untuk menghitung BM25 antara query dan dokumen
def compute_bm25(query, documents):
    
   
    tokenized_documents = [word_tokenize(doc.lower()) for doc in documents]
    tokenized_query = word_tokenize(query.lower())
    #print("tokenquery",tokenized_query)
    #print("tokendoc",tokenized_documents)

    # Inisialisasi model BM25
    bm25 = BM25Okapi(tokenized_documents,
                     k1=1.5,
                     b=0.75,
                     epsilon=0.25)

    # Menghitung skor BM25 untuk query
    scores = bm25.get_scores(tokenized_query)
	
    
    return scores




# Fungsi untuk menghitung similarity score
def calculate_bert(row, query, selected_domain_final, selected_field_final, user_keywords, model, min_citation, max_citation, min_impact, max_impact):
    
    # 1. Cocokkan query dengan row['Title'], kalikan dengan 0.5
    existing_title_emb = row.get('Vector Embedding Title', None)
    sim_score_1, emb_vector_title = compute_similarity(query, row['Title'],model,existing_emb=existing_title_emb)
    title_bert = 0.55 * sim_score_1


    # 2. Kombinasi selected_domain_final, selected_field_final, user_keywords, query dicocokkan dengan row['Abstract'], kalikan dengan 0.4
    combined_query_abstract = ", ".join(filter(None, [
            str(selected_domain_final),
            str(selected_field_final),
            str(" ".join(user_keywords)),
            str(query)
        ]))
    
    existing_abs_emb = row.get('Vector Embedding Abstract', None)
    sim_score_2, emb_vector_abstract = compute_similarity(combined_query_abstract, row['Abstract'], model, existing_emb=existing_abs_emb)
    abstract_bert = 0.35 * sim_score_2
       

    # 3. Perhitungan similarity antara user_keywords dan row['Extracted Keywords'], kalikan dengan 0.05
    existing_kw_emb = row.get('Vector Embedding Extracted Keywords', None)
    sim_score_3, emb_vector_keywords = compute_similarity(" ".join(user_keywords), " ".join([kw.strip() for kw in row['Extracted Keywords'].replace("—", "").replace(';', ',').replace('·', ',').split(',')]), model,existing_emb=existing_kw_emb)
    keywords_bert = 0.05 * sim_score_3
    
    # 4. Kombinasi selected_domain_final, selected_field_final, query dicocokkan dengan row['Discipline(s)'], kalikan dengan 0.05
  
    combined_query_discipline = ", ".join(filter(None, [
            str(selected_domain_final),
            str(selected_field_final),
            str(query)
        ]))
    existing_disc_emb = row.get('Vector Embedding Discipline(s)', None)
    sim_score_4, emb_vector_discipline = compute_similarity(combined_query_discipline, row['Discipline(s)'], model, existing_emb=existing_disc_emb)
    
    discipline_bert = 0.05 * sim_score_4

    # 5. Menambahkan faktor Citation Count dengan bobot 0.05 setelah dinormalisasi
    normalized_citation =  (row['Citation Count'] - min_citation) / (max_citation - min_citation) if max_citation != min_citation else 0
    citation_score = 0.6 *normalized_citation

    # 6. Menambahkan faktor Impact Factor dengan bobot 0.05 setelah dinormalisasi
    normalized_impact =  (row['Impact Factor'] - min_impact) / (max_impact - min_impact) if max_impact != min_impact else 0
    impact_score = 0.4 * normalized_impact

    # Similarity Score
    total_bert = ((title_bert + abstract_bert + keywords_bert + discipline_bert) + (0.15*(citation_score + impact_score)))
        
    if(total_bert>1):
        total_bert_final=1
    else:
        total_bert_final=total_bert

    return title_bert, abstract_bert,keywords_bert,discipline_bert,citation_score,impact_score,total_bert_final,emb_vector_title,emb_vector_abstract,emb_vector_keywords,emb_vector_discipline


def bert_summary(abstract, max_sentences=20,device="cuda"):
    # Split abstract menjadi kalimat
    sentences = re.split(r'\.|\?|!', abstract)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Hitung embedding setiap kalimat
    embeddings = model.encode(sentences, convert_to_tensor=True, device=device)
    
    # Centroid embedding abstract
    #centroid = np.mean(embeddings.cpu().numpy(), axis=0)
    centroid = torch.mean(embeddings, dim=0)
    
    # Hitung similarity tiap kalimat dengan centroid
    sims = util.cos_sim(embeddings, centroid)
    sims = sims.cpu().numpy().flatten()
    
    # Pilih kalimat top-k
    top_idx = sims.argsort()[-max_sentences:][::-1]
    summary = '. '.join([sentences[i] for i in sorted(top_idx)])
    return summary


def lda_modeling(df):

    # =========================
    # Load CSV
    # =========================

    # Ambil kolom Abstract
    documents = (
        df['Title'].astype(str)
        + " "
        + df['Abstract'].astype(str)
    ).tolist()

    # =========================
    # Count Vectorizer
    # =========================
    # LDA lebih cocok menggunakan CountVectorizer
    # dibanding TF-IDF

    vectorizer = CountVectorizer(
        stop_words='english',
        max_features=500,
        ngram_range=(1,2),
        min_df=2,
        max_df=0.85
        
    )

    doc_term_matrix = vectorizer.fit_transform(documents)

    terms = vectorizer.get_feature_names_out()

    #print("=== Vocabulary Terms ===")
    #print(terms)

    # =========================
    # LDA Model
    # =========================

    lda_model = LatentDirichletAllocation(
        n_components=10,
        random_state=42,
        learning_method='batch',
        max_iter=20
    )

    lda_matrix = lda_model.fit_transform(doc_term_matrix)
    
    TOP_N_TOPICS = 3
    TOP_N_WORDS = 20

    topic_contexts = []

    for doc_index, topic_probs in enumerate(lda_matrix):

        top_topics = topic_probs.argsort()[::-1][:TOP_N_TOPICS]

        topic_text = []

        for topic_idx in top_topics:

            prob = topic_probs[topic_idx]

            top_terms = lda_model.components_[topic_idx].argsort()[-TOP_N_WORDS:][::-1]

            keywords = [
                terms[i]
                for i in top_terms
            ]

            topic_text.append(
                f"Topic {topic_idx + 1} ({prob:.2%}): {', '.join(keywords)}"
            )

        topic_contexts.append("\n".join(topic_text))

    # Tambahkan hasil LDA ke DataFrame
    df["LDA_Topics"] = topic_contexts
    
    return df


    # =========================
    # Perplexity & Log Likelihood
    # =========================

    #print("\n=== Evaluation ===")

    #print(
     #   "Perplexity:",
      #  lda_model.perplexity(doc_term_matrix)
    #)

    #print(
     #   "Log Likelihood:",
      #  lda_model.score(doc_term_matrix)
    #)
    
def rag_metrics_embeddings(row, query, user_keywords, selected_domain_final, selected_field_final):

    from datasets import Dataset
    from ragas import evaluate
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.metrics import faithfulness
    from ragas.metrics import AspectCritic
    



    # Paper information as context
    context = f"""
    Paper Title:
    {row['Title']}

    Paper Abstract:
    {row['Abstract']}

    Paper Discipline:
    {row['Discipline(s)']}

    Paper Keywords:
    {row['Extracted Keywords']}
    """

    question = f"""
    Why is the retrieved paper relevant to the user query?

    User Query:
    {query}

    Query Keywords:
    {user_keywords}

    Query Research Domain:
    {selected_domain_final}

    Query Subject Field:
    {selected_field_final}

   """





    dataset = Dataset.from_dict({
        "question": [question],
        "answer": [row['AI Explanation']],
        "contexts": [[context]]
    })
    #Relevansi Penjelasan mengukur apakah justifikasi AI mampu menghubungkan query pengguna dengan karakteristik paper secara tepat, termasuk menjelaskan kesamaan dan perbedaannya.
    explanation_relevance = AspectCritic(
    name="explanation_relevance",
    definition="""
    Evaluate the quality of the AI-generated explanation regarding the relationship between the user query and the retrieved paper.

    Assign a score:

    3 = Good: The explanation clearly describes the query-paper relationship and provides supporting evidence.

    2 = Acceptable: The explanation identifies the relationship but lacks sufficient detail or justification.

    1 = Poor: The explanation does not clearly justify the relationship or contains unsupported claims.

    Answer only the score: 1, 2, or 3.


    """
)


    # OpenRouter LLM evaluator
    evaluator_llm = ChatOpenAI(
        model="openai/gpt-4o-mini",
        temperature=0,
        top_p=1.0,
        max_tokens=256,
        seed=42,
        openai_api_key="sk-",
        openai_api_base="https://openrouter.ai/api/v1"
    )


    # OpenRouter embedding
    evaluator_embeddings = OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        openai_api_key="sk-",
        openai_api_base="https://openrouter.ai/api/v1"
    )


    result = evaluate(
        dataset,
        metrics=[
            explanation_relevance,
            faithfulness
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings
    )


    return (
        float(result["explanation_relevance"][0]),
        float(result["faithfulness"][0])
    )



# Fungsi RAG evaluation semua berbasis embedding
def rag_metrics_embeddings2(row, query, user_keywords, model):
    
    
    # Preprocess texts
    context_text = (row['Title'] + ". " + bert_summary(row['Abstract']))
    justification_text = (row['AI Explanation'])
    query_text  = query + ". " + ", ".join(user_keywords)


    # Pastikan teks bukan kosong atau hanya berisi spasi
    if not context_text or not justification_text or not query_text or not context_text.strip() or not justification_text.strip() or not query_text.strip():
        # Jika salah satu atau kedua teks kosong atau hanya berisi spasi, return similarity 0
        return 0.0
    
    # Mengubah semua teks menjadi lowercase untuk konsistensi
    context_text = context_text.lower()
    justification_text = justification_text.lower()
    query_text = query_text.lower()
    
    try:
        # Encode teks yang sudah diubah menjadi lowercase
        context_emb = model.encode(context_text,convert_to_tensor=True, device="cuda")
        justification_emb = model.encode(justification_text, convert_to_tensor=True, device="cuda")
        query_emb = model.encode(query_text, convert_to_tensor=True, device="cuda")
        
    except Exception as e:
        # Tangani kesalahan pada saat encoding
        print(f"Error during encoding2: {e}")
        return 0.0
    
    try:
        # Menghitung cosine similarity
        
        faithfulness = util.cos_sim(justification_emb, context_emb).item()
        explanation_relevance = util.cos_sim(justification_emb, query_emb).item()

    except Exception as e:
        # Tangani kesalahan saat perhitungan cosine similarity
        print(f"Error during similarity calculation2: {e}")
        return 0.0
    

    #context_emb = model.encode(context_text, convert_to_tensor=True)
    #justification_emb = model.encode(justification_text, convert_to_tensor=True)
    #query_emb = model.encode(query_text, convert_to_tensor=True)


    
    return explanation_relevance,faithfulness



def llm_as_judge(df_api_type, query, user_keywords,selected_domain_final, selected_field_final):
    
    
    
    # 1. ========== CONFIGURATION ==========
    client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-",
    )
    base_url="https://openrouter.ai/api/v1"
    headers = {
    "Authorization": "sk-",
    "Content-Type": "application/json",
    # Enable debugging to see parameter transformations and defaults
    "X-OpenRouter-Metadata": "enabled" 
}
    # ==================================


    categories = ['Highly relevant', 'Moderately relevant', 'Somewhat relevant', 'Low relevance']

    # ---------------------------------------------
    # 2. Prepare few-shot examples (from top ranked)
    # ---------------------------------------------


    relevance_map = {
    3:"Highly relevant",
    2:"Moderately relevant",
    1:"Somewhat relevant",
    0:"Low relevance"
    }

    few_shot_text = ""

    # pastikan numeric
    df_api_type['Final Average Human Rating'] = pd.to_numeric(
        df_api_type['Final Average Human Rating'], errors='coerce'
    )

    for cat in categories:
        print("\n=== CATEGORY:", cat, "===")

        # 🔹 PRIORITY 1: dari human rating
        filtered = df_api_type[
            (df_api_type['Final Average Human Rating'].notna()) &
            (df_api_type['Final Average Human Rating'] >= 0)
        ].copy()

        # mapping rating → category
        filtered['mapped_category'] = filtered['Final Average Human Rating'].apply(
            lambda x: relevance_map.get(int(round(x)), None)
        )

        # ambil sesuai kategori
        filtered_cat = filtered[filtered['mapped_category'] == cat]

        print("From human rating:", len(filtered_cat))

        # 🔹 PRIORITY 2: fallback
        if len(filtered_cat) >= 3:
            examples = filtered_cat.head(3)
        else:
            fallback = df_api_type[
                df_api_type['Relevance Category'] == cat
            ]

            examples = pd.concat([filtered_cat, fallback]) \
                .drop_duplicates(subset=['Title']) \
                .head(3)

        print("Final selected:", len(examples))
            
        for i, row in examples.iterrows():
            val = row["Final Average Human Rating"]

            if pd.notna(val) and float(val)>= 0:
                rounded_val = math.floor(float(val) + 0.5)
                final_rating = relevance_map.get(rounded_val, "-")
            else:
                final_rating = "-"

                print("final_rating 1",final_rating)
                
            discipline_prompt = row['Discipline(s)']
            keywords_prompt = row['Extracted Keywords']

            if discipline_prompt == "N/A":
                discipline_prompt = "-"

            if keywords_prompt == "N/A":
                keywords_prompt = "-"

            few_shot_text += f"""
      
    Example of results ({cat}):
    Paper Title: {row['Title']}
    Paper Abstract: {row['Abstract']}
    Paper Discipline or Subject: {discipline_prompt}
    Paper Keywords: {keywords_prompt}
    Current Relevant Category: {row['Relevance Category']}
    Human Rating: {final_rating}

    ---
    """

    # ---------------------------------------------
    # 3. Function to query LLM with JSON output
    # ---------------------------------------------
    def apply_llm(prompt: str, retries=3, delay=2):

        for attempt in range(1, retries + 1):
            try:
                response = client.chat.completions.create(
                    model='mistralai/mistral-small-24b-instruct-2501',
                    # model='google/gemini-2.5-flash-lite',
                    # model='mistralai/Mistral-7B-Instruct-v0.3',
                    messages=[
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    temperature=0,
                    top_p=1.0,
                    max_tokens=256,
                    seed=42
                )
                print("==========LLM Response:", response)
                content = response.choices[0].message.content
                # Clean possible code block markers
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"```$", "", content)
                content = content.strip()
                print("Full Response:", response.model_dump())
                
                if not content:
                    raise ValueError("Empty response from model")
                
                result_json = json.loads(content)
                return result_json
            
            except Exception as e:
                print(f"[MODEL ERROR] Attempt {attempt}: {e}")
                if attempt < retries:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("All retry attempts failed.")
                    return {}

    # ---------------------------------------------
    # 4. Iterate over candidate papers
    # ---------------------------------------------
    
    
    df_api_type_selected = df_api_type[:50]

    #Given the following examples of relevance categories which generated by sentence embedding using mpnet-base-v2-model, text similarity, and threshold categories:

    #{few_shot_text}

    
       
    def process_paper(row):

        relevance_map = {
        3:"Highly relevant",
        2:"Moderately relevant",
        1:"Somewhat relevant",
        0:"Low relevance"
        }


        val = row["Final Average Human Rating"]

        if pd.notna(val) and float(val)>= 0 :
            rounded_val = math.floor(float(val) + 0.5)
            final_rating = relevance_map.get(rounded_val, "-")
        else:
            final_rating = "-"

            #print("final_rating 2",final_rating)


        prompt = f"""
            You are an academic paper relevance assessor or expert judgment in expertise fields. 

            Given the following few-shot examples of relevance categories which previously generated by sentence embedding using mpnet-base-v2-model and text similarity:

            {few_shot_text}

            However, the few-shot examples are provided only as additional references, you may update the relevance category based on your own expert judgment in your field with reasonable justification.
        
            
            Evaluate the relevance of the paper to query by considering the following aspects:
            1. Research Domain
            Determine whether the query and the paper belong to the same broad research domain.
            Examples include Physical Sciences, Social Sciences, Health Sciences, Life Sciences, Multidisciplinary, and etc.

            2. Subject Field
            Determine whether the query and the paper belong to the same academic discipline or subject field within the research domain.
            Examples include Mathematics, Computer Science, Mechanical Engineering, Public Health, Economics, Law, Psychology, Education, Chemistry, Physics, and etc.

            3. Research Topic
            Determine whether both studies investigate the same or closely related research topics.
            Examples include Programming Learning Assistant System, Brain Tumor Segmentation, Renewable Energy Forecasting, Supply Chain Risk Management, and etc.

            4. Research Focus
            Determine whether both studies address the same core research problem, objective, or research question.
            Examples include developing a new algorithm, improving prediction accuracy, evaluating model performance, enhancing interpretability, optimizing computational efficiency, conducting a systematic literature review, and etc.

            5. Research Methods
            Determine whether both studies employ similar methodologies, analytical approaches, algorithms, models, or experimental procedures.
            Examples include Transformer-based models, Large Language Models (LLMs), Graph Neural Networks (GNNs), Convolutional Neural Networks (CNNs), Support Vector Machines (SVMs), Random Forests, and etc.

                
            Follow these rules when assigning the relevance categories of each paper to the query context: 

            1. Highly relevant:The paper belongs to the same research domain and subject field as the query, investigates the same research topic, addresses the same or highly similar research objective, and applies similar research methods or approaches. The paper directly addresses the main focus of the query.

            2. Moderately relevant:The paper belongs to the same research domain and subject field, investigates the same or closely related research topic, but addresses a narrower or more specific research objective than the query. Similar or partially similar research methods provide additional support for this category. The paper is strongly related to the query but does not fully cover the broader objective.

            3. Somewhat relevant:The paper belongs to the same or a related research domain and subject field, investigates a related research topic, and addresses a broader, more general, or different research objective than the query. The paper shares some relevant aspects with the query but does not directly address the main research objective.

            4. Low relevance:The paper belongs to a different research domain or subject field, or investigates an unrelated research topic. Similar research methods, algorithms, or technical approaches alone are not sufficient to classify a paper as relevant.
            
            For all relevance categories, ignore the scope of geographic location.
            Please do not overestimate the relevance of a category, do not assign Highly relevant if the paper focuses on a narrower or more specific subtopic of the query context.


            Now assess the relevance of the following primary section of paper to the query context:

                1. User Query: 
                    a. Title/topic: {query}
                    b. Keywords (as supplementary): {user_keywords}
                    c. Domain: {selected_domain_final}
                    d. Field: {selected_field_final}
                2. Paper Information:
                    a. Paper Title: {row['Title']}
                    b. Paper Abstract: {row['Abstract']}
                    c. Paper Discipline or Subject: {discipline_prompt}
                    d. Paper Keywords: {keywords_prompt}
                    e. Current Relevance Category: {row['Relevance Category']}
                    

            Please output a JSON object with these keys:
            {{
                "Updated Relevance Category": <Highly relevant | Moderately relevant | Somewhat relevant | Low relevance>,
                "Short Explanation": "<Provide a brief justification in 1–2 sentences. Start by explaining the direct relationship between the paper and the user's query topic. Then provide supporting evidence from the paper metadata, such as the main objective, developed system, or approach. Focus on the most relevant information only and avoid listing all relevance criteria or adding unsupported claims.>",
                
            }} 


            """
        result_json = apply_llm(prompt)
        


        
        pred_cat = result_json.get("Updated Relevance Category")
        just = result_json.get("Short Explanation", "")
        human_rating_cat_hist=result_json.get("Human Rating")
        
        return pred_cat, just, human_rating_cat_hist
        
    rows = [row for _, row in df_api_type_selected.iterrows()]

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(process_paper, rows))
        
    pred_cat = [r[0] for r in results]
    just = [r[1] for r in results]
    human_rating_cat_hist = [r[2] for r in results]

    df_api_type_selected['AI Relevance Category'] = pred_cat
    df_api_type_selected['AI Explanation'] = just
        
    #predicted_categories.append(pred_cat)
    #justifications.append(just)
        
    #json_store.append(result_json)
        
    # Map kategori ke skor numerik
    relevance_score_map = {
        "Highly relevant":3,
        "Moderately relevant":2,
        "Somewhat relevant":1,
        "Low relevance":0
    }

    # Map skor kembali ke kategori
    score_to_category = {v: k for k, v in relevance_score_map.items()}
        
    # Ambil human rating
    #human_rating = row.get('Final Average Human Rating', -2)
    #human_rating = df_api_type_selected['Final Average Human Rating']
    
    final_categories = []
    final_explanations = []
    final_human_rating_cat = []

    for i, row in df_api_type_selected.iterrows():

        human_rating = row.get('Final Average Human Rating', -2)
        ai_cat = pred_cat[i]

        ai_score = relevance_score_map.get(ai_cat, 0)

        if human_rating >= 0:

            combined_score = round((0.6 * float(human_rating)) + (0.4 * float(ai_score)))
            final_cat = score_to_category.get(combined_score, ai_cat)

            explanation = (
                f"Human and AI Ratings considered both 60% Human Rating ({human_rating:.2f}) "
                f"+ 40% AI Suggested ({ai_score}) = {combined_score}, "
                f"which corresponds to '{final_cat}'"
            )

        else:

            final_cat = ai_cat

            explanation = (
                f"Human Ratings unavailable ({human_rating}), "
                f"Final Relevance Category uses AI Suggested '{ai_cat}'"
            )

        final_categories.append(final_cat)
        final_explanations.append(explanation)
        final_human_rating_cat.append(human_rating_cat_hist)

    # ---------------------------------------------
    # 5. Save results into DataFrame 
    # ---------------------------------------------
    #df_api_type_selected = df_api_type_selected.copy()
    #df_api_type_selected['AI Relevance Category'] = predicted_categories
    #df_api_type_selected['AI Explanation'] = justifications
    df_api_type_selected['Human Rating Category History'] = final_human_rating_cat
    df_api_type_selected['Human and AI Ratings'] = final_categories
    df_api_type_selected['Human and AI Ratings Explanation'] = final_explanations
    
    #df_api_type_selected.to_csv("df_api_type_selected.csv", index=False)
	
    
    return df_api_type_selected



# Fungsi untuk menghitung skor menggunakan PAV dengan sigmoid
def apply_pav_with_sigmoid(bm25_scores, lambda_value=1.0):
    bm25_min = np.min(bm25_scores)  # Nilai BM25 minimum dari seluruh koleksi dokumen
    # Terapkan rumus sigmoid
    pav_scores = 1 / (1 + np.exp(-lambda_value * (bm25_scores - bm25_min)))
    return pav_scores

def plot_donut_chart(df, column_name, title, colors):
    # Count the occurrences of each category in the column
    access_counts = df[column_name].value_counts()

    # Create a donut chart using Plotly with custom colors and a thinner hole
    fig = px.pie(
        access_counts, 
        names=access_counts.index, 
        values=access_counts.values, 
        hole=0.5,  # This creates a thinner donut
        title=title,
        color=access_counts.index,  # Color segments by value
        color_discrete_map=colors  # Custom colors
    )

    # Customize the chart for smaller text and interactivity
    fig.update_layout(
        title_font_size=16,  # Smaller title font size
        legend_title_font_size=12,  # Smaller legend title font size
        legend_font_size=10,  # Smaller legend font size
        margin=dict(t=40, b=40, l=40, r=40),  # Add margins to fit the smaller size
        height=400,  # Adjust height of the chart
    )
    
    return fig

def create_stacked_bar_chart(successfully_collected, total_available_pdf1, total_available_pdf2):
    """
    Generates a stacked horizontal bar chart for PDF availability before and after enhancement.

    Args:
        successfully_collected (int): Total number of papers collected.
        total_available_pdf1 (int): Available PDFs before enhancement.
        total_available_pdf2 (int): Available PDFs after enhancement.

    Returns:
        Plotly Express Figure object.
    """
    # Calculate "Not Available PDF"
    not_available_pdf1=0
    not_available_pdf2=0
    not_available_pdf1 = successfully_collected - total_available_pdf1
    not_available_pdf2 = successfully_collected - total_available_pdf2

    # Prepare DataFrame for Plotly Express
    data = {
        "Category": ["Before Enhancement", "After Enhancement"] * 2,
        "Count": [
            total_available_pdf1, total_available_pdf2,
            not_available_pdf1, not_available_pdf2
        ],
        "PDF Status": ["Available PDF", "Available PDF", "Not Available PDF", "Not Available PDF"]
    }

    df = pd.DataFrame(data)

    # Create Stacked Bar Chart
    fig = px.bar(
        df,
        x="Count",
        y="Category",
        color="PDF Status",
        orientation="h",
        title="PDF Availability Before and After Enhancement",
        color_discrete_map={"Available PDF": "blue", "Not Available PDF": "orange"},
        height=400  # Adjust chart height for compactness
    )
    fig.update_traces(width=0.5)  # Make the bars thinner for a cleaner look

    return fig





def fetch_data_from_api(api_function, query, user_keywords=None):
    """Fungsi untuk memanggil API dan mengembalikan hasil."""
    try:
        if api_function.__name__ == "get_ai_data":
            results, stats = api_function(query, user_keywords)
        else:
            results, stats = api_function(query)

        return results, stats

    except Exception as e:
        st.error(f"Error in API {api_function.__name__}: {e}")
        return [], {}


def get_connection():
    return mysql.connector.connect(
        host="",
        user="",
        password="",
        database="",
        port=3306)

def insert_query_history(api_source, domain, field, title, keywords):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            insert_query = """
            INSERT INTO tb_query_history
            (query_api_source_hist, query_domain_hist, query_field_hist, query_title_hist, query_keywords_hist, username, created_at_query_hist)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            data = (api_source, domain, field, title, keywords, st.session_state['username'])
            cursor.execute(insert_query, data)
            conn.commit()
            return cursor.lastrowid
    except mysql.connector.Error as e:
        st.error(f"Database error tb_query_history: {e}")
        return None
        
        



def insert_papers(df):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        inserted_ids = []

        # ========================
        # QUERY CEK APAKAH SUDAH ADA
        # ========================
        check_query = "SELECT id_paper FROM tb_papers WHERE title_paper = %s"

        # ========================
        # QUERY INSERT BARU
        # ========================
        insert_query = """
        INSERT INTO tb_papers
        (external_paper_id, title_paper, abstract_paper, year_paper, authors_paper, citation_count_paper,
         disciplines_paper, document_type_paper, journal_name_paper, journal_volume_paper, journal_pages_paper,
         conference_name_paper, publication_type_paper, venue_paper, publication_date_paper, is_open_access_pdf_url_paper,
         open_access_pdf_url_paper, pdf_available_paper, url_paper, doi_paper,
         extracted_keywords_paper, source_paper, issn_paper, impact_factor_paper,
         emb_title_vector, emb_abstract_vector, emb_keywords_vector, emb_disciplines_vector,
         created_at_paper)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        for idx, row in df.iterrows():

            try:
                title_value = row['Title']

                # ================================
                # 1️⃣ CEK APakah SUDAH ADA DI DB
                # ================================
                cursor.execute(check_query, (title_value,))
                existing = cursor.fetchone()

                if existing:
                    # Sudah ada → ambil ID saja
                    existing_id = existing[0]
                    inserted_ids.append(existing_id)
                    continue  # lanjut ke row berikutnya tanpa insert

                # ================================
                # 2️⃣ JIKA BELUM ADA → INSERT BARU
                # ================================
                data = (
                    row['Paper Id'],
                    row['Title'],
                    row['Abstract'],
                    row['Year'],
                    row['Authors'],
                    row['Citation Count'],
                    row['Discipline(s)'],
                    row['Document Type'],
                    row['Journal Name'],
                    row['Journal Volume'],
                    row['Journal Pages'],
                    row['Conference Name'],
                    row['Publication Type'],
                    row['Venue'],
                    format_date_for_mysql(row['Publication Date']),
                    row['Is Open Access'],
                    row['Open Access PDF URL'],
                    row['PDF Available'],
                    row['URL'],
                    row['DOI'],
                    row['Extracted Keywords'],
                    row['Source'],
                    row['ISSN'],
                    row['Impact Factor'],
                    json.dumps(row['Vector Embedding Title'].tolist()),
                    json.dumps(row['Vector Embedding Abstract'].tolist()),
                    json.dumps(row['Vector Embedding Extracted Keywords'].tolist()),
                    json.dumps(row['Vector Embedding Discipline(s)'].tolist())
                )

                cursor.execute(insert_query, data)
                inserted_ids.append(cursor.lastrowid)

            except Exception as e:
                st.error(f"❌ Gagal insert row index {idx}: {e}")

                # 🔥 PRINT SEMUA KOLOM untuk debug
                st.write("### Debug Row Data")
                try:
                    for i, val in enumerate(data):
                        st.write(f"- Kolom {i+1}: {val}  (type={type(val)})")
                except:
                    st.write("Gagal menampilkan data row untuk debug.")

                return None  # stop proses insert

        conn.commit()
        return inserted_ids

    except mysql.connector.Error as e:
        st.error(f"Database error tb_papers: {e}")
        return None

    finally:
        if cursor: cursor.close()
        if conn: conn.close()


    

def insert_ai_rating(df, get_id_query_history, get_id_papers):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        inserted_ids = []

        insert_query = """
        INSERT INTO tb_ai_rating (
            id_paper, id_query_hist, 
            title_bm25_score, abstract_bm25_score, total_bm25_score,
            title_bert_score, abstract_bert_score, extracted_bert_score,
            discipline_norm_score, citation_norm_score, impactf_norm_score, total_sim_bert_score,
            sent_emb_rev_cat, gen_ai_rev_cat, ai_explain, created_at_ai_rating
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        for i, (_, row) in enumerate(df.iterrows()):
            data = (
                get_id_papers[i],
                get_id_query_history,
                row['Title BM25 Score'],
                row['Abstract BM25 Score'],
                row['Total BM25 Score'],

                row['Title BERT Score'],
                row['Abstract BERT Score'],
                row['Extracted Keywords BERT Score'],

                row['Discipline(s) BERT Score'],
                row['Citation Count Norm Score'],
                row['Impact Factor Norm Score'],
                row['Similarity Score'],

                row['Relevance Category'],
                row['AI Relevance Category'],
                row['AI Explanation']
            )
            cursor.execute(insert_query, data)
            inserted_ids.append(cursor.lastrowid)  # simpan ID tiap insert

        conn.commit()
        return inserted_ids

    except mysql.connector.Error as e:
        st.error(f"Database Insert Error tb_ai_rating: {e}")
        return None

    finally:
        cursor.close()
        conn.close()


def insert_human_rating(df, get_id_papers, get_id_query_history):
    """Insert human rating results into tb_human_rating table."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO tb_human_rating (
                id_paper, id_query_hist,
                human_rating_high, human_rating_moderate,
                human_rating_somewhat, human_rating_low,
                created_at_human_rating
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """

        select_id_paper = """
            SELECT id_paper
            FROM tb_papers
            WHERE title_paper = %s
            LIMIT 1
        """
	
        values = []

        for _, row in df.iterrows():
            r = row["User Rating"]
            title = row["Title"]   # sesuaikan dengan nama kolom title di df

            if r is None:
                continue

            # ambil id_paper berdasarkan title
            cursor.execute(select_id_paper, (title,))
            result = cursor.fetchone()

            if result is None:
                continue  # skip kalau paper tidak ditemukan

            id_paper = result[0]
	
            values.append((
                id_paper,
                get_id_query_history,
                1 if r == "👍 High Relevant" else 0,
                1 if r == "👌 Moderate Relevant" else 0,
                1 if r == "✋ Somewhat Relevant" else 0,
                1 if r == "👎 Low Relevance" else 0
            ))

        if values:
            cursor.executemany(insert_query, values)
            conn.commit()


    except mysql.connector.Error as e:
        st.error(f"Database Insert Error tb_human_rating: {e}")
        return None
    

    finally:
        cursor.close()
        conn.close()




def insert_syst_perform(average_ragas_scores, performance_retrieval,collection_retrieval, get_id_query_history):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO tb_system_performance (
            id_query_hist, explanation_relevance, faithfulness, paper_collected,
            response_time, initial_memory_usage, final_memory_usage, memory_used,
            percentage_cpu_usage, total_logical_processor, total_cpu_usage_core, created_at_syst_perform
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        values = (
            get_id_query_history,
            average_ragas_scores.get('Explanation Relevance'),
            average_ragas_scores.get('Faithfulness'),
            collection_retrieval.get('successfully_collected'),
            performance_retrieval.get('Execution Time'),
            performance_retrieval.get('Initial Memory Usage'),
            performance_retrieval.get('Final Memory Usage'),
            performance_retrieval.get('Memory Used'),
            performance_retrieval.get('Percentage of CPU Usage'),
            performance_retrieval.get('Total Logical Processor'),
            performance_retrieval.get('Total CPU Usage in Core')

        )

        cursor.execute(insert_query, values)
        conn.commit()

        return cursor.lastrowid  # id record yang berhasil disimpan

    except mysql.connector.Error as e:
        st.error(f"Database Insert Error tb_system_performance: {e}")
        return None

    finally:
        cursor.close()
        conn.close()


def select_check_exist_title_api(df_api_type):
    
    conn = get_connection()
    cursor = conn.cursor()

    # Ambil semua title yang sudah ada
    cursor.execute("SELECT title_paper FROM tb_papers")
    existing_titles = [row[0] for row in cursor.fetchall()]

    # Filter df_api_type: hanya title yang belum ada di DB
    df_api_type = df_api_type[~df_api_type['Title'].isin(existing_titles)]
    
    return df_api_type



def select_get_title_db(user_query):

    keywords = user_query.lower().split()

    # LIKE dynamic clauses
    like_query_history = " AND ".join([f"a.query_title_hist LIKE '%{kw}%'" for kw in keywords])
    like_title = " AND ".join([f"c.title_paper LIKE '%{kw}%'" for kw in keywords])
    like_abstract = " AND ".join([f"c.abstract_paper LIKE '%{kw}%'" for kw in keywords])

    sql = f"""
    SELECT *
    FROM (
        SELECT c.*
        FROM tb_query_history a
        JOIN tb_ai_rating b ON a.id_query_hist = b.id_query_hist
        JOIN tb_papers c ON b.id_paper = c.id_paper
        WHERE {like_query_history}

        UNION

        SELECT c.*
        FROM tb_papers c
        WHERE ({like_title})
           OR ({like_abstract})
    ) AS combined_results
    GROUP BY id_paper;
    """
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql)
    rows = cursor.fetchall()

    df = pd.DataFrame(rows)

    # Rename columns to desired output format
    rename_map = {
        "external_paper_id": "Paper Id",
        "title_paper": "Title",
        "abstract_paper": "Abstract",
        "year_paper": "Year",
        "authors_paper": "Authors",
        "citation_count_paper": "Citation Count",
        "disciplines_paper": "Discipline(s)",
        "document_type_paper": "Document Type",
        "journal_name_paper": "Journal Name",
        "journal_volume_paper": "Journal Volume",
        "journal_pages_paper": "Journal Pages",
        "conference_name_paper": "Conference Name",
        "publication_type_paper": "Publication Type",
        "venue_paper": "Venue",
        "publication_date_paper": "Publication Date",
        "is_open_access_pdf_url_paper": "Is Open Access",
        "open_access_pdf_url_paper": "Open Access PDF URL",
        "pdf_available_paper": "PDF Available",
        "url_paper": "URL",
        "doi_paper": "DOI",
        "extracted_keywords_paper": "Extracted Keywords",
        "source_paper": "Source",
        "issn_paper": "ISSN",
        "impact_factor_paper": "Impact Factor",
        "emb_title_vector": "Vector Embedding Title",
        "emb_abstract_vector": "Vector Embedding Abstract",
        "emb_keywords_vector": "Vector Embedding Extracted Keywords",
        "emb_disciplines_vector": "Vector Embedding Discipline(s)"
        
    }

    df = df.rename(columns=rename_map)

    # Ensure all desired columns exist (fill empty if missing)
    desired_cols = list(rename_map.values())
    for col in desired_cols:
        if col not in df.columns:
            df[col] = None

    # Reorder DataFrame columns
    df_api_type = df[desired_cols]

    return df_api_type

def select_human_rating_stats(df, query):

    conn = get_connection()
    results = []
    threshold=4
    
    # 🔹 Preprocess query → keywords
    keywords = query.lower().split()
    like_clauses = " + ".join(["(LOWER(query_title_hist) LIKE %s)" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]

    with conn.cursor(dictionary=True, buffered=True) as cursor:

        # =====================================================
        # STEP 1: Ambil query_history yang match (≥ threshold)
        # =====================================================
        sql_qh = f"""
        SELECT id_query_hist
        FROM tb_query_history
        WHERE {like_clauses} >= %s
        """

        cursor.execute(sql_qh, params + [threshold])
        qh_rows = cursor.fetchall()

        qh_ids = [row['id_query_hist'] for row in qh_rows]

    # ❗ Kalau tidak ada query_history yang match
    if len(qh_ids) == 0:
        for title in df['Title']:
            results.append({
                'title_paper': title,
                'final_human_average': -2  # tidak ada data
            })
        return pd.DataFrame(results)

    # =====================================================
    # STEP 2: Ambil rating berdasarkan qh_ids
    # =====================================================
    placeholders = ",".join(["%s"] * len(qh_ids))

    sql_main = f"""
    SELECT
        p.id_paper,
        p.title_paper,
        CASE 
            WHEN SUM(hr.human_rating_high + hr.human_rating_moderate + 
                     hr.human_rating_somewhat + hr.human_rating_low) > 0
            THEN (
                SUM(hr.human_rating_high)*3 +
                SUM(hr.human_rating_moderate)*2 +
                SUM(hr.human_rating_somewhat)*1
            ) /
            SUM(hr.human_rating_high +
                hr.human_rating_moderate +
                hr.human_rating_somewhat +
                hr.human_rating_low)
            ELSE NULL
        END AS final_human_average
    FROM tb_papers p
    LEFT JOIN tb_human_rating hr 
        ON hr.id_paper = p.id_paper
    WHERE p.title_paper = %s
    AND hr.id_query_hist IN ({placeholders})
    GROUP BY p.id_paper, p.title_paper
    """

    # =====================================================
    # LOOP tiap paper
    # =====================================================
    for title in df['Title']:

        with conn.cursor(dictionary=True, buffered=True) as cursor:
            cursor.execute(sql_main, [title] + qh_ids)
            row = cursor.fetchone()

        if row is None:
            row = {
                'title_paper': title,
                'final_human_average': -2  # tidak ada rating sama sekali
            }

        elif row['final_human_average'] is None:
            row['final_human_average'] = -1  # ada tapi kosong

        results.append(row)

    # =====================================================
    # MERGE ke dataframe awal
    # =====================================================
    df_results = pd.DataFrame(results)

    df_merged = df.merge(
        df_results[['title_paper', 'final_human_average']],
        left_on='Title',
        right_on='title_paper',
        how='left'
    )

    df_merged.drop(columns=['title_paper'], inplace=True)

    df_merged.rename(columns={
        'final_human_average': 'Final Average Human Rating'
    }, inplace=True)

    return df_merged


def show_data_editor(df_api_type, column_config_, rating_options, db_ids):

    # Encode gambar ke base64
    with open("assets/relevance_ratings_expert_judgment.jpg", "rb") as f:
        data = f.read()
        data_url = "data:image/jpg;base64," + base64.b64encode(data).decode()

    # CSS untuk lingkaran tanda seru dan hover preview
    st.markdown("""
    <style>
    .hover-preview-container {
        position: relative;
        display: inline-block;
    }

    .hover-preview-container img {
        display: none;
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        max-width: 45%;
        max-height: 45%;
        border: 3px solid #444;
        box-shadow: 4px 4px 20px rgba(0,0,0,0.7);
        z-index: 1000;
    }

    .hover-preview-container:hover img {
        display: block;
    }

    .exclamation-circle {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background-color:#f1c40f;
        color:white;
        font-weight:bold;
        font-size:16px;
        cursor:pointer;
        margin-left:10px;
        border: 2px solid #d39e00;
        user-select: none;
    }
    </style>
    """, unsafe_allow_html=True)


        

    # === MESSAGE CONTAINER DI ATAS TABEL ===
    messages = st.container()

    # ---------------------------------------
    # TABEL DATA EDITOR
    # ---------------------------------------
    edited_df = st.data_editor(
        df_api_type,
        column_config=column_config_,
        hide_index=True,
        use_container_width=True,
        height=400,
        key="rating_editor"
    )

    # Validasi rating per row
    warnings_list = []
    multiple_choice_detected = False

    for idx in edited_df.index:
        selected = [edited_df.at[idx, opt] for opt in rating_options]
        if sum(selected) > 1:
            multiple_choice_detected = True
            warnings_list.append(f"⚠ Row {idx + 1}: More than one rating selected!")
            for opt in rating_options:
                edited_df.at[idx, opt] = False

    # Convert to single rating column
    edited_df["User Rating"] = edited_df.apply(
        lambda r: next((opt for opt in rating_options if r[opt] is True), None),
        axis=1
    )

    any_rating_selected = edited_df["User Rating"].notna().any()

    # =================================
    # PESAN DITEMPATKAN DI ATAS TABEL
    # =================================
    with messages:
        for msg in warnings_list:
            st.error(msg)

        if multiple_choice_detected:
            st.error("❌ Invalid rating selection: Fix multiple ratings before submitting.")
        elif not any_rating_selected:
            # Warning dengan lingkaran tanda seru sebagai tombol hover
            st.markdown(f"""
            <div style="border-left:4px solid #f1c40f; padding:8px; background-color:#fff3cd; display:flex; align-items:center;">
                ⚠ No rating selected. You can participate by providing a relevance rating for the paper(s). Learn more information here
                <span class="hover-preview-container">
                    <span class="exclamation-circle">!</span>
                    <img src="{data_url}" />
                </span>
            </div>
            """, unsafe_allow_html=True)
    # =================================
    # BUTTON SUBMIT
    # =================================
    if not multiple_choice_detected and any_rating_selected:
        btn_submit_human_rating = st.button("Submit Rating", type="primary")

        if btn_submit_human_rating:
            try:
                insert_human_rating(
                    edited_df,
                    db_ids.get("get_id_papers"),
                    db_ids.get("get_id_query_history")
                )
                with messages:
                    st.success("✅ Rating submitted successfully!")

            except Exception as e:
                with messages:
                    st.error(f"Database insert failed: {e}")

 

def run_retrieval_pipeline(query, get_api_type_data, api_option,user_keywords,selected_domain_final,selected_field_final):
    
    
    api_option = json.dumps(api_option)   
    user_keywords = json.dumps(normalize_keywords(user_keywords))

    
    #insert tb_query_history
    try:
        get_id_query_history = insert_query_history(api_option, selected_domain_final, selected_field_final, query, user_keywords)
        #st.success(f"Query ID tb_query_history: {get_id_query_history}")
    except Exception as e:
        st.error(f"Database insert failed: {e}")   

    api_option = json.loads(api_option)
    user_keywords = json.loads(user_keywords)
    
    # Display spinner while fetching data
    with st.spinner('Fetching data... This may take a moment...'):
        # Start timer
        start_time = time.time()
        
        # Log initial CPU and memory usage
        initial_cpu = psutil.cpu_percent(interval=None)
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # Convert to MB

        if api_option != ["Multiple API Integration"] and len(api_option)==1:
    
            try:
                if(api_option==["AI-Assisted Search API"]):
                    results_list, collection_retrieval = get_ai_data(query, user_keywords)
                else:
                    results_list, collection_retrieval = get_api_type_data(query)
                #print("collection_retrieval", collection_retrieval)

            except Exception as e:

                st.warning(f"Rate limit reached. {api_option} request skipped.")
         
       

        else:
            st.success((api_option))
            #st.write(f"Fetching data from multiple APIs: {', '.join([fn.__name__ for fn in get_api_type_data])}")
            results_list = []
            collection_retrieval = {"successfully_collected": 0,
                "total_available_pdf1": 0,
                "total_available_pdf2": 0}
            

            with ThreadPoolExecutor(max_workers=len(get_api_type_data)) as executor:
                # Submit semua API ke thread pool
                future_to_api = {
                    executor.submit(fetch_data_from_api, api_function, query): api_function
                    for api_function in get_api_type_data
                }
                for future in as_completed(future_to_api):
                    api_function = future_to_api[future]
                    try:
                        results, stats = future.result()
                        results_list.extend(results)
                        # Gabungkan statistik retrieval
                        for key in collection_retrieval:
                            collection_retrieval[key] += stats.get(key, 0)
                    except Exception as e:
                        st.error(f"Error fetching data from {api_function.__name__}: {e}")
                        #st.error(f"Error fetching data from {getattr(api_function, '__name__', str(api_function))}: {e}")
                
        

    # Convert results to DataFrame
    df_api_type = pd.DataFrame(results_list)
    #df_api_type.to_csv("output_merger_all.csv",index=False,encoding="utf-8-sig")
    #df_api_type.to_csv("merger_results_time_limit.csv",index=False,encoding="utf-8-sig")

    # Normalisasi kolom 'Title': Menggunakan title case dan menghapus titik di akhir
    #df_api_type['Title'] = df_api_type['Title'].apply(lambda x: x.title().rstrip('.') if isinstance(x, str) else x)
    # Periksa apakah kolom 'Title' ada dalam DataFrame
    if 'Title' in df_api_type.columns:
        # Cek apakah semua data kosong
        if df_api_type['Title'].isna().all():
            st.warning("⚠️ The title you are looking for is empty in the search results! ")
            st.stop()
        else:
            
            # Normalisasi kolom 'Title': Menggunakan title case dan menghapus titik di akhir
            df_api_type['Title'] = df_api_type['Title'].apply(
                lambda x: x.title().rstrip('.') if isinstance(x, str) else x
            )
            # Membersihkan simbol-simbol dan spasi ganda di kolom 'Title'
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'[\"[\]\s]{2,}', ' ', regex=True)  # Menghapus tanda kutip, kurung, dan spasi ganda
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'["\[\]]', '', regex=True)  # Menghapus tanda kutip dan kurung
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'\s+', ' ', regex=True)  # Mengganti spasi ganda dengan spasi tunggal
            df_api_type['Title'] = df_api_type['Title'].str.strip()  # Menghapus spasi di awal dan akhir
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'[^\x00-\x7F]+', '-', regex=True) #Mengganti encode text ・・ menjadi -
            
            
            
            print("Starting data preprocessing and merging duplicates...")
            # -------------------------
            # 1. Preprocessing
            # -------------------------    
            
            
            # Normalisasi kolom 'Title': Menggunakan title case dan menghapus titik di akhir
            df_api_type['Title'] = df_api_type['Title'].apply(
                lambda x: x.title().rstrip('.') if isinstance(x, str) else x
            )
            # Membersihkan simbol-simbol dan spasi ganda di kolom 'Title'
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'[\"[\]\s]{2,}', ' ', regex=True)  # Menghapus tanda kutip, kurung, dan spasi ganda
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'["\[\]]', '', regex=True)  # Menghapus tanda kutip dan kurung
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'\s+', ' ', regex=True)  # Mengganti spasi ganda dengan spasi tunggal
            df_api_type['Title'] = df_api_type['Title'].str.strip()  # Menghapus spasi di awal dan akhir
            df_api_type['Title'] = df_api_type['Title'].str.replace(r'[^\x00-\x7F]+', '-', regex=True) #Mengganti encode text ・・ menjadi -
            
 
            df = df_api_type.copy()

            # -------------------------
            # 2. Assume N/A as missing value
            # -------------------------

            df = df.replace("N/A", pd.NA)


            # -------------------------
            # 3. Count metadata completeness
            # -------------------------

            df["completeness"] = df.notna().sum(axis=1)


            # -------------------------
            # 4. Extract preprint version from URL
            # -------------------------

            df["version"] = (
                df["URL"]
                .str.extract(r'v(\d+)$')[0]
                .fillna(0)
                .astype(int)
            )


            # -------------------------
            # 5. Create key duplicate
            # Prioritize DOI
            # If value is " ", use Title
            # Normalize lowercase
            # -------------------------

            df["dup_key"] = (
                df["DOI"]
                .fillna(df["Title"])
                .str.lower()
                .str.strip()
                .str.replace(r'\s+', ' ', regex=True)
            )

            # -------------------------
            # 6. Sorting prioritize
            # - The new version
            # - The most completeness
            # -------------------------

            df_sorted = df.sort_values(
                ["dup_key","version","completeness"],
                ascending=[True,False,False]
            )

            # -------------------------
            # 7. Merge duplicate metadata
            # Fill out missing field from other field
            # -------------------------

            def merge_group(group):

                # record terbaik = baris pertama
                best = group.iloc[0].copy()

                for col in group.columns:

                    if pd.isna(best[col]):

                        # cari value yang tidak kosong
                        values = group[col].dropna()

                        if len(values) > 0:
                            best[col] = values.iloc[0]

                return best


            df_clean = (
                df_sorted
                .groupby("dup_key", as_index=False)
                .apply(merge_group)
                .reset_index(drop=True)
            )


            # -------------------------
            # 8. Drop auxiliary column
            # -------------------------

            df_clean = df_clean.drop(
                columns=["completeness","version","dup_key"]
            )


            # -------------------------
            # 9. Optional: convert fillna to N/A
            # -------------------------

            df_api_type = df_clean.fillna("N/A")
            #df_api_type.to_csv("output_new.csv",index=False,encoding="utf-8-sig")
            #df_api_type.to_excel("output_merger_all.xlsx", index=False)
            
            
            # -------------------------
            # 10. #Check existing paper in DB based on title --> get new record
            # -------------------------
            
    
            #df_api_type = select_check_exist_title_api(df_api_type)

            # -------------------------
            # 11. Check existing paper in DB based similarity search query --> get old record
            # -------------------------
            
            stop_words = set(stopwords.words('english'))
            words = query.split()
            important_words = [w for w in words if w.lower() not in stop_words]
       
            result_string = " ".join(important_words)
            
            df_get_title_db = select_get_title_db(result_string)
            #df_get_title_db.to_csv("output_olds.csv",index=False,encoding="utf-8-sig")
        
            
            # -------------------------
            # 12. Concat new record from API and paper record in DB
            # -------------------------
            
            # Skip jika df_get_title_db kosong atau semua isinya NA
            if not df_get_title_db.empty and not df_get_title_db.isna().all().all():
                df_api_type = df_api_type[~df_api_type["Title"].isin(df_get_title_db["Title"])]
                df_api_type = pd.concat([df_api_type, df_get_title_db], ignore_index=True)

            # Ubah semua NA menjadi None (aman dilakukan setelah concat)
            df_api_type = df_api_type.where(pd.notna(df_api_type), None)
            
            #df_api_type.to_csv("output_newwww.csv",index=False,encoding="utf-8-sig")

            
                    

            
            #st.success("✅ Kolom 'Title' telah dinormalisasi!")
    else:
        st.error("❌ The title you are looking for was not found!")
        st.stop()


    
    
    
    # Gabungkan user_keywords dengan Title untuk membuat input user
    
    #1. Semantic Scholar and DOAJ refine data
    #mask_title = df_api_type['Title'] == "Dynamic Mirroring: Unveiling The Role Of Digital Twins, Artificial Intelligence And Synthetic Data For Personalized Medicine In Laboratory Medicine"

    # Ganti Title menjadi "N/A" hanya untuk baris tersebut
    #df_api_type.loc[mask_title, 'Abstract'] = "N/A"
                    
    #mask_title = df_api_type['Title'] == "Utilizing An Artificial Intelligence Framework (Conditional Generative Adversarial Network) To Enhance Telemedicine Strategies For Cancer Pain Management"

    # Ganti Title menjadi "N/A" hanya untuk baris tersebut
    #df_api_type.loc[mask_title, 'Abstract'] = "N/A"
                    
    #mask_title = df_api_type['Title'] == "Artificial Intelligence-Enhanced Care Pathway Planning And Scheduling System: Content Validity Assessment Of Required Functionalities"

    # Ganti Title menjadi "N/A" hanya untuk baris tersebut
    #df_api_type.loc[mask_title, 'Abstract'] = "N/A"

    print("Starting data extraction and refinement...")

    # Proses ekstraksi setelah mengganti Abstract menjadi "N/A"
    if 'Open Access PDF URL' in df_api_type.columns:
        def clean_pubmed_url(url):
            if isinstance(url, str):
                return re.sub(r'/pdf$', '/', url)
            return url
        
        with ThreadPoolExecutor() as executor:
            
        
            # Tentukan mask untuk setiap API
            ss_mask = df_api_type['Source'] == 'Semantic Scholar'
            doaj_mask = df_api_type['Source'] == 'DOAJ'
            pubmed_mask = df_api_type['Source'] == 'PubMed'

            # Buat list mask untuk looping
            api_masks = [ss_mask, doaj_mask, pubmed_mask]
            

            # Looping untuk setiap mask API yang dipilih
            for mask in api_masks:
                #st.warning(mask[0])
                if mask.any():  # Cek apakah ada baris yang sesuai dengan mask
                    


                    #Refine Retrieve title from Crossref SS, DOAJ, PubMed
                    mask_na = df_api_type['Title'].isna() | (df_api_type['Title'] == "N/A") | (df_api_type['Title'].apply(lambda x: len(x) if x is not None else 0) <= 15) | (~df_api_type['Title'].apply(is_english))
                    urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    title_crossref = list(executor.map(get_journal_title_crossref, urls_to_extract))
                    df_api_type.loc[mask_na & mask, 'Title'] = title_crossref

                    
                    #Refine Retrieve abstract from Crossref SS, DOAJ, PubMed
                    mask_na = df_api_type['Abstract'].isna() | (df_api_type['Abstract'] == "N/A") 
                    urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    abstract_crossref = list(executor.map(get_journal_abstract_crossref, urls_to_extract))
                    df_api_type.loc[mask_na & mask, 'Abstract'] = abstract_crossref
                    
                        

                    #Refine Ekstraksi untuk PubMed hanya jika mask-nya PubMed
                    if mask is pubmed_mask:  # Gunakan 'is' untuk membandingkan objek
                        # Ekstraksi abstract untuk PubMed
                        extracted_abstracts = list(
                            executor.map(
                                lambda url: extract_abstract_pmc_pubmed(clean_pubmed_url(url)),
                                urls_to_extract
                            )
                        )
                        df_api_type.loc[mask_na & mask, 'Abstract'] = extracted_abstracts

                        # Ekstraksi keyword untuk PubMed
                        df_api_type.loc[mask, 'Extracted Keywords'] = list(
                            executor.map(
                                lambda url: extract_keywords_pmc_pubmed(clean_pubmed_url(url)),
                                df_api_type.loc[mask, 'Open Access PDF URL']
                            )
                        )

            
            
            
            
            
           
            df_api_type['Title BM25 Score'] = pd.NA
            df_api_type['Title BM25 Score'] = compute_bm25(query, df_api_type['Title'])
            
            #df_api_type['Title PAV'] = apply_pav_with_sigmoid(df_api_type['Title BM25 Score'])
            
            combined_query_abstract = ", ".join(filter(None, [
            str(selected_domain_final),
            str(selected_field_final),
            str(" ".join(user_keywords)),
            str(query)
            ]))
            df_api_type['Abstract BM25 Score'] = pd.NA
            df_api_type['Abstract BM25 Score'] = compute_bm25(combined_query_abstract,df_api_type['Abstract'] )
            #df_api_type['Abstract PAV'] = apply_pav_with_sigmoid(df_api_type['Abstract BM25'])
            
            
            df_api_type['Total BM25 Score'] = df_api_type[['Title BM25 Score', 'Abstract BM25 Score']].sum(axis=1)
            if len(df_api_type) > 100:
                # Sortir dataframe berdasarkan kolom 'Total BM25' secara descending
                df_api_type = df_api_type.sort_values(by='Total BM25 Score', ascending=False)
                
                # Ambil 100 baris pertama setelah disorting
                df_api_type = df_api_type.head(100)
                #df_api_type.to_csv("output_bm25.csv",index=False,encoding="utf-8-sig")
            
            
            
            #Refine Retrieve PDF Available from Crossref SS, DOAJ, PubMed
            mask_na = df_api_type['Open Access PDF URL'].isna() | (df_api_type['Open Access PDF URL'] == "N/A") | (df_api_type['Open Access PDF URL'] == False)
            source_mask = ss_mask | doaj_mask | pubmed_mask
            combined_mask = mask_na & source_mask
            urls_to_extract = df_api_type.loc[combined_mask, 'DOI']
            pdf_url_crossref = list(executor.map(get_journal_pdf_crossref, urls_to_extract))
            df_api_type.loc[combined_mask, 'Open Access PDF URL'] = pdf_url_crossref
            
            #Refine Retrieve PDF Available from Unpaywall SS, DOAJ, PubMed
            mask_na = df_api_type['Open Access PDF URL'].isna() | (df_api_type['Open Access PDF URL'] == "N/A") | (df_api_type['Open Access PDF URL'] == False)
            source_mask = ss_mask | doaj_mask | pubmed_mask
            combined_mask = mask_na & source_mask
            urls_to_extract = df_api_type.loc[combined_mask, 'DOI']
            pdf_url_unpaywall = list(executor.map(get_pdf_unpaywall, urls_to_extract))
            df_api_type.loc[combined_mask, 'Open Access PDF URL'] = pdf_url_unpaywall
        

            mask_na = (df_api_type['Open Access PDF URL'] != None) & (df_api_type['Open Access PDF URL'] != "N/A") & (df_api_type['Open Access PDF URL'] != False)
            df_api_type.loc[mask_na, 'PDF Available'] = 'Yes'
            
            
        
            
            for mask in api_masks:
                
                #st.warning(mask[0])
                if mask.any():  # Cek apakah ada baris yang sesuai dengan mask
                    
                    
                    
                    #Refine Ekstraksi Abstract SS, DOAJ, PubMed
                    # Filter Abstract yang kosong / "N/A"
                    mask_na = df_api_type['Abstract'].isna() | (df_api_type['Abstract'] == "N/A")
                    urls_to_extract = df_api_type.loc[mask_na & mask, 'Open Access PDF URL']

                    if not urls_to_extract.empty:
                        # Ekstraksi Abstract hanya untuk baris yang sesuai
                        extracted_abstracts = list(
                                executor.map(
                                    extract_abstract_from_url,
                                    urls_to_extract
                                )
                            )
                        # Simpan hasil ekstraksi kembali ke kolom Abstract
                        df_api_type.loc[mask_na & mask, 'Abstract'] = extracted_abstracts
            
                    #Refine Retrieve Document Type from Crossref SS, DOAJ, PubMed
                    #mask_na = df_api_type['Document Type'].isna() | (df_api_type['Document Type'] == "N/A") 
                    #urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    #doct_type_crossref = list(executor.map(get_journal_doc_type_crossref, urls_to_extract))
                    #df_api_type.loc[mask_na & mask, 'Document Type'] = doct_type_crossref
                            
                
                    #Refine Retrieve Journal Name from Crossref SS, DOAJ, PubMed
                    mask_na = df_api_type['Journal Name'].isna() | (df_api_type['Journal Name'] == "N/A") | (df_api_type['Journal Name'].apply(lambda x: len(x) if x is not None else 0) <= 3)
                    urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    journal_names_crossref = list(executor.map(get_journal_name_crossref, urls_to_extract))
                    df_api_type.loc[mask_na & mask, 'Journal Name'] = journal_names_crossref
                            
                    #Refine Retrieve Journal Volume from Crossref SS, DOAJ, PubMed
                    #mask_na = df_api_type['Journal Volume'].isna() | (df_api_type['Journal Volume'] == "N/A") 
                    #urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    #journal_vol_crossref = list(executor.map(get_journal_vol_crossref, urls_to_extract))
                    #df_api_type.loc[mask_na & mask, 'Journal Volume'] = journal_vol_crossref
                            
                            
                    #Refine Retrieve Journal Page from Crossref SS, DOAJ, PubMed
                    #mask_na = df_api_type['Journal Pages'].isna() | (df_api_type['Journal Pages'] == "N/A") 
                    #urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    #journal_page_crossref = list(executor.map(get_journal_page_crossref, urls_to_extract))
                    #df_api_type.loc[mask_na & mask, 'Journal Pages'] = journal_page_crossref
                            

                    #Refine Retrieve Citation Count from Crossref SS, DOAJ, PubMed
                    df_api_type['Citation Count'] = df_api_type['Citation Count'].replace('', pd.NA).fillna('N/A')
                    mask_na = df_api_type['Citation Count'].isna() | (df_api_type['Citation Count'] == "N/A")
                    urls_to_extract = df_api_type.loc[mask_na & mask, 'DOI']
                    citation_count_crossref = list(executor.map(get_journal_citation_crossref, urls_to_extract))
                    df_api_type.loc[mask_na & mask, 'Citation Count'] = citation_count_crossref
                    
                    df_api_type['Extracted Keywords'] = df_api_type['Extracted Keywords'].str.replace(r'[^\x00-\x7F]+', 'N/A', regex=True)
                    # Ekstraksi keywords ALL
                    mask_na = df_api_type['Extracted Keywords'].isna() | (df_api_type['Extracted Keywords'] == "N/A")
                    keywords_to_extract = df_api_type.loc[mask_na, 'Open Access PDF URL']
                    keywords_to_extract_func = list(executor.map(extract_keywords_from_url, keywords_to_extract))
                    df_api_type.loc[mask_na, 'Extracted Keywords'] = keywords_to_extract_func
         
            
            

        
       
            #Refine Retrieve ISSN from Crossref SS, DOAJ, PubMed
            #df_api_type['ISSN'] = pd.NA

        with ThreadPoolExecutor() as executor:
            df_api_type['ISSN'] = list(
                executor.map(get_journal_issn_crossref, df_api_type['DOI'])
            )

        # barrier otomatis di sini (keluar dari block)

        with ThreadPoolExecutor() as executor:
            df_api_type['Impact Factor'] = list(
                executor.map(get_journal_if, df_api_type['ISSN'])
            )

            #df_api_type.to_csv("output_if2.csv",index=False,encoding="utf-8-sig")

        
    # Inisialisasi kolom kosong dulu
    cols = ['Title BERT Score', 'Abstract BERT Score', 'Extracted Keywords BERT Score', 
            'Discipline(s) BERT Score', 'Citation Count Norm Score','Impact Factor Norm Score']
            #'Similarity Score', 'Vector Embedding Title','Vector Embedding Abstract', 'Vector Embedding Extracted Keywords','Vector Embedding Discipline(s)']


    df_api_type[cols] = None
    
    # Pastikan kolom embedding ada sebelum digunakan
    embed_cols = [
        'Vector Embedding Title',
        'Vector Embedding Abstract',
        'Vector Embedding Extracted Keywords',
        'Vector Embedding Discipline(s)'
    ]

    for c in embed_cols:
        if c not in df_api_type.columns:
            df_api_type[c] = None
    
    #First checking stage - Sentence Embedding
    df_api_type['Vector Embedding Title'] = df_api_type['Vector Embedding Title'].apply(parse_embedding)
    df_api_type['Vector Embedding Abstract'] = df_api_type['Vector Embedding Abstract'].apply(parse_embedding)
    df_api_type['Vector Embedding Extracted Keywords'] = df_api_type['Vector Embedding Extracted Keywords'].apply(parse_embedding)
    df_api_type['Vector Embedding Discipline(s)'] = df_api_type['Vector Embedding Discipline(s)'].apply(parse_embedding)
    #df_api_type.to_excel("output_first_checka.xlsx", index=False)
    

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(
            lambda row: compute_similarity(
                query,
                row["Title"],
                model,
                existing_emb=row["Vector Embedding Title"]  # gunakan embedding row
            ),
            (row for _, row in df_api_type.iterrows())
        ))


    # Pisahkan similarity dan embeddings
    title_results = [res[0] for res in results]  # float
    #st.success(title_results)
    extracted_embeddings = [res[1] for res in results]  # vector/tuple
    #st.warning(extracted_embeddings)
    
    # Simpan ke dataframe
    df_api_type['Similarity Score'] = title_results
    df_api_type['Vector Embedding Title'] = extracted_embeddings

    # Tentukan kategori berdasarkan title similarity dulu
    df_api_type['Relevance Category'] = [
    "Highly relevant 1" if float(val) >= 0.8 else None
    for val in title_results
    ]
    
    #df_api_type.to_excel("output_first_checkb.xlsx", index=False)
    
    #Hanya proses Abstract, Keywords, Discipline untuk yang relevan
    relevant_idx = df_api_type.index[df_api_type['Relevance Category'] == "Highly relevant 1"]
    
    
    with ThreadPoolExecutor() as executor: 
        results = list(executor.map(
            lambda row: {
                field: compute_similarity(query, row[field], model)
                for field in ['Abstract', 'Extracted Keywords', 'Discipline(s)']
                # hanya hitung jika kolom embedding kosong
                if row[f'Vector Embedding {field}'] is None
            },
            (row for _, row in df_api_type.loc[relevant_idx].iterrows())
        ))

    # Masukkan hasil kembali ke dataframe
    for i, idx in enumerate(relevant_idx):
        for field in ['Abstract', 'Extracted Keywords', 'Discipline(s)']:
            if field in results[i]:  # hanya update jika memang dihitung
                df_api_type.at[idx, f'Vector Embedding {field}'] = results[i][field][1]
            

    print("Starting second checking stage - Sentence Embedding")
    
    #Second checking stage - Sentence Embedding
    with ThreadPoolExecutor() as executor:
        df_api_type['Citation Count'] = df_api_type['Citation Count'].replace('N/A', 0)
 
        # Normalisasi Citation Count dan Impact Factor sebelum menghitung similarity
        min_citation, max_citation = normalize_values(df_api_type, 'Citation Count')
        
        min_impact, max_impact = normalize_values(df_api_type, 'Impact Factor')
        
        # Menjalankan fungsi secara paralel dengan executor.map
        results = list(executor.map(
            lambda row: calculate_bert(
                row, 
                query, 
                selected_domain_final, 
                selected_field_final, 
                user_keywords, 
                model,
                min_citation, 
                max_citation,
                min_impact, 
                max_impact
            )
           if df_api_type.at[row.name, 'Relevance Category'] is None else (-1,-1,-1,-1,-1,-1, df_api_type.at[row.name, 'Similarity Score'],df_api_type.at[row.name, 'Vector Embedding Title'],df_api_type.at[row.name, 'Vector Embedding Abstract'],df_api_type.at[row.name, 'Vector Embedding Extracted Keywords'],df_api_type.at[row.name, 'Vector Embedding Discipline(s)']), (row for _, row in df_api_type.iterrows())
        
        ))
        
    print("Finished second checking stage - Sentence Embedding")

    # Memasukkan hasil ke DataFrame
    df_api_type[['Title BERT Score', 'Abstract BERT Score', 'Extracted Keywords BERT Score', 'Discipline(s) BERT Score','Citation Count Norm Score','Impact Factor Norm Score','Similarity Score', 'Vector Embedding Title','Vector Embedding Abstract', 'Vector Embedding Extracted Keywords','Vector Embedding Discipline(s)']] = pd.DataFrame(results, index=df_api_type.index)

    #df_api_type.to_excel("output22222222.xlsx", index=False)
   

    # Check whether Similarity Score exceeds 1
    if df_api_type["Similarity Score"].max() > 1:
        
        S_min = df_api_type["Similarity Score"].min()
        S_max = df_api_type["Similarity Score"].max()

        # Normalize only if score range exceeds 1
        df_api_type["Similarity Score"] = (
            (df_api_type["Similarity Score"] - S_min) /
            (S_max - S_min)
        )

    # Assign relevance category
    with ThreadPoolExecutor() as executor:
        df_api_type["Relevance Category"] = list(
            executor.map(
                lambda val: (
                    "Highly relevant" if val >= 0.8 else
                    "Moderately relevant" if 0.6 <= val < 0.8 else
                    "Somewhat relevant" if 0.4 <= val < 0.6 else
                    "Low relevance"
                ),
                df_api_type["Similarity Score"]
            )
        )
    
    df_api_type['Relevance Category'] = df_api_type['Relevance Category'].replace({
    'Highly relevant 1': 'Highly relevant',
    'Highly relevant 2': 'Highly relevant'
    })

    
    #df_api_type.to_excel("output_first_checkc.xlsx", index=False)
    
    
    #df_api_type=lda_modeling(df_api_type)
    

    #Select human rating stats from DB
    df_api_type = select_human_rating_stats(df_api_type,query)
    #df_api_type.to_excel("output_first_check-humanrating.xlsx", index=False)
    print("Starting RAG as judge stage")
    #RAG as judge
    df_api_type=llm_as_judge(df_api_type, query, user_keywords, selected_domain_final, selected_field_final)
    
    #df_api_type.to_excel("output_first_check-llm.xlsx", index=False)
    

    # Filter: Hanya yang memiliki 'Open Access PDF URL' != 'N/A' atau 'Extracted Keywords' != 'N/A'
    df_api_type['Abstract Valid'] = df_api_type['Abstract'] != 'N/A'
    df_api_type['Open Access PDF URL Valid'] = df_api_type['Open Access PDF URL'] != 'N/A' 
    df_api_type['Extracted Keywords Valid'] = df_api_type['Extracted Keywords'] != 'N/A' 
    

    # Prioritaskan baris yang memiliki valid Open Access PDF URL atau Extracted Keywords
    df_api_type_sorted = df_api_type.sort_values(by=['Abstract Valid', 'Open Access PDF URL Valid','Extracted Keywords Valid'], ascending=False)

    # Hapus duplikat berdasarkan 'Title', memilih baris pertama yang valid
    df_api_type = df_api_type_sorted.drop_duplicates(subset='Title', keep='first')
    
    
    #df_api_type['User Rating'] = None  # None artinya belum di-rate

    rating_columns = ["👍 High Relevant", "👌 Moderate Relevant", "✋ Somewhat Relevant", "👎 Low Relevance"]

    # Initialize semua kolom dengan False (belum dicentang)
    for col in rating_columns:
        df_api_type[col] = False

    # Sort by similarity score (descending order)
    df_api_type = df_api_type.sort_values(by='Similarity Score', ascending=False)

    df_api_type.reset_index(inplace=True)                   # pindahkan index menjadi kolom
    df_api_type.rename(columns={"index": "Index"}, inplace=True)
    df_api_type["Index"] = range(1, len(df_api_type) + 1)   # set ulang jadi 1..N
    
    #df_api_type.to_csv("output_embeddings.csv", index=False)

    #df_api_type.to_excel("output1a.xlsx", index=False)
    #st.success(f"Vector Embedding Title: {type(df_api_type['Vector Embedding Title'])}")
    #st.success(f"Vector Embedding Abstract: {type(df_api_type['Vector Embedding Abstract'])}")
    #st.success(f"Vector Embedding Extracted Keywords: {type(df_api_type['Vector Embedding Extracted Keywords'])}")
    #st.success(f"Vector Embedding Discipline(s): {type(df_api_type['Vector Embedding Discipline(s)'])}")
    
    
    
    #insert tb_papers
    try:
        get_id_papers = insert_papers(df_api_type)
        #st.success(f"Query ID tb_papers: {get_id_papers}")
    except Exception as e:
        st.error(f"Database insert failed tb_papers: {e}")   
    
    #df_api_type.to_excel("output1b.xlsx", index=False)
    
    #insert tb_ai_ratings
    try:

        paper_id = get_id_papers  # ambil ID sesuai index
        #st.success(f"Query ID PAPER ID: {paper_id}")
        get_id_ai_rating = insert_ai_rating(df_api_type, get_id_query_history, paper_id)
            
        #st.success(f"Query ID insert_ai_rating: {get_id_ai_rating}")
    except Exception as e:
        st.error(f"Database insert failed tb_ai_rating: {e}")   
      
    #df_api_type.to_excel("output_2026.xlsx", index=False)


    relevance_map = { 
        "Highly relevant": 3, 
        "Moderately relevant": 2, 
        "Somewhat relevant": 1, 
        "Low relevance": 0 
    }

    df_api_type['_Relevance_Score_Temp'] = df_api_type['AI Relevance Category'].map(relevance_map)

    print("#1: Starting RAGAS evaluation for top-10 papers...")
    # 1. Ambil top-10 berdasarkan relevance category dan similarity
    df_top10 = df_api_type.sort_values(
        by=["_Relevance_Score_Temp", "Similarity Score"],
        ascending=[False, False]
    ).head(10).copy()

    print("#2: Starting RAGAS evaluation for top-10 papers...")
    # 2. Hitung RAGAS hanya untuk top-10
    scores = df_top10.apply(
        lambda row: pd.Series(
            rag_metrics_embeddings(
                row=row,
                query=query,
                user_keywords=user_keywords,
                selected_domain_final=selected_domain_final,
                selected_field_final=selected_field_final
            )
        ),
        axis=1
    )

    scores.columns = [
        "Explanation_Relevance",
        "Faithfulness"
    ]


    # 3. Gabungkan hasil RAGAS
    df_top10 = pd.concat(
        [df_top10.reset_index(drop=True), scores],
        axis=1
    )


    # 4. Simpan hasil sementara
    df_top10.to_csv("output_ragas_10.csv", index=False)
    

    # 5. Hapus kolom sementara setelah selesai
    df_api_type.drop(
        columns=["_Relevance_Score_Temp"],
        inplace=True
    )


    # Rata-rata top-10
    average_ragas_scores_get = {
        "Explanation Relevance": df_top10["Explanation_Relevance"].mean(),
        "Faithfulness": df_top10["Faithfulness"].mean()
    }
    
    
    # Calculate elapsed time

    elapsed_time = time.time() - start_time
    st.success(f"Data fetched in {elapsed_time:.2f} seconds!")
    
    
    

    # Log performance metrics
    #end_time = time.time()
    #execution_time = end_time - start_time
    final_memory = process.memory_info().rss / (1024 * 1024)  # Convert to MB
    memory_used = final_memory - initial_memory
    cpu_usage_percent = psutil.cpu_percent(interval=None)
    total_logical_processors = psutil.cpu_count(logical=True)
    total_cpu_usage = f"{(cpu_usage_percent / 100) * total_logical_processors:.2f}"

    performance_retrieval_get = {
            "Execution Time": elapsed_time,
            "Initial Memory Usage": initial_memory,
            "Final Memory Usage": final_memory,
            "Memory Used": memory_used,
            "Percentage of CPU Usage": cpu_usage_percent,
            "Total Logical Processor": total_logical_processors,
            "Total CPU Usage in Core": total_cpu_usage
        }


    collection_retrieval_get = {"successfully_collected": len(df_api_type),
            "total_available_pdf1": collection_retrieval.get('total_available_pdf1', 'N/A'),
            "total_available_pdf2": df_api_type['Open Access PDF URL'].str.startswith(('http', 'https')).sum()}
    




    #insert tb_syst_perform
    try:
        get_id_syst_perform = insert_syst_perform(average_ragas_scores_get, performance_retrieval_get,collection_retrieval_get, get_id_query_history)
        #st.success(f"Query ID insert_syst_perform: {get_id_syst_perform}")
    except Exception as e:
        st.error(f"Database insert failed: {e}")   
    
    db_ids_get = {"get_id_query_history": get_id_query_history, 
                 "get_id_papers": get_id_papers, 
                 "get_id_ai_rating": get_id_ai_rating, 
                 "get_id_syst_perform": get_id_syst_perform
        
    }
    
    #df_api_type.to_csv("paper_result_mistral.csv",index=False,encoding="utf-8-sig")
    #df_perf = pd.DataFrame([performance_retrieval_get])
    #df_perf.to_csv("perfomance_result_mistral.csv",index=False,encoding="utf-8-sig")
    
    return df_api_type, average_ragas_scores_get,  performance_retrieval_get, collection_retrieval_get, db_ids_get





# Add tabs for the different APIs
def main():
    
    if "df_api_type" not in st.session_state:
        st.session_state.df_api_type = pd.DataFrame()  # kosong di awal
    if "average_ragas_scores" not in st.session_state:
        st.session_state.average_ragas_scores = {}
    if "performance_retrieval" not in st.session_state:
        st.session_state.performance_retrieval = {}
    if "collection_retrieval" not in st.session_state:
        st.session_state.collection_retrieval = {}
    if "page_index" not in st.session_state:
        st.session_state.page_index = 0

        
        
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/e/ee/Okayama_University_Logo.svg" 
                alt="Okayama Logo" style="width: 230px; min-width: 230px;">
            <div>
                <h2 style="margin: 0; padding: 0;">Welcome to ARPACS Project</h2>
                <p style="margin: 4px 0 0 0; font-size: 14px; color: gray;">
                    A Reference Paper Collection System – Open Access Paper Retrieval via APIs
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True  # ← penting banget!
    )


    
    # Streamlit app title
    st.title("Open Access Paper Retrieval")
    
    # Tabs for selecting API
    # === Styled Label ===
    
    api_label_to_code = {
    "Semantic Scholar": "Semantic Scholar API",
    "DOAJ": "DOAJ API",
    "PubMed": "PubMed API",
    "arXiv": "arXiv API",
    "bioRxiv": "bioRxiv API",
    "medRxiv": "medRxiv API",
    "PsyArXiv": "PsyArXiv API",
    "SocArXiv": "SocArXiv API",
    "EdArXiv": "EdArXiv API",
    "Crossref": "Crossref API",
    "OpenAlex": "OpenAlex API",
    "Scopus": "Scopus API",
    "Web of Science": "Web of Science API",
    #"AI-Assisted Search": "AI-Assisted Search API",
    "All Sources": "Multiple API Integration"
    }
    
    col1_source_api, col2_source_api = st.columns([0.3, 0.7])

    with col1_source_api:
        st.markdown(
            """
            <span style='
                background-color:#e6f0ff;
                padding:6px 12px;
                border-radius:6px;
                font-weight:bold;
                color:#003366;
                display:inline-block;
            '>
                Select Source of Academic Papers (API):
            </span>
            """,
            unsafe_allow_html=True
        )

    with col2_source_api:

        # Initialize session state if it doesn't exist
        if 'selected_apis' not in st.session_state:
            st.session_state.selected_apis = {key: False for key in api_label_to_code.keys()}

        # Create columns for a 3x3 grid layout
        cols = st.columns(3)

        # Create a dictionary to store the checkbox selections
        checkbox_index = 0  # Track the checkbox index to manage columns

        # Handle the logic for "All Sources"
        selected_value_all_sources = st.checkbox("All Sources", value=st.session_state.selected_apis["All Sources"], key="All Sources")
        st.session_state.selected_apis["All Sources"] = selected_value_all_sources  # Update session state for "All Sources"

        # If "All Sources" is selected, hide other checkboxes and reset them
        if st.session_state.selected_apis["All Sources"]:
            # Reset all other checkboxes if "All Sources" is selected
            for key in api_label_to_code.keys():
                if key != "All Sources":
                    st.session_state.selected_apis[key] = False  # Reset all other checkboxes
            
            # Display only the "All Sources" checkbox
            st.checkbox("All Sources", value=True, disabled=True, key="All Sources_disabled")  # "All Sources" is disabled, since it is selected
        else:
            # Loop through the API labels and create checkboxes for the other sources
            for api_label in api_label_to_code.keys():
                if api_label != "All Sources":  # Skip "All Sources"
                    col_idx = checkbox_index % 3  # Find the appropriate column index
                    with cols[col_idx]:  # Assign each checkbox to a column
                        selected_value = st.checkbox(api_label, value=st.session_state.selected_apis[api_label], key=api_label)  # Unique key for each checkbox
                        st.session_state.selected_apis[api_label] = selected_value
                    checkbox_index += 1  # Increment to next checkbox

        # Get the selected API codes
        api_option = [api_label_to_code[api_label] for api_label, is_checked in st.session_state.selected_apis.items() if is_checked]

        st.success(f"Searching for {api_option}")


    # === Section Label for Domain & Field ===
    
    col1_domain_api, col2_domain_api = st.columns([0.3, 0.7])
    
    with col1_domain_api:
        st.markdown(
            """
            <span style='
                background-color:#e6f0ff;
                padding:6px 12px;
                border-radius:6px;
                font-weight:bold;
                color:#003366;
                display:inline-block;
            '>
                Select Domain and Field:
            </span>
            """,
            unsafe_allow_html=True
        )

    with col2_domain_api:
        # === Domain & Fields options ===
        domain_options = {
            "Physical Sciences": [
                "Computer Science", "Engineering", "Physics and Astronomy",
                "Chemistry", "Materials Science", "Mathematics",
                "Chemical Engineering", "Energy", "Earth and Planetary Sciences", "Decision Sciences"
            ],
            "Social Sciences": [
                "Social Sciences", "Business, Management and Accounting", "Economics, Econometrics and Finance",
                "Arts and Humanities", "Psychology", "Law"
            ],
            "Health Sciences": [
                "Medicine", "Health Professions", "Nursing",
                "Pharmacology, Toxicology and Pharmaceutics"
            ],
            "Life Sciences": [
                "Biochemistry, Genetics and Molecular Biology", "Agricultural and Biological Sciences",
                "Environmental Science", "Neuroscience", "Immunology and Microbiology", "Veterinary"
            ],
            "Multidisciplinary": ["Multidisciplinary"]
        }
        
        
        # === select domain (with manual option) ===
        domain_list = ["-- Select Domain --"] + list(domain_options.keys()) + ["Other (type manually)"]
        selected_domain = st.selectbox("Select a Domain:", domain_list)

      
        if selected_domain == "Other (type manually)":
            custom_domain = st.text_input("Enter your custom domain:")
            selected_domain_final = custom_domain
        else:
            selected_domain_final = selected_domain

        # === select field ONLY IF domain SELECTED ===
        if selected_domain in domain_options:
            field_list = domain_options[selected_domain] + ["Other (type manually)"]
            selected_field = st.selectbox("Select a Field:", field_list)
            if selected_field == "Other (type manually)":
                custom_field = st.text_input("Enter your custom field:")
                selected_field_final = custom_field
            else:
                selected_field_final = selected_field
                
        elif selected_domain == "Other (type manually)":
            # custom domain, so also ask for custom field
            custom_field = st.text_input("Enter your custom field:")
            selected_field_final = custom_field

        else:
            selected_field_final = None


    # Query input for the selected API
    st.markdown(
        """
        <span style='
            background-color:#e6f0ff;
            padding:6px 12px;
            border-radius:6px;
            font-weight:bold;
            color:#003366;
            display:inline-block;
        '>
            Enter The Title or Topic:
        </span>
        """,
        unsafe_allow_html=True
    )

    # === Input field without label ===
    query = st.text_input(
        label="",
        placeholder="Type something like 'AI-Powered Chatbots for Healthcare'",
        label_visibility="collapsed"
    ).replace(":", "")

    # Input field for multiple keywords with a tag-style UI
    
    st.markdown(
        """
        <span style='
            background-color:#e6f0ff;
            padding:6px 12px;
            border-radius:6px;
            font-weight:bold;
            color:#003366;
            display:inline-block;
        '>
            Enter Keywords:
        </span>
        """,
        unsafe_allow_html=True
    )
    #st.subheader
    keywords = st_tags(
        label="❗Enter up to 10 keywords",
        text="Press enter to add more", 
        value=[],
        suggestions=[],
        maxtags=10,
        key="1"
    )
    

    #st.success(keywords)
    # Tombol search hanya aktif jika query dan keywords tidak kosong
    search_button = st.button("Search")

    if search_button:
        if not api_option:
            st.warning("Please select at least one API source before searching.")
        elif not query:
            st.warning("Please enter a query before searching.")
        elif not keywords:
            st.warning("Please enter at least one keyword before searching.")
        elif selected_domain_final in [None, "-- Select Domain --", ""]:
            st.warning("Please select or enter a domain searching.")
        elif selected_field_final in [None, "-- Select Field --", ""]:
            st.warning("Please select or enter a field searching.")
        else:
            st.success(f"Searching for '{query}' with keywords: {keywords}")

            # Daftar semua fungsi API
            all_api_functions = [
                get_semantic_data,
                get_doaj_data,
                get_pubmed_data,
                get_arxiv_data,
                get_biorxiv_data,
                get_medrxiv_data,
                get_psyarxiv_data,
                get_socarxiv_data,
                get_edarxiv_data,
                get_crossref_data,
                get_openalex_data,
                get_scopus_data,
                get_wos_data
                #get_ai_data
            ] 
            api_get_functions = {
                "Semantic Scholar API": get_semantic_data,
                "DOAJ API": get_doaj_data,
                "PubMed API": get_pubmed_data,
                "arXiv API": get_arxiv_data,
                "bioRxiv API": get_biorxiv_data,
                "medRxiv API": get_medrxiv_data,
                "PsyArXiv API": get_psyarxiv_data,
                "SocArXiv API": get_socarxiv_data,
                "EdArXiv API": get_edarxiv_data,
                "Crossref API": get_crossref_data,
                "OpenAlex API": get_openalex_data,
                "Scopus API": get_scopus_data,
                "Web of Science API": get_wos_data,
                #"AI-Assisted Search API": get_ai_data,
                "Multiple API Integration": all_api_functions
            }
            
            all_results_get = []

            for api_name in api_option:
                if api_name in api_get_functions:
                    func = api_get_functions[api_name]

                    if  len(api_option)>1:
                        # Tambahkan semua fungsi di dalam list, tanpa memanggilnya
                        all_results_get.append(func)
                        
                    elif api_option==["Multiple API Integration"]:
                        all_results_get.extend(func)
                        
                    else:
                        # Tambahkan fungsi tunggal, tanpa memanggilnya
                        all_results_get=func
                        
                        
                        #st.success(all_results_get)
    
        

            df_api_type, average_ragas_scores, performance_retrieval, collection_retrieval, db_ids = run_retrieval_pipeline(query, all_results_get, api_option, keywords, selected_domain_final, selected_field_final)
            st.session_state.df_api_type = df_api_type
            st.session_state.average_ragas_scores = average_ragas_scores
            st.session_state.performance_retrieval = performance_retrieval
            st.session_state.collection_retrieval = collection_retrieval
            st.session_state.page_index = 0  # reset pagination saat search baru
            st.session_state.db_ids = db_ids
                        

        
        #df_selected_column1 = df_api_type[['Title', 'Abstract', 'Year', 'Authors', 'Journal Name', 'Citation Count', 'Impact Factor', 'Open Access PDF URL','URL','Similarity Score','Relevance Category']]



            
    if not st.session_state.df_api_type.empty:
        average_ragas_scores = st.session_state.average_ragas_scores.copy()
        df_api_type = st.session_state.df_api_type.copy()
        performance_retrieval =  st.session_state.performance_retrieval.copy()
        collection_retrieval = st.session_state.collection_retrieval.copy()
        db_ids = st.session_state.db_ids.copy()
        
        rating_options = ["👍 High Relevant", "👌 Moderate Relevant", "✋ Somewhat Relevant", "👎 Low Relevance"]
        column_selected=['Index','Title', 'Abstract', 'Year', 'Authors', 'Journal Name', 'Citation Count', 'Impact Factor', 'Open Access PDF URL','URL','AI Relevance Category','AI Explanation', 'Human and AI Ratings', 'Human and AI Ratings Explanation', "👍 High Relevant", "👌 Moderate Relevant", "✋ Somewhat Relevant", "👎 Low Relevance"]
        column_config_ = {
                "Index": st.column_config.NumberColumn("Index", width="40", disabled=True),
                "URL": st.column_config.LinkColumn("URL", width="medium", disabled=True),
                "Open Access PDF URL": st.column_config.LinkColumn("Open Access PDF URL", width="medium", disabled=True),
                "Title": st.column_config.TextColumn("Title", width="medium", disabled=True),
                "Abstract": st.column_config.TextColumn("Abstract", width="medium", disabled=True),
                "Year": st.column_config.NumberColumn("Year", width="40", disabled=True),
                "Authors": st.column_config.TextColumn("Authors", width="small", disabled=True),
                "Journal Name": st.column_config.TextColumn("Journal Name", width="small", disabled=True),
                "Citation Count": st.column_config.NumberColumn("Citation Count", width="small", disabled=True),
                "Impact Factor": st.column_config.NumberColumn("Impact Factor", width="small", disabled=True),
                "AI Relevance Category": st.column_config.TextColumn("AI Relevance Category", width="small", disabled=True),
                "AI Explanation": st.column_config.TextColumn("AI Explanation", width="small", disabled=True),
                "Human and AI Ratings": st.column_config.TextColumn("Human and AI Ratings", width="small", disabled=True),
                "Human and AI Ratings Explanation": st.column_config.TextColumn("Human and AI Ratings Explanation", width="small", disabled=True),
                "👍 High Relevant": st.column_config.CheckboxColumn("👍 High Relevant", width="small"),
                "👌 Moderate Relevant": st.column_config.CheckboxColumn("👌 Moderate Relevant", width="small"),
                "✋ Somewhat Relevant": st.column_config.CheckboxColumn("✋ Somewhat Relevant", width="small"),
                "👎 Low Relevance": st.column_config.CheckboxColumn("👎 Low Relevance", width="small")
                
                #"User Rating": st.column_config.CheckboxColumn(
                 #   "User Rating",
                  #  options=rating_options,
                   # width="medium"
                #)
            }

        col_showall, col_sort = st.columns([8, 1])
        
        
        # ---- Checkbox Show All Rows ----
        with col_showall:
            show_all = st.checkbox("Show All Rows", value=False)
            # CSS to make mini selectbox
            st.markdown("""
                <style>
                div[data-baseweb="select"] {
                    min-width: 200px !important;
                    max-width: 200px !important;
                }
                </style>
                """, unsafe_allow_html=True)

            # ---- Mapping relevance category ke angka untuk sorting internal ----
            relevance_map = {
                "Highly relevant": 3,
                "Moderately relevant": 2,
                "Somewhat relevant": 1,
                "Low relevance": 0
            }
            df_api_type['_Relevance_Score'] = df_api_type['Human and AI Ratings'].map(relevance_map)
            
            

        # ---- SORT COLUMN (only when show_all is True) ----
        
        with col_sort:
            if show_all:
                sort_column = st.selectbox(
                    "Sort By:",
                    options=["Impact Factor", "Citation Count","Human and AI Ratings"],
                    index=0,
                    
                ) 

                if sort_column == "Human and AI Ratings":
                    df_api_type = df_api_type.sort_values(by=["_Relevance_Score","Similarity Score"],ascending=[False, False]).reset_index(drop=True)

                else:
                    df_api_type = df_api_type.sort_values(by=[sort_column, "Similarity Score"],ascending=[False, False]).reset_index(drop=True)

        # ---- Data to display (drop score) ----
        #df_display = df_api_type.drop(columns=["_Relevance_Score"])
        
        

        # ---- Display depending show_all ----
        if show_all:
              
            show_data_editor(df_api_type[column_selected], column_config_, rating_options, db_ids)
                                        
        else:


            # Urutkan berdasarkan Relevance Score (tertinggi di atas)
            df_api_type= df_api_type.sort_values(
            by=["_Relevance_Score","Similarity Score"],
            ascending=[False, False]
            ).reset_index(drop=False)


            page_size = 10
            total_pages = math.ceil(len(df_api_type) / page_size)

            if "page_index" not in st.session_state:
                st.session_state.page_index = 0

            start_row = st.session_state.page_index * page_size
            end_row = start_row + page_size

            #st.dataframe(df_api_type[column_selected].iloc[start_row:end_row],
                #column_config = column_config_ )
            

            show_data_editor(df_api_type[column_selected].iloc[start_row:end_row], column_config_, rating_options, db_ids)
                

            # Pagination controls
            def go_prev():
                if st.session_state.page_index > 0:
                    st.session_state.page_index -= 1

            def go_next():
                if st.session_state.page_index < total_pages - 1:
                    st.session_state.page_index += 1

            col_prev, col_label, col_next = st.columns([1, 6, 1])
            with col_prev:
                st.button("⬅ Prev", on_click=go_prev)
            with col_label:
                st.write(f"Page {st.session_state.page_index + 1} of {total_pages}")
            with col_next:
                st.button("Next ➡", on_click=go_next)



        # Display performance metrics
        st.subheader("Performance Metrics")
                

        # Donut charts
        colors = {'Yes': 'blue', 'No': 'orange'}
        col1, col2 = st.columns(2)
        with col1:
            fig_open_access = plot_donut_chart(df_api_type, 'Is Open Access', 'Open Access Availability', colors)
            st.plotly_chart(fig_open_access, use_container_width=True)
        with col2:
            fig_pdf_available = plot_donut_chart(df_api_type, 'PDF Available', 'PDF Accessibility', colors)
            st.plotly_chart(fig_pdf_available, use_container_width=True)

                    
        st.write(f"**Successfully Collected:** {collection_retrieval.get('successfully_collected','N/A')} paper(s)")
        st.write("")
        
        
        
        #with ThreadPoolExecutor() as executor:
         #   results_rag_metric = list(
          #  executor.map(lambda row: rag_metrics_embeddings(row, query, keywords, model), [row for _, row in df_api_type.iterrows()])
    
        #)
        
        
        #eval_df_rag_metric = pd.DataFrame(results_rag_metric)
        #top10 = eval_df_rag_metric.head(10)
        #top10.to_csv("output_rag_metrics.csv",index=False,encoding="utf-8-sig")
        #answer_relevancy, faithfulness = top10.mean()
        #answer_relevancy, faithfulness = eval_df_rag_metric.mean()
        #rag_metrics_get =  {'Answer Relevancy': answer_relevancy, 'Faithfulness': faithfulness}
                
        if average_ragas_scores:
            st.write(f"**Generation Metrics**")
            st.write(f"**Faithfulness:** {average_ragas_scores.get('Faithfulness',0) * 100:.2f}%")
            st.write(f"**Explanation Relevance:** {average_ragas_scores.get('Explanation Relevance',0) * 100:.2f}%")
            
            st.write("")       
         
        
        if performance_retrieval:
            st.write(f"**Resource Performance Metrics**")
            
            st.write(f"**Execution Time:** {performance_retrieval.get('Execution Time', 0):.2f} seconds")
            st.write(f"**Initial Memory Usage:** {performance_retrieval.get('Initial Memory Usage', 0):.2f} MB")
            st.write(f"**Final Memory Usage:** {performance_retrieval.get('Final Memory Usage', 0):.2f} MB")
            st.write(f"**Memory Used:** {performance_retrieval.get('Memory Used', 0):.2f} MB")
            st.write(f"**CPU Usage:** {performance_retrieval.get('Percentage of CPU Usage'):.2f}% of "
            f"{performance_retrieval.get('Total Logical Processor')} logical processors available "
            f"({performance_retrieval.get('Total CPU Usage in Core')} cores)")

		
            # Urutkan berdasarkan Relevance Score (tertinggi di atas)
            df_api_type= df_api_type.sort_values(
            by=["_Relevance_Score","Similarity Score"],
            ascending=[False, False]
            ).reset_index(drop=False)

            #df_api_type = df_api_type.sort_values(
            #by="_Relevance_Score",
            #ascending=False
            #).reset_index(drop=True)

            cols_to_drop = [
            "👍 High Relevant",
            "👌 Moderate Relevant",
            "✋ Somewhat Relevant",
            "👎 Low Relevance"]


            csv_data = (
            df_api_type.to_csv(
            index=False,
            encoding="utf-8",
            quotechar='"',
            quoting=csv.QUOTE_ALL
             )
            .encode("utf-8")
            )
            
            #torch.cuda.empty_cache()
	    
		
            st.download_button(
                label="Download data as CSV",
                data=csv_data,
                file_name=f"{query.replace("\t", "_").replace("\n", "_").replace("\r", "_")}_results_{api_option}.csv",
                mime='text/csv',
                key="download_csv"
                )
        else:
            st.warning("No data returned for the query. Try a different search term.")

            
            
            
           
    # Footer with caption
    st.markdown(
        """
        <div  text-align: left; font-size: 12px; color: gray;">
            <p>Developed by テルスナ・マウラナ・ファルディン </p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    try:
	
        # ====== MAIN APP ======
        if "logged_in" not in st.session_state:
            st.session_state["logged_in"] = False
        if not st.session_state["logged_in"]:
            login()
        else:
            st.sidebar.success(f"Logged in as {st.session_state['username']}")
            if st.sidebar.button("Logout"):
                logout()

	
            main()
    except Exception as e:
        print("STREAMLIT ERROR:", e)

    
        

    # Convert to DataFrames
    #df_semantic = pd.DataFrame(results_list_semanticsc)
    #df_doaj = pd.DataFrame(doaj_data)
    #df_pubmed = pd.DataFrame(pubmed_data)

    # Merge DataFrames
    #combined_df = pd.concat([df_semantic, df_doaj, df_pubmed], ignore_index=True)

    
    #print(df_semantic) 
    # Save to CSV (optional)
    #df_semantic.to_excel("combined_output.xlsx", index=False)
    #print(f"\nExecution Time: {performance_retrieval_semanticsc.get('Execution Time',0):.2f} seconds")
    #print(f"Initial Memory Usage: {performance_retrieval_semanticsc.get('Initial Memory Usage',0):.2f} MB")
    #print(f"Final Memory Usage: {performance_retrieval_semanticsc.get('Final Memory Usage',0):.2f} MB")
    #print(f"Memory Used: {performance_retrieval_semanticsc.get('Memory Used',0):.2f} MB")
    #print(f"CPU Usage: {performance_retrieval_semanticsc.get('Percentage of CPU Usage',0):.2f}% of {performance_retrieval_semanticsc.get('Total Logical Processor',0):.2f} logical processors available ({performance_retrieval_semanticsc.get('Total CPU Usage in Core',0)} cores)")

