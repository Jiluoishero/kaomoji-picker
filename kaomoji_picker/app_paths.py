import os
import sys


def runtime_dir(module_file):
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def runtime_file(module_file, filename):
    return os.path.join(runtime_dir(module_file), filename)
