"""Where Should the Next Teacher Go? Dash app.

Run locally:  python dash_app.py   (then open http://localhost:8050, add ?demo=1 for the demo path)
Production:   gunicorn dash_app:server --bind 0.0.0.0:$PORT
Uses the same processed tables and calculations as streamlit_app.py.
"""
import os

from dash import Dash

from dashapp.layout import layout

app = Dash(__name__, title="Where Should the Next Teacher Go?", suppress_callback_exceptions=True,
           update_title=None)
app.layout = layout
import dashapp.callbacks  # noqa: E402,F401  (registers callbacks)

server = app.server

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)), debug=os.environ.get("DASH_DEBUG") == "1")
