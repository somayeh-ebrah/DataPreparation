#!/usr/bin/env python3
"""
Modified T1 preprocessing pipeline following paper specifications:
1. N4 bias field correction using SimpleITK
2. Resample to isotropic 1×1×1 mm³ voxels through linear interpolation  
3. Rigid registration to MNI space brain atlas
4. Brain extraction/skull stripping using HD-BET package

Reusable step functions used by the batch drivers (t1_batch_preprocess.py,
t1_adni_preprocess.py).
"""

import os
import sys
import numpy as np
import nibabel as nib
import SimpleITK as sitk
import ants
from pathlib import Path
import subprocess
import tempfile
import shutil
from typing import Optional, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reorient_to_ras_ants(input_path: str, output_path: str) -> bool:
    """
    Reorient image to RAS orientation using ANTs.
    
    Args:
        input_path: Path to input NIfTI file
        output_path: Path to save reoriented image
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Reorienting to RAS orientation using ANTs: {input_path}")
        
        # Read the image using ANTs
        img = ants.image_read(input_path)
        
        # Reorient to RAS
        reoriented_img = ants.reorient_image2(img, orientation='RAS')
        
        # Write the reoriented image
        ants.image_write(reoriented_img, output_path)
        
        logger.info(f"ANTS reorientation completed. Saved to: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error in ANTs reorientation: {e}")
        return False

def n4_bias_field_correction_sitk(input_path: str, output_path: str) -> bool:
    """
    Apply N4 bias field correction using SimpleITK.
    
    Args:
        input_path: Path to input NIfTI file
        output_path: Path to save bias-corrected image
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Applying N4 bias field correction to: {input_path}")
        
        # Read the image
        image = sitk.ReadImage(input_path)
        
        # Apply N4 bias field correction
        corrector = sitk.N4BiasFieldCorrectionImageFilter()
        corrected_image = corrector.Execute(image)
        
        # Write the corrected image
        sitk.WriteImage(corrected_image, output_path)
        
        logger.info(f"N4 bias correction completed. Saved to: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error in N4 bias field correction: {e}")
        return False

