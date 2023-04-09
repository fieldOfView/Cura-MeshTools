// Copyright (c) 2023 Aldo Hoeben / fieldOfView
// MeshTools is released under the terms of the AGPLv3 or higher.

import QtQuick 2.2
import QtQuick.Controls 1.1
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.1

import UM 1.2 as UM
import Cura 1.0 as Cura

Menu
{
    id: base

    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Reload model")
        enabled: UM.Selection.selectionCount == 1
        onTriggered: manager.reloadMesh()
    }
    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Rename model...")
        enabled: UM.Selection.selectionCount == 1
        onTriggered: manager.renameMesh()
    }
    MenuItem
    {
        text: catalog.i18ncp("@item:inmenu", "Replace model...", "Replace models...", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.replaceMeshes()
    }
    MenuSeparator {}
    MenuItem
    {
        text: catalog.i18ncp("@item:inmenu", "Check mesh", "Check meshes", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.checkMeshes()
    }
    MenuItem
    {
        text: catalog.i18ncp("@item:inmenu", "Analyse mesh", "Analyse meshes", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.analyseMeshes()
    }
    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Fix simple holes")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.fixSimpleHolesForMeshes()
    }
    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Fix model normals")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.fixNormalsForMeshes()
    }
    MenuItem
    {
        text: catalog.i18ncp("@item:inmenu", "Split model into parts", "Split models into parts", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.splitMeshes()
    }
    MenuSeparator {}
    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Randomise location")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.randomiseMeshLocation()
    }
    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Apply transformations to mesh")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.bakeMeshTransformation()
    }
    MenuItem
    {
        text: catalog.i18nc("@item:inmenu", "Reset origin to center of mesh")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.resetMeshOrigin()
    }

    function moveToContextMenu(contextMenu)
    {
        for(var i in base.items)
        {
            contextMenu.items[0].insertItem(i,base.items[i])
        }
    }

    UM.I18nCatalog { id: catalog; name: "meshtools" }
}
