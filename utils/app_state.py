# utils/app_state.py 
import streamlit as st

class AppState:
    VIEW_TERRITORY = "territory"
    VIEW_DEALER = "dealer"

    @staticmethod
    def init() -> None:
        defaults: dict[str, object] = {
            "df": None,
            "view": AppState.VIEW_TERRITORY,
            "selected_territory": None,
            "selected_dealer": None,
            "debug_mode": False,
            "recent_dealers": [],
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    @staticmethod
    def navigate_to_territory(territory_name: str) -> None:
        st.session_state.view = AppState.VIEW_TERRITORY
        st.session_state.selected_territory = territory_name
        st.session_state.selected_dealer = None

    @staticmethod
    def navigate_to_dealer(dealer_id: str) -> None:
        st.session_state.view = AppState.VIEW_DEALER
        st.session_state.selected_dealer = dealer_id
        AppState.remember_recent_dealer(dealer_id)

    @staticmethod
    def remember_recent_dealer(dealer_id: str) -> None:
        if not dealer_id:
            return
        rec = st.session_state.get("recent_dealers", [])
        if dealer_id not in rec:
            rec.append(dealer_id)
        st.session_state.recent_dealers = rec[-30:]
