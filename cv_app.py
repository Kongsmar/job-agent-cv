import streamlit as st
from openai import OpenAI
import io
import requests
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import json

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="CV-Builder Pro: Brødtekst Edition", page_icon="✍️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1a1c24; color: #e0e0e0; }
    h1 { text-align: center; color: #ffffff; border-bottom: 2px solid #4a90e2; padding-bottom: 10px; }
    .cv-block { background-color: #2d303d; padding: 25px; border-radius: 12px; border-left: 5px solid #4a90e2; margin-bottom: 20px; }
    .cv-section-title { font-size: 1.3em; font-weight: bold; color: #4a90e2; margin-bottom: 10px; text-transform: uppercase; }
    .cv-text { font-family: 'Georgia', serif; line-height: 1.7; white-space: pre-wrap; color: #f0f0f0; }
    .analyse-card { background-color: #262936; padding: 20px; border-radius: 10px; border: 1px solid #4a90e2; margin-bottom: 25px; }
</style>
""", unsafe_allow_html=True)

# --- FUNKTIONER ---
def get_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer", "header"]): element.extract()
        return "\n".join([tag.get_text().strip() for tag in soup.find_all(['h1', 'h2', 'p', 'li']) if tag.get_text()])
    except: return "Kunne ikke hente tekst."

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
st.markdown("<h1>✍️ CV-Builder: Professionel Brødtekst</h1>", unsafe_allow_html=True)

if 'cv_step' not in st.session_state: st.session_state.cv_step = 1

if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("📁 Upload dokumenter")
        master_cv = st.file_uploader("Dit Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Din Word-skabelon (DOCX)", type="docx")
        navn = st.text_input("Fulde navn:")
    with col2:
        st.subheader("🎯 Jobmål")
        job_url = st.text_input("Link til opslag:")
        if st.button("Hent tekst 🌐") and job_url:
            st.session_state.temp_job_text = get_text_from_url(job_url)
        job_text = st.text_area("Jobbeskrivelse:", value=st.session_state.get('temp_job_text', ""), height=250)

    if st.button("Analyser & Skriv CV ✨", type="primary"):
        st.session_state.master_cv_text = extract_pdf(master_cv)
        st.session_state.job_content = job_text
        st.session_state.cv_template = cv_template
        st.session_state.user_name = navn
        st.session_state.cv_step = 2
        st.rerun()

elif st.session_state.cv_step == 2:
    with st.spinner("AI skriver dit CV i flydende brødtekst..."):
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"""
            Du er en professionel CV-forfatter. Omskriv Master-CV'et til et målrettet CV i BRØDTEKST.
            
            KRAV TIL FORMULERING:
            1. Erhvervserfaring: Skriv hvert job som et sammenhængende afsnit (ikke bullets). Beskriv ansvar og integrér resultater (tal/succeser) flydende i teksten. 
            2. Uddannelse: Beskriv hver uddannelse i brødtekst med fokus på relevante fag eller specialiseringer for dette job.
            3. Profil: En stærk, narrativ indledning.
            4. Sprog: Skal være professionelt og matche terminologien i jobopslaget.

            SVAR KUN I JSON FORMAT:
            - 'analyse': {{ 'score': int, 'vurdering': str, 'sandsynlighed': str }}
            - 'kontakt': str
            - 'profil': str
            - 'erfaring': str (Brødtekst-afsnit pr. job)
            - 'uddannelse': str (Brødtekst-afsnit pr. uddannelse)
            - 'kompetencer': str (10 vigtigste ord adskilt af komma)

            DATA:
            JOB: {st.session_state.job_content}
            CV: {st.session_state.master_cv_text}
            """
            
            resp = client.chat.completions.create(
                model="gpt-4o", 
                messages=[{"role": "user", "content": prompt}], 
                response_format={"type": "json_object"}
            )
            res = json.loads(resp.choices[0].message.content)
            ana = res.get('analyse', {})

            # --- VISNING ---
            st.markdown("<div class='analyse-card'>", unsafe_allow_html=True)
            st.subheader(f"🎯 Match Score: {ana.get('score')}%")
            st.write(f"**Vurdering:** {ana.get('vurdering')}")
            st.write(f"**Chancer for samtale:** {ana.get('sandsynlighed')}")
            st.markdown("</div>", unsafe_allow_html=True)

            # Forhåndsvisning
            st.markdown(f"<div class='cv-block'><h1>{st.session_state.user_name}</h1>{res.get('kontakt')}</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("<div class='cv-block'><div class='cv-section-title'>Profil</div>" + res.get('profil') + "</div>", unsafe_allow_html=True)
                st.markdown("<div class='cv-block'><div class='cv-section-title'>Erhvervserfaring</div>" + res.get('erfaring') + "</div>", unsafe_allow_html=True)
            with c2:
                st.markdown("<div class='cv-block'><div class='cv-section-title'>Uddannelse</div>" + res.get('uddannelse') + "</div>", unsafe_allow_html=True)
                st.markdown("<div class='cv-block'><div class='cv-section-title'>Kompetencer</div>" + res.get('kompetencer') + "</div>", unsafe_allow_html=True)

            # Download
            if st.session_state.cv_template:
                replacements = {
                    "{{NAVN}}": st.session_state.user_name,
                    "{{CV_KONTAKT}}": res.get('kontakt', ''),
                    "{{CV_PROFIL}}": res.get('profil', ''),
                    "{{CV_ERFARING}}": res.get('erfaring', ''),
                    "{{CV_UDDANNELSE}}": res.get('uddannelse', ''),
                    "{{CV_KOMPETENCER}}": res.get('kompetencer', '')
                }
                final_doc = fill_cv_docx(st.session_state.cv_template, replacements)
                st.download_button("Hent CV med brødtekst (.docx) 📄", final_doc, f"CV_{st.session_state.user_name}.docx", type="primary")

        except Exception as e:
            st.error(f"Fejl: {e}")

    if st.button("Start forfra 🔄"):
        st.session_state.cv_step = 1
        st.rerun()
