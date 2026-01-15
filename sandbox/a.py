# a.py
import b

def func_a(x):
    # intentional bug: wrong addition
    return x + 1  # should be integer addition

def unused_function():
    print("This is unused")
