import random
import string


# Remove RID to avoid markers containing substrings like ERROR, FAIL, WARN, INFO or DEBUG
MARKER_POOL = tuple(c for c in string.ascii_uppercase if c not in 'RID')

def gen_marker():
    return ''.join(random.choice(MARKER_POOL) for i in range(10))
