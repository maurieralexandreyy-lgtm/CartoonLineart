# Cartoon Lineart for Maya

A fast and versatile cartoon lineart tool for Autodesk Maya. Create, deform, and style procedural stroke lines on 3D character meshes.

---

## Installation

Drag and drop **`installer.py`** (or **`cartoon_lineart.py`**) directly into the Maya 3D viewport. A shelf button with the tool icon will be created automatically.

---

## Features

- **Paint Mode**: Interactively draw lines directly on the surface of any target mesh.
- **Edge Conversion**: Turn selected polygon edges into procedural cartoon lines with one click.
- **Taper & Profile Styling**: Full control over line width, profile roundness, number of sides, rotation, and custom taper curve points.
- **Mesh Deformation & Follow**:
  - **Node based**: Fast edge-interpolation constraint.
  - **Wrap deformer**: Standard Maya wrap constraint.
  - **UV pin**: High-precision surface rivets driven by UV coordinates.
- **Smoothing & Displacement**: Procedural mesh smoothing and texture deformers (*noise*, *mountain*, *fractal*).
- **Symmetry**: Mirror lines cleanly across the symmetry plane (**L to R** / **R to L**) with automatic suffix handling (`_L` / `_R`).
- **Presets & Management**: Save, load, and delete custom line presets; copy and paste line attributes across multiple lines.
- **Selective Rebuild**: Rebuild specific subsets of properties (*UI elements*, *Custom attributes*, *Follow method*).
- **Bake**: Bake deformers into vertex animation for real-time viewport performance and export.

