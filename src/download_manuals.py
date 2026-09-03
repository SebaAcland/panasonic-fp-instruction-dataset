import urllib.request
import os

MANUALS = {
    "ARCT1F313E-18_FP_Series_Programming_Manual.pdf": "https://industrial.panasonic.com/content/data/SC/PDF/ARCT1F313E-18.pdf",
    "WUME-FP0HPGR_FP0H_Programming_Manual.pdf": "https://industrial.panasonic.com/content/data/SC/PDF/WUME-FP0HPGR.pdf"
}

output_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(output_dir, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

for filename, url in MANUALS.items():
    filepath = os.path.join(output_dir, filename)
    print(f"Descargando {filename} desde {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response, open(filepath, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
            print(f"-> Guardado correctamente ({len(data)} bytes).")
    except Exception as e:
        print(f"-> Error descargando {filename}: {e}")
