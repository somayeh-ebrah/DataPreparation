# Resting-State fMRI Preprocessing Pipeline

End-to-end preprocessing of resting-state functional MRI (BOLD) data, from raw
DICOM to a denoised, MNI-registered 4D time series. The pipeline is a thin
orchestration script (`fmri_preprocess.py`) on top of a library of
FSL/ANTs command wrappers (`fmri_utils.py`).

For the structural counterpart see [T1_README.md](T1_README.md),
and for the project overview see [README.md](README.md).

---

## Pipeline overview

```
DICOM series
   │  dicom2nifti
   ▼
4D BOLD NIfTI
   ▼
1. Slice-timing correction   (FSL slicetimer)
2. Motion correction         (FSL mcflirt)      → also writes .par motion params
3. Brain extraction (BET)    (FSL bet)          → also writes _mask.nii.gz
4. Spatial smoothing         (FSL fslmaths -s)  → 6 mm FWHM Gaussian
5. Intensity normalization   (FSL fslmaths -ing)→ grand-mean scaling
6. Temporal filtering        (FSL fslmaths -bptf) [optional, off by default]
7. ICA denoising             (FSL melodic / ICA-AROMA)
8. Registration to standard  (FSL flirt + fnirt)→ func → struct → MNI152
   ▼
Preprocessed BOLD in MNI space
```

---

## Files

| File | Role |
|------|------|
| `fmri_preprocess.py` | Main driver — runs the full pipeline for one subject |
| `fmri_utils.py` | Step functions (FSL/ANTs wrappers); importable and reusable |

---

## Requirements

- Python deps: `pip install -r requirements.txt` (uses `dicom2nifti`, `nibabel`)
- **FSL** on `PATH`, with `FSLDIR` set — provides `slicetimer`, `mcflirt`,
  `bet`, `fslmaths`, `flirt`, `fnirt`, `melodic`
- **ANTs** on `PATH` (optional; only for the ANTs brain-extraction helper),
  with `ANTSPATH` set
- **ICA-AROMA** (optional) for automated ICA denoising —
  https://github.com/maartenmennes/ICA-AROMA
- An **MNI152 template** under `$FSLDIR/data/standard/` (ships with FSL)

Verify the tools resolve before running:
```bash
which slicetimer mcflirt bet fslmaths flirt fnirt melodic
echo "$FSLDIR"
```

---

## Configuration

`fmri_preprocess.py` has a `CONFIG` block near the top — edit it before
running:

```python
# === CONFIG: edit these for your setup ===
ANTS_BIN       = "/path/to/ANTs/install/bin"              # prepended to PATH if it exists
ROOT_DIR       = "data/subject_dicom_folder"              # folder containing the subject's DICOMs
OUTPUT_ROOT    = "./outputs/temp_preprocessed"            # where intermediates/outputs are written
STRUCTURAL_NII = "./outputs/temp_preprocessedBrainExtractionBrain.nii.gz"  # skull-stripped T1 target
TR_SECONDS     = 2          # repetition time in seconds; set to None to read from the NIfTI header
```

> The structural registration target (`STRUCTURAL_NII`) must **already exist** —
> preprocess/skull-strip the subject's T1 first (see the T1 pipeline).

---

## Usage

```bash
python fmri_preprocess.py
```

The script will:
1. Walk `ROOT_DIR` for DICOM folders.
2. Convert the first subject's DICOMs to NIfTI.
3. Run steps 1–8 in order, printing each intermediate file path and checking
   that critical outputs were produced.

### Processing one vs. all subjects
By default the loop processes only the **first** discovered DICOM folder:

```python
for d in [dicom_dirs[0]]:
```

To batch every subject, change it to:

```python
for d in dicom_dirs:
```

---

## Outputs

Written under `OUTPUT_ROOT`, the intermediates form a suffix chain on the input
name:

| Suffix | Produced by | Contents |
|--------|-------------|----------|
| `_stc` | slice-timing correction | timing-corrected BOLD |
| `_mc` | motion correction | realigned BOLD (+ `.par` motion params) |
| `_bet` | brain extraction | skull-stripped BOLD (+ `_mask.nii.gz`) |
| `_smooth` | smoothing | spatially smoothed BOLD |
| `_norm` | normalization | intensity-normalized BOLD |
| `_denoised` | ICA denoising | denoised BOLD (see caveat below) |
| `_reg` | registration | BOLD resampled into MNI152 space |

All outputs are git-ignored — keep them out of version control.

---

## Reusing individual steps

Every step is a standalone function in `fmri_utils.py` returning the path it
produced, so you can build a custom pipeline:

```python
from fmri_utils import (
    slice_time_correct_fmri, motion_correct_fmri, bet_brain_extraction,
    spatial_smoothing, intensity_normalization, temporal_filtering,
    temporal_bandpass_fmri, ica_denoising, registration_to_standard,
)

stc   = slice_time_correct_fmri("bold.nii.gz", tr=2.0, slice_order="ascending")
mc    = motion_correct_fmri(stc)
bet   = bet_brain_extraction(mc, frac_intensity=0.5)
sm    = spatial_smoothing(bet, fwhm=6.0)
norm  = intensity_normalization(sm, mean_intensity=10000)
den   = ica_denoising(norm)
reg   = registration_to_standard(den, "T1_brain.nii.gz")
```

---

## Caveats / known limitations

- **ICA denoising (step 7) is a placeholder.** `ica_denoising()` runs MELODIC
  and then copies the input through unchanged — it does not yet remove noise
  components automatically. Classify components manually, or wire up
  [ICA-AROMA](https://github.com/maartenmennes/ICA-AROMA).
- **Single subject by default** — see [the loop note](#processing-one-vs-all-subjects).
- **Structural target required** — `STRUCTURAL_NII` must point at an existing
  skull-stripped T1; the script does not create it.
- The first NIfTI load only prints diagnostics (shape, header, TR); the TR used
  downstream comes from `TR_SECONDS`.

---

## Troubleshooting

**`command not found` (slicetimer, flirt, …)** — FSL isn't on `PATH`; check the
install and that `FSLDIR` is exported in the shell running the script.

**Registration looks wrong / fails** — confirm `STRUCTURAL_NII` is skull-stripped
and that an MNI152 template exists under `$FSLDIR/data/standard/`.

**`IndexError` on `dicom_dirs[0]`** — no DICOM folders were found under
`ROOT_DIR`; check the path and that files end in `.dcm`.
