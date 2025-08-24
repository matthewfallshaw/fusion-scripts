# Export Components to STEP

A Fusion 360 add-in that exports each component or configuration to separate STEP files.

## Features

- Export each component in the active design to separate STEP files
- Export each configuration in the active design to separate STEP files
- Automatically names files based on component or configuration names
- Removes version suffixes (like _v1, _v42) from filenames for cleaner output
- Adds buttons to the Utilities panel for easy access

## Installation

For installation instructions, see: https://tapnair.github.io/installation.html

## Usage

### Export Components
1. Open a design with multiple components in Fusion 360
2. Click the "Export Components to STEP" button in the Utilities panel
3. Each component will be exported as a separate STEP file

### Export Configurations
1. Open a configured design in Fusion 360
2. Click the "Export Configurations to STEP" button in the Utilities panel
3. Each configuration will be exported as a separate STEP file

## Output

- You'll be prompted to select a folder for the STEP files (defaults to Downloads)
- Files are named based on component/configuration names with version suffixes removed
- Success/failure messages are displayed after export completion

## Requirements

- Autodesk Fusion 360
- Python support enabled in Fusion 360