"""CLI for importing verified SBLGNT book XML into the separate verse table."""

from app.sblgnt import import_sblgnt_books


if __name__ == "__main__":
    print(import_sblgnt_books(persist=True))
