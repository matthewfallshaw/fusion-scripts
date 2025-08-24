# Fusion 360 Scripts and Add-ins

A collection of Fusion 360 add-ins that extend the software's functionality with custom tools and utilities.

See the README in each add-in directory for installation instructions.


## API Documentation Tools
- **[apidocs/](apidocs/)** - Command-line navigator for Fusion 360 API documentation

## API Documentation Navigator

The `apidocs` command provides access to Fusion 360 API documentation.

### Installation
```bash
# Install dependencies and console script
pip install -e .
```

### Usage
```bash
# List all documentation books
apidocs

# Show API reference objects
apidocs reference

# Show specific API object documentation
apidocs show GUID-9910880d-2299-4947-917a-39b5f030eef4

# Get C++ examples instead of Python (default)
apidocs --language cpp show GUID-0f6e9ca0-dc67-49c3-b902-baf881063e24

# Show User's Manual sections
apidocs manual
```