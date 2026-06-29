"""Minimal ANTs-based T1 preprocessing: reorient -> N4 -> denoise -> resample.

Writes a resampled copy and a normalized copy of every NIfTI found under
``input_dir`` (see the CONFIG block near the bottom of this file).
"""

import glob
import os
from pathlib import Path

import ants
import nibabel as nib
from nibabel.orientations import axcodes2ornt, ornt_transform
from tqdm import tqdm
def reorient_RAI(nifti_file,output_file):
    # Load the NIfTI file
    img = nib.load(nifti_file)

    current_orientation = nib.io_orientation(img.affine)
    print("Current Orientation:", nib.aff2axcodes(img.affine))

    # Define the desired orientation (RAS)
    desired_orientation = axcodes2ornt(('R', 'A', 'I'))

    # Compute the transformation to reorient the image
    transform = ornt_transform(current_orientation, desired_orientation)

    # Apply the transformation to the image data
    reoriented_data = nib.orientations.apply_orientation(img.get_fdata(), transform)

    # Compute the new affine matrix
    new_affine = nib.orientations.inv_ornt_aff(transform, img.shape)
    new_affine = img.affine @ new_affine

    # Create a new NIfTI image with the reoriented data and updated affine
    reoriented_img = nib.Nifti1Image(reoriented_data, new_affine)

    # Save the reoriented NIfTI file
    reoriented_img.to_filename(output_file)

    # Verify the new orientation
    new_orientation = nib.io_orientation(reoriented_img.affine)
    print("New Orientation:", nib.aff2axcodes(reoriented_img.affine))

def retrieve_nii_list_from_csv(csv_path,column_name):
    import pandas as pd
    df = pd.read_csv(csv_path)
    return list(df[column_name])

def full_preprocess(nii_path):
    #create dirs
    img = ants.image_read(nii_path)
    output_str = nii_path.replace(str(input_dir),str(output_dir))
    os.makedirs(os.path.dirname(output_str), exist_ok=True)
    output_norm_str = nii_path.replace(str(input_dir),str(output_dir_norm))
    os.makedirs(os.path.dirname(output_norm_str), exist_ok=True)

    #main preprocessing
    assert img is not None
    img = ants.reorient_image2(img,orientation='RAI')
    corrected = ants.n4_bias_field_correction(img)
    denoised = ants.denoise_image(corrected, noise_model="Gaussian")
    # Resample to 1×1×1 mm³
    resampled_image = ants.resample_image(denoised, (1.0, 1.0, 1.0), use_voxels=False, interp_type=1)
    normalized = ants.iMath(resampled_image, "Normalize")
    


    ants.image_write(resampled_image, str(output_str))
    reorient_RAI(str(output_str),str(output_str))
    
    ants.image_write(normalized, str(output_norm_str))
    reorient_RAI(str(output_norm_str),str(output_norm_str))
    
# === CONFIG: edit these paths to match your setup ===
input_dir = Path("/path/to/input/ADNI_MP_RAGE_nii")
output_dir = Path("/path/to/output/ADNI_MP_RAGE_RAI")
output_dir_norm = Path("/path/to/output/ADNI_MP_RAGE_RAI_norm")

output_dir.mkdir(parents=True, exist_ok=True)
output_dir_norm.mkdir(parents=True, exist_ok=True)

nii_list = glob.glob(f"{input_dir}/**/*.nii.gz", recursive=True)


if __name__ == "__main__":
    for nii_path in tqdm(nii_list):
        full_preprocess(nii_path)
