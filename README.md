# MarkItDown REST API

A RESTful API built with FastAPI that exposes the functionality of the [MarkItDown](https://github.com/Intelligenza/MarkItDown) library. This API allows you to convert various file types, URLs, and text formats into Markdown.

## Features

*   Convert local files (`.docx`, `.pptx`, `.pdf`, `.html`, `.csv`, etc.) to Markdown.
*   Convert multiple files at once.
*   Extract and convert files from a `.zip` archive.
*   Convert content from a URL, including YouTube video transcripts.
*   Convert raw text snippets (HTML, CSV, JSON, XML) to Markdown.
*   Optional integration with LLM providers (OpenAI, Gemini, Groq, Claude) for advanced processing.
*   Simple health check and format listing endpoints.

## Requirements

The project is built in Python and uses FastAPI. To install the necessary dependencies, run:

```bash
pip install -r requirements.txt
```

This will install FastAPI, Uvicorn, MarkItDown, and other required libraries.

## Running the API

To run the API server locally, use `uvicorn`:

```bash
uvicorn api_markitdown:app --reload --host 0.0.0.0 --port 8002
```

The API will be available at `http://localhost:8002`.

## API Endpoints

The API returns JSON by default. To download the result as a Markdown file, you can add the query parameter `?download=1` to the relevant endpoints.

---

### Health and Configuration

#### `GET /health`

Returns the operational status of the API.

*   **Response:**
    ```json
    {
      "status": "ok"
    }
    ```

#### `GET /formats`

Lists the file formats and sources supported by the underlying `markitdown` library.

*   **Response:**
    ```json
    {
      "files": [
        "docx", "pptx", "xlsx", "pdf", "html", "csv", "json", "xml",
        "jpg", "jpeg", "png", "tiff", "webp", "mp3", "wav", "m4a", "aac",
        "zip", "epub"
      ],
      "urls": ["http(s)://...", "YouTube URLs"],
      "notes": "Instale 'markitdown[all]' para suporte a OCR, áudio, YouTube, etc."
    }
    ```

#### `POST /config/llm`

Configures an LLM client (e.g., OpenAI, Gemini) for use with MarkItDown. This is an optional feature for advanced text processing.

*   **Request Body:**
    ```json
    {
      "provider": "openai",
      "api_key": "YOUR_API_KEY",
      "model": "gpt-4"
    }
    ```
*   **Example:**
    ```bash
    curl -X POST "http://localhost:8002/config/llm" \
    -H "Content-Type: application/json" \
    -d {
      "provider": "openai",
      "api_key": "sk-...",
      "model": "gpt-4-turbo"
    }}
    ```

---

### Conversion Endpoints

#### `POST /convert/file`

Converts a single uploaded file to Markdown.

*   **Example:**
    ```bash
    curl -X POST "http://localhost:8002/convert/file" \
    -F "file=@/path/to/your/document.docx"
    ```
    To download the result directly:
    ```bash
    curl -X POST "http://localhost:8002/convert/file?download=1" \
    -F "file=@/path/to/your/document.docx" -o "converted.md"
    ```

#### `POST /convert/files`

Converts multiple files in a single request.

*   **Example:**
    ```bash
    curl -X POST "http://localhost:8002/convert/files" \
    -F "files=@/path/to/file1.pdf" \
    -F "files=@/path/to/file2.pptx"
    ```
    To get the output as NDJSON (one JSON object per line):
    ```bash
    curl -X POST "http://localhost:8002/convert/files?as_ndjson=1" \
    -F "files=@/path/to/file1.pdf" \
    -F "files=@/path/to/file2.pptx"
    ```

#### `POST /convert/url`

Converts the content of a URL to Markdown. This works for web pages and YouTube videos.

*   **Request Body:**
    ```json
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
    ```
*   **Example:**
    ```bash
    curl -X POST "http://localhost:8002/convert/url" \
    -H "Content-Type: application/json" \
    -d '{"url": "https://en.wikipedia.org/wiki/Markdown"}'
    ```

#### `POST /convert/text`

Converts a raw string of HTML, CSV, JSON, or XML to Markdown.

*   **Request Body:** (Provide one of the following)
    ```json
    {
      "html": "<h1>Title</h1><p>Some text.</p>"
    }
    ```
*   **Example (HTML):**
    ```bash
    curl -X POST "http://localhost:8002/convert/text" \
    -H "Content-Type: application/json" \
    -d '{"html": "<h1>Hello</h1><p>This is a test.</p>"}'
    ```

#### `POST /convert/zip`

Upload a `.zip` file. The API will extract each file, convert it to Markdown, and return the results as NDJSON.

*   **Example:**
    ```bash
    curl -X POST "http://localhost:8002/convert/zip" \
    -F "file=@/path/to/your/archive.zip"
    ```
    The output will be a stream of JSON objects, one for each file in the archive:
    ```
    {"filename": "file1.docx", "markdown": "..."}
    {"filename": "image.png", "markdown": "..."}
    ```
