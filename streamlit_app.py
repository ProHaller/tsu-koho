import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import hashlib
import gspread
from google.oauth2.service_account import Credentials
from gspread.auth import authorize

# Page config
st.set_page_config(
    page_title="Tsunagaru Analytics Dashboard", page_icon="📊", layout="wide"
)

# Google Sheets setup
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Spreadsheet URL
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1EHKE1qal6Zi-ghjryx5_-vk39anL662yZN09bXBs41Q/edit"

# Add debug flag at the top of the file
DEBUG = False

# Function to load Google Sheets credentials
@st.cache_resource
def get_gsheet_client():
    try:
        credentials = Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        return client
    except FileNotFoundError:
        st.error("❌ credentials.json file not found. Please ensure the file exists in the app directory.")
        return None
    except ValueError as e:
        st.error(f"❌ Invalid credentials format: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Authentication error: {str(e)}")
        return None


# Password protection
def check_password():
    def password_entered():
        if (
            hashlib.sha256(st.session_state["password"].encode()).hexdigest()
            == hashlib.sha256("tsunagaru".encode()).hexdigest()
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Please enter the dashboard password",
            type="password",
            on_change=password_entered,
            key="password",
        )
        return False

    elif not st.session_state["password_correct"]:
        st.text_input(
            "Please enter the dashboard password",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.error("😕 Password incorrect")
        return False
    return True


if check_password():
    # Data loading function
    @st.cache_data(ttl=600)
    def load_data(worksheet_name):
        def debug_print(message):
            if DEBUG:
                st.write(f"🔍 Debug: {message}")

        try:
            client = get_gsheet_client()
            if not client:
                st.warning("⚠️ Unable to initialize Google Sheets client. Check if credentials.json exists and is valid.")
                return pd.DataFrame()

            debug_print(f"Attempting to access spreadsheet: {SPREADSHEET_URL}")
            
            try:
                sheet = client.open_by_url(SPREADSHEET_URL)
            except gspread.exceptions.APIError as e:
                if "PERMISSION_DENIED" in str(e):
                    service_account_email = Credentials.from_service_account_file("credentials.json").service_account_email
                    st.error(f"""❌ Permission denied. Please ensure:
                    1. The service account email ({service_account_email}) has been given access to the spreadsheet
                    2. The spreadsheet has been shared with this email
                    3. The sharing permission is at least "Editor"
                    """)
                else:
                    st.error(f"❌ Failed to open spreadsheet: {str(e)}")
                return pd.DataFrame()
            except Exception as e:
                st.error(f"❌ Failed to open spreadsheet: {str(e)}\nType: {type(e).__name__}")
                return pd.DataFrame()

            debug_print(f"Attempting to access worksheet: {worksheet_name}")
            
            try:
                worksheet = sheet.worksheet(worksheet_name)
            except Exception as e:
                st.error(f"❌ Failed to open worksheet '{worksheet_name}': {str(e)}\nType: {type(e).__name__}")
                return pd.DataFrame()

            debug_print("Attempting to read data from worksheet")
            
            data = worksheet.get_all_records()
            if not data:
                st.info(f"ℹ️ No data found in worksheet '{worksheet_name}'")
                return pd.DataFrame()

            return pd.DataFrame(data)

        except Exception as e:
            st.error(f"❌ Unexpected error loading {worksheet_name} data: {str(e)}\nType: {type(e).__name__}")
            return pd.DataFrame()

    # Load all data
    platforms = ["note", "wantedly", "benchmark", "prtimes_post", "prtimes_daily", "GA4"]
    data = {platform: load_data(platform) for platform in platforms}

    # Dashboard Title
    st.title("Tsunagaru Multi-Platform Analytics Dashboard")
    st.markdown("---")

    # Metrics Overview
    cols = st.columns(len(platforms))

    for col, (platform, df) in zip(cols, data.items()):
        with col:
            st.metric(f"{platform.capitalize()} Posts", len(df) if not df.empty else 0)

    # Platform Tabs
    tabs = st.tabs([p.capitalize() for p in platforms])

    # Note Tab
    with tabs[0]:
        st.header("Note Analytics")

        if not data["note"].empty:
            # Views distribution
            fig_views = px.bar(
                data["note"], x="記事", y="ビュー", title="Article Views Distribution"
            )
            fig_views.update_layout(xaxis_tickangle=-45, height=500)
            st.plotly_chart(fig_views, use_container_width=True)

            # Engagement metrics
            fig_engagement = go.Figure()
            fig_engagement.add_trace(
                go.Bar(
                    name="Comments", x=data["note"]["記事"], y=data["note"]["コメント"]
                )
            )
            fig_engagement.add_trace(
                go.Bar(name="Likes", x=data["note"]["記事"], y=data["note"]["スキ"])
            )
            fig_engagement.update_layout(
                title="Engagement Metrics by Article",
                barmode="group",
                xaxis_tickangle=-45,
                height=500,
            )
            st.plotly_chart(fig_engagement, use_container_width=True)

            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Views", data["note"]["ビュー"].sum())
            with col2:
                st.metric("Total Comments", data["note"]["コメント"].sum())
            with col3:
                st.metric("Total Likes", data["note"]["スキ"].sum())

    # Other platform tabs
    for tab, platform in zip(tabs[1:], platforms[1:]):
        with tab:
            st.header(f"{platform.capitalize()} Analytics")
            if data[platform].empty:
                st.info(f"No data available for {platform} tab")
            else:
                # Show the raw data for now
                st.dataframe(data[platform])

                # Display basic metrics if data is available
                if not data[platform].empty:
                    st.subheader("Summary Statistics")
                    st.write("Column totals:")

                    # Get numeric columns
                    numeric_cols = (
                        data[platform]
                        .select_dtypes(include=["int64", "float64"])
                        .columns
                    )
                    if len(numeric_cols) > 0:
                        totals = data[platform][numeric_cols].sum()
                        st.write(totals)

    # Cross-platform comparison section
    st.markdown("---")
    st.header("Cross-Platform Performance Comparison")

    # Add platform comparison metrics here
    # For example, total engagement across platforms

    # Footer
    st.markdown("---")
    st.markdown(
        "*Dashboard last updated: "
        + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S JST")
        + "*"
    )