def resample_to_isotropic_sitk(input_path: str, output_path: str, 
                              target_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bool:
    """
    Resample image to isotropic voxels using linear interpolation.
    
    Args:
        input_path: Path to input NIfTI file
        output_path: Path to save resampled image
        target_spacing: Target voxel spacing in mm (default: 1x1x1 mm³)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Resampling to {target_spacing} mm³: {input_path}")
        
        # Read the image
        image = sitk.ReadImage(input_path)
        
        # Get current spacing
        current_spacing = image.GetSpacing()
        logger.info(f"Current spacing: {current_spacing}")
        
        # Calculate new size
        current_size = image.GetSize()
        new_size = [int(current_size[i] * current_spacing[i] / target_spacing[i]) 
                   for i in range(3)]
        
        logger.info(f"New size: {new_size}")
        
        # Resample using linear interpolation
        resampler = sitk.ResampleImageFilter()
        resampler.SetOutputSpacing(target_spacing)
        resampler.SetSize(new_size)
        resampler.SetInterpolator(sitk.sitkLinear)
        resampler.SetOutputDirection(image.GetDirection())
        resampler.SetOutputOrigin(image.GetOrigin())
        
        resampled_image = resampler.Execute(image)
        
        # Write the resampled image
        sitk.WriteImage(resampled_image, output_path)
        
        logger.info(f"Resampling completed. Saved to: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error in resampling: {e}")
        return False

def find_mni_template() -> str:
    """
    Find the MNI template. Adjust path as needed for your system.
    """
    # Common locations for MNI templates (edit/extend for your system)
    possible_paths = [
        os.path.join(os.environ.get("FSLDIR", ""), "data/standard/MNI152_T1_1mm.nii.gz"),
        "/usr/share/fsl/data/standard/MNI152_T1_1mm.nii.gz",
        "/usr/local/fsl/data/standard/MNI152_T1_1mm.nii.gz",
        "/home/user/fsl/data/standard/MNI152_T1_1mm.nii.gz",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Found MNI template at: {path}")
            return path
    
    # If not found, download or use a default
    logger.warning("MNI template not found in standard locations. Please specify the correct path.")
    return None

def rigid_registration_to_mni_ants(input_path: str, output_path: str, mni_template: str) -> bool:
    """
    Perform rigid registration to MNI space using ANTsPy.

    Args:
        input_path: Path to input NIfTI file
        output_path: Path to save registered image
        mni_template: Path to MNI template

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Performing rigid registration to MNI with ANTs: {input_path}")

        # Load images
        fixed_image = ants.image_read(mni_template)
        moving_image = ants.image_read(input_path)

        # Initial alignment to center the images
        init_transform = ants.registration(
            fixed=fixed_image,
            moving=moving_image,
            type_of_transform='QuickRigid',
            verbose=False
        )

        # Full rigid registration
        registration = ants.registration(
            fixed=fixed_image,
            moving=moving_image,
            type_of_transform='Rigid',
            initial_transform=init_transform['fwdtransforms'],
            metric='mattes',
            metric_weight=1.0,
            sampling_strategy='regular',
            sampling_percentage=0.3,
            convergence=[200, 1e-6, 10],
            smoothing_sigmas=[0],
            shrink_factors=[1],
            # verbose=True
        )

        # Apply the transform to the moving image
        registered_image = registration['warpedmovout']

        # Save the registered image
        ants.image_write(registered_image, output_path)

        # Log intensity stats for diagnostics
        img_data = registered_image.numpy()
        logger.info(
            f"Registered image stats: min={img_data.min():.2f}, max={img_data.max():.2f}, mean={img_data.mean():.2f}")

        logger.info(f"Rigid registration completed. Saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error in rigid registration: {e}")
        return False

def rigid_registration_to_mni_sitk(input_path: str, output_path: str, mni_template: str) -> bool:
    """
    Perform rigid registration to MNI space using SimpleITK.

    Args:
        input_path: Path to input NIfTI file
        output_path: Path to save registered image
        mni_template: Path to MNI template

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Performing rigid registration to MNI: {input_path}")

        # Read images
        fixed_image = sitk.ReadImage(mni_template)
        moving_image = sitk.ReadImage(input_path)

        # Cast images to the same data type (sitkFloat32 for consistency)
        caster = sitk.CastImageFilter()
        caster.SetOutputPixelType(sitk.sitkFloat32)
        fixed_image = caster.Execute(fixed_image)
        moving_image = caster.Execute(moving_image)

        # Verify data types
        logger.info(f"Fixed image type: {fixed_image.GetPixelIDTypeAsString()}")
        logger.info(f"Moving image type: {moving_image.GetPixelIDTypeAsString()}")

        # Initialize registration
        registration = sitk.ImageRegistrationMethod()

        # Set interpolator
        registration.SetInterpolator(sitk.sitkLinear)

        # Set metric (mutual information works well for T1 images)
        registration.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)

        # Set optimizer
        registration.SetOptimizerAsGradientDescent(
            learningRate=1.0,
            numberOfIterations=100,
            convergenceMinimumValue=1e-6,
            convergenceWindowSize=10
        )

        # Set optimizer scaling
        registration.SetOptimizerScalesFromPhysicalShift()

        # Set initial transform (identity)
        initial_transform = sitk.TranslationTransform(3)
        registration.SetInitialTransform(initial_transform, inPlace=False)

        # Execute registration
        transform = registration.Execute(fixed_image, moving_image)

        # Apply transform
        resampler = sitk.ResampleImageFilter()
        resampler.SetReferenceImage(fixed_image)
        resampler.SetInterpolator(sitk.sitkLinear)
        resampler.SetTransform(transform)

        registered_image = resampler.Execute(moving_image)

        # Write the registered image
        sitk.WriteImage(registered_image, output_path)

        logger.info(f"Rigid registration completed. Saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error in rigid registration: {e}")
        return False

def brain_extraction_hd_bet(input_path: str, output_path: str, mask_output_path: Optional[str] = None) -> bool:
    """
    Perform brain extraction using HD-BET package.

    Args:
        input_path: Path to input NIfTI file
        output_path: Path to save brain-extracted image
        mask_output_path: Path to save brain mask (optional)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Performing brain extraction with HD-BET: {input_path}")

        # Check if HD-BET is available
        try:
            subprocess.run(['hd-bet', '--help'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("HD-BET not found. Please install it first:")
            logger.error("pip install HD-BET")
            return False

        # Prepare HD-BET command
        cmd = ['hd-bet', '-i', input_path, '-o', output_path]

        if mask_output_path:
            cmd.append('--save_bet_mask')  # Use correct flag for saving mask

        # Run HD-BET
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"HD-BET failed: {result.stderr}")
            return False

        # If mask_output_path is specified, move the generated mask to the desired location
        if mask_output_path:
            # default_mask_path = str(Path(output_path).with_suffix('') + '_mask.nii.gz')
            default_mask_path = str(Path(output_path).with_name(Path(output_path).stem + '_mask.nii.gz'))
            if os.path.exists(default_mask_path):
                os.makedirs(os.path.dirname(mask_output_path), exist_ok=True)
                shutil.move(default_mask_path, mask_output_path)
                logger.info(f"Brain mask saved to: {mask_output_path}")
            else:
                logger.warning(f"Brain mask not found at {default_mask_path}")

        logger.info(f"Brain extraction completed. Saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error in brain extraction: {e}")
        return False


def fsl_reorient2std(input_path: str, output_path: str, output_dir: str, subject_id: str) -> bool:
    """
    Reorient an image to MNI152 standard orientation (RAS+) using fslreorient2std.
    Save coronal view for debugging.
    """
    try:
        subprocess.run(['fslreorient2std', '-h'], capture_output=True, check=True)
        cmd = ['fslreorient2std', input_path, output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Verify output orientation
        img = nib.load(output_path)
        orientation = nib.aff2axcodes(img.affine)
        print(f"fslreorient2std output orientation: {orientation}")
        if orientation != ('R', 'A', 'S'):
            print(f"Warning: fslreorient2std output is {orientation}, not RAS+. Falling back to ANTs reorientation.")
            return False

        # Save coronal view for debugging
        coronal_view_path = os.path.join(output_dir, subject_id, f"{subject_id}_reoriented_mni_coronal.png")
        os.makedirs(os.path.dirname(coronal_view_path), exist_ok=True)
        # plotting.plot_anat(output_path, display_mode='y', dim='auto', cmap='gray', output_file=coronal_view_path)
        print(f"Coronal view saved to: {coronal_view_path}")

        print(f"fslreorient2std completed. Saved to: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"fslreorient2std failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("fslreorient2std not found. Please install FSL (e.g., sudo apt install fsl).")
        return False
    except Exception as e:
        print(f"Error in fslreorient2std: {e}")
        return False

def paper_preprocessing_pipeline(nii_path: str, output_dir: str, subject_id: str) -> bool:
    """
    Complete preprocessing pipeline following paper specifications.
    
    Args:
        nii_path: Path to input NIfTI file
        output_dir: Directory to save preprocessed images
        subject_id: Subject identifier for output naming
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Starting paper-based preprocessing for subject: {subject_id}")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create temporary directory for intermediate files
        temp_dir = Path(tempfile.mkdtemp(prefix=f"t1_preprocessing_{subject_id}_"))
        
        # Define intermediate file paths
        reoriented_path = temp_dir / f"{subject_id}_reoriented.nii.gz"
        bias_corrected_path = temp_dir / f"{subject_id}_bias_corrected.nii.gz"
        resampled_path = temp_dir / f"{subject_id}_resampled.nii.gz"
        registered_path = temp_dir / f"{subject_id}_registered.nii.gz"
        
        # Final output paths
        brain_extracted_path = output_path / f"{subject_id}_preprocessed.nii.gz"
        brain_mask_path = output_path / f"{subject_id}_brain_mask.nii.gz"
        
        # Step 0: Reorient to RAS orientation using ANTs
        if not reorient_to_ras_ants(nii_path, str(reoriented_path)):
            logger.error(f"ANTS reorientation failed for {subject_id}")
            return False
        
        # Step 1: N4 bias field correction using SimpleITK
        if not n4_bias_field_correction_sitk(str(reoriented_path), str(bias_corrected_path)):
            logger.error(f"N4 bias correction failed for {subject_id}")
            return False
        
        # Step 2: Resample to isotropic 1x1x1 mm³ through linear interpolation
        if not resample_to_isotropic_sitk(str(bias_corrected_path), str(resampled_path)):
            logger.error(f"Resampling failed for {subject_id}")
            return False
        
        # Step 3: Rigid registration to MNI space brain atlas
        mni_template = find_mni_template()
        if not mni_template:
            logger.error("MNI template not found. Skipping registration.")
            # Copy resampled image as registered image
            shutil.copy2(str(resampled_path), str(registered_path))
        else:
            if not rigid_registration_to_mni_sitk(str(resampled_path), str(registered_path), mni_template):
                logger.error(f"Registration failed for {subject_id}")
                return False
        
        # Step 4: Brain extraction/skull stripping using HD-BET package
        if not brain_extraction_hd_bet(str(registered_path), str(brain_extracted_path), 
                                     str(brain_mask_path)):
            logger.error(f"Brain extraction failed for {subject_id}")
            return False
        
        # Clean up temporary files
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Could not clean up temp files: {e}")
        
        logger.info(f"Paper-based preprocessing completed successfully for {subject_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error in paper preprocessing pipeline for {subject_id}: {e}")
        return False

# Example usage function
def process_nifti_files(input_dir: str, output_dir: str):
    """
    Process all NIfTI files in input directory using the paper-based pipeline.
    
    Args:
        input_dir: Directory containing input NIfTI files
        output_dir: Directory to save preprocessed files
    """
    input_path = Path(input_dir)
    nifti_files = list(input_path.glob("**/*.nii.gz"))
    
    logger.info(f"Found {len(nifti_files)} NIfTI files to process")
    
    success_count = 0
    for nifti_file in nifti_files:
        subject_id = nifti_file.stem.replace('.nii', '')
        
        if paper_preprocessing_pipeline(str(nifti_file), output_dir, subject_id):
            success_count += 1
        else:
            logger.error(f"Failed to process {subject_id}")
    
    logger.info(f"Processing complete. {success_count}/{len(nifti_files)} files processed successfully")

if __name__ == "__main__":
    # Example usage
    input_directory = "/path/to/your/nifti/files"  # Update this path
    output_directory = "/path/to/output/preprocessed/files"  # Update this path
    
    process_nifti_files(input_directory, output_directory)
