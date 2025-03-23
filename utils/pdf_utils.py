import requests
import fitz

def download_pdf(url, filepath):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=120, allow_redirects=True)

    if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
        with open(filepath, 'wb') as f:
            f.write(response.content)
    else:
        raise Exception(f"Failed to download PDF, status code: {response.status_code}, URL: {url}")


def extract_pdf_text(filepath):
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    return text
