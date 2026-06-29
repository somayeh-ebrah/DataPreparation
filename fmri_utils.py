"""FSL/ANTs command wrappers for resting-state fMRI preprocessing.

Each function shells out to an external neuroimaging tool (FSL or ANTs) and
returns the path to the file it produced. FSL and ANTs must be installed and
on ``PATH`` (and ``FSLDIR`` / ``ANTSPATH`` set where noted).
"""

import os
import subprocess


def check_file_exists(file_path):
    """Raise FileNotFoundError if ``file_path`` does not exist; else return it."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    return file_path

def slice_time_correct_fmri(input_nii, output_nii=None, tr=2.0, slice_order="ascending"):
    """
    Runs FSL slicetimer for slice timing correction.
    Args:
        input_nii (str): Path to the input NIfTI file.
        output_nii (str, optional): Output path for corrected NIfTI.
        tr (float): Repetition time (TR) in seconds.
        slice_order (str): "ascending", "descending", or provide a custom order.
    Returns:
        str: Path to slice-time-corrected NIfTI.
        # Example usage:
# corrected = slice_time_correct_fmri("subject01_bold_mc.nii.gz", tr=2.0, slice_order="ascending")
# print("Slice-time-corrected file saved to:", corrected)
    """
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_stc{ext}"

    # FSL slicetimer options
    order_flag = ""
    if slice_order == "descending":
        order_flag = "--down"
    elif slice_order != "ascending":
        # If custom order, write to file and use --ocustom
        with open("slice_order.txt", "w") as f:
            f.write(" ".join(map(str, slice_order)))
        order_flag = "--ocustom=slice_order.txt"

    command = [
        "slicetimer",
        "-i", input_nii,
        "-o", output_nii,
        "-r", str(tr),
    ]
    if order_flag:
        command.extend(order_flag.split())

    print(command)
    subprocess.run(command, check=True)
    return output_nii

# 2. Motion Correction (Already Provided)
def motion_correct_fmri(input_nii, output_nii=None):
    """
    Runs FSL MCFLIRT motion correction on an fMRI NIfTI file.
    Args:
        input_nii (str): Path to the input 4D NIfTI file.
        output_nii (str, optional): Path to the output corrected NIfTI file.
            If None, appends '_mc' to input filename.
    Returns:
        str: Path to the motion-corrected NIfTI file.
    """
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_mc{ext}"

    # Call FSL's MCFLIRT
    command = [
        "mcflirt",
        "-in", input_nii,
        "-out", output_nii,
        "-plots"  # Save motion parameters
    ]
    print(command)
    subprocess.run(command, check=True)

    return output_nii

# 3. BET Brain Extraction
def bet_brain_extraction(input_nii, output_nii=None, frac_intensity=0.5):
    """
    Runs FSL BET for brain extraction on fMRI data.
    Args:
        input_nii (str): Path to the input NIfTI file (after motion correction).
        output_nii (str, optional): Path to the output brain-extracted NIfTI.
        frac_intensity (float): Fractional intensity threshold (default: 0.5).
    Returns:
        str: Path to the brain-extracted NIfTI file.
    """
    check_file_exists(input_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_bet{ext}"

    command = ["bet", input_nii, output_nii, "-F", "-f", str(frac_intensity)]
    print("Running:", command)
    subprocess.run(command, check=True)
    return output_nii



def ants_brain_extraction(input_nii, output_root="./outputs/temp_preprocessed"):
    """
        Run ANTs antsBrainExtraction.sh for brain extraction.
        Args:
            input_nii (str): Path to the input NIfTI file.
            output_root (str): Output directory for brain extraction results.
        Returns:
            str: Output prefix (directory where results are stored).
        """
    # Assume ANTSPATH and FSLDIR are set in the environment
    fsldir = os.environ.get("FSLDIR")
    ants_path = os.environ.get("ANTSPATH")

    if not fsldir:
        raise RuntimeError("FSLDIR environment variable is not set.")
    # Compose template and mask paths
    template = os.path.join(fsldir, "data/standard/MNI152_T1_2mm.nii.gz")
    template_mask = os.path.join(fsldir, "data/standard/MNI152_T1_2mm_brain_mask_dil.nii.gz")
    # Ensure output directory exists
    os.makedirs(output_root, exist_ok=True)
    out_prefix = os.path.join(output_root)
    ants_script = os.path.join(ants_path, "antsBrainExtraction.sh") if ants_path else "antsBrainExtraction.sh"
    cmd = [
        ants_script,
        "-d", "3",
        "-a", input_nii,
        "-e", template,
        "-m", template_mask,
        "-o", out_prefix
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return out_prefix

# 4. Spatial Smoothing
def spatial_smoothing(input_nii, output_nii=None, fwhm=5.0):
    """
    Runs FSL spatial smoothing with a Gaussian kernel.
    Args:
        input_nii (str): Path to the input NIfTI file (after BET).
        output_nii (str, optional): Path to the output smoothed NIfTI.
        fwhm (float): Full Width at Half Maximum (mm) for Gaussian kernel (default: 5.0).
    Returns:
        str: Path to the smoothed NIfTI file.
    """
    check_file_exists(input_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_smooth{ext}"

    # Convert FWHM to sigma (sigma = FWHM / (2 * sqrt(2 * ln(2))))
    sigma = fwhm / 2.35482
    command = ["fslmaths", input_nii, "-s", str(sigma), output_nii]
    print("Running:", command)
    subprocess.run(command, check=True)
    return output_nii

# 5. Intensity Normalization
def intensity_normalization(input_nii, output_nii=None, mean_intensity=10000):
    """
    Runs FSL intensity normalization (grand-mean scaling).
    Args:
        input_nii (str): Path to the input NIfTI file (after smoothing).
        output_nii (str, optional): Path to the output normalized NIfTI.
        mean_intensity (float): Target mean intensity (default: 10000).
    Returns:
        str: Path to the normalized NIfTI file.
    """
    check_file_exists(input_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_norm{ext}"

    command = ["fslmaths", input_nii, "-ing", str(mean_intensity), output_nii]
    print("Running:", command)
    subprocess.run(command, check=True)
    return output_nii


# 6. Temporal Filtering
def temporal_filtering(input_nii, output_nii=None, highpass_sigma=50.0, tr=1.0):
    """
    Runs FSL temporal filtering (highpass).
    Args:
        input_nii (str): Path to the input NIfTI file (after normalization).
        output_nii (str, optional): Path to the output filtered NIfTI.
        highpass_sigma (float): Highpass filter cutoff in seconds (default: 50s).
        tr (float): Repetition time (TR) in seconds.
    Returns:
        str: Path to the filtered NIfTI file.
    """
    check_file_exists(input_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_filt{ext}"

    # Convert highpass cutoff (seconds) to sigma (in volumes: sigma = cutoff / (2 * TR))
    sigma_volumes = highpass_sigma / (2 * tr)
    command = ["fslmaths", input_nii, "-bptf", str(sigma_volumes), "-1", output_nii]
    print("Running:", command)
    subprocess.run(command, check=True)
    return output_nii

def temporal_bandpass_fmri(input_nii, low_freq=0.01, high_freq=0.1, output_nii=None):
    """
    Applies bandpass temporal filtering to 4D fMRI data using FSL fslmaths.
    Args:
        input_nii (str): Path to input NIfTI file.
        low_freq (float): Lower frequency bound (Hz), e.g., 0.01.
        high_freq (float): Upper frequency bound (Hz), e.g., 0.1.
        output_nii (str, optional): Output path.
    Returns:
        str: Path to filtered NIfTI file.

        # Example usage:
