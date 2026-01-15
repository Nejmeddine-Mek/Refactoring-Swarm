# c.py
from a import func_a

def func_c(z):
    return func_a(z) * 2  # depends on func_a
