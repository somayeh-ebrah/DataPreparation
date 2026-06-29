"""Select one T1 scan per ADNI subject, convert from DICOM, and preprocess.

Finds subjects common to an fMRI and a T1 CSV export, picks the most recent
T1 scan per subject, loads the DICOM series, and runs the structural pipeline
(N4 -> resample -> denoise -> normalize -> reorient -> MNI registration ->
HD-BET brain extraction). Paths are set in the CONFIG block near the bottom.
"""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import ants
import nibabel as nib
import pandas as pd
import SimpleITK as sitk
from nilearn import plotting
from tqdm import tqdm

from t1_utils import *


def find_common_subjects(fmri_csv_path, t1_csv_path):
    # Load the fMRI CSV
    df_fmri = pd.read_csv(fmri_csv_path)

    # Load the T1 MP-RAGE CSV
    df_t1 = pd.read_csv(t1_csv_path)

    # Extract unique Subject IDs from each
    subjects_fmri = set(df_fmri['Subject ID'].unique())
    subjects_t1 = set(df_t1['Subject'].unique())
    #subjects_t1 = set(df_t1['Subject ID'].unique())

    # Find the intersection (common subjects)
    common_subjects = subjects_fmri.intersection(subjects_t1)

    # Sort and return as a list
    return sorted(common_subjects)


def extract_date_from_path(dirpath):
    """
    Extract date from directory path (e.g., '2011-11-04_12_16_02.0' -> datetime object).
    Returns None if date cannot be parsed.
    """
    try:
        # Extract the date part (e.g., '2011-11-04' from '2011-11-04_12_16_02.0')
        date_str = os.path.basename(os.path.dirname(dirpath)).split('_')[0]
        return datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, IndexError):
        return None


def select_one_scan_per_subject(root_dir, common_subjects):
    # Convert common_subjects to a set for faster lookup
    common_subjects_set = set(common_subjects)

    # Dictionary to store scans for each subject
    subject_scans = {}

    # Walk through all subdirectories
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Check if this folder contains DICOM files (usually .dcm)
        dcm_files = [f for f in filenames if f.lower().endswith(".dcm")]
        if dcm_files:
            # Extract subject ID from the path (assuming subject ID is in the path)
            path_parts = dirpath.split(os.sep)
            for part in path_parts:
                if part in common_subjects_set:
                    subject_id = part
                    if subject_id not in subject_scans:
                        subject_scans[subject_id] = []
                    subject_scans[subject_id].append(dirpath)
                    break

    # Select one scan per subject (most recent based on date)
    selected_scans = {}
    for subject_id, scans in subject_scans.items():
        if len(scans) == 1:
            selected_scans[subject_id] = scans[0]
        else:
            # Sort scans by date (most recent first)
            scans_with_dates = [(scan, extract_date_from_path(scan)) for scan in scans]
            # Filter out scans with invalid dates
            valid_scans = [(scan, date) for scan, date in scans_with_dates if date is not None]
            if valid_scans:
                # Select the most recent scan
                selected_scans[subject_id] = max(valid_scans, key=lambda x: x[1])[0]
            else:
                # If no valid dates, pick the first scan as a fallback
                selected_scans[subject_id] = scans[0]

    return selected_scans


