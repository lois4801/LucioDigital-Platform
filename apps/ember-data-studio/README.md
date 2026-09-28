# EMBER 3D Data Studio — V6

Luxury orange-and-black interactive analytics prototype. Source: `index.html`.

## Run locally
Open `index.html` in a desktop browser. A network connection is needed to load third-party visualization and Excel libraries.

## Features
- Import multiple Excel/CSV workbooks and worksheets (up to 20 files per batch).
- Profile and clean datasets, suggest possible joins, compare cross-file discrepancies.
- Ask questions to produce aggregations, charts, missing-record tables and supported models.
- Interactive 3D visualizations and exportable analysis evidence.
- Local Ollama is the default generative model; an OpenAI-compatible cloud API is optional.

## Ollama setup
Install Ollama, run `ollama pull llama3.1`, then ensure Ollama is running. In EMBER, select Local Ollama and test the connection. Browser-origin restrictions may require configuring Ollama allowed origins or serving this application locally. Cloud API calls may require a secure backend proxy.

## Security and limitations
This is a browser-based prototype, not a production-ready multi-tenant service. Never commit credentials, customer datasets or sensitive exports. The configured model provider may receive the selected evidence summary and optional sampled rows. Validate AI suggestions against your actual data; a suggested join or cause is not a confirmed finding.

This module is isolated under `apps/ember-data-studio/` and does not replace Lucio platform code.
