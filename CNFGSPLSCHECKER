import streamlit as st
import re

# ==========================================
# 1. NETTOYAGE ET PARSING DES LOGS DE PROD (SPOOLCOM)
# ==========================================

def clean_line(line):
    """Supprime les résidus de logs de transfert comme """
    return re.sub(r'\', '', line).strip()

def parse_spoolcom_log(file_content):
    """
    Parse un log global SPOOLCOM (contenant DEV, PRINT et LOC mélangés)
    Retourne 3 dictionnaires : devs, prints, locs
    """
    devs = {}
    prints = {}
    locs = {}
    
    current_section = None
    lines = file_content.splitlines()
    
    for line in lines:
        line_upper = line.upper()
        # Détection des changements de section dans le fichier de log
        if "DEV" in line_upper and "DEVICE" in line_upper and "STATE" in line_upper:
            current_section = "DEV"
            continue
        elif "PRINT" in line_upper and "STATE" in line_upper and "CPU" in line_upper:
            current_section = "PRINT"
            continue
        elif "LOC" in line_upper and "LOCATION" in line_upper and "DEVICE" in line_upper:
            current_section = "LOC"
            continue
        elif line_upper.startswith(")PRINT") or line_upper.startswith(")LOC") or "LOG END" in line_upper:
            current_section = None
            continue
            
        cleaned = clean_line(line)
        if not cleaned or cleaned.startswith("=") or cleaned.startswith(")") or "LOG START" in cleaned:
            continue
            
        # --- Section DEV ---
        if current_section == "DEV" and cleaned.startswith("$"):
            parts = re.split(r'\s+', cleaned)
            if len(parts) >= 2:
                dev_name = parts[0]
                if "ERROR" in cleaned:
                    error_match = re.search(r'(DEV ERROR \d+)', cleaned)
                    state = error_match.group(1) if error_match else "ERROR"
                    proc = parts[-1] if parts[-1].startswith("$") else (parts[-2] if len(parts) > 2 else "UNKNOWN")
                else:
                    state = parts[1]
                    proc = parts[-1] if parts[-1].startswith("$") else "UNKNOWN"
                devs[dev_name] = {"state": state, "proc": proc}
                
        # --- Section PRINT ---
        elif current_section == "PRINT" and cleaned.startswith("$"):
            parts = re.split(r'\s+', cleaned)
            if len(parts) >= 4:
                print_name = parts[0]
                state = parts[1]
                # Reconstitution CPU/BACKUP
                cpu_backup = "".join(parts[2:5]) if len(parts) >= 5 else parts[2]
                pri = parts[-1]
                prints[print_name] = {"state": state, "cpu_backup": cpu_backup, "pri": pri}
                
        # --- Section LOC ---
        elif current_section == "LOC" and cleaned.startswith("#"):
            parts = re.split(r'\s+', cleaned)
            if len(parts) >= 2:
                loc_name = parts[0]
                target_dev = parts[1] if parts[1].startswith("$") else "UNKNOWN"
                locs[loc_name] = target_dev

    return devs, prints, locs

# ==========================================
# 2. PARSING DU FICHIER DE CONFIGURATION (CNFGSPLS)
# ==========================================

def parse_cnfgspls(file_content):
    """
    Parse le fichier de conf d'origine pour lister ce qui est déclaré officiellement
    """
    conf_devs = set()
    conf_prints = set()
    conf_locs = {}  # {location: target_dev}
    
    lines = file_content.splitlines()
    for line in lines:
        cleaned = clean_line(line).upper()
        if cleaned.startswith("COMMENT") or not cleaned:
            continue
            
        if cleaned.startswith("DEV") and "$" in cleaned:
            match = re.search(r'DEV\s+(\$[A-Z0-9#\.]+)', cleaned)
            if match:
                conf_devs.add(match.group(1))
                
        elif cleaned.startswith("PRINT") and "$" in cleaned:
            match = re.search(r'PRINT\s+(\$[A-Z0-9#\.]+)', cleaned)
            if match:
                conf_prints.add(match.group(1))
                
        elif cleaned.startswith("LOC") and "#" in cleaned:
            # Extraction du type: LOC #NOM ,DEV $CIBLE
            match = re.search(r'LOC\s+(#[A-Z0-9\.\-_]+)\s*,\s*DEV\s+(\$[A-Z0-9#\.]+)', cleaned)
            if match:
                conf_locs[match.group(1)] = match.group(2)
                
    return conf_devs, conf_prints, conf_locs

# ==========================================
# 3. INTERFACE DE L'APPLICATION STREAMLIT
# ==========================================

st.set_page_config(page_title="Tandem Spooler Analyzer", layout="wide")

st.title("🖨️ HP NonStop - Analyseur de Spooler Spoolcom")
st.markdown("Compare tes logs de production actifs avec ton fichier de configuration globale `CNFGSPLS` sans effort.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Données de Production (Actif)")
    spool_file = st.file_uploader("Importer le log SPOOLCOM (ISIS ou ATLAS)", type=["log", "txt"])

with col2:
    st.subheader("2. Référentiel de Configuration")
    conf_file = st.file_uploader("Importer le fichier CNFGSPLS", type=["log", "txt"])

if spool_file and conf_file:
    spool_content = spool_file.read().decode("utf-8")
    conf_content = conf_file.read().decode("utf-8")
    
    # Extraction des données
    prod_devs, prod_prints, prod_locs = parse_spoolcom_log(spool_content)
    conf_devs, conf_prints, conf_locs = parse_cnfgspls(conf_content)
    
    st.success("Fichiers chargés et nettoyés avec succès ! Début de l'analyse réglementaire...")
    
    # --- ONGLET 1 : ANALYSE DES DEV ---
    st.header("🛠️ Analyse des Imprimantes (DEV)")
    missing_devs = sorted([d for d in prod_devs if d not in conf_devs])
    
    if missing_devs:
        st.error(f"Il manque {len(missing_devs)} imprimantes dans ton fichier de conf !")
        dev_code = ""
        for dev in missing_devs:
            info = prod_devs[dev]
            dev_code += f"DEV {dev} ,PROCESS {info['proc']} ,SPEED 100,WIDTH -1 ,RESTART 120,HEADER OFF,FIFO ON\n"
            dev_code += f"DEV {dev} ,PARM 1024,RETRY 10 ,TIMEOUT 360 ,LUEOLVALUE CRLF\n"
            dev_code += f"DEV {dev} ,DEVRESET ON ,STARTFF OFF,ENDFF ON ,EXCLUSIVE OFF,DEVTYPE\n\n"
        st.text_area("Lignes TACL à rajouter dans ton CNFGSPLS :", value=dev_code, height=250)
    else:
        st.success("Toutes les imprimantes actives sont bien déclarées dans la conf !")

    # --- ONGLET 2 : ANALYSE DES LOC ---
    st.header("📍 Analyse des Locations (LOC)")
    missing_locs = sorted([l for l in prod_locs if l not in conf_locs])
    incoherent_locs = sorted([l for l in prod_locs if l in conf_locs and prod_locs[l] != conf_locs[l]])
    
    tab_missing, tab_incoherent = st.tabs(["Locations Manquantes", "Incohérences de Cibles"])
    
    with tab_missing:
        if missing_locs:
            st.warning(f"{len(missing_locs)} locations sont actives en prod mais absentes de ta conf.")
            loc_code = ""
            for loc in missing_locs:
                loc_code += f"LOC {loc:<20} ,DEV    {prod_locs[loc]}\n"
            st.text_area("Lignes LOC à coller dans ton CNFGSPLS :", value=loc_code, height=200)
        else:
            st.success("Aucune location manquante.")
            
    with tab_incoherent:
        if incoherent_locs:
            st.error("🚨 ATTENTION : Ces locations existent des deux côtés mais ne pointent pas vers le même device !")
            for loc in incoherent_locs:
                st.write(f"• **{loc}** : Pointe vers `{prod_locs[loc]}` en Prod ➡️ mais configurée vers `{conf_locs[loc]}` dans ton fichier.")
        else:
            st.success("Aucune incohérence de routage détectée.")

    # --- ONGLET 3 : ANALYSE DES PRINT ---
    st.header("⚙️ Analyse des Processus (PRINT)")
    missing_prints = sorted([p for p in prod_prints if p not in conf_prints])
    
    if missing_prints:
        st.warning(f"Il manque {len(missing_prints)} processus PRINT dans ta conf.")
        print_code = ""
        for prt in missing_prints:
            print_code += f"PRINT {prt}, FILE $SYSEXP.OPRPRINT.OPRINTCN\nPRINT {prt}, PRI 145, BACKUP 1\nPRINT {prt}, CPU 2\n\n"
        st.text_area("Lignes PRINT à rajouter :", value=print_code, height=180)
    else:
        st.success("Tous les processus d'impression sont bien configurés.")
