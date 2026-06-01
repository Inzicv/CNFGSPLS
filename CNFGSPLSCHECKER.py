import streamlit as st
import pandas as pd
import re

# ==========================================
# 1. NETTOYAGE ET PARSING DES LOGS DE PROD (SPOOLCOM)
# ==========================================

def clean_line(line):
    return re.sub(r'\\', '', line).strip()

def parse_spoolcom_log(file_content):
    devs = {}
    prints = {}
    locs = {}
    
    current_section = None
    lines = file_content.splitlines()
    
    for line in lines:
        line_upper = line.upper()
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
    conf_devs = set()
    conf_prints = set()
    conf_locs = {}
    
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
            match = re.search(r'LOC\s+(#[A-Z0-9\.\-_]+)\s*,\s*DEV\s+(\$[A-Z0-9#\.]+)', cleaned)
            if match:
                conf_locs[match.group(1)] = match.group(2)
                
    return conf_devs, conf_prints, conf_locs

# ==========================================
# 3. INTERFACE DE L'APPLICATION STREAMLIT (AFFICHAGE EN LISTE TEXTE BRUT)
# ==========================================

st.set_page_config(page_title="Tandem Spooler Auditor", layout="wide")

st.title("Rapport d'Audit Spooler HP NonStop")
st.markdown("Analyse des ecarts et mouvements de configuration (Prod vs Fichier de Conf).")

col1, col2 = st.columns(2)
with col1:
    spool_file = st.file_uploader("1. Importer le log SPOOLCOM (Existant / Prod)", type=["log", "txt"])
with col2:
    conf_file = st.file_uploader("2. Importer le fichier CNFGSPLS (Theorique)", type=["log", "txt"])

if spool_file and conf_file:
    spool_content = spool_file.read().decode("utf-8")
    conf_content = conf_file.read().decode("utf-8")
    
    prod_devs, prod_prints, prod_locs = parse_spoolcom_log(spool_content)
    conf_devs, conf_prints, conf_locs = parse_cnfgspls(conf_content)
    
    st.info("Analyse croisee effectuee. Resultats complets affiches a la suite pour copier-coller.")
    
    # =========================================================================
    # BLOC 1 : LES ELEMENTS EXISTANTS MAIS ABSENTS DE LA CONF (A RAJOUTER)
    # =========================================================================
    st.markdown("# PARTIE 1 : Elements EXISTANTS en Prod mais ABSENTS du CNFGSPLS")
    
    # 1. DEV Manquants
    st.markdown("## 1. DEV (Imprimantes) existants non declares")
    missing_devs = sorted([d for d in prod_devs if d not in conf_devs])
    if missing_devs:
        df_m_dev = pd.DataFrame([{
            "Device": d, "Processus": prod_devs[d]['proc'], "Etat Actuel": prod_devs[d]['state']
        } for d in missing_devs])
        st.table(df_m_dev)
    else:
        st.text("Aucun peripherique existant n'est absent de la conf.")
        
    # 2. PRINT Manquants
    st.markdown("## 2. PRINT (Processus d'impression) existants non declares")
    missing_prints = sorted([p for p in prod_prints if p not in conf_prints])
    if missing_prints:
        df_m_print = pd.DataFrame([{
            "Processus PRINT": p, "Etat": prod_prints[p]['state'], "PRI": prod_prints[p]['pri'], "CPU/Backup": prod_prints[p]['cpu_backup']
        } for p in missing_prints])
        st.table(df_m_print)
    else:
        st.text("Aucun processus d'impression existant n'est absent de la conf.")
        
    # 3. LOC Manquantes
    st.markdown("## 3. LOC (Locations) existantes non declarees")
    missing_locs = sorted([l for l in prod_locs if l not in conf_locs])
    if missing_locs:
        df_m_loc = pd.DataFrame([{
            "Location": l, "Cible Spooler (Prod)": prod_locs[l]
        } for l in missing_locs])
        st.table(df_m_loc)
    else:
        st.text("Aucune location existante n'est absente de la conf.")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # =========================================================================
    # BLOC 2 : LES ELEMENTS DE LA CONF QUI SONT INACTIFS OU ABSENTS (A DEMONTER)
    # =========================================================================
    st.markdown("# PARTIE 2 : Elements CONFIGURES mais ABSENTS ou INACTIFS en Prod")
    
    # 4. DEV Inactifs
    st.markdown("## 4. DEV (Imprimantes) configures mais inactifs ou supprimes")
    inactive_devs = sorted([d for d in conf_devs if d not in prod_devs or prod_devs[d]['state'].upper() == "OFFLINE"])
    if inactive_devs:
        df_i_dev = pd.DataFrame([{
            "Device": d,
            "Statut en Prod": "Supprime du Spooler" if d not in prod_devs else "OFFLINE (Inactif)"
        } for d in inactive_devs])
        st.table(df_i_dev)
    else:
        st.text("Tous les devices configures sont actifs et en ligne.")
        
    # 5. PRINT Inactifs
    st.markdown("## 5. PRINT (Processus) configures mais non demarres")
    inactive_prints = sorted([p for p in conf_prints if p not in prod_prints])
    if inactive_prints:
        df_i_print = pd.DataFrame([{
            "Processus PRINT": p, "Statut": "Non demarre / Absent du Spooler"
        } for p in inactive_prints])
        st.table(df_i_print)
    else:
        st.text("Tous les processus d'impression configures tournent en prod.")
        
    # 6. LOC Inactives
    st.markdown("## 6. LOC (Locations) configurees mais inactives ou envoyees a la poubelle")
    inactive_locs = sorted([l for l in conf_locs if l not in prod_locs or prod_locs[l] == "$NULL.#POUB" or prod_locs[l] not in prod_devs])
    if inactive_locs:
        df_i_loc = pd.DataFrame([{
            "Location": l,
            "Cible theorique (Conf)": conf_locs[l],
            "Raison de l'inactivite": (
                "Supprimee de la Prod" if l not in prod_locs 
                else "Redirigee vers la Poubelle ($NULL)" if prod_locs[l] == "$NULL.#POUB"
                else f"Pointe vers un device inexistant ({prod_locs[l]})"
            )
        } for l in inactive_locs])
        st.table(df_i_loc)
    else:
        st.text("Toutes les locations configurees sont saines et actives.")
