"""
This Fusion 360 add-in provides buttons on the Utilities panel that, when clicked,
exports each Component in the active design to a separate STEP file, or exports each
Configuration in the active design to a separate STEP file.

The add-in works as follows:
1. When loaded, it adds buttons to the Utilities panel.
2. When a button is clicked, it triggers the execution of the command.
3. For Components export:
   - The command iterates over all the Components in the active design.
   - For each Component, it creates a STEP export options object with the
     Component's name as the filename.
   - It then executes the export operation, creating a STEP file for the Component.
4. For Configurations export:
   - The command iterates over all the Configurations in the active design.
   - For each Configuration, it activates that Configuration and exports the
     entire design as a STEP file.
   - It then returns to the original Configuration.
5. If the export operation is successful, it shows a message box saying that the
   Components/Configurations were exported successfully.
6. If an error occurs at any point, it shows a message box with the error message.
7. When the add-in is unloaded, it removes the buttons from the Utilities panel
   and cleans up the event handlers.

This add-in is written in Python and uses the Autodesk Fusion 360 API.
"""

import os
import sys
import time
from typing import Any, Callable, Dict, List, cast

sys.path.append(os.path.abspath(
    '~/Library/Application Support/Autodesk/webdeploy/pre-production/'
    'Autodesk Fusion [pre-production].app/Contents/Api/Python/packages/adsk'
))

import adsk.core
import adsk.fusion

handlers: List[Any] = []


def strip_version_from_name(name: str) -> str:
    """Remove version suffixes like _v1, _v42, etc. from component names."""
    import re

    return re.sub(r'[_\s]v\d+$', '', name)


def collect_visible_components(design: adsk.fusion.Design) -> List[Dict[str, Any]]:
    """Collector: Get visible components from the design."""
    app = adsk.core.Application.get()
    ui = app.userInterface
    textPalette = ui.palettes.itemById('TextCommands')
    textPalette.isVisible = True

    start_time = time.time()
    rootComp = design.rootComponent
    components = []

    textPalette.writeText(f"Starting optimized collection of {rootComp.occurrences.count} occurrences...")

    for occurrence in rootComp.occurrences:
        if occurrence.isVisible:
            filename = get_component_filename(occurrence)

            components.append({
                'item': occurrence,
                'filename': filename,
                'export_target': occurrence.component
            })

    total_time = time.time() - start_time
    textPalette.writeText(f"Optimized collection completed: {len(components)} components in {total_time:.3f}s")
    return components


def collect_configurations(design: adsk.fusion.Design) -> List[Dict[str, Any]]:
    """Collector: Get configurations from the design."""
    if not design.isConfiguredDesign:
        return []

    topTable = design.configurationTopTable
    currentRow = topTable.activeRow
    designName = design.rootComponent.name

    def make_activator(row: adsk.fusion.ConfigurationRow) -> Callable[[], None]:
        """Create a closure that activates a specific configuration row."""
        return lambda: row.activate()

    configurations = []
    for row in topTable.rows:
        configurations.append({
            'item': row,
            'filename': f"{strip_version_from_name(designName)}_{row.name}",
            'export_target': design.rootComponent,
            'setup_fn': make_activator(row),
            'cleanup_fn': make_activator(currentRow)
        })
    return configurations


def collect_bodies_fallback(design: adsk.fusion.Design) -> List[Dict[str, Any]]:
    """Collector: Get bodies as fallback when no components exist."""
    rootComp = design.rootComponent
    bodies = []
    for body in rootComp.bRepBodies:
        if body.isVisible:
            bodies.append({
                'item': body,
                'filename': strip_version_from_name(rootComp.name),
                'export_target': rootComp
            })
    return bodies


def get_component_filename(occurrence: adsk.fusion.Occurrence) -> str:
    """Get the appropriate filename for a component occurrence - optimized version.

    The Fusion API is crazy - here's what each property actually gives us:
    - occurrence.configuredDataFile.name: "cake tin asy v9" (actual underlying component)
    - occurrence.name: "top v23:1" (config name + instance number)
    - occurrence.component.name: "top v23" (just the config name, no instance)
    """
    if occurrence.isConfiguration:
        # For configurations, we want: "actual_component.config_name"
        config_name_with_version = occurrence.component.name  # "top v23"

        try:
            # This is the SLOW call (~0.3s) but gives actual component name
            actual_component_name = occurrence.configuredDataFile.name  # "cake tin asy v9"

            # Extract the config name by removing version suffix from component name
            # "top v23" -> "top", "A v1" -> "A"
            config_name = strip_version_from_name(config_name_with_version)  # "top"

            return f"{strip_version_from_name(actual_component_name)}.{config_name}"
        except Exception:
            # Fallback to config name if configuredDataFile fails
            return strip_version_from_name(config_name_with_version)
    else:
        # Regular occurrence - just use component name
        regular_component_name = occurrence.component.name
        return strip_version_from_name(regular_component_name)


