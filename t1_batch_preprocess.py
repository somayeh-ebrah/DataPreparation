
#!/usr/bin/env python3
"""
Simple script to process all NIfTI files in a directory using the preprocessing pipeline.
This is an alternative to the subject-specific processing in t1_adni_preprocess.py
"""

from pathlib import Path
from t1_pipeline import paper_preprocessing_pipeline

def process_all_nifti_files(input_dir: str, output_dir: str):
    """
    Process all NIfTI files in the input directory.
    
    Args:
        input_dir: Directory containing NIfTI files
        output_dir: Directory to save preprocessed files
    """
    input_path = Path(input_dir)
    nifti_files = list(input_path.glob("**/*.nii.gz"))
    
    print(f"Found {len(nifti_files)} NIfTI files to process")
    
    success_count = 0
    for nifti_file in nifti_files:
        subject_id = nifti_file.stem.replace('.nii', '')
        print(f"Processing: {subject_id}")
        
        if paper_preprocessing_pipeline(str(nifti_file), output_dir, subject_id):
            success_count += 1
            print(f"✓ Successfully processed {subject_id}")
        else:
            print(f"✗ Failed to process {subject_id}")
    
    print(f"\nProcessing complete. {success_count}/{len(nifti_files)} files processed successfully")

if __name__ == "__main__":
    # === CONFIG: edit these paths to match your setup ===
    INPUT_DIRECTORY = "/path/to/input/converted_nifti"
    OUTPUT_DIRECTORY = "/path/to/output/preprocessed_subjects"

    process_all_nifti_files(INPUT_DIRECTORY, OUTPUT_DIRECTORY)

