import os
import tempfile

def atomic_replace(filename, data):
    try:
        with tempfile.NamedTemporaryFile(
                mode='wb',
                dir=os.path.dirname(filename),
                delete=False) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(f.name, filename)
    finally:
        try:
            os.unlink(f.name)
        except FileNotFoundError:
            pass
