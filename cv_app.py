import streamlit as st
from openai import OpenAI
import io
import requests
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import json

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="CV-Builder Pro: Premium Layout", page_icon="🖋️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    h1 { text-align: center; font-weight: 800; color: #4a90e2; margin-bottom: 20px; }
    
    /* CV Container i appen */
    .cv-preview {
        background-color: #ffffff;
        color: #1a1a1a;
        padding: 40px;
        border-radius: 5px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        font-family: 'Times New Roman', Times, serif;
    }
    
    .cv-header {
        border-bottom: 2px solid #1a1a1a;
        margin-bottom: 20px;
        padding-bottom: 10px;
    }
    
    .section-title {
        font-size: 1.2em;
        font-weight: bold;
        text-transform: uppercase;
        border-bottom: 1px solid #ddd;
        margin-top: 25px;
        margin-bottom: 10px;
        color: #2c3e50;
    }
    
    /* Styling af de enkelte poster/afsnit */
    .entry-block {
        margin-bottom: 15px;
    }
    
    .entry-title {
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 2px;
    }
    
    .entry-meta {
        font-style: italic;
        color: #555;
        margin-bottom: 5px;
    }
    
    .entry-desc {
        line-height: 1.6;
        text-align: justify;
    }

    .analyse-box {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #4a90e2;
        margin-bottom: 30px;
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
st.markdown("<h1>🖋️ Premium CV Designer & Match Analyst</h1>", unsafe_allow_html=True)

if 'cv_step' not in st.session_state: st.session_state.cv_step = 1

if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("📄 Grundlag")
        master_cv = st.file_uploader("Upload Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Upload Word-skabelon (DOCX)", type="docx")
        navn = st.text_input("Dit fulde navn:")
    with col2:
        st.subheader("🎯 Jobmål")
        job_url = st.text_input("Link til opslag:")
        if st.button("Hent jobtekst 🌐"):
            st.session_state.temp_job_text = get_text_from_url(job_url)
        job_text = st.text_area("Jobbeskrivelse:", value=st.session_state.get('temp_job_text', ""), height=250)

    if st.button("Generér Målrettet CV ✨", type="primary", use_container_width=True):
        if master_cv and job_text:
            st.session_state.master_cv_text = extract_pdf(master_cv)
            st.session_state.job_content = job_text
            st.session_state.cv_template = cv_template
            st.session_state.user_name = navn
            st.session_state.cv_step = 2
            st.rerun()
        else:
            st.error("Husk at uploade dit CV og indsætte jobteksten.")

elif st.session_state.cv_step == 2:
    with st.spinner("AI strukturerer dine afsnit og skriver brødtekst..."):
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"""
            Du er en elite CV-forfatter. Omskriv Master-CV'et, så det matcher jobopslaget perfekt.
            
            KRAV TIL STRUKTUR OG INDHOLD:
            1. AFDELING: Hver uddannelse, hvert job og hvert kursus skal være sit eget afsnit.
            2. BRØDTEKST: Under hver titel skal der være en beskrivelse i narrativ brødtekst (ikke punktform). 
            3. ERHVERVSERFARING: Beskrivelsen skal integrere resultater og ansvar flydende. Match sproget fra jobopslaget.
            4. UDDANNELSE: Beskriv relevansen af uddannelsen for dette specifikke job.
            5. KURSER: Forklar kort, hvad kurset har givet dig af kompetencer.

            SVAR KUN I JSON FORMAT:
            - 'analyse': {{ 'score': int, 'vurdering': str, 'sandsynlighed': str }}
            - 'kontakt': str
            - 'profil': str
            - 'erfaring': str (Hvert job som: TITEL | FIRMA | PERIODE efterfulgt af beskrivende brødtekst-afsnit)
            - 'uddannelse': str (Hver uddannelse som: TITEL | STED | ÅR efterfulgt af beskrivende brødtekst-afsnit)
            - 'kurser': str (Hvert kursus med beskrivelse)
            - 'kompetencer': str (10 nøgleord adskilt af komma)

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

            # --- ANALYSE OVERBLIK ---
            st.markdown("<div class='analyse-box'>", unsafe_allow_html=True)
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Match Score", f"{ana.get('score')}%")
            col_b.write(f"**Vurdering:**\n{ana.get('vurdering')}")
            col_c.write(f"**Chancer:**\n{ana.get('sandsynlighed')}")
            st.markdown("</div>", unsafe_allow_html=True)

            # --- FORHÅNDSVISNING (PREMIUM LAYOUT) ---
            st.markdown('<div class="cv-preview">', unsafe_allow_html=True)
            
            # Header
            st.markdown(f'<div class="cv-header"><h1>{st.session_state.user_name}</h1><p>{res.get("kontakt")}</p></div>', unsafe_allow_html=True)
            
            # Profil
            st.markdown('<div class="section-title">Profil</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="entry-desc">{res.get("profil")}</div>', unsafe_allow_html=True)
            
            # Erfaring
            st.markdown('<div class="section-title">Erhvervserfaring</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="entry-desc">{res.get("erfaring")}</div>', unsafe_allow_html=True)
            
            # Uddannelse
            st.markdown('<div class="section-title">Uddannelse</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="entry-desc">{res.get("uddannelse")}</div>', unsafe_allow_html=True)
            
            # Kurser
            if res.get("kurser"):
                st.markdown('<div class="section-title">Kurser & Certificeringer</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="entry-desc">{res.get("kurser")}</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

            # --- DOWNLOAD ---
            st.markdown("<br>", unsafe_allow_html=True)
            if st.session_state.cv_template:
                replacements = {
                    "{{NAVN}}": st.session_state.user_name,
                    "{{CV_KONTAKT}}": res.get('kontakt', ''),
                    "{{CV_PROFIL}}": res.get('profil', ''),
                    "{{CV_ERFARING}}": res.get('erfaring', ''),
                    "{{CV_UDDANNELSE}}": res.get('uddannelse', ''),
                    "{{CV_KURSER}}": res.get('kurser', ''),
                    "{{CV_KOMPETENCER}}": res.get('kompetencer', '')
                }
                final_doc = fill_cv_docx(st.session_state.cv_template, replacements)
                st.download_button("Download færdigt CV (.docx) 📄", final_doc, f"CV_{st.session_state.user_name}.docx", type="primary", use_container_width=True)

        except Exception as e:
            st.error(f"Fejl: {e}")

    if st.button("Start forfra 🔄"):
        st.session_state.cv_step = 1
        st.rerun()
