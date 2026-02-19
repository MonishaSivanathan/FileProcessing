import io
import tempfile
import docx2txt
from PyPDF2 import PdfReader

ALLOWED_EXTENSIONS = {'doc', 'docx', 'pdf'}


def validate_file(file_storage):
    filename = file_storage.filename
    if not filename or '.' not in filename:
        raise ValueError('Filename invalid')

    ext = filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f'Extension {ext} not allowed')

    data = file_storage.stream.read()
    if not data or len(data) == 0:
        raise ValueError('File is empty')

    # PDF validation
    if ext == 'pdf':
        try:
            reader = PdfReader(io.BytesIO(data))

            if reader.is_encrypted:
                raise ValueError('PDF is encrypted')

            # no pages
            if len(reader.pages) == 0:
                raise ValueError('PDF has no pages')

            # no readable content
            has_text = False
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    has_text = True
                    break

            if not has_text:
                raise ValueError('PDF has no readable content')

        except ValueError:
            raise
        except Exception:
            raise ValueError('PDF invalid or corrupted')

    # DOC / DOCX validation
    if ext in ('doc', 'docx'):
        try:
            with tempfile.NamedTemporaryFile(delete=True, suffix=f'.{ext}') as tmp:
                tmp.write(data)
                tmp.flush()

                text = docx2txt.process(tmp.name)
                if not text or not text.strip():
                    raise ValueError('DOC/DOCX has no readable content')

        except ValueError:
            raise
        except Exception:
            raise ValueError('DOC/DOCX invalid or corrupted')

    # reset stream for further processing
    file_storage.stream.seek(0)