import pydicom
import os
import numpy as np
import nibabel as nib

def read_dicom_files_for_subject(scan_path):
    """
    Read all DICOM files in the given folder for a single subject.
    Returns a list of dictionaries containing metadata and pixel data for each file.
    """
    dicom_files = []

    # Check if the directory exists
    if not os.path.exists(scan_path):
        print(f"Directory not found: {scan_path}")
        return dicom_files

    # Iterate through files in the directory
    for filename in os.listdir(scan_path):
        if filename.lower().endswith('.dcm'):
            file_path = os.path.join(scan_path, filename)
            try:
                # Read DICOM file
                dicom = pydicom.dcmread(file_path)

                # Extract relevant metadata
                metadata = {
                    'PatientID': getattr(dicom, 'PatientID', 'N/A'),
                    'StudyDate': getattr(dicom, 'StudyDate', 'N/A'),
                    'SeriesDescription': getattr(dicom, 'SeriesDescription', 'N/A'),
                    'Modality': getattr(dicom, 'Modality', 'N/A'),
                    'FilePath': file_path
                }

                # Optionally extract pixel data (if needed)
                pixel_data = None
                if hasattr(dicom, 'PixelData'):
                    pixel_data = dicom.pixel_array  # Returns numpy array

                dicom_files.append({
                    'metadata': metadata,
                    'pixel_data': pixel_data
                })

            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    return dicom_files


def load_dicom_series(dicom_dir):
    """
    Load a DICOM series from a folder and return a nibabel NIfTI image.
    Constructs a proper affine using DICOM tags with robust fallback.
    Returns None if loading fails.
    """
    try:
        import pydicom
        import numpy as np
        import os
        # Collect all DICOM files
        dicom_files = [os.path.join(dicom_dir, f) for f in os.listdir(dicom_dir) if f.lower().endswith('.dcm')]
        if not dicom_files:
            print(f"No DICOM files found in {dicom_dir}")
            return None

        # Read and sort DICOM files by InstanceNumber or SliceLocation
        slices = []
        for f in dicom_files:
            dcm = pydicom.dcmread(f)
            if hasattr(dcm, 'PixelData'):
                instance_num = dcm.get('InstanceNumber', dcm.get('SliceLocation', 0))
                slices.append((f, dcm, instance_num))

        if not slices:
            print(f"No valid DICOM slices found in {dicom_dir}")
            return None

        slices.sort(key=lambda x: x[2])  # Sort by instance number

        # Stack pixel data into 3D array (height, width, slices)
        pixel_array = np.stack([dcm.pixel_array.astype(np.float32) for _, dcm, _ in slices], axis=-1)

        # Use the first DICOM for metadata
        first_dcm = slices[0][1]

        # Extract DICOM tags for affine construction
        pixel_spacing = first_dcm.get('PixelSpacing', [1.0, 1.0])
        slice_thickness = first_dcm.get('SliceThickness', 1.0)
        orientation_patient = first_dcm.get('ImageOrientationPatient', [1, 0, 0, 0, 1, 0])
        position_patient = first_dcm.get('ImagePositionPatient', [0, 0, 0])

        # Log metadata for debugging
        print(f"DICOM metadata for {dicom_dir}:")
        print(f"  PixelSpacing: {pixel_spacing}")
        print(f"  SliceThickness: {slice_thickness}")
        print(f"  ImageOrientationPatient: {orientation_patient}")
        print(f"  ImagePositionPatient: {position_patient}")

        # Construct the affine matrix (LPS+ space, as per DICOM standard)
        affine = np.eye(4)

        # Row 0: X direction
        affine[0, :3] = np.array(orientation_patient[0:3]) * pixel_spacing[0]
        # Row 1: Y direction
        affine[1, :3] = np.array(orientation_patient[3:6]) * pixel_spacing[1]
        # Row 2: Z direction (compute from cross product if possible, or use fallback)
        try:
            row_vec = np.array(orientation_patient[0:3])
            col_vec = np.array(orientation_patient[3:6])
            slice_direction = np.cross(row_vec, col_vec)
            slice_direction = slice_direction / np.linalg.norm(slice_direction)  # Normalize
        except:
            slice_direction = np.array([0, 0, 1])  # Fallback
        affine[2, :3] = slice_direction * slice_thickness

        # Translation
        affine[:3, 3] = position_patient

        print(f"Constructed affine for {dicom_dir}:")
        print(affine)

        # Validate affine determinant
        det = np.linalg.det(affine[:3, :3])
        print(f"Affine determinant: {det}")
        if abs(det) < 1e-6:
            print(f"Warning: Singular affine matrix (det ≈ {det}). Using fallback affine.")
            affine = np.eye(4)
            affine[0, 0] = pixel_spacing[0] if pixel_spacing[0] > 0 else 1.0
            affine[1, 1] = pixel_spacing[1] if pixel_spacing[1] > 0 else 1.0
            affine[2, 2] = slice_thickness if slice_thickness > 0 else 1.0

        # Create NIfTI image
        nifti_img = nib.Nifti1Image(pixel_array, affine)
        _ = nifti_img.affine  # Validate affine

        # Log orientation
        orientation = nib.aff2axcodes(nifti_img.affine)
        print(f"Input image orientation: {orientation} (should be close to RAS+)")

        print(f"Successfully loaded DICOM series: shape {pixel_array.shape}, affine det {np.linalg.det(nifti_img.affine[:3, :3]):.3f}")
        return nifti_img

    except Exception as e:
        print(f"Error loading DICOM series from {dicom_dir}: {e}")
        import traceback
        traceback.print_exc()
        return None
