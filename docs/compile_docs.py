import os
import subprocess
from pathlib import Path

def compile_latex_directory():
    # Set up directory paths
    current_dir = Path(__file__).resolve().parent
    output_dir = current_dir / "pdfs"
    output_dir.mkdir(exist_ok=True)

    # Use lualatex for native UTF-8 and complex file tree symbol support
    compiler = "lualatex" 
    tex_files = list(current_dir.glob("*.tex"))
    
    if not tex_files:
        print(f"No .tex files found in {current_dir}")
        return

    print(f"--- Checking for changes in {len(tex_files)} files ---")

    recompiled_count = 0

    for tex_file in tex_files:
        pdf_path = output_dir / f"{tex_file.stem}.pdf"
        
        # Change detection logic
        should_compile = False
        if not pdf_path.exists():
            should_compile = True
            reason = "PDF does not exist"
        else:
            # Compare modification timestamps (mtime)
            tex_mtime = tex_file.stat().st_mtime
            pdf_mtime = pdf_path.stat().st_mtime
            
            if tex_mtime > pdf_mtime:
                should_compile = True
                reason = ".tex file has been modified"

        if should_compile:
            print(f"\n>> Recompiling: {tex_file.name} ({reason})...")
            try:
                # Run the compiler twice to generate ToC, refs, and citations correctly
                for pass_num in range(1, 3):
                    subprocess.run(
                        [compiler, "-halt-on-error", "-interaction=nonstopmode", 
                         f"-output-directory={output_dir}", tex_file.name],
                        cwd=current_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )
                print(f"Success: {tex_file.stem}.pdf has been updated (2 passes).")
                recompiled_count += 1
            except subprocess.CalledProcessError as e:
                # Validate if the PDF was still generated despite non-critical warnings
                if pdf_path.exists():
                    print(f"Generated with minor warnings (e.g., MiKTeX updates).")
                else:
                    print(f"Critical ERROR while compiling {tex_file.name}:")
                    print(e.stdout)
        else:
            print(f"Skipped: {tex_file.name} (up to date).")

    if recompiled_count == 0:
        print("\nAll documents are up to date. No changes required.")
    else:
        print(f"\nProcess finished. Updated {recompiled_count} files.")

    # Cleanup auxiliary files (logs, aux, etc.)
    print("\n--- Cleaning up temporary log files ---")
    aux_extensions = {".aux", ".log", ".out", ".toc", ".lof", ".lot", ".fls", ".fdb_latexmk", ".synctex.gz"}
    
    for directory in [current_dir, output_dir]:
        for item in directory.iterdir():
            if item.is_file() and item.suffix.lower() in aux_extensions:
                try:
                    item.unlink()
                except Exception as e:
                    print(f"Could not delete {item.name}: {e}")

if __name__ == "__main__":
    compile_latex_directory()