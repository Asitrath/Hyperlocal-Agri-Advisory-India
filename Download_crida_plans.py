#!/usr/bin/env python3
"""
ICAR-CRIDA District Agriculture Contingency Plan Downloader
============================================================
Downloads district-level contingency plan PDFs for your agriculture RAG system.

Pre-configured for 5 diverse agro-climatic states:
  - Bihar (38 districts)      — Eastern wet, flood-prone
  - Odisha (30 districts)     — Coastal + tribal hinterland
  - Maharashtra (34 districts) — Semi-arid Deccan + Konkan coast
  - Rajasthan (11 districts)  — Arid/semi-arid western India
  - Andhra Pradesh (12 districts) — Southern coastal + dryland

Usage:
    python download_crida_plans.py                         # Download all 5 states
    python download_crida_plans.py --states Bihar,Odisha   # Specific states only
    python download_crida_plans.py --dry-run               # Preview without downloading

After downloading, feed these PDFs into your LangChain RAG pipeline:
    from langchain_community.document_loaders import PyPDFDirectoryLoader
    loader = PyPDFDirectoryLoader("./crida_plans/Bihar")
"""

import os
import re
import sys
import json
import time
import argparse
import urllib.parse
import urllib.request

# ── Pre-extracted PDF URLs (from icar-crida.res.in/Crop_Contingency_Plan.html) ──
STATES_DATA = {
    "Andhra_Pradesh": [
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP14-Anantapur%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP2-Chittoor%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP3-East%20Godavari%2031.1.11.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP1-Guntur%2031.1.11.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP5-Kadapa%2031%20jan.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP6-Krishna%2031.1.11.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP7-%20Kurnool%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP11-Nellore%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP17%20Prakasam%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP13-Srikakulam%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP19-Visakhapatnam%2031.1.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Andhra%20pradesh%20(Pdf)/ANGRAU,%20Hyderabad/AP12-%20West%20Godawari%2031.1.2011.pdf",
    ],
    "Bihar": [
        "https://www.icar-crida.res.in/cp/Bihar/BI1-%20Aurangabad-10.08.12-.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR31_Araria_28.12.13.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR10_Arwal_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR11_Banka_28.12.203.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR12_Begusarai%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR13_Bhagalpur_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR14_Bhojpur_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR15_Buxar_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BI2-Dharbhanga-10.08.12-.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR16_East%20Champaran_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR17_Gaya%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR8_Gopalganj_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR7_Jamui_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR18_Jehanabad%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR6_Katihar_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR20_Khagaria_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR21_Kishanganj%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR19_Kaimur%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR22_Lakhisaria_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR23_Madhepura_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR24_Madhubani_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR25_Munger_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR26_Muzaffarpur_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR29_Nalanda%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR5_Nawada_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR27_Patna_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR28_Purnea_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR4_Saharsa_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR3_Samastipur_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR9_Saran_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR37_Sitamarhi%20_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR34_Siwan_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR32_Sheohar_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR33_Sheikhpura_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR35_Supaul_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR30_Rohtas_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR36_Vaishali_28.12.2013.pdf",
        "https://www.icar-crida.res.in/CP/Bihar/BR38_West%20Champaran_28.12.2013.pdf",
    ],
    "Maharashtra": [
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/BSKKV,%20Dapoli/MH22-Thane%20%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/BSKKV,%20Dapoli/MH23-Raigarh%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/BSKKV,%20Dapoli/MH24-Ratnagiri%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/BSKKV,%20Dapoli/MH25-Sindhudurg%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2026-Aurangabad-3%201-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2027-Beed-3%201-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2028%20-Latur-%2031-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2029-Nanded-%2031-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2030-Osmanabad-%2031-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2031-Parbhani-%2031-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2032-Hingoli-%2031-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MAU,%20Parbhani/Maharashtra%2033-Jalna-31-12-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH1-Solapur%203.2.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH2-AHMEDNAGAR%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH3-DHULE%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH4-JALGAON%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH5-%20KOLHAPUR%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH6-NANDURBAR%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH7-NASIK%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH8-%20PUNE%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH9-SANGLI%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MPKVV,%20Rahuri/MH10-SATARA%2031.03.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Akola.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Amravati.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Bhandara.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Buldhana.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Chandrapur.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Gadchiroli.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Gondia.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Nagpur.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Wardha.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Washim.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/PDKV,%20Akola/Yavatmal.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Maharastra(Pdf)/MH34-Palghar-07.05.2016.pdf",
    ],
    "Odisha": [
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%201-Angul%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2027-%20Balasore%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2010-%20Bargarh%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2011-%20Bhadrak%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2012-%20Bolangir%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2015-%20Boudh%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%202-Cuttack%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%203-%20Deogarh%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2017-%20Dhenkanal%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2013-%20Gajapati%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2014-%20Ganjam%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2018-%20Jagatsinghpur%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2019-%20Jajpur%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2020-%20Jharsuguda%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%204-%20Kalahandi%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2021-%20Kandhamal%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2028-%20Kendrapara%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2025-%20Keonjhar%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2029-%20Khurdha%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2022-%20Koraput%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2016-%20Malkangiri%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2024-%20Mayurbhanj%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2030-%20Nabaranaga%2004.10.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%205-%20Nayagarh%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2023-%20Nuapada%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%206-%20Puri%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%2026-%20Rayagada%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%207-%20Sambalpur%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%208-%20Sonapur%2031.05.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Orissa%20(Pdf)/OUAT,%20Bhubaneswar/Orissa%209-%20Sundargarh%2031.05.2011.pdf",
    ],
    "Rajasthan": [
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAU,%20Bikaner/RAJ2-Tonk%203.2.2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAU,%20Bikaner/RAJ9-Sriganganagar-30-06-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAJ33-Sirohi-30.10.12.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAU,%20Bikaner/RAJ7-Sikar-30-06-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/MPUA&T,%20Udaipur/RAJ28-SAWAI%20MADHOPUR-26.7.2012.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/MPUA&T,%20Udaipur/RAJ21-Rajsamand-9.3.2012.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAJ32-Pratapgarh-30.10.12.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAJ31-Pali-28.08.12.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/RAU,%20Bikaner/RAJ8-Nagaur-30-06-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/MPUA&T,%20Udaipur/RAJ4-Kota-30-06-2011.pdf",
        "https://www.icar-crida.res.in/CP-2012/statewiseplans/Rajastan%20(Pdf)/MPUA&T,%20Udaipur/RAJ22-Udaipur-9.3.2012.pdf",
    ],
}

