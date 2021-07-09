import multiprocessing

from .main import main

multiprocessing.freeze_support()  # For bundle Apps with PyInstaller
main()
