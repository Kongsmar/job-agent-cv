import streamlit as st
from openai import OpenAI
import io
import requests
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import json
import re

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="CV-Builder Pro", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1a1c24; color: #e0e0e0; }
    h1 { text-align: center; color: #ffffff !important; border-bottom: 2px solid #4a90e2; padding-bottom: 15px; font-weight: 800; }
    
    .cv-block {
        background-color: #2d303d;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #4a90e2;
        margin-bottom: 20px;
    }
    
    .analyse-block {
        background-color: #262936;
        padding: 25px;
        border-radius: 12px;
        border: 2px solid #4a90e2;
        margin-bottom: 30px;
    }

    .score-container {
        background-color: #0e1117;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #4a90e2;
    }
    
    .score-number {
        font-size: 2.5em;
        font-weight: 800;
        color: #4a90e2;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNKTIONER ---
def get_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer"]): element.extract()
        return "\n".join([tag.get_text().strip() for tag in soup.find_all(['h1', 'h2', 'p', 'li']) if tag.get_text()])
    except: return "Kunne ikke hente tekst."

def extract_pdf(file):
    try:
        reader = PdfReader(file)
        return "".join([p.extract_text() for p in reader.pages])
    except: return ""

def format_text_for_word(text):
    if not text: return ""
    formatted = re.sub(r'\[(.*?)\]', r'\n\n\1\n', text)
    return formatted.strip()

def fill_cv_docx(template, data_dict):
    try:
        template.seek(0)
        doc = Document(template)
        clean_data = {k: format_text_for_word(str(v)) for k, v in data_dict.items()}

        for p in doc.paragraphs:
            for key, value in clean_data.items():
                if key in p.text: p.text = p.text.replace(key, value)
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for key, value in clean_data.items():
                            if key in p.text: p.text = p.text.replace(key, value)
        
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
    except: return None

# --- APP FLOW ---
st.markdown("<h1>🎯 CV-Builder Pro: Redigér & Optimer</h1>", unsafe_allow_html=True)

if 'cv_step' not in st.session_state: st.session_state.cv_step = 1

if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("1. Filer & Grundlag")
        master_cv = st.file_uploader("Upload Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Upload Word-skabelon (DOCX)", type="docx")
        navn = st.text_input("Dit fulde navn:")
    with col2:
        st.subheader("2. Jobmål")
        job_url = st.text_input("Link til jobopslag:")
        if st.button("Hent jobtekst 🌐") and job_url:
            st.session_state.temp_job_text = get_text_from_url(job_url)
        job_text = st.text_area("Jobbeskrivelse:", value=st.session_state.get('temp_job_text', ""), height=250)

    if st.button("Generér udkast ✨", type="primary", use_container_width=True):
        if master_cv and job_text:
            st.session_state.master_cv_text = extract_pdf(master_cv)
            st.session_state.job_content = job_text
            st.session_state.cv_template = cv_template
            st.session_state.user_name = navn
            st.session_state.cv_step = 2
            st.rerun()

elif st.session_state.cv_step == 2:
    if 'ai_output' not in st.session_state:
        with st.spinner("AI analyserer og skriver..."):
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"""
            Du er elite-rekrutteringskonsulent. Omskriv Master-CV'et så det matcher jobopslaget.
            FOKUS: 1. person ("Jeg"), konkrete RESULTATER, og brug af vigtige nøgleord fra jobopslaget.
            STRUKTUR: Hver post skal starte med [TITEL | STED | PERIODE].
            
            SVAR KUN I JSON FORMAT:
            {{
              "analyse": {{ "score": int, "vurdering": str, "manglende_ord": list }},
              "kontakt": str, "profil": str, "erfaring": str, "uddannelse": str, "sprog": str, "kompetencer": str
            }}
            DATA: JOB: {st.session_state.job_content} | CV: {st.session_state.master_cv_text}
            """
            resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
            st.session_state.ai_output = json.loads(resp.choices[0].message.content)

    res = st.session_state.ai_output
    ana = res.get('analyse', {})

    # --- ANALYSE SEKTION ---
    st.markdown("<div class='analyse-block'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 2])
    c1.markdown(f"<div class='score-container'><span class='score-number'>{ana.get('score')}%</span>Match</div>", unsafe_allow_html=True)
    c2.write(f"**Vurdering:** {ana.get('vurdering')}")
    c3.write("**Manglende nøgleord:**")
    c3.write(", ".join(ana.get('manglende_ord', [])))
    st.markdown("</div>", unsafe_allow_html=True)

    # --- REDIGERINGS SEKTION ---
    st.subheader("✍️ Tilpas dit CV")
    st.info("Herunder kan du rette i teksten før download. Husk at fjerne klammerne [ ] hvis de generer dig, eller lad dem stå for struktur.")
    
    col_l, col_r = st.columns(2)
    with col_l:
        edit_profil = st.text_area("Profiltekst:", value=res.get('profil'), height=200)
        edit_erfaring = st.text_area("Erhvervserfaring (Brug [TITEL | STED | DATO]):", value=res.get('erfaring'), height=500)
    with col_r:
        edit_kontakt = st.text_input("Kontaktinfo:", value=res.get('kontakt'))
        edit_kompetencer = st.text_area("Kompetencer:", value=res.get('kompetencer'), height=150)
        edit_uddannelse = st.text_area("Uddannelse:", value=res.get('uddannelse'), height=200)
        edit_sprog = st.text_area("Sprog:", value=res.get('sprog'), height=100)

    # --- DOWNLOAD MED REDIGERET INDHOLD ---
    if st.session_state.cv_template:
        replacements = {
            "{{NAVN}}": st.session_state.user_name,
            "{{CV_KONTAKT}}": edit_kontakt,
            "{{CV_PROFIL}}": edit_profil,
            "{{CV_ERFARING}}": edit_erfaring,
            "{{CV_UDDANNELSE}}": edit_uddannelse,
            "{{CV_SPROG}}": edit_sprog,
            "{{CV_KOMPETENCER}}": edit_kompetencer
        }
        final_doc = fill_cv_docx(st.session_state.cv_template, replacements)
        st.download_button("Download dit tilpassede CV (.docx) 📄", final_doc, f"CV_{st.session_state.user_name}.docx", type="primary", use_container_width=True)

    if st.button("Start forfra 🔄"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