def full_preprocess(nifti_img, subject_id, output_dir, t1_image_id):
    """
    Modified preprocessing following paper specifications:
    0. Reorient to RAS orientation using ANTs
    1. N4 bias field correction using SimpleITK
    2. Resample to isotropic 1×1×1 mm³ voxels through linear interpolation
    3. Rigid registration to MNI space brain atlas
    4. Brain extraction/skull stripping using HD-BET package
    """

    import tempfile
    import shutil
    from t1_pipeline import (
        reorient_to_ras_ants,
        n4_bias_field_correction_sitk,
        resample_to_isotropic_sitk,
        rigid_registration_to_mni_ants,
        rigid_registration_to_mni_sitk,
        brain_extraction_hd_bet,
        fsl_reorient2std,
        find_mni_template
    )

    # Create output directories
    output_str = os.path.join(output_dir, subject_id, f"{subject_id}_{t1_image_id}.nii.gz")
    os.makedirs(os.path.dirname(output_str), exist_ok=True)

    # Create temporary directory for intermediate files
    temp_dir = Path(tempfile.mkdtemp(prefix=f"t1_preprocessing_{subject_id}_"))

    try:
        # Save the input NIfTI image to a temporary file
        temp_nii_path = temp_dir / f"{subject_id}.nii.gz"
        nib.save(nifti_img, str(temp_nii_path))

        # Step 1: N4 bias field correction using SimpleITK
        bias_corrected_path = temp_dir / f"{subject_id}_bias_corrected.nii.gz"
        if not n4_bias_field_correction_sitk(str(temp_nii_path), str(bias_corrected_path)):
            print(f"N4 bias correction failed for {subject_id}")
            return False

        # Step 2: Resample to isotropic 1x1x1 mm³ through linear interpolation
        resampled_path = temp_dir / f"{subject_id}_resampled.nii.gz"
        if not resample_to_isotropic_sitk(str(bias_corrected_path), str(resampled_path)):
            print(f"Resampling failed for {subject_id}")
            return False

        # Step 3: Denoise using ANTs (Gaussian noise model)
        denoised_path = temp_dir / f"{subject_id}_denoised.nii.gz"
        resampled_sitk = sitk.ReadImage(str(resampled_path))
        resampled_ants = ants.from_sitk(resampled_sitk)  # Convert to ANTs format
        denoised = ants.denoise_image(resampled_ants, noise_model="Gaussian")
        ants.image_write(denoised, str(denoised_path))

        # Step 4: Normalize using ANTs
        normalized_path = temp_dir / f"{subject_id}_normalized.nii.gz"
        normalized = ants.iMath(denoised, "Normalize")
        ants.image_write(normalized, str(normalized_path))

        # Step 4: Reorient to MNI standard (RAS+) using fslreorient2std
        reoriented_mni_path = temp_dir / f"{subject_id}_reoriented_mni.nii.gz"
        print(f"Reorienting to MNI standard using fslreorient2std: {normalized_path}")
        if not fsl_reorient2std(str(normalized_path), str(reoriented_mni_path), output_dir, subject_id):
            print(f"fslreorient2std failed for {subject_id}, attempting ANTs reorientation")
            if not reorient_to_ras_ants(str(normalized_path), str(reoriented_mni_path)):
                print(f"ANTs reorientation also failed, using normalized image")
                shutil.copy2(str(normalized_path), str(reoriented_mni_path))
            else:
                print(f"ANTs reorientation completed. Saved to: {reoriented_mni_path}")
                # Save coronal view for ANTs reorientation
                coronal_view_path = os.path.join(output_dir, subject_id, f"{subject_id}_reoriented_mni_coronal.png")
                plotting.plot_anat(str(reoriented_mni_path), display_mode='y', dim='auto', cmap='gray',
                                   output_file=coronal_view_path)
                print(f"Coronal view saved to: {coronal_view_path}")
        img_data = nib.load(str(reoriented_mni_path)).get_fdata()
        print(
            f"Reoriented MNI image stats: min={img_data.min():.2f}, max={img_data.max():.2f}, mean={img_data.mean():.2f}")

        # Step 3: Rigid registration to MNI space brain atlas
        mni_template = find_mni_template()
        registered_path = temp_dir / f"{subject_id}_registered.nii.gz"

        if mni_template:
            if not rigid_registration_to_mni_ants(str(reoriented_mni_path), str(registered_path), mni_template):
                print(f"Registration failed for {subject_id}, using normalized image")
                shutil.copy2(str(reoriented_mni_path), str(registered_path))
            else:
                print(f"Rigid registration completed. Saved to: {registered_path}")
        else:
            print("MNI template not found, skipping registration")
            shutil.copy2(str(normalized_path), str(registered_path))
        img_data = nib.load(str(registered_path)).get_fdata()
        print(
            f"Registered image stats: min={img_data.min():.2f}, max={img_data.max():.2f}, mean={img_data.mean():.2f}")

        # Step 5: Brain extraction/skull stripping using HD-BET package
        if not brain_extraction_hd_bet(str(registered_path), output_str):
            print(f"Brain extraction failed for {subject_id}")
            return False

        print(f"Preprocessing completed successfully for {subject_id}")
        return True

    except Exception as e:
        print(f"Error in preprocessing pipeline for {subject_id}: {e}")
        return False

    finally:
        # Clean up temporary files
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Could not clean up temp files: {e}")


# === CONFIG: edit these paths to match your setup ===
root_dir = "/path/to/adni/T1_MPRAGE/ADNI"                  # DICOM root directory
t1_csv_path = "/path/to/adni/t1_mprage_search.csv"        # ADNI T1 image-search CSV export
fmri_csv_path = "/path/to/adni/resting_state_fmri_search.csv"  # ADNI fMRI image-search CSV export
output_dir = "/path/to/output/preprocessed_subjects"

dicom_dirs = []
for dirpath, dirnames, filenames in os.walk(root_dir):
    # Keep folders that contain DICOM (.dcm) files
    dcm_files = [f for f in filenames if f.lower().endswith(".dcm")]
    if dcm_files:
        dicom_dirs.append(dirpath)

print(f"Found {len(dicom_dirs)} DICOM directories")
for d in dicom_dirs[:3]:
    print(d)

common_subjects = find_common_subjects(fmri_csv_path, t1_csv_path)
print(f"Common Subjects: {len(common_subjects)}")

df_t1 = pd.read_csv(t1_csv_path)

# Select one scan per subject
selected_scans = select_one_scan_per_subject(root_dir, common_subjects)

for subject in tqdm(common_subjects):
    print(f"Processing subject {subject}")
    t1_data_path = selected_scans[subject]

    if t1_data_path is None:
        print(f"No scan path found for subject {subject}")
        continue

    # Extract the last part of t1_data_path (e.g., I303066)
    t1_image_id = os.path.basename(t1_data_path)

    # Load DICOM series as NIfTI
    nifti_img = load_dicom_series(t1_data_path)

    if nifti_img is None:
        print(f"Skipping preprocessing for {subject} due to failed DICOM loading")
        continue

    # Preprocess the NIfTI image
    try:
        success = full_preprocess(nifti_img, subject, output_dir, t1_image_id)
        if success:
            output_nii_path = os.path.join(output_dir, subject, f"{subject}_{t1_image_id}.nii.gz")
            print(f"Saved preprocessed image: {output_nii_path}")
    except Exception as e:
        print(f"Error preprocessing {subject}: {e}")
