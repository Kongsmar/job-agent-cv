import streamlit as st
from openai import OpenAI
import io
import requests
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import json

# --- KONFIGURATION ---
st.set_page_config(page_title="CV-Builder Pro: ATS Optimizer", page_icon="📄", layout="wide")

# --- HJÆLPEFUNKTIONER ---
def get_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.extract()
        output = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
            text = tag.get_text().strip()
            if text:
                if tag.name in ['h1', 'h2', 'h3']: output.append(f"\n\n### {text.upper()}\n")
                elif tag.name == 'li': output.append(f"* {text}")
                else: output.append(f"{text}\n")
        return "\n".join(output)
    except: return "Kunne ikke hente teksten."

def extract_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([p.extract_text() for p in reader.pages])
    except: return ""

def fill_cv_docx(template, data_dict):
    try:
        template.seek(0)
        doc = Document(template)
        for p in doc.paragraphs:
            for key, value in data_dict.items():
                if key in p.text: p.text = p.text.replace(key, str(value))
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for key, value in data_dict.items():
                            if key in p.text: p.text = p.text.replace(key, str(value))
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
    except: return None

# --- APP FLOW ---
st.title("📄 CV-Builder Pro")
st.markdown("Optimér dit CV mod jobopslagets nøgleord og gå gennem ATS-screening.")

if 'cv_step' not in st.session_state: st.session_state.cv_step = 1

if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2)
    with col1:
        st.header("1. Dit CV-grundlag")
        master_cv = st.file_uploader("Upload dit Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Upload din Word-skabelon (CV)", type="docx")
        navn = st.text_input("Dit fulde navn:")
    
    with col2:
        st.header("2. Jobmålet")
        job_url = st.text_input("Link til jobopslag:")
        if st.button("Hent jobtekst 🌐") and job_url:
            st.session_state.temp_job_text = get_text_from_url(job_url)
        job_text = st.text_area("Jobtekst:", value=st.session_state.get('temp_job_text', ""), height=450)

    if st.button("Generér optimeret CV ✨", disabled=not (master_cv and job_text)):
        st.session_state.master_cv_text = extract_pdf(master_cv)
        st.session_state.job_content = job_text
        st.session_state.cv_template = cv_template
        st.session_state.user_name = navn
        st.session_state.cv_step = 2
        st.rerun()

elif st.session_state.cv_step == 2:
    with st.spinner("AI omskriver dit CV..."):
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        prompt = f"""Du er ekspert i ATS-optimering. Omskriv CV'et så det matcher jobopslaget perfekt.
        Brug nøgleord fra jobopslaget. Gør erfaringen RESULTATORIENTERET.
        Svar KUN i JSON format:
        - 'profil': En skarp indledning (5-6 linjer).
        - 'erfaring': Al relevant erhvervserfaring omskrevet til bullets.
        - 'kompetencer': Liste over de 10 vigtigste skills.
        DATA: JOB: {st.session_state.job_content}, CV: {st.session_state.master_cv_text}"""
        
        resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        res = json.loads(resp.choices[0].message.content)

        col_res1, col_res2 = st.columns([2, 1])
        with col_res1:
            st.subheader("Målrettet Erfaring")
            st.write(res['erfaring'])
        with col_res2:
            st.subheader("Nøglekompetencer")
            st.info(res['kompetencer'])

        if st.session_state.cv_template:
            replacements = {"{{NAVN}}": st.session_state.user_name, "{{CV_PROFIL}}": res['profil'], "{{CV_ERFARING}}": res['erfaring'], "{{CV_KOMPETENCER}}": res['kompetencer']}
            final_cv = fill_cv_docx(st.session_state.cv_template, replacements)
            st.download_button("Hent optimeret CV (.docx) 📄", final_cv, f"CV_{st.session_state.user_name}.docx")

    if st.button("Start forfra 🔄"):
        st.session_state.cv_step = 1
        st.rerun()