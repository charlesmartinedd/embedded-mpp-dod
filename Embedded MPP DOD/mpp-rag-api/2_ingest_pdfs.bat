@echo off
echo ========================================
echo MPP RAG - Ingesting PDFs
echo ========================================
echo.
echo This will process all PDFs and create the vector database.
echo This only needs to run ONCE (or when PDFs are updated).
echo.
echo Starting ingestion...
echo.

python ingest_pdfs.py

echo.
echo Ingestion complete!
echo Next step: Run 3_start_server.bat
echo.
pause
