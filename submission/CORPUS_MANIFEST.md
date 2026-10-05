# Demonstration corpus manifest

The local demonstration used the following four indexed documents. PDFs, database rows, and vector files are not stored in Git.

| Document | Classification | Authority/status | Local indexed passages |
| --- | --- | --- | ---: |
| SEBI derivatives | Consultation paper / draft circular | SEBI - Draft / Consultation | 110 |
| Shadow banking | Research or financial-stability report | RBI - Not applicable as a binding rule | 375 |
| Zerodha Policies and Procedures | Internal company policy | In force | 56 |
| 2026 SEBI Master Circulars | Master direction | SEBI - In force | 845 |

Total local index size: 1,386 passages.

## Reproduction note

The database currently has no public source URLs recorded for these files. Before submission, either:

1. attach the exact PDFs separately if redistribution is permitted; or
2. add the official RBI, SEBI, and company-policy download URLs to this manifest.

Do not copy the local `media/`, `db.sqlite3`, or `vectorstore/` directories into Git merely to reproduce the demo. The intended workflow is to upload and index approved source files after setup.

Document labels describe how the files were classified in the application. A consultation paper or financial-stability report must not be presented as a binding regulation.
