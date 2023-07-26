// Copyright (c) 2023 Aldo Hoeben / fieldOfView
// MeshTools is released under the terms of the AGPLv3 or higher.

import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

import UM 1.6 as UM
import Cura 1.7 as Cura


UM.Dialog
{
    id: base

    title: catalog.i18nc("@title:window", "Mesh Tools Settings")

    minimumWidth: 300 * screenScaleFactor
    minimumHeight: contents.implicitHeight + 5 * UM.Theme.getSize("default_margin").height
    width: minimumWidth
    height: minimumHeight

    property variant catalog: UM.I18nCatalog { name: "meshtools" }

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

            UM.CheckBox
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
            text: catalog.i18nc("@info:tooltip", "Always recalculate model normals when loading them")

            UM.CheckBox
            {
                text: catalog.i18nc("@option:check", "Fix normals on load")
                checked: boolCheck(UM.Preferences.getValue("meshtools/fix_normals_on_load"))
                onCheckedChanged: UM.Preferences.setValue("meshtools/fix_normals_on_load", checked)
            }
        }

        // spacer
        Item { height: UM.Theme.getSize("default_margin").height; width: 1 }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: catalog.i18nc("@info:tooltip", "Unit to convert meshes from when the file does not specify a unit (such as STL files). All units will be converted to millimeters.")

            Column
            {
                spacing: 4 * screenScaleFactor

                UM.Label
                {
                    text: catalog.i18nc("@window:text", "Unit for files that don't specify a unit:")
                }

                ListModel
                {
                    id: unitsList
                    Component.onCompleted:
                    {
                        append({ text: catalog.i18nc("@option:unit", "Micron"), factor: 0.001 })
                        append({ text: catalog.i18nc("@option:unit", "Millimeter (default)"), factor: 1 })
                        append({ text: catalog.i18nc("@option:unit", "Centimeter"), factor: 10 })
                        append({ text: catalog.i18nc("@option:unit", "Meter"), factor: 1000 })
                        append({ text: catalog.i18nc("@option:unit", "Inch"), factor: 25.4 })
                        append({ text: catalog.i18nc("@option:unit", "Feet"), factor: 304.8 })
                    }
                }

                Cura.ComboBox
                {
                    id: modelUnitDropDownButton
                    width: 200 * screenScaleFactor

                    textRole: "text"
                    model: unitsList

                    implicitWidth: UM.Theme.getSize("combobox").width
                    implicitHeight: UM.Theme.getSize("combobox").height

                    currentIndex:
                    {
                        var currentChoice = UM.Preferences.getValue("meshtools/model_unit_factor");
                        for(var i = 0; i < unitsList.count; ++i)
                        {
                            if(model.get(i).factor == currentChoice)
                            {
                                return i
                            }
                        }
                    }

                    onActivated:
                    {
                        UM.Preferences.setValue("meshtools/model_unit_factor", model.get(index).factor)
                    }
                }
            }
        }

        // spacer
        Item { height: UM.Theme.getSize("default_margin").height; width: 1 }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: catalog.i18nc("@info:tooltip", "Place models at a random location on the build plate when loading them")

            UM.CheckBox
            {
				id: checkRandom
				enabled: !checkPosition.checked
                text: catalog.i18nc("@option:check", "Randomize position on load")
                checked: boolCheck(UM.Preferences.getValue("meshtools/randomise_location_on_load"))
                onCheckedChanged: UM.Preferences.setValue("meshtools/randomise_location_on_load", checked)
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width
            height: childrenRect.height
            text: catalog.i18nc("@info:tooltip", "Place models at a specific location on the build plate when loading them")

            UM.CheckBox
            {
				id: checkPosition
				enabled: !checkRandom.checked
                text: catalog.i18nc("@option:check", "Set position on load")
                checked: boolCheck(UM.Preferences.getValue("meshtools/set_location_on_load"))
                onCheckedChanged: UM.Preferences.setValue("meshtools/set_location_on_load", checked)
            }
        }
		
		UM.TooltipArea
		{
			width: childrenRect.width
			height: childrenRect.height
			text: catalog.i18nc("@info:tooltip", "X position relative / Bed Center")
			
			UM.Label
			{
				id: label_X				
				text: catalog.i18nc("@label:text", "X position")
			}
			UM.TextFieldWithUnit
			{
				width: UM.Theme.getSize("setting_control").width
				height: UM.Theme.getSize("setting_control").height		
				unit: "mm"
				text: UM.Preferences.getValue("meshtools/set_location_x")
				
				anchors.left: label_X.right

				validator: DoubleValidator
				{
					decimals: 1
					locale: "en_US"
				}
				
				onEditingFinished:
				{
					var modified_text = text.replace(",", ".") // User convenience. We use dots for decimal values
					UM.Preferences.setValue("meshtools/set_location_x", modified_text)
				}				
			}
		}
		UM.TooltipArea
		{
			width: childrenRect.width
			height: childrenRect.height
			text: catalog.i18nc("@info:tooltip", "Y position relative / Bed Center")
				
			UM.Label
			{
				id: label_Y
				text: catalog.i18nc("@label:text", "Y position")
			}
			UM.TextFieldWithUnit
			{
				width: UM.Theme.getSize("setting_control").width
				height: UM.Theme.getSize("setting_control").height
				unit: "mm"
				text: UM.Preferences.getValue("meshtools/set_location_y")
				
				anchors.left: label_Y.right

				validator: DoubleValidator
				{
					decimals: 1
					locale: "en_US"
				}
			
				onEditingFinished:
				{
					var modified_text = text.replace(",", ".") // User convenience. We use dots for decimal values
					UM.Preferences.setValue("meshtools/set_location_y", modified_text)
				}				
			}

		}				
		
    }

    rightButtons: [
        Cura.PrimaryButton
        {
            id: cancelButton
            text: catalog.i18nc("@action:button","Close")
            onClicked: base.reject()
        }
    ]
}