# filtered = temporal_bandpass_fmri("your_intensity_normalized_file.nii.gz", low_freq=0.01, high_freq=0.1)
# print("Bandpass-filtered file saved to:", filtered)

Highpass: 0.01 Hz
Period = 1 / 0.01 = 100 seconds
Sigma highpass = 100 / 2.3548 ≈ 42.47
Lowpass: 0.1 Hz
Period = 1 / 0.1 = 10 seconds
Sigma lowpass = 10 / 2.3548 ≈ 4.25
fslmaths input_norm.nii.gz -bptf 42.47 4.25 input_bp.nii.gz
This applies a bandpass filter keeping 0.01–0.1Hz fluctuations.
    """
    highpass_period = 1.0 / low_freq
    lowpass_period = 1.0 / high_freq
    highpass_sigma = highpass_period / 2.3548
    lowpass_sigma = lowpass_period / 2.3548
    # if output_nii is None:
    #     output_nii = input_nii.replace(".nii", "_bp.nii").replace(".gz", "_bp.nii.gz")
    check_file_exists(input_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_filt{ext}"
    command = [
        "fslmaths",
        input_nii,
        "-bptf", str(highpass_sigma), str(lowpass_sigma),
        output_nii
    ]
    print(command)
    subprocess.run(command, check=True)
    return output_nii

# # 7. ICA Denoising (MELODIC)
def ica_denoising(input_nii, output_nii=None, melodic_dir="melodic_output"):
    """
    Runs FSL MELODIC for ICA denoising.
    Args:
        input_nii (str): Path to the input NIfTI file (after filtering).
        output_nii (str, optional): Path to the output denoised NIfTI.
        melodic_dir (str): Directory for MELODIC output.
    Returns:
        str: Path to the denoised NIfTI file.
    Note: Requires manual component classification or ICA-AROMA for automation.
    """
    check_file_exists(input_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_denoised{ext}"

    # Run MELODIC
    command = ["melodic", "-i", input_nii, "-o", melodic_dir, "--nobet", "--no_mm"]
    print("Running:", command)
    subprocess.run(command, check=True)

    # Note: Denoising requires identifying noise components (manual or via ICA-AROMA)
    print(f"MELODIC output saved to {melodic_dir}. Manually classify components or use ICA-AROMA.")
    # Placeholder: Copy input to output (denoising requires additional steps)
    command = ["cp", input_nii, output_nii]
    subprocess.run(command, check=True)
    return output_nii

# 8. Registration to Standard Space
def registration_to_standard(input_nii, structural_nii, output_nii=None, standard_nii="MNI152_T1_1mm_brain.nii.gz"):
    """
    Runs FSL FLIRT (affine) and FNIRT (nonlinear) for registration to standard space (MNI 1mm).
    Args:
        input_nii (str): Path to the input NIfTI file (after denoising).
        structural_nii (str): Path to the skull-stripped high-resolution structural image (T1).
        output_nii (str, optional): Path to the output registered NIfTI.
        standard_nii (str): Path to standard brain template (default: MNI 1mm brain). Update with full path if needed.
    Returns:
        str: Path to the registered NIfTI file.
    """
    check_file_exists(input_nii)
    check_file_exists(structural_nii)

    # Expand FSLDIR if needed; assume common path, adjust if different
    fsl_dir = os.environ.get('FSLDIR', '/usr/local/fsl')  # Replace with your FSLDIR if not set
    standard_nii_full = os.path.join(fsl_dir, 'data/standard', standard_nii)
    standard_full = os.path.join(fsl_dir, 'data/standard', 'MNI152_T1_1mm.nii.gz')  # Non-brain version for FNIRT
    standard_mask = os.path.join(fsl_dir, 'data/standard', 'MNI152_T1_1mm_brain_mask_dil.nii.gz')
    check_file_exists(standard_nii_full)
    check_file_exists(standard_full)
    check_file_exists(standard_mask)

    # if output_nii is None:
    #     output_nii = f"{get_base_path(input_nii)}_reg.nii.gz"
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_reg{ext}"

    # Step 1: Register functional to structural (FLIRT linear)
    func2struct_mat = "func2struct.mat"
    command = ["flirt", "-in", input_nii, "-ref", structural_nii, "-out", "func2struct.nii.gz", "-omat", func2struct_mat, "-dof", "9"]
    print("Running FLIRT (func to struct):", command)
    subprocess.run(command, check=True)

    # Step 2: Register structural to standard (FLIRT affine guess)
    struct2standard_mat = "struct2standard.mat"
    command = ["flirt", "-in", structural_nii, "-ref", standard_nii_full, "-out", "struct2standard.nii.gz", "-omat", struct2standard_mat, "-dof", "9"]
    print("Running FLIRT (struct to standard affine):", command)
    subprocess.run(command, check=True)

    # Step 3: Nonlinear registration with FNIRT (struct to standard)
    warp_nii = "warp_struct2standard.nii.gz"
    command = [
        "fnirt",
        "--ref=" + standard_full,
        "--in=" + structural_nii,
        "--aff=" + struct2standard_mat,
        "--cout=" + warp_nii,
        "--refmask=" + standard_mask,
        "--imprefm=1", "--impinm=1",
        "--imprefval=0", "--impinval=0",
        "--subsamp=4,4,2,2,1,1", "--miter=5,5,5,5,5,10",
        "--infwhm=8,6,5,4.5,3,2", "--reffwhm=8,6,5,4,2,0",
        "--lambda=300,150,100,50,40,30", "--estint=1,1,1,1,1,0",
        "--applyrefmask=0,0,0,0,1,1", "--applyinmask=1",
        "--warpres=10,10,10", "--ssqlambda=1", "--regmod=bending_energy",
        "--intmod=global_non_linear_with_bias", "--intorder=5", "--biasres=50,50,50",
        "--biaslambda=10000", "--refderiv=0"
    ]
    print("Running FNIRT (struct to standard nonlinear):", command)
    subprocess.run(command, check=True)

    # Step 4: Combine transformations (affine + nonlinear warp)
    func2standard_warp = "func2standard_warp.nii.gz"
    command = ["convertwarp", "--ref=" + standard_nii_full, "--premat=" + func2struct_mat, "--warp1=" + warp_nii, "--out=" + func2standard_warp]
    print("Running convertwarp (combine transformations):", command)
    subprocess.run(command, check=True)

    # Step 5: Apply combined warp to functional data
    command = ["applywarp", "--ref=" + standard_nii_full, "--in=" + input_nii, "--warp=" + func2standard_warp, "--out=" + output_nii, "--interp=sinc"]
    print("Running applywarp (func to standard):", command)
    subprocess.run(command, check=True)
    return output_nii


def registration_to_standard_2(input_nii, output_nii=None, standard_nii="$FSLDIR/data/standard/MNI152_T1_2mm.nii.gz"):
    """
    Runs FSL FLIRT for direct registration of fMRI to standard space (e.g., MNI) without T1.
    Args:
        input_nii (str): Path to the input NIfTI file (after motion correction).
        output_nii (str, optional): Path to the output registered NIfTI.
        standard_nii (str): Path to standard template (default: MNI 2mm).
    Returns:
        str: Path to the registered NIfTI file.

    # Example usage
