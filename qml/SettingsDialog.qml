// Copyright (c) 2020 Aldo Hoeben / fieldOfView
// MeshTools is released under the terms of the AGPLv3 or higher.

import QtQuick 2.1
import QtQuick.Controls 1.1
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.1

import UM 1.3 as UM
import Cura 1.0 as Cura


UM.Dialog
{
    id: base

    title: catalog.i18nc("@title:window", "Mesh Tools Settings")

    minimumWidth: 300 * screenScaleFactor
    minimumHeight: contents.implicitHeight + 3 * UM.Theme.getSize("default_margin").height
    width: minimumWidth
    height: minimumHeight

    property variant catalog: UM.I18nCatalog { name: "cura" }

    function boolCheck(value) //Hack to ensure a good match between python and qml.
    {
        if(value == "True")
        {
            return true
        }else if(value == "False" || value == undefined)
        {
            return false
        }
        else
        {
            return value
        }
    }

    Column
    {
        id: contents
        anchors.fill: parent
        spacing: UM.Theme.getSize("default_lining").height

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: catalog.i18nc("@info:tooltip", "Check if models are watertight when loading them")

            CheckBox
            {
                text: catalog.i18nc("@option:check", "Check models on load")
                checked: boolCheck(UM.Preferences.getValue("meshtools/check_models_on_load"))
                onCheckedChanged: UM.Preferences.setValue("meshtools/check_models_on_load", checked)
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: catalog.i18nc("@info:tooltip", "Always recalculate models when loading them")

            CheckBox
            {
                text: catalog.i18nc("@option:check", "Fix normals on load")
                checked: boolCheck(UM.Preferences.getValue("meshtools/fix_normals_on_load"))
                onCheckedChanged: UM.Preferences.setValue("meshtools/fix_normals_on_load", checked)
            }
        }
    }

    rightButtons: [
        Button
        {
            id: cancelButton
            text: catalog.i18nc("@action:button","Close")
            onClicked: base.reject()
        }
    ]
}

