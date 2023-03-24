// Copyright (c) 2019 Ultimaker B.V.
// Copyright (c) 2023 Aldo Hoeben / fieldOfView
// Uranium is released under the terms of the LGPLv3 or higher.

import QtQuick 2.1
import QtQuick.Controls 2.0

import UM 1.5 as UM
import Cura 1.0 as Cura

UM.Dialog
{
    id: base

    function setName(new_name) {
        nameField.text = new_name;
        nameField.selectAll();
        nameField.forceActiveFocus();
    }

    buttonSpacing: UM.Theme.getSize("default_margin").width

    property bool validName: true
    property string validationError
    property string dialogTitle: catalog.i18nc("@title:window", "Rename")
    property string explanation: catalog.i18nc("@info", "Please provide a new name.")

    title: dialogTitle

    minimumWidth: UM.Theme.getSize("small_popup_dialog").width
    minimumHeight: UM.Theme.getSize("small_popup_dialog").height
    width: minimumWidth
    height: minimumHeight

    property variant catalog: UM.I18nCatalog { name: "uranium" }

    onAccepted:
    {
        manager.setSelectedMeshName(nameField.text)
    }

    Column
    {
        anchors.fill: parent

        UM.Label
        {
            text: base.explanation + "\n" //Newline to make some space using system theming.
            width: parent.width
            wrapMode: Text.WordWrap
        }

        Cura.TextField
        {
            id: nameField
            width: parent.width
            text: base.object
            maximumLength: 40
        }
    }

    rightButtons: [
        Cura.SecondaryButton
        {
            id: cancelButton
            text: catalog.i18nc("@action:button","Cancel")
            onClicked: base.reject()
        },
        Cura.PrimaryButton
        {
            id: okButton
            text: catalog.i18nc("@action:button", "OK")
            onClicked: base.accept()
            enabled: base.validName
        }
    ]
}

