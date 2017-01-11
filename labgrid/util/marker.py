import random
import string


def gen_marker():
    return ''.join(random.choice(string.ascii_uppercase) for i in range(10))
