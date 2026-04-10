import streamlit as st
from openai import OpenAI
import io
import requests
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import json

# --- KONFIGURATION ---
st.set_page_config(page_title="CV-Builder Pro & Analyst", page_icon="📊", layout="wide")

# --- HJÆLPEFUNKTIONER ---
def get_text_from_url(url):
    """Henter og oprenser jobopslag fra nettet."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.extract()
        output = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
            text = tag.get_text().strip()
            if text:
                if tag.name in ['h1', 'h2', 'h3']: output.append(f"\n\n{text.upper()}\n")
                elif tag.name == 'li': output.append(f"• {text}")
                else: output.append(f"{text}\n")
        return "\n".join(output)
    except: return "Kunne ikke hente tekst automatisk. Indsæt venligst teksten manuelt."

def extract_pdf(file):
    """Læser tekst fra PDF."""
    try:
        reader = PdfReader(file)
        return "".join([p.extract_text() for p in reader.pages])
    except: return ""

def format_as_clean_text(data):
    """Sikrer at data altid er en pæn tekststreng uden klammer."""
    if isinstance(data, list):
        return "\n".join([str(item).replace("[", "").replace("]", "").replace("'", "") for item in data])
    return str(data).replace("[", "").replace("]", "").replace("'", "")

def fill_cv_docx(template, data_dict):
    """Fletter data ind i Word-skabelonen."""
    try:
        template.seek(0)
        doc = Document(template)
        # Erstat i paragraffer og tabeller
        for p in doc.paragraphs:
            for key, value in data_dict.items():
                if key in p.text:
                    p.text = p.text.replace(key, format_as_clean_text(value))
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for key, value in data_dict.items():
                            if key in p.text:
                                p.text = p.text.replace(key, format_as_clean_text(value))
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
    except: return None

# --- APP FLOW ---
st.title("📊 CV-Builder Pro & Match Analyst")
st.markdown("---")

if 'cv_step' not in st.session_state: st.session_state.cv_step = 1

if st.session_state.cv_step == 1:
    col1, col2 = st.columns(2)
    with col1:
        st.header("1. Dine Filer")
        master_cv = st.file_uploader("Upload dit Master-CV (PDF)", type="pdf")
        cv_template = st.file_uploader("Upload din Word-skabelon (DOCX)", type="docx")
        navn = st.text_input("Dit fulde navn:", placeholder="Navn Navnesen")
    
    with col2:
        st.header("2. Jobannoncen")
        job_url = st.text_input("Link til jobopslag:")
        if st.button("Hent jobtekst 🌐") and job_url:
            st.session_state.temp_job_text = get_text_from_url(job_url)
        job_text = st.text_area("Jobtekst:", value=st.session_state.get('temp_job_text', ""), height=350)

    if st.button("Start Match-Analyse & Generering ✨", disabled=not (master_cv and job_text), type="primary"):
        st.session_state.master_cv_text = extract_pdf(master_cv)
        st.session_state.job_content = job_text
        st.session_state.cv_template = cv_template
        st.session_state.user_name = navn
        st.session_state.cv_step = 2
        st.rerun()

elif st.session_state.cv_step == 2:
    with st.spinner("AI analyserer match og optimerer dit CV..."):
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"""
            Du er en elite-rekrutteringskonsulent og ATS-ekspert.
            
            OPGAVE:
            1. Analysér Master-CV mod Jobopslag. Giv en score og vurdering.
            2. Omskriv CV'et så det er 100% målrettet med fokus på RESULTATER.
            
            Svar KUN i JSON format. Alle felter (pånær score) skal være rene TEXT STRINGS.
            Brug punkttegn (•) og linjeskift (\\n) for struktur. Ingen klammer [].

            STRUKTUR:
            - 'analyse': {{ 'score': int, 'styrker': str, 'mangler': str, 'sandsynlighed': str }}
            - 'kontakt': str (tlf, mail, linkedin)
            - 'profil': str (fængende indledning)
            - 'erfaring': str (titel, sted, år + resultatorienterede bullets)
            - 'uddannelse': str (år, titel, sted)
            - 'kurser': str
            - 'sprog': str
            - 'kompetencer': str (de 10 vigtigste ord)

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

            # --- VIS ANALYSE ---
            st.header("🎯 Match-Analyse")
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                st.metric("Match Score", f"{ana.get('score')}%")
            with c2:
                st.metric("Sandsynlighed for samtale", ana.get('sandsynlighed'))
            with c3:
                st.progress(ana.get('score', 0) / 100)
                st.write(f"**Vurdering:** {ana.get('sandsynlighed')}")

            with st.container(border=True):
                st.write(f"✅ **Dine største styrker:** {ana.get('styrker')}")
                st.write(f"⚠️ **Her skal du være opmærksom (mangler):** {ana.get('mangler')}")

            st.divider()

            # --- VIS FLOT PRÆSENTATION ---
            st.header("📄 Forhåndsvisning af dit optimerede CV")
            
            with st.container(border=True):
                st.title(st.session_state.user_name if st.session_state.user_name else "Dit Navn")
                st.caption(res.get('kontakt'))
                
                col_left, col_right = st.columns([2, 1])
                with col_left:
                    st.markdown("#### Profil")
                    st.write(res.get('profil'))
                    st.markdown("#### Erhvervserfaring")
                    st.text(res.get('erfaring'))
                with col_right:
                    st.markdown("#### Kernekompetencer")
                    st.info(res.get('kompetencer'))
                    st.markdown("#### Uddannelse")
                    st.text(res.get('uddannelse'))
                    st.markdown("#### Sprog")
                    st.write(res.get('sprog'))

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
                final_cv = fill_cv_docx(st.session_state.cv_template, replacements)
                st.download_button("Download dit færdige CV (.docx) 📄", final_cv, f"CV_{st.session_state.user_name}.docx", type="primary", use_container_width=True)

        except Exception as e:
            st.error(f"Der skete en fejl under genereringen: {e}")

    if st.button("Start forfra 🔄"):
        st.session_state.cv_step = 1
        st.rerun()
