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
from typing import Any, List, cast

sys.path.append(os.path.abspath(
    '~/Library/Application Support/Autodesk/webdeploy/pre-production/'
    'Autodesk Fusion [pre-production].app/Contents/Api/Python/packages/adsk'
))

import adsk.cam
import adsk.core
import adsk.fusion

# This list will hold the event handlers.
handlers: List[Any] = []


def strip_version_from_name(name: str) -> str:
    """Remove version suffixes like _v1, _v42, etc. from component names."""
    import re

    # Remove patterns like _v1, _v42, _v123, or v1, v42, v123 from the end of the name
    # This handles both underscore and space prefixes
    return re.sub(r'[_\s]v\d+$', '', name)


def exportComponentsToStep() -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    design = cast(adsk.fusion.Design, app.activeProduct)
    rootComp = design.rootComponent

    # Check for visible components first
    visible_components = []
    for occurrence in rootComp.occurrences:
        if occurrence.isVisible:
            visible_components.append(occurrence)

    # Check for bodies if no components found
    visible_bodies = []
    if not visible_components:
        for body in rootComp.bRepBodies:
            if body.isVisible:
                visible_bodies.append(body)

    # If neither components nor bodies found, show message and return
    if not visible_components and not visible_bodies:
        ui.messageBox('No visible components or bodies found to export.')
        return

    # Create a folder dialog
    folderDialog = ui.createFolderDialog()
    folderDialog.title = "Select folder for STEP files"
    folderDialog.initialDirectory = os.path.expanduser("~") + "/Downloads"
    dialogResult = folderDialog.showDialog()

    try:
        if str(dialogResult) == str(adsk.core.DialogResults.DialogOK):
            # Get the selected directory directly
            directory = folderDialog.folder
            exportMgr = design.exportManager
            exported_count = 0

            # Export components if available, otherwise export bodies
            if visible_components:
                for occurrence in visible_components:
                    # Create a full file path for the STEP file.
                    clean_name = strip_version_from_name(occurrence.component.name)
                    filename = os.path.join(directory, clean_name + '.step')
                    stepExportOptions = exportMgr.createSTEPExportOptions(filename, occurrence.component)
                    try:
                        exportMgr.execute(stepExportOptions)
                        exported_count += 1
                    except Exception as e:
                        ui.messageBox(f'Error exporting component {occurrence.component.name}: {str(e)}')
                        return

                if exported_count > 0:
                    ui.messageBox(f'{exported_count} visible components exported to STEP files successfully.')
                else:
                    ui.messageBox('No components were exported.')
            else:
                # Export bodies - export the entire design as a single STEP file
                # This is more reliable than trying to export individual bodies
                clean_name = strip_version_from_name(rootComp.name)
                filename = os.path.join(directory, f"{clean_name}.step")
                stepExportOptions = exportMgr.createSTEPExportOptions(filename, rootComp)
                try:
                    exportMgr.execute(stepExportOptions)
                    exported_count = 1
                    ui.messageBox(f'Design exported to STEP file successfully: {filename}')
                except Exception as e:
                    ui.messageBox(f'Error exporting design: {str(e)}')
                    return
        else:
            ui.messageBox('No directory selected.')
    except Exception as e:
        ui.messageBox('Failed:\n{}'.format(str(e)))

def exportConfigurationsToStep() -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Create a folder dialog
    folderDialog = ui.createFolderDialog()
    folderDialog.title = "Select folder for STEP files"
    folderDialog.initialDirectory = os.path.expanduser("~") + "/Downloads"
    dialogResult = folderDialog.showDialog()

    try:
        if str(dialogResult) == str(adsk.core.DialogResults.DialogOK):
            # Get the selected directory directly
            directory = folderDialog.folder

            design = cast(adsk.fusion.Design, app.activeProduct)

            # Check if the design is a configured design
            if not design.isConfiguredDesign:
                ui.messageBox('The active design is not a configured design.')
                return

            # Get the configuration top table
            topTable = design.configurationTopTable

            # Get the current active configuration
            currentRow = topTable.activeRow

            # Get the design name for the file naming
            designName = design.rootComponent.name

            exportMgr = design.exportManager
            exported_count = 0

            # Iterate through all configurations
            for row in topTable.rows:
                # Activate this configuration
                row.activate()

                # Create a full file path for the STEP file
                clean_name = strip_version_from_name(designName)
                filename = os.path.join(directory, f"{clean_name}_{row.name}.step")

                # Create STEP export options for the entire design
                stepExportOptions = exportMgr.createSTEPExportOptions(filename, design.rootComponent)

                try:
                    exportMgr.execute(stepExportOptions)
                    exported_count += 1
                except Exception as e:
                    ui.messageBox(f'Error exporting configuration {row.name}: {str(e)}')

            # Restore the original configuration
            currentRow.activate()

            if exported_count > 0:
                ui.messageBox(f'{exported_count} configurations exported to STEP files successfully.')
            else:
                ui.messageBox('No configurations found to export.')
        else:
            ui.messageBox('No directory selected.')
    except Exception as e:
        ui.messageBox('Failed:\n{}'.format(str(e)))

class ExportComponentsToStepCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, eventArgs: adsk.core.CommandCreatedEventArgs) -> None:
        onExecute = ExportComponentsToStepExecuteHandler()
        eventArgs.command.execute.add(onExecute)
        handlers.append(onExecute)

class ExportComponentsToStepExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, eventArgs: adsk.core.CommandEventArgs) -> None:
        exportComponentsToStep()

class ExportConfigurationsToStepCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, eventArgs: adsk.core.CommandCreatedEventArgs) -> None:
        onExecute = ExportConfigurationsToStepExecuteHandler()
        eventArgs.command.execute.add(onExecute)
        handlers.append(onExecute)

class ExportConfigurationsToStepExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, eventArgs: adsk.core.CommandEventArgs) -> None:
        exportConfigurationsToStep()

def run(context: Any) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    cmdDefs = ui.commandDefinitions

    # Create button for exporting components
    exportComponentsToStepButton = cmdDefs.addButtonDefinition(
        'ExportComponentsToStep_ID', 'Export Components to STEP',
        'Export each component to a separate STEP file.',
        './resources'
    )

    exportComponentsToStepCreated = ExportComponentsToStepCreatedEventHandler()
    exportComponentsToStepButton.commandCreated.add(exportComponentsToStepCreated)
    handlers.append(exportComponentsToStepCreated)

    # Create button for exporting configurations
    exportConfigurationsToStepButton = cmdDefs.addButtonDefinition(
        'ExportConfigurationsToStep_ID', 'Export Configurations to STEP',
        'Export each configuration to a separate STEP file.',
        './resources'
    )

    exportConfigurationsToStepCreated = ExportConfigurationsToStepCreatedEventHandler()
    exportConfigurationsToStepButton.commandCreated.add(exportConfigurationsToStepCreated)
    handlers.append(exportConfigurationsToStepCreated)

    designWS = ui.workspaces.itemById('FusionSolidEnvironment')
    addInsPanel = designWS.toolbarPanels.itemById('SolidScriptsAddinsPanel')

    # Add both buttons to the panel
    addInsPanel.controls.addCommand(exportComponentsToStepButton)
    addInsPanel.controls.addCommand(exportConfigurationsToStepButton)

def stop(context: Any) -> None:
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

    for handler in handlers:
        handler.deleteMe()
    handlers.clear()