import streamlit as st
import pandas as pd
import re

# ==========================================
# 1. NETTOYAGE ET PARSING DES LOGS DE PROD (SPOOLCOM)
# ==========================================

def clean_line(line):
    """Supprime les résidus de logs de transfert comme """
    return re.sub(r'\\', '', line).strip()

def parse_spoolcom_log(file_content):
    """Parse un log global SPOOLCOM actif (DEV, PRINT, LOC)"""
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
    """Parse le fichier de conf d'origine pour lister ce qui est déclaré"""
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
# 3. INTERFACE DE L'APPLICATION STREAMLIT (AFFICHAGE EN LISTE)
# ==========================================

st.set_page_config(page_title="Tandem Spooler Auditor", layout="wide")

st.title("📋 Audit Spooler HP NonStop")
st.markdown("Analyse complète des écarts et mouvements de configuration (Prod vs Fichier de Conf).")

col1, col2 = st.columns(2)
with col1:
    spool_file = st.file_uploader("1. Importer le log SPOOLCOM (Existant / Prod)", type=["log", "txt"])
with col2:
    conf_file = st.file_uploader("2. Importer le fichier CNFGSPLS (Théorique)", type=["log", "txt"])

if spool_file and conf_file:
    spool_content = spool_file.read().decode("utf-8")
    conf_content = conf_file.read().decode("utf-8")
    
    prod_devs, prod_prints, prod_locs = parse_spoolcom_log(spool_content)
    conf_devs, conf_prints, conf_locs = parse_cnfgspls(conf_content)
    
    st.success("Analyse croisée effectuée ! Les résultats sont listés ci-dessous.")
    
    # =========================================================================
    # BLOC 1 : LES ELEMENTS EXISTANTS MAIS ABSENTS DE LA CONF (A RAJOUTER)
    # =========================================================================
    st.markdown("## ⚠️ PARTIE 1 : Éléments EXISTANTS en Prod mais ABSENTS du CNFGSPLS")
    st.caption("Ces éléments tournent actuellement mais seront perdus au prochain redémarrage propre du spooler.")
    
    # 1. DEV Manquants
    st.markdown("### 🖨️ 1. DEV (Imprimantes) existants non déclarés")
    missing_devs = sorted([d for d in prod_devs if d not in conf_devs])
    if missing_devs:
        df_m_dev = pd.DataFrame([{
            "Device": d, "Processus": prod_devs[d]['proc'], "État Actuel": prod_devs[d]['state']
        } for d in missing_devs])
        st.dataframe(df_m_dev, width="stretch")
    else:
        st.success("Aucun périphérique existant n'est absent de la conf.")
        
    # 2. PRINT Manquants
    st.markdown("### ⚙️ 2. PRINT (Processus d'impression) existants non déclarés")
    missing_prints = sorted([p for p in prod_prints if p not in conf_prints])
    if missing_prints:
        df_m_print = pd.DataFrame([{
            "Processus PRINT": p, "État": prod_prints[p]['state'], "PRI": prod_prints[p]['pri'], "CPU/Backup": prod_prints[p]['cpu_backup']
        } for p in missing_prints])
        st.dataframe(df_m_print, width="stretch")
    else:
        st.success("Aucun processus d'impression existant n'est absent de la conf.")
        
    # 3. LOC Manquantes
    st.markdown("### 📍 3. LOC (Locations) existantes non déclarées")
    missing_locs = sorted([l for l in prod_locs if l not in conf_locs])
    if missing_locs:
        df_m_loc = pd.DataFrame([{
            "Location": l, "Cible Spooler (Prod)": prod_locs[l]
        } for l in missing_locs])
        st.dataframe(df_m_loc, width="stretch")
    else:
        st.success("Aucune location existante n'est absente de la conf.")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # =========================================================================
    # BLOC 2 : LES ELEMENTS DE LA CONF QUI SONT INACTIFS OU ABSENTS (A DEMONTER)
    # =========================================================================
    st.markdown("## 🧹 PARTIE 2 : Éléments CONFIGURÉS mais ABSENTS ou INACTIFS en Prod")
    st.caption("Ces éléments sont déclarés dans le fichier mais n'existent plus ou sont inutilisés sur la machine.")
    
    # 4. DEV Inactifs
    st.markdown("### 💤 4. DEV (Imprimantes) configurés mais inactifs ou supprimés")
    inactive_devs = sorted([d for d in conf_devs if d not in prod_devs or prod_devs[d]['state'].upper() == "OFFLINE"])
    if inactive_devs:
        df_i_dev = pd.DataFrame([{
            "Device": d,
            "Statut en Prod": "❌ Supprimé du Spooler" if d not in prod_devs else "💤 OFFLINE (Inactif)"
        } for d in inactive_devs])
        st.dataframe(df_i_dev, width="stretch")
    else:
        st.success("Tous les devices configurés sont actifs et en ligne.")
        
    # 5. PRINT Inactifs
    st.markdown("### 💤 5. PRINT (Processus) configurés mais non démarrés")
    inactive_prints = sorted([p for p in conf_prints if p not in prod_prints])
    if inactive_prints:
        df_i_print = pd.DataFrame([{
            "Processus PRINT": p, "Statut": "❌ Non démarré / Absent du Spooler"
        } for p in inactive_prints])
        st.dataframe(df_i_print, width="stretch")
    else:
        st.success("Tous les processus d'impression configurés tournent en prod.")
        
    # 6. LOC Inactives
    st.markdown("### 🗑️ 6. LOC (Locations) configurées mais inactives ou envoyées à la poubelle")
    inactive_locs = sorted([l for l in conf_locs if l not in prod_locs or prod_locs[l] == "$NULL.#POUB" or prod_locs[l] not in prod_devs])
    if inactive_locs:
        df_i_loc = pd.DataFrame([{
            "Location": l,
            "Cible théorique (Conf)": conf_locs[l],
            "Raison de l'inactivité": (
                "❌ Supprimée de la Prod" if l not in prod_locs 
                else "🗑️ Redirigée vers la Poubelle ($NULL)" if prod_locs[l] == "$NULL.#POUB"
                else f"⚠️ Pointe vers un device inexistant ({prod_locs[l]})"
            )
        } for l in inactive_locs])
        st.dataframe(df_i_loc, width="stretch")
    else:
        st.success("Toutes les locations configurées sont saines et actives.")
