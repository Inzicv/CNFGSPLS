import streamlit as st
import pandas as pd
import re

# ==========================================
# 1. FONCTIONS DE NETTOYAGE DU TEXTE
# ==========================================

def clean_line(line):
    # Supprime les marqueurs de transfert spécifiques 
    line = re.sub(r'\\', '', line)
    return line.strip()

# ==========================================
# 2. FONCTIONS DE PARSING (SPOOLER)
# ==========================================

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
            
        # Section DEV
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
                
        # Section PRINT
        elif current_section == "PRINT" and cleaned.startswith("$"):
            parts = re.split(r'\s+', cleaned)
            if len(parts) >= 4:
                print_name = parts[0]
                state = parts[1]
                cpu_backup = "".join(parts[2:5]) if len(parts) >= 5 else parts[2]
                pri = parts[-1]
                prints[print_name] = {"state": state, "cpu_backup": cpu_backup, "pri": pri}
                
        # Section LOC
        elif current_section == "LOC" and cleaned.startswith("#"):
            parts = re.split(r'\s+', cleaned)
            if len(parts) >= 2:
                loc_name = parts[0]
                target_dev = parts[1] if parts[1].startswith("$") else "UNKNOWN"
                locs[loc_name] = target_dev

    return devs, prints, locs

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
# 3. INTERFACE DE L'APPLICATION STREAMLIT
# ==========================================

st.set_page_config(page_title="Tandem Configuration Auditor", layout="wide")

# Menu de sélection dans la barre latérale
st.sidebar.title("Menu d'Audit")
mode_analyse = st.sidebar.selectbox(
    "Choisir le type d'analyse :",
    ["Audit Spooler (SPOOLCOM)", "Audit Générique (Logins / Profils / Conf)"]
)

if mode_analyse == "Audit Spooler (SPOOLCOM)":
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
        
        st.markdown("# PARTIE 1 : Elements EXISTANTS en Prod mais ABSENTS du CNFGSPLS")
        
        st.markdown("## 1. DEV (Imprimantes) existants non declares")
        missing_devs = sorted([d for d in prod_devs if d not in conf_devs])
        if missing_devs:
            df_m_dev = pd.DataFrame([{
                "Device": d, "Processus": prod_devs[d]['proc'], "Etat Actuel": prod_devs[d]['state']
            } for d in missing_devs])
            st.table(df_m_dev)
        else:
            st.text("Aucun peripherique existant n'est absent de la conf.")
            
        st.markdown("## 2. PRINT (Processus d'impression) existants non declares")
        missing_prints = sorted([p for p in prod_prints if p not in conf_prints])
        if missing_prints:
            df_m_print = pd.DataFrame([{
                "Processus PRINT": p, "Etat": prod_prints[p]['state'], "PRI": prod_prints[p]['pri'], "CPU/Backup": prod_prints[p]['cpu_backup']
            } for p in missing_prints])
            st.table(df_m_print)
        else:
            st.text("Aucun processus d'impression existant n'est absent de la conf.")
            
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

        st.markdown("# PARTIE 2 : Elements CONFIGURES mais ABSENTS ou INACTIFS en Prod")
        
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
            
        st.markdown("## 5. PRINT (Processus) configures mais non demarres")
        inactive_prints = sorted([p for p in conf_prints if p not in prod_prints])
        if inactive_prints:
            df_i_print = pd.DataFrame([{
                "Processus PRINT": p, "Statut": "Non demarre / Absent du Spooler"
            } for p in inactive_prints])
            st.table(df_i_print)
        else:
            st.text("Tous les processus d'impression configures tournent en prod.")
            
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

else:
    st.title("Audit Générique de Fichiers NonStop")
    st.markdown("Compare deux listes brutes nettoyées de leurs résidus OutsideView (ex: Logins, configurations, etc.).")
    
    col1, col2 = st.columns(2)
    with col1:
        file_a = st.file_uploader("Fichier A", type=["log", "txt"])
    with col2:
        file_b = st.file_uploader("Fichier B", type=["log", "txt"])
        
    if file_a and file_b:
        content_a = file_a.read().decode("utf-8").splitlines()
        content_b = file_b.read().decode("utf-8").splitlines()
        
        # Nettoyage et élimination des doublons
        set_a = set(clean_line(line) for line in content_a if clean_line(line) and not line.strip().startswith("="))
        set_b = set(clean_line(line) for line in content_b if clean_line(line) and not line.strip().startswith("="))
        
        st.info("Analyse comparative brute effectuée.")
        
        st.markdown("# Éléments présents dans le fichier A mais absents du fichier B")
        diff_a_b = sorted(list(set_a - set_b))
        if diff_a_b:
            df_diff_ab = pd.DataFrame({"Élément": diff_a_b})
            st.table(df_diff_ab)
        else:
            st.text("Aucune différence.")
            
        st.markdown("# Éléments présents dans le fichier B mais absents du fichier A")
        diff_b_a = sorted(list(set_b - set_a))
        if diff_b_a:
            df_diff_ba = pd.DataFrame({"Élément": diff_b_a})
            st.table(df_diff_ba)
        else:
            st.text("Aucune différence.")

```
