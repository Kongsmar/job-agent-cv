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
    """Henter og formaterer jobopslaget med overskrifter og lister."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Fjern støj
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.extract()

        formatted_output = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
            text = tag.get_text().strip()
            if text:
                if tag.name in ['h1', 'h2', 'h3']:
                    formatted_output.append(f"\n\n### {text.upper()}\n")
                elif tag.name == 'li':
                    formatted_output.append(f"* {text}")
                else:
                    formatted_output.append(f"{text}\n")
        return "\n".join(formatted_output)
    except:
        return "Kunne ikke hente teksten fra linket. Kopier venligst teksten manuelt ind."

def extract_pdf(file):
    """Læser tekst fra det uploadede Master-CV."""
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except:
        return ""

def fill_cv_docx(template, data_dict):
    """Erstatter flettekoder i Word-skabelonen."""
    try:
        template.seek(0)
        doc = Document(template)
        # Erstat i brødtekst
        for p in doc.paragraphs:
            for key, value in data_dict.items():
                if key in p.text:
                    p.text = p.text.replace(key, str(value))
        # Erstat i tabeller
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for key, value in data_dict.items():
                            if key in p.text:
                                p.text = p.text.replace(key, str(value))
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
    except Exception as e:
        st.error(f"Fejl ved Word-fletning: {e}")
        return None

# --- APP INTERFACE ---
st.title("📄 CV-Builder Pro")
st.markdown("Optimér dit CV mod jobopslagets nøgleord og gå gennem ATS-screening.")

if 'cv_step' not in st.session_state: 
    st.session_state.cv_step = 1

# STEP 1: INPUT DATA
if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2)
    with col1:
        st.header("1. Dit CV-grundlag")
        master_cv = st.file_uploader("Upload dit Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Upload din Word-skabelon (CV)", type="docx")
        navn = st.text_input("Dit fulde navn:", placeholder="F.eks. Jensen Jensen")
    
    with col2:
        st.header("2. Jobmålet")
        job_url = st.text_input("Link til jobopslag:")
        if st.button("Hent jobtekst 🌐") and job_url:
            st.session_state.temp_job_text = get_text_from_url(job_url)
        
        job_text = st.text_area("Jobtekst (tjek formatering):", 
                                value=st.session_state.get('temp_job_text', ""), 
                                height=450)

    if st.button("Analyser og generér nyt CV ✨", disabled=not (master_cv and job_text)):
        st.session_state.master_cv_text = extract_pdf(master_cv)
        st.session_state.job_content = job_text
        st.session_state.cv_template = cv_template
        st.session_state.user_name = navn
        st.session_state.cv_step = 2
        st.rerun()

# STEP 2: GENERERING OG RESULTAT
elif st.session_state.cv_step == 2:
    with st.spinner("AI omskriver dit CV med fokus på resultater og ATS-match..."):
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            
            prompt = f"""
            Du er ekspert i ATS-optimering og rekruttering. 
            Omskriv indholdet fra Master-CV'et, så det matcher jobopslaget perfekt.
            
            REGLER:
            1. Brug nøgleord fra jobopslaget.
            2. Gør erhvervserfaring RESULTATORIENTERET. Brug bullets: 'Opnåede X ved at gøre Y'.
            3. Svar KUN i JSON format.
            
            JSON STRUKTUR:
            - 'profil': En skarp indledning (5-6 linjer).
            - 'erfaring': Al erhvervserfaring omskrevet med bullets.
            - 'kompetencer': Liste over de 10 vigtigste skills.
            
            DATA:
            JOB: {st.session_state.job_content}
            CV: {st.session_state.master_cv_text}
            """
            
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "Du er en professionel CV-editor. Svar KUN i JSON format."}, 
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            content = resp.choices[0].message.content
            if not content:
                st.error("Fejl: AI returnerede intet indhold.")
                st.stop()
                
            res = json.loads(content)
            
            st.success("CV'et er nu målrettet!")
            
            col_res1, col_res2 = st.columns([2, 1])
            with col_res1:
                st.subheader("Omskrevet Erfaring")
                st.write(res.get('erfaring', ''))
            with col_res2:
                st.subheader("Ny Profiltekst")
                st.info(res.get('profil', ''))
                st.subheader("Nøglekompetencer")
                st.write(res.get('kompetencer', ''))

            if st.session_state.cv_template:
                replacements = {
                    "{{NAVN}}": st.session_state.user_name,
                    "{{CV_PROFIL}}": res.get('profil', ''),
                    "{{CV_ERFARING}}": res.get('erfaring', ''),
                    "{{CV_KOMPETENCER}}": res.get('kompetencer', '')
                }
                final_doc = fill_cv_docx(st.session_state.cv_template, replacements)
                if final_doc:
                    st.download_button("Hent dit færdige CV (.docx) 📄", final_doc, f"CV_{st.session_state.user_name}.docx")
            
        except Exception as e:
            st.error(f"Der skete en fejl: {e}")

    if st.button("Start forfra 🔄"):
        st.session_state.cv_step = 1
        st.rerun()
