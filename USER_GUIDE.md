# User Guide

Step-by-step instructions for running the preprocessing pipelines. For a
high-level overview and installation, see [README.md](README.md).

## Contents
1. [Before you start](#1-before-you-start)
2. [Configuring paths](#2-configuring-paths)
3. [T1 structural preprocessing](#3-t1-structural-preprocessing)
4. [Resting-state fMRI preprocessing](#4-resting-state-fmri-preprocessing)
5. [Outputs](#5-outputs)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Before you start

Make sure the following are installed and available (see README for links):

- Python dependencies: `pip install -r requirements.txt`
- **FSL** on `PATH`, with `FSLDIR` set (fMRI steps + some T1 steps)
- **ANTs** on `PATH`, with `ANTSPATH` set (registration, segmentation)
- **HD-BET** (`pip install HD-BET`) for T1 brain extraction
- An **MNI152 template** (`MNI152_T1_1mm.nii.gz`), shipped with FSL under
  `$FSLDIR/data/standard/`

Verify the external tools resolve:
```bash
which slicetimer mcflirt bet fslmaths flirt fnirt melodic   # FSL
which antsRegistration N4BiasFieldCorrection                 # ANTs
hd-bet --help                                                # HD-BET
```

---

## 2. Configuring paths

These scripts are **research scripts driven by in-file configuration**, not a
CLI. Each one has a clearly marked block:

```python
# === CONFIG: edit these paths to match your setup ===
input_dir = Path("/path/to/input")
output_dir = Path("/path/to/output")
```

Open the script, edit the `CONFIG` block to point at your data, then run it.
The relevant paths per script are listed in the sections below.

> Tip: keep your data **outside** the repository folder (or under `data/` /
> `outputs/`, which are git-ignored) so you never accidentally commit scans.

---

## 3. T1 structural preprocessing

There are three entry points depending on your input format and needs.

### Option A — Full ADNI pipeline from DICOM (`t1_adni_preprocess.py`)
Selects one T1 scan per subject (subjects common to a T1 and an fMRI CSV
export), loads the DICOM series, and runs the full structural pipeline.

**CONFIG paths (bottom of file):** `root_dir` (DICOM root), `t1_csv_path`,
`fmri_csv_path`, `output_dir`.

```bash
python t1_adni_preprocess.py
```

### Option B — Batch a folder of NIfTI files (`t1_batch_preprocess.py`)
Runs the paper-spec pipeline (reorient → N4 → resample → MNI registration →
HD-BET) over every `*.nii.gz` found under the input directory.

**CONFIG paths:** `input_directory`, `output_directory` (in the
`if __name__ == "__main__"` block).

```bash
python t1_batch_preprocess.py
```

### Option C — Minimal ANTs pipeline (`t1_ants_preprocess.py`)
Reorient → N4 → denoise → resample, writing both a resampled and a normalized
copy. Lighter weight; no registration or skull stripping.

**CONFIG paths:** `input_dir`, `output_dir`, `output_dir_norm`.

```bash
python t1_ants_preprocess.py
```

### Reusable building blocks (`t1_pipeline.py`)
You can call individual steps directly:

```python
from t1_pipeline import paper_preprocessing_pipeline

paper_preprocessing_pipeline(
    nii_path="/data/sub-001_T1w.nii.gz",
    output_dir="/out",
    subject_id="sub-001",
)
```

Available functions: `reorient_to_ras_ants`, `n4_bias_field_correction_sitk`,
`resample_to_isotropic_sitk`, `rigid_registration_to_mni_sitk`,
`rigid_registration_to_mni_ants`, `fsl_reorient2std`, `brain_extraction_hd_bet`,
`find_mni_template`.

> **MNI template:** `find_mni_template()` looks in common locations. If your
> template lives elsewhere, edit the `possible_paths` list in that function in
> `t1_pipeline.py`.

---

## 4. Resting-state fMRI preprocessing

`fmri_preprocess.py` runs the full functional pipeline for one subject,
starting from DICOM.

**CONFIG block (top of file):**
- `ANTS_BIN` — local ANTs bin dir to prepend to `PATH` (ignored if not present)
- `ROOT_DIR` — folder containing the subject's DICOMs
- `OUTPUT_ROOT` — where intermediates/outputs are written
- `STRUCTURAL_NII` — skull-stripped structural image used as registration target
- `TR_SECONDS` — repetition time (set to `None` to read it from the NIfTI header)

```bash
python fmri_preprocess.py
```

The individual steps live in `fmri_utils.py` and can be reused:
`slice_time_correct_fmri`, `motion_correct_fmri`, `bet_brain_extraction`,
`ants_brain_extraction`, `spatial_smoothing`, `intensity_normalization`,
`temporal_filtering`, `temporal_bandpass_fmri`, `ica_denoising`,
`registration_to_standard`, `registration_to_standard_2`, `create_brain_mask`.

---

## 5. Outputs

- **T1 pipelines** write preprocessed `*.nii.gz` (and, where applicable,
  brain masks / normalized copies) into the configured output directory,
  organized by subject.
- **fMRI pipeline** writes a chain of intermediates under `OUTPUT_ROOT`
  (`*_stc`, `*_mc`, `*_bet`, `*_smooth`, `*_norm`, `*_denoised`, `*_reg`).

All of these are git-ignored — keep them out of version control.

---

## 6. Troubleshooting

**`command not found` (slicetimer, flirt, hd-bet, …)**
The external tool isn't on your `PATH`. Re-check the install steps and that
`FSLDIR` / `ANTSPATH` are exported in the shell that runs the script.

**MNI template not found**
T1 pipelines fall back to skipping registration if no template is found.
Install FSL (provides `$FSLDIR/data/standard/MNI152_T1_1mm.nii.gz`) or edit
`find_mni_template()` in `t1_pipeline.py`.

**HD-BET install issues**
```bash
pip install git+https://github.com/MIC-DKFZ/HD-BET.git
```

**Out-of-memory / very slow**
N4 correction, registration, and HD-BET are memory- and compute-intensive.
Process in smaller batches, and use a GPU for HD-BET where available.

**DICOM loading fails / wrong orientation**
`t1_utils.load_dicom_series` builds an affine from DICOM tags and falls back to
an identity affine for degenerate cases — inspect the printed affine and
orientation diagnostics it logs.
