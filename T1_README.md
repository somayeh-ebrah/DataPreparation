
# T1 MRI Preprocessing Pipeline - Installation and Usage Guide

## Overview
This preprocessing pipeline follows the paper specifications for T1 MRI preprocessing:
0. Reorient to RAS orientation using ANTs
1. N4 bias field correction using SimpleITK
2. Resample to isotropic 1×1×1 mm³ voxels through linear interpolation
3. Rigid registration to MNI space brain atlas
4. Brain extraction/skull stripping using HD-BET package

## Installation

### 1. Install Required Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install HD-BET
```bash
pip install HD-BET
```

### 3. Install ANTsPy
```bash
pip install antspyx
```

### 4. Install FSL (for MNI templates)
```bash
# On Ubuntu/Debian:
sudo apt-get install fsl

# Or download from: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation
```

## Usage

### Option 1: Batch a folder with t1_batch_preprocess.py
`t1_batch_preprocess.py` runs the paper pipeline over every NIfTI file in a
directory. Edit the paths in its `if __name__ == "__main__"` block:

```python
# Update the paths in t1_batch_preprocess.py
input_directory = "/path/to/your/nifti/files"
output_directory = "/path/to/output/preprocessed/files"
```

```bash
# Run the preprocessing
python t1_batch_preprocess.py
```

### Option 2: Use the Standalone Pipeline
```python
from t1_pipeline import process_nifti_files

# Process all NIfTI files
process_nifti_files(
    input_dir="/path/to/your/nifti/files",
    output_dir="/path/to/output/preprocessed/files"
)
```

### Option 3: Process Individual Files
```python
from t1_pipeline import paper_preprocessing_pipeline

# Process a single file
success = paper_preprocessing_pipeline(
    nii_path="/path/to/subject.nii.gz",
    output_dir="/path/to/output",
    subject_id="subject_001"
)
```

## Output Files
For each input file, the pipeline generates:
- `{subject_id}_preprocessed.nii.gz`: Final preprocessed brain-extracted image
- `{subject_id}_brain_mask.nii.gz`: Brain mask used for extraction

## Troubleshooting

### MNI Template Not Found
If the MNI template is not found, the pipeline will skip registration and use the resampled image directly. To fix this:
1. Install FSL properly
2. Or download MNI152_T1_1mm.nii.gz manually and update the path in `find_mni_template()`

### HD-BET Installation Issues
If HD-BET fails to install:
```bash
# Try installing with conda
conda install -c conda-forge hd-bet

# Or install from source
pip install git+https://github.com/MIC-DKFZ/HD-BET.git
```

### Memory Issues
For large datasets, consider processing files in batches or increasing system memory.

## Pipeline Steps Explained

0. **ANTS Reorientation**: Reorients images to RAS orientation using ANTs for consistency
1. **N4 Bias Field Correction**: Corrects intensity non-uniformity using SimpleITK's implementation
2. **Isotropic Resampling**: Resamples to 1×1×1 mm³ voxels using linear interpolation
3. **MNI Registration**: Performs rigid registration to MNI space for standardization
4. **Brain Extraction**: Uses HD-BET for robust skull stripping

## Notes
- The pipeline creates temporary files during processing and cleans them up automatically
- All intermediate steps are logged for debugging
- The pipeline is designed to be robust and continue processing even if individual steps fail
