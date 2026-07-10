"""The `livemeta` command-line front end.

A third thin front end over the shared pipeline core, alongside the FastAPI web
app and the MCP server. Every subcommand drives the same `livemeta.core`
functions the other two use, so the three cannot diverge. See `app.py` for the
argparse surface and `render.py` for the pure text renderers.
"""
