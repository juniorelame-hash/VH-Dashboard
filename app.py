"""
app.py - Cellule Dashboard (Streamlit)
Fonctionnalités :
- Gestion minimale des membres
- Enregistrement de présences (attendance)
- Gestion des demandes de prière (ajout / marquer comme répondu)
- Statistiques et graphiques interactifs (période, filtres)
- Export CSV
Dépendances : streamlit, pandas, altair
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import altair as alt
import io

DB_PATH = "cellule_dashboard.db"

# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            role TEXT,
            joined DATE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER,
            attend_date DATE,
            present INTEGER,
            note TEXT,
            FOREIGN KEY(member_id) REFERENCES members(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS prayers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester TEXT,
            content TEXT,
            created DATE,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def run_query(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

# ---------- Core actions ----------
def add_member(name, phone, email, role):
    execute(
        "INSERT INTO members (name, phone, email, role, joined) VALUES (?, ?, ?, ?, ?)",
        (name, phone, email, role, date.today().isoformat())
    )

def add_attendance(member_id, attend_date, present, note):
    execute(
        "INSERT INTO attendance (member_id, attend_date, present, note) VALUES (?, ?, ?, ?)",
        (member_id, attend_date, 1 if present else 0, note)
    )

def add_prayer(requester, content):
    execute(
        "INSERT INTO prayers (requester, content, created, status) VALUES (?, ?, ?, ?)",
        (requester, content, date.today().isoformat(), "open")
    )

def update_prayer_status(prayer_id, status):
    execute("UPDATE prayers SET status = ? WHERE id = ?", (status, prayer_id))


# ---------- Utils ----------
def get_members_df():
    return run_query("SELECT * FROM members")

def get_attendance_df():
    return run_query("SELECT a.id, a.member_id, m.name as member_name, a.attend_date, a.present, a.note FROM attendance a LEFT JOIN members m ON a.member_id = m.id")

def get_prayers_df():
    return run_query("SELECT * FROM prayers ORDER BY created DESC")

def csv_from_df(df):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer

# ---------- UI ----------
st.set_page_config(page_title="Cellule Dashboard — Saint-Jérôme", layout="wide")
init_db()

st.title("📊 Cellule Dashboard — Saint-Jérôme")
st.markdown("Outil léger pour suivre membres, présences et demandes de prière.")

# Sidebar navigation
page = st.sidebar.selectbox("Section", ["Vue d'ensemble", "Membres", "Présences", "Prière", "Paramètres / Export"])

# ---------------- VUE D'ENSEMBLE ----------------
if page == "Vue d'ensemble":
    st.header("Vue d'ensemble")
    members = get_members_df()
    attendance = get_attendance_df()
    prayers = get_prayers_df()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Membres enregistrés", len(members))
    col2.metric("Demandes de prière (ouvertes)", len(prayers[prayers['status']=='open']))
    # average attendance over last 30 days
    if len(attendance) > 0:
        try:
            attendance['attend_date'] = pd.to_datetime(attendance['attend_date'])
            last_30 = attendance[attendance['attend_date'] >= (pd.Timestamp.today() - pd.Timedelta(days=30))]
            if len(last_30) > 0:
                avg_att = last_30['present'].mean() * 100
                col3.metric("Taux de présence (30j)", f"{avg_att:.0f}%")
            else:
                col3.metric("Taux de présence (30j)", "N/A")
        except Exception:
            col3.metric("Taux de présence (30j)", "N/A")
    else:
        col3.metric("Taux de présence (30j)", "N/A")
    col4.metric("Dernière mise à jour", datetime.now().strftime("%Y-%m-%d %H:%M"))

    st.markdown("---")
    st.subheader("Présences — graphique")
    # Attendance chart: présences par date
    if len(attendance) > 0:
        attendance['attend_date'] = pd.to_datetime(attendance['attend_date']).dt.date
        agg = attendance.groupby('attend_date')['present'].mean().reset_index()
        agg['taux'] = agg['present'] * 100
        chart = alt.Chart(agg).mark_line(point=True).encode(
            x=alt.X("attend_date:T", title="Date"),
            y=alt.Y("taux:Q", title="Taux de présence (%)")
        ).properties(width=800, height=350)
        st.altair_chart(chart)
    else:
        st.info("Aucune donnée de présence pour le moment.")

    st.markdown("---")
    st.subheader("Demandes de prière récentes")
    st.table(prayers.head(10))

# ---------------- MEMBRES ----------------
elif page == "Membres":
    st.header("Membres")
    st.subheader("Ajouter un membre")
    with st.form("add_member_form"):
        name = st.text_input("Nom complet")
        phone = st.text_input("Téléphone (optionnel)")
        email = st.text_input("Email (optionnel)")
        role = st.selectbox("Rôle", ["Membre", "Leader", "Serviteur", "Jeunesse", "Visiteur"])
        submitted = st.form_submit_button("Ajouter")
        if submitted:
            if not name:
                st.warning("Le nom est requis.")
            else:
                add_member(name, phone, email, role)
                st.success(f"Membre '{name}' ajouté.")
    st.markdown("---")
    st.subheader("Liste des membres")
    members = get_members_df()
    if len(members) > 0:
        st.dataframe(members)
        csv_buf = csv_from_df(members)
        csv_data = csv_buf.getvalue()
        st.download_button(    label="Exporter membres CSV",data=csv_data,file_name="membres.csv", mime="text/csv")
    else:
        st.info("Aucun membre pour l'instant.")

# ---------------- PRÉSENCES ----------------
elif page == "Présences":
    st.header("Présences / Attendance")
    members = get_members_df()
    if len(members) == 0:
        st.info("Ajoute des membres avant d'enregistrer des présences.")
    else:
        st.subheader("Enregistrer une présence")
        with st.form("attendance_form"):
            member_map = {f"{r['id']} - {r['name']}": r['id'] for _, r in members.iterrows()}
            member_choice = st.selectbox("Membre", list(member_map.keys()))
            present = st.checkbox("Présent ?", value=True)
            attend_date = st.date_input("Date", value=date.today())
            note = st.text_input("Note (optionnel)")
            submit_att = st.form_submit_button("Enregistrer")
            if submit_att:
                add_attendance(member_map[member_choice], attend_date.isoformat(), present, note)
                st.success("Présence enregistrée.")
        st.markdown("---")
        st.subheader("Historique des présences")
        attendance = get_attendance_df()
        if len(attendance) > 0:
            attendance['attend_date'] = pd.to_datetime(attendance['attend_date'])
            # filtre date range
            min_date = attendance['attend_date'].min().date()
            max_date = attendance['attend_date'].max().date()
            dr = st.date_input("Filtrer - plage de dates", value=(min_date, max_date))
            mask = (attendance['attend_date'].dt.date >= dr[0]) & (attendance['attend_date'].dt.date <= dr[1])
            st.dataframe(attendance[mask].sort_values(by='attend_date', ascending=False))
            csv_buf = csv_from_df(attendance[mask])
            st.download_button("Exporter présences CSV", csv_buf, file_name="presences.csv", mime="text/csv")
        else:
            st.info("Aucune présence enregistrée.")

# ---------------- PRIÈRE ----------------
elif page == "Prière":
    st.header("Demandes de prière")
    st.subheader("Soumettre une demande")
    with st.form("prayer_form"):
        requester = st.text_input("Nom du demandeur (ou 'Anonyme')", value="Anonyme")
        content = st.text_area("Contenu / besoin de prière")
        sub = st.form_submit_button("Soumettre")
        if sub:
            if not content:
                st.warning("La demande doit contenir un texte.")
            else:
                add_prayer(requester, content)
                st.success("Demande de prière ajoutée.")

    st.markdown("---")
    st.subheader("Liste des prières")
    prayers = get_prayers_df()
    if len(prayers) > 0:
        # affichage avec actions
        for _, row in prayers.iterrows():
            with st.expander(f"{row['requester']} — {row['created']} — status: {row['status']}"):
                st.write(row['content'])
                cols = st.columns([1,1,6])
                if cols[0].button(f"Marquer comme 'répondu' (id {row['id']})"):
                    update_prayer_status(row['id'], 'answered')
                    st.experimental_rerun()
                if cols[1].button(f"Marquer 'en prière' (id {row['id']})"):
                    update_prayer_status(row['id'], 'open')
                    st.experimental_rerun()
    else:
        st.info("Aucune demande de prière pour l'instant.")

# ---------------- PARAMÈTRES / EXPORT ----------------
elif page == "Paramètres / Export":
    st.header("Paramètres et export")
    st.subheader("Export complet des données")
    members = get_members_df()
    attendance = get_attendance_df()
    prayers = get_prayers_df()

    if st.button("Exporter tout en ZIP (CSV)"):
        # crée un zip en mémoire
        import zipfile, tempfile, os
        temp_buffer = io.BytesIO()
        with zipfile.ZipFile(temp_buffer, "w") as z:
            z.writestr("membres.csv", members.to_csv(index=False))
            z.writestr("presences.csv", attendance.to_csv(index=False))
            z.writestr("prayers.csv", prayers.to_csv(index=False))
        temp_buffer.seek(0)
        st.download_button("Télécharger ZIP", temp_buffer, file_name="cellule_data.zip", mime="application/zip")

    st.markdown("---")
    st.subheader("Maintenance")
    if st.button("Réinitialiser la base (SUPPRIME TOUT)"):
        confirm = st.text_input("Tape 'CONFIRMER' pour valider réinitialisation")
        if confirm.strip().upper() == "CONFIRMER":
            execute("DROP TABLE IF EXISTS attendance")
            execute("DROP TABLE IF EXISTS prayers")
            execute("DROP TABLE IF EXISTS members")
            init_db()
            st.success("Base réinitialisée.")
        else:
            st.warning("Action non confirmée.")
