# DataPreparation — Brain MRI Preprocessing Pipelines

A collection of Python pipelines for preparing **structural (T1-weighted)** and
**resting-state functional (fMRI)** brain MRI scans for downstream analysis and
machine learning. The scripts cover the full path from raw DICOM/NIfTI input to
standardized, brain-extracted, MNI-aligned images.

The pipelines were developed against public aging/Alzheimer's datasets
(**ADNI**, **NACC**, **UK Biobank**) but work with any T1 or BOLD NIfTI/DICOM
data.

> ⚠️ **Data is not included.** Medical imaging data is subject to Data Use
> Agreements that prohibit redistribution. See [Data & ethics](#data--ethics).

---

## What the pipelines do

### T1 structural preprocessing
Raw scan → standardized brain image, following these steps:

1. **Reorient** to a standard orientation (RAS/RAI) using ANTs / `fslreorient2std`
2. **N4 bias-field correction** (intensity non-uniformity) — SimpleITK
3. **Resample** to isotropic 1×1×1 mm³ voxels (linear interpolation)
4. **Denoise + intensity normalize** — ANTs
5. **Rigid registration** to the MNI152 template
6. **Brain extraction / skull stripping** — [HD-BET](https://github.com/MIC-DKFZ/HD-BET)

### Resting-state fMRI preprocessing
DICOM → analysis-ready BOLD series:

slice-timing correction → motion correction (MCFLIRT) → BET brain extraction →
spatial smoothing → intensity normalization → (optional temporal filtering) →
ICA denoising (MELODIC / ICA-AROMA) → registration to standard space (FLIRT/FNIRT).

---

## Repository layout

```
.
├── t1_adni_preprocess.py          # ADNI: pick 1 T1/subject, DICOM→NIfTI, full T1 pipeline
├── t1_ants_preprocess.py          # Minimal ANTs-based T1 pipeline
├── t1_batch_preprocess.py         # Batch-process a folder of NIfTI files (paper-spec pipeline)
├── t1_pipeline.py                 # Reusable T1 step functions (N4, resample, register, HD-BET…)
├── t1_utils.py                    # DICOM I/O helpers for structural scans
│
├── fmri_preprocess.py             # End-to-end fMRI pipeline for one subject
├── fmri_utils.py                  # FSL/ANTs command wrappers for fMRI steps
│
├── requirements.txt               # Python dependencies
├── T1_README.md                   # Detailed notes for the T1 paper pipeline
├── FMRI_README.md                 # Detailed notes for the resting-state fMRI pipeline
├── USER_GUIDE.md                  # Step-by-step usage guide
└── LICENSE
```

**Not committed** (see [.gitignore](.gitignore)): imaging data, generated
outputs, and any `.nii/.nii.gz/.dcm` files. Medical imaging data must never be
added to the repository — see [Data & ethics](#data--ethics).

---

## Installation

### 1. Python dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. External neuroimaging tools
Several steps shell out to external tools that are **not** pip-installable and
must be on your `PATH`:

| Tool | Used for | Install |
|------|----------|---------|
| **FSL** | slicetimer, mcflirt, bet, fslmaths, flirt, fnirt, melodic | https://fsl.fmrib.ox.ac.uk |
| **ANTs** | reorientation, registration, segmentation | https://github.com/ANTsX/ANTs |
| **HD-BET** | deep-learning brain extraction | `pip install HD-BET` |
| **ICA-AROMA** | automated fMRI ICA denoising | https://github.com/maartenmennes/ICA-AROMA |

Set the standard environment variables where applicable:
```bash
export FSLDIR=/path/to/fsl
export ANTSPATH=/path/to/ants/bin
```

---

## Quick start

Every script has a **`CONFIG` block** (near the top or bottom of the file)
with the input/output paths — edit those to point at your data, then run:

```bash
# Structural (T1)
python t1_batch_preprocess.py       # batch a folder of NIfTI T1s (paper-spec pipeline)
python t1_ants_preprocess.py      # minimal ANTs-based pipeline

# Functional (fMRI), single subject
python fmri_preprocess.py
```

See **[USER_GUIDE.md](USER_GUIDE.md)** for detailed, step-by-step instructions,
**[T1_README.md](T1_README.md)** for the paper-based
T1 pipeline, and **[FMRI_README.md](FMRI_README.md)**
for the resting-state fMRI pipeline.

---

## Data & ethics

- **No imaging data is distributed with this repository.** ADNI, NACC, and
  UK Biobank data are governed by Data Use Agreements that prohibit
  redistribution. Obtain data through the official channels:
  [ADNI](https://adni.loni.usc.edu/), [NACC](https://naccdata.org/),
  [UK Biobank](https://www.ukbiobank.ac.uk/).
- Do not commit imaging data, generated outputs, or any `.nii/.nii.gz/.dcm`
  files — these are excluded by `.gitignore`. Keep patient/subject identifiers
  out of commits.
- External tools such as **ICA-AROMA** are third-party software with their own
  licenses — install them from their upstream sources rather than vendoring them
  into this repository.

---

## License

Released under the [MIT License](LICENSE) for the original code in this
repository. Third-party tools and atlases retain their own respective licenses.
