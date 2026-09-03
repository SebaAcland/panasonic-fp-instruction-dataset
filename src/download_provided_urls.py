import urllib.request
import os

URLS = {
    "mn_fp0h_cpu_programming_pid_en.pdf": "https://industry.panasonic.eu/storage/download-files/import/mn_fp0h_cpu_programming_pid_en.pdf",
    "FP-Series_ProgrammingManual.pdf": "http://makkontrol.com/dokumanlar/FP-Series_ProgrammingManual.pdf"
}

output_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(output_dir, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

for filename, url in URLS.items():
    filepath = os.path.join(output_dir, filename)
    print(f"Descargando {filename} desde {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response, open(filepath, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
            print(f"-> Guardado correctamente ({len(data)} bytes).")
    except Exception as e:
        print(f"-> Error descargando {filename}: {e}")
