# Copyright (c) 2023 Aldo Hoeben / fieldOfView
# MeshTools is released under the terms of the AGPLv3 or higher.

try:
    from cura.ApplicationMetadata import CuraSDKVersion
except ImportError:  # Cura <= 3.6
    CuraSDKVersion = "6.0.0"
USE_QT5 = False
if CuraSDKVersion >= "8.0.0":
    from PyQt6.QtCore import pyqtSlot, QObject
    from PyQt6.QtWidgets import QFileDialog
else:
    from PyQt5.QtCore import pyqtSlot, QObject
    from PyQt5.QtWidgets import QFileDialog
    USE_QT5 = True

from cura.CuraApplication import CuraApplication
from UM.Extension import Extension
from UM.PluginRegistry import PluginRegistry
from UM.Message import Message
from UM.Logger import Logger

from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.SetTransformOperation import SetTransformOperation
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from UM.Mesh.MeshData import MeshData, calculateNormalsFromIndexedVertices
from UM.Math.AxisAlignedBox import AxisAlignedBox
from UM.Mesh.ReadMeshJob import ReadMeshJob
from UM.Math.Vector import Vector
from UM.Math.Matrix import Matrix
from UM.Resources import Resources
from UM.i18n import i18nCatalog

from .SetTransformMatrixOperation import SetTransformMatrixOperation
from .SetParentOperationSimplified import SetParentOperationSimplified
from .SetMeshDataAndNameOperation import SetMeshDataAndNameOperation

import os
import sys
import numpy
import trimesh
import random

from typing import Optional, List, Dict


