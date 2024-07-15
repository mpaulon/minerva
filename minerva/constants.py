import os

if os.name == "nt":
    PAGEFIND_BINARY = "pagefind_extended.exe"
    PAGEFIND_URL = "https://github.com/CloudCannon/pagefind/releases/download/v1.1.0/pagefind_extended-v1.1.0-x86_64-pc-windows-msvc.tar.gz"
else:
    PAGEFIND_BINARY = "pagefind_extended"
    PAGEFIND_URL = "https://github.com/CloudCannon/pagefind/releases/download/v1.1.0/pagefind_extended-v1.1.0-x86_64-unknown-linux-musl.tar.gz"