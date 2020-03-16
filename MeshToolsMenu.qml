// Copyright (c) 2016 Ultimaker B.V.
// Cura is released under the terms of the LGPLv3 or higher.

import QtQuick 2.2
import QtQuick.Controls 1.1
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.1

import UM 1.2 as UM
import Cura 1.0 as Cura

Menu
{
    id: base

    title: catalog.i18nc("@title:menu", "Mesh Tools")

    MenuItem
    {
        text: catalog.i18ncp("@label", "Replace model...", "Replace models...", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.replaceMeshes()
    }
    MenuSeparator {}
    MenuItem
    {
        text: catalog.i18ncp("@label", "Check mesh", "Check meshes", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.checkMeshes()
    }
    MenuItem
    {
        text: catalog.i18nc("@label", "Fix simple holes")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.fixSimpleHolesForMeshes()
    }
    MenuItem
    {
        text: catalog.i18nc("@label", "Fix model normals")
        enabled: UM.Selection.hasSelection
        onTriggered: manager.fixNormalsForMeshes()
    }
    MenuItem
    {
        text: catalog.i18ncp("@label", "Split model into parts", "Split models into parts", UM.Selection.selectionCount)
        enabled: UM.Selection.hasSelection
        onTriggered: manager.splitMeshes()
    }

    function moveToContextMenu(contextMenu, itemIndex)
    {
        for(var i in base.items)
        {
            contextMenu.items[itemIndex].insertItem(i,base.items[i])
        }
    }

    UM.I18nCatalog { id: catalog; name: "cura" }
}
