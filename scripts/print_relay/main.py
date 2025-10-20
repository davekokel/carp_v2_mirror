import os, tempfile, subprocess
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

TOKEN = os.getenv("PRINT_RELAY_TOKEN", "")
DEFAULT_QUEUE = os.getenv("PRINT_RELAY_QUEUE", "Brother_QL_1110NWB")

app = FastAPI(title="CARP Print Relay")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"])

@app.post("/print")
async def print_pdf(
    pdf: UploadFile,
    queue: str = Form(None),
    media: str = Form("Custom.61x38mm"),
    token: str = Form("")
):
    if not TOKEN or token != TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")
    q = queue or DEFAULT_QUEUE
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="expected PDF")
    try:
        with tempfile.NamedTemporaryFile(prefix="carp_label_", suffix=".pdf", delete=False) as tmp:
            content = await pdf.read()
            tmp.write(content)
            tmp_path = tmp.name
        cmd = ["lp", "-d", q, "-o", f"media={media}", tmp_path]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        return JSONResponse({"ok": True, "queue": q, "media": media, "lp_out": out.strip()})
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=502, detail=f"CUPS error: {e.output.strip()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
