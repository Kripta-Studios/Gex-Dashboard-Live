# neural/run_preprocess.py
import multiprocessing

# 1. freeze_support() must be called immediately at the top level
# on Windows to support PyInstaller / frozen executables, and it's 
# good practice for 'spawn' method in general before any other imports.
multiprocessing.freeze_support()

if __name__ == "__main__":
    import sys
    import os
    
    # 2. Add the neural/ directory to sys.path so we can import rl.preprocess
    # even when running this script directly.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    # 3. Import the main function from the package module. Note that
    # the heavy torch loads are still prevented by the lazy __init__.py.
    from rl.preprocess import main
    main()