class MeshTools(Extension, QObject,):
    def __init__(self, parent = None) -> None:
        QObject.__init__(self, parent)
        Extension.__init__(self)

        Resources.addSearchPath(
            os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                "resources"
            )
        )  # Plugin translation file import
        self._catalog = i18nCatalog("meshtools")

        self._qml_folder = "qml_qt6" if not USE_QT5 else "qml_qt5"

        self._application = CuraApplication.getInstance()

        self._application.engineCreatedSignal.connect(self._onEngineCreated)
        self._application.fileLoaded.connect(self._onFileLoaded)
        self._application.fileCompleted.connect(self._onFileCompleted)

        self._controller = self._application.getController()
        self._controller.getScene().sceneChanged.connect(self._onSceneChanged)

        self._currently_loading_files = []  # type: List[str]
        self._node_queue = []  # type: List[SceneNode]
        self._mesh_not_watertight_messages = {}  # type: Dict[str, Message]

        self._settings_dialog = None
        self._rename_dialog = None

        self._preferences = self._application.getPreferences()
        self._preferences.addPreference("meshtools/check_models_on_load", True)
        self._preferences.addPreference("meshtools/fix_normals_on_load", False)
        self._preferences.addPreference("meshtools/randomise_location_on_load", False)
        self._preferences.addPreference("meshtools/model_unit_factor", 1)

        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Reload model"), self.reloadMesh)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Rename model..."), self.renameMesh)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Replace models..."), self.replaceMeshes)
        self.addMenuItem("", lambda: None)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Check models"), self.checkMeshes)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Analyse models"), self.analyseMeshes)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Fix simple holes"), self.fixSimpleHolesForMeshes)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Fix model normals"), self.fixNormalsForMeshes)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Split model into parts"), self.splitMeshes)
        self.addMenuItem(" ", lambda: None)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Randomise location"), self.randomiseMeshLocation)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Apply transformations to mesh"), self.bakeMeshTransformation)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Reset origin to center of mesh"), self.resetMeshOrigin)
        self.addMenuItem("  ", lambda: None)
        self.addMenuItem(self._catalog.i18nc("@item:inmenu", "Mesh Tools settings..."), self.showSettingsDialog)

        self._message = Message(title=self._catalog.i18nc("@info:title", "Mesh Tools"))
        self._additional_menu = None  # type: Optional[QObject]

    def showSettingsDialog(self) -> None:
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "resources",
            self._qml_folder,
            "SettingsDialog.qml"
        )

        self._settings_dialog = self._application.createQmlComponent(path, {"manager": self})
        if self._settings_dialog:
            self._settings_dialog.show()

    def _onEngineCreated(self) -> None:
        # To add items to the ContextMenu, we need access to the QML engine
        # There is no way to access the context menu directly, so we have to search for it
        main_window = self._application.getMainWindow()
        if not main_window:
            return

        context_menu = None
        for child in main_window.contentItem().children():
            try:
                if not USE_QT5:
                    test = child.handleVisibility  # With QtQuick Controls 2, ContextMenu is the only item that has a findItemIndex function in the main window root contentitem
                else:
                    test = child.findItemIndex  # With QtQuick Controls 1, ContextMenu is the only item that has a findItemIndex function
                context_menu = child
                break
            except:
                pass

        if not context_menu:
            Logger.log("w", "Could not find the viewport context menu")
            return

        Logger.log("d", "Inserting item in context menu")
        qml_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "resources",
            self._qml_folder,
            "MeshToolsMenu.qml"
        )
        self._additional_menu = self._application.createQmlComponent(qml_path, {"manager": self})
        if not self._additional_menu:
            return

        if USE_QT5:
            context_menu.insertSeparator(0)
            context_menu.insertMenu(0, self._catalog.i18nc("@info:title", "Mesh Tools"))

        # Move additional menu items into context menu
        self._additional_menu.moveToContextMenu(context_menu)

    def _onFileLoaded(self, file_name) -> None:
        self._currently_loading_files.append(file_name)

    def _onFileCompleted(self, file_name) -> None:
        if file_name in self._currently_loading_files:
            self._currently_loading_files.remove(file_name)

    def _onSceneChanged(self, node) -> None:
        if not node or not node.getMeshData():
            return

        # only check meshes that have just been loaded
        if node.getMeshData().getFileName() not in self._currently_loading_files:
            return

        # the scene may change multiple times while loading a mesh,
        # but we want to process the mesh only once
        if node not in self._node_queue:
            self._node_queue.append(node)
            self._application.callLater(self.checkQueuedNodes)

    def checkQueuedNodes(self) -> None:
        global_container_stack = self._application.getGlobalContainerStack()
        if global_container_stack:
            disallowed_edge = self._application.getBuildVolume().getEdgeDisallowedSize() + 2  # Allow for some rounding errors
            max_x_coordinate = (global_container_stack.getProperty("machine_width", "value") / 2) - disallowed_edge
            max_y_coordinate = (global_container_stack.getProperty("machine_depth", "value") / 2) - disallowed_edge

        for node in self._node_queue:
            mesh_data = node.getMeshData()
            if not mesh_data:
                continue
            file_name = mesh_data.getFileName()

            if self._preferences.getValue("meshtools/randomise_location_on_load") and global_container_stack != None:
                if file_name and os.path.splitext(file_name)[1].lower() == ".3mf": # don't randomise project files
                    continue

                node_bounds = node.getBoundingBox()
                position = self._randomLocation(node_bounds, max_x_coordinate, max_y_coordinate)
                node.setPosition(position)

            if (
                self._preferences.getValue("meshtools/check_models_on_load") or
                self._preferences.getValue("meshtools/fix_normals_on_load") or
                self._preferences.getValue("meshtools/model_unit_factor") != 1
            ):

                tri_node = self._toTriMesh(mesh_data)

            if self._preferences.getValue("meshtools/model_unit_factor") != 1:
                if file_name and os.path.splitext(file_name)[1].lower() not in [".stl", ".obj", ".ply"]:
                    # only resize models that don't have an intrinsic unit set
                    continue

                scale_matrix = Matrix()
                scale_matrix.setByScaleFactor(float(self._preferences.getValue("meshtools/model_unit_factor")))
                tri_node.apply_transform(scale_matrix.getData())

                self._replaceSceneNode(node, [tri_node])

            if self._preferences.getValue("meshtools/check_models_on_load") and not tri_node.is_watertight:
                if not file_name:
                    file_name = self._catalog.i18nc("@text Print job name", "Untitled")
                base_name = os.path.basename(file_name)

                if file_name in self._mesh_not_watertight_messages:
                    self._mesh_not_watertight_messages[file_name].hide()

                message = Message(title=self._catalog.i18nc("@info:title", "Mesh Tools"))
                body = self._catalog.i18nc("@info:status", "Model %s is not watertight, and may not print properly.") % base_name

                # XRayView may not be available if the plugin has been disabled
                active_view = self._controller.getActiveView()
                if active_view and "XRayView" in self._controller.getAllViews() and active_view.getPluginId() != "XRayView":
                    body += " " + self._catalog.i18nc("@info:status", "Check X-Ray View and repair the model before printing it.")
                    message.addAction("X-Ray", self._catalog.i18nc("@action:button", "Show X-Ray View"), "", "")
                    message.actionTriggered.connect(self._showXRayView)
                else:
                    body += " " +self._catalog.i18nc("@info:status", "Repair the model before printing it.")

                message.setText(body)
                message.show()

                self._mesh_not_watertight_messages[file_name] = message

            if self._preferences.getValue("meshtools/fix_normals_on_load") and tri_node.is_watertight:
                tri_node.fix_normals()
                self._replaceSceneNode(node, [tri_node])

        self._node_queue = []

    def _showXRayView(self, message, action) -> None:
        try:
            major_api_version = self._application.getAPIVersion().getMajor()
        except AttributeError:
            # UM.Application.getAPIVersion was added for API > 6 (Cura 4)
            # Since this plugin version is only compatible with Cura 3.5 and newer, it is safe to assume API 5
            major_api_version = 5

        if major_api_version >= 6 and "SidebarGUIPlugin" not in PluginRegistry.getInstance().getActivePlugins():
            # in Cura 4.x, X-Ray view is in the preview stage
            self._controller.setActiveStage("PreviewStage")
        else:
            # in Cura 3.x, and in 4.x with the Sidebar GUI Plugin, X-Ray view is in the prepare stage
            self._controller.setActiveStage("PrepareStage")

        self._controller.setActiveView("XRayView")
        message.hide()

    def _getSelectedNodes(self, force_single = False) -> List[SceneNode]:
        self._message.hide()
        selection = Selection.getAllSelectedObjects()[:]
        if force_single:
            if len(selection) == 1:
                return selection[:]

            self._message.setText(self._catalog.i18nc("@info:status", "Please select a single model first"))
        else:
            if len(selection) >= 1:
                return selection[:]

            self._message.setText(self._catalog.i18nc("@info:status", "Please select one or more models first"))

        self._message.show()
        return []

    def _getAllSelectedNodes(self) -> List[SceneNode]:
        self._message.hide()
        selection = Selection.getAllSelectedObjects()[:]
        if selection:
            deep_selection = []  # type: List[SceneNode]
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() != None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        self._message.setText(self._catalog.i18nc("@info:status", "Please select one or more models first"))
        self._message.show()

        return []

    @pyqtSlot()
    def checkMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        message_body = self._catalog.i18nc("@info:status", "Check summary:")
        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            message_body = message_body + "\n - %s" % node.getName()
            if tri_node.is_watertight:
                message_body = message_body + " " + self._catalog.i18nc("@info:status", "is watertight")
            else:
                message_body = message_body + " " + self._catalog.i18nc("@info:status", "is not watertight and may not print properly")
            if tri_node.body_count > 1:
                message_body = message_body + " " + self._catalog.i18nc("@info:status", "and consists of {body_count} submeshes").format(body_count = tri_node.body_count)

        self._message.setText(message_body)
        self._message.show()

    @pyqtSlot()
    def analyseMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        message_body = self._catalog.i18nc("@info:status", "Analysis summary:")
        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshDataTransformed())
            message_body = message_body + "\n - %s:" % node.getName()
            message_body += "\n\t" + self._catalog.i18nc("@info:status", "%d vertices, %d faces") % (len(tri_node.vertices), len(tri_node.faces))
            if tri_node.is_watertight:
                message_body += "\n\t" + self._catalog.i18nc("@info:status", "area: %d mm2, volume: %d mm3") % (tri_node.area, tri_node.volume)

        self._message.setText(message_body)
        self._message.show()

    @pyqtSlot()
    def fixSimpleHolesForMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            success = tri_node.fill_holes()
            self._replaceSceneNode(node, [tri_node])
            if not success:
                self._message.setText(self._catalog.i18nc(
                    "@info:status",
                    "The mesh needs more extensive repair to become watertight"
                ))
                self._message.show()

    @pyqtSlot()
    def fixNormalsForMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        for node in nodes_list:
            tri_node = self._toTriMesh(node.getMeshData())
            tri_node.fix_normals()
            self._replaceSceneNode(node, [tri_node])

    @pyqtSlot()
    def splitMeshes(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        message_body = self._catalog.i18nc("@info:status", "Split result:")
        for node in nodes_list:
            message_body = message_body + "\n - %s" % node.getName()
            tri_node = self._toTriMesh(node.getMeshData())
            if tri_node.body_count > 1:
                self._replaceSceneNode(node, tri_node.split(only_watertight=False))
                message_body = message_body + " " + self._catalog.i18nc("@info:status", "was split in %d submeshes") % tri_node.body_count
            else:
                message_body = message_body + " " + self._catalog.i18nc("@info:status", "could not be split into submeshes")

        self._message.setText(message_body)
        self._message.show()

    @pyqtSlot()
    def replaceMeshes(self) -> None:
        self._node_queue = self._getSelectedNodes()
        if not self._node_queue:
            return

        for node in self._node_queue:
            mesh_data = node.getMeshData()
            if not mesh_data:
                self._message.setText(self._catalog.i18nc("@info:status", "Replacing a group is not supported"))
                self._message.show()
                self._node_queue = [] #type: List[SceneNode]
                return

        directory = None  # type: Optional[str]
        mesh_data = self._node_queue[0].getMeshData()
        if mesh_data:
            directory = mesh_data.getFileName()
        if not directory:
            directory = self._application.getDefaultPath("dialog_load_path").toLocalFile()

        file_name = ""
        if USE_QT5:
            options = QFileDialog.Options()
            if sys.platform == "linux" and "KDE_FULL_SESSION" in os.environ:
                options |= QFileDialog.DontUseNativeDialog
            filter_types = ";;".join(self._application.getMeshFileHandler().supportedReadFileTypes)

            file_name, _ = QFileDialog.getOpenFileName(
                parent=None,
                caption=self._catalog.i18nc("@title:window", "Select Replacement Mesh File"),
                directory=directory, options=options, filter=filter_types
            )
        else:
            dialog = QFileDialog()
            dialog.setWindowTitle(self._catalog.i18nc("@title:window", "Select Replacement Mesh File"))
            dialog.setDirectory(directory)
            dialog.setNameFilters(self._application.getMeshFileHandler().supportedReadFileTypes)
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            if dialog.exec():
                file_name = dialog.selectedFiles()[0]

        if not file_name:
            self._node_queue = [] #type: List[SceneNode]
            return

        job = ReadMeshJob(file_name)
        job.finished.connect(self._readMeshFinished)
        job.start()

    @pyqtSlot()
    def renameMesh(self) -> None:
        self._node_queue = self._getSelectedNodes(force_single=True)
        if not self._node_queue:
            return

        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "resources",
            self._qml_folder,
            "RenameDialog.qml"
        )
        self._rename_dialog = self._application.createQmlComponent(path, {"manager": self})
        if not self._rename_dialog:
            return
        self._rename_dialog.show()
        self._rename_dialog.setName(self._node_queue[0].getName())

    @pyqtSlot(str)
    def setSelectedMeshName(self, new_name:str) -> None:
        node = self._node_queue[0]
        node.setName(new_name)
        Selection.remove(node)
        Selection.add(node)

    @pyqtSlot()
    def reloadMesh(self) -> None:
        self._node_queue = self._getSelectedNodes(force_single=True)
        if not self._node_queue:
            return

        mesh_data = self._node_queue[0].getMeshData()
        if not mesh_data:
            self._message.setText(self._catalog.i18nc("@info:status", "Reloading a group is not supported"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        file_name = mesh_data.getFileName()
        if not file_name:
            self._message.setText(self._catalog.i18nc("@info:status", "No link to the original file was found"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        job = ReadMeshJob(file_name)
        job.finished.connect(self._readMeshFinished)
        job.start()

    def _readMeshFinished(self, job) -> None:
        job_result = job.getResult()
        if len(job_result) == 0:
            self._message.setText(self._catalog.i18nc("@info:status", "Failed to load mesh"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        mesh_data = job_result[0].getMeshData()
        if not mesh_data:
            self._message.setText(self._catalog.i18nc("@info:status", "Replacing meshes with a group of meshes is not supported"))
            self._message.show()
            self._node_queue = [] #type: List[SceneNode]
            return

        file_name = mesh_data.getFileName()
        if file_name:
            mesh_name = os.path.basename(file_name)
        else:
            mesh_name = self._catalog.i18nc("@text Print job name", "Untitled")

        has_merged_nodes = False

        op = GroupedOperation()
        for node in self._node_queue:
            op.addOperation(SetMeshDataAndNameOperation(node, mesh_data, mesh_name))

            if not isinstance(node, CuraSceneNode) or not node.getMeshData():
                if node.getName() == "MergedMesh":
                    has_merged_nodes = True
        op.push()

        if has_merged_nodes:
            self._application.updateOriginOfMergedMeshes(None)

        self._node_queue = [] #type: List[SceneNode]

    @pyqtSlot()
    def randomiseMeshLocation(self) -> None:
        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            return

        global_container_stack = self._application.getGlobalContainerStack()
        if not global_container_stack:
            return

        disallowed_edge = self._application.getBuildVolume().getEdgeDisallowedSize() + 2  # Allow for some rounding errors
        max_x_coordinate = (global_container_stack.getProperty("machine_width", "value") / 2) - disallowed_edge
        max_y_coordinate = (global_container_stack.getProperty("machine_depth", "value") / 2) - disallowed_edge

        op = GroupedOperation()
        for node in nodes_list:
            node_bounds = node.getBoundingBox()
            position = self._randomLocation(node_bounds, max_x_coordinate, max_y_coordinate)
            op.addOperation(SetTransformOperation(node, translation=position))
        op.push()

    def _randomLocation(self, node_bounds, max_x_coordinate, max_y_coordinate):
        return Vector(
            (2 * random.random() - 1) * (max_x_coordinate - (node_bounds.width / 2)),
            node_bounds.height / 2,
            (2 * random.random() - 1) * (max_y_coordinate - (node_bounds.depth / 2))
        )

    @pyqtSlot()
    def bakeMeshTransformation(self) -> None:
        nodes_list = self._getSelectedNodes()
        if not nodes_list:
            return

        op = GroupedOperation()
        for node in nodes_list:
            mesh_data = node.getMeshData()
            if not mesh_data:
                continue
            mesh_name = node.getName()
            if not mesh_name:
                file_name = mesh_data.getFileName()
                if not file_name:
                    file_name = ""
                mesh_name = os.path.basename(file_name)
                if not mesh_name:
                    mesh_name = self._catalog.i18nc("@text Print job name", "Untitled")

            local_transformation = node.getLocalTransformation()
            position = local_transformation.getTranslation()
            local_transformation.setTranslation(Vector(0,0,0))
            transformed_mesh_data = mesh_data.getTransformed(local_transformation)
            new_transformation = Matrix()
            new_transformation.setTranslation(position)

            op.addOperation(SetMeshDataAndNameOperation(node, transformed_mesh_data, mesh_name))
            op.addOperation(SetTransformMatrixOperation(node, new_transformation))

        op.push()


    @pyqtSlot()
    def resetMeshOrigin(self) -> None:
        nodes_list = self._getSelectedNodes()
        if not nodes_list:
            return

        op = GroupedOperation()
        for node in nodes_list:
            mesh_data = node.getMeshData()
            if not mesh_data:
                continue

            extents = mesh_data.getExtents()
            center = Vector(extents.center.x, extents.center.y, extents.center.z)

            translation = Matrix()
            translation.setByTranslation(-center)
            transformed_mesh_data = mesh_data.getTransformed(translation).set(zero_position=Vector())

            new_transformation = Matrix(node.getLocalTransformation().getData())  # Matrix.copy() is not available in Cura 3.5-4.0
            new_transformation.translate(center)

            op.addOperation(SetMeshDataAndNameOperation(node, transformed_mesh_data, node.getName()))
            op.addOperation(SetTransformMatrixOperation(node, new_transformation))

        op.push()


    def _replaceSceneNode(self, existing_node, trimeshes) -> None:
        name = existing_node.getName()
        file_name = existing_node.getMeshData().getFileName()
        transformation = existing_node.getWorldTransformation()
        parent = existing_node.getParent()
        extruder_id = existing_node.callDecoration("getActiveExtruder")
        build_plate = existing_node.callDecoration("getBuildPlateNumber")
        selected = Selection.isSelected(existing_node)

        children = existing_node.getChildren()
        new_nodes = []

        op = GroupedOperation()
        op.addOperation(RemoveSceneNodeOperation(existing_node))

        for i, tri_node in enumerate(trimeshes):
            mesh_data = self._toMeshData(tri_node, file_name)

            new_node = CuraSceneNode()
            new_node.setSelectable(True)
            new_node.setMeshData(mesh_data)
            new_node.setName(name if i==0 else "%s %d" % (name, i))
            new_node.callDecoration("setActiveExtruder", extruder_id)
            new_node.addDecorator(BuildPlateDecorator(build_plate))
            new_node.addDecorator(SliceableObjectDecorator())

            op.addOperation(AddSceneNodeOperation(new_node, parent))
            op.addOperation(SetTransformMatrixOperation(new_node, transformation))

            new_nodes.append(new_node)

            if selected:
                Selection.add(new_node)

        for child in children:
            mesh_data = child.getMeshData()
            if not mesh_data:
                continue
            child_bounding_box = mesh_data.getTransformed(child.getWorldTransformation()).getExtents()
            if not child_bounding_box:
                continue
            new_parent = None
            for potential_parent in new_nodes:
                parent_mesh_data = potential_parent.getMeshData()
                if not parent_mesh_data:
                    continue
                parent_bounding_box = parent_mesh_data.getTransformed(potential_parent.getWorldTransformation()).getExtents()
                if not parent_bounding_box:
                    continue
                intersection = child_bounding_box.intersectsBox(parent_bounding_box)
                if intersection != AxisAlignedBox.IntersectionResult.NoIntersection:
                    new_parent = potential_parent
                    break
            if not new_parent:
                new_parent = new_nodes[0]
            op.addOperation(SetParentOperationSimplified(child, new_parent))

        op.push()

    def _toTriMesh(self, mesh_data: Optional[MeshData]) -> trimesh.base.Trimesh:
        if not mesh_data:
            return trimesh.base.Trimesh()

        indices = mesh_data.getIndices()
        if indices is None:
            # some file formats (eg 3mf) don't supply indices, but have unique vertices per face
            indices = numpy.arange(mesh_data.getVertexCount()).reshape(-1, 3)

        return trimesh.base.Trimesh(vertices=mesh_data.getVertices(), faces=indices)

    def _toMeshData(self, tri_node: trimesh.base.Trimesh, file_name: str = "") -> MeshData:
        tri_faces = tri_node.faces
        tri_vertices = tri_node.vertices

        indices = []
        vertices = []

        index_count = 0
        face_count = 0
        for tri_face in tri_faces:
            face = []
            for tri_index in tri_face:
                vertices.append(tri_vertices[tri_index])
                face.append(index_count)
                index_count += 1
            indices.append(face)
            face_count += 1

        vertices = numpy.asarray(vertices, dtype=numpy.float32)
        indices = numpy.asarray(indices, dtype=numpy.int32)
        normals = calculateNormalsFromIndexedVertices(vertices, indices, face_count)

        mesh_data = MeshData(file_name = file_name, vertices=vertices, indices=indices, normals=normals)
        return mesh_data
