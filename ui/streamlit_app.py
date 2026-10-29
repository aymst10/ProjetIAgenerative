"""Interface Streamlit. Elle parle à l'API, elle ne crée pas de ticket seule."""

from __future__ import annotations

import httpx
import streamlit as st

from maintidoc.config import get_settings

EQUIPMENT = ["", "POMPE-A", "POMPE-B", "POMPE-C", "COMP-A", "COMP-B"]


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_settings().api_url, timeout=60.0)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def main() -> None:
    st.set_page_config(page_title="MaintiDoc", layout="centered")
    st.title("MaintiDoc")
    st.caption(
        "Aide documentaire pour la maintenance. Aucun équipement n'est piloté, "
        "aucun diagnostic n'est garanti."
    )
    if "token" not in st.session_state:
        st.session_state.token = None
    if "last" not in st.session_state:
        st.session_state.last = None

    with st.sidebar:
        st.subheader("Comptes fictifs")
        st.text("alice / alice-demo\nbob / bob-demo\ncarol / carol-demo\ndiana / diana-demo")
        if st.session_state.token and st.button("Quitter"):
            st.session_state.token = None
            st.session_state.last = None
            st.rerun()

    if not st.session_state.token:
        with st.form("login"):
            user_id = st.text_input("Identifiant", value="alice")
            password = st.text_input("Mot de passe", value="alice-demo", type="password")
            submitted = st.form_submit_button("Entrer")
        if submitted:
            response = _client().post("/auth/login", json={"user_id": user_id, "password": password})
            if response.status_code != 200:
                st.error("Accès refusé.")
                return
            payload = response.json()
            st.session_state.token = payload["token"]
            st.session_state.display_name = payload["display_name"]
            st.rerun()
        return

    st.write(f"Session : {st.session_state.get('display_name', '')}")
    with st.form("demande"):
        question = st.text_area("Question", height=120)
        equipment_id = st.selectbox("Équipement", EQUIPMENT)
        photo = st.file_uploader("Photographie", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Interroger", type="primary")
    if submitted:
        data = {"question": question, "equipment_id": equipment_id}
        files = None
        if photo is not None:
            files = {"image": (photo.name, photo.getvalue(), photo.type or "application/octet-stream")}
        response = _client().post("/ask", data=data, files=files, headers=_auth())
        if response.status_code == 429:
            st.warning("Quota journalier atteint.")
            return
        if response.status_code >= 400:
            st.error("La demande a été refusée.")
            return
        st.session_state.last = response.json()

    last = st.session_state.last
    if not last:
        return
    output = last["output"]
    st.subheader(output["status"])
    st.write(output["answer"])
    if output.get("clarification_question"):
        st.info(output["clarification_question"])
    if output.get("uncertainties"):
        st.write("Incertitudes")
        for item in output["uncertainties"]:
            st.write(f"- {item}")
    if output.get("citations"):
        st.write("Citations")
        for citation in output["citations"]:
            st.write(
                f"- {citation['document_id']}, page {citation['page']}, élément {citation['element_id']}"
            )
    if last.get("tool_trace"):
        st.write("Outils")
        for trace in last["tool_trace"]:
            st.write(f"- {trace['tool']} ({trace['equipment_id']})")
    action = output.get("proposed_action")
    if output["status"] == "awaiting_approval" and action:
        st.divider()
        st.subheader("Brouillon de ticket")
        title = st.text_input("Titre", value=action["title"])
        description = st.text_area("Description", value=action["description"], height=180)
        st.caption("Toute modification du texte impose une nouvelle validation : l'approbation sera refusée.")
        col1, col2 = st.columns(2)
        if col1.button("Approuver et créer"):
            response = _client().post(
                f"/runs/{last['run_id']}/decision",
                headers=_auth(),
                json={"approved": True, "title": title, "description": description},
            )
            if response.status_code == 200:
                st.session_state.last = response.json()
                st.rerun()
            st.error("Création refusée.")
        if col2.button("Refuser"):
            response = _client().post(
                f"/runs/{last['run_id']}/decision",
                headers=_auth(),
                json={"approved": False, "title": action["title"], "description": action["description"]},
            )
            if response.status_code == 200:
                st.session_state.last = response.json()
                st.rerun()
    if last.get("ticket_id"):
        st.success(f"Ticket créé : {last['ticket_id']}")


if __name__ == "__main__":
    main()
