"""Turn a tariff PDF into plain text the LLM can read."""
import pdfplumber


def extract_pages(pdf_path):
    """Return a list of page strings."""
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def full_text(pdf_path):
    """Return the whole document as one string, with page markers."""
    pages = extract_pages(pdf_path)
    return "\n".join(f"[PAGE {i + 1}]\n{t}" for i, t in enumerate(pages))


if __name__ == "__main__":
    import sys
    print(full_text(sys.argv[1] if len(sys.argv) > 1 else "data/port_tariff.pdf"))