def create_export_options(filename: str,
                          target: Any,
                          export_format: str,
                          exportMgr: adsk.fusion.ExportManager) -> Any:
    """Factory function to create appropriate export options based on format."""
    if export_format.upper() == 'STEP':
        return exportMgr.createSTEPExportOptions(filename, target)
    elif export_format.upper() == '3MF':
        return exportMgr.createC3MFExportOptions(filename, target)
    else:
        raise ValueError(f'Unsupported export format: {export_format}')


def export_items(items: List[Dict[str, Any]],
                 directory: str,
                 export_format: str,
                 exportMgr: adsk.fusion.ExportManager,
                 ui: adsk.core.UserInterface,
                 skip_duplicates: bool = True) -> int:
    """Exporter: Export a collection of items with deduplication."""
    if not items:
        return 0

    used_filenames: set = set()
    exported_count = 0
    cleanup_functions = []

    try:
        for item_data in items:
            filename_base = item_data['filename']

            # Skip duplicates if requested
            if skip_duplicates and filename_base in used_filenames:
                continue

            if skip_duplicates:
                used_filenames.add(filename_base)

            filename = os.path.join(
                directory,
                filename_base + f'.{export_format.lower()}'
            )

            # Run setup function if provided (e.g., activate configuration)
            if 'setup_fn' in item_data:
                item_data['setup_fn']()
                if 'cleanup_fn' in item_data:
                    cleanup_functions.append(item_data['cleanup_fn'])

            # Create and execute export
            try:
                exportOptions = create_export_options(
                    filename,
                    item_data['export_target'],
                    export_format,
                    exportMgr
                )
                exportMgr.execute(exportOptions)
                exported_count += 1
            except Exception as e:
                ui.messageBox(f'Error exporting {filename_base}: {str(e)}')
                return 0

    finally:
        # Run cleanup functions in reverse order
        for cleanup_fn in reversed(cleanup_functions):
            try:
                cleanup_fn()
            except Exception:
                pass  # Don't let cleanup errors break the export

    return exported_count


def export_with_collector(collector_fn: Callable[[adsk.fusion.Design], List[Dict[str, Any]]],
                          export_format: str,
                          dialog_title: str) -> None:
    """Generic export function using collector functions."""
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = cast(adsk.fusion.Design, app.activeProduct)

    # Collect items to export
    start_time = time.time()
    textPalette = ui.palettes.itemById('TextCommands')
    textPalette.isVisible = True
    textPalette.writeText(f"Starting {export_format} export process...")

    collection_start = time.time()
    items = collector_fn(design)
    collection_time = time.time() - collection_start
    textPalette.writeText(f"Primary collection took {collection_time:.3f}s")

    # Try fallback collectors if primary collector returns nothing
    if not items and collector_fn == collect_visible_components:
        fallback_start = time.time()
        items = collect_bodies_fallback(design)
        fallback_time = time.time() - fallback_start
        textPalette.writeText(f"Fallback collection took {fallback_time:.3f}s")

    if not items:
        ui.messageBox('No items found to export.')
        return

    # Create a folder dialog
    folderDialog = ui.createFolderDialog()
    folderDialog.title = dialog_title
    folderDialog.initialDirectory = os.path.expanduser("~") + "/Downloads"
    dialogResult = folderDialog.showDialog()

    try:
        if str(dialogResult) == str(adsk.core.DialogResults.DialogOK):
            directory = folderDialog.folder
            exportMgr = design.exportManager

            export_start = time.time()
            exported_count = export_items(
                items, directory, export_format, exportMgr, ui
            )
            export_time = time.time() - export_start
            textPalette.writeText(f"Export execution took {export_time:.3f}s")

            if exported_count > 0:
                ui.messageBox(
                    f'{exported_count} items exported to {export_format} files successfully.'
                )
            else:
                ui.messageBox('No items were exported.')
        else:
            ui.messageBox('No directory selected.')
    except Exception as e:
        ui.messageBox('Failed:\n{}'.format(str(e)))

    total_time = time.time() - start_time
    textPalette.writeText(f"Total export process took {total_time:.3f}s")


def exportComponentsToStep() -> None:
    export_with_collector(
        collect_visible_components,
        'STEP',
        'Select folder for STEP files'
    )


def exportComponentsTo3MF() -> None:
    export_with_collector(
        collect_visible_components,
        '3MF',
        'Select folder for 3MF files'
    )


def exportConfigurationsToStep() -> None:
    export_with_collector(
        collect_configurations,
        'STEP',
        'Select folder for STEP files'
    )


class ExportComponentsToStepCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, eventArgs: adsk.core.CommandCreatedEventArgs) -> None:
        onExecute = ExportComponentsToStepExecuteHandler()
        eventArgs.command.execute.add(onExecute)
        handlers.append(onExecute)


class ExportComponentsToStepExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, _eventArgs: adsk.core.CommandEventArgs) -> None:
        exportComponentsToStep()


class ExportConfigurationsToStepCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, eventArgs: adsk.core.CommandCreatedEventArgs) -> None:
        onExecute = ExportConfigurationsToStepExecuteHandler()
        eventArgs.command.execute.add(onExecute)
        handlers.append(onExecute)


class ExportConfigurationsToStepExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, _eventArgs: adsk.core.CommandEventArgs) -> None:
        exportConfigurationsToStep()


class ExportComponentsTo3MFCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, eventArgs: adsk.core.CommandCreatedEventArgs) -> None:
        onExecute = ExportComponentsTo3MFExecuteHandler()
        eventArgs.command.execute.add(onExecute)
        handlers.append(onExecute)


class ExportComponentsTo3MFExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, _eventArgs: adsk.core.CommandEventArgs) -> None:
        exportComponentsTo3MF()


def run(_context: Any) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    cmdDefs = ui.commandDefinitions

    # Create button for exporting components
    exportComponentsToStepButton = cmdDefs.addButtonDefinition(
        'ExportComponentsToStep_ID',
        'Export Components to STEP',
        'Export each component to a separate STEP file.',
        './resources/step'
    )

    exportComponentsToStepCreated = ExportComponentsToStepCreatedEventHandler()
    exportComponentsToStepButton.commandCreated.add(exportComponentsToStepCreated)
    handlers.append(exportComponentsToStepCreated)

    # Create button for exporting configurations
    exportConfigurationsToStepButton = cmdDefs.addButtonDefinition(
        'ExportConfigurationsToStep_ID',
        'Export Configurations to STEP',
        'Export each configuration to a separate STEP file.',
        './resources/step'
    )

    exportConfigurationsToStepCreated = ExportConfigurationsToStepCreatedEventHandler()
    exportConfigurationsToStepButton.commandCreated.add(exportConfigurationsToStepCreated)
    handlers.append(exportConfigurationsToStepCreated)

    # Create button for exporting components to 3MF
    exportComponentsTo3MFButton = cmdDefs.addButtonDefinition(
        'ExportComponentsTo3MF_ID',
        'Export Components to 3MF',
        'Export each component to a separate 3MF file.',
        './resources/3mf'
    )

    exportComponentsTo3MFCreated = ExportComponentsTo3MFCreatedEventHandler()
    exportComponentsTo3MFButton.commandCreated.add(exportComponentsTo3MFCreated)
    handlers.append(exportComponentsTo3MFCreated)

    designWS = ui.workspaces.itemById('FusionSolidEnvironment')
    addInsPanel = designWS.toolbarPanels.itemById('SolidScriptsAddinsPanel')

    # Add all buttons to the panel
    addInsPanel.controls.addCommand(exportComponentsToStepButton)
    addInsPanel.controls.addCommand(exportConfigurationsToStepButton)
    addInsPanel.controls.addCommand(exportComponentsTo3MFButton)


def stop(_context: Any) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Remove the components export button
    cmdDef = ui.commandDefinitions.itemById('ExportComponentsToStep_ID')
    if cmdDef:
        cmdDef.deleteMe()

    # Remove the configurations export button
    cmdDef = ui.commandDefinitions.itemById('ExportConfigurationsToStep_ID')
    if cmdDef:
        cmdDef.deleteMe()

    # Remove the 3MF export button
    cmdDef = ui.commandDefinitions.itemById('ExportComponentsTo3MF_ID')
    if cmdDef:
        cmdDef.deleteMe()

    designWS = ui.workspaces.itemById('FusionSolidEnvironment')
    addInsPanel = designWS.toolbarPanels.itemById('SolidScriptsAddinsPanel')

    # Remove the components export control
    cmdControl = addInsPanel.controls.itemById('ExportComponentsToStep_ID')
    if cmdControl:
        cmdControl.deleteMe()

    # Remove the configurations export control
    cmdControl = addInsPanel.controls.itemById('ExportConfigurationsToStep_ID')
    if cmdControl:
        cmdControl.deleteMe()

    # Remove the 3MF export control
    cmdControl = addInsPanel.controls.itemById('ExportComponentsTo3MF_ID')
    if cmdControl:
        cmdControl.deleteMe()

    # Event handlers don't have deleteMe() - just clear the list
    handlers.clear()
