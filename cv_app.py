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
st.set_page_config(page_title="Strategisk CV-Builder Pro", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1a1c24; color: #e0e0e0; }
    h1 { text-align: center; color: #ffffff !important; border-bottom: 2px solid #4a90e2; padding-bottom: 15px; font-weight: 800; }
    
    .cv-block {
        background-color: #2d303d;
        padding: 25px;
        border-radius: 12px;
        border-left: 5px solid #4a90e2;
        margin-bottom: 25px;
        box-shadow: 0 6px 10px rgba(0, 0, 0, 0.4);
    }
    
    .cv-section-title {
        font-size: 1.4em;
        font-weight: bold;
        color: #4a90e2;
        margin-bottom: 20px;
        border-bottom: 1px solid #4a4d5e;
        padding-bottom: 8px;
        text-transform: uppercase;
    }
    
    .cv-text {
        font-family: 'Segoe UI', sans-serif;
        line-height: 1.6;
        white-space: pre-wrap;
        color: #f0f0f0;
    }

    .entry-headline {
        background-color: #262936;
        padding: 12px 18px;
        border-radius: 8px;
        border: 1px solid #4a4d5e;
        color: #ffffff;
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 15px;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

# --- HJÆLPEFUNKTIONER ---
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
    if not text or len(str(text).strip()) < 2: return ""
    formatted = re.sub(r'(\[.*?\])', r'\n\n\1\n', str(text))
    return formatted.strip()

def fill_cv_docx(template, data_dict):
    try:
        template.seek(0)
        doc = Document(template)
        clean_data = {k: format_text_for_word(v) for k, v in data_dict.items()}
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
    if not raw_text or len(str(raw_text).strip()) < 5: return None
    pattern = r'(\[.*?\])'
    parts = re.split(pattern, str(raw_text))
    formatted_html = ""
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part:
            i += 1
            continue
        if part.startswith('[') and part.endswith(']'):
            headline = part.replace('[', '').replace(']', '')
            content = parts[i+1].strip() if (i+1) < len(parts) else ""
            formatted_html += f"""
            <div class='cv-block'>
                <div class='entry-headline'>{headline}</div>
                <div class='cv-text'>{content}</div>
            </div>"""
            i += 2
        else:
            formatted_html += f"<div class='cv-block'><div class='cv-text'>{part}</div></div>"
            i += 1
    return formatted_html

# --- APP FLOW ---
if 'cv_step' not in st.session_state: st.session_state.cv_step = 1

if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("1. Dit Grundlag")
        master_cv = st.file_uploader("Upload dit Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Upload din Word-skabelon (DOCX)", type="docx")
        navn = st.text_input("Dit fulde navn:")
        
        # NY BOKS: Særlige tilføjelser / Fokuspunkter
        user_notes = st.text_area("Særlige fokuspunkter (AI vil lægge ekstra vægt på dette):", 
                                 placeholder="F.eks.: Læg vægt på projektledelse, fremhæv mine tyskkundskaber, eller gør opmærksom på min erfaring med Python...")
        
    with col2:
        st.subheader("2. Jobmålet")
        job_url = st.text_input("Link til jobopslag (valgfrit):")
        if st.button("Hent jobtekst fra link 🌐") and job_url:
            st.session_state.temp_job_text = get_text_from_url(job_url)
        job_text = st.text_area("Indsæt jobbeskrivelsen her:", value=st.session_state.get('temp_job_text', ""), height=250)

    if st.button("Generér strategisk CV ✨", type="primary", use_container_width=True):
        if master_cv and job_text:
            st.session_state.master_cv_text = extract_pdf(master_cv)
            st.session_state.job_content = job_text
            st.session_state.cv_template = cv_template
            st.session_state.user_name = navn
            st.session_state.user_notes = user_notes # Gemmer brugerens noter
            st.session_state.cv_step = 2
            st.rerun()

elif st.session_state.cv_step == 2:
    with st.spinner("AI vægter dine specifikke ønsker og optimerer indholdet..."):
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"""
            Du er elite-rekrutteringskonsulent. Omskriv Master-CV'et efter disse regler:
            
            1. SÆRLIG VÆGTNING (VIGTIGT): Brugeren har anmodet om følgende fokus: "{st.session_state.user_notes}". Integrer dette som højeste prioritet i profilteksten og de relevante erfaringer.
            2. BEHOLD DISKRETE POSTER: Hver ansættelse skal forblive sin egen unikke boks.
            3. FORMAT: Hver post skal starte med [STILLING | VIRKSOMHED | PERIODE].
            4. BROBYGNING: Beskriv substans og kobl det direkte til jobopslagets behov.
            5. TERMINOLOGI: "Erfaring" er kun erhverv. Uddannelse er "faglig baggrund".

            SVAR KUN I JSON FORMAT:
            {{
              "analyse": {{ "score": int, "vurdering": str }},
              "kontakt": str, "profil": str, "erfaring": str, "uddannelse": str, 
              "kompetencer": str, "kurser": str, "sprog": str, "fritid": str
            }}
            DATA: JOB: {st.session_state.job_content} | Master-CV: {st.session_state.master_cv_text}
            """
            
            resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
            res = json.loads(resp.choices[0].message.content)
            
            # --- VISNING ---
            st.markdown(f"<div class='cv-block' style='text-align:center;'><h1>{st.session_state.user_name}</h1>{res.get('kontakt', '')}</div>", unsafe_allow_html=True)
            
            col_l, col_r = st.columns([2, 1], gap="medium")
            with col_l:
                if res.get('profil'):
                    st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Profil</div><div class='cv-text'>{res.get('profil')}</div></div>", unsafe_allow_html=True)
                if res.get('erfaring'):
                    st.markdown("<div class='cv-section-title'>Erhvervserfaring</div>", unsafe_allow_html=True)
                    st.markdown(style_cv_entries(res.get('erfaring')), unsafe_allow_html=True)
            
            with col_r:
                if res.get('kompetencer'):
                    st.markdown(f"<div class='cv-block'><div class='cv-section-title'>Kompetencer</div><div class='cv-text'>{res.get('kompetencer')}</div></div>", unsafe_allow_html=True)
                if res.get('uddannelse'):
                    st.markdown("<div class='cv-section-title'>Uddannelse</div>", unsafe_allow_html=True)
                    st.markdown(style_cv_entries(res.get('uddannelse')), unsafe_allow_html=True)
                if res.get('kurser'):
                    st.markdown("<div class='cv-section-title'>Kurser</div>", unsafe_allow_html=True)
                    st.markdown(style_cv_entries(res.get('kurser')), unsafe_allow_html=True)

            if st.session_state.cv_template:
                replacements = {
                    "{{NAVN}}": st.session_state.user_name,
                    "{{CV_KONTAKT}}": res.get('kontakt', ''),
                    "{{CV_PROFIL}}": res.get('profil', ''),
                    "{{CV_ERFARING}}": res.get('erfaring', ''),
                    "{{CV_UDDANNELSE}}": res.get('uddannelse', ''),
                    "{{CV_KURSER}}": res.get('kurser', ''),
                    "{{CV_SPROG}}": res.get('sprog', ''),
                    "{{CV_KOMPETENCER}}": res.get('kompetencer', ''),
                    "{{CV_FRITID}}": res.get('fritid', '')
                }
                final_doc = fill_cv_docx(st.session_state.cv_template, replacements)
                st.download_button("Download målrettet CV (.docx) 📄", final_doc, f"CV_{st.session_state.user_name}.docx", type="primary", use_container_width=True)

        except Exception as e:
            st.error(f"Fejl: {e}")

    if st.button("Start forfra 🔄"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.cv_step = 1
        st.rerun()