# ── Additional resources to download alongside the contingency plans ──
EXTRA_RESOURCES = {
    "handbooks": [
        ("Farmers_Handbook_Basic_Agriculture.pdf", "https://www.manage.gov.in/publications/farmerbook.pdf"),
        ("Farmer_Friendly_Handbook_2018-19.pdf", "https://agricoop.gov.in/sites/default/files/FFH201819_BiLing.pdf"),
        ("IPM_Vegetables_ICAR.pdf", "https://agricoop.nic.in/sites/default/files/ICAR_7.pdf"),
        ("ICAR_Biopesticides.pdf", "https://icar.org.in/sites/default/files/2022-06/ICAR-Technologies-Biopesticides.pdf"),
    ]
}


def sanitize(name):
    """Make string filesystem-safe."""
    name = urllib.parse.unquote(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_')


def district_name(url):
    """Extract district name from PDF URL."""
    fname = urllib.parse.unquote(url.split("/")[-1]).replace(".pdf", "")
    fname = re.sub(r'^[A-Z]{2,}\d*[-_]\s*', '', fname)
    fname = re.sub(r'[-_\s]*\d{1,2}[._]\d{1,2}[._]\d{2,4}[-_]?$', '', fname)
    fname = re.sub(r'[-_]+', ' ', fname).strip()
    return fname or urllib.parse.unquote(url.split("/")[-1])


def download(url, path, label=""):
    """Download a file with retries."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (AgriRAG research project)"
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) < 500:
                print(f"    ⚠ Suspiciously small ({len(data)}B), skipping")
                return False
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            print(f"    ✓ {label} ({len(data)//1024}KB)")
            return True
        except Exception as e:
            if attempt < 2:
                print(f"    ⚠ Retry {attempt+1}: {e}")
                time.sleep(2 * (attempt + 1))
            else:
                print(f"    ✗ Failed: {e}")
                return False
    return False


def main():
    ap = argparse.ArgumentParser(
        description="Download ICAR-CRIDA District Agriculture Contingency Plans for RAG"
    )
    ap.add_argument("--states", help='Comma-separated states, e.g. "Bihar,Odisha"')
    ap.add_argument("--dry-run", action="store_true", help="Preview only")
    ap.add_argument("--output", default="./crida_plans", help="Output directory")
    ap.add_argument("--extras", action="store_true", help="Also download handbook PDFs")
    ap.add_argument("--delay", type=float, default=1.5, help="Seconds between downloads")
    args = ap.parse_args()

    # Select states
    states = STATES_DATA
    if args.states:
        requested = [s.strip() for s in args.states.split(",")]
        states = {}
        for r in requested:
            matches = [k for k in STATES_DATA if k.lower().replace("_", " ").startswith(r.lower())]
            if matches:
                for m in matches:
                    states[m] = STATES_DATA[m]
            else:
                print(f"⚠ '{r}' not found. Available: {', '.join(STATES_DATA.keys())}")

    total = sum(len(v) for v in states.values())
    print(f"\n CRIDA Contingency Plan Downloader")
    print(f"   {total} PDFs across {len(states)} states\n")

    for state, urls in states.items():
        print(f"   {state.replace('_', ' ')}: {len(urls)} districts")

    if args.dry_run:
        print(f"\n[DRY RUN] Would download {total} files to {args.output}/")
        for state, urls in states.items():
            for url in urls:
                print(f"  {state}/{district_name(url)}.pdf")
        return

    print(f"\n⏬ Downloading to {os.path.abspath(args.output)}/\n")
    ok, fail = 0, 0

    for state, urls in states.items():
        state_dir = os.path.join(args.output, state)
        print(f"\n {state.replace('_', ' ')} ({len(urls)} files)")

        for i, url in enumerate(urls, 1):
            name = district_name(url)
            fpath = os.path.join(state_dir, sanitize(name) + ".pdf")

            if os.path.exists(fpath):
                print(f"  [{i}/{len(urls)}] ⏭ {name} (exists)")
                ok += 1
                continue

            print(f"  [{i}/{len(urls)}] {name}...")
            if download(url, fpath, name):
                ok += 1
            else:
                fail += 1
            time.sleep(args.delay)

    # Optional extra resources
    if args.extras:
        print(f"\n Downloading extra handbooks...")
        extras_dir = os.path.join(args.output, "_handbooks")
        for fname, url in EXTRA_RESOURCES["handbooks"]:
            fpath = os.path.join(extras_dir, fname)
            if os.path.exists(fpath):
                print(f"  ⏭ {fname} (exists)")
                continue
            print(f"  {fname}...")
            download(url, fpath, fname)
            time.sleep(args.delay)

    print(f"\n{'='*50}")
    print(f" Done! {ok} downloaded, {fail} failed")
    print(f" Output: {os.path.abspath(args.output)}/")


if __name__ == "__main__":
    main()