"""End-to-end resting-state fMRI preprocessing for a single DICOM subject.

Converts DICOM -> NIfTI, then runs slice-timing correction, motion correction,
brain extraction, smoothing, intensity normalization, ICA denoising, and
registration to standard space using the helpers in ``fmri_utils``.
"""

import glob
import os

import dicom2nifti
import nibabel as nib

from fmri_utils import *

# === CONFIG: edit these for your setup ===
# Prepend a local ANTs install to PATH (leave as-is if ANTs is already on PATH).
ANTS_BIN = "/path/to/ANTs/install/bin"
ROOT_DIR = "data/subject_dicom_folder"        # folder containing the subject's DICOMs
OUTPUT_ROOT = "./outputs/temp_preprocessed"   # where intermediate/outputs are written
# Skull-stripped structural image used as the registration target.
STRUCTURAL_NII = "./outputs/temp_preprocessedBrainExtractionBrain.nii.gz"
TR_SECONDS = 2  # repetition time; set to None to read from the NIfTI header

if os.path.isdir(ANTS_BIN):
    os.environ["PATH"] = ANTS_BIN + ":" + os.environ["PATH"]

root_dir = ROOT_DIR
output_root = OUTPUT_ROOT
os.makedirs(output_root, exist_ok=True)

dicom_dirs = []

# Walk through all subdirectories
for dirpath, dirnames, filenames in os.walk(root_dir):
    # Check if this folder contains DICOM files (usually .dcm)
    dcm_files = [f for f in filenames if f.lower().endswith(".dcm")]
    if dcm_files:
        dicom_dirs.append(dirpath)

print(f"Found {len(dicom_dirs)} DICOM directories")
for d in dicom_dirs[:3]:  # show first 10
    print(d)

t1_files = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    for f in filenames:
        if f.lower().endswith(".nii") or f.lower().endswith(".nii.gz"):
            t1_files.append(os.path.join(dirpath, f))

print(f"Found {len(t1_files)} structural MRI files")
for t1 in t1_files:
    print(t1)



for d in [dicom_dirs[0]]:
    # subject_id = d.replace(root_dir, "").strip("/").replace("/", "_")  # flatten hierarchy

    rel_path = os.path.relpath(d, root_dir)
    parts = rel_path.split(os.sep)
    subject_id = f"{parts[0]}_{parts[-1]}"  # first + last folder
    output_file = os.path.join(output_root, f"{subject_id}.nii.gz")

    try:
        # dicom2nifti.convert_dicom(d, output_file, reorient=True)
        dicom2nifti.convert_directory(d, output_root, compression=True, reorient=True)
        print(f"Converted {d} -> {output_root}")
    except Exception as e:
        print(f"Failed on {d}: {e}")


    # Find the generated file(s)
    nifti_file = sorted(glob.glob(os.path.join(output_root, '*.nii.gz')))
    nii_fmri_path = nifti_file[0]
    img = nib.load(nii_fmri_path)
    data= img.get_fdata() # shape: (X, Y, Z, T)
    print(f"Shape of the fMRI data: {data.shape}")  # Shape of the fMRI data: (64, 64, 48, 140)
    # 48 slices × 140 timepoints = 6720 slices
    tr = img.header.get_zooms()[3]
    print("TR (s):", tr)
    print(img.header)

    structural_nii = STRUCTURAL_NII

    # TR in seconds: use the configured value, or read it from the header.
    tr = TR_SECONDS if TR_SECONDS is not None else img.header.get_zooms()[3]

    # 1. Slice Timing Correction
    stc_nii = slice_time_correct_fmri(nifti_file[0], tr=tr, slice_order="ascending")
    print("Slice-time-corrected file:", stc_nii)

    # 2. Motion Correction
    mc_nii = motion_correct_fmri(stc_nii)
    print("Motion-corrected file:", mc_nii)
    mc_par = f"{mc_nii}.par" #f"{os.path.splitext(mc_nii)[0]}.par"  # Motion parameters from mcflirt
    check_file_exists(mc_par)

    # 3. BET Brain Extraction
    bet_nii = bet_brain_extraction(mc_nii, frac_intensity=0.5)
    print("Brain-extracted file:", bet_nii)  # it saves two files bet_mask.nii.gz shape (64, 64, 48), bet.nii.gz shape (64, 64, 48, 100)
    mask_nii = f"{os.path.splitext(os.path.splitext(bet_nii)[0])[0]}_mask.nii.gz" #f"{os.path.splitext(bet_nii)[0]}_mask.nii.gz"  # Mask from BET (-m option)
    check_file_exists(mask_nii)

    # 4. Spatial Smoothing
    smooth_nii = spatial_smoothing(bet_nii, fwhm=6.0)
    print("Smoothed file:", smooth_nii)

    # 5. Intensity Normalization
    norm_nii = intensity_normalization(smooth_nii, mean_intensity=10000)
    print("Normalized file:", norm_nii)

    # 6. Temporal Filtering (optional; enable if you need band-limited signal)
    # filt_nii = temporal_filtering(norm_nii, highpass_sigma=50.0, tr=tr)

    # 7. ICA Denoising (runs MELODIC; classify components or use ICA-AROMA)
    denoised_nii = ica_denoising(norm_nii)
    print("Denoised file (check MELODIC output for components):", denoised_nii)

    # 8. Registration to Standard Space
    reg_nii = registration_to_standard(denoised_nii, structural_nii)
    print("Registered file:", reg_nii)