input_file = "6_axial_rsfmri_eyes_open__msv21_stc_mc.nii.gz"
registered_file = registration_to_standard(input_file)
print(f"Registered file: {registered_file}")
    """
    # Expand FSLDIR environment variable for the standard template
    standard_nii = os.path.expandvars(standard_nii)
    check_file_exists(input_nii)
    check_file_exists(standard_nii)
    if output_nii is None:
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_nii = f"{base}_mni{ext}"

    # Step 1: Direct linear registration of fMRI to MNI space
    fMRI_to_MNI_mat = "fMRI_to_MNI.mat"
    command = [
        "flirt",
        "-in", input_nii,
        "-ref", os.path.expandvars(standard_nii),
        "-out", "linear_mni.nii.gz",
        "-omat", fMRI_to_MNI_mat,
        "-bins", "256",
        "-cost", "corratio",
        "-searchrx", "-90", "90",
        "-searchry", "-90", "90",
        "-searchrz", "-90", "90",
        "-dof", "12"
    ]
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)

    # Step 2: Nonlinear registration with fnirt to refine alignment
    command = [
        "fnirt",
        "--in=" + input_nii,
        "--ref=" + os.path.expandvars(standard_nii),  # Expand $FSLDIR here
        "--aff=" + fMRI_to_MNI_mat,
        "--iout=" + output_nii,
        "--config=" + os.path.expandvars("$FSLDIR/etc/flirtsch/T1_2_MNI152_2mm.cnf")  # Expand config path
    ]
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)

    return output_nii




def create_brain_mask(input_nii, output_prefix=None, frac=0.3):
    """
    Generates a skull-stripped image and brain mask using FSL BET from a mean functional image.
    Args:
        input_nii (str): Path to 4D fMRI NIfTI file.
        output_prefix (str, optional): Prefix for the output files.
        frac (float): BET fractional intensity threshold (default 0.3).
    Returns:
        tuple: (path_to_skull_stripped_image, path_to_brain_mask)
    Example:
        brain_img, brain_mask = create_brain_mask("your_bandpass_file.nii.gz")
        print("Skull-stripped image:", brain_img)
        print("Brain mask:", brain_mask)

        # Example usage:
