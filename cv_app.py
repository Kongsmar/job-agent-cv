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
    
    /* CV-Blocks Layout */
    .cv-block {
        background-color: #2d303d;
        padding: 25px;
        border-radius: 12px;
        border-left: 5px solid #4a90e2;
        margin-bottom: 25px;
        box-shadow: 0 6px 10px rgba(0, 0, 0, 0.4);
    }
    
    .cv-section-title {
        font-size: 1.5em;
        font-weight: bold;
        color: #4a90e2;
        margin-bottom: 20px;
        border-bottom: 1px solid #4a4d5e;
        padding-bottom: 8px;
        text-transform: uppercase;
    }
    
    .cv-text {
        font-family: 'Georgia', serif;
        line-height: 1.8;
        white-space: pre-wrap;
        color: #f0f0f0;
    }

    .entry-container {
        margin-bottom: 25px;
        border-bottom: 1px dashed #4a4d5e;
        padding-bottom: 15px;
    }
    
    .entry-container:last-child {
        border-bottom: none;
    }

    .entry-headline {
        background-color: #262936;
        padding: 10px 15px;
        border-radius: 6px;
        border: 1px solid #3a3d4d;
        color: #ffffff;
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 10px;
    }

    /* Analyse-sektion */
    .analyse-block {
        background-color: #262936;
        padding: 30px;
        border-radius: 12px;
        border: 2px solid #4a90e2;
        margin-bottom: 35px;
    }

    .score-container {
        background-color: #0e1117;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #4a90e2;
    }
    
    .score-number {
        font-size: 3em;
        font-weight: 800;
        color: #4a90e2;
        display: block;
    }
    
    .score-label {
        font-size: 1em;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 1px;
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
    """Sørger for rene overskrifter og linjeskift i Word-filen."""
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

def style_cv_entries(raw_text):
    """Opdeler teksten i visuelle felter i appen."""
    if not raw_text: return ""
    pattern = r'(\[.*?\])'
    segments = re.split(pattern, raw_text)
    formatted_html = ""
    current_headline = None
    
    for segment in segments:
        segment = segment.strip()
        if not segment: continue
        if segment.startswith('[') and segment.endswith(']'):
            current_headline = segment.replace('[', '').replace(']', '')
        else:
            if current_headline:
                formatted_html += f"""
                <div class='entry-container'>
                    <div class='entry-headline'>{current_headline}</div>
                    <div class='cv-text'>{segment}</div>
                </div>"""
                current_headline = None
            else:
                formatted_html += f"<div class='entry-container'><div class='cv-text'>{segment}</div></div>"
    return formatted_html

# --- APP FLOW ---
st.markdown("<h1>🎯 CV-Builder Pro & Match Analyst</h1>", unsafe_allow_html=True)

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

    if st.button("Start Match-Analyse & Skriv CV ✨", type="primary", use_container_width=True):
        if master_cv and job_text:
            st.session_state.master_cv_text = extract_pdf(master_cv)
            st.session_state.job_content = job_text
            st.session_state.cv_template = cv_template
            st.session_state.user_name = navn
            st.session_state.cv_step = 2
            st.rerun()

elif st.session_state.cv_step == 2:
    with st.spinner("AI målretter dit CV og optimerer dine resultater..."):
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"""
            Du er elite-rekrutteringskonsulent. Omskriv Master-CV'et så det matcher jobopslaget 100%.
            KRAV:
            1. SPROG: Skriv i 1. person ("Jeg").
            2. RESULTATER: Beskriv konkrete resultater for hver rolle i brødteksten.
            3. STRUKTUR: Hver post (job/uddannelse) SKAL starte med: [TITEL | STED | PERIODE].
            
            SVAR KUN I JSON FORMAT:
            {{
              "analyse": {{ "score": int, "vurdering": str, "sandsynlighed": str }},
              "kontakt": str, "profil": str, "erfaring": str, "uddannelse": str, "sprog": str, "kompetencer": str, "kurser": str
            }}
            DATA: JOB: {st.session_state.job_content} | CV: {st.session_state.master_cv_text}
            """
            
            resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
            res = json.loads(resp.choices[0].message.content)
            ana = res.get('analyse', {})

            # --- ANALYSE VISNING ---
            st.markdown("<div class='analyse-block'>", unsafe_allow_html=True)
            col_score, col_details = st.columns([1, 2])
            with col_score:
                st.markdown(f"<div class='score-container'><span class='score-label'>Match Score</span><span class='score-number'>{ana.get('score')}%</span></div>", unsafe_allow_html=True)
            with col_details:
                st.markdown(f"### Strategisk Vurdering")
                st.write(f"**Vurdering:** {ana.get('vurdering')}")
                st.progress(ana.get('score', 0) / 100)
            st.markdown("</div>", unsafe_allow_html=True)

            # --- FORHÅNDSVISNING I APP ---
            st.markdown(f"<div class='cv-block' style='text-align:center;'><h1>{st.session_state.user_name}</h1>{res.get('kontakt', '')}</div>", unsafe_allow_html=True)
            
            col_l, col_r = st.columns([2, 1], gap="medium")
            with col_l:
                st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Profil</div><div class='cv-text'>{res.get('profil', '')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Erhvervserfaring</div>{style_cv_entries(res.get('erfaring', ''))}</div>", unsafe_allow_html=True)
            with col_r:
                st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Kompetencer</div><div class='cv-text'>{res.get('kompetencer', '')}</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Uddannelse</div>{style_cv_entries(res.get('uddannelse', ''))}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Sprog</div><div class='cv-text'>{res.get('sprog', '')}</div></div>", unsafe_allow_html=True)
                if res.get('kurser'):
                    st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Kurser</div>{style_cv_entries(res.get('kurser', ''))}</div>", unsafe_allow_html=True)

            # --- DOWNLOAD ---
            if st.session_state.cv_template:
                replacements = {
                    "{{NAVN}}": st.session_state.user_name,
                    "{{CV_KONTAKT}}": res.get('kontakt', ''),
                    "{{CV_PROFIL}}": res.get('profil', ''),
                    "{{CV_ERFARING}}": res.get('erfaring', ''),
                    "{{CV_UDDANNELSE}}": res.get('uddannelse', ''),
                    "{{CV_KURSER}}": res.get('kurser', ''),
                    "{{CV_SPROG}}": res.get('sprog', ''),
                    "{{CV_KOMPETENCER}}": res.get('kompetencer', '')
                }
                final_doc = fill_cv_docx(st.session_state.cv_template, replacements)
                st.download_button("Download målrettet CV (.docx) 📄", final_doc, f"CV_{st.session_state.user_name}.docx", type="primary", use_container_width=True)

        except Exception as e:
            st.error(f"Fejl under generering: {e}")

    if st.button("Start forfra 🔄"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.cv_step = 1
        st.rerun()
