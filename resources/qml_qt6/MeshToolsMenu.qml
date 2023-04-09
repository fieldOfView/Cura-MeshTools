// Copyright (c) 2023 Aldo Hoeben / fieldOfView
// MeshTools is released under the terms of the AGPLv3 or higher.

import QtQuick 2.1

import UM 1.2 as UM
import Cura 1.0 as Cura

Cura.Menu
{
    Cura.Menu
    {
        id: meshToolsMenu

        title: catalog.i18nc("@item:inmenu", "Mesh Tools")

        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Reload model")
            enabled: UM.Selection.selectionCount == 1
            onTriggered: manager.reloadMesh()
        }
        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Rename model...")
            enabled: UM.Selection.selectionCount == 1
            onTriggered: manager.renameMesh()
        }
        Cura.MenuItem
        {
            text: catalog.i18ncp("@item:inmenu", "Replace model...", "Replace models...", UM.Selection.selectionCount)
            enabled: UM.Selection.hasSelection
            onTriggered: manager.replaceMeshes()
        }
        Cura.MenuSeparator {}
        Cura.MenuItem
        {
            text: catalog.i18ncp("@item:inmenu", "Check mesh", "Check meshes", UM.Selection.selectionCount)
            enabled: UM.Selection.hasSelection
            onTriggered: manager.checkMeshes()
        }
        Cura.MenuItem
        {
            text: catalog.i18ncp("@item:inmenu", "Analyse mesh", "Analyse meshes", UM.Selection.selectionCount)
            enabled: UM.Selection.hasSelection
            onTriggered: manager.analyseMeshes()
        }
        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Fix simple holes")
            enabled: UM.Selection.hasSelection
            onTriggered: manager.fixSimpleHolesForMeshes()
        }
        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Fix model normals")
            enabled: UM.Selection.hasSelection
            onTriggered: manager.fixNormalsForMeshes()
        }
        Cura.MenuItem
        {
            text: catalog.i18ncp("@item:inmenu", "Split model into parts", "Split models into parts", UM.Selection.selectionCount)
            enabled: UM.Selection.hasSelection
            onTriggered: manager.splitMeshes()
        }
        Cura.MenuSeparator {}
        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Randomise location")
            enabled: UM.Selection.hasSelection
            onTriggered: manager.randomiseMeshLocation()
        }
        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Apply transformations to mesh")
            enabled: UM.Selection.hasSelection
            onTriggered: manager.bakeMeshTransformation()
        }
        Cura.MenuItem
        {
            text: catalog.i18nc("@item:inmenu", "Reset origin to center of mesh")
            enabled: UM.Selection.hasSelection
            onTriggered: manager.resetMeshOrigin()
        }
    }
    Cura.MenuSeparator
    {
        id: meshToolsSeparator
    }

    function moveToContextMenu(contextMenu)
    {
        contextMenu.insertItem(0, meshToolsSeparator)
        contextMenu.insertMenu(0, meshToolsMenu)
    }

    UM.I18nCatalog { id: catalog; name: "meshtools" }
}
