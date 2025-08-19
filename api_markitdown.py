""" API RESTful que expõe (quase) todas as capacidades do Microsoft MarkItDown.

Framework: FastAPI

Execução local: uvicorn api_markitdown:app --reload --port 8002

Requisitos: ver requirements no final do arquivo


Observações:

1. O MarkItDown aceita caminhos de arquivos, URLs (incl. YouTube) e arquivos ZIP.


2. Para imagens e PDFs que precisem de OCR, instale a extra extra [all] do pacote.


3. Integração opcional com LLM (ex.: OpenAI) via API (endpoint /config/llm).


4. Endpoints retornam JSON por padrão (markdown + metadados). Para baixar como .md, use ?download=1.
"""
from __future__ import annotations

import io
import os
import tempfile
from typing import List, Optional, Literal

import litellm
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Body
from pydantic import BaseModel, AnyHttpUrl

# --- MarkItDown --------------------------------------------------------------

try:
    from markitdown import MarkItDown
except Exception as e:
    raise RuntimeError(
        "markitdown não está instalado. Execute: pip install 'markitdown[all]'"
        f"Erro: {e}"
    )

# --- LLM opcional ------------------------------------------------------------

# Instância global do conversor. Será configurada via API.
md = MarkItDown()


# --- FastAPI -----------------------------------------------------------------

app = FastAPI(
    title="MarkItDown REST API",
    description=(
        "Converta arquivos, URLs, YouTube e ZIPs para Markdown com o MarkItDown.\n\n"
        "Retorno padrão: JSON {markdown, bytes, metadata}. Acrescente ?download=1 para baixar .md."
    ),
    version="1.0.0",
)

# ----------------------------------------------------------------------------
# Modelos de entrada/saída
# ----------------------------------------------------------------------------

class LlmConfigIn(BaseModel):
    provider: Literal["openai", "gemini", "groq", "claude"] = "openai"
    api_key: str
    model: str

class ConvertUrlIn(BaseModel):
    url: AnyHttpUrl

class ConvertTextIn(BaseModel):
    html: Optional[str] = None
    csv: Optional[str] = None
    json_text: Optional[str] = None
    xml: Optional[str] = None

class MarkdownOut(BaseModel):
    markdown: str
    source: Optional[str] = None
    filename: Optional[str] = None
    bytes: Optional[int] = None
    content_type: Optional[str] = None

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _convert_to_markdown_from_path(path: str) -> MarkdownOut:
    result = md.convert(path)
    text = getattr(result, "text_content", None) or str(result)
    # Metadados best-effort
    size = os.path.getsize(path) if os.path.exists(path) else None
    return MarkdownOut(
        markdown=text,
        source="file",
        filename=os.path.basename(path),
        bytes=size,
        content_type=None,
    )

def _save_upload_to_temp(upload: UploadFile) -> str:
    suffix = f"_{upload.filename}" if upload.filename else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        data = upload.file.read()
        tmp.write(data)
        tmp.flush()
        return tmp.name

# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------

class LiteLLMClient:
    def __init__(self, api_key, model, provider):
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.model_name = self.model

        if self.provider == "gemini":
            self.model_name = f"gemini/{self.model}"
        elif self.provider == "groq":
            self.model_name = f"groq/{self.model}"

    def chat(self):
        return self

    def completions(self):
        return self

    def create(self, *args, **kwargs):
        kwargs['model'] = self.model_name
        kwargs['messages'] = kwargs.get('messages')
        kwargs['api_key'] = self.api_key
        return litellm.completion(*args, **kwargs)

@app.post("/config/llm")
def configure_llm(config: LlmConfigIn):
    """Configura o cliente LLM para o MarkItDown."""
    try:
        global md
        md.llm_client = LiteLLMClient(api_key=config.api_key, model=config.model, provider=config.provider)
        md.llm_model = md.llm_client.model_name
        return {"status": "ok", "message": f"LLM provider '{config.provider}' configured."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to configure LLM: {e}")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/formats")
def formats():
    """Lista de formatos tipicamente suportados pelo MarkItDown."""
    return {
        "files": [
            "docx", "pptx", "xlsx", "pdf", "html", "csv", "json", "xml",
            "jpg", "jpeg", "png", "tiff", "webp", "mp3", "wav", "m4a", "aac",
            "zip", "epub"
        ],
        "urls": ["http(s)://...", "YouTube URLs"],
        "notes": "Instale 'markitdown[all]' para suporte a OCR, áudio, YouTube, etc."
    }

@app.post("/convert/file", response_model=MarkdownOut)
async def convert_file(
    file: UploadFile = File(...),
    download: bool = Query(False, description="Se true, baixa um .md"),
):
    try:
        temp_path = _save_upload_to_temp(file)
        out = _convert_to_markdown_from_path(temp_path)
        if download:
            # Salva em .md temporário para devolver como arquivo
            md_path = tempfile.mktemp(suffix=".md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(out.markdown)
            return FileResponse(
                md_path,
                media_type="text/markdown",
                filename=(file.filename or "output") + ".md"
            )
        return JSONResponse(out.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass

@app.post("/convert/files")
async def convert_multiple_files(
    files: List[UploadFile] = File(...),
    as_ndjson: bool = Query(False, description="Se true, retorna NDJSON (1 linha por arquivo)."),
):
    results: List[MarkdownOut] = []
    lines: List[str] = []
    for f in files:
        temp_path = _save_upload_to_temp(f)
        try:
            out = _convert_to_markdown_from_path(temp_path)
            results.append(out)
            if as_ndjson:
                import json
                lines.append(json.dumps(out.model_dump(), ensure_ascii=False))
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    if as_ndjson:
        payload = "\n".join(lines)
        return PlainTextResponse(payload, media_type="application/x-ndjson")
    return {"items": [r.model_dump() for r in results]}

@app.post("/convert/url", response_model=MarkdownOut)
async def convert_url(
    request: ConvertUrlIn,
    download: bool = Query(False),
):
    try:
        result = md.convert(request.url)
        text = getattr(result, "text_content", None) or str(result)
        out = MarkdownOut(
            markdown=text,
            source=str(request.url),
            filename=None,
            bytes=None,
            content_type=None,
        )
        if download:
            md_path = tempfile.mktemp(suffix="_url.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(out.markdown)
            return FileResponse(md_path, media_type="text/markdown", filename="converted.md")
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/convert/text", response_model=MarkdownOut)
async def convert_raw_text(payload: ConvertTextIn):
    """Converte strings cruas de HTML/CSV/JSON/XML em Markdown.
    Obs.: o MarkItDown opera nativamente sobre arquivos/URLs; aqui salvamos
    o conteúdo temporariamente para obter conversão consistente.
    """
    if not any([payload.html, payload.csv, payload.json_text, payload.xml]):
        raise HTTPException(400, detail="Envie ao menos um dos campos: html, csv, json_text ou xml")

    try:
        if payload.html is not None:
            suffix = ".html"
            content = payload.html.encode("utf-8")
        elif payload.csv is not None:
            suffix = ".csv"
            content = payload.csv.encode("utf-8")
        elif payload.json_text is not None:
            suffix = ".json"
            content = payload.json_text.encode("utf-8")
        else:
            suffix = ".xml"
            content = payload.xml.encode("utf-8")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp.flush()
            temp_path = tmp.name

        out = _convert_to_markdown_from_path(temp_path)
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass

@app.post("/convert/zip")
async def convert_zip(file: UploadFile = File(...)):
    """Recebe um .zip e converte cada arquivo interno em Markdown, retornando NDJSON.
    Cada linha é um objeto com {filename, markdown}.
    """
    import zipfile, json

    temp_zip = _save_upload_to_temp(file)
    lines: List[str] = []
    try:
        with zipfile.ZipFile(temp_zip, 'r') as z:
            names = [n for n in z.namelist() if not n.endswith('/')]  # ignora pastas
            for name in names:
                with z.open(name) as f:
                    # Salva cada entrada como arquivo temporário e converte
                    suffix = os.path.splitext(name)[1] or ""
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(f.read())
                        tmp.flush()
                        path = tmp.name
                    try:
                        out = _convert_to_markdown_from_path(path)
                        lines.append(json.dumps({
                            "filename": name,
                            "markdown": out.markdown,
                        }, ensure_ascii=False))
                    finally:
                        try:
                            os.unlink(path)
                        except Exception:
                            pass
        payload = "\n".join(lines)
        return PlainTextResponse(payload, media_type="application/x-ndjson")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            if os.path.exists(temp_zip):
                os.unlink(temp_zip)
        except Exception:
            pass

# ----------------------------------------------------------------------------
# Execução local (opcional)
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_markitdown:app", host="0.0.0.0", port=8002, reload=True)