# brain_img, brain_mask = create_brain_mask("your_bandpass_file.nii.gz")
    """
    # Create mean image from 4D file
    # mean_img = input_nii.replace(".nii", "_mean.nii").replace(".gz", "_mean.nii.gz")
    base, ext = os.path.splitext(input_nii)
    if ext == '.gz':
        base, ext2 = os.path.splitext(base)
        ext = ext2 + ext
    mean_img = f"{base}_mean{ext}"
    subprocess.run(["fslmaths", input_nii, "-Tmean", mean_img], check=True)

    # Set prefix for BET outputs
    if output_prefix is None:
        # output_prefix = mean_img.replace(".nii", "_brain").replace(".gz", "_brain")  #-
        base, ext = os.path.splitext(input_nii)
        if ext == '.gz':
            base, ext2 = os.path.splitext(base)
            ext = ext2 + ext
        output_prefix = f"{base}_ss{ext}"


    # Run BET: will output output_prefix.nii.gz and output_prefix_mask.nii.gz
    subprocess.run(["bet", mean_img, output_prefix, "-m", "-f", str(frac)], check=True)

    # FSL BET output files
    skull_stripped_img = output_prefix #+ ".nii.gz"
    brain_mask = f"{base}_ss_mask{ext}" #output_prefix + "_mask.nii.gz"
    return skull_stripped_img, brain_mask

